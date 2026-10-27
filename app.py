import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

# ====================== Page Config ======================
st.set_page_config(
    page_title="Gold18K Pro | تحلیلگر هوشمند طلای ۱۸ عیار",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== Custom CSS (Modern Dark + Gold) ======================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Vazirmatn', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(160deg, #0f0f13 0%, #1a1a24 50%, #12121a 100%);
    }
    
    .main-header {
        background: linear-gradient(90deg, #1a1a24, #2a2118, #1a1a24);
        padding: 1.5rem 1rem;
        border-radius: 16px;
        border: 1px solid #3d3428;
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(212, 175, 55, 0.08);
    }
    
    .main-title {
        font-size: 1.9rem;
        font-weight: 700;
        background: linear-gradient(90deg, #f0d78c, #d4af37, #f0d78c);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    
    .sub-title {
        color: #9ca3af;
        font-size: 0.95rem;
        margin-top: 0.4rem;
    }
    
    .metric-box {
        background: linear-gradient(145deg, #1e1e2a, #16161f);
        border: 1px solid #2d2d3a;
        border-radius: 14px;
        padding: 1.1rem 0.8rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .metric-box:hover {
        border-color: #d4af37;
        box-shadow: 0 0 20px rgba(212, 175, 55, 0.15);
    }
    
    .metric-label {
        color: #9ca3af;
        font-size: 0.85rem;
        margin-bottom: 0.3rem;
    }
    
    .metric-value {
        font-size: 1.45rem;
        font-weight: 700;
        color: #f3f4f6;
    }
    
    .metric-delta-up {
        color: #4ade80;
        font-size: 0.9rem;
    }
    
    .metric-delta-down {
        color: #f87171;
        font-size: 0.9rem;
    }
    
    .signal-card {
        border-radius: 14px;
        padding: 1.3rem;
        text-align: center;
        font-size: 1.35rem;
        font-weight: 700;
        margin: 0.8rem 0;
    }
    
    .signal-buy {
        background: linear-gradient(135deg, #064e3b, #065f46);
        color: #6ee7b7;
        border: 1px solid #10b981;
    }
    
    .signal-sell {
        background: linear-gradient(135deg, #7f1d1d, #991b1b);
        color: #fca5a5;
        border: 1px solid #ef4444;
    }
    
    .signal-neutral {
        background: linear-gradient(135deg, #1f2937, #374151);
        color: #d1d5db;
        border: 1px solid #6b7280;
    }
    
    .info-card {
        background: #1a1a24;
        border: 1px solid #2d2d3a;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #1e1e2a;
        border-radius: 10px;
        padding: 0.5rem 1.2rem;
        color: #9ca3af;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #2a2118 !important;
        color: #d4af37 !important;
        border: 1px solid #d4af37;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }
</style>
""", unsafe_allow_html=True)

# ====================== Data Sources ======================
LIVE_API = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/popular.json"
HISTORY_USD = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/USD_IRR_FREE.json"
HISTORY_GOLD18 = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/GOLD_18K_IRR.json"


@st.cache_data(ttl=45, show_spinner=False)
def get_live_data():
    try:
        r = requests.get(LIVE_API, timeout=12)
        r.raise_for_status()
        items = r.json().get("data", [])
        
        data = {
            "usd": None,
            "gold18": None,
            "ounce": None,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for item in items:
            sym = item.get("symbol", "")
            if sym == "USD_IRR_FREE":
                data["usd"] = {
                    "price": float(item.get("price", 0)),
                    "change": item.get("change_pct"),
                    "high": item.get("high"),
                    "low": item.get("low")
                }
                data["timestamp"] = item.get("timestamp_tehran") or data["timestamp"]
            elif sym == "GOLD_18K_IRR":
                data["gold18"] = {
                    "price": float(item.get("price", 0)),
                    "change": item.get("change_pct"),
                    "high": item.get("high"),
                    "low": item.get("low")
                }
        
        # Global Gold Ounce
        try:
            m = requests.get("https://api.metals.live/v1/spot/gold", timeout=7)
            if m.status_code == 200:
                mj = m.json()
                price = mj[0]["price"] if isinstance(mj, list) else mj.get("price")
                data["ounce"] = {"price": float(price)}
        except:
            data["ounce"] = {"price": None}
            
        return data
    except Exception as e:
        return None


@st.cache_data(ttl=180, show_spinner=False)
def get_history(days=60):
    try:
        usd_raw = requests.get(HISTORY_USD, timeout=15).json()
        gold_raw = requests.get(HISTORY_GOLD18, timeout=15).json()
        
        df_u = pd.DataFrame(usd_raw.get("data", []))
        df_g = pd.DataFrame(gold_raw.get("data", []))
        
        if df_u.empty or df_g.empty:
            return None
            
        for df in [df_u, df_g]:
            if "date_jalali" in df.columns:
                df["date"] = df["date_jalali"]
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
        
        merged = pd.merge(
            df_u[["date", "close"]].rename(columns={"close": "usd"}),
            df_g[["date", "close"]].rename(columns={"close": "gold18"}),
            on="date", how="inner"
        ).dropna().tail(days)
        
        merged["gold18"] = merged["gold18"].astype(float)
        merged["usd"] = merged["usd"].astype(float)
        return merged
    except:
        return None


def calc_theoretical(ounce, usd):
    if not ounce or not usd:
        return None
    return (ounce * usd / 31.1035) * 0.75


def calc_volatility(series, window=10):
    if series is None or len(series) < window:
        return None
    return series.pct_change().tail(window).std() * 100


def generate_smart_signal(premium, gold_chg, usd_chg, volatility):
    score = 0
    reasons = []
    
    if premium is not None:
        if premium <= -4.5:
            score += 2
            reasons.append(f"پریمیوم بسیار منفی ({premium:.1f}%) → ارزش خرید نسبی")
        elif premium <= -2.5:
            score += 1
            reasons.append(f"پریمیوم منفی ({premium:.1f}%)")
        elif premium >= 6:
            score -= 2
            reasons.append(f"پریمیوم بالا ({premium:.1f}%) → گران‌تر از ارزش جهانی")
        elif premium >= 3.5:
            score -= 1
            reasons.append(f"پریمیوم نسبتاً بالا ({premium:.1f}%)")
    
    if gold_chg is not None and usd_chg is not None:
        if gold_chg > 1.3 and usd_chg > 0.9:
            score += 1.5
            reasons.append("هم‌جهتی قوی صعودی طلا و دلار")
        elif gold_chg < -1.3 and usd_chg < -0.6:
            score -= 1.5
            reasons.append("هم‌جهتی نزولی")
    
    if volatility is not None and volatility > 2.8:
        reasons.append(f"نوسان بالا ({volatility:.1f}%) → احتیاط بیشتر")
        score *= 0.85
    
    if score >= 2:
        return "خرید قوی", reasons, "buy"
    elif score >= 0.8:
        return "خرید محتاطانه", reasons, "buy"
    elif score <= -2:
        return "فروش / کاهش موقعیت", reasons, "sell"
    elif score <= -0.8:
        return "فروش محتاطانه", reasons, "sell"
    else:
        return "خنثی / نظاره‌گر", reasons, "neutral"


def make_prediction(df):
    if df is None or len(df) < 12:
        return None
    
    last = df["gold18"].iloc[-1]
    rets = df["gold18"].pct_change().dropna()
    usd_rets = df["usd"].pct_change().dropna()
    
    short_mom = rets.tail(3).mean()
    med_mom = rets.tail(7).mean()
    corr = rets.corr(usd_rets)
    
    # Weighted momentum
    expected_daily = short_mom * 0.55 + med_mom * 0.25 + (usd_rets.tail(3).mean() * (corr if not np.isnan(corr) else 0.65)) * 0.20
    
    hour_pred = last * (1 + expected_daily * 0.18)
    
    days = []
    price = last
    for i in range(1, 4):
        # slight mean reversion
        price = price * (1 + expected_daily * (0.9 ** i))
        days.append(price)
    
    return {
        "current": last,
        "hour": hour_pred,
        "d1": days[0],
        "d2": days[1],
        "d3": days[2],
        "corr": corr if not np.isnan(corr) else 0,
        "momentum": expected_daily * 100
    }


# ====================== Sidebar ======================
with st.sidebar:
    st.markdown("### ⚙️ تنظیمات")
    auto_refresh = st.toggle("به‌روزرسانی خودکار (۴۵ ثانیه)", value=False)
    hist_days = st.slider("تعداد روز تاریخچه", 20, 90, 45)
    
    st.markdown("---")
    st.markdown("### 📌 آستانه‌های هشدار")
    premium_buy = st.number_input("پریمیوم خرید (منفی)", value=-3.5, step=0.5)
    premium_sell = st.number_input("پریمیوم فروش (مثبت)", value=4.5, step=0.5)
    
    st.markdown("---")
    if st.button("🔄 رفرش دستی", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.caption("نسخه Pro • فقط جنبه تحلیلی دارد")
    st.caption("توصیه سرمایه‌گذاری نیست")


# ====================== Header ======================
st.markdown("""
<div class="main-header">
    <h1 class="main-title">🥇 Gold18K Pro</h1>
    <p class="sub-title">تحلیلگر هوشمند طلای ۱۸ عیار ایران | لحظه‌ای • سیگنال • پیش‌بینی</p>
</div>
""", unsafe_allow_html=True)


# ====================== Load Data ======================
live = get_live_data()
history = get_history(hist_days)

if live is None:
    st.error("عدم دسترسی به داده‌های زنده. لطفاً چند لحظه دیگر تلاش کنید.")
    st.stop()

usd = live.get("usd")
gold = live.get("gold18")
ounce = live.get("ounce")


# ====================== Top Metrics ======================
c1, c2, c3, c4 = st.columns(4)

with c1:
    val = f"{usd['price']:,.0f}" if usd else "—"
    delta = usd.get("change") if usd else None
    delta_html = f'<div class="metric-delta-{"up" if delta and delta > 0 else "down"}">{delta:+.2f}%</div>' if delta is not None else ""
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-label">دلار آزاد</div>
        <div class="metric-value">{val}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

with c2:
    val = f"{gold['price']:,.0f}" if gold else "—"
    delta = gold.get("change") if gold else None
    delta_html = f'<div class="metric-delta-{"up" if delta and delta > 0 else "down"}">{delta:+.2f}%</div>' if delta is not None else ""
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-label">طلای ۱۸ عیار</div>
        <div class="metric-value">{val}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

with c3:
    val = f"{ounce['price']:,.1f} $" if ounce and ounce.get("price") else "—"
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-label">انس جهانی</div>
        <div class="metric-value">{val}</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    theo = calc_theoretical(ounce["price"] if ounce else None, usd["price"] if usd else None)
    prem = ((gold["price"] - theo) / theo * 100) if theo and gold else None
    prem_txt = f"{prem:+.2f}%" if prem is not None else "—"
    color = "#4ade80" if prem and prem < -2 else "#f87171" if prem and prem > 3 else "#d1d5db"
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-label">پریمیوم</div>
        <div class="metric-value" style="color:{color}">{prem_txt}</div>
    </div>
    """, unsafe_allow_html=True)

st.caption(f"آخرین بروزرسانی داده: {live.get('timestamp', '—')}")


# ====================== Tabs ======================
tab1, tab2, tab3, tab4 = st.tabs(["📊 داشبورد", "🧠 تحلیل هوشمند", "🔮 پیش‌بینی", "📈 تاریخچه"])

# ---------- Tab 1: Dashboard ----------
with tab1:
    col_left, col_right = st.columns([1.1, 1])
    
    with col_left:
        st.subheader("وضعیت لحظه‌ای")
        
        theo = calc_theoretical(ounce["price"] if ounce else None, usd["price"] if usd else None)
        prem = ((gold["price"] - theo) / theo * 100) if theo and gold else None
        vol = calc_volatility(history["gold18"]) if history is not None else None
        
        signal, reasons, sig_type = generate_smart_signal(
            prem,
            gold.get("change") if gold else None,
            usd.get("change") if usd else None,
            vol
        )
        
        css_class = f"signal-{sig_type}"
        st.markdown(f'<div class="signal-card {css_class}">سیگنال: {signal}</div>', unsafe_allow_html=True)
        
        if reasons:
            for r in reasons:
                st.markdown(f"• {r}")
        else:
            st.write("در حال حاضر سیگنال قوی مشاهده نمی‌شود.")
    
    with col_right:
        st.subheader("شاخص‌های کلیدی")
        
        if theo:
            st.markdown(f"""
            <div class="info-card">
                <b>قیمت تئوریک</b><br>
                <span style="font-size:1.3rem;color:#d4af37">{theo:,.0f} تومان</span>
            </div>
            """, unsafe_allow_html=True)
        
        if vol is not None:
            st.markdown(f"""
            <div class="info-card">
                <b>نوسان ۱۰ روزه</b><br>
                <span style="font-size:1.2rem">{vol:.2f}%</span>
            </div>
            """, unsafe_allow_html=True)
        
        if history is not None and len(history) > 5:
            chg5 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-6] - 1) * 100
            st.markdown(f"""
            <div class="info-card">
                <b>تغییر ۵ روزه طلا</b><br>
                <span style="font-size:1.2rem;color:{'#4ade80' if chg5>0 else '#f87171'}">{chg5:+.2f}%</span>
            </div>
            """, unsafe_allow_html=True)


# ---------- Tab 2: Smart Analysis ----------
with tab2:
    st.subheader("تحلیل عمیق بازار طلای ۱۸ عیار")
    
    if prem is not None:
        if prem < -3:
            st.success(f"**پریمیوم منفی ({prem:.2f}%)** — طلای داخلی نسبت به ارزش جهانی ارزان‌تر معامله می‌شود. این وضعیت معمولاً فرصت نسبی ایجاد می‌کند.")
        elif prem > 4:
            st.error(f"**پریمیوم مثبت بالا ({prem:.2f}%)** — طلای داخلی گران‌تر از ارزش جهانی است. احتمال اصلاح یا توقف صعود وجود دارد.")
        else:
            st.info(f"**پریمیوم در محدوده نرمال ({prem:.2f}%)**")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**عوامل حمایت‌کننده قیمت**")
        st.write("- افزایش دلار آزاد")
        st.write("- رشد انس جهانی")
        st.write("- تقاضای فیزیکی بالا")
        st.write("- انتظارات تورمی")
    
    with col2:
        st.markdown("**عوامل فشار بر قیمت**")
        st.write("- کاهش دلار")
        st.write("- اصلاح انس جهانی")
        st.write("- عرضه سنگین")
        st.write("- اخبار سیاسی مثبت")


# ---------- Tab 3: Prediction ----------
with tab3:
    st.subheader("پیش‌بینی کوتاه‌مدت")
    
    pred = make_prediction(history)
    
    if pred:
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("فعلی", f"{pred['current']:,.0f}")
        p2.metric("\~۱ ساعت", f"{pred['hour']:,.0f}")
        p3.metric("فردا", f"{pred['d1']:,.0f}")
        p4.metric("۳ روز بعد", f"{pred['d3']:,.0f}")
        
        st.caption(f"مومنتوم روزانه تقریبی: {pred['momentum']:+.2f}% | همبستگی با دلار: {pred['corr']:.3f}")
        st.warning("این پیش‌بینی بر اساس مدل آماری ساده (مومنتوم + همبستگی) است و اخبار سیاسی یا تصمیمات ارزی می‌تواند آن را کاملاً تغییر دهد.")
    else:
        st.info("داده کافی برای تولید پیش‌بینی وجود ندارد.")


# ---------- Tab 4: History Charts ----------
with tab4:
    if history is not None and len(history) > 5:
        st.subheader("روند قیمت طلای ۱۸ عیار و دلار")
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(
            go.Scatter(x=history["date"], y=history["gold18"], name="طلای ۱۸ عیار",
                       line=dict(color="#d4af37", width=2.5)),
            secondary_y=False
        )
        fig.add_trace(
            go.Scatter(x=history["date"], y=history["usd"], name="دلار آزاد",
                       line=dict(color="#60a5fa", width=2)),
            secondary_y=True
        )
        
        fig.update_layout(
            template="plotly_dark",
            height=420,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        fig.update_yaxes(title_text="طلا (تومان)", secondary_y=False, gridcolor="#2d2d3a")
        fig.update_yaxes(title_text="دلار (تومان)", secondary_y=True, gridcolor="#2d2d3a")
        fig.update_xaxes(gridcolor="#2d2d3a")
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Normalized chart
        st.subheader("مقایسه روند نرمال‌شده")
        norm = history.copy()
        norm["gold_n"] = norm["gold18"] / norm["gold18"].iloc[0] * 100
        norm["usd_n"] = norm["usd"] / norm["usd"].iloc[0] * 100
        
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=norm["date"], y=norm["gold_n"], name="طلا", line=dict(color="#d4af37", width=2.5)))
        fig2.add_trace(go.Scatter(x=norm["date"], y=norm["usd_n"], name="دلار", line=dict(color="#60a5fa", width=2)))
        fig2.update_layout(
            template="plotly_dark",
            height=360,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.08)
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("تاریخچه در دسترس نیست.")


# ====================== Auto Refresh ======================
if auto_refresh:
    time.sleep(45)
    st.rerun()
