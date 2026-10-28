import io
import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Gold18K Intelligence",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ====================== استایل (مینیمال فلت، کنتراست بالا) ======================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');

html, body, [class*="css"], .stMarkdown, div, p, span, label {
    font-family: Vazirmatn, Tahoma, sans-serif !important;
}
.stApp { background-color: #0d1117 !important; }
.stApp p, .stApp li { color: #dbe2ea !important; }
.block-container { padding-top: 1.2rem; max-width: 1060px; }

.card {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 14px;
    padding: 1rem 0.75rem;
    text-align: center;
}
.card-label { color: #c3ccd6 !important; font-size: 0.85rem !important; margin-bottom: 0.4rem; font-weight: 700; }
.card-value { font-size: 1.3rem !important; font-weight: 800 !important; color: #f0f3f6 !important; }
.pos { color: #3fb950 !important; }
.neg { color: #f85149 !important; }

[data-testid="stMetricValue"] { color: #f0f3f6 !important; font-size: 1.2rem !important; font-weight: 800 !important; }
[data-testid="stMetricLabel"] { color: #c3ccd6 !important; font-size: 0.85rem !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"] { font-weight: 700 !important; }

.stCaption, [data-testid="stCaptionContainer"] { color: #a8b3c0 !important; font-size: 0.88rem !important; }

[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span {
    color: #f0f3f6 !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
}

div.stButton > button, div.stDownloadButton > button {
    background: #161b22 !important;
    color: #f0f3f6 !important;
    font-weight: 700 !important;
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
    color: #dbe2ea !important;
    padding: 0.5rem 1rem !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab"] p { color: inherit !important; }
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
.buy    { background: rgba(63,185,80,0.12);  color: #4ade80; border: 1px solid rgba(63,185,80,0.5); }
.sell   { background: rgba(248,81,73,0.12);  color: #f87171; border: 1px solid rgba(248,81,73,0.5); }
.neutral{ background: rgba(110,118,129,0.12); color: #e2e8f0; border: 1px solid rgba(110,118,129,0.45); }

.factor {
    display: flex; justify-content: space-between; align-items: center;
    background: #161b22; border: 1px solid #30363d; border-radius: 10px;
    padding: 0.55rem 0.85rem; margin-bottom: 0.4rem;
}
.factor-name { color: #f0f3f6; font-size: 0.92rem; font-weight: 700; }
.chip { font-size: 0.8rem; font-weight: 800; border-radius: 8px; padding: 0.15rem 0.55rem; }
.chip.pos { background: rgba(63,185,80,0.14); color: #4ade80; }
.chip.neg { background: rgba(248,81,73,0.14); color: #f87171; }
.chip.neu { background: rgba(110,118,129,0.14); color: #adbac7; }
.factor-desc { color: #a8b3c0; font-size: 0.8rem; margin-top: 0.15rem; }

table.ind { width: 100%; border-collapse: collapse; }
table.ind td, table.ind th {
    padding: 0.5rem 0.7rem; text-align: right;
    border-bottom: 1px solid #21262d; font-size: 0.92rem;
}
table.ind th { color: #c3ccd6; font-weight: 700; }
table.ind td { color: #dbe2ea; font-weight: 600; }
table.ind td.v { color: #f0f3f6; font-weight: 800; direction: ltr; text-align: left; }

.section { font-size: 1.02rem; font-weight: 800; color: #f0f3f6 !important; margin: 1.2rem 0 0.5rem 0; }
.stAlert { opacity: 1 !important; }
[data-testid="stAlert"] p, [data-testid="stAlert"] div { color: inherit !important; }
</style>
""", unsafe_allow_html=True)

# ====================== منابع ======================
LIVE_API = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/popular.json"
HISTORY_USD = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/USD_IRR_FREE.json"
HISTORY_GOLD18 = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/GOLD_18K_IRR.json"
METAL_API = "https://api.gold-api.com/price/{}"
XAU_HISTORY = "https://stooq.com/q/d/l/?s=xauusd&i=d"

FA_DIGITS = str.maketrans("0123456789,%", "۰۱۲۳۴۵۶۷۸۹،٪")
WEEKDAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]  # دوشنبه=0


def fa(x):
    """تبدیل ارقام لاتین به فارسی."""
    return str(x).translate(FA_DIGITS)


def now_tehran():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Tehran"))
    except Exception:
        return datetime.utcnow() + timedelta(hours=3, minutes=30)


def to_jalali(dt=None):
    """بازگشت: (تاریخ شمسی، ساعت، روز هفته فارسی) بر اساس ساعت رسمی تهران."""
    if dt is None:
        dt = now_tehran()
    wd = WEEKDAYS_FA[dt.weekday()]
    try:
        import jdatetime
        j = jdatetime.datetime.fromgregorian(datetime=dt)
        return j.strftime("%Y/%m/%d"), j.strftime("%H:%M"), wd
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
        return f"{j_y:04d}/{j_m:02d}/{j_d:02d}", dt.strftime("%H:%M"), wd


def jalali_to_greg(s):
    try:
        import jdatetime
        y, m, d = [int(x) for x in str(s).strip().split("/")]
        return jdatetime.date(y, m, d).togregorian().isoformat()
    except Exception:
        return None


def _get(url, timeout=10, retries=2):
    for _ in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            pass
    return None


# ====================== داده ======================
@st.cache_data(ttl=40, show_spinner=False)
def fetch_live():
    out = {
        "usd": None, "gold18": None,
        "ounce": None, "silver": None, "copper": None,
        "ts": now_tehran().strftime("%H:%M")
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
    try:
        r = _get(XAU_HISTORY, timeout=12)
        if r is None:
            return None
        df = pd.read_csv(io.StringIO(r.text))
        if "Close" not in df.columns or "Date" not in df.columns:
            return None
        df = df[["Date", "Close"]].rename(columns={"Date": "date_g", "Close": "ounce"})
        df["date_g"] = df["date_g"].astype(str)
        df["ounce"] = pd.to_numeric(df["ounce"], errors="coerce")
        return df.dropna().tail(days).reset_index(drop=True)
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
    feat["prem"] = np.nan
    if oh is not None and feat["date_g"].notna().sum() > 20:
        feat = feat.merge(oh, on="date_g", how="left")
        feat["usd"] = pd.to_numeric(feat["usd"], errors="coerce")
        theo_hist = feat["ounce"] * feat["usd"] / 31.1035 * 0.75
        prem = feat["gold18"] - theo_hist
        if prem.notna().sum() >= 30:
            feat["prem"] = prem
    if feat["prem"].notna().sum() < 30:
        # جایگزین پایدار: نسبت طلا به دلار — شکاف این نسبت از میانگین غلتان خودش
        # همان گران‌بودن/ارزان‌بودن نسبی طلای داخلی را می‌سنجد، حتی بدون داده انس.
        feat["prem"] = feat["gold18"] / feat["usd"]
        feat["prem_proxy"] = True
    else:
        feat["prem_proxy"] = False

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
    return feat


# ====================== پارامترهای موتور (بر اساس سند مرجع) ======================
HORIZON_DAYS = 5   # افق تصمیم؛ تنها پارامتری که در آزمون پایداری یکنوا بود
COST_PCT = 0.45    # هزینه رفت‌وبرگشت معامله (درصد)
COST_MULT = 1.15   # ضریب حاشیه آستانه دروازه هزینه


# ====================== استراتژی‌ها ======================
def prem_z_at(d, i):
    try:
        s = d["prem"].iloc[max(0, i - 40):i + 1].dropna()
        if len(s) >= 35:
            std = s.std()
            mean = s.mean()
            # آستانه نسبی تا هم پریمیوم تومانی و هم نسبت طلا/دلار کار کند
            if std and mean and std / abs(mean) > 0.0005:
                return (s.iloc[-1] - mean) / std
    except Exception:
        pass
    return None


def sc_composite(d, i):
    r = d.iloc[i]
    s, rs = 0.0, []
    s += 1 if r["ema20"] > r["ema50"] else -1
    rs.append("میانگین‌های متحرک: " + ("صعودی" if r["ema20"] > r["ema50"] else "نزولی"))
    s += 1 if r["macd_hist"] > 0 else -1
    rs.append("MACD: " + ("مثبت" if r["macd_hist"] > 0 else "منفی"))
    if r["mom5"] > 1:
        s += 0.8; rs.append("مومنتوم ۵روزه مثبت")
    elif r["mom5"] < -1:
        s -= 0.8; rs.append("مومنتوم ۵روزه منفی")
    bb = r["bb_pos"]
    if not np.isnan(bb):
        if bb <= -0.9:
            s += 0.6; rs.append("قیمت پایین بولینگر")
        elif bb >= 0.9:
            s -= 0.6; rs.append("قیمت بالای بولینگر")
    rsi = r["rsi"]
    if not np.isnan(rsi):
        if rsi <= 32:
            s += 0.6; rs.append("RSI اشباع فروش")
        elif rsi >= 68:
            s -= 0.6; rs.append("RSI اشباع خرید")
    z = prem_z_at(d, i)
    if z is not None:
        if z <= -1.5:
            s += 0.8; rs.append("پریمیوم منفی (ارزش نسبی)")
        elif z >= 1.5:
            s -= 0.8; rs.append("پریمیوم بالا (گران‌نمایی)")
    return s, rs


def sc_ema_cross(d, i):
    r = d.iloc[i]
    s, rs = 0.0, []
    if r["ema20"] > r["ema50"]:
        s += 1.5; rs.append("کراس صعودی EMA20 بالای EMA50")
    else:
        s -= 1.5; rs.append("کراس نزولی EMA20 زیر EMA50")
    if r["gold18"] > r["ema20"]:
        s += 0.8; rs.append("قیمت بالای EMA20")
    else:
        s -= 0.8; rs.append("قیمت زیر EMA20")
    s += 0.7 if r["macd_hist"] > 0 else -0.7
    rs.append("تأیید MACD" if r["macd_hist"] > 0 else "MACD مخالف روند")
    return s, rs


def sc_bb_revert(d, i):
    r = d.iloc[i]
    s, rs = 0.0, []
    bb = r["bb_pos"]
    if np.isnan(bb):
        return 0.0, ["داده بولینگر ناکافی"]
    if bb <= -1:
        s += 1.2; rs.append("فشار فروش شدید زیر باند پایین")
    elif bb <= -0.5:
        s += 0.6; rs.append("نزدیک باند پایین")
    elif bb >= 1:
        s -= 1.2; rs.append("بالاتر از باند بالایی")
    elif bb >= 0.5:
        s -= 0.6; rs.append("نزدیک باند بالایی")
    rsi = r["rsi"]
    if not np.isnan(rsi):
        if rsi <= 35:
            s += 1.0; rs.append(f"RSI={rsi:.0f} (اشباع فروش)")
        elif rsi >= 65:
            s -= 1.0; rs.append(f"RSI={rsi:.0f} (اشباع خرید)")
    if not np.isnan(r["mom3"]) and r["mom3"] < -2:
        s += 0.4; rs.append("افت شدید کوتاه‌مدت، پتانسیل برگشت")
    return s, rs


def sc_breakout(d, i):
    r = d.iloc[i]
    if i < 20:
        return 0.0, []
    s, rs = 0.0, []
    win = d["gold18"].iloc[i - 19:i]
    px = r["gold18"]
    if px >= win.max():
        s += 2.0; rs.append("شکست سقف ۲۰روزه")
    elif px <= win.min():
        s -= 2.0; rs.append("شکست کف ۲۰روزه")
    if not np.isnan(r["mom10"]):
        if r["mom10"] > 1.5:
            s += 0.6; rs.append("مومنتوم ۱۰روزه مثبت")
        elif r["mom10"] < -1.5:
            s -= 0.6; rs.append("مومنتوم ۱۰روزه منفی")
    return s, rs


def sc_premium(d, i):
    z = prem_z_at(d, i)
    if z is None:
        return 0.0, ["سری تاریخی پریمیوم در دسترس نیست"]
    proxy = bool(d["prem_proxy"].iloc[-1]) if "prem_proxy" in d.columns else False
    label = "شاخص نسبی طلا/دلار" if proxy else "Z-Score پریمیوم"
    s = max(-2.4, min(2.4, -z * 1.2))
    rs = [f"{label} = {z:+.2f}"]
    if z <= -1:
        rs.append("طلای داخلی ارزان‌تر از ارزش جهانی")
    elif z >= 1:
        rs.append("طلای داخلی گران‌تر از ارزش جهانی")
    return s, rs


STRATEGIES = [
    {"id": "composite", "name": "ترکیبی هوشمند", "fn": sc_composite, "thr": 1.6,
     "desc": "ترکیب وزن‌دار روند، مومنتوم، RSI، بولینگر و پریمیوم — پیش‌فرض"},
    {"id": "ema_cross", "name": "کراس میانگین متحرک", "fn": sc_ema_cross, "thr": 1.2,
     "desc": "استراتژی کلاسیک روندی: تقاطع EMA20 و EMA50 با تأیید MACD"},
    {"id": "bb_revert", "name": "بازگشت به میانگین (بولینگر)", "fn": sc_bb_revert, "thr": 1.2,
     "desc": "خرید در اشباع فروش و فروش در اشباع خرید بر اساس باندهای بولینگر و RSI"},
    {"id": "breakout", "name": "شکست سقف/کف ۲۰روزه", "fn": sc_breakout, "thr": 1.5,
     "desc": "دنباله‌روی روند با شکست کانال Donchian و تأیید مومنتوم"},
    {"id": "premium", "name": "پریمیوم هوشمند", "fn": sc_premium, "thr": 1.0,
     "desc": "بازگشت پریمیوم طلای داخلی به ارزش جهانی (Z-Score غلتان ۴۰روزه)؛ بدون داده انس، نسبت طلا/دلار"},
]


def backtest_strategy(feat, strat):
    try:
        d = feat
        if len(d) < 45:
            return None
        hits = sigs = 0
        for i in range(30, len(d) - 1):
            s, _ = strat["fn"](d, i)
            if abs(s) >= strat["thr"]:
                sigs += 1
                if np.sign(d.iloc[i + 1]["ret"]) == np.sign(s):
                    hits += 1
        if sigs >= 4:
            return {"n": sigs, "hit": hits / sigs * 100}
    except Exception:
        pass
    return None


def backtest_all(feat):
    return {st_["id"]: backtest_strategy(feat, st_) for st_ in STRATEGIES}


def bt_stats_range(feat, strat, i0, i1):
    """آمار واقعی روی یک بازه: نتیجه روز بعد + افق ۵روزه + آمار جهت‌دار
    (برای قاعده سرخ کالیبراسیون). خروجی: تعداد سیگنال، وین‌ریت، میانگین بازده
    هر سیگنال، بازده تجمعی، بازده بازار، وین‌ریت/بازده ۵روزه، وین‌ریت جداگانه
    سیگنال‌های خرید و فروش."""
    d = feat
    n = len(d)
    sigs = wins = 0
    total_ret = 0.0
    bench = 0.0
    sigs5 = wins5 = 0
    total5 = 0.0
    buy_n = buy_w = sell_n = sell_w = 0
    g = d["gold18"]
    for i in range(i0, i1):
        s, _ = strat["fn"](d, i)
        r = d.iloc[i + 1]["ret"]
        if r is None or pd.isna(r):
            continue
        bench += r
        if abs(s) >= strat["thr"]:
            pos = 1.0 if s > 0 else -1.0
            rr = pos * r
            sigs += 1
            total_ret += rr
            if rr > 0:
                wins += 1
            if pos > 0:
                buy_n += 1
                if rr > 0:
                    buy_w += 1
            else:
                sell_n += 1
                if rr > 0:
                    sell_w += 1
            j = i + HORIZON_DAYS
            if j < n:
                g_i, g_j = g.iloc[i], g.iloc[j]
                if g_i and g_j and not pd.isna(g_i) and not pd.isna(g_j):
                    r5 = pos * (g_j / g_i - 1)
                    sigs5 += 1
                    total5 += r5
                    if r5 > 0:
                        wins5 += 1
    return {
        "n": sigs,
        "hit": (wins / sigs * 100) if sigs else None,
        "avg_ret": (total_ret / sigs * 100) if sigs else None,
        "total_ret": total_ret * 100,
        "bench_ret": bench * 100,
        "n5": sigs5,
        "hit5": (wins5 / sigs5 * 100) if sigs5 else None,
        "avg5": (total5 / sigs5 * 100) if sigs5 else None,
        "buy_n": buy_n,
        "buy_hit": (buy_w / buy_n * 100) if buy_n else None,
        "sell_n": sell_n,
        "sell_hit": (sell_w / sell_n * 100) if sell_n else None,
    }


def run_evaluation(feat):
    """بک‌تست (۷۰٪ اول داده) + فورواردتست واقعی (۳۰٪ آخر، خارج از نمونه)."""
    try:
        if feat is None or len(feat) < 60:
            return None
        split = max(35, int(len(feat) * 0.7))
        out = {"split_date": str(feat["date"].iloc[split]), "strats": {}}
        for st in STRATEGIES:
            ins = bt_stats_range(feat, st, 30, split)
            oos = bt_stats_range(feat, st, split, len(feat) - 1)
            out["strats"][st["id"]] = {"ins": ins, "oos": oos}
        return out
    except Exception:
        return None


def consensus_votes(feat):
    """رأی هر ۵ استراتژی در لحظه فعلی: (خرید، فروش، خنثی)."""
    buy = sell = neu = 0
    if feat is not None:
        i = len(feat) - 1
        for st in STRATEGIES:
            s, _ = st["fn"](feat, i)
            if s >= st["thr"] * 0.6:
                buy += 1
            elif s <= -st["thr"] * 0.6:
                sell += 1
            else:
                neu += 1
    return buy, sell, neu


# ====================== موتور اجرا ======================
def fn(v):
    """عدد با جداکننده هزارگان و ارقام فارسی."""
    return fa(format(v, ",.0f"))


def fp(v):
    """درصد با علامت و ارقام فارسی."""
    return fa(format(v, "+.2f")) + "٪"


def fhit(blk):
    """وین‌ریت یک بلوک آماری به‌صورت درصد فارسی یا —؛ نمونه زیر ۱۰ سیگنال علامت هشدار می‌گیرد."""
    if blk and blk.get("hit") is not None:
        s = fa(format(blk["hit"], ".0f")) + "٪"
        if blk.get("n", 0) < 10:
            s += " ⚠️"
        return s
    return "—"


def fhit5(blk):
    """وین‌ریت افق ۵روزه یک بلوک آماری؛ نمونه زیر ۱۰ سیگنال علامت هشدار می‌گیرد."""
    if blk and blk.get("hit5") is not None:
        s = fa(format(blk["hit5"], ".0f")) + "٪"
        if blk.get("n5", 0) < 10:
            s += " ⚠️"
        return s
    return "—"


def run_strategy(feat, strat, cons=0.0, bt=None):
    i = len(feat) - 1
    score, reasons = strat["fn"](feat, i)
    norm = score / strat["thr"]
    if norm >= 1.5:
        regime, signal = "صعودی قوی", "خرید قوی"
    elif norm >= 0.6:
        regime, signal = "صعودی ملایم", "خرید محتاطانه"
    elif norm <= -1.5:
        regime, signal = "نزولی قوی", "فروش / کاهش"
    elif norm <= -0.6:
        regime, signal = "نزولی ملایم", "فروش محتاطانه"
    else:
        regime, signal = "رنج / نامشخص", "خنثی / نظاره‌گر"

    # تعدیل اطمینان و احتمال با اجماع سایر استراتژی‌ها
    conf = max(42, min(92, 52 + abs(norm) * 22))
    conf = max(40, min(94, conf + cons * 9))
    p_up = max(12, min(88, 50 + norm * 16 + cons * 5))

    # قاعده سرخ کالیبراسیون: اگر تاریخچه جهتِ سیگنال را تأیید نکند، احتمال به ۵۰
    # برمی‌گردد (لبه صفر می‌شود) و هرگز جهت بی‌صدا معکوس نمی‌شود.
    calib_note = None
    dirn = None
    if signal.startswith("خرید"):
        dirn = "buy"
    elif signal.startswith("فروش"):
        dirn = "sell"
    if bt is not None and dirn:
        if dirn == "buy" and (bt.get("buy_n") or 0) >= 5 and bt.get("buy_hit") is not None and bt["buy_hit"] < 50:
            p_up = 50.0
            calib_note = "تاریخچه جهت خرید این استراتژی را تأیید نمی‌کند؛ احتمال به ۵۰٪ برگشت."
        elif dirn == "sell" and (bt.get("sell_n") or 0) >= 5 and bt.get("sell_hit") is not None and bt["sell_hit"] < 50:
            p_up = 50.0
            calib_note = "تاریخچه جهت فروش این استراتژی را تأیید نمی‌کند؛ احتمال به ۵۰٪ برگشت."

    p_down = 100 - p_up

    # دروازه هزینه: لبه انتظاری افق ۵روزه باید از هزینه رفت‌وبرگشت بیشتر شود،
    # وگرنه خروجی «نظاره» است — پرشمارترین و درست‌ترین خروجی موتور.
    p_dir = p_up if dirn == "buy" else p_down if dirn == "sell" else 50.0
    try:
        v = feat["ret"].tail(10).std()
        vol = v * 100 if (v is not None and not np.isnan(v) and v > 0) else 1.2
    except Exception:
        vol = 1.2
    edge = (2 * p_dir / 100 - 1) * 0.8 * vol * (HORIZON_DAYS ** 0.5)
    edge_thr = COST_PCT * COST_MULT
    gated = dirn is not None and abs(edge) < edge_thr
    raw_signal = signal
    if gated:
        signal = "نظاره — لبه زیر هزینه"
    else:
        reasons = list(reasons) + [
            "لبه انتظاری " + fa(str(HORIZON_DAYS)) + "روزه: " + fp(edge)
            + " در برابر آستانه هزینه " + fp(edge_thr)
        ]

    return {"score": score, "norm": norm, "reasons": reasons,
            "regime": regime, "signal": signal, "raw_signal": raw_signal,
            "confidence": conf, "p_up": p_up, "p_down": p_down,
            "edge": edge, "edge_thr": edge_thr, "gated": gated,
            "dirn": dirn, "calib_note": calib_note}


def make_levels(feat, g_price, signal):
    try:
        atr = feat["atr"].iloc[-1]
        if atr is None or np.isnan(atr):
            atr = 0.012
        atr_t = atr * g_price
        if signal.startswith("خرید"):
            return {"entry": g_price, "sl": g_price - 1.6 * atr_t,
                    "tp": g_price + 2.6 * atr_t, "atr": atr_t}
        if signal.startswith("فروش"):
            return {"entry": g_price, "sl": g_price + 1.6 * atr_t,
                    "tp": g_price - 2.6 * atr_t, "atr": atr_t}
        return {"entry": g_price, "sl": None, "tp": None, "atr": atr_t}
    except Exception:
        return None


def make_pred(feat, g_price, p_up):
    try:
        rets = feat["ret"].dropna()
        if len(rets) < 15:
            return None
        short = rets.tail(3).mean()
        med = rets.tail(8).mean()
        usd_s = feat["usd"].pct_change().dropna().tail(3).mean()
        corr = feat["corr"].iloc[-1]
        corr = 0.55 if (corr is None or np.isnan(corr)) else corr
        drift = (0.5 if p_up >= 58 else (-0.5 if p_up <= 42 else 0.0)) / 100
        expected = 0.38 * short + 0.28 * med + 0.24 * (usd_s * corr) + drift
        daily_vol = rets.tail(10).std()
        if daily_vol is None or np.isnan(daily_vol):
            daily_vol = 0.012
        d1 = g_price * (1 + expected * 0.90)
        d3 = g_price * (1 + expected * 2.15)
        return {
            "d1": d1, "d1_low": d1 * (1 - daily_vol * 1.05), "d1_high": d1 * (1 + daily_vol * 1.05),
            "d3": d3, "d3_low": d3 * (1 - daily_vol * 1.7), "d3_high": d3 * (1 + daily_vol * 1.7),
            "expected_daily": expected * 100,
        }
    except Exception:
        return None


def theo_now(live):
    usd = (live.get("usd") or {}).get("price")
    ounce = (live.get("ounce") or {}).get("price")
    return theoretical(ounce, usd)


def build_market_report(live, feat, sig, strat, bt, lv, pred, z_prem,
                        fwd=None, split_date=None, votes=None):
    j_date, j_time, j_wd = to_jalali()
    usd_p = (live.get("usd") or {}).get("price") or 0
    g18 = (live.get("gold18") or {}).get("price") or 0
    xau = (live.get("ounce") or {}).get("price")
    theo = theo_now(live)
    prem = ((g18 - theo) / theo * 100) if (theo and g18) else None

    conf_s = fa(format(sig["confidence"], ".0f")) + "٪"
    pup_s = fa(format(sig["p_up"], ".0f")) + "٪"
    pdn_s = fa(format(sig["p_down"], ".0f")) + "٪"
    hit_s = fhit(bt) if bt else None
    n_s = fa(str(bt["n"])) if bt else None

    lines = [
        "📊 گزارش جامع بازار طلای ۱۸ عیار",
        f"📅 {j_wd} {fa(j_date)} | 🕐 {fa(j_time)} (ساعت رسمی تهران)",
        "",
        "━━━━━━━━━━━━━━",
        "قیمت‌های لحظه‌ای (تومان)",
    ]
    lines.append(f"🥇 طلای ۱۸ عیار: {fn(g18)}" if g18 else "🥇 طلای ۱۸ عیار: —")
    lines.append(f"💵 دلار آزاد: {fn(usd_p)}" if usd_p else "💵 دلار آزاد: —")
    lines.append(f"🌍 انس جهانی: {fa(format(xau, ',.1f'))} $" if xau else "🌍 انس جهانی: —")
    lines.append(f"🧮 ارزش تئوریک: {fn(theo)}" if theo else "🧮 ارزش تئوریک: —")
    lines.append(f"📈 پریمیوم داخلی: {fp(prem)}" if prem is not None else "📈 پریمیوم: —")

    lines += [
        "",
        "━━━━━━━━━━━━━━",
        f"🎯 استراتژی فعال: {strat['name']}",
        f"سیگنال: {sig['signal']} | اطمینان: {conf_s}",
        f"رژیم بازار: {sig['regime']}",
        f"احتمال رشد: {pup_s} | احتمال نزول: {pdn_s}",
    ]
    if sig.get("dirn") and sig.get("edge") is not None:
        lines.append("لبه انتظاری " + fa(str(HORIZON_DAYS)) + "روزه: " + fp(sig["edge"])
                     + " | آستانه هزینه: " + fp(sig["edge_thr"]))
        if sig.get("gated"):
            lines.append("دروازه هزینه: سیگنال به نظاره تبدیل شد (لبه < هزینه رفت‌وبرگشت).")
    if sig.get("calib_note"):
        lines.append("کالیبراسیون: " + sig["calib_note"])
    if hit_s:
        lines.append(f"وین‌ریت بک‌تست این استراتژی: {hit_s} ({n_s} سیگنال)")
    if votes:
        bv, sv, nv = votes
        lines.append(f"اجماع استراتژی‌ها: {fa(str(bv))} خرید | {fa(str(sv))} فروش | {fa(str(nv))} خنثی")
    if fwd:
        lines += ["", "🧪 فورواردتست (داده خارج از نمونه):"]
        if split_date:
            lines.append(f"شروع بازه آزمون: {fa(split_date)}")
        fh_s = fa(format(fwd["hit"], ".0f")) + "٪" if fwd.get("hit") is not None else "—"
        fn_s = fa(str(fwd["n"])) if fwd.get("n") else "۰"
        lines.append(f"وین‌ریت: {fh_s} | تعداد سیگنال: {fn_s}")
        if fwd.get("avg_ret") is not None:
            lines.append(f"میانگین بازده هر سیگنال: {fp(fwd['avg_ret'])}")
        if fwd.get("n"):
            lines.append(f"بازده تجمعی سیگنال‌ها: {fp(fwd['total_ret'])} در برابر بازار: {fp(fwd['bench_ret'])}")
    if sig["reasons"]:
        lines += ["", "دلایل سیگنال:"]
        for rs in sig["reasons"][:6]:
            lines.append(f"• {rs}")

    lines += ["", "━━━━━━━━━━━━━━"]
    if lv:
        if lv.get("sl"):
            lines += [
                f"ورود: {fn(lv['entry'])}",
                f"حد ضرر: {fn(lv['sl'])}",
                f"هدف: {fn(lv['tp'])}",
            ]
        else:
            lines.append(f"محدوده نوسان روزانه (ATR): {fa('±')}{fn(lv['atr'])}")
    if pred:
        lines += [
            "",
            f"🔮 پیش‌بینی فردا: {fn(pred['d1'])}",
            f"   محدوده: {fn(pred['d1_low'])} تا {fn(pred['d1_high'])}",
            f"🔮 پیش‌بینی ۳ روز بعد: {fn(pred['d3'])}",
            f"   محدوده: {fn(pred['d3_low'])} تا {fn(pred['d3_high'])}",
        ]
    row = feat.iloc[-1] if feat is not None else None
    if row is not None and not np.isnan(row["rsi"]):
        lines += [
            "",
            "━━━━━━━━━━━━━━",
            "شاخص‌های کلیدی:",
            f"• RSI(۱۴): {fa(format(row['rsi'], '.1f'))}",
            f"• EMA20: {fn(row['ema20'])} | EMA50: {fn(row['ema50'])}",
            f"• نوسان ۱۰روزه: {fa(format(row['vol10'], '.1f'))}٪",
        ]
        if z_prem is not None:
            lines.append(f"• Z-Score پریمیوم: {fa(format(z_prem, '+.2f'))}")
    lines += ["", "⚠️ این گزارش توصیه سرمایه‌گذاری نیست."]
    return "\n".join(lines)


def build_signal_text(sig, strat, lv, g18, votes=None):
    j_date, j_time, j_wd = to_jalali()
    conf_s = fa(format(sig["confidence"], ".0f")) + "٪"
    pup_s = fa(format(sig["p_up"], ".0f")) + "٪"
    pdn_s = fa(format(sig["p_down"], ".0f")) + "٪"
    lines = [
        "🎯 سیگنال Gold18K",
        f"📅 {j_wd} {fa(j_date)} | 🕐 {fa(j_time)} تهران",
        "",
        f"استراتژی: {strat['name']}",
        f"سیگنال: {sig['signal']}",
        f"اطمینان: {conf_s}",
        f"احتمال رشد / نزول: {pup_s} / {pdn_s}",
        f"طلای ۱۸ عیار: {fn(g18)}",
    ]
    if sig.get("dirn") and sig.get("edge") is not None:
        lines.append("لبه انتظاری " + fa(str(HORIZON_DAYS)) + "روزه: " + fp(sig["edge"])
                     + " | آستانه هزینه: " + fp(sig["edge_thr"]))
    if sig.get("calib_note"):
        lines.append("کالیبراسیون: " + sig["calib_note"])
    if votes:
        bv, sv, nv = votes
        lines.append(f"اجماع: {fa(str(bv))} خرید / {fa(str(sv))} فروش / {fa(str(nv))} خنثی از {fa(str(len(STRATEGIES)))} استراتژی")
    if lv:
        if lv.get("sl"):
            lines += [f"ورود: {fn(lv['entry'])}",
                      f"حد ضرر: {fn(lv['sl'])}",
                      f"هدف: {fn(lv['tp'])}"]
        else:
            lines.append(f"ATR روزانه: {fa('±')}{fn(lv['atr'])}")
    lines += ["", "⚠️ توصیه سرمایه‌گذاری نیست."]
    return "\n".join(lines)


# ====================== اجرا ======================
live = fetch_live()
feat = build_dataset()

if not live.get("gold18"):
    st.error("داده زنده در دسترس نیست. چند لحظه دیگر تلاش کنید.")
    st.stop()

g_price = live["gold18"]["price"]
eval_ = run_evaluation(feat) if feat is not None else None
if eval_:
    bts = {sid: v["ins"] for sid, v in eval_["strats"].items()}
    fwd = {sid: v["oos"] for sid, v in eval_["strats"].items()}
    split_date = eval_["split_date"]
else:
    bts, fwd, split_date = {}, {}, None

buy_v, sell_v, neu_v = consensus_votes(feat)
cons = (buy_v - sell_v) / max(1, len(STRATEGIES))

AUTO_LABEL = "🏆 خودکار — بهترین بر اساس فورواردتست"


def pick_best_strategy():
    """استراتژی با بهترین میانگین بازده افق ۵روزه در فورواردتست (حداقل ۵ سیگنال)؛
    اگر نمونه ۵روزه کم بود، میانگین روز بعد."""
    best, best_key = None, None
    for s_ in STRATEGIES:
        f = fwd.get(s_["id"])
        if not f:
            continue
        key = None
        if f.get("n5", 0) >= 5 and f.get("avg5") is not None:
            key = f["avg5"]
        elif f.get("n", 0) >= 5 and f.get("avg_ret") is not None:
            key = f["avg_ret"]
        if key is not None and (best_key is None or key > best_key):
            best, best_key = s_, key
    return best if best is not None else STRATEGIES[0]


strat_options = [AUTO_LABEL]
for s_ in STRATEGIES:
    strat_options.append(s_["name"] + " • دقت " + fhit(bts.get(s_["id"])))

selected = st.selectbox(
    "استراتژی سیگنال‌دهی",
    strat_options,
    index=0,
    help="گزینه خودکار استراتژی با بهترین میانگین بازده افق ۵روزه در فورواردتست (حداقل ۵ سیگنال) را برمی‌گزیند. علامت ⚠️ یعنی نمونه زیر ۱۰ سیگنال و عدد از نظر آماری قابل اتکا نیست."
)
if selected == AUTO_LABEL:
    strat = pick_best_strategy()
else:
    strat = STRATEGIES[strat_options.index(selected) - 1]

if feat is not None:
    sig = run_strategy(feat, strat, cons, bts.get(strat["id"]))
else:
    sig = {"score": 0, "norm": 0, "reasons": ["داده تاریخی ناکافی"],
           "regime": "نامشخص", "signal": "خنثی / نظاره‌گر",
           "raw_signal": "خنثی / نظاره‌گر",
           "confidence": 45, "p_up": 50, "p_down": 50,
           "edge": 0.0, "edge_thr": COST_PCT * COST_MULT,
           "gated": False, "dirn": None, "calib_note": None}
lv = make_levels(feat, g_price, sig["signal"])
pred = make_pred(feat, g_price, sig["p_up"]) if feat is not None else None
z_prem = prem_z_at(feat, len(feat) - 1) if feat is not None else None
theo = theo_now(live)
prem = ((g_price - theo) / theo * 100) if theo else None

report_text = build_market_report(live, feat, sig, strat, bts.get(strat["id"]), lv, pred, z_prem,
                                  fwd.get(strat["id"]), split_date, (buy_v, sell_v, neu_v))
signal_text = build_signal_text(sig, strat, lv, g_price, (buy_v, sell_v, neu_v))

# ====================== هدر ======================
j_date, j_time, j_wd = to_jalali()
st.markdown(f"""
<div style="text-align:center;margin-bottom:1.2rem;">
    <div style="font-size:1.5rem;font-weight:800;color:#e3b341;">🥇 Gold18K Intelligence</div>
    <div style="color:#dbe2ea;font-size:0.9rem;font-weight:600;">{j_wd} {fa(j_date)} — موتور سیگنال طلای ۱۸ عیار</div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

def card(label, value, chg=None):
    delta = ""
    if chg is not None:
        cls = "pos" if chg >= 0 else "neg"
        delta = f'<div class="{cls}" style="font-size:0.8rem;font-weight:700;">{fp(chg)}</div>'
    st.markdown(
        f'<div class="card"><div class="card-label">{label}</div>'
        f'<div class="card-value">{fa(value)}</div>{delta}</div>',
        unsafe_allow_html=True
    )

with c1:
    usd_val = fn(live["usd"]["price"]) if live.get("usd") else "—"
    card("دلار آزاد", usd_val, live.get("usd", {}).get("chg"))
with c2:
    card("طلای ۱۸ عیار", fn(g_price), live.get("gold18", {}).get("chg"))
with c3:
    oz = live.get("ounce", {}).get("price")
    card("انس جهانی", fa(format(oz, ",.1f")) + " $" if oz else "—")
with c4:
    card("پریمیوم", fp(prem) if prem is not None else "—")

# ====================== دکمه‌ها ======================
st.markdown("---")
b1, b2, b3 = st.columns([1, 1.2, 1.2])
with b1:
    if st.button("🔄 بروزرسانی", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with b2:
    st.download_button("💾 دانلود گزارش کامل", data=report_text,
                       file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                       mime="text/plain", use_container_width=True)
with b3:
    st.download_button("🎯 دانلود سیگنال", data=signal_text,
                       file_name=f"signal_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                       mime="text/plain", use_container_width=True)

with st.expander("📋 مشاهده و کپی متن گزارش"):
    st.code(report_text, language=None)

# ====================== تب‌ها ======================
t1, t2, t3, t4, t5, t6 = st.tabs(["🎯 سیگنال", "🔮 پیش‌بینی", "📊 اندیکاتورها", "⚖️ مقایسه استراتژی‌ها", "🧪 بک‌تست و فورواردتست", "📈 روند قیمت"])

with t1:
    sig_class = "buy" if "خرید" in sig["signal"] else "sell" if "فروش" in sig["signal"] else "neutral"
    conf_s = fa(format(sig["confidence"], ".0f")) + "٪"
    box_line = sig["signal"] + "  •  اطمینان " + conf_s
    if sig.get("gated"):
        box_line += "  •  لبه " + fp(sig["edge"]) + " < هزینه " + fp(sig["edge_thr"])
    st.markdown(
        f'<div class="signal-box {sig_class}">{box_line}</div>',
        unsafe_allow_html=True
    )
    if sig.get("gated"):
        st.caption("دروازه هزینه فعال است: لبه انتظاری افق ۵روزه کمتر از هزینه رفت‌وبرگشت (×۱٫۱۵) است، پس خروجی درست «نظاره» است.")
    if sig.get("calib_note"):
        st.caption("⚖️ " + sig["calib_note"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("احتمال رشد", fa(format(sig["p_up"], ".0f")) + "٪")
    m2.metric("احتمال نزول", fa(format(sig["p_down"], ".0f")) + "٪")
    m3.metric("امتیاز استراتژی", fa(format(sig["score"], "+.1f")))
    b = bts.get(strat["id"])
    m4.metric("وین‌ریت بک‌تست", fhit(b))
    f_ = fwd.get(strat["id"])
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("وین‌ریت فورواردتست", fhit(f_))
    m6.metric("بازده/سیگنال (فوروارد)", fp(f_["avg_ret"]) if f_ and f_.get("avg_ret") is not None else "—")
    m7.metric("اجماع خرید", fa(str(buy_v)) + " از " + fa(str(len(STRATEGIES))))
    m8.metric("اجماع فروش", fa(str(sell_v)) + " از " + fa(str(len(STRATEGIES))))
    n9, n10, n11, n12 = st.columns(4)
    n9.metric("لبه انتظاری (" + fa(str(HORIZON_DAYS)) + "روزه)",
              fp(sig["edge"]) if sig.get("edge") is not None else "—")
    n10.metric("آستانه هزینه", fp(sig.get("edge_thr") or COST_PCT * COST_MULT))
    n11.metric("دروازه هزینه", "عبور ✓" if sig.get("dirn") and not sig.get("gated")
               else ("نظاره" if sig.get("dirn") else "—"))
    n12.metric("وین‌ریت ۵روزه (فوروارد)", fhit5(f_))

    if lv:
        st.markdown('<div class="section">سطوح معامله</div>', unsafe_allow_html=True)
        if lv.get("sl"):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("ورود", fn(lv["entry"]))
            k2.metric("حد ضرر", fn(lv["sl"]))
            k3.metric("هدف", fn(lv["tp"]))
            k4.metric("ATR روزانه", fa("±") + fn(lv["atr"]))
        else:
            st.info(f"محدوده نوسان روزانه (ATR): {fa('±')}{fn(lv['atr'])} تومان — سیگنال فعال نیست.")

    st.markdown('<div class="section">دلایل سیگنال</div>', unsafe_allow_html=True)
    if sig["reasons"]:
        for rs in sig["reasons"]:
            st.markdown(
                f'<div class="factor"><div class="factor-name">{rs}</div></div>',
                unsafe_allow_html=True
            )
    else:
        st.write("دلیل مشخصی ثبت نشد.")
    st.info(f"رژیم: **{sig['regime']}**")

with t2:
    if pred:
        a, b, c = st.columns(3)
        a.metric("فعلی", fn(g_price))
        b.metric("فردا (نقطه‌ای)", fn(pred["d1"]),
                 delta=fp((pred["d1"] / g_price - 1) * 100))
        c.metric("۳ روز بعد", fn(pred["d3"]),
                 delta=fp((pred["d3"] / g_price - 1) * 100))
        st.caption(f"محدوده فردا: {fn(pred['d1_low'])} تا {fn(pred['d1_high'])}")
        st.caption(f"محدوده ۳روزه: {fn(pred['d3_low'])} تا {fn(pred['d3_high'])}")
        st.caption(f"بازده انتظاری روزانه: {fp(pred['expected_daily'])}")
    else:
        st.warning("داده کافی برای پیش‌بینی نیست.")

with t3:
    row = feat.iloc[-1] if feat is not None else None
    if row is not None and not np.isnan(row["rsi"]):
        zlab = "Z-Score پریمیوم"
        if "prem_proxy" in feat.columns and bool(feat["prem_proxy"].iloc[-1]):
            zlab = "شاخص نسبی طلا/دلار (تقریبی)"
        rows = [
            ("EMA20", fn(row["ema20"])),
            ("EMA50", fn(row["ema50"])),
            ("RSI (14)", fa(format(row["rsi"], ".1f"))),
            ("MACD Hist", fn(row["macd_hist"])),
            ("موقعیت بولینگر (σ)", fa(format(row["bb_pos"], "+.2f")) if not np.isnan(row["bb_pos"]) else "—"),
            ("مومنتوم ۳روزه", fp(row["mom3"])),
            ("مومنتوم ۵روزه", fp(row["mom5"])),
            ("مومنتوم ۱۰روزه", fp(row["mom10"])),
            ("نوسان ۱۰روزه", fa(format(row["vol10"], ".2f")) + "٪"),
            ("همبستگی با دلار", fa(format(row["corr"], ".2f")) if not np.isnan(row["corr"]) else "—"),
            ("ارزش تئوریک", fn(theo) if theo else "—"),
            (zlab, fa(format(z_prem, "+.2f")) if z_prem is not None else "—"),
        ]
        html = "<table class='ind'><tr><th>شاخص</th><th style='text-align:left'>مقدار</th></tr>"
        for n, v in rows:
            html += f"<tr><td>{n}</td><td class='v'>{v}</td></tr>"
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("داده تاریخی کافی برای محاسبه اندیکاتورها نیست.")

with t4:
    st.caption("وین‌ریت = سهم سیگنال‌هایی که جهت روز بعد را درست حدس زده‌اند. فورواردتست روی ۳۰٪ آخر داده (خارج از نمونه) محاسبه می‌شود. علامت ⚠️ یعنی نمونه زیر ۱۰ سیگنال است.")
    if feat is not None:
        html = ("<table class='ind'><tr><th>استراتژی</th><th>سیگنال فعلی</th>"
                "<th style='text-align:left'>وین‌ریت بک‌تست</th>"
                "<th style='text-align:left'>وین‌ریت فورواردتست</th>"
                "<th style='text-align:left'>بازده/سیگنال (فوروارد)</th></tr>")
        for s_ in STRATEGIES:
            sc_, _ = s_["fn"](feat, len(feat) - 1)
            if sc_ >= s_["thr"] * 0.6:
                cur = "خرید"
            elif sc_ <= -s_["thr"] * 0.6:
                cur = "فروش"
            else:
                cur = "خنثی"
            b = bts.get(s_["id"])
            hit = fhit(b)
            f_ = fwd.get(s_["id"])
            oos_hit = fhit(f_)
            oos_avg = fp(f_["avg_ret"]) if f_ and f_.get("avg_ret") is not None else "—"
            html += (f"<tr><td>{s_['name']}</td><td>{cur}</td>"
                     f"<td class='v'>{hit}</td><td class='v'>{oos_hit}</td>"
                     f"<td class='v'>{oos_avg}</td></tr>")
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)
        for s_ in STRATEGIES:
            st.caption(f"**{s_['name']}**: {s_['desc']}")
    else:
        st.warning("داده تاریخی کافی برای مقایسه نیست.")

with t5:
    if eval_:
        st.caption("بک‌تست روی ۷۰٪ اول داده انجام می‌شود؛ فورواردتست روی ۳۰٪ آخر که مدل هرگز ندیده (خارج از نمونه). بازده‌ها مجموع بازدهِ روزِ بعدِ سیگنال‌هاست؛ «بازده بازار» یعنی همان روزها صرفاً خرید و نگهداری. وین‌ریت ۵روزه یعنی جهتِ درست تا ۵ روز بعد — افق ۵روزه در آزمون‌های مرجع تنها پارامتر یکنوا بود.")
        if split_date:
            st.caption("تاریخ شروع داده آزمون (فورواردتست): " + fa(split_date))
        html = ("<table class='ind'><tr><th>استراتژی</th><th>بازه</th>"
                "<th style='text-align:left'>سیگنال‌ها</th>"
                "<th style='text-align:left'>وین‌ریت</th>"
                "<th style='text-align:left'>وین‌ریت ۵روزه</th>"
                "<th style='text-align:left'>میانگین بازده/سیگنال</th>"
                "<th style='text-align:left'>بازده کل</th>"
                "<th style='text-align:left'>بازده بازار</th></tr>")
        for s_ in STRATEGIES:
            v = eval_["strats"].get(s_["id"], {})
            for tag, blk in [("بک‌تست", v.get("ins")), ("فوروارد", v.get("oos"))]:
                if blk is None:
                    continue
                n_s = fa(str(blk["n"]))
                h_s = fhit(blk)
                h5_s = fhit5(blk)
                a_s = fp(blk["avg_ret"]) if blk.get("avg_ret") is not None else "—"
                t_s = fp(blk["total_ret"])
                b_s = fp(blk["bench_ret"])
                html += (f"<tr><td>{s_['name']}</td><td>{tag}</td>"
                         f"<td class='v'>{n_s}</td><td class='v'>{h_s}</td>"
                         f"<td class='v'>{h5_s}</td>"
                         f"<td class='v'>{a_s}</td><td class='v'>{t_s}</td>"
                         f"<td class='v'>{b_s}</td></tr>")
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)
        st.info("فورواردتست معتبرترین سنجه است: عملکرد استراتژی روی داده‌ای که در ساختن یا تنظیم آن هیچ نقشی نداشته. اگر وین‌ریت فوروارد نزدیک بک‌تست باشد، استراتژی پایدار است. ردیف‌های با علامت ⚠️ نمونه زیر ۱۰ سیگنال دارند.")
    else:
        st.warning("داده تاریخی کافی برای بک‌تست و فورواردتست نیست.")

with t6:
    if feat is not None and len(feat) > 8:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=feat["date"], y=feat["gold18"], name="طلای ۱۸ عیار",
                                 line=dict(color="#e3b341", width=2.2)), secondary_y=False)
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