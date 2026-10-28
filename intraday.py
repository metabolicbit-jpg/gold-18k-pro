# ========== Gold18K Pro · intraday.py ==========
# 📂 مسیر ریپو: intraday.py
# خواندنِ کندل‌های ۵ دقیقه‌ای و ساختنِ افق یک‌ساعتهٔ واقعی: نوسان، جهت و احتمال.
# اگر فایل نباشد یا کندل کافی نباشد، برنامه به تخمینِ روزانه برمی‌گردد.

from __future__ import annotations

import math
import os
import sqlite3
from contextlib import closing

import numpy as np
import pandas as pd

BARS_DB = os.getenv("GOLD18K_BARS", "data/bars5.db")
MIN_BARS_READY = 864          # سه روز کاملِ ۲۸۸ کندلی
BARS_PER_HOUR = 12
Z80 = 1.2816


def clip(x, lo=-1.0, hi=1.0):
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return 0.0


def load_bars(path: str | None = None, symbol: str = "GOLD_18K_IRR", limit: int = 20000) -> pd.DataFrame:
    """کندل‌های یک نماد، مرتب بر اساس زمان."""
    p = path or BARS_DB
    if not os.path.exists(p):
        return pd.DataFrame()
    try:
        with closing(sqlite3.connect(p, timeout=8)) as con:
            df = pd.read_sql_query(
                "SELECT ts, open, high, low, close, n FROM bars5 WHERE symbol=? ORDER BY ts DESC LIMIT ?",
                con,
                params=(symbol, limit),
            )
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df["dt"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    return df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)


def _knn_hit(comp: np.ndarray, fwd: np.ndarray, current: float, k: int = 40, shrink: int = 15):
    """نرخ بردِ جهتی در نزدیک‌ترین نمونه‌های گذشته، با شرینکِ اندازهٔ نمونه."""
    valid = (~np.isnan(comp)) & (~np.isnan(fwd))
    idx = np.where(valid)[0]
    if len(idx) < 30 or not current:
        return None
    nn = idx[np.argsort(np.abs(comp[idx] - current))[:k]]
    if len(nn) == 0:
        return None
    hit = float((np.sign(fwd[nn]) == np.sign(current)).mean())
    m = len(nn)
    return (m / (m + shrink)) * hit + (shrink / (m + shrink)) * 0.5


def state(bars: pd.DataFrame, daily_comp: float = 0.0, sigma_daily: float = 0.012) -> dict:
    """وضعیتِ درون‌روزی: نوسانِ ۵ دقیقه و ۱ ساعت، مومنتوم، انحراف، و احتمالِ هم‌جهت."""
    out = {
        "ready": False, "n": 0, "last": None, "sigma_5m": None, "sigma_1h": None,
        "mom_z": None, "dev_z": None, "comp": 0.0, "p_up": 0.5, "hit": None,
        "bars_needed": MIN_BARS_READY,
    }
    if bars is None or len(bars) == 0:
        return out

    g = bars.dropna(subset=["close"]).reset_index(drop=True)
    out["n"] = len(g)
    out["last"] = str(g["ts"].iloc[-1]) if len(g) else None
    if len(g) < 30:
        return out

    close = g["close"].astype(float)
    ret = np.log(close).diff()
    s5 = ret.ewm(span=24, adjust=False).std().iloc[-1]
    if s5 is None or (isinstance(s5, float) and math.isnan(s5)) or s5 <= 0 or pd.isna(s5):
        s5 = (sigma_daily or 0.012) / math.sqrt(288)
    s5 = float(s5)
    s1h = s5 * math.sqrt(BARS_PER_HOUR)
    out["sigma_5m"], out["sigma_1h"] = s5, s1h

    zero = close * 0.0
    mom = close.pct_change(BARS_PER_HOUR)
    mom_z = (mom / s1h).replace([np.inf, -np.inf], np.nan).fillna(0.0) if s1h else zero
    ma = close.rolling(BARS_PER_HOUR).mean()
    dev_z = (((close - ma) / close) / s1h).replace([np.inf, -np.inf], np.nan).fillna(0.0) if s1h else zero

    mv = mom_z.to_numpy(dtype=float)
    dv = dev_z.to_numpy(dtype=float)
    comp_i = np.where(np.abs(mv) > 1, np.clip(mv, -1, 1), np.clip(-dv, -1, 1) * 0.7)
    cs = 0.75 * comp_i + 0.25 * clip(daily_comp)
    fwd = (close.pct_change(BARS_PER_HOUR).shift(-BARS_PER_HOUR) * 100).to_numpy(dtype=float)

    out["mom_z"] = float(mv[-1])
    out["dev_z"] = float(dv[-1])
    out["comp"] = float(cs[-1])

    hit = _knn_hit(cs, fwd, out["comp"])
    out["hit"] = hit
    if hit is not None:
        # جهت هرگز معکوس نمی‌شود؛ اگر تاریخچه تأیید نکند، احتمال به ۰٫۵ برمی‌گردد
        out["p_up"] = float(np.clip(0.5 + np.sign(out["comp"]) * max(0.0, hit - 0.5) * 0.9, 0.15, 0.85))
    else:
        out["p_up"] = float(np.clip(1.0 / (1.0 + math.exp(-1.1 * (out["comp"] / 0.6))), 0.15, 0.85))

    out["ready"] = len(g) >= MIN_BARS_READY
    return out


def hourly_band(price: float, sigma_1h: float | None, comp: float) -> dict:
    """بازهٔ ۸۰٪ برای یک ساعت آینده."""
    if not price:
        return {}
    s = float(sigma_1h or 0.004)
    drift = clip(comp) * 0.30 * s
    med = price * math.exp(drift)
    return {
        "lo": price * math.exp(drift - Z80 * s),
        "med": med,
        "hi": price * math.exp(drift + Z80 * s),
        "move": (med / price - 1) * 100,
        "sig": s * 100,
    }