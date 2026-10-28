# ========== Gold18K Pro · daily_signal.py ==========
# 📂 مسیر ریپو: daily_signal.py
# ثبتِ روزانهٔ تصمیمِ موتور در data/signals.csv + ارزیابی خودکار پس از افق
# + سنجهٔ «گران یا ارزان» برای زمان‌بندی خرید ماهانه طلا.
# اجرا: python daily_signal.py   (فایل app.py باید کنارش باشد)

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

SIGNALS = os.getenv("GOLD18K_SIGNALS", "data/signals.csv")
FIELDS = ["created_utc", "day", "decision", "p_up", "comp", "price", "sigma",
          "horizon", "due_day", "ret_pct", "result", "pct90", "dev30", "rank30", "tag"]

# همان تنظیماتی که در برنامه انتخاب می‌کنی؛ اینجا باید یکی باشد
CONFIG = {
    "horizon_days": 5,
    "cost_pct": 0.45,
    "knn_k": 40,
    "z_win": 60,
}

LOOKBACK = 90          # صدک قیمت نسبت به چند روز
RANK_WINDOW = 180      # پنجرهٔ رتبه‌بندی انحراف از روند
EMA_SPAN = 30          # میانگین متحرک مرجع


def load_engine():
    for name in ("app", "app_v3", "gold18k"):
        try:
            return __import__(name)
        except Exception:
            continue
    print("فایل app پیدا نشد. app.py باید کنار daily_signal.py باشد.")
    sys.exit(1)


def get_history(engine):
    func = getattr(engine.fetch_history, "__wrapped__", engine.fetch_history)
    for candidate in (func, engine.fetch_history):
        try:
            hist = candidate()
            if hist is not None and len(hist) > 60:
                return hist
        except Exception:
            continue
    return None


def read_signals() -> pd.DataFrame:
    if os.path.exists(SIGNALS):
        try:
            df = pd.read_csv(SIGNALS)
            for col in FIELDS:
                if col not in df.columns:
                    df[col] = ""
            return df[FIELDS]
        except Exception:
            pass
    return pd.DataFrame(columns=FIELDS)


def write_signals(df: pd.DataFrame) -> None:
    folder = os.path.dirname(os.path.abspath(SIGNALS))
    if folder:
        os.makedirs(folder, exist_ok=True)
    df = df.drop_duplicates(subset=["day"], keep="last").sort_values("day")
    df.to_csv(SIGNALS, index=False)


def price_context(hist: pd.DataFrame) -> dict:
    """امروز گران است یا ارزان — هم به قیمت خام، هم نسبت به روند.
    در بازارِ صعودی، صدکِ قیمت خام همیشه بالا می‌ماند؛ پس داوریِ نهایی بر پایهٔ
    انحراف از میانگین ۳۰ روزه است، نه خودِ قیمت."""
    out = {"pct90": None, "dev30": None, "rank30": None, "tag": "نامشخص"}
    try:
        closed = hist["gold18"].astype(float).reset_index(drop=True)
        if len(closed) < 35:
            return out
        price = float(closed.iloc[-1])

        win = closed.tail(LOOKBACK)
        if len(win) >= 20:
            out["pct90"] = float((win < price).mean() * 100)

        ema = closed.ewm(span=EMA_SPAN, adjust=False).mean()
        dev = (closed / ema - 1) * 100
        dev_now = float(dev.iloc[-1])
        out["dev30"] = dev_now

        past = dev.tail(RANK_WINDOW).dropna()
        if len(past) >= 40:
            rank = float((past < dev_now).mean() * 100)
            out["rank30"] = rank
            if rank <= 30:
                out["tag"] = "ارزان"
            elif rank >= 70:
                out["tag"] = "گران"
            else:
                out["tag"] = "متعادل"
    except Exception:
        pass
    return out


def resolve(df: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    closes = hist.set_index("day")["gold18"]
    today = closes.index.max()
    for i, row in df.iterrows():
        if str(row["result"]).strip() not in ("", "nan"):
            continue
        if str(row["decision"]).strip() == "نظاره":
            continue
        try:
            due = pd.Timestamp(row["due_day"])
            price = float(row["price"])
        except Exception:
            continue
        if pd.isna(due) or due > today:
            continue
        after = closes[closes.index >= due]
        if after.empty:
            continue
        exit_price = float(after.iloc[0])
        side = 1 if str(row["decision"]).startswith("خرید") else -1
        ret = (exit_price / price - 1) * 100 * side - CONFIG["cost_pct"]
        df.at[i, "ret_pct"] = round(ret, 2)
        df.at[i, "result"] = "برد" if ret > 0 else "باخت"
    return df


def main() -> int:
    engine = load_engine()
    for k, v in CONFIG.items():
        engine.CFG[k] = v

    hist = get_history(engine)
    if hist is None:
        print("تاریخ روزانه به دست نیامد.")
        return 1

    live = engine.fetch_live()
    r = engine.build_engine(hist, live, pd.DataFrame())
    if not r.get("ok"):
        print("موتور نتوانست محاسبه کند:", r.get("reason", "نامشخص"))
        return 1

    ctx = price_context(hist)
    df = read_signals()
    df = resolve(df, hist)

    today = str(hist["day"].max())[:10]
    if today not in set(df["day"].astype(str)):
        horizon = int(CONFIG["horizon_days"])
        due = (pd.Timestamp(today) + pd.Timedelta(days=horizon)).strftime("%Y-%m-%d")
        df = pd.concat([df, pd.DataFrame([{
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "day": today,
            "decision": r["decision"],
            "p_up": round(r["p_now"], 4),
            "comp": round(r["comp"], 4),
            "price": int(r["price"]),
            "sigma": round(r["sigma_d"], 5),
            "horizon": horizon,
            "due_day": due,
            "ret_pct": "",
            "result": "",
            "pct90": "" if ctx["pct90"] is None else round(ctx["pct90"]),
            "dev30": "" if ctx["dev30"] is None else round(ctx["dev30"], 2),
            "rank30": "" if ctx["rank30"] is None else round(ctx["rank30"]),
            "tag": ctx["tag"],
        }])], ignore_index=True)
        print(f"سیگنال امروز ثبت شد: {r['decision']} | احتمال {r['p_now'] * 100:.0f}٪ | "
              f"قیمت {r['price']:,.0f} | موعد {due}")
    else:
        print(f"سیگنال {today} قبلاً ثبت شده است.")

    write_signals(df)

    print("\nگران یا ارزان (برای خرید ماهانه)")
    if ctx["dev30"] is not None:
        print(f"  قیمت نسبت به میانگین ۳۰ روزه: {ctx['dev30']:+.2f}٪")
    if ctx["rank30"] is not None:
        print(f"  رتبهٔ این انحراف در {RANK_WINDOW} روز: {ctx['rank30']:.0f} از ۱۰۰")
    if ctx["pct90"] is not None:
        print(f"  صدک قیمت خام در {LOOKBACK} روز: {ctx['pct90']:.0f} از ۱۰۰")
    print(f"  داوری: {ctx['tag']}")

    if ctx["tag"] == "ارزان":
        print("  پیشنهاد: نسبت به روندِ اخیر پایین‌تر است؛ برای خرید نقطهٔ بهتری از میانگین است.")
    elif ctx["tag"] == "گران":
        print("  پیشنهاد: بالاتر از روندِ اخیر است؛ اگر عجله نداری، چند روز صبر ارزان‌تر است.")
    elif ctx["tag"] == "متعادل":
        print("  پیشنهاد: نه گران نه ارزان؛ خرید در برنامهٔ ماهانه‌ات را عقب نینداز.")
    else:
        print("  دادهٔ کافی برای داوری نیست.")

    done = df[df["result"].isin(["برد", "باخت"])]
    if not done.empty:
        wins = int((done["result"] == "برد").sum())
        avg = float(done["ret_pct"].astype(float).mean())
        print(f"\nکارنامهٔ واقعی تا امروز: {len(done)} نتیجه — {wins} برد "
              f"({wins / len(done) * 100:.0f}٪) — میانگین هر معامله {avg:+.2f}٪")
    else:
        print("\nهنوز هیچ سیگنالی به موعدش نرسیده است.")
    return 0


if __name__ == "__main__":
    sys.exit(main())