import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

st.set_page_config(
    page_title="Gold18K Intelligence",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ====================== استایل (مینیمال فلت) ======================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');

html, body, [class*="css"], .stMarkdown, div, p, span, label {
    font-family: Vazirmatn, Tahoma, sans-serif !important;
}
.stApp { background-color: #0d1117 !important; }
.block-container { padding-top: 1.2rem; max-width: 1060px; }

.card {
    background: #161b22 !important;
    border: 1px solid #262c36 !important;
    border-radius: 14px;
    padding: 1rem 0.75rem;
    text-align: center;
}
.card-label { color: #8b949e !important; font-size: 0.82rem !important; margin-bottom: 0.4rem; }
.card-value { font-size: 1.3rem !important; font-weight: 700 !important; color: #f0f3f6 !important; }
.pos { color: #3fb950 !important; }
.neg { color: #f85149 !important; }

[data-testid="stMetricValue"] { color: #f0f3f6 !important; font-size: 1.2rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.85rem !important; }
[data-testid="stMetricDelta"] { font-weight: 600 !important; }

.stCaption, [data-testid="stCaptionContainer"] { color: #8b949e !important; font-size: 0.85rem !important; }

div.stButton > button, div.stDownloadButton > button {
    background: #161b22 !important;
    color: #f0f3f6 !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    border: 1px solid #30363d !important;
    border-radius: 10px !important;
    padding: 0.6rem 1rem !important;
}
div.stButton > button:hover, div.stDownloadButton > button:hover {
    background: #1c2129 !important;
    border-color: #e3b341 !important;
    color: #e3b341 !important;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    color: #8b949e !important;
    padding: 0.5rem 1rem !important;
    font-weight: 600 !important;
}
.stTabs [aria-selected="true"] {
    color: #e3b341 !important;
    border-bottom: 2px solid #e3b341 !important;
}

.signal-box {
    border-radius: 14px;
    padding: 1.1rem;
    text-align: center;
    font-size: 1.25rem;
    font-weight: 800;
    margin: 0.4rem 0 0.8rem 0;
}
.buy    { background: rgba(63,185,80,0.10);  color: #3fb950; border: 1px solid rgba(63,185,80,0.45); }
.sell   { background: rgba(248,81,73,0.10);  color: #f85149; border: 1px solid rgba(248,81,73,0.45); }
.neutral{ background: rgba(110,118,129,0.10); color: #adbac7; border: 1px solid rgba(110,118,129,0.40); }

.factor {
    display: flex; justify-content: space-between; align-items: center;
    background: #161b22; border: 1px solid #262c36; border-radius: 10px;
    padding: 0.55rem 0.85rem; margin-bottom: 0.4rem;
}
.factor-name { color: #f0f3f6; font-size: 0.92rem; font-weight: 600; }
.chip {
    font-size: 0.8rem; font-weight: 700; border-radius: 8px;
    padding: 0.15rem 0.55rem;
}
.chip.pos { background: rgba(63,185,80,0.12);  color: #3fb950; }
.chip.neg { background: rgba(248,81,73,0.12);  color: #f85149; }
.factor-desc { color: #8b949e; font-size: 0.8rem; margin-top: 0.15rem; }

table.ind { width: 100%; border-collapse: collapse; }
table.ind td, table.ind th {
    padding: 0.5rem 0.7rem; text-align: right;
    border-bottom: 1px solid #21262d; font-size: 0.9rem;
}
table.ind th { color: #8b949e; font-weight: 600; }
table.ind td.v { color: #f0f3f6; font-weight: 700; direction: ltr; text-align: left; }

.section { font-size: 1.02rem; font-weight: 700; color: #f0f3f6 !important; margin: 1.2rem 0 0.5rem 0; }
.stAlert { opacity: 1 !important; }
</style>
""", unsafe_allow_html=True)

# ====================== منابع ======================
LIVE_API = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/popular.json"
HISTORY_USD = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/USD_IRR_FREE.json"
HISTORY_GOLD18 = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/GOLD_18K_IRR.json"
METAL_API = "https://api.gold-api.com/price/{}"
XAU_HISTORY = "https://stooq.com/q/d/l/?s=xauusd&i=d"


def _get(url, timeout=10, retries=2):
    """دریافت با تلاش مجدد؛ در خطا None برمی‌گرداند."""
    for _ in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            pass
    return None


def to_jalali(dt=None):
    if dt is None:
        dt = datetime.now()
    try:
        import jdatetime
        j = jdatetime.datetime.fromgregorian(datetime=dt)
        return j.strftime("%Y/%m/%d"), j.strftime("%H:%M")
    except Exception:
        g_y, g_m, g_d = dt.year, dt.month, dt.day
        gy2 = g_y - 1600
        days = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
        md = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
        days += md[g_m - 1] + g_d - 1
        if g_m > 2 and ((g_y % 4 == 0 and g_y % 100 != 0) or g_y % 400 == 0):
            days += 1
        j_days = days - 79
        j_np = j_days // 12053
        j_days %= 12053
        j_y = 979 + 33 * j_np + 4 * (j_days // 1461)
        j_days %= 1461
        if j_days >= 366:
            j_y += (j_days - 1) // 365
            j_days = (j_days - 1) % 365
        if j_days < 186:
            j_m = 1 + j_days // 31
            j_d = 1 + j_days % 31
        else:
            j_m = 7 + (j_days - 186) // 30
            j_d = 1 + (j_days - 186) % 30
        return f"{j_y:04d}/{j_m:02d}/{j_d:02d}", dt.strftime("%H:%M")


def jalali_to_greg(s):
    try:
        import jdatetime
        y, m, d = [int(x) for x in str(s).strip().split("/")]
        return jdatetime.date(y, m, d).togregorian().isoformat()
    except Exception:
        return None


# ====================== داده ======================
@st.cache_data(ttl=40, show_spinner=False)
def fetch_live():
    out = {
        "usd": None, "gold18": None,
        "ounce": None, "silver": None, "copper": None,
        "ts": datetime.now().strftime("%H:%M")
    }
    r = _get(LIVE_API, timeout=9)
    if r is not None:
        try:
            for it in r.json().get("data", []):
                s = it.get("symbol", "")
                if s == "USD_IRR_FREE":
                    out["usd"] = {"price": float(it.get("price", 0)), "chg": it.get("change_pct")}
                elif s == "GOLD_18K_IRR":
                    out["gold18"] = {"price": float(it.get("price", 0)), "chg": it.get("change_pct")}
        except Exception:
            pass

    for key, sym in [("ounce", "XAU"), ("silver", "XAG"), ("copper", "HG")]:
        r = _get(METAL_API.format(sym), timeout=7)
        if r is not None:
            try:
                out[key] = {"price": float(r.json().get("price", 0))}
            except Exception:
                pass
    return out


@st.cache_data(ttl=300, show_spinner=False)
def fetch_base_history(days=90):
    try:
        u = pd.DataFrame(_get(HISTORY_USD, timeout=11).json().get("data", []))
        g = pd.DataFrame(_get(HISTORY_GOLD18, timeout=11).json().get("data", []))
        if u.empty or g.empty:
            return None
        for df in [u, g]:
            if "date_jalali" in df.columns:
                df["date"] = df["date_jalali"]
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = pd.merge(
            u[["date", "close"]].rename(columns={"close": "usd"}),
            g[["date", "close"]].rename(columns={"close": "gold18"}),
            on="date", how="inner"
        ).dropna().tail(days).reset_index(drop=True)
        return df
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_ounce_history(days=150):
    """سری تاریخی انس طلا (XAU/USD) از استوق برای محاسبه‌ی پریمیوم تاریخی."""
    try:
        r = _get(XAU_HISTORY, timeout=12)
        if r is None:
            return None
        import io
        df = pd.read_csv(io.StringIO(r.text))
        if "Close" not in df.columns or "Date" not in df.columns:
            return None
        df = df[["Date", "Close"]].rename(columns={"Date": "date_g", "Close": "ounce"})
        df["date_g"] = df["date_g"].astype(str)
        df["ounce"] = pd.to_numeric(df["ounce"], errors="coerce")
        df = df.dropna().tail(days)
        return df.reset_index(drop=True)
    except Exception:
        return None


def theoretical(ounce, usd):
    if not ounce or not usd:
        return None
    return (ounce * usd / 31.1035) * 0.75


def build_dataset():
    base = fetch_base_history()
    if base is None:
        return None
    feat = base.copy()
    feat["date_g"] = feat["date"].apply(jalali_to_greg)

    oh = fetch_ounce_history()
    has_ounce = False
    if oh is not None and feat["date_g"].notna().sum() > 20:
        feat = feat.merge(oh, on="date_g", how="left")
        feat["usd"] = pd.to_numeric(feat["usd"], errors="coerce")
        theo_hist = feat["ounce"] * feat["usd"] / 31.1035 * 0.75
        feat["prem"] = feat["gold18"] - theo_hist
        if feat["prem"].notna().sum() >= 30:
            has_ounce = True
        else:
            feat["prem"] = np.nan
    else:
        feat["prem"] = np.nan

    # --- اندیکاتورها ---
    feat["ret"] = feat["gold18"].pct_change()
    feat["ema20"] = feat["gold18"].ewm(span=20, adjust=False).mean()
    feat["ema50"] = feat["gold18"].ewm(span=50, adjust=False).mean()

    delta = feat["gold18"].diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    feat["rsi"] = 100 - 100 / (1 + rs)

    ema12 = feat["gold18"].ewm(span=12, adjust=False).mean()
    ema26 = feat["gold18"].ewm(span=26, adjust=False).mean()
    feat["macd"] = ema12 - ema26
    feat["macd_sig"] = feat["macd"].ewm(span=9, adjust=False).mean()
    feat["macd_hist"] = feat["macd"] - feat["macd_sig"]

    ma20 = feat["gold18"].rolling(20).mean()
    sd20 = feat["gold18"].rolling(20).std()
    feat["bb_pos"] = (feat["gold18"] - ma20) / (2 * sd20.replace(0, np.nan))

    feat["atr"] = feat["ret"].abs().rolling(14).mean()
    feat["vol10"] = feat["ret"].rolling(10).std() * 100
    feat["mom3"] = feat["gold18"].pct_change(3) * 100
    feat["mom5"] = feat["gold18"].pct_change(5) * 100
    feat["mom10"] = feat["gold18"].pct_change(10) * 100
    feat["usd_mom5"] = feat["usd"].pct_change(5) * 100
    feat["corr"] = feat["ret"].rolling(20).corr(feat["usd"].pct_change())

    feat["has_ounce"] = has_ounce
    return feat


# ====================== موتور تحلیل ======================
def get_prem_z(feat, prem_now):
    """Z-Score واقعی پریمیوم از سری تاریخی؛ در نبود داده، تقریب ثابت."""
    if prem_now is None:
        return None
    try:
        if feat is not None and "prem" in feat.columns and feat["prem"].notna().sum() >= 35:
            s = feat["prem"].dropna()
            mean = s.tail(40).mean()
            std = s.tail(40).std()
            if std and not np.isnan(std) and std > 1:
                return (prem_now - mean) / std
    except Exception:
        pass
    return prem_now / 2.8


def intelligence_engine(live, feat):
    gold = live.get("gold18") or {}
    usd = live.get("usd") or {}
    ounce = live.get("ounce") or {}

    g_price = gold.get("price")
    o_price = ounce.get("price")
    u_price = usd.get("price")

    theo = theoretical(o_price, u_price)
    prem = ((g_price - theo) / theo * 100) if (theo and g_price) else None
    z_prem = get_prem_z(feat, prem)

    row = feat.iloc[-1] if feat is not None else None
    ok = row is not None and len(feat) > 25 and row["rsi"] is not None and not np.isnan(row["rsi"])

    score = 0.0
    factors = []
    max_score = 10.5

    # 1) روند (EMA20/50)
    if ok:
        e20, e50, px = row["ema20"], row["ema50"], row["gold18"]
        if e20 > e50 and px > e20:
            score += 2
            factors.append(("روند صعودی تاییدشده", +2, "قیمت بالای EMA20 و EMA20 بالای EMA50"))
        elif e20 > e50:
            score += 1
            factors.append(("روند صعودی ملایم", +1, "میانگین‌ها صعودی اما قیمت زیر EMA20"))
        elif e20 < e50 and px < e20:
            score -= 2
            factors.append(("روند نزولی تاییدشده", -2, "قیمت زیر EMA20 و EMA20 زیر EMA50"))
        else:
            score -= 1
            factors.append(("روند نزولی ملایم", -1, "میانگین‌ها نزولی اما قیمت بالای EMA20"))

        # 2) RSI
        rsi = row["rsi"]
        if rsi <= 32:
            score += 1.5
            factors.append(("RSI اشباع فروش", +1.5, f"RSI={rsi:.0f} → پتانسیل برگشت صعودی"))
        elif rsi >= 68:
            score -= 1.5
            factors.append(("RSI اشباع خرید", -1.5, f"RSI={rsi:.0f} → ریسک اصلاح"))
        else:
            factors.append(("RSI خنثی", 0, f"RSI={rsi:.0f}"))

        # 3) MACD
        hist, hist_prev = row["macd_hist"], feat["macd_hist"].iloc[-2]
        if hist > 0:
            sc = 1.5 if (not np.isnan(hist_prev) and hist > hist_prev) else 0.8
            score += sc
            factors.append(("MACD مثبت", +sc, "هیستوگرام بالای صفر → مومنتوم صعودی"))
        else:
            sc = 1.5 if (not np.isnan(hist_prev) and hist < hist_prev) else 0.8
            score -= sc
            factors.append(("MACD منفی", -sc, "هیستوگرام زیر صفر → مومنتوم نزولی"))

        # 4) موقعیت بولینگر
        bb = row["bb_pos"]
        if bb is not None and not np.isnan(bb):
            if bb <= -0.9:
                score += 1
                factors.append(("پایین بولینگر", +1, f"فاصله معنادار زیر میانگین ({bb:.1f}σ)"))
            elif bb >= 0.9:
                score -= 1
                factors.append(("بالای بولینگر", -1, f"فاصله معنادار بالای میانگین ({bb:.1f}σ)"))

    # 5) پریمیوم و Z-Score
    if z_prem is not None:
        if z_prem <= -1.5:
            score += 2
            factors.append(("پریمیوم بسیار منفی", +2, f"Z={z_prem:.2f} → ارزش نسبی جذاب"))
        elif z_prem <= -0.7:
            score += 1
            factors.append(("پریمیوم منفی", +1, f"Z={z_prem:.2f}"))
        elif z_prem >= 1.5:
            score -= 2
            factors.append(("پریمیوم بسیار بالا", -2, f"Z={z_prem:.2f} → گران نسبت به جهانی"))
        elif z_prem >= 0.7:
            score -= 1
            factors.append(("پریمیوم بالا", -1, f"Z={z_prem:.2f}"))

    # 6) مومنتوم
    if ok:
        m3, m5 = row["mom3"], row["mom5"]
        if m3 > 1.5 and m5 > 2.5:
            score += 1.5
            factors.append(("مومنتوم صعودی", +1.5, f"۳روزه {m3:+.1f}% | ۵روزه {m5:+.1f}%"))
        elif m3 < -1.5 and m5 < -2.5:
            score -= 1.5
            factors.append(("مومنتوم نزولی", -1.5, f"۳روزه {m3:+.1f}% | ۵روزه {m5:+.1f}%"))

        # 7) دلار با وزن همبستگی
        corr = row["corr"]
        um5 = row["usd_mom5"]
        if corr is not None and not np.isnan(corr) and corr > 0.6:
            if um5 > 1.5:
                score += 1
                factors.append(("حمایت دلار", +1, f"دلار ۵روزه {um5:+.1f}% با همبستگی {corr:.2f}"))
            elif um5 < -1.5:
                score -= 1
                factors.append(("فشار دلار", -1, f"دلار ۵روزه {um5:+.1f}% با همبستگی {corr:.2f}"))

    # جریمه‌ی نوسان
    vol = row["vol10"] if ok else None
    penalty = 1.0
    if vol is not None and not np.isnan(vol):
        if vol > 3.0:
            penalty = 0.70
            factors.append(("نوسان بسیار بالا", 0, f"نوسان {vol:.1f}% → کاهش وزن سیگنال"))
        elif vol > 2.2:
            penalty = 0.85
            factors.append(("نوسان بالا", 0, f"نوسان {vol:.1f}% → احتیاط"))
    score *= penalty

    norm = score / max_score
    if norm >= 0.5:
        regime, signal = "صعودی قوی", "خرید قوی"
    elif norm >= 0.2:
        regime, signal = "صعودی ملایم", "خرید محتاطانه"
    elif norm <= -0.5:
        regime, signal = "نزولی قوی", "فروش / کاهش"
    elif norm <= -0.2:
        regime, signal = "نزولی ملایم", "فروش محتاطانه"
    else:
        regime, signal = "رنج / نامشخص", "خنثی / نظاره‌گر"

    conf = min(92, 52 + abs(norm) * 40)
    if penalty < 1:
        conf *= 0.9
    conf = max(40, conf)

    p_up = max(12, min(88, 50 + norm * 32))
    p_down = 100 - p_up

    # --- پیش‌بینی ---
    pred = None
    if ok and g_price:
        rets = feat["ret"].dropna()
        short = rets.tail(3).mean()
        med = rets.tail(8).mean()
        usd_s = feat["usd"].pct_change().dropna().tail(3).mean()
        corr_safe = row["corr"]
        if corr_safe is None or np.isnan(corr_safe):
            corr_safe = 0.55
        z_term = -0.20 * (z_prem / 100) if z_prem is not None else 0

        if abs(norm) >= 0.45:
            w = (0.34, 0.20, 0.28, 0.18)
        elif abs(norm) >= 0.2:
            w = (0.30, 0.24, 0.28, 0.18)
        else:
            w = (0.26, 0.26, 0.26, 0.22)
        expected = (w[0] * short + w[1] * med + w[2] * (usd_s * corr_safe) + w[3] * z_term)

        daily_vol = rets.tail(10).std()
        if daily_vol is None or np.isnan(daily_vol):
            daily_vol = 0.012

        d1 = g_price * (1 + expected * 0.90)
        d3 = g_price * (1 + expected * 2.15)
        pred = {
            "d1": d1,
            "d1_low": d1 * (1 - daily_vol * 1.05),
            "d1_high": d1 * (1 + daily_vol * 1.05),
            "d3": d3,
            "d3_low": d3 * (1 - daily_vol * 1.7),
            "d3_high": d3 * (1 + daily_vol * 1.7),
            "expected_daily": expected * 100,
        }

    # --- سطوح معامله ---
    levels = None
    if g_price and ok:
        atr = row["atr"]
        if atr is None or np.isnan(atr):
            atr = 0.012
        atr_toman = atr * g_price
        if signal.startswith("خرید"):
            levels = {"entry": g_price, "sl": g_price - 1.6 * atr_toman,
                      "tp": g_price + 2.6 * atr_toman, "atr": atr_toman}
        elif signal.startswith("فروش"):
            levels = {"entry": g_price, "sl": g_price + 1.6 * atr_toman,
                      "tp": g_price - 2.6 * atr_toman, "atr": atr_toman}
        else:
            levels = {"entry": g_price, "sl": None, "tp": None,
                      "atr": atr_toman}

    return {
        "theo": theo, "prem": prem, "z_prem": z_prem,
        "score": score, "norm": norm, "factors": factors,
        "regime": regime, "signal": signal, "confidence": conf,
        "p_up": p_up, "p_down": p_down,
        "pred": pred, "levels": levels,
        "row": row if ok else None,
    }


def quick_backtest(feat):
    """بک‌تست سبک: اعمال امتیاز ساده در هر روز تاریخی و سنجش دقت جهت روز بعد."""
    try:
        d = feat.dropna(subset=["rsi", "macd_hist", "bb_pos", "ema20", "ema50"]).reset_index(drop=True)
        if len(d) < 40:
            return None
        hits = sigs = 0
        for i in range(len(d) - 1):
            r = d.iloc[i]
            s = 0.0
            s += 1 if r["ema20"] > r["ema50"] else -1
            s += 1 if r["macd_hist"] > 0 else -1
            if r["mom5"] > 1.0:
                s += 0.8
            elif r["mom5"] < -1.0:
                s -= 0.8
            if r["bb_pos"] <= -0.9:
                s += 0.6
            elif r["bb_pos"] >= 0.9:
                s -= 0.6
            if r["rsi"] <= 32:
                s += 0.6
            elif r["rsi"] >= 68:
                s -= 0.6
            if abs(s) >= 1.6:
                sigs += 1
                if np.sign(d.iloc[i + 1]["ret"]) == np.sign(s):
                    hits += 1
        if sigs >= 5:
            return {"n": sigs, "hit": hits / sigs * 100}
    except Exception:
        pass
    return None


def build_market_report(live, intel):
    j_date, j_time = to_jalali()
    usd = live.get("usd") or {}
    gold = live.get("gold18") or {}
    ounce = live.get("ounce") or {}
    usd_p = usd.get("price") or 0
    g18 = gold.get("price") or 0
    xau = ounce.get("price")

    factors_txt = ""
    if intel.get("factors"):
        for name, sc, desc in intel["factors"][:5]:
            arrow = "▲" if sc > 0 else ("▼" if sc < 0 else "•")
            factors_txt += f"\n{arrow} {name}: {desc}"
    else:
        factors_txt = "\n• عامل قوی خاصی در داده‌های فعلی دیده نشد."

    lines = [
        "📊 گزارش وضعیت بازار فلزات",
        f"📅 {j_date}  |  🕐 {j_time}",
        "",
        "━━━━━━━━━━━━━━",
        "قیمت‌های لحظه‌ای (تقریبی به تومان)",
        f"🥇 طلای ۱۸ عیار: {g18:,.0f}" if g18 else "🥇 طلای ۱۸ عیار: —",
        f"💵 دلار آزاد: {usd_p:,.0f}" if usd_p else "💵 دلار آزاد: —",
        f"🌍 انس طلا: {xau:,.1f} $" if xau else "🌍 انس طلا: —",
        "",
        "━━━━━━━━━━━━━━",
        f"🎯 سیگنال: {intel.get('signal', '—')}  |  اطمینان: {intel.get('confidence', 0):.0f}٪",
        f"رژیم بازار: {intel.get('regime', '—')}",
        f"احتمال رشد: {intel.get('p_up', 50):.0f}٪  |  احتمال نزول: {intel.get('p_down', 50):.0f}٪",
        "",
        "عوامل دخیل:",
        factors_txt.strip(),
        "",
        "━━━━━━━━━━━━━━",
    ]
    lv = intel.get("levels")
    if lv:
        if lv.get("sl"):
            lines += [
                f"ورود: {lv['entry']:,.0f}",
                f"حد ضرر: {lv['sl']:,.0f}",
                f"هدف: {lv['tp']:,.0f}",
            ]
        else:
            lines.append(f"محدوده نوسان روزانه (ATR): ±{lv['atr']:,.0f}")
    pred = intel.get("pred")
    if pred:
        lines += [
            "",
            f"پیش‌بینی فردا: {pred['d1']:,.0f}",
            f"پیش‌بینی ۳ روز بعد: {pred['d3']:,.0f}",
        ]
    lines += ["", "⚠️ این گزارش توصیه سرمایه‌گذاری نیست."]
    return "\n".join(lines)


def build_signal_text(live, intel):
    j_date, j_time = to_jalali()
    g18 = (live.get("gold18") or {}).get("price") or 0
    lines = [
        "🎯 سیگنال Gold18K",
        f"📅 {j_date}  |  🕐 {j_time}",
        "",
        f"سیگنال: {intel.get('signal', '—')}",
        f"اطمینان: {intel.get('confidence', 0):.0f}٪",
        f"احتمال رشد / نزول: {intel.get('p_up', 50):.0f}٪ / {intel.get('p_down', 50):.0f}٪",
        f"قیمت فعلی طلای ۱۸: {g18:,.0f}",
    ]
    lv = intel.get("levels")
    if lv:
        if lv.get("sl"):
            lines += [f"ورود: {lv['entry']:,.0f}", f"حد ضرر: {lv['sl']:,.0f}", f"هدف: {lv['tp']:,.0f}"]
        else:
            lines.append(f"محدوده نوسان روزانه (ATR): ±{lv['atr']:,.0f}")
    lines += ["", "⚠️ توصیه سرمایه‌گذاری نیست."]
    return "\n".join(lines)


# ====================== اجرا ======================
live = fetch_live()
feat = build_dataset()

if not live.get("gold18"):
    st.error("داده زنده در دسترس نیست. چند لحظه دیگر تلاش کنید.")
    st.stop()

intel = intelligence_engine(live, feat)
report_text = build_market_report(live, intel)
signal_text = build_signal_text(live, intel)
bt = quick_backtest(feat) if feat is not None else None

# ====================== هدر ======================
st.markdown("""
<div style="text-align:center;margin-bottom:1.2rem;">
    <div style="font-size:1.5rem;font-weight:800;color:#e3b341;letter-spacing:0.3px;">🥇 Gold18K Intelligence</div>
    <div style="color:#8b949e;font-size:0.85rem;">موتور سیگنال طلای ۱۸ عیار</div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

def card(label, value, chg=None):
    delta = ""
    if chg is not None:
        cls = "pos" if chg >= 0 else "neg"
        delta = f'<div class="{cls}" style="font-size:0.78rem;font-weight:600;">{chg:+.2f}%</div>'
    st.markdown(
        f'<div class="card"><div class="card-label">{label}</div>'
        f'<div class="card-value">{value}</div>{delta}</div>',
        unsafe_allow_html=True
    )

with c1:
    card("دلار آزاد", f"{live['usd']['price']:,.0f}" if live.get("usd") else "—", live.get("usd", {}).get("chg"))
with c2:
    card("طلای ۱۸ عیار", f"{live['gold18']['price']:,.0f}", live.get("gold18", {}).get("chg"))
with c3:
    card("انس جهانی", f"{live['ounce']['price']:,.1f} $" if live.get("ounce") and live["ounce"].get("price") else "—")
with c4:
    prem_txt = f"{intel['prem']:+.2f}%" if intel["prem"] is not None else "—"
    card("پریمیوم", prem_txt)

# ====================== دکمه‌ها ======================
st.markdown("---")
b1, b2, b3 = st.columns([1, 1.2, 1.2])

with b1:
    if st.button("🔄 بروزرسانی", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with b2:
    st.download_button(
        label="💾 دانلود گزارش کامل",
        data=report_text,
        file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        use_container_width=True
    )
with b3:
    st.download_button(
        label="🎯 دانلود سیگنال",
        data=signal_text,
        file_name=f"signal_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        use_container_width=True
    )

with st.expander("📋 مشاهده و کپی متن گزارش"):
    st.code(report_text, language=None)

# ====================== تب‌ها ======================
t1, t2, t3, t4 = st.tabs(["🎯 سیگنال", "🔮 پیش‌بینی", "📊 اندیکاتورها", "📈 روند قیمت"])

with t1:
    sig_class = "buy" if "خرید" in intel["signal"] else "sell" if "فروش" in intel["signal"] else "neutral"
    st.markdown(
        f'<div class="signal-box {sig_class}">{intel["signal"]}  •  اطمینان {intel["confidence"]:.0f}٪</div>',
        unsafe_allow_html=True
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("احتمال رشد", f"{intel['p_up']:.0f}٪")
    m2.metric("احتمال نزول", f"{intel['p_down']:.0f}٪")
    m3.metric("امتیاز موتور", f"{intel['score']:+.1f} از 10.5")

    if intel.get("levels"):
        lv = intel["levels"]
        st.markdown('<div class="section">سطوح معامله</div>', unsafe_allow_html=True)
        if lv.get("sl"):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("ورود", f"{lv['entry']:,.0f}")
            k2.metric("حد ضرر", f"{lv['sl']:,.0f}")
            k3.metric("هدف", f"{lv['tp']:,.0f}")
            k4.metric("ATR روزانه", f"±{lv['atr']:,.0f}")
        else:
            st.info(f"محدوده نوسان روزانه (ATR): ±{lv['atr']:,.0f} تومان — سیگنال فعال نیست.")

    st.markdown('<div class="section">عوامل مؤثر</div>', unsafe_allow_html=True)
    if intel["factors"]:
        for name, sc, desc in intel["factors"]:
            chip = "pos" if sc > 0 else "neg" if sc < 0 else "neutral"
            chip_color = "color:#8b949e;" if sc == 0 else ""
            st.markdown(
                f'<div class="factor"><div><div class="factor-name">{name}</div>'
                f'<div class="factor-desc">{desc}</div></div>'
                f'<span class="chip {chip}" style="{chip_color}">{sc:+.1f}</span></div>',
                unsafe_allow_html=True
            )
    else:
        st.write("عامل قوی خاصی شناسایی نشد.")

    st.info(f"رژیم: **{intel['regime']}** | پریمیوم: {intel['prem']:+.2f}٪" if intel["prem"] is not None
            else f"رژیم: **{intel['regime']}**")

    if bt:
        st.caption(f"🧪 بک‌تست روی {len(feat)} روز گذشته: {bt['n']} سیگنال، دقت جهت روز بعد ≈ {bt['hit']:.0f}٪")

with t2:
    if intel.get("pred"):
        p = intel["pred"]
        a, b, c = st.columns(3)
        a.metric("فعلی", f"{live['gold18']['price']:,.0f}")
        b.metric("فردا (نقطه‌ای)", f"{p['d1']:,.0f}",
                 delta=f"{(p['d1'] / live['gold18']['price'] - 1) * 100:+.2f}%")
        c.metric("۳ روز بعد", f"{p['d3']:,.0f}",
                 delta=f"{(p['d3'] / live['gold18']['price'] - 1) * 100:+.2f}%")
        st.caption(f"محدوده فردا: {p['d1_low']:,.0f} تا {p['d1_high']:,.0f}")
        st.caption(f"محدوده ۳روزه: {p['d3_low']:,.0f} تا {p['d3_high']:,.0f}")
        st.caption(f"بازده انتظاری روزانه: {p['expected_daily']:+.2f}٪")
    else:
        st.warning("داده کافی برای پیش‌بینی نیست.")

with t3:
    row = intel.get("row")
    if row is not None:
        rows = [
            ("EMA20", f"{row['ema20']:,.0f}"),
            ("EMA50", f"{row['ema50']:,.0f}"),
            ("RSI (14)", f"{row['rsi']:.1f}"),
            ("MACD Hist", f"{row['macd_hist']:,.0f}"),
            ("موقعیت بولینگر (σ)", f"{row['bb_pos']:+.2f}" if not np.isnan(row["bb_pos"]) else "—"),
            ("مومنتوم ۳روزه", f"{row['mom3']:+.2f}%"),
            ("مومنتوم ۵روزه", f"{row['mom5']:+.2f}%"),
            ("مومنتوم ۱۰روزه", f"{row['mom10']:+.2f}%"),
            ("نوسان ۱۰روزه", f"{row['vol10']:.2f}%"),
            ("همبستگی با دلار", f"{row['corr']:.2f}" if not np.isnan(row["corr"]) else "—"),
            ("تئوریک (انس×دلار)", f"{intel['theo']:,.0f}" if intel["theo"] else "—"),
            ("Z-Score پریمیوم", f"{intel['z_prem']:+.2f}" if intel["z_prem"] is not None else "—"),
        ]
        html = "<table class='ind'><tr><th>شاخص</th><th style='text-align:left'>مقدار</th></tr>"
        for n, v in rows:
            html += f"<tr><td>{n}</td><td class='v'>{v}</td></tr>"
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("داده تاریخی کافی برای محاسبه اندیکاتورها نیست.")

with t4:
    if feat is not None and len(feat) > 8:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=feat["date"], y=feat["gold18"], name="طلای ۱۸ عیار",
                                 line=dict(color="#e3b341", width=2.2)), secondary_y=False)
        if "ema20" in feat.columns:
            fig.add_trace(go.Scatter(x=feat["date"], y=feat["ema20"], name="EMA20",
                                     line=dict(color="#58a6ff", width=1, dash="dot")), secondary_y=False)
        fig.add_trace(go.Scatter(x=feat["date"], y=feat["usd"], name="دلار",
                                 line=dict(color="#3fb950", width=1.2, dash="dash")), secondary_y=True)
        fig.update_layout(
            template="plotly_dark", height=320,
            margin=dict(l=10, r=10, t=15, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.1),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("داده تاریخی در دسترس نیست.")

st.caption("این ابزار تحلیلی است و توصیه سرمایه‌گذاری نیست. مدیریت ریسک و حد ضرر در مسئولیت خود شماست.")