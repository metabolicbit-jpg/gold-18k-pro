# ========== Gold18K Pro · daily_signal.py ==========
# 📂 مسیر ریپو: daily_signal.py
# ثبتِ روزانهٔ تصمیمِ موتور در data/signals.csv و ارزیابیِ خودکار پس از گذشت افق.
# اجرا: python daily_signal.py   (فایل app.py باید کنارش باشد؛ برای GitHub Actions ساخته شده)

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone

import pandas as pd

SIGNALS = os.getenv("GOLD18K_SIGNALS", "data/signals.csv")
FIELDS = ["created_utc", "day", "decision", "p_up", "comp", "price", "sigma",
          "horizon", "due_day", "ret_pct", "result"]

# همان تنظیماتی که در برنامه انتخاب می‌کنی؛ اینجا باید یکی باشد
CONFIG = {
    "horizon_days": 5,
    "cost_pct": 0.45,
    "knn_k": 40,
    "z_win": 60,
}


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


def resolve(df: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    """سیگنال‌هایی که موعدشان گذشته و نتیجه‌شان ثبت نشده را ارزیابی می‌کند."""
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
    empty_ticks = pd.DataFrame()
    r = engine.build_engine(hist, live, empty_ticks)
    if not r.get("ok"):
        print("موتور نتوانست محاسبه کند:", r.get("reason", "نامشخص"))
        return 1

    df = read_signals()
    df = resolve(df, hist)

    today = str(hist["day"].max())[:10]
    if today not in set(df["day"].astype(str)):
        horizon = int(CONFIG["horizon_days"])
        due = (pd.Timestamp(today) + pd.Timedelta(days=horizon)).strftime("%Y-%m-%d")
        row = {
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
        }
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        print(f"سیگنال امروز ثبت شد: {row['decision']} | احتمال {row['p_up'] * 100:.0f}٪ | "
              f"قیمت {row['price']:,} | موعد {due}")
    else:
        print(f"سیگنال {today} قبلاً ثبت شده است.")

    write_signals(df)

    done = df[df["result"].isin(["برد", "باخت"])]
    if not done.empty:
        wins = int((done["result"] == "برد").sum())
        total = len(done)
        avg = float(done["ret_pct"].astype(float).mean())
        print(f"\nکارنامهٔ واقعی تا امروز: {total} نتیجه — {wins} برد "
              f"({wins / total * 100:.0f}٪) — میانگین هر معامله {avg:+.2f}٪")
    else:
        print("\nهنوز هیچ سیگنالی به موعدش نرسیده است.")
    return 0


if __name__ == "__main__":
    sys.exit(main())