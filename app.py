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

# ====================== استایل ======================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');
html, body, [class*="css"], .stMarkdown, div {
    font-family: Vazirmatn, Tahoma, sans-serif !important;
}
.stApp { background-color: #0b0d12; }
.block-container { padding-top: 1rem; max-width: 1080px; }
.card {
    background: #151821; border: 1px solid #252a36;
    border-radius: 10px; padding: 0.9rem 0.7rem; text-align: center;
}
.card-label { color: #8b93a7; font-size: 0.78rem; margin-bottom: 0.2rem; }
.card-value { font-size: 1.25rem; font-weight: 700; color: #f1f5f9; }
.pos { color: #34d399; } .neg { color: #f87171; }
.signal-box {
    border-radius: 10px; padding: 0.9rem; text-align: center;
    font-size: 1.15rem; font-weight: 700; margin: 0.5rem 0 1rem 0;
}
.buy { background: #064e3b; color: #6ee7b7; border: 1px solid #059669; }
.sell { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; }
.neutral { background: #1e293b; color: #cbd5e1; border: 1px solid #475569; }
.section { font-size: 1.05rem; font-weight: 600; color: #e2e8f0; margin: 1.3rem 0 0.6rem 0; }
.stTabs [data-baseweb="tab"] {
    background: #151821; border-radius: 8px; color: #94a3b8; padding: 0.4rem 0.9rem;
}
.stTabs [aria-selected="true"] {
    background: #1e293b !important; color: #fbbf24 !important; border: 1px solid #fbbf24;
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
    except:
        pass
    try:
        r = requests.get(OUNCE_API, timeout=7)
        if r.status_code == 200:
            out["ounce"] = {"price": float(r.json().get("price", 0))}
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


# ====================== موتور تحلیل جدید ======================
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

    vol = corr = mom3 = mom5 = mom10 = None
    z_prem = None

    if history is not None and len(history) > 15:
        rets_g = history["gold18"].pct_change().dropna()
        rets_u = history["usd"].pct_change().dropna()

        vol = rets_g.tail(10).std() * 100
        corr = rets_g.corr(rets_u)
        mom3 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-4] - 1) * 100
        mom5 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-6] - 1) * 100
        mom10 = (history["gold18"].iloc[-1] / history["gold18"].iloc[-11] - 1) * 100

    # Z-Score پریمیوم (فرض میانگین ≈ 0 و انحراف معیار تاریخی ≈ 2.8٪)
    if prem is not None:
        z_prem = prem / 2.8

    # ----- امتیاز چندعاملی -----
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

    # رژیم و سیگنال
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

    # ----- پیش‌بینی با محدوده و وزن‌های پویا -----
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
        expected = (w_short * short +
                    w_med * med +
                    w_usd * (usd_s * corr_safe) +
                    w_prem * (-0.15 * (z_prem if z_prem else 0) / 100))

        daily_vol = rets.tail(10).std()
        if daily_vol is None or np.isnan(daily_vol):
            daily_vol = 0.012

        hour_p = g_price * (1 + expected * 0.18)
        d1_p = g_price * (1 + expected * 0.90)
        d3_p = g_price * (1 + expected * 2.15)

        d1_low = d1_p * (1 - daily_vol * 1.05)
        d1_high = d1_p * (1 + daily_vol * 1.05)
        d3_low = d3_p * (1 - daily_vol * 1.7)
        d3_high = d3_p * (1 + daily_vol * 1.7)

        pred = {
            "hour": hour_p,
            "d1": d1_p, "d1_low": d1_low, "d1_high": d1_high,
            "d3": d3_p, "d3_low": d3_low, "d3_high": d3_high,
            "expected_daily": expected * 100,
            "weights": {"short": w_short, "med": w_med, "usd": w_usd, "prem": w_prem}
        }

    return {
        "theo": theo, "prem": prem, "z_prem": z_prem,
        "vol": vol, "corr": corr,
        "mom3": mom3, "mom5": mom5, "mom10": mom10,
        "score": score, "factors": factors,
        "regime": regime, "signal": signal, "confidence": conf,
        "pred": pred
    }


def scenario(gold_price, usd_price, ounce_price, usd_change_pct):
    if not all([gold_price, usd_price, ounce_price]):
        return None
    new_usd = usd_price * (1 + usd_change_pct / 100)
    new_theo = theoretical(ounce_price, new_usd)
    estimated_gold = gold_price * (1 + usd_change_pct / 100 * 0.7)
    return {"new_usd": new_usd, "new_theo": new_theo, "est_gold": estimated_gold}


# ====================== چک‌لیست حرفه‌ای روزانه ======================
def run_daily_checklist(live, intel):
    checks = []
    total_score = 0
    max_score = 0

    # ۱. ارزش‌گذاری
    max_score += 2
    if intel.get("z_prem") is not None:
        z = intel["z_prem"]
        if z <= -1.5:
            checks.append(("ارزش‌گذاری", "✅ عالی", f"Z-Score={z:.2f} → طلای داخلی ارزان نسبی", 2))
            total_score += 2
        elif z <= -0.7:
            checks.append(("ارزش‌گذاری", "✅ خوب", f"Z-Score={z:.2f} → ارزش نسبی مناسب", 1))
            total_score += 1
        elif z >= 1.5:
            checks.append(("ارزش‌گذاری", "❌ ضعیف", f"Z-Score={z:.2f} → طلای داخلی گران", 0))
        else:
            checks.append(("ارزش‌گذاری", "⚪ خنثی", f"Z-Score={z:.2f} → در محدوده نرمال", 1))
            total_score += 1
    else:
        checks.append(("ارزش‌گذاری", "⚪ نامشخص", "داده کافی برای Z-Score نیست", 0))

    # ۲. مومنتوم
    max_score += 2
    mom5 = intel.get("mom5")
    if mom5 is not None:
        if mom5 > 2.5:
            checks.append(("مومنتوم", "✅ قوی صعودی", f"تغییر ۵روزه: {mom5:+.1f}%", 2))
            total_score += 2
        elif mom5 > 0.8:
            checks.append(("مومنتوم", "✅ ملایم صعودی", f"تغییر ۵روزه: {mom5:+.1f}%", 1))
            total_score += 1
        elif mom5 < -2.5:
            checks.append(("مومنتوم", "❌ قوی نزولی", f"تغییر ۵روزه: {mom5:+.1f}%", 0))
        elif mom5 < -0.8:
            checks.append(("مومنتوم", "❌ ملایم نزولی", f"تغییر ۵روزه: {mom5:+.1f}%", 0))
        else:
            checks.append(("مومنتوم", "⚪ خنثی", f"تغییر ۵روزه: {mom5:+.1f}%", 1))
            total_score += 1
    else:
        checks.append(("مومنتوم", "⚪ نامشخص", "داده ناکافی", 0))

    # ۳. همبستگی
    max_score += 2
    corr = intel.get("corr")
    if corr is not None:
        if corr > 0.75:
            checks.append(("همبستگی", "✅ بالا و قابل اتکا", f"همبستگی: {corr:.2f}", 2))
            total_score += 2
        elif corr > 0.50:
            checks.append(("همبستگی", "✅ متوسط", f"همبستگی: {corr:.2f}", 1))
            total_score += 1
        else:
            checks.append(("همبستگی", "⚠️ پایین", f"همبستگی: {corr:.2f} → پیش‌بینی سخت‌تر", 0))
    else:
        checks.append(("همبستگی", "⚪ نامشخص", "داده ناکافی", 0))

    # ۴. نوسان
    max_score += 2
    vol = intel.get("vol")
    if vol is not None:
        if vol < 1.8:
            checks.append(("نوسان", "✅ آرام", f"نوسان ۱۰روزه: {vol:.1f}%", 2))
            total_score += 2
        elif vol < 2.6:
            checks.append(("نوسان", "✅ قابل قبول", f"نوسان ۱۰روزه: {vol:.1f}%", 1))
            total_score += 1
        else:
            checks.append(("نوسان", "⚠️ بالا", f"نوسان ۱۰روزه: {vol:.1f}% → ریسک بیشتر", 0))
    else:
        checks.append(("نوسان", "⚪ نامشخص", "داده ناکافی", 0))

    # ۵. قدرت سیگنال
    max_score += 2
    conf = intel.get("confidence", 0)
    if conf >= 75:
        checks.append(("قدرت سیگنال", "✅ قوی", f"اطمینان: {conf:.0f}%", 2))
        total_score += 2
    elif conf >= 55:
        checks.append(("قدرت سیگنال", "✅ متوسط", f"اطمینان: {conf:.0f}%", 1))
        total_score += 1
    else:
        checks.append(("قدرت سیگنال", "⚪ ضعیف", f"اطمینان: {conf:.0f}%", 0))

    pct = (total_score / max_score * 100) if max_score > 0 else 0
    if pct >= 75:
        overall, color = "شرایط کلی مساعد", "success"
    elif pct >= 50:
        overall, color = "شرایط متوسط / مختلط", "info"
    else:
        overall, color = "شرایط نامساعد یا پرریسک", "warning"

    return {
        "checks": checks,
        "total_score": total_score,
        "max_score": max_score,
        "pct": pct,
        "overall": overall,
        "color": color
    }


# ====================== ارسال به بله ======================
def send_to_bale(signal, confidence, regime, usd_price, gold_price, premium, z_prem):
    try:
        bot_token = st.secrets["BALE_BOT_TOKEN"]
        chat_id = st.secrets["BALE_CHAT_ID"]
    except Exception:
        return False

    prem_text = f"{premium:+.1f}%" if premium is not None else "—"
    z_text = f"{z_prem:.2f}" if z_prem is not None else "—"

    message = f"""🥇 سیگنال طلای ۱۸ عیار
زمان: {datetime.now().strftime('%H:%M')}

سیگنال: {signal}
اطمینان: {confidence:.0f}٪
رژیم: {regime}

دلار: {usd_price:,.0f}
طلا: {gold_price:,.0f}
پریمیوم: {prem_text}
Z-Score: {z_text}

#طلا #سیگنال"""

    url = f"https://tapi.bale.ai/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        st.warning(f"خطا در ارسال به بله: {e}")
        return False


# ====================== اجرای اصلی ======================
live = fetch_live()
history = fetch_history()

if not live.get("gold18"):
    st.error("داده زنده در دسترس نیست. چند لحظه دیگر تلاش کنید.")
    st.stop()

intel = intelligence_engine(live, history)
checklist = run_daily_checklist(live, intel)

# ---------- ارسال سیگنال فقط وقتی تغییر کرده باشد ----------
if "last_signal" not in st.session_state:
    st.session_state.last_signal = None

current_signal = intel["signal"]

if current_signal != st.session_state.last_signal:
    if "خرید" in current_signal or "فروش" in current_signal:
        success = send_to_bale(
            signal=intel["signal"],
            confidence=intel["confidence"],
            regime=intel["regime"],
            usd_price=live["usd"]["price"] if live.get("usd") else 0,
            gold_price=live["gold18"]["price"],
            premium=intel["prem"],
            z_prem=intel["z_prem"]
        )
        if success:
            st.toast("سیگنال به بله ارسال شد", icon="✅")
    st.session_state.last_signal = current_signal

# ====================== رابط کاربری ======================
st.markdown("""
<div style="text-align:center;margin-bottom:1rem;">
    <div style="font-size:1.55rem;font-weight:700;color:#fbbf24;">🥇 Gold18K Intelligence</div>
    <div style="color:#94a3b8;font-size:0.85rem;">موتور تحلیل هوشمند طلای ۱۸ عیار ایران</div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

def card(label, value, chg=None):
    delta = ""
    if chg is not None:
        cls = "pos" if chg >= 0 else "neg"
        delta = f'<div class="{cls}" style="font-size:0.8rem;">{chg:+.2f}%</div>'
    st.markdown(f'<div class="card"><div class="card-label">{label}</div><div class="card-value">{value}</div>{delta}</div>', unsafe_allow_html=True)

with c1:
    card("دلار آزاد", f"{live['usd']['price']:,.0f}" if live.get("usd") else "—", live.get("usd", {}).get("chg"))
with c2:
    card("طلای ۱۸ عیار", f"{live['gold18']['price']:,.0f}", live.get("gold18", {}).get("chg"))
with c3:
    card("انس جهانی", f"{live['ounce']['price']:,.1f} $" if live.get("ounce") and live["ounce"].get("price") else "—")
with c4:
    prem_txt = f"{intel['prem']:+.2f}%" if intel["prem"] is not None else "—"
    card("پریمیوم", prem_txt)

st.caption(f"آخرین بروزرسانی: {live.get('ts')} | رژیم فعلی: **{intel['regime']}** | Z-Score: **{intel['z_prem']:.2f}**" if intel.get("z_prem") is not None else f"آخرین بروزرسانی: {live.get('ts')} | رژیم فعلی: **{intel['regime']}**")

t1, t2, t3, t4 = st.tabs(["هوش مصنوعی", "پیش‌بینی و سناریو", "چک‌لیست روزانه", "جزئیات فنی"])

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
    if intel.get("pred"):
        p = intel["pred"]
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("فعلی", f"{live['gold18']['price']:,.0f}")
        p2.metric("\~۱ ساعت", f"{p['hour']:,.0f}")
        p3.metric("فردا (نقطه‌ای)", f"{p['d1']:,.0f}")
        p4.metric("۳ روز بعد", f"{p['d3']:,.0f}")

        st.caption(f"محدوده محتمل فردا: **{p['d1_low']:,.0f}** تا **{p['d1_high']:,.0f}** تومان")
        st.caption(f"محدوده محتمل ۳ روزه: **{p['d3_low']:,.0f}** تا **{p['d3_high']:,.0f}** تومان")
        st.caption(f"بازده مورد انتظار روزانه: {p['expected_daily']:+.2f}%")
    else:
        st.warning("داده کافی برای پیش‌بینی نیست.")

    st.markdown('<div class="section">سناریوسازی</div>', unsafe_allow_html=True)
    sc = st.slider("فرض تغییر دلار آزاد (درصد)", -3.0, 3.0, 0.0, 0.5)
    res = scenario(live["gold18"]["price"],
                   live["usd"]["price"] if live.get("usd") else None,
                   live["ounce"]["price"] if live.get("ounce") else None, sc)
    if res:
        st.write(f"اگر دلار **{sc:+.1f}%** تغییر کند:")
        st.write(f"- دلار جدید تقریبی: **{res['new_usd']:,.0f}** تومان")
        st.write(f"- قیمت تئوریک جدید: **{res['new_theo']:,.0f}** تومان")
        st.write(f"- تخمین طلای ۱۸ عیار: **{res['est_gold']:,.0f}** تومان")

with t3:
    st.markdown('<div class="section">چک‌لیست حرفه‌ای روزانه (خودکار)</div>', unsafe_allow_html=True)

    if checklist["color"] == "success":
        st.success(f"**نتیجه کلی:** {checklist['overall']}  |  امتیاز: {checklist['total_score']}/{checklist['max_score']} ({checklist['pct']:.0f}%)")
    elif checklist["color"] == "warning":
        st.warning(f"**نتیجه کلی:** {checklist['overall']}  |  امتیاز: {checklist['total_score']}/{checklist['max_score']} ({checklist['pct']:.0f}%)")
    else:
        st.info(f"**نتیجه کلی:** {checklist['overall']}  |  امتیاز: {checklist['total_score']}/{checklist['max_score']} ({checklist['pct']:.0f}%)")

    st.markdown("---")
    for name, status, detail, sc in checklist["checks"]:
        st.markdown(f"**{name}**: {status}  \n{detail}")

with t4:
    col1, col2, col3 = st.columns(3)
    col1.metric("قیمت تئوریک", f"{intel['theo']:,.0f}" if intel["theo"] else "—")
    col2.metric("نوسان ۱۰روزه", f"{intel['vol']:.2f}%" if intel["vol"] else "—")
    col3.metric("همبستگی با دلار", f"{intel['corr']:.2f}" if intel["corr"] is not None else "—")

    if intel.get("z_prem") is not None:
        st.metric("Z-Score پریمیوم", f"{intel['z_prem']:.2f}")
    if intel.get("mom5") is not None:
        st.metric("تغییر ۵ روزه طلا", f"{intel['mom5']:+.2f}%")
    if intel.get("mom10") is not None:
        st.metric("تغییر ۱۰ روزه طلا", f"{intel['mom10']:+.2f}%")

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