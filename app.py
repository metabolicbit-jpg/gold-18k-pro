import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

st.set_page_config(
    page_title="Gold18K Intelligence",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ====================== استایل مینیمال + وزیرمتن ======================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');

html, body, [class*="css"], .stMarkdown, div {
    font-family: Vazirmatn, Tahoma, sans-serif !important;
}

.stApp { background-color: #0b0d12; }

.block-container {
    padding-top: 1rem;
    max-width: 1080px;
}

.card {
    background: #151821;
    border: 1px solid #252a36;
    border-radius: 10px;
    padding: 0.9rem 0.7rem;
    text-align: center;
}

.card-label { color: #8b93a7; font-size: 0.78rem; margin-bottom: 0.2rem; }
.card-value { font-size: 1.25rem; font-weight: 700; color: #f1f5f9; }
.pos { color: #34d399; }
.neg { color: #f87171; }

.signal-box {
    border-radius: 10px;
    padding: 0.9rem;
    text-align: center;
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0.5rem 0 1rem 0;
}
.buy { background: #064e3b; color: #6ee7b7; border: 1px solid #059669; }
.sell { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; }
.neutral { background: #1e293b; color: #cbd5e1; border: 1px solid #475569; }

.section { font-size: 1.05rem; font-weight: 600; color: #e2e8f0; margin: 1.3rem 0 0.6rem 0; }

.stTabs [data-baseweb="tab"] {
    background: #151821;
    border-radius: 8px;
    color: #94a3b8;
    padding: 0.4rem 0.9rem;
}
.stTabs [aria-selected="true"] {
    background: #1e293b !important;
    color: #fbbf24 !important;
    border: 1px solid #fbbf24;
}
</style>
""", unsafe_allow_html=True)

# ====================== منابع داده ======================
LIVE_API = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/popular.json"
HISTORY_USD = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/USD_IRR_FREE.json"
HISTORY_GOLD18 = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/history/GOLD_18K_IRR.json"
OUNCE_API = "https://api.gold-api.com/price/XAU"


@st.cache_data(ttl=35, show_spinner=False)
def fetch_live():
    out = {"usd": None, "gold18": None, "ounce": None, "ts": datetime.now().strftime("%H:%M")}
    try:
        items = requests.get(LIVE_API, timeout=9).json().get("data", [])
        for it in items:
            s = it.get("symbol", "")
            if s == "USD_IRR_FREE":
                out["usd"] = {"price": float(it.get("price", 0)), "chg": it.get("change_pct")}
            elif s == "GOLD_18K_IRR":
                out["gold18"] = {"price": float(it.get("price", 0)), "chg": it.get("change_pct")}
    except: pass

    try:
        r = requests.get(OUNCE_API, timeout=7)
        if r.status_code == 200:
            out["ounce"] = {"price": float(r.json().get("price", 0))}
    except: pass
    return out


@st.cache_data(ttl=160, show_spinner=False)
def fetch_history(days=55):
    try:
        u = pd.DataFrame(requests.get(HISTORY_USD, timeout=11).json().get("data", []))
        g = pd.DataFrame(requests.get(HISTORY_GOLD18, timeout=11).json().get("data", []))
        if u.empty or g.empty: return None
        for df in [u, g]:
            if "date_jalali" in df.columns: df["date"] = df["date_jalali"]
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = pd.merge(
            u[["date", "close"]].rename(columns={"close": "usd"}),
            g[["date", "close"]].rename(columns={"close": "gold18"}),
            on="date", how="inner"
        ).dropna().tail(days)
        return df
    except: return None


def theoretical(ounce, usd):
    if not ounce or not usd: return None
    return (ounce * usd / 31.1035) * 0.75


def intelligence_engine(live, history):
    """موتور تحلیل هوشمند چندعاملی"""
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

    # محاسبه نوسان و همبستگی
    vol = None
    corr = None
    mom5 = None
    if history is not None and len(history) > 12:
        rets = history["gold18"].pct_change().dropna()
        vol = rets.tail(10).std() * 100
        corr = rets.corr(history["usd"].pct_change().dropna())
        mom5 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-6] - 1) * 100

    # امتیازدهی چندعاملی
    score = 0.0
    factors = []

    # عامل ۱: پریمیوم (Mean Reversion)
    if prem is not None:
        if prem <= -4.0:
            score += 2.1
            factors.append(("پریمیوم خیلی منفی", +2.1, "فرصت خرید نسبی"))
        elif prem <= -2.2:
            score += 1.1
            factors.append(("پریمیوم منفی", +1.1, "ارزش نسبی خوب"))
        elif prem >= 5.5:
            score -= 2.1
            factors.append(("پریمیوم خیلی بالا", -2.1, "گران‌تر از ارزش جهانی"))
        elif prem >= 3.2:
            score -= 1.0
            factors.append(("پریمیوم بالا", -1.0, "احتیاط"))

    # عامل ۲: مومنتوم کوتاه‌مدت
    if g_chg is not None and u_chg is not None:
        if g_chg > 1.2 and u_chg > 0.8:
            score += 1.6
            factors.append(("مومنتوم هم‌جهت صعودی", +1.6, "قدرت روند"))
        elif g_chg < -1.2 and u_chg < -0.6:
            score -= 1.6
            factors.append(("مومنتوم هم‌جهت نزولی", -1.6, "فشار فروش"))

    # عامل ۳: همبستگی
    if corr is not None:
        if corr > 0.75 and g_chg and g_chg > 0 and u_chg and u_chg > 0:
            score += 0.7
            factors.append(("همبستگی قوی + دلار صعودی", +0.7, "حمایت از روند"))
        elif corr > 0.75 and g_chg and g_chg < 0 and u_chg and u_chg < 0:
            score -= 0.7
            factors.append(("همبستگی قوی + دلار نزولی", -0.7, "فشار بیشتر"))

    # عامل ۴: فیلتر نوسان
    if vol is not None and vol > 2.7:
        score *= 0.72
        factors.append(("نوسان بالا", 0, f"نوسان {vol:.1f}% → کاهش اطمینان"))

    # تشخیص رژیم
    if score >= 2.4:
        regime, signal, conf = "صعودی قوی", "خرید قوی", min(92, 68 + score * 8)
    elif score >= 1.0:
        regime, signal, conf = "صعودی ملایم", "خرید محتاطانه", min(78, 55 + score * 9)
    elif score <= -2.4:
        regime, signal, conf = "نزولی قوی", "فروش / کاهش", min(92, 68 + abs(score) * 8)
    elif score <= -1.0:
        regime, signal, conf = "نزولی ملایم", "فروش محتاطانه", min(78, 55 + abs(score) * 9)
    else:
        regime, signal, conf = "رنج / نامشخص", "خنثی / نظاره‌گر", 45 + abs(score) * 5

    # پیش‌بینی ساده اما وزن‌دار
    pred = None
    if history is not None and len(history) > 14 and g_price:
        rets = history["gold18"].pct_change().dropna()
        short = rets.tail(3).mean()
        med = rets.tail(8).mean()
        usd_s = history["usd"].pct_change().tail(3).mean()
        expected = short * 0.48 + med * 0.27 + (usd_s * (corr if corr and not np.isnan(corr) else 0.6)) * 0.25
        # کمی بازگشت به میانگین اگر پریمیوم خیلی منحرف باشد
        if prem is not None:
            if prem < -4: expected += 0.004
            elif prem > 5: expected -= 0.004
        hour = g_price * (1 + expected * 0.16)
        d1 = g_price * (1 + expected * 0.85)
        d3 = g_price * (1 + expected * 2.1)
        pred = {"hour": hour, "d1": d1, "d3": d3, "expected_daily": expected * 100}

    return {
        "theo": theo, "prem": prem, "vol": vol, "corr": corr, "mom5": mom5,
        "score": score, "factors": factors, "regime": regime,
        "signal": signal, "confidence": conf, "pred": pred
    }


def scenario(gold_price, usd_price, ounce_price, usd_change_pct):
    """سناریو: اگر دلار X درصد تغییر کند"""
    if not all([gold_price, usd_price, ounce_price]):
        return None
    new_usd = usd_price * (1 + usd_change_pct / 100)
    new_theo = theoretical(ounce_price, new_usd)
    # فرض: طلا حدود ۷۰٪ حرکت دلار را دنبال می‌کند در کوتاه‌مدت
    estimated_gold = gold_price * (1 + usd_change_pct / 100 * 0.7)
    return {"new_usd": new_usd, "new_theo": new_theo, "est_gold": estimated_gold}


# ====================== اجرا ======================
live = fetch_live()
history = fetch_history()

if not live.get("gold18"):
    st.error("داده زنده در دسترس نیست. چند لحظه دیگر تلاش کنید.")
    st.stop()

intel = intelligence_engine(live, history)

# هدر
st.markdown("""
<div style="text-align:center;margin-bottom:1rem;">
    <div style="font-size:1.55rem;font-weight:700;color:#fbbf24;">🥇 Gold18K Intelligence</div>
    <div style="color:#94a3b8;font-size:0.85rem;">موتور تحلیل هوشمند طلای ۱۸ عیار ایران</div>
</div>
""", unsafe_allow_html=True)

# کارت‌های اصلی
c1, c2, c3, c4 = st.columns(4)

def card(label, value, chg=None):
    delta = ""
    if chg is not None:
        cls = "pos" if chg >= 0 else "neg"
        delta = f'<div class="{cls}" style="font-size:0.8rem;">{chg:+.2f}%</div>'
    st.markdown(f'<div class="card"><div class="card-label">{label}</div><div class="card-value">{value}</div>{delta}</div>', unsafe_allow_html=True)

with c1: card("دلار آزاد", f"{live['usd']['price']:,.0f}" if live.get("usd") else "—", live.get("usd", {}).get("chg"))
with c2: card("طلای ۱۸ عیار", f"{live['gold18']['price']:,.0f}", live.get("gold18", {}).get("chg"))
with c3: card("انس جهانی", f"{live['ounce']['price']:,.1f} $" if live.get("ounce") and live["ounce"].get("price") else "—")
with c4:
    prem_txt = f"{intel['prem']:+.2f}%" if intel["prem"] is not None else "—"
    card("پریمیوم", prem_txt)

st.caption(f"آخرین بروزرسانی: {live.get('ts')} | رژیم فعلی: **{intel['regime']}**")

# تب‌ها
t1, t2, t3, t4 = st.tabs(["هوش مصنوعی", "پیش‌بینی و سناریو", "اخبار و تأثیر", "جزئیات فنی"])

with t1:
    sig_class = "buy" if "خرید" in intel["signal"] else "sell" if "فروش" in intel["signal"] else "neutral"
    st.markdown(f'<div class="signal-box {sig_class}">{intel["signal"]}  •  اطمینان {intel["confidence"]:.0f}٪</div>', unsafe_allow_html=True)

    st.markdown('<div class="section">عوامل مؤثر در سیگنال</div>', unsafe_allow_html=True)
    if intel["factors"]:
        for name, sc, desc in intel["factors"]:
            color = "#34d399" if sc > 0 else "#f87171" if sc < 0 else "#94a3b8"
            st.markdown(f"- **{name}** <span style='color:{color}'>({sc:+.1f})</span> → {desc}", unsafe_allow_html=True)
    else:
        st.write("عامل قوی خاصی شناسایی نشد.")

    st.markdown('<div class="section">خلاصه هوشمند امروز</div>', unsafe_allow_html=True)
    summary = f"بازار در رژیم **{intel['regime']}** قرار دارد. "
    if intel["prem"] is not None:
        if intel["prem"] < -3:
            summary += "طلای داخلی نسبت به ارزش جهانی ارزان‌تر است. "
        elif intel["prem"] > 4:
            summary += "طلای داخلی گران‌تر از ارزش جهانی معامله می‌شود. "
    if intel["vol"] and intel["vol"] > 2.5:
        summary += "نوسان بالاست و باید با حجم کمتر وارد شد."
    else:
        summary += "نوسان در محدوده قابل قبول قرار دارد."
    st.info(summary)

with t2:
    if intel["pred"]:
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("فعلی", f"{live['gold18']['price']:,.0f}")
        p2.metric("\~۱ ساعت", f"{intel['pred']['hour']:,.0f}")
        p3.metric("فردا", f"{intel['pred']['d1']:,.0f}")
        p4.metric("۳ روز بعد", f"{intel['pred']['d3']:,.0f}")
        st.caption(f"مومنتوم مورد انتظار روزانه: {intel['pred']['expected_daily']:+.2f}%")
    else:
        st.warning("داده کافی برای پیش‌بینی نیست.")

    st.markdown('<div class="section">سناریوسازی</div>', unsafe_allow_html=True)
    sc = st.slider("فرض تغییر دلار آزاد (درصد)", -3.0, 3.0, 0.0, 0.5)
    res = scenario(live["gold18"]["price"], live["usd"]["price"] if live.get("usd") else None,
                   live["ounce"]["price"] if live.get("ounce") else None, sc)
    if res:
        st.write(f"اگر دلار **{sc:+.1f}%** تغییر کند:")
        st.write(f"- دلار جدید تقریبی: **{res['new_usd']:,.0f}** تومان")
        st.write(f"- قیمت تئوریک جدید: **{res['new_theo']:,.0f}** تومان")
        st.write(f"- تخمین طلای ۱۸ عیار: **{res['est_gold']:,.0f}** تومان")

with t3:
    st.markdown('<div class="section">قوانین تأثیر اخبار بر طلای ایران</div>', unsafe_allow_html=True)
    st.markdown("""
| نوع خبر | تأثیر کوتاه‌مدت روی طلای ۱۸ عیار | شدت |
|--------|----------------------------------|------|
| افزایش تنش سیاسی / تحریم جدید | صعودی (دلار + طلا با هم بالا می‌روند) | بالا |
| خبر توافق یا کاهش تنش | نزولی کوتاه‌مدت | متوسط تا بالا |
| افزایش شدید دلار آزاد | صعود قوی طلا | خیلی بالا |
| کاهش دلار آزاد | اصلاح طلا | بالا |
| تصمیم انقباضی فدرال رزرو | فشار روی انس → تأثیر منفی روی طلای داخلی | متوسط |
| تقاضای فیزیکی بالا (مناسبت‌ها) | حمایت از قیمت | متوسط |
| عرضه سنگین یا فروش دولتی | فشار نزولی | متوسط |
""")
    st.markdown("---")
    st.markdown("**وضعیت فعلی از دید خبری (بر اساس قیمت):**")
    if intel["prem"] is not None and intel["prem"] < -3:
        st.success("پریمیوم منفی فعلی معمولاً در نبود خبر منفی سیاسی، از قیمت حمایت می‌کند.")
    elif intel["prem"] is not None and intel["prem"] > 4.5:
        st.error("پریمیوم بالا نشان می‌دهد بازار داخلی نسبت به انس گران شده و حساس به خبر منفی است.")
    else:
        st.info("بازار در تعادل نسبی قرار دارد. خبرهای سیاسی بیشترین تأثیر را خواهند داشت.")

with t4:
    col1, col2, col3 = st.columns(3)
    col1.metric("قیمت تئوریک", f"{intel['theo']:,.0f}" if intel["theo"] else "—")
    col2.metric("نوسان ۱۰روزه", f"{intel['vol']:.2f}%" if intel["vol"] else "—")
    col3.metric("همبستگی با دلار", f"{intel['corr']:.2f}" if intel["corr"] is not None else "—")
    if intel["mom5"] is not None:
        st.metric("تغییر ۵ روزه طلا", f"{intel['mom5']:+.2f}%")

# نمودار
if history is not None and len(history) > 8:
    st.markdown('<div class="section">روند قیمت</div>', unsafe_allow_html=True)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=history["date"], y=history["gold18"], name="طلای ۱۸ عیار",
                             line=dict(color="#fbbf24", width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=history["date"], y=history["usd"], name="دلار",
                             line=dict(color="#60a5fa", width=1.6)), secondary_y=True)
    fig.update_layout(template="plotly_dark", height=320, margin=dict(l=10, r=10, t=15, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", y=1.08))
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

st.caption("این سیستم تحلیلی است و توصیه سرمایه‌گذاری محسوب نمی‌شود. اخبار سیاسی می‌تواند همه محاسبات را تغییر دهد.")