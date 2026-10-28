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

# ====================== استایل (خوانا و بدون محو شدن) ======================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');

html, body, [class*="css"], .stMarkdown, div, p, span, label {
    font-family: Vazirmatn, Tahoma, sans-serif !important;
}
.stApp { background-color: #0b0d12 !important; }
.block-container { padding-top: 1rem; max-width: 1080px; }

.card {
    background: #1a1d27 !important;
    border: 1px solid #3a3f50 !important;
    border-radius: 12px;
    padding: 1rem 0.75rem;
    text-align: center;
}
.card-label {
    color: #a8b0c4 !important;
    font-size: 0.85rem !important;
    margin-bottom: 0.35rem;
    font-weight: 500;
}
.card-value {
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: #ffffff !important;
}
.pos { color: #34d399 !important; }
.neg { color: #f87171 !important; }

[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-size: 1.25rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: #b0b8cc !important;
    font-size: 0.9rem !important;
}
[data-testid="stMetricDelta"] { font-weight: 600 !important; }

.stCaption, [data-testid="stCaptionContainer"] {
    color: #c5cdd9 !important;
    font-size: 0.9rem !important;
}

div.stButton > button {
    background: linear-gradient(90deg, #c2410c, #ea580c) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.7rem 1rem !important;
    opacity: 1 !important;
}
div.stButton > button:hover {
    background: linear-gradient(90deg, #ea580c, #f97316) !important;
    color: #ffffff !important;
}

.stTabs [data-baseweb="tab"] {
    background: #1a1d27 !important;
    border-radius: 8px;
    color: #c5cdd9 !important;
    padding: 0.45rem 0.95rem;
    font-weight: 500 !important;
    opacity: 1 !important;
}
.stTabs [aria-selected="true"] {
    background: #252a38 !important;
    color: #fbbf24 !important;
    border: 1px solid #fbbf24 !important;
    opacity: 1 !important;
}

.signal-box {
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
    font-size: 1.2rem;
    font-weight: 700;
    margin: 0.5rem 0 1rem 0;
    opacity: 1 !important;
}
.buy { background: #064e3b; color: #6ee7b7; border: 1px solid #059669; }
.sell { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; }
.neutral { background: #1e293b; color: #e2e8f0; border: 1px solid #64748b; }

.section {
    font-size: 1.1rem;
    font-weight: 600;
    color: #f1f5f9 !important;
    margin: 1.3rem 0 0.6rem 0;
}
.stAlert { opacity: 1 !important; }
</style>
""", unsafe_allow_html=True)

# ====================== منابع ======================
LIVE_API = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/popular.json"
HISTORY_USD = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/USD_IRR_FREE.json"
HISTORY_GOLD18 = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/GOLD_18K_IRR.json"
METAL_API = "https://api.gold-api.com/price/{}"


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


@st.cache_data(ttl=40, show_spinner=False)
def fetch_live():
    out = {
        "usd": None, "gold18": None,
        "ounce": None, "silver": None, "copper": None,
        "ts": datetime.now().strftime("%H:%M")
    }
    try:
        items = requests.get(LIVE_API, timeout=9).json().get("data", [])
        for it in items:
            s = it.get("symbol", "")
            if s == "USD_IRR_FREE":
                out["usd"] = {"price": float(it.get("price", 0)), "chg": it.get("change_pct")}
            elif s == "GOLD_18K_IRR":
                out["gold18"] = {"price": float(it.get("price", 0)), "chg": it.get("change_pct")}
    except:
        pass

    for key, sym in [("ounce", "XAU"), ("silver", "XAG"), ("copper", "HG")]:
        try:
            r = requests.get(METAL_API.format(sym), timeout=7)
            if r.status_code == 200:
                out[key] = {"price": float(r.json().get("price", 0))}
        except:
            pass
    return out


@st.cache_data(ttl=160, show_spinner=False)
def fetch_history(days=55):
    try:
        u = pd.DataFrame(requests.get(HISTORY_USD, timeout=11).json().get("data", []))
        g = pd.DataFrame(requests.get(HISTORY_GOLD18, timeout=11).json().get("data", []))
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
        ).dropna().tail(days)
        return df
    except:
        return None


def theoretical(ounce, usd):
    if not ounce or not usd:
        return None
    return (ounce * usd / 31.1035) * 0.75


def intelligence_engine(live, history):
    gold = live.get("gold18") or {}
    usd = live.get("usd") or {}
    ounce = live.get("ounce") or {}

    g_price = gold.get("price")
    u_price = usd.get("price")
    o_price = ounce.get("price")
    g_chg = gold.get("chg")
    u_chg = usd.get("chg")

    theo = theoretical(o_price, u_price)
    prem = ((g_price - theo) / theo * 100) if theo and g_price else None
    z_prem = (prem / 2.8) if prem is not None else None

    vol = corr = mom3 = mom5 = mom10 = None
    if history is not None and len(history) > 15:
        rets_g = history["gold18"].pct_change().dropna()
        rets_u = history["usd"].pct_change().dropna()
        vol = rets_g.tail(10).std() * 100
        corr = rets_g.corr(rets_u)
        mom3 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-4] - 1) * 100
        mom5 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-6] - 1) * 100
        mom10 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-11] - 1) * 100

    score = 0.0
    factors = []

    if z_prem is not None:
        if z_prem <= -1.8:
            score += 2.4
            factors.append(("Z-Score پریمیوم خیلی منفی", +2.4, f"Z={z_prem:.2f} → فرصت خرید نسبی قوی"))
        elif z_prem <= -1.0:
            score += 1.3
            factors.append(("Z-Score پریمیوم منفی", +1.3, f"Z={z_prem:.2f} → ارزش نسبی خوب"))
        elif z_prem >= 1.8:
            score -= 2.4
            factors.append(("Z-Score پریمیوم خیلی مثبت", -2.4, f"Z={z_prem:.2f} → گران‌تر از ارزش"))
        elif z_prem >= 1.0:
            score -= 1.2
            factors.append(("Z-Score پریمیوم مثبت", -1.2, f"Z={z_prem:.2f} → احتیاط"))

    if mom3 is not None and mom5 is not None:
        if mom3 > 1.5 and mom5 > 2.0:
            score += 1.5
            factors.append(("مومنتوم قوی کوتاه‌مدت", +1.5, "روند صعودی تأیید شده"))
        elif mom3 < -1.5 and mom5 < -2.0:
            score -= 1.5
            factors.append(("مومنتوم قوی نزولی", -1.5, "فشار فروش تأیید شده"))

    if corr is not None and u_chg is not None and g_chg is not None:
        if corr > 0.70:
            if u_chg > 0.7 and g_chg > 0.5:
                score += 1.1
                factors.append(("همبستگی بالا + دلار صعودی", +1.1, "حمایت قوی از روند"))
            elif u_chg < -0.7 and g_chg < -0.5:
                score -= 1.1
                factors.append(("همبستگی بالا + دلار نزولی", -1.1, "فشار قوی"))

    vol_penalty = 1.0
    if vol is not None:
        if vol > 3.0:
            vol_penalty = 0.65
            factors.append(("نوسان بسیار بالا", 0, f"نوسان {vol:.1f}% → کاهش وزن سیگنال"))
        elif vol > 2.3:
            vol_penalty = 0.80
            factors.append(("نوسان بالا", 0, f"نوسان {vol:.1f}% → احتیاط"))
    score *= vol_penalty

    if score >= 2.6:
        regime, signal, conf = "صعودی قوی", "خرید قوی", min(93, 70 + score * 7)
    elif score >= 1.1:
        regime, signal, conf = "صعودی ملایم", "خرید محتاطانه", min(80, 58 + score * 8)
    elif score <= -2.6:
        regime, signal, conf = "نزولی قوی", "فروش / کاهش", min(93, 70 + abs(score) * 7)
    elif score <= -1.1:
        regime, signal, conf = "نزولی ملایم", "فروش محتاطانه", min(80, 58 + abs(score) * 8)
    else:
        regime, signal, conf = "رنج / نامشخص", "خنثی / نظاره‌گر", 48 + abs(score) * 6

    p_up = max(15, min(85, 50 + score * 12))
    p_down = 100 - p_up

    pred = None
    if history is not None and len(history) > 14 and g_price:
        rets = history["gold18"].pct_change().dropna()
        short = rets.tail(3).mean()
        med = rets.tail(8).mean()
        usd_s = history["usd"].pct_change().tail(3).mean()
        if abs(score) >= 2.0:
            w_short, w_med, w_usd, w_prem = 0.42, 0.22, 0.28, 0.08
        elif abs(score) >= 1.0:
            w_short, w_med, w_usd, w_prem = 0.35, 0.25, 0.30, 0.10
        else:
            w_short, w_med, w_usd, w_prem = 0.25, 0.25, 0.25, 0.25
        corr_safe = corr if corr is not None and not np.isnan(corr) else 0.55
        expected = (w_short * short + w_med * med + w_usd * (usd_s * corr_safe) +
                    w_prem * (-0.15 * (z_prem if z_prem else 0) / 100))
        daily_vol = rets.tail(10).std()
        if daily_vol is None or np.isnan(daily_vol):
            daily_vol = 0.012
        d1_p = g_price * (1 + expected * 0.90)
        d3_p = g_price * (1 + expected * 2.15)
        pred = {
            "d1": d1_p,
            "d1_low": d1_p * (1 - daily_vol * 1.05),
            "d1_high": d1_p * (1 + daily_vol * 1.05),
            "d3": d3_p,
            "d3_low": d3_p * (1 - daily_vol * 1.7),
            "d3_high": d3_p * (1 + daily_vol * 1.7),
            "expected_daily": expected * 100,
        }

    return {
        "theo": theo, "prem": prem, "z_prem": z_prem,
        "vol": vol, "corr": corr, "mom3": mom3, "mom5": mom5, "mom10": mom10,
        "score": score, "factors": factors,
        "regime": regime, "signal": signal, "confidence": conf,
        "p_up": p_up, "p_down": p_down, "pred": pred
    }


def run_daily_checklist(live, intel):
    checks, total_score, max_score = [], 0, 0

    max_score += 2
    if intel.get("z_prem") is not None:
        z = intel["z_prem"]
        if z <= -1.5:
            checks.append(("ارزش‌گذاری", "✅ عالی", f"Z={z:.2f}", 2)); total_score += 2
        elif z <= -0.7:
            checks.append(("ارزش‌گذاری", "✅ خوب", f"Z={z:.2f}", 1)); total_score += 1
        elif z >= 1.5:
            checks.append(("ارزش‌گذاری", "❌ ضعیف", f"Z={z:.2f}", 0))
        else:
            checks.append(("ارزش‌گذاری", "⚪ خنثی", f"Z={z:.2f}", 1)); total_score += 1
    else:
        checks.append(("ارزش‌گذاری", "⚪ نامشخص", "—", 0))

    max_score += 2
    mom5 = intel.get("mom5")
    if mom5 is not None:
        if mom5 > 2.5:
            checks.append(("مومنتوم", "✅ قوی صعودی", f"{mom5:+.1f}%", 2)); total_score += 2
        elif mom5 > 0.8:
            checks.append(("مومنتوم", "✅ ملایم صعودی", f"{mom5:+.1f}%", 1)); total_score += 1
        elif mom5 < -2.5:
            checks.append(("مومنتوم", "❌ قوی نزولی", f"{mom5:+.1f}%", 0))
        elif mom5 < -0.8:
            checks.append(("مومنتوم", "❌ ملایم نزولی", f"{mom5:+.1f}%", 0))
        else:
            checks.append(("مومنتوم", "⚪ خنثی", f"{mom5:+.1f}%", 1)); total_score += 1
    else:
        checks.append(("مومنتوم", "⚪ نامشخص", "—", 0))

    max_score += 2
    corr = intel.get("corr")
    if corr is not None:
        if corr > 0.75:
            checks.append(("همبستگی", "✅ بالا", f"{corr:.2f}", 2)); total_score += 2
        elif corr > 0.50:
            checks.append(("همبستگی", "✅ متوسط", f"{corr:.2f}", 1)); total_score += 1
        else:
            checks.append(("همبستگی", "⚠️ پایین", f"{corr:.2f}", 0))
    else:
        checks.append(("همبستگی", "⚪ نامشخص", "—", 0))

    max_score += 2
    vol = intel.get("vol")
    if vol is not None:
        if vol < 1.8:
            checks.append(("نوسان", "✅ آرام", f"{vol:.1f}%", 2)); total_score += 2
        elif vol < 2.6:
            checks.append(("نوسان", "✅ قابل قبول", f"{vol:.1f}%", 1)); total_score += 1
        else:
            checks.append(("نوسان", "⚠️ بالا", f"{vol:.1f}%", 0))
    else:
        checks.append(("نوسان", "⚪ نامشخص", "—", 0))

    max_score += 2
    conf = intel.get("confidence", 0)
    if conf >= 75:
        checks.append(("قدرت سیگنال", "✅ قوی", f"{conf:.0f}%", 2)); total_score += 2
    elif conf >= 55:
        checks.append(("قدرت سیگنال", "✅ متوسط", f"{conf:.0f}%", 1)); total_score += 1
    else:
        checks.append(("قدرت سیگنال", "⚪ ضعیف", f"{conf:.0f}%", 0))

    pct = (total_score / max_score * 100) if max_score else 0
    if pct >= 75:
        overall, color = "شرایط کلی مساعد", "success"
    elif pct >= 50:
        overall, color = "شرایط متوسط / مختلط", "info"
    else:
        overall, color = "شرایط نامساعد یا پرریسک", "warning"

    return {
        "checks": checks, "total_score": total_score, "max_score": max_score,
        "pct": pct, "overall": overall, "color": color
    }


def build_market_report(live, intel):
    j_date, j_time = to_jalali()
    usd = live.get("usd") or {}
    gold = live.get("gold18") or {}
    ounce = live.get("ounce") or {}
    silver = live.get("silver") or {}
    copper = live.get("copper") or {}

    usd_p = usd.get("price") or 0
    g18 = gold.get("price") or 0
    xau = ounce.get("price")
    xag = silver.get("price")
    hg = copper.get("price")

    silver_toman_g = (xag * usd_p / 31.1035) if (xag and usd_p) else None
    copper_toman_kg = (hg * usd_p / 0.453592) if (hg and usd_p) else None

    p_up = intel.get("p_up", 50)
    p_down = intel.get("p_down", 50)

    factors_txt = ""
    if intel.get("factors"):
        for name, sc, desc in intel["factors"][:4]:
            arrow = "▲" if sc > 0 else ("▼" if sc < 0 else "•")
            factors_txt += f"\n{arrow} {name}: {desc}"
    else:
        factors_txt = "\n• عامل قوی خاصی در داده‌های فعلی دیده نشد."

    note = "بازار در تعادل نسبی است؛ بهتر است تا تثبیت جهت صبر شود."
    if intel.get("z_prem") is not None:
        if intel["z_prem"] <= -1.5:
            note = "پریمیوم منفی قابل توجه: فاصله قیمت داخلی از ارزش جهانی فرصت نسبی ایجاد کرده است."
        elif intel["z_prem"] >= 1.5:
            note = "پریمیوم بالا: طلای داخلی نسبت به انس گران‌تر است؛ حساسیت به اصلاح بیشتر است."
    if intel.get("vol") and intel["vol"] > 2.6:
        note = "نوسان بالاست؛ مدیریت حجم و حد ضرر اهمیت بیشتری دارد."

    lines = [
        "📊 گزارش وضعیت بازار فلزات",
        f"📅 {j_date}  |  🕐 {j_time}",
        "",
        "━━━━━━━━━━━━━━",
        "قیمت‌های لحظه‌ای (تقریبی به تومان)",
        f"🥇 طلای ۱۸ عیار: {g18:,.0f}" if g18 else "🥇 طلای ۱۸ عیار: —",
        f"💵 دلار آزاد: {usd_p:,.0f}" if usd_p else "💵 دلار آزاد: —",
        f"🌍 انس طلا: {xau:,.1f} $" if xau else "🌍 انس طلا: —",
        f"🥈 نقره (هر گرم): {silver_toman_g:,.0f}" if silver_toman_g else "🥈 نقره: —",
        f"🟤 مس (هر کیلو): {copper_toman_kg:,.0f}" if copper_toman_kg else "🟤 مس: —",
        "",
        "━━━━━━━━━━━━━━",
        f"رژیم بازار: {intel.get('regime', '—')}",
        f"احتمال رشد قیمت: {p_up:.0f}٪",
        f"احتمال نزول قیمت: {p_down:.0f}٪",
        "",
        "عوامل دخیل:",
        factors_txt.strip(),
        "",
        "━━━━━━━━━━━━━━",
        f"💡 نکته فرصت: {note}",
        "",
        "#بازار_طلا #گزارش"
    ]
    return "\n".join(lines)


def send_bale_message(text):
    try:
        bot_token = st.secrets["BALE_BOT_TOKEN"]
        chat_id = st.secrets["BALE_CHAT_ID"]
    except Exception:
        st.error("Secrets تنظیم نشده: BALE_BOT_TOKEN و BALE_CHAT_ID")
        return False

    url = f"https://tapi.bale.ai/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
        if r.status_code == 200:
            return True
        st.error(f"پاسخ بله: {r.status_code} — {r.text[:200]}")
        return False
    except requests.exceptions.ConnectTimeout:
        st.error(
            "اتصال به سرور بله قطع است (Timeout).\n"
            "سرور فعلی (مثل Streamlit Cloud) معمولاً به tapi.bale.ai دسترسی ندارد.\n"
            "راه‌حل: هاست/VPS ایرانی، یا کپی دستی گزارش از بخش پایین."
        )
        return False
    except Exception as e:
        st.error(f"خطا: {e}")
        return False


# ====================== اجرا ======================
live = fetch_live()
history = fetch_history()

if not live.get("gold18"):
    st.error("داده زنده در دسترس نیست. چند لحظه دیگر تلاش کنید.")
    st.stop()

intel = intelligence_engine(live, history)
checklist = run_daily_checklist(live, intel)
report_text = build_market_report(live, intel)

# ====================== UI ======================
st.markdown("""
<div style="text-align:center;margin-bottom:1rem;">
    <div style="font-size:1.55rem;font-weight:700;color:#fbbf24;">🥇 Gold18K Intelligence</div>
    <div style="color:#c5cdd9;font-size:0.9rem;">موتور تحلیل + گزارش وضعیت بازار</div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

def card(label, value, chg=None):
    delta = ""
    if chg is not None:
        cls = "pos" if chg >= 0 else "neg"
        delta = f'<div class="{cls}" style="font-size:0.8rem;">{chg:+.2f}%</div>'
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

s1, s2, s3 = st.columns(3)
usd_p = live.get("usd", {}).get("price") or 0
if live.get("silver") and live["silver"].get("price") and usd_p:
    s1.metric("نقره (تومان/گرم)", f"{(live['silver']['price'] * usd_p / 31.1035):,.0f}")
else:
    s1.metric("نقره (تومان/گرم)", "—")
if live.get("copper") and live["copper"].get("price") and usd_p:
    s2.metric("مس (تومان/کیلو)", f"{(live['copper']['price'] * usd_p / 0.453592):,.0f}")
else:
    s2.metric("مس (تومان/کیلو)", "—")
s3.metric("احتمال رشد / نزول", f"{intel.get('p_up', 50):.0f}% / {intel.get('p_down', 50):.0f}%")

st.caption(f"آخرین بروزرسانی: {live.get('ts')} | رژیم: **{intel['regime']}**")

# ---------- دکمه‌های ارسال / دانلود ----------
st.markdown("---")
b1, b2 = st.columns(2)

with b1:
    if st.button("📤 ارسال گزارش به بله", use_container_width=True, type="primary"):
        if send_bale_message(report_text):
            st.success("✅ گزارش با موفقیت به کانال بله ارسال شد.")

with b2:
    st.download_button(
        label="💾 دانلود گزارش متنی",
        data=report_text,
        file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        use_container_width=True
    )

with st.expander("📋 مشاهده و کپی متن گزارش (برای ارسال دستی در بله)"):
    st.code(report_text, language=None)

# ---------- تب‌ها ----------
t1, t2, t3, t4 = st.tabs(["هوش مصنوعی", "پیش‌بینی", "چک‌لیست روزانه", "جزئیات"])

with t1:
    sig_class = "buy" if "خرید" in intel["signal"] else "sell" if "فروش" in intel["signal"] else "neutral"
    st.markdown(
        f'<div class="signal-box {sig_class}">{intel["signal"]}  •  اطمینان {intel["confidence"]:.0f}٪</div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="section">عوامل مؤثر</div>', unsafe_allow_html=True)
    if intel["factors"]:
        for name, sc, desc in intel["factors"]:
            color = "#34d399" if sc > 0 else "#f87171" if sc < 0 else "#94a3b8"
            st.markdown(f"- **{name}** <span style='color:{color}'>({sc:+.1f})</span> → {desc}", unsafe_allow_html=True)
    else:
        st.write("عامل قوی خاصی شناسایی نشد.")
    st.info(f"رژیم: **{intel['regime']}** | احتمال رشد ≈ {intel.get('p_up', 50):.0f}% | احتمال نزول ≈ {intel.get('p_down', 50):.0f}%")

with t2:
    if intel.get("pred"):
        p = intel["pred"]
        a, b, c = st.columns(3)
        a.metric("فعلی", f"{live['gold18']['price']:,.0f}")
        b.metric("فردا (نقطه‌ای)", f"{p['d1']:,.0f}")
        c.metric("۳ روز بعد", f"{p['d3']:,.0f}")
        st.caption(f"محدوده فردا: {p['d1_low']:,.0f} تا {p['d1_high']:,.0f}")
        st.caption(f"محدوده ۳روزه: {p['d3_low']:,.0f} تا {p['d3_high']:,.0f}")
    else:
        st.warning("داده کافی برای پیش‌بینی نیست.")

with t3:
    if checklist["color"] == "success":
        st.success(f"**{checklist['overall']}** | {checklist['total_score']}/{checklist['max_score']} ({checklist['pct']:.0f}%)")
    elif checklist["color"] == "warning":
        st.warning(f"**{checklist['overall']}** | {checklist['total_score']}/{checklist['max_score']} ({checklist['pct']:.0f}%)")
    else:
        st.info(f"**{checklist['overall']}** | {checklist['total_score']}/{checklist['max_score']} ({checklist['pct']:.0f}%)")
    for name, status, detail, sc in checklist["checks"]:
        st.markdown(f"**{name}**: {status} — {detail}")

with t4:
    c1, c2, c3 = st.columns(3)
    c1.metric("تئوریک", f"{intel['theo']:,.0f}" if intel["theo"] else "—")
    c2.metric("نوسان ۱۰روزه", f"{intel['vol']:.2f}%" if intel["vol"] else "—")
    c3.metric("همبستگی", f"{intel['corr']:.2f}" if intel["corr"] is not None else "—")
    if intel.get("z_prem") is not None:
        st.metric("Z-Score پریمیوم", f"{intel['z_prem']:.2f}")

if history is not None and len(history) > 8:
    st.markdown('<div class="section">روند قیمت</div>', unsafe_allow_html=True)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=history["date"], y=history["gold18"], name="طلای ۱۸ عیار",
                             line=dict(color="#fbbf24", width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=history["date"], y=history["usd"], name="دلار",
                             line=dict(color="#60a5fa", width=1.6)), secondary_y=True)
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=10, r=10, t=15, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.08)
    )
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

st.caption("گزارش بله فقط با دکمه دستی یا کپی متن ارسال می‌شود و توصیه سرمایه‌گذاری نیست.")