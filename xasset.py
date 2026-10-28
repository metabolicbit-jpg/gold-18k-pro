# ========== Gold18K Pro · xasset.py ==========
# 📂 مسیر ریپو: xasset.py
# ویژگی‌های بین‌بازاری: طلا/نقرهٔ جهانی، شاخص دلار، بازده ۱۰ساله.
# دو منبع پشتِ سرِ هم: Yahoo سپس Stooq. اگر شبکه بسته باشد، کشِ قبلی استفاده می‌شود.
# اجرای دستی برای عیب‌یابی:  python xasset.py

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from io import StringIO

import numpy as np
import pandas as pd
import requests

CACHE = os.getenv("GOLD18K_XASSET", "data/xasset.csv")
OUNCE_GRAM = 31.1034768
FINENESS_18K = 0.750

YAHOO = {
    "xau": ["GC=F", "XAUUSD=X"],
    "xag": ["SI=F", "XAGUSD=X"],
    "dxy": ["DX-Y.NYB"],
    "tnx": ["^TNX"],
}
STOOQ = {
    "xau": ["xauusd"],
    "xag": ["xagusd"],
    "dxy": ["dx.f", "^dxy"],
    "tnx": ["10usy.b"],
}
LABELS = {"xau": "طلا جهانی", "xag": "نقره جهانی", "dxy": "شاخص دلار", "tnx": "بازده ۱۰ساله"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; Gold18K/1.2)", "Accept": "*/*"}
LAST_ERRORS: list[str] = []


# ─────────── ابزار ───────────


def _rz(s: pd.Series, win: int = 60) -> pd.Series:
    base = s.shift(1)
    med = base.rolling(win, min_periods=20).median()
    mad = (base - med).abs().rolling(win, min_periods=20).median()
    sd = (mad * 1.4826).replace(0, np.nan)
    return ((s - med) / sd).clip(-3, 3)


def _series(idx, values, name: str) -> pd.Series | None:
    try:
        s = pd.Series(values, index=pd.to_datetime(idx), name=name, dtype="float64").dropna()
        s = s[~s.index.duplicated(keep="last")].sort_index()
        return s if len(s) > 30 else None
    except Exception:
        return None


def _yahoo(symbol: str, name: str, rng: str = "2y") -> pd.Series | None:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{requests.utils.quote(symbol)}?range={rng}&interval=1d"
    )
    try:
        r = requests.get(url, headers=UA, timeout=(5, 15))
        if r.status_code != 200:
            LAST_ERRORS.append(f"yahoo/{symbol}: HTTP {r.status_code}")
            return None
        res = r.json()["chart"]["result"][0]
        ts = res.get("timestamp") or []
        closes = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        if not ts or not closes:
            LAST_ERRORS.append(f"yahoo/{symbol}: خالی")
            return None
        idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(None).normalize()
        return _series(idx, closes, name)
    except Exception as e:
        LAST_ERRORS.append(f"yahoo/{symbol}: {type(e).__name__}")
        return None


def _stooq(symbol: str, name: str) -> pd.Series | None:
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    try:
        r = requests.get(url, headers=UA, timeout=(5, 20))
        if r.status_code != 200 or "Date" not in r.text[:300]:
            LAST_ERRORS.append(f"stooq/{symbol}: HTTP {r.status_code}")
            return None
        df = pd.read_csv(StringIO(r.text))
        if "Close" not in df.columns or df.empty:
            LAST_ERRORS.append(f"stooq/{symbol}: ستون نامعتبر")
            return None
        return _series(df["Date"], df["Close"].astype(float).values, name)
    except Exception as e:
        LAST_ERRORS.append(f"stooq/{symbol}: {type(e).__name__}")
        return None


def _read(path: str) -> pd.DataFrame:
    try:
        if not os.path.exists(path):
            return pd.DataFrame()
        df = pd.read_csv(path, parse_dates=["date"])
        return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _write(path: str, df: pd.DataFrame) -> None:
    try:
        folder = os.path.dirname(os.path.abspath(path))
        if folder:
            os.makedirs(folder, exist_ok=True)
        df.to_csv(path, index=False)
    except Exception:
        pass


def _cache_ok(df: pd.DataFrame, max_age_h: float) -> bool:
    """کش وقتی معتبر است که محتوایش تازه باشد، نه فقط زمانِ فایل."""
    if df is None or df.empty or "date" not in df.columns:
        return False
    try:
        last = pd.to_datetime(df["date"]).max()
        age_days = (pd.Timestamp.utcnow().tz_localize(None).normalize() - last.normalize()).days
        if age_days <= 4:
            return True
    except Exception:
        pass
    try:
        return (time.time() - os.path.getmtime(CACHE)) < max_age_h * 3600
    except Exception:
        return False


# ─────────── بارگذاری ───────────


def load(max_age_h: float = 6.0, force: bool = False) -> pd.DataFrame:
    """سری‌های روزانهٔ بین‌بازاری با کشِ فایل. ستون‌ها: date, xau, xag, dxy, tnx."""
    global LAST_ERRORS
    cached = _read(CACHE)
    if not force and _cache_ok(cached, max_age_h):
        return cached

    LAST_ERRORS = []
    series = {}
    for key in YAHOO:
        found = None
        for sym in YAHOO[key]:
            found = _yahoo(sym, key)
            if found is not None:
                break
        if found is None:
            for sym in STOOQ.get(key, []):
                found = _stooq(sym, key)
                if found is not None:
                    break
        if found is not None:
            series[key] = found
        else:
            LAST_ERRORS.append(f"{key}: هیچ منبعی پاسخ نداد")

    if not series:
        return cached

    df = None
    for s in series.values():
        df = s.to_frame() if df is None else df.join(s, how="outer")
    df = df.sort_index().ffill(limit=5).reset_index()
    df.columns = ["date"] + [c for c in df.columns[1:]]
    _write(CACHE, df)
    return df


def status() -> dict:
    return {"errors": list(LAST_ERRORS), "cache": CACHE, "exists": os.path.exists(CACHE)}


# ─────────── تزریق به پنل ───────────


def augment(d: pd.DataFrame) -> pd.DataFrame:
    """دو لایهٔ تازه: فشار دلار جهانی و کشش طلا به نقره. اگر داده نبود صفر می‌مانند."""
    d = d.copy()
    for col in ("s_dxy", "s_gsr"):
        d[col] = 0.0
    d["xau"] = np.nan
    d["dxy"] = np.nan
    d["gsr"] = np.nan
    d["prem_hist"] = np.nan

    xa = load()
    if xa is None or xa.empty:
        return d

    try:
        left = d.sort_values("day").reset_index(drop=True)
        right = xa.sort_values("date").reset_index(drop=True)
        m = pd.merge_asof(
            left, right, left_on="day", right_on="date",
            direction="backward", tolerance=pd.Timedelta("5D"),
        )
        if "date" in m.columns:
            m = m.drop(columns=["date"])
        m = m.sort_values("day").reset_index(drop=True)

        m["gsr"] = m["xau"] / m["xag"]
        m["dxy_mom"] = m["dxy"].pct_change(5)
        m["gsr_z"] = _rz(m["gsr"], 60)
        m["dxy_z"] = _rz(m["dxy_mom"], 60)

        # دلار جهانی بالا → فشار نزولی · نسبت طلا/نقره بالا → کشش بازگشتی
        m["s_dxy"] = (-m["dxy_z"] / 2).clip(-1, 1).fillna(0.0)
        m["s_gsr"] = (-m["gsr_z"] / 2).clip(-1, 1).fillna(0.0)

        m["theo_hist"] = m["xau"] * m["usd"] / OUNCE_GRAM * FINENESS_18K
        with np.errstate(divide="ignore", invalid="ignore"):
            m["prem_hist"] = (m["close"] - m["theo_hist"]) / m["theo_hist"] * 100
        return m
    except Exception:
        return d


def coverage(df: pd.DataFrame) -> dict:
    out = {}
    for col, label in LABELS.items():
        if df is not None and col in df.columns and not df[col].isna().all():
            last = df["date"].iloc[-1] if "date" in df.columns else None
            out[col] = {"label": label, "rows": int(df[col].notna().sum()), "last": str(last)[:10]}
    return out


if __name__ == "__main__":
    print(f"زمان: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}Z")
    frame = load(force=True)
    if frame is None or frame.empty:
        print("هیچ سری‌ای دریافت نشد.")
    else:
        print(f"ردیف‌ها: {len(frame)} | از {str(frame['date'].min())[:10]} تا {str(frame['date'].max())[:10]}")
        for v in coverage(frame).values():
            print(f"  {v['label']}: {v['rows']} روز، آخرین {v['last']}")
    errs = status()["errors"]
    if errs:
        print("خطاهای منابع:")
        for e in errs[:8]:
            print(f"  - {e}")