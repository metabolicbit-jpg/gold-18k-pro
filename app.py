# ========== Gold18K Pro · app_v3.py ==========
# 📂 مسیر ریپو: app_v3.py
# نسخهٔ ۳.۲.۰ — نمایشی و بدون ارسال.
# تازه: جهت و احتمال همیشه هم‌جهت‌اند (رفع تناقض ۵۸٪ صعودی با امتیاز منفی)،
# عناوین «چرا این تصمیم» بر اساس نتیجه، رژیم از شیب واقعی، و افق یک‌ساعتهٔ زنده از کندل ۵ دقیقه‌ای.
# فایل‌های همراه: collector.py (جمع‌آورِ کندل) · intraday.py (موتور افق ساعتی)
# وابستگی: streamlit>=1.41, requests, pandas, numpy, plotly, jdatetime

from __future__ import annotations

import math
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import intraday as intr
except Exception:  # اگر فایل همراه در ریپو نبود، برنامه به تخمینِ روزانه برمی‌گردد
    intr = None

# ═══════════════ ۱) پیکربندی ═══════════════

APP = "Gold18K Pro"
VERSION = "3.2.0"
BUILD = "1405-08-06"

LIVE_API = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/popular.json"
HISTORY_USD = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/USD_IRR_FREE.json"
HISTORY_GOLD18 = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/GOLD_18K_IRR.json"
METAL_API = "https://api.gold-api.com/price/{}"

OUNCE_GRAM = 31.1034768
FINENESS_18K = 0.750

CFG = {
    "horizon_days": 3,
    "cost_pct": 0.45,
    "cost_mult": 1.15,
    "risk_pct": 1.0,
    "stop_sigma": 1.5,
    "target_sigma": 2.5,
    "z_win": 60,
    "ew_span": 40,
    "knn_k": 40,
    "knn_min": 12,
    "shrink": 15,
    "z80": 1.2816,
    "max_conf": 84.0,
    "prem_mean_default": 1.5,
    "prem_sd_default": 2.8,
    "fallback_sigma": 0.012,
    "min_days_reliable": 60,
    "min_trades_reliable": 20,
    "min_bars_ready": 864,
    "ticks_per_day": 288,
}

STRATS = {"trend": "روند", "break": "شکست کانال", "value": "ارزش نسبی", "fx": "کانال ارزی"}
ROLE = {"trend": "مومنتوم زمانی", "break": "شکست کانال ۲۰ روزه",
        "value": "بازگشت نسبت طلا/دلار", "fx": "سرایت نرخ دلار"}

UA = {"User-Agent": "Gold18K-Pro/3.2"}

# ═══════════════ ۲) ابزار ═══════════════


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def jalali(dt: datetime | None = None):
    dt = dt or datetime.now()
    try:
        import jdatetime

        j = jdatetime.datetime.fromgregorian(datetime=dt)
        return j.strftime("%Y/%m/%d"), j.strftime("%H:%M")
    except Exception:
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def safe_float(v, default=None):
    try:
        if v is None:
            return default
        f = float(str(v).replace(",", "").strip())
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default


def fmt(v, d: int = 0) -> str:
    try:
        return "—" if v is None else f"{v:,.{d}f}"
    except Exception:
        return "—"


def pc(v, d: int = 2) -> str:
    return "—" if v is None else f"{v:+.{d}f}٪"


def scr(msg) -> str:
    return re.sub(r"https?://[^\s'\"]+", "<آدرس پنهان>", str(msg))[:240]


def age_txt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        s = (now_utc() - dt).total_seconds()
        return "همین حالا" if s < 0 else (f"{s:.0f} ثانیه پیش" if s < 90 else f"{s / 60:.0f} دقیقه پیش")
    except Exception:
        return "—"


def _digits(s: str) -> str:
    return str(s).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _dt(v):
    if v is None:
        return pd.NaT
    s = _digits(v).strip()
    if not s:
        return pd.NaT
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = mm = 0
        tm = re.search(r"(\d{1,2}):(\d{2})", s[m.end():])
        if tm:
            hh, mm = int(tm.group(1)), int(tm.group(2))
        if 1300 <= y <= 1500:
            try:
                import jdatetime

                g = jdatetime.date(y, mo, dd).togregorian()
                return pd.Timestamp(g.year, g.month, g.day, hh, mm)
            except Exception:
                return pd.NaT
        try:
            return pd.Timestamp(y, mo, dd, hh, mm)
        except Exception:
            return pd.NaT
    try:
        return pd.Timestamp(s)
    except Exception:
        return pd.NaT


def _pick(df, cands):
    low = {str(c).lower(): c for c in df.columns}
    for c in cands:
        if c in low:
            return low[c]
    return None


# ═══════════════ ۳) انبار سبک ═══════════════


class Store:
    def __init__(self, path: str | None = None):
        self.path = self._resolve(path or os.getenv("GOLD18K_DB", "data/gold18k.db"))
        try:
            with closing(sqlite3.connect(self.path)) as c:
                c.execute(
                    "CREATE TABLE IF NOT EXISTS ticks(id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " ts TEXT, usd REAL, gold18 REAL, ounce REAL, silver REAL, copper REAL)"
                )
                c.commit()
        except Exception:
            pass

    @staticmethod
    def _resolve(p: str) -> str:
        for cand in (p, "/tmp/gold18k_pro.db", ":memory:"):
            try:
                if cand == ":memory:":
                    return cand
                fp = os.path.abspath(cand)
                os.makedirs(os.path.dirname(fp) or ".", exist_ok=True)
                sqlite3.connect(fp).close()
                return fp
            except Exception:
                continue
        return ":memory:"

    def _con(self):
        con = sqlite3.connect(self.path, timeout=8)
        con.row_factory = sqlite3.Row
        return con

    def add_tick(self, live: dict):
        g = safe_float((live.get("gold18") or {}).get("price"))
        if not g:
            return
        try:
            with closing(self._con()) as c:
                last = c.execute("SELECT ts, gold18 FROM ticks ORDER BY id DESC LIMIT 1").fetchone()
                if last and last["gold18"]:
                    gap = 999
                    try:
                        gap = (now_utc() - datetime.fromisoformat(last["ts"])).total_seconds()
                    except Exception:
                        pass
                    if abs(float(last["gold18"]) - g) / max(g, 1) < 1e-6 and gap < 240:
                        return
                c.execute(
                    "INSERT INTO ticks(ts,usd,gold18,ounce,silver,copper) VALUES(?,?,?,?,?,?)",
                    (
                        now_utc().isoformat(timespec="seconds"),
                        safe_float((live.get("usd") or {}).get("price")),
                        g,
                        safe_float((live.get("ounce") or {}).get("price")),
                        safe_float((live.get("silver") or {}).get("price")),
                        safe_float((live.get("copper") or {}).get("price")),
                    ),
                )
                c.commit()
        except Exception:
            pass

    def ticks(self, limit: int = 4000) -> pd.DataFrame:
        try:
            with closing(self._con()) as c:
                rows = c.execute(
                    "SELECT ts,usd,gold18,ounce,silver,copper FROM ticks ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame([dict(r) for r in rows])
            df["dt"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
            return df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)
        except Exception:
            return pd.DataFrame()

    def change(self, col: str, current):
        if current is None:
            return None
        t = self.ticks(limit=600)
        if t.empty or col not in t.columns:
            return None
        s = t.dropna(subset=[col])
        if len(s) < 2:
            return None
        prev = s[(s[col] - current).abs() / max(abs(current), 1) > 1e-6]
        if prev.empty:
            return None
        base = float(prev.iloc[-1][col])
        return (current / base - 1) * 100 if base > 0 else None


@st.cache_resource(show_spinner=False)
def get_store() -> Store:
    return Store()


# ═══════════════ ۴) داده ═══════════════


def _session() -> requests.Session:
    s = requests.Session()
    s.mount(
        "https://",
        HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1.2,
                                      status_forcelist=(429, 500, 502, 503, 504))),
    )
    s.headers.update(UA)
    return s


@st.cache_data(ttl=45, show_spinner=False)
def fetch_live() -> dict:
    out = {"usd": None, "gold18": None, "ounce": None, "silver": None, "copper": None,
           "at": now_utc().isoformat(timespec="seconds"), "errors": []}
    s = _session()
    try:
        r = s.get(LIVE_API, timeout=(5, 12))
        r.raise_for_status()
        for it in (r.json().get("data") or []):
            sym = str(it.get("symbol", ""))
            if sym in ("USD_IRR_FREE", "GOLD_18K_IRR"):
                p = safe_float(it.get("price"))
                if p:
                    out["usd" if sym.startswith("USD") else "gold18"] = {"price": p,
                                                                        "chg": safe_float(it.get("change_pct"))}
    except Exception as e:
        out["errors"].append(f"iran-market: {scr(e)}")
    for k, sym in (("ounce", "XAU"), ("silver", "XAG"), ("copper", "HG")):
        try:
            r = s.get(METAL_API.format(sym), timeout=(4, 8))
            r.raise_for_status()
            p = safe_float(r.json().get("price"))
            if p:
                out[k] = {"price": p}
        except Exception as e:
            out["errors"].append(f"gold-api/{sym}: {scr(e)}")
    return out


@st.cache_data(ttl=600, show_spinner=False)
def fetch_history(days: int = 400):
    def load(url):
        r = _session().get(url, timeout=(6, 15))
        r.raise_for_status()
        df = pd.DataFrame(r.json().get("data") or [])
        if df.empty:
            return None
        dc, cc = _pick(df, ["ts", "timestamp", "datetime", "date_jalali", "date", "day"]), _pick(
            df, ["close", "price", "value", "p"])
        if not dc or not cc:
            return None
        out = pd.DataFrame({"dt": df[dc].map(_dt), "close": pd.to_numeric(df[cc], errors="coerce")}).dropna()
        return out.sort_values("dt") if not out.empty else None

    try:
        u, g = load(HISTORY_USD), load(HISTORY_GOLD18)
        if u is None or g is None:
            return None
        u, g = u.rename(columns={"close": "usd"}), g.rename(columns={"close": "gold18"})
        for d in (u, g):
            d["day"] = d["dt"].dt.normalize()
        u = u.groupby("day", as_index=False).last()[["day", "usd"]]
        g = g.groupby("day", as_index=False).last()[["day", "gold18"]]
        df = pd.merge(g, u, on="day", how="inner").sort_values("day").reset_index(drop=True)
        df = df[(df["gold18"] > 0) & (df["usd"] > 1000)]
        r = df["gold18"].pct_change(fill_method=None)
        df = df[(r.abs() < 0.25) | r.isna()].reset_index(drop=True)
        return df.tail(days)
    except Exception:
        return None


def hist_change(history, col: str):
    try:
        if history is None or len(history) < 2:
            return None
        a, b = float(history[col].iloc[-1]), float(history[col].iloc[-2])
        return (a / b - 1) * 100 if b > 0 else None
    except Exception:
        return None


# ═══════════════ ۵) موتور ═══════════════


def rz(s: pd.Series, win: int = 60) -> pd.Series:
    base = s.shift(1)
    med = base.rolling(win, min_periods=20).median()
    mad = (base - med).abs().rolling(win, min_periods=20).median()
    sd = (mad * 1.4826).replace(0, np.nan)
    return ((s - med) / sd).clip(-3, 3)


def build_panel(h: pd.DataFrame) -> pd.DataFrame:
    d = pd.DataFrame({"day": h["day"], "close": h["gold18"].astype(float), "usd": h["usd"].astype(float)})
    d["ret"] = np.log(d["close"]).diff()
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    d["ema60"] = d["close"].ewm(span=60, adjust=False).mean()
    d["ma20"] = d["close"].rolling(20).mean()
    d["sd20"] = d["close"].rolling(20).std()
    d["sigma"] = d["ret"].ewm(span=12, adjust=False).std()
    d["slope"] = d["ema20"] / d["ema20"].shift(5) - 1
    d["slope_z"] = rz(d["slope"], CFG["z_win"])
    d["ratio"] = d["close"] / d["usd"]
    d["ratio_z"] = rz(d["ratio"], CFG["z_win"])
    d["usd_mom"] = np.log(d["usd"]).diff(5)
    d["usd_ret"] = np.log(d["usd"]).diff()
    d["corr"] = d["ret"].rolling(30, min_periods=15).corr(d["usd_ret"])
    d["hh"] = d["close"].rolling(20).max().shift(1)
    d["ll"] = d["close"].rolling(20).min().shift(1)

    d["s_trend"] = (d["slope_z"] / 2).clip(-1, 1)
    rng = (d["hh"] - d["ll"]).replace(0, np.nan)
    d["s_break"] = ((d["close"] - (d["hh"] + d["ll"]) / 2) / (rng / 2)).clip(-1, 1)
    gate = 1 / (1 + np.exp(1.2 * (d["slope_z"].abs() - 1.2)))
    d["s_value"] = ((-d["ratio_z"] / 1.5).clip(-1, 1)) * gate
    d["s_fx"] = (rz(d["usd_mom"], CFG["z_win"]) / 2).clip(-1, 1) * d["corr"].fillna(0).clip(0, 1)

    H = CFG["horizon_days"]
    d["fwd"] = d["close"].pct_change(H, fill_method=None).shift(-H) * 100

    def skill(col: str) -> pd.Series:
        s = d[col]
        contrib = (np.sign(s) * d["fwd"]).where(s.abs() >= 0.30)
        return contrib.ewm(span=CFG["ew_span"], min_periods=10).mean().shift(H + 1)

    sk = pd.DataFrame({k: skill(f"s_{k}") for k in STRATS})
    w = np.exp(sk.fillna(0.0) * 1.0)
    w = w.div(w.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    d["composite"] = (w.values * d[[f"s_{k}" for k in STRATS]].values).sum(axis=1)
    for k in STRATS:
        d[f"w_{k}"] = w[k].values
        d[f"k_{k}"] = sk[k].values
    return d


def _fallback_prob(comp: np.ndarray) -> np.ndarray:
    """نگاشتِ امتیاز به احتمال؛ همیشه هم‌جهت با علامتِ امتیاز."""
    return 1.0 / (1.0 + np.exp(-1.1 * (comp / 0.6)))


def walk_probability(d: pd.DataFrame):
    """کالیبراسیونِ جهتی: احتمالِ هم‌جهت با امتیاز، هرگز مخالفِ آن. با شرینکِ اندازهٔ نمونه."""
    H = CFG["horizon_days"]
    comp = np.nan_to_num(d["composite"].values, nan=0.0)
    fwd = d["fwd"].values
    n = len(comp)
    p = _fallback_prob(comp).copy()
    used = np.zeros(n, dtype=bool)

    for i in range(n):
        upto = max(0, i - H)
        idx = np.where(~np.isnan(fwd[:upto]))[0]
        if len(idx) < CFG["knn_min"]:
            continue
        k = int(min(CFG["knn_k"], max(10, len(idx) // 6)))
        nn = idx[np.argsort(np.abs(comp[idx] - comp[i]))[:k]]
        hit = float((np.sign(fwd[nn]) == np.sign(comp[i])).mean())
        m = len(nn)
        h = (m / (m + CFG["shrink"])) * hit + (CFG["shrink"] / (m + CFG["shrink"])) * 0.5
        p[i] = 0.5 + np.sign(comp[i]) * (h - 0.5) * 0.9
        used[i] = True

    return pd.Series(np.clip(p, 0.12, 0.88), index=d.index), float(used.mean())


def run_backtest(d: pd.DataFrame, p: pd.Series, horizon: int | None = None) -> dict:
    H = int(horizon or CFG["horizon_days"])
    thr = CFG["cost_pct"] * CFG["cost_mult"]
    sigma_pct = (d["sigma"].fillna(CFG["fallback_sigma"]) * 100).values
    comp = np.nan_to_num(d["composite"].values, nan=0.0)
    pv = p.values
    edge = (2 * pv - 1) * 0.8 * sigma_pct * math.sqrt(H)
    pos = np.where((edge >= thr) & (comp > 0), 1, np.where((edge <= -thr) & (comp < 0), -1, 0))
    close = d["close"].values.astype(float)

    trades, i = [], 0
    while i < len(d) - H:
        if pos[i] != 0:
            ret = (close[i + H] / close[i] - 1) * 100 * pos[i] - CFG["cost_pct"]
            trades.append({"day": d["day"].iloc[i], "side": int(pos[i]), "ret": ret,
                           "p": pv[i], "sigma": sigma_pct[i]})
            i += H
        else:
            i += 1

    tdf = pd.DataFrame(trades)
    empty = {"n": 0, "win": None, "pf": None, "exp": None, "total": None, "dd": None,
             "sharpe": None, "trades": tdf, "equity": pd.Series(dtype=float),
             "pos": pos, "reliable": False, "exposure": float((pos != 0).mean() * 100), "horizon": H}
    if tdf.empty:
        return empty

    eq = (1 + tdf["ret"] / 100).cumprod()
    dd = float(((eq / eq.cummax()) - 1).min() * 100)
    wins, losses = tdf[tdf["ret"] > 0]["ret"], tdf[tdf["ret"] <= 0]["ret"]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else None
    sharpe = (float(tdf["ret"].mean() / tdf["ret"].std() * math.sqrt(252 / H))
              if len(tdf) > 2 and tdf["ret"].std() > 0 else None)
    return {
        "n": len(tdf), "win": float((tdf["ret"] > 0).mean() * 100), "pf": pf,
        "exp": float(tdf["ret"].mean()), "total": float(eq.iloc[-1] - 1) * 100, "dd": dd,
        "sharpe": sharpe, "trades": tdf, "equity": eq, "pos": pos,
        "reliable": len(tdf) >= CFG["min_trades_reliable"],
        "exposure": float((pos != 0).mean() * 100), "horizon": H,
    }


def build_engine(history, live: dict, ticks: pd.DataFrame) -> dict:
    price = safe_float((live.get("gold18") or {}).get("price"))
    usd = safe_float((live.get("usd") or {}).get("price"))
    ounce = safe_float((live.get("ounce") or {}).get("price"))
    res = {"ok": False, "price": price, "usd": usd, "ounce": ounce, "n_days": 0}

    theo = ounce * usd / OUNCE_GRAM * FINENESS_18K if (ounce and usd) else None
    prem = (price - theo) / theo * 100 if (theo and price) else None
    res.update(theo=theo, prem=prem, prem_z=None, prem_est=True)

    if ticks is not None and len(ticks) >= 40 and prem is not None:
        t = ticks.dropna(subset=["gold18", "usd", "ounce"]).copy()
        if len(t) >= 40:
            intr_val = t["ounce"] * t["usd"] / OUNCE_GRAM * FINENESS_18K
            t["prem"] = (t["gold18"] - intr_val) / intr_val * 100
            win = t["prem"].tail(CFG["z_win"])
            med = float(win.median())
            sd = max(float((win - med).abs().median()) * 1.4826, 0.4)
            res.update(prem_z=(prem - med) / sd, prem_est=False, prem_med=med)
    if res["prem_z"] is None and prem is not None:
        res["prem_z"] = (prem - CFG["prem_mean_default"]) / CFG["prem_sd_default"]

    if history is None or len(history) < 40 or not price:
        res["reason"] = ("تاریخ روزانهٔ کافی در دسترس نیست" if history is None or len(history) < 40
                         else "قیمت زنده در دسترس نیست")
        return res

    d = build_panel(history)
    d = d.dropna(subset=["composite"]).reset_index(drop=True)
    if len(d) < 25:
        res["reason"] = "پنجرهٔ معتبر کوتاه است"
        return res

    p, calib_share = walk_probability(d)
    d["p"] = p
    bt = run_backtest(d, p)

    last = d.iloc[-1]
    sigma_d = float(last["sigma"]) if not math.isnan(last["sigma"]) else CFG["fallback_sigma"]
    comp = float(last["composite"])
    p_now = float(p.iloc[-1])
    thr = CFG["cost_pct"] * CFG["cost_mult"]
    edge = (2 * p_now - 1) * 0.8 * sigma_d * 100 * math.sqrt(CFG["horizon_days"])

    if abs(edge) >= thr and comp > 0:
        decision = "خرید"
    elif abs(edge) >= thr and comp < 0:
        decision = "فروش / کاهش"
    else:
        decision = "نظاره"

    denom = 0.8 * sigma_d * 100 * math.sqrt(CFG["horizon_days"])
    p_req = min(0.95, 0.5 + (thr / denom) / 2) if denom > 0 else 0.5
    conv = max(p_now, 1 - p_now)

    sides = {k: float(last[f"s_{k}"]) for k in STRATS}
    agree = sum(1 for v in sides.values() if v * comp > 0 and abs(v) >= 0.2)
    conf = min(CFG["max_conf"], max(50.0, 50 + abs(p_now - 0.5) * 200 * (0.55 + 0.45 * agree / len(STRATS))))

    slope_z = None if pd.isna(last["slope_z"]) else float(last["slope_z"])
    if slope_z is None:
        regime = "نامشخص"
    elif slope_z > 0.6:
        regime = "روند صعودی"
    elif slope_z < -0.6:
        regime = "روند نزولی"
    else:
        regime = "رنج"

    res.update(
        ok=True, panel=d, backtest=bt, p_now=p_now, p_req=p_req, conv=conv,
        gap=max(0.0, (p_req - conv) * 100),
        comp=comp, decision=decision, edge=edge, edge_dir=("صعودی" if edge > 0 else "نزولی"),
        threshold=thr, sigma_d=sigma_d, conf=conf, agree=agree, sides=sides,
        regime=regime, slope_z=slope_z, calib_share=calib_share, calib_on=calib_share >= 0.5,
        weights={k: float(last[f"w_{k}"]) for k in STRATS},
        skills={k: (None if pd.isna(last[f"k_{k}"]) else float(last[f"k_{k}"])) for k in STRATS},
        ema20=float(last["ema20"]), ema60=float(last["ema60"]),
        ma20=None if pd.isna(last["ma20"]) else float(last["ma20"]),
        sd20=None if pd.isna(last["sd20"]) else float(last["sd20"]),
        hh=None if pd.isna(last["hh"]) else float(last["hh"]),
        ll=None if pd.isna(last["ll"]) else float(last["ll"]),
        ratio_z=None if pd.isna(last["ratio_z"]) else float(last["ratio_z"]),
        corr=None if pd.isna(last["corr"]) else float(last["corr"]),
        n_days=len(d),
    )
    return res


def horizon_table(r: dict) -> pd.DataFrame:
    rows = []
    for h in (1, 2, 3, 5, 10):
        edge = (2 * r["p_now"] - 1) * 0.8 * r["sigma_d"] * 100 * math.sqrt(h)
        denom = 0.8 * r["sigma_d"] * 100 * math.sqrt(h)
        need = min(0.95, 0.5 + (r["threshold"] / denom) / 2) if denom > 0 else 0.5
        dec = ("خرید" if edge >= r["threshold"] and r["comp"] > 0
               else "فروش" if edge <= -r["threshold"] and r["comp"] < 0 else "نظاره")
        rows.append({"افق (روز)": h, "لبه (٪)": round(edge, 2), "احتمال لازم (٪)": round(need * 100),
                     "تصمیم": dec})
    return pd.DataFrame(rows)


def forecast(price: float, sigma_d: float, comp: float) -> dict:
    out = {}
    for label, h in (("۱ ساعت", 1 / 24), ("۱ روز", 1.0), ("۳ روز", 3.0)):
        s = sigma_d * math.sqrt(max(h, 1 / 24))
        drift = comp * 0.30 * s
        out[label] = {
            "lo": price * math.exp(drift - CFG["z80"] * s),
            "med": price * math.exp(drift),
            "hi": price * math.exp(drift + CFG["z80"] * s),
            "move": (math.exp(drift) - 1) * 100,
            "sig": s * 100,
        }
    return out


def risk_plan(price: float, sigma_d: float, decision: str, capital: float, risk_pct: float) -> dict:
    side = 1 if decision == "خرید" else (-1 if "فروش" in decision else 0)
    stop_pct = CFG["stop_sigma"] * sigma_d
    if side == 0 or not price:
        return {"side": 0, "stop": None, "target": None, "stop_pct": stop_pct * 100,
                "target_pct": CFG["target_sigma"] * sigma_d * 100, "pos_pct": 0.0, "amount": 0.0}
    pos_pct = min(100.0, risk_pct / (stop_pct * 100) * 100) if stop_pct > 0 else 0.0
    return {
        "side": side,
        "stop": price * (1 - side * stop_pct),
        "target": price * (1 + side * CFG["target_sigma"] * sigma_d),
        "stop_pct": stop_pct * 100, "target_pct": CFG["target_sigma"] * sigma_d * 100,
        "pos_pct": pos_pct, "amount": capital * pos_pct / 100,
    }


# ═══════════════ ۶) متن‌های قابل کپی ═══════════════


def signal_text(r: dict, fc: dict, plan: dict, inta: dict | None = None) -> str:
    jd, jt = jalali()
    L = [
        "سیگنال طلای ۱۸ عیار", f"{jd} — {jt}", "",
        f"تصمیم: {r['decision']}",
        f"احتمال رشد: {r['p_now'] * 100:.1f}٪" + ("" if r["calib_on"] else " (کالیبراسیون در حال بلوغ)"),
        f"امتیاز ترکیبی: {r['comp']:+.2f}",
        f"اطمینان: {r['conf']:.0f}٪ — رژیم: {r['regime']}",
        "",
        f"قیمت: {fmt(r['price'])} تومان", f"دلار: {fmt(r['usd'])} تومان",
        f"انس: {fmt(r['ounce'], 1)} دلار",
        f"پریمیوم: {pc(r['prem'])}" + (" (تخمینی)" if r.get("prem_est") else ""),
        "",
        f"لبهٔ {CFG['horizon_days']}روزه: {abs(r['edge']):.2f}٪ {r['edge_dir']} | آستانهٔ هزینه: {r['threshold']:.2f}٪",
        f"برای ورود لازم است اطمینان ≥ {r['p_req'] * 100:.0f}٪ (اکنون {r['conv'] * 100:.0f}٪)",
        "", "پیش‌بینی (بازهٔ ۸۰٪):",
    ]
    if inta and inta.get("ready"):
        hb = intr.hourly_band(r["price"], inta["sigma_1h"], inta["comp"]) if intr else None
        if hb:
            L.append(f"• ۱ ساعت (کندل ۵ دقیقه): {fmt(hb['lo'])} تا {fmt(hb['hi'])} "
                     f"(میانه {fmt(hb['med'])}) · جهت {inta['p_up'] * 100:.0f}٪ صعود")
    for label, q in fc.items():
        if label == "۱ ساعت" and inta and inta.get("ready"):
            continue
        L.append(f"• {label}: {fmt(q['lo'])} تا {fmt(q['hi'])} (میانه {fmt(q['med'])})")
    L.append("")
    if plan["side"] != 0:
        L += [f"حد ضرر: {fmt(plan['stop'])} ({plan['stop_pct']:.1f}٪)",
              f"هدف: {fmt(plan['target'])} ({plan['target_pct']:.1f}٪)",
              f"حجم: {plan['pos_pct']:.0f}٪ سرمایه"]
    else:
        L.append("برنامه: بدون ورود تا روشن شدن لبه.")
    return "\n".join(L)


def report_text(r: dict, fc: dict, plan: dict, live: dict, inta: dict | None = None) -> str:
    jd, jt = jalali()
    bt = r["backtest"]
    L = [
        "گزارش تحلیلی طلای ۱۸ عیار", f"{jd} — {jt}", "──────────────", "بازار",
        f"طلای ۱۸ عیار: {fmt(r['price'])} تومان/گرم",
        f"دلار آزاد: {fmt(r['usd'])} تومان",
        f"انس جهانی: {fmt(r['ounce'], 1)} دلار",
        f"ارزش ذاتی (۰.۷۵ عیار): {fmt(r['theo'])} تومان/گرم",
        f"پریمیوم: {pc(r['prem'])}" + (f" | z={r['prem_z']:+.2f}" if r.get("prem_z") is not None else ""),
        "──────────────", "تصمیم",
        f"سیگنال: {r['decision']}",
        f"احتمال: {r['p_now'] * 100:.1f}٪ (آستانهٔ اطمینان {r['p_req'] * 100:.0f}٪)",
        f"لبه: {abs(r['edge']):.2f}٪ {r['edge_dir']} | هزینه: {CFG['cost_pct']:.2f}٪ | آستانه: {r['threshold']:.2f}٪",
        f"رژیم: {r['regime']} | توافق: {r['agree']} از ۴",
        f"وضعیت کالیبراسیون: {'فعال' if r['calib_on'] else 'در حال بلوغ'}",
        "──────────────", "لایه‌های استراتژی",
    ]
    for k, name in STRATS.items():
        sk = r["skills"].get(k)
        L.append(f"{name}: امتیاز {r['sides'][k]:+.2f} | وزن {r['weights'][k] * 100:.0f}٪"
                 + (f" | مهارت اخیر {sk:+.2f}٪" if sk is not None else ""))
    L += ["──────────────", "پیش‌بینی"]
    if inta and inta.get("ready") and intr:
        hb = intr.hourly_band(r["price"], inta["sigma_1h"], inta["comp"])
        if hb:
            L.append(f"۱ ساعت (واقعی): {fmt(hb['lo'])} — {fmt(hb['med'])} — {fmt(hb['hi'])} | نوسان {hb['sig']:.2f}٪")
    else:
        q = fc["۱ ساعت"]
        L.append(f"۱ ساعت (تقریبی): {fmt(q['lo'])} — {fmt(q['med'])} — {fmt(q['hi'])}")
    for label in ("۱ روز", "۳ روز"):
        q = fc[label]
        L.append(f"{label}: {fmt(q['lo'])} — {fmt(q['med'])} — {fmt(q['hi'])} | نوسان {q['sig']:.2f}٪")
    L += ["──────────────", "برنامهٔ ریسک"]
    if plan["side"] != 0:
        L += [f"حد ضرر {fmt(plan['stop'])} ({plan['stop_pct']:.1f}٪) · هدف {fmt(plan['target'])} ({plan['target_pct']:.1f}٪)",
              f"نسبت سود به ضرر {CFG['target_sigma'] / CFG['stop_sigma']:.1f} · حجم {plan['pos_pct']:.0f}٪ سرمایه"]
    else:
        L.append("بدون ورود؛ حجم صفر.")
    L += ["──────────────", "کارنامهٔ بک‌تست (گام‌به‌گام، با هزینه)"]
    if bt["n"]:
        L += [f"تعداد معامله: {bt['n']}" + ("" if bt["reliable"] else " (نمونهٔ کم)"),
              f"نرخ برد: {bt['win']:.1f}٪",
              f"میانگین بازده هر معامله: {bt['exp']:+.2f}٪",
              f"سود انباشته: {bt['total']:+.1f}٪ | حداکثر افت: {bt['dd']:.1f}٪",
              f"Profit Factor: {bt['pf']:.2f}" if bt["pf"] else "Profit Factor: نامشخص",
              f"بازده به افت: {bt['total'] / abs(bt['dd']):.2f}" if bt["dd"] else "بازده به افت: —"]
    else:
        L.append("معامله‌ای در پنجرهٔ آزمون ثبت نشد.")
    L += ["──────────────",
          f"کیفیت داده: {r['n_days']} روز تاریخ · {inta.get('n', 0) if inta else 0} کندل ۵ دقیقه‌ای · "
          f"بروزرسانی {age_txt(live.get('at'))}",
          "این گزارش تحلیلی است و توصیهٔ سرمایه‌گذاری نیست."]
    return "\n".join(L)


# ═══════════════ ۷) ظاهر ═══════════════

CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');
:root{
  --bg:#f5f6fa; --surface:#ffffff; --ink:#101828; --muted:#667085; --line:#e5e8f0;
  --gold:#b45309; --gold2:#f59e0b; --up:#0e9f6e; --down:#dc2626; --soft:#fff8ec;
}
html, body, [class*="css"], .stMarkdown, div, p, span, label, input, button, td, th {
  font-family: Vazirmatn, Tahoma, sans-serif !important;
}
.stApp{ background: var(--bg) !important; }
.block-container{ max-width: 1120px; padding-top: 1.2rem; padding-bottom: 2.5rem; direction: rtl; text-align: right; }
#MainMenu, footer, [data-testid="stToolbar"]{ visibility: hidden; height: 0; }
.num{ font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }

.topbar{ display:flex; align-items:center; justify-content:space-between; gap:12px;
  background: linear-gradient(100deg,#181d2b,#232a3d 60%,#2c2413);
  border:1px solid #2d3446; border-radius:16px; padding:14px 18px; margin-bottom:14px; }
.brand{ display:flex; align-items:center; gap:10px; }
.brand-title{ color:#fff; font-size:1.05rem; font-weight:700; letter-spacing:-.01em; }
.brand-sub{ color:#a9b1c6; font-size:.72rem; }
.chip{ display:inline-flex; align-items:center; gap:6px; padding:5px 11px; border-radius:999px;
  font-size:.72rem; font-weight:600; border:1px solid; background:rgba(255,255,255,.06); }
.chip-ok{ color:#6ee7b7; border-color:#0e9f6e; }
.chip-warn{ color:#fcd34d; border-color:#b45309; }
.chip-mut{ color:#c7cede; border-color:#3a4358; }

.kpi{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:13px 14px;
  box-shadow:0 1px 2px rgba(16,24,40,.04); }
.kpi-h{ display:flex; align-items:center; gap:7px; color:var(--muted); font-size:.74rem; margin-bottom:7px; }
.kpi-v{ color:var(--ink); font-size:1.28rem; font-weight:700; letter-spacing:-.02em; line-height:1.25; }
.kpi-s{ font-size:.72rem; margin-top:4px; color:var(--muted); }
.up{ color:var(--up) !important; } .down{ color:var(--down) !important; }

.hero{ background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:18px;
  box-shadow:0 1px 2px rgba(16,24,40,.05); margin-top:12px; }
.hero-top{ display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
.dec{ font-size:1.6rem; font-weight:800; letter-spacing:-.02em; }
.dec-buy{ color:#0e9f6e; } .dec-sell{ color:#dc2626; } .dec-wait{ color:#475467; }
.pill{ display:inline-block; padding:4px 12px; border-radius:999px; font-size:.72rem; font-weight:700;
  background:var(--soft); color:var(--gold); border:1px solid #f3ddb4; }
.meter{ margin-top:14px; }
.meter-track{ position:relative; height:12px; border-radius:999px; overflow:hidden;
  background:#eef0f6; display:flex; }
.meter-down{ background:linear-gradient(90deg,#fca5a5,#dc2626); }
.meter-up{ background:linear-gradient(90deg,#34d399,#0e9f6e); }
.meter-mark{ position:absolute; top:-4px; width:3px; height:20px; background:#101828; border-radius:2px; }
.meter-legend{ display:flex; justify-content:space-between; font-size:.7rem; color:var(--muted); margin-top:6px; }

.card{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:16px;
  box-shadow:0 1px 2px rgba(16,24,40,.04); }
.h{ font-size:.92rem; font-weight:700; color:var(--ink); margin:0 0 10px; display:flex; align-items:center; gap:8px; }
.row{ display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px dashed var(--line); font-size:.85rem; }
.row:last-child{ border-bottom:none; }
.k{ color:var(--muted); } .v{ color:var(--ink); font-weight:600; }
.why{ display:flex; gap:9px; align-items:flex-start; padding:9px 0; border-bottom:1px dashed var(--line); font-size:.84rem; }
.why:last-child{ border-bottom:none; }
.why-t{ color:var(--ink); font-weight:600; }
.why-d{ color:var(--muted); font-size:.78rem; margin-top:2px; }
.notice{ background:#fffbeb; border:1px solid #f3ddb4; color:#7c4a03; border-radius:12px;
  padding:10px 14px; font-size:.8rem; line-height:1.9; margin-bottom:10px; }
.notice-b{ font-weight:700; }

[data-testid="stMetricValue"]{ color:var(--ink) !important; font-size:1.15rem !important; font-weight:700; }
[data-testid="stMetricLabel"]{ color:var(--muted) !important; font-size:.78rem; }
div.stButton > button{ border-radius:10px; font-weight:600; padding:8px 14px; min-height:42px;
  display:flex; align-items:center; justify-content:center; line-height:1.3; border:1px solid var(--line);
  background:#fff; color:var(--ink); }
div.stButton > button:hover{ border-color:var(--gold2); color:var(--gold); }
div[data-testid="stDownloadButton"] > button{ border-radius:10px; border:1px solid var(--line);
  background:#fff; color:var(--ink); font-weight:600; padding:8px 14px; min-height:42px; }
div[data-testid="stDownloadButton"] > button:hover{ border-color:var(--gold2); color:var(--gold); }
code, pre{ direction: ltr; text-align: left; }
hr{ border-color:var(--line); }
</style>
"""


def icon(name: str, color: str = "#b45309") -> str:
    p = {
        "usd": '<path d="M12 3v18M16 7.5c0-1.7-1.8-2.5-4-2.5s-4 .8-4 2.5S9.8 10 12 10s4 .9 4 2.5S14.2 15 12 15s-4-.8-4-2.5"/>',
        "gold": '<rect x="4" y="8" width="7" height="5" rx="1"/><rect x="13" y="8" width="7" height="5" rx="1"/><rect x="8.5" y="15" width="7" height="5" rx="1"/>',
        "globe": '<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2.5 2.4 2.5 12.6 0 16M12 4c-2.5 2.4-2.5 12.6 0 16"/>',
        "scale": '<path d="M12 4v16M6 8h12M6 8l-3 6h6L6 8zm12 0l-3 6h6l-3-6z"/>',
        "check": '<path d="M5 13l4 4L19 7"/>',
        "x": '<path d="M6 6l12 12M18 6L6 18"/>',
        "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
        "shield": '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z"/>',
    }.get(name, "")
    return (f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{p}</svg>')


def kpi(label, value, sub=None, cls="", ic="gold"):
    s = f'<div class="kpi-s {cls}">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="kpi"><div class="kpi-h">{icon(ic)}<span>{label}</span></div>'
        f'<div class="kpi-v num">{value}</div>{s}</div>', unsafe_allow_html=True)


def rows(items):
    body = "".join(f'<div class="row"><span class="k">{k}</span><span class="v num">{v}</span></div>'
                   for k, v in items)
    return f'<div class="card">{body}</div>'


def why_block(items):
    body = ""
    for ok, title, desc in items:
        ic = "check" if ok else "x"
        col = "#0e9f6e" if ok else "#dc2626"
        body += (f'<div class="why">{icon(ic, col)}<div><div class="why-t">{title}</div>'
                 f'<div class="why-d">{desc}</div></div></div>')
    return f'<div class="card">{body}</div>'


# ═══════════════ ۸) اجرا ═══════════════


def main():
    st.set_page_config(page_title="Gold18K Pro", page_icon="◈", layout="wide",
                       initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)

    store = get_store()
    with st.expander("تنظیمات موتور", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        cost = c1.number_input("هزینهٔ رفت‌وبرگشت (٪)", 0.0, 5.0, CFG["cost_pct"], 0.05,
                               help="اسپرد + اسلیپیج. برای طلای آب‌شده معمولاً ۰٫۴ تا ۰٫۸ درصد.")
        risk = c2.number_input("ریسک هر معامله (٪)", 0.1, 5.0, CFG["risk_pct"], 0.1)
        capital = c3.number_input("سرمایه (تومان)", 0, 10 ** 13, 200_000_000, 10_000_000)
        horizon = c4.selectbox("افق تصمیم (روز)", [1, 2, 3, 5], index=2)
        if st.button("بروزرسانی داده و پاک‌سازی کش"):
            st.cache_data.clear()
            st.rerun()
        st.caption("هزینه و افق، هم تصمیم امروز و هم کارنامهٔ بک‌تست را عوض می‌کنند.")
    CFG["cost_pct"], CFG["risk_pct"], CFG["horizon_days"] = float(cost), float(risk), int(horizon)

    live = fetch_live()
    store.add_tick(live)
    history = fetch_history()
    ticks = store.ticks()
    r = build_engine(history, live, ticks)

    bars = intr.load_bars() if intr else pd.DataFrame()
    inta = intr.state(bars, r.get("comp", 0.0), r.get("sigma_d", CFG["fallback_sigma"])) if intr else {"ready": False, "n": 0}

    jd, jt = jalali()
    fresh = age_txt(live.get("at"))
    ok_live = r.get("price") is not None

    st.markdown(
        f"""<div class="topbar">
  <div class="brand">{icon("gold", "#f59e0b")}
    <div><div class="brand-title">Gold18K Pro</div>
    <div class="brand-sub">موتور تحلیل طلای ۱۸ عیار · نگارش {VERSION} · {BUILD}</div></div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <span class="chip {'chip-ok' if ok_live else 'chip-warn'}">{'داده زنده' if ok_live else 'داده ناقص'}</span>
    <span class="chip chip-mut">{jd} · {jt}</span>
    <span class="chip chip-mut">بروزرسانی {fresh}</span>
  </div></div>""", unsafe_allow_html=True)

    if not ok_live:
        st.error("قیمت زندهٔ طلای ۱۸ عیار در دسترس نیست. چند لحظه بعد دوباره تلاش کنید.")
        if live.get("errors"):
            st.caption(" · ".join(live["errors"]))
        st.stop()

    g_local, u_local = store.change("gold18", r["price"]), store.change("usd", r["usd"])
    g_show = g_local if g_local is not None else hist_change(history, "gold18")
    u_show = u_local if u_local is not None else hist_change(history, "usd")
    g_tag = ("محلی" if g_local is not None else "روزانه") if g_show is not None else "در حال جمع‌آوری"
    u_tag = ("محلی" if u_local is not None else "روزانه") if u_show is not None else "در حال جمع‌آوری"

    c = st.columns(4)
    with c[0]:
        kpi("طلای ۱۸ عیار", fmt(r["price"]),
            (pc(g_show) + f" · {g_tag}") if g_show is not None else g_tag,
            "up" if (g_show or 0) >= 0 else "down", "gold")
    with c[1]:
        kpi("دلار آزاد", fmt(r["usd"]),
            (pc(u_show) + f" · {u_tag}") if u_show is not None else u_tag,
            "up" if (u_show or 0) >= 0 else "down", "usd")
    with c[2]:
        kpi("انس جهانی", fmt(r["ounce"], 1) + " $", "دلار بر انس", "", "globe")
    with c[3]:
        sub = ("تخمینی" if r.get("prem_est") else f"z={r['prem_z']:+.2f}") if r.get("prem_z") is not None else None
        kpi("پریمیوم", pc(r["prem"]), sub, "up" if (r.get("prem") or 0) >= 0 else "down", "scale")

    if not r.get("ok"):
        st.warning(r.get("reason", "موتور نتوانست محاسبه کند."))
        st.stop()

    if not r["calib_on"]:
        st.markdown(
            '<div class="notice"><span class="notice-b">کالیبراسیون تجربی هنوز بالغ نشده است.</span> '
            f'تنها {r["calib_share"] * 100:.0f}٪ از ردیف‌های تاریخی نتیجهٔ معلوم داشتند، پس احتمال از '
            'مدل پشتیبان می‌آید. با افزایش تاریخ، این عدد خودکار به کالیبراسیون تجربی می‌رسد.</div>',
            unsafe_allow_html=True)

    plan = risk_plan(r["price"], r["sigma_d"], r["decision"], capital, risk)
    fc = forecast(r["price"], r["sigma_d"], r["comp"])

    dcls = "dec-buy" if r["decision"] == "خرید" else ("dec-sell" if "فروش" in r["decision"] else "dec-wait")
    pu = r["p_now"] * 100
    if abs(r["edge"]) < r["threshold"]:
        gap_txt = (f'برای ورود لازم است اطمینان ≥ <b class="num">{r["p_req"] * 100:.0f}٪</b> باشد؛ '
                   f'اکنون <b class="num">{r["conv"] * 100:.0f}٪</b> است (فاصله <b class="num">{r["gap"]:.1f}</b> واحد).')
    else:
        gap_txt = "لبه از آستانهٔ هزینه بیشتر است."

    ipill = ""
    if inta.get("ready"):
        d_h = "صعودی" if inta["comp"] > 0 else ("نزولی" if inta["comp"] < 0 else "بی‌جهت")
        ipill = (f'<span class="pill">۱ ساعت: {d_h} {inta["p_up"] * 100:.0f}٪ '
                 f'· σ {inta["sigma_1h"] * 100:.2f}٪</span>')
    else:
        ipill = '<span class="pill">۱ ساعت: تقریبی</span>'

    st.markdown(
        f"""<div class="hero">
  <div class="hero-top">
    <div>
      <div class="brand-sub" style="margin-bottom:4px;">تصمیم موتور برای افق {CFG['horizon_days']} روزه</div>
      <div class="dec {dcls}">{r['decision']}</div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <span class="pill">رژیم: {r['regime']}</span>
      <span class="pill">توافق {r['agree']} از ۴</span>
      <span class="pill">اطمینان {r['conf']:.0f}٪</span>
      {ipill}
    </div>
  </div>
  <div class="meter">
    <div class="meter-track">
      <div class="meter-down" style="width:{100 - pu:.1f}%"></div>
      <div class="meter-up" style="width:{pu:.1f}%"></div>
      <div class="meter-mark" style="left:{100 - pu:.1f}%"></div>
    </div>
    <div class="meter-legend"><span>نزول {100 - pu:.1f}٪</span><span>رشد {pu:.1f}٪</span></div>
  </div>
  <div style="margin-top:12px;font-size:.8rem;color:var(--muted);line-height:1.9;">
    لبهٔ تخمینی <b class="num">{abs(r['edge']):.2f}٪ {r['edge_dir']}</b> در برابر آستانهٔ هزینهٔ
    <b class="num">{r['threshold']:.2f}٪</b> · {gap_txt}
  </div>
</div>""", unsafe_allow_html=True)
    st.write("")

    pages = ["نمای کلی", "سیگنال", "پیش‌بینی", "کارنامه", "داده‌ها"]
    try:
        page = st.segmented_control("ناوبری", pages, default=pages[0], label_visibility="collapsed")
        page = page or pages[0]
    except Exception:
        page = st.radio("ناوبری", pages, horizontal=True, label_visibility="collapsed")
    st.write("")

    # ═══ نمای کلی
    if page == "نمای کلی":
        ok_dir = abs(r["comp"]) >= 0.15
        ok_edge = abs(r["edge"]) >= r["threshold"]
        ok_agree = r["agree"] >= 2
        left, right = st.columns([1.35, 1])
        with left:
            st.markdown('<div class="h">چرا این تصمیم؟</div>', unsafe_allow_html=True)
            st.markdown(why_block([
                (ok_dir, "جهت مشخص است" if ok_dir else "جهت مشخص نیست",
                 f"امتیاز ترکیبی {r['comp']:+.2f}" + ("" if ok_dir else " — زیر آستانهٔ ۰٫۱۵، بازار بی‌جهت")),
                (ok_edge, "لبه از هزینه بیشتر است" if ok_edge else "لبه کمتر از هزینه است",
                 f"لبه {abs(r['edge']):.2f}٪ {r['edge_dir']} در برابر آستانهٔ {r['threshold']:.2f}٪"),
                (ok_agree, "استراتژی‌ها هم‌جهت‌اند" if ok_agree else "استراتژی‌ها هم‌جهت نیستند",
                 f"{r['agree']} از ۴ لایه هم‌جهت‌اند"),
                (r["calib_on"], "کالیبراسیون بالغ است" if r["calib_on"] else "کالیبراسیون در حال بلوغ",
                 f"{r['calib_share'] * 100:.0f}٪ ردیف‌ها نمونهٔ معتبر داشتند"),
            ]), unsafe_allow_html=True)
            st.write("")
            st.markdown(rows([("امتیاز ترکیبی", f"{r['comp']:+.2f}")]
                             + [(STRATS[k], f"{r['sides'][k]:+.2f} · وزن {r['weights'][k] * 100:.0f}٪") for k in STRATS]),
                        unsafe_allow_html=True)
        with right:
            bt = r["backtest"]
            if bt["n"]:
                st.markdown(rows([
                    ("نرخ برد بک‌تست", f"{bt['win']:.1f}٪" if bt["reliable"] else "نمونهٔ کم"),
                    ("تعداد معامله", f"{bt['n']}"),
                    ("میانگین هر معامله", f"{bt['exp']:+.2f}٪"),
                    ("Profit Factor", f"{bt['pf']:.2f}" if bt["pf"] else "نامشخص"),
                    ("حداکثر افت", f"{bt['dd']:.1f}٪"),
                ]), unsafe_allow_html=True)
            else:
                st.info("بک‌تست قابل اتکا هنوز شکل نگرفته است.")
            st.write("")
            if plan["side"] != 0:
                st.markdown(rows([
                    ("حد ضرر", f"{fmt(plan['stop'])} ({plan['stop_pct']:.1f}٪)"),
                    ("هدف", f"{fmt(plan['target'])} ({plan['target_pct']:.1f}٪)"),
                    ("حجم", f"{plan['pos_pct']:.0f}٪ سرمایه"),
                ]), unsafe_allow_html=True)
            else:
                st.markdown(rows([("برنامهٔ معامله", "بدون ورود")]), unsafe_allow_html=True)

        st.write("")
        p = r["panel"]
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28],
                            vertical_spacing=0.06)
        fig.add_trace(go.Scatter(x=p["day"], y=p["close"], name="طلای ۱۸", line=dict(color="#b45309", width=2.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=p["day"], y=p["ema20"], name="EMA20", line=dict(color="#0e9f6e", width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=p["day"], y=p["ema60"], name="EMA60", line=dict(color="#dc2626", width=1.2)), row=1, col=1)
        if p["sd20"].notna().any():
            up, lo = p["ma20"] + 2 * p["sd20"], p["ma20"] - 2 * p["sd20"]
            fig.add_trace(go.Scatter(x=p["day"], y=up, line=dict(width=0), showlegend=False, hoverinfo="skip"), row=1, col=1)
            fig.add_trace(go.Scatter(x=p["day"], y=lo, line=dict(width=0), fill="tonexty",
                                     fillcolor="rgba(180,83,9,.07)", name="باند ۲σ", hoverinfo="skip"), row=1, col=1)
        colors = ["#0e9f6e" if v >= 0 else "#dc2626" for v in p["composite"].fillna(0)]
        fig.add_trace(go.Bar(x=p["day"], y=p["composite"], marker_color=colors, name="امتیاز"), row=2, col=1)
        fig.update_layout(template="plotly_white", height=430, margin=dict(l=8, r=8, t=10, b=8),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          legend=dict(orientation="h", y=1.08, x=0.02, font=dict(size=10)), bargap=0.2)
        fig.update_yaxes(showgrid=True, gridcolor="#eef0f6", tickformat=",", row=1, col=1)
        fig.update_yaxes(showgrid=False, zeroline=True, zerolinecolor="#d0d5e2", row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)

    # ═══ سیگنال
    elif page == "سیگنال":
        st.markdown('<div class="h">لایه‌های استراتژی</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{
            "استراتژی": STRATS[k], "امتیاز امروز": round(r["sides"][k], 2),
            "وزن": f"{r['weights'][k] * 100:.0f}٪",
            "مهارت اخیر": "—" if r["skills"][k] is None else f"{r['skills'][k]:+.2f}٪",
            "نقش": ROLE[k],
        } for k in STRATS]), use_container_width=True, hide_index=True)
        st.caption("وزن هر لایه از عملکرد گذشتهٔ خودش می‌آید (میانگین نمایی، عقب‌افتاده به اندازهٔ افق)؛ "
                   "لایهٔ بی‌مهارت وزن نزدیک صفر می‌گیرد.")

        st.write("")
        st.markdown('<div class="h">ارزش انتظاری و حساسیت به افق</div>', unsafe_allow_html=True)
        st.dataframe(horizon_table(r), use_container_width=True, hide_index=True)
        st.caption(f"احتمال فعلی {r['p_now'] * 100:.1f}٪ و برای افق {CFG['horizon_days']} روزه "
                   f"آستانهٔ {r['threshold']:.2f}٪ لازم است. ستون تصمیم نشان می‌دهد با همان احتمال، "
                   "افق‌های دیگر چه می‌گفتند — کمکی برای انتخاب افق، نه توصیهٔ جداگانه.")

        st.write("")
        st.markdown('<div class="h">سطوح تصمیم</div>', unsafe_allow_html=True)
        ma, sd = r["ma20"] or 0, r["sd20"] or 0
        st.markdown(rows([
            ("EMA20 (میانگین سریع)", fmt(r["ema20"])),
            ("EMA60 (میانگین کند)", fmt(r["ema60"])),
            ("سقف کانال ۲۰ روزه", fmt(r["hh"])),
            ("کف کانال ۲۰ روزه", fmt(r["ll"])),
            ("+۲σ", fmt(ma + 2 * sd)),
            ("−۲σ", fmt(ma - 2 * sd)),
        ]), unsafe_allow_html=True)
        st.caption("بستن قیمت بالای سقف کانال، لایهٔ شکست را مثبت می‌کند؛ زیر کف، منفی. "
                   "عبور از EMA20 به سمت EMA60 جهت روند را عوض می‌کند.")

        st.write("")
        st.markdown('<div class="h">متن آمادهٔ سیگنال</div>', unsafe_allow_html=True)
        st.code(signal_text(r, fc, plan, inta), language=None)
        st.download_button("دانلود متن سیگنال", signal_text(r, fc, plan, inta),
                           file_name=f"signal_{datetime.now():%Y%m%d_%H%M}.txt", mime="text/plain")

    # ═══ پیش‌بینی
    elif page == "پیش‌بینی":
        st.markdown('<div class="h">بازهٔ ۸۰٪ برای هر افق</div>', unsafe_allow_html=True)
        table = []
        if inta.get("ready") and intr:
            hb = intr.hourly_band(r["price"], inta["sigma_1h"], inta["comp"])
            table.append({"افق": "۱ ساعت (واقعی)", "کمینه": fmt(hb["lo"]), "میانه": fmt(hb["med"]),
                          "بیشینه": fmt(hb["hi"]), "حرکت میانه": pc(hb["move"]),
                          "نوسان دوره": f"{hb['sig']:.2f}٪"})
        else:
            q = fc["۱ ساعت"]
            table.append({"افق": "۱ ساعت (تقریبی)", "کمینه": fmt(q["lo"]), "میانه": fmt(q["med"]),
                          "بیشینه": fmt(q["hi"]), "حرکت میانه": pc(q["move"]),
                          "نوسان دوره": f"{q['sig']:.2f}٪"})
        for label in ("۱ روز", "۳ روز"):
            q = fc[label]
            table.append({"افق": label, "کمینه": fmt(q["lo"]), "میانه": fmt(q["med"]),
                          "بیشینه": fmt(q["hi"]), "حرکت میانه": pc(q["move"]),
                          "نوسان دوره": f"{q['sig']:.2f}٪"})
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        if inta.get("ready"):
            st.caption("افق یک‌ساعته از کندل‌های ۵ دقیقه‌ای خودمان محاسبه شده؛ افق‌های روزانه از تاریخ روزانه.")
        else:
            st.caption(f"افق یک‌ساعته هنوز تقریبی است: {inta.get('n', 0)} کندل ۵ دقیقه‌ای داریم و "
                       f"{CFG['min_bars_ready']} لازم است. افق روزانه از تاریخ روزانه می‌آید و مستقل است.")

        if inta.get("ready"):
            st.write("")
            st.markdown('<div class="h">تصویر درون‌روزی</div>', unsafe_allow_html=True)
            st.markdown(rows([
                ("نوسان ۵ دقیقه", f"{inta['sigma_5m'] * 100:.3f}٪"),
                ("نوسان ۱ ساعت", f"{inta['sigma_1h'] * 100:.2f}٪"),
                ("مومنتوم ۱ ساعت (z)", f"{inta['mom_z']:+.2f}"),
                ("انحراف از میانگین (z)", f"{inta['dev_z']:+.2f}"),
                ("امتیاز درون‌روزی", f"{inta['comp']:+.2f}"),
                ("نرخ برد جهتی (تاریخی)", "—" if inta["hit"] is None else f"{inta['hit'] * 100:.0f}٪"),
            ]), unsafe_allow_html=True)
            st.caption(f"{inta['n']} کندل ۵ دقیقه‌ای · آخرین کندل {inta['last']}")

        st.write("")
        p = r["panel"]
        cur = r["price"]
        future = [p["day"].iloc[-1] + pd.Timedelta(days=i) for i in (1, 2, 3)]
        st.markdown('<div class="h">قیف پیش‌بینی ۳ روزه</div>', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=p["day"].iloc[-40:], y=p["close"].iloc[-40:], name="قیمت",
                                 line=dict(color="#101828", width=2)))
        fig.add_trace(go.Scatter(x=[p["day"].iloc[-1]] + future, y=[cur] + [fc["۳ روز"]["med"]] * 3,
                                 name="میانه", line=dict(color="#f59e0b", width=2, dash="dot")))
        fig.add_trace(go.Scatter(x=[p["day"].iloc[-1]] + future, y=[cur] + [fc["۳ روز"]["hi"]] * 3,
                                 name="سقف ۸۰٪", line=dict(color="#0e9f6e", width=1)))
        fig.add_trace(go.Scatter(x=[p["day"].iloc[-1]] + future, y=[cur] + [fc["۳ روز"]["lo"]] * 3,
                                 name="کف ۸۰٪", line=dict(color="#dc2626", width=1), fill="tonexty",
                                 fillcolor="rgba(180,83,9,.10)"))
        fig.update_layout(template="plotly_white", height=340, margin=dict(l=8, r=8, t=10, b=8),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          legend=dict(orientation="h", y=1.1), hovermode="x unified")
        fig.update_yaxes(gridcolor="#eef0f6", tickformat=",")
        st.plotly_chart(fig, use_container_width=True)

    # ═══ کارنامه
    elif page == "کارنامه":
        bt = r["backtest"]
        if not bt["n"]:
            st.info("در پنجرهٔ فعلی شرط ورود (لبه بیش از هزینه) فعال نشده؛ کارنامه خالی است. "
                    "این یعنی موتور سکوت کرده، نه اینکه خراب است.")
        else:
            c = st.columns(6)
            c[0].metric("نرخ برد", f"{bt['win']:.1f}٪" if bt["reliable"] else "نمونهٔ کم")
            c[1].metric("معاملات", f"{bt['n']}")
            c[2].metric("میانگین هر معامله", f"{bt['exp']:+.2f}٪")
            c[3].metric("Profit Factor", f"{bt['pf']:.2f}" if bt["pf"] else "نامشخص")
            c[4].metric("حداکثر افت", f"{bt['dd']:.1f}٪")
            c[5].metric("بازده به افت", f"{bt['total'] / abs(bt['dd']):.2f}" if bt["dd"] else "—")
            st.caption(f"نمایش موتور (درصد روزهایی که پوزیشن داشت): {bt['exposure']:.0f}٪ · "
                       + ("نمونه برای قضاوت کافی است." if bt["reliable"]
                          else f"کمتر از {CFG['min_trades_reliable']} معامله؛ عدد نرخ برد شکننده است."))
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=bt["equity"] * 100, name="سرمایه", line=dict(color="#0e9f6e", width=2)))
            fig.update_layout(template="plotly_white", height=260, margin=dict(l=8, r=8, t=10, b=8),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
            fig.update_yaxes(gridcolor="#eef0f6", ticksuffix="٪")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown('<div class="h">کالیبراسیون: احتمال گفته‌شده در برابر نتیجهٔ واقعی</div>',
                        unsafe_allow_html=True)
            t = bt["trades"].copy()
            t["bucket"] = pd.cut(t["p"], bins=[0, .45, .5, .55, .6, 1],
                                 labels=["<۴۵٪", "۴۵–۵۰٪", "۵۰–۵۵٪", "۵۵–۶۰٪", ">۶۰٪"])
            cal = t.groupby("bucket", observed=True).agg(
                تعداد=("p", "size"), احتمال=("p", "mean"), برد=("ret", lambda s: (s > 0).mean()))
            cal["احتمال"] = (cal["احتمال"] * 100).round(1)
            cal["برد"] = (cal["برد"] * 100).round(1)
            st.dataframe(cal.rename(columns={"احتمال": "احتمال میانگین (٪)", "برد": "نرخ برد واقعی (٪)"}),
                         use_container_width=True)
            st.caption("هر چه ستون آخر به ستون قبل نزدیک‌تر باشد، احتمال‌ها صادق‌ترند.")

            st.markdown('<div class="h">معاملات</div>', unsafe_allow_html=True)
            show = bt["trades"].tail(20).iloc[::-1].copy()
            show["day"] = pd.to_datetime(show["day"]).dt.strftime("%Y-%m-%d")
            show["side"] = np.where(show["side"] > 0, "خرید", "فروش")
            show["ret"] = show["ret"].round(2)
            show["p"] = (show["p"] * 100).round(1)
            st.dataframe(show.rename(columns={"day": "تاریخ", "side": "جهت",
                                              "ret": "بازده (٪)", "p": "احتمال (٪)"}),
                         use_container_width=True, hide_index=True)
            csv = bt["trades"].to_csv(index=False).encode("utf-8-sig")
            st.download_button("دانلود CSV معاملات", csv,
                               file_name=f"trades_{datetime.now():%Y%m%d_%H%M}.csv", mime="text/csv")

        st.caption(f"بک‌تست روی {r['n_days']} روز، گام‌به‌گام و بدون نگاه به آینده، با هزینهٔ "
                   f"{CFG['cost_pct']:.2f}٪ در هر معامله.")

    # ═══ داده‌ها
    else:
        st.markdown('<div class="h">منابع</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            ("دلار آزاد", fmt(r["usd"]), "iran-market", r["usd"] is not None),
            ("طلای ۱۸ عیار", fmt(r["price"]), "iran-market", True),
            ("انس جهانی", fmt(r["ounce"], 1), "gold-api", r["ounce"] is not None),
            ("نقره", fmt(safe_float((live.get("silver") or {}).get("price")), 2), "gold-api",
             live.get("silver") is not None),
            ("مس", fmt(safe_float((live.get("copper") or {}).get("price")), 3), "gold-api",
             live.get("copper") is not None),
        ], columns=["قلم", "مقدار", "منبع", "دریافت شد"]), use_container_width=True, hide_index=True)
        st.caption(f"آخرین دریافت {fresh} · تاریخ روزانه {r['n_days']} روز · نمونه‌های محلی {len(ticks)}")

        st.write("")
        st.markdown('<div class="h">آمادگی داده</div>', unsafe_allow_html=True)
        days_ok = r["n_days"] >= CFG["min_days_reliable"]
        nb = int(inta.get("n", 0))
        st.markdown(why_block([
            (days_ok, f"تاریخ روزانه: {r['n_days']} روز",
             "کافی برای سیگنال روزانه" if days_ok else f"حداقل {CFG['min_days_reliable']} روز لازم است"),
            (len(ticks) >= 40, f"نمونهٔ محلی: {len(ticks)}",
             "برای z پریمیوم و تغییر لحظه‌ای استفاده می‌شود"),
            (nb >= CFG["min_bars_ready"], f"کندل ۵ دقیقه‌ای: {nb} از {CFG['min_bars_ready']}",
             "با رسیدن به این حد، افق یک‌ساعته واقعی می‌شود" if nb < CFG["min_bars_ready"]
             else "افق یک‌ساعته از دادهٔ واقعی محاسبه می‌شود"),
            (intr is not None, "موتور درون‌روزی متصل است" if intr is not None else "intraday.py پیدا نشد",
             "فایل همراه در کنار app_v3.py باشد" if intr is None else "آماده"),
        ]), unsafe_allow_html=True)
        st.caption("برای جمع‌آوری پیوسته، collector.py باید روی سروری با اجرای مستمر بماند؛ "
                   "باز بودن صفحه کافی نیست.")

        st.write("")
        st.markdown('<div class="h">گزارش کامل</div>', unsafe_allow_html=True)
        txt = report_text(r, fc, plan, live, inta)
        st.code(txt, language=None)
        st.download_button("دانلود گزارش کامل", txt,
                           file_name=f"report_{datetime.now():%Y%m%d_%H%M}.txt", mime="text/plain")
        if live.get("errors"):
            st.warning("منابع ناقص:\n\n" + "\n".join(f"- {e}" for e in live["errors"]))

    st.write("")
    st.caption("این ابزار تحلیلی است و توصیهٔ سرمایه‌گذاری نیست. هیچ ارسالی به بیرون انجام نمی‌شود.")


if __name__ == "__main__":
    main()