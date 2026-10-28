# ========== Gold18K Pro · xasset.py ==========
# 📂 مسیر ریپو: xasset.py
# ویژگی‌های بین‌بازاری: شاخص دلار (DXY)، بازده اوراق ۱۰سالهٔ آمریکا، طلا و نقرهٔ جهانی.
# داده از Yahoo Finance با requests خام گرفته و در data/xasset.csv کش می‌شود (بدون وابستگی تازه).
# اگر شبکه یا منبع در دسترس نباشد، لایه‌های تازه صفر می‌شوند و مدل قبلی دست‌نخورده کار می‌کند.

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

CACHE = os.getenv("GOLD18K_XASSET", "data/xasset.csv")
SYMBOLS = {
    "xau": ("GC=F", "طلا جهانی"),
    "xag": ("SI=F", "نقره جهانی"),
    "dxy": ("DX-Y.NYB", "شاخص دلار"),
    "tnx": ("^TNX", "بازده ۱۰ساله"),
}
FALLBACK = {"xau": ("XAUUSD=X",)}
UA = {"User-Agent": "Mozilla/5.0 (compatible; Gold18K/1.0)", "Accept": "application/json"}
OUNCE_GRAM = 31.1034768
FINENESS_18K = 0.750


# ─────────── ابزار ───────────


def _rz(s: pd.Series, win: int = 60) -> pd.Series:
    base = s.shift(1)
    med = base.rolling(win, min_periods=20).median()
    mad = (base - med).abs().rolling(win, min_periods=20).median()
    sd = (mad * 1.4826).replace(0, np.nan)
    return ((s - med) / sd).clip(-3, 3)


def _yahoo(symbol: str, name: str, rng: str = "2y") -> pd.Series | None:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{requests.utils.quote(symbol)}?range={rng}&interval=1d"
    )
    try:
        r = requests.get(url, headers=UA, timeout=(5, 15))
        r.raise_for_status()
        res = r.json()["chart"]["result"][0]
        ts = res.get("timestamp") or []
        closes = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        if not ts or not closes:
            return None
        idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(None).normalize()
        s = pd.Series(closes, index=idx, name=name, dtype="float64").dropna()
        s = s[~s.index.duplicated(keep="last")].sort_index()
        return s if len(s) > 30 else None
    except Exception:
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


# ─────────── بارگذاری ───────────


def load(max_age_h: float = 6.0, force: bool = False) -> pd.DataFrame:
    """سری‌های روزانهٔ بین‌بازاری با کشِ فایل. ستون‌ها: date, xau, xag, dxy, tnx."""
    if not force and os.path.exists(CACHE):
        age_h = (time.time() - os.path.getmtime(CACHE)) / 3600
        if age_h < max_age_h:
            cached = _read(CACHE)
            if not cached.empty:
                return cached

    series = {}
    for key, (sym, name) in SYMBOLS.items():
        s = _yahoo(sym, key)
        if s is None:
            for alt in FALLBACK.get(key, ()):
                s = _yahoo(alt, key)
                if s is not None:
                    break
        if s is not None:
            series[key] = s

    if not series:
        cached = _read(CACHE)
        return cached

    df = None
    for s in series.values():
        df = s.to_frame() if df is None else df.join(s, how="outer")
    df = df.sort_index().ffill(limit=5).reset_index().rename(columns={"index": "date"})
    df.columns = ["date"] + [c for c in df.columns[1:]]
    _write(CACHE, df)
    return df


# ─────────── تزریق به پنل ───────────


def augment(d: pd.DataFrame) -> pd.DataFrame:
    """دو لایهٔ تازه به پنل اضافه می‌کند: فشار دلار جهانی و کشش طلا به نقره.
    اگر داده نبود، ستون‌ها صفر می‌شوند و مدل قبلی همان‌طور کار می‌کند."""
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

        # دلار جهانی بالا → فشار نزولی بر طلا · نسبت طلا/نقره بالا → کشش بازگشتی
        m["s_dxy"] = (-m["dxy_z"] / 2).clip(-1, 1).fillna(0.0)
        m["s_gsr"] = (-m["gsr_z"] / 2).clip(-1, 1).fillna(0.0)

        m["theo_hist"] = m["xau"] * m["usd"] / OUNCE_GRAM * FINENESS_18K
        with np.errstate(divide="ignore", invalid="ignore"):
            m["prem_hist"] = (m["close"] - m["theo_hist"]) / m["theo_hist"] * 100
        return m
    except Exception:
        return d


def coverage(df: pd.DataFrame) -> dict:
    """برای نمایش در تب داده‌ها: چند روز پوشش و آخرین تاریخ هر سری."""
    out = {}
    for col, label in (("xau", "طلا جهانی"), ("xag", "نقره"), ("dxy", "شاخص دلار"), ("tnx", "بازده ۱۰ساله")):
        if df is not None and col in df.columns and not df[col].isna().all():
            last = df["date"].iloc[-1] if "date" in df.columns else None
            out[col] = {"label": label, "rows": int(df[col].notna().sum()), "last": str(last)[:10]}
    return out


if __name__ == "__main__":
    frame = load(force=True)
    if frame is None or frame.empty:
        print("هیچ سری‌ای دریافت نشد.")
    else:
        print(f"ردیف‌ها: {len(frame)} | از {str(frame['date'].min())[:10]} تا {str(frame['date'].max())[:10]}")
        for k, v in coverage(frame).items():
            print(f"  {v['label']}: {v['rows']} روز، آخرین {v['last']}")
        print(f"زمان دریافت: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}Z")