import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

# ====================== تنظیمات صفحه ======================
st.set_page_config(
    page_title="Gold18K Pro | تحلیلگر هوشمند طلا",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ====================== استایل مینیمال + وزیرمتن ======================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');

html, body, [class*="css"], .stMarkdown, .stText, div {
    font-family: Vazirmatn, Tahoma, sans-serif !important;
}

.stApp {
    background-color: #0f1117;
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1100px;
}

/* کارت‌های مینیمال */
.card {
    background: #181b23;
    border: 1px solid #2a2e3a;
    border-radius: 12px;
    padding: 1.1rem 1rem;
    text-align: center;
}

.card-label {
    color: #9ca3af;
    font-size: 0.82rem;
    margin-bottom: 0.25rem;
}

.card-value {
    font-size: 1.35rem;
    font-weight: 700;
    color: #f3f4f6;
}

.positive { color: #34d399; }
.negative { color: #f87171; }

.signal-box {
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
    font-size: 1.25rem;
    font-weight: 700;
    margin: 0.6rem 0 1rem 0;
}

.signal-buy { background: #064e3b; color: #6ee7b7; border: 1px solid #059669; }
.signal-sell { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; }
.signal-neutral { background: #1f2937; color: #d1d5db; border: 1px solid #4b5563; }

.section-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #e5e7eb;
    margin: 1.4rem 0 0.7rem 0;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: transparent;
}

.stTabs [data-baseweb="tab"] {
    background: #181b23;
    border-radius: 8px;
    color: #9ca3af;
    padding: 0.45rem 1rem;
}

.stTabs [aria-selected="true"] {
    background: #1f2937 !important;
    color: #fbbf24 !important;
    border: 1px solid #fbbf24;
}

div[data-testid="stMetricValue"] {
    font-size: 1.3rem !important;
}
</style>
""", unsafe_allow_html=True)

# ====================== منابع داده ======================
LIVE_API = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/popular.json"
HISTORY_USD = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/USD_IRR_FREE.json"
HISTORY_GOLD18 = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/GOLD_18K_IRR.json"
GOLD_OUNCE_API = "https://api.gold-api.com/price/XAU"


@st.cache_data(ttl=40, show_spinner=False)
def get_live():
    result = {
        "usd": None, "gold18": None, "ounce": None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    try:
        r = requests.get(LIVE_API, timeout=10)
        items = r.json().get("data", [])
        for item in items:
            sym = item.get("symbol", "")
            if sym == "USD_IRR_FREE":
                result["usd"] = {
                    "price": float(item.get("price", 0)),
                    "change": item.get("change_pct")
                }
                result["timestamp"] = item.get("timestamp_tehran") or result["timestamp"]
            elif sym == "GOLD_18K_IRR":
                result["gold18"] = {
                    "price": float(item.get("price", 0)),
                    "change": item.get("change_pct")
                }
    except:
        pass

    # انس جهانی - منبع پایدار
    try:
        r = requests.get(GOLD_OUNCE_API, timeout=8)
        if r.status_code == 200:
            data = r.json()
            result["ounce"] = {"price": float(data.get("price", 0))}
    except:
        result["ounce"] = {"price": None}

    return result


@st.cache_data(ttl=180, show_spinner=False)
def get_history(days=50):
    try:
        u = requests.get(HISTORY_USD, timeout=12).json()
        g = requests.get(HISTORY_GOLD18, timeout=12).json()
        df_u = pd.DataFrame(u.get("data", []))
        df_g = pd.DataFrame(g.get("data", []))
        if df_u.empty or df_g.empty:
            return None
        for df in [df_u, df_g]:
            if "date_jalali" in df.columns:
                df["date"] = df["date_jalali"]
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = pd.merge(
            df_u[["date", "close"]].rename(columns={"close": "usd"}),
            df_g[["date", "close"]].rename(columns={"close": "gold18"}),
            on="date", how="inner"
        ).dropna().tail(days)
        return df
    except:
        return None


def theoretical(ounce, usd):
    if not ounce or not usd:
        return None
    return (ounce * usd / 31.1035) * 0.75


def calc_strategies(premium, gold_chg, usd_chg, vol, history):
    """چند استراتژی ساده و کاربردی"""
    scores = []
    reasons = []

    # استراتژی ۱: Mean Reversion پریمیوم
    if premium is not None:
        if premium <= -3.8:
            scores.append(1.8)
            reasons.append("استراتژی پریمیوم: طلای داخلی ارزان‌تر از ارزش جهانی است")
        elif premium >= 5.0:
            scores.append(-1.8)
            reasons.append("استراتژی پریمیوم: طلای داخلی گران‌تر از ارزش جهانی است")

    # استراتژی ۲: Momentum + همبستگی دلار
    if gold_chg is not None and usd_chg is not None:
        if gold_chg > 1.1 and usd_chg > 0.7:
            scores.append(1.4)
            reasons.append("استراتژی مومنتوم: هم‌جهتی صعودی طلا و دلار")
        elif gold_chg < -1.1 and usd_chg < -0.5:
            scores.append(-1.4)
            reasons.append("استراتژی مومنتوم: هم‌جهتی نزولی")

    # استراتژی ۳: فیلتر نوسان
    if vol is not None and vol > 2.6:
        scores = [s * 0.7 for s in scores]
        reasons.append(f"فیلتر نوسان: نوسان بالا ({vol:.1f}%) → کاهش وزن سیگنال")

    total = sum(scores) if scores else 0

    if total >= 2.2:
        return "خرید قوی", reasons, "buy"
    elif total >= 0.9:
        return "خرید محتاطانه", reasons, "buy"
    elif total <= -2.2:
        return "فروش / کاهش", reasons, "sell"
    elif total <= -0.9:
        return "فروش محتاطانه", reasons, "sell"
    else:
        return "خنثی / نظاره‌گر", reasons, "neutral"


def make_prediction(df):
    if df is None or len(df) < 12:
        return None
    last = df["gold18"].iloc[-1]
    rets = df["gold18"].pct_change().dropna()
    usd_rets = df["usd"].pct_change().dropna()
    short = rets.tail(3).mean()
    med = rets.tail(7).mean()
    corr = rets.corr(usd_rets)
    expected = short * 0.5 + med * 0.3 + (usd_rets.tail(3).mean() * (corr if not np.isnan(corr) else 0.6)) * 0.2
    hour = last * (1 + expected * 0.15)
    days = []
    p = last
    for i in range(3):
        p = p * (1 + expected * (0.88 ** (i+1)))
        days.append(p)
    return {
        "current": last, "hour": hour,
        "d1": days[0], "d2": days[1], "d3": days[2],
        "corr": corr if not np.isnan(corr) else 0
    }


# ====================== بارگذاری داده ======================
live = get_live()
history = get_history(50)

if not live or not live.get("gold18"):
    st.error("خطا در دریافت داده. چند لحظه دیگر تلاش کنید.")
    st.stop()

usd = live["usd"]
gold = live["gold18"]
ounce = live["ounce"]

theo = theoretical(ounce["price"] if ounce else None, usd["price"] if usd else None)
prem = ((gold["price"] - theo) / theo * 100) if theo and gold else None
vol = None
if history is not None and len(history) > 12:
    vol = history["gold18"].pct_change().tail(10).std() * 100

# ====================== هدر ======================
st.markdown("""
<div style="text-align:center; margin-bottom:1.2rem;">
    <div style="font-size:1.7rem; font-weight:700; color:#fbbf24;">🥇 Gold18K Pro</div>
    <div style="color:#9ca3af; font-size:0.9rem;">تحلیلگر هوشمند طلای ۱۸ عیار ایران</div>
</div>
""", unsafe_allow_html=True)

# ====================== کارت‌های قیمت ======================
c1, c2, c3, c4 = st.columns(4)

def render_card(label, value, change=None):
    delta = ""
    if change is not None:
        cls = "positive" if change >= 0 else "negative"
        delta = f'<div class="{cls}" style="font-size:0.85rem;">{change:+.2f}%</div>'
    st.markdown(f"""
    <div class="card">
        <div class="card-label">{label}</div>
        <div class="card-value">{value}</div>
        {delta}
    </div>
    """, unsafe_allow_html=True)

with c1:
    render_card("دلار آزاد", f"{usd['price']:,.0f}" if usd else "—", usd.get("change") if usd else None)
with c2:
    render_card("طلای ۱۸ عیار", f"{gold['price']:,.0f}" if gold else "—", gold.get("change") if gold else None)
with c3:
    render_card("انس جهانی", f"{ounce['price']:,.1f} $" if ounce and ounce.get("price") else "—")
with c4:
    prem_txt = f"{prem:+.2f}%" if prem is not None else "—"
    render_card("پریمیوم", prem_txt)

st.caption(f"آخرین بروزرسانی: {live.get('timestamp', '—')}")

# ====================== تب‌ها ======================
tab1, tab2, tab3, tab4 = st.tabs(["داشبورد", "استراتژی‌ها", "پیش‌بینی", "اخبار و تأثیر"])

# ---------- داشبورد ----------
with tab1:
    signal, reasons, sig_type = calc_strategies(
        prem,
        gold.get("change") if gold else None,
        usd.get("change") if usd else None,
        vol,
        history
    )

    st.markdown(f'<div class="signal-box signal-{sig_type}">سیگنال: {signal}</div>', unsafe_allow_html=True)

    if reasons:
        for r in reasons:
            st.markdown(f"• {r}")
    else:
        st.write("در حال حاضر سیگنال قوی بر اساس استراتژی‌ها وجود ندارد.")

    st.markdown('<div class="section-title">شاخص‌های کلیدی</div>', unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("قیمت تئوریک", f"{theo:,.0f}" if theo else "—")
    with k2:
        st.metric("نوسان ۱۰ روزه", f"{vol:.2f}%" if vol else "—")
    with k3:
        if history is not None and len(history) > 5:
            chg5 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-6] - 1) * 100
            st.metric("تغییر ۵ روزه", f"{chg5:+.2f}%")

# ---------- استراتژی‌ها ----------
with tab2:
    st.markdown('<div class="section-title">استراتژی‌های فعال</div>', unsafe_allow_html=True)
    
    st.markdown("""
    **۱. استراتژی پریمیوم (Mean Reversion)**  
    وقتی طلای داخلی خیلی ارزان‌تر یا گران‌تر از ارزش جهانی معامله شود، احتمال بازگشت به میانگین وجود دارد.

    **۲. استراتژی مومنتوم + دلار**  
    وقتی طلا و دلار همزمان در یک جهت حرکت قوی داشته باشند، احتمال ادامه روند بیشتر است.

    **۳. فیلتر نوسان**  
    در روزهای پرنوسان وزن سیگنال‌ها کاهش می‌یابد تا از ورود در شرایط پرریسک جلوگیری شود.
    """)

    st.info("این استراتژی‌ها صرفاً ابزاری کمکی هستند و تضمینی برای سود ندارند.")

# ---------- پیش‌بینی ----------
with tab3:
    pred = make_prediction(history)
    if pred:
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("فعلی", f"{pred['current']:,.0f}")
        p2.metric("\~۱ ساعت", f"{pred['hour']:,.0f}")
        p3.metric("فردا", f"{pred['d1']:,.0f}")
        p4.metric("۳ روز بعد", f"{pred['d3']:,.0f}")
        st.caption(f"همبستگی با دلار: {pred['corr']:.3f}")
        st.warning("پیش‌بینی آماری ساده است و اخبار سیاسی می‌تواند آن را کاملاً تغییر دهد.")
    else:
        st.info("داده کافی برای پیش‌بینی وجود ندارد.")

# ---------- اخبار و تأثیر ----------
with tab4:
    st.markdown('<div class="section-title">اخبار مهم و تأثیر احتمالی</div>', unsafe_allow_html=True)
    
    st.markdown("""
    | نوع خبر | تأثیر محتمل روی طلای ۱۸ عیار |
    |---------|-------------------------------|
    | افزایش تنش سیاسی / تحریم جدید | افزایش قیمت (حمایت از طلا و دلار) |
    | خبر توافق یا کاهش تنش | فشار نزولی کوتاه‌مدت |
    | تصمیم فدرال رزرو (افزایش نرخ بهره) | فشار روی انس جهانی → تأثیر منفی |
    | افزایش شدید دلار آزاد | صعود قوی طلای داخلی |
    | کاهش دلار آزاد | اصلاح قیمت طلا |
    | تقاضای فیزیکی بالا (مناسبت‌ها) | حمایت از قیمت |
    """)

    st.markdown("---")
    st.markdown("**نکته تحلیلی امروز:**")
    if prem is not None:
        if prem < -3:
            st.success("پریمیوم منفی فعلی می‌تواند در صورت نبود خبر منفی، از قیمت حمایت کند.")
        elif prem > 4:
            st.error("پریمیوم بالا نشان‌دهنده گران بودن نسبی طلای داخلی است.")
        else:
            st.info("پریمیوم در محدوده معمولی قرار دارد.")

# ====================== نمودار ----------
if history is not None and len(history) > 8:
    st.markdown('<div class="section-title">روند قیمت</div>', unsafe_allow_html=True)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=history["date"], y=history["gold18"], name="طلای ۱۸ عیار",
                             line=dict(color="#fbbf24", width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=history["date"], y=history["usd"], name="دلار",
                             line=dict(color="#60a5fa", width=1.8)), secondary_y=True)
    fig.update_layout(
        template="plotly_dark", height=340,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.08)
    )
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

st.caption("این ابزار صرفاً جنبه تحلیلی دارد و توصیه سرمایه‌گذاری نیست.")