# ========== Gold18K Pro · stability.py ==========
# 📂 مسیر ریپو: stability.py
# آزمون پایداری: همان موتورِ اپ را روی ۱۰۸ ترکیب تنظیمات می‌آزماید تا معلوم شود
# کارنامه لبهٔ واقعی دارد یا فقط به یک تنظیمِ خوش‌شانس چسبیده است.
# اجرا: python stability.py   (فایل app.py باید کنارش باشد) — پایتون ۳.۸ به بالا

from __future__ import annotations

import itertools
import sys
from statistics import median

import pandas as pd

GRID = {
    "cost_pct": [0.30, 0.45, 0.60, 0.75],
    "horizon_days": [2, 3, 5],
    "z_win": [45, 60, 75],
    "knn_k": [25, 40, 60],
}
PARAM_FA = {
    "cost_pct": "هزینه (٪)",
    "horizon_days": "افق (روز)",
    "z_win": "پنجرهٔ z",
    "knn_k": "همسایه‌ها",
}


def load_engine():
    """فایل اپ را به‌عنوان ماژول وارد می‌کند، بدون اجرای رابط کاربری."""
    for name in ("app", "app_v3", "gold18k"):
        try:
            return __import__(name)
        except Exception:
            continue
    print("فایل اپ پیدا نشد. app.py باید کنار stability.py باشد.")
    sys.exit(1)


def get_history(engine) -> pd.DataFrame | None:
    func = getattr(engine.fetch_history, "__wrapped__", engine.fetch_history)
    for candidate in (func, engine.fetch_history):
        try:
            hist = candidate()
            if hist is not None and len(hist) > 60:
                return hist
        except Exception:
            continue
    return None


def run_one(engine, hist, overrides: dict):
    base = dict(engine.CFG)
    try:
        engine.CFG.update(overrides)
        d = engine.build_panel(hist)
        d = d.dropna(subset=["composite"]).reset_index(drop=True)
        if len(d) < 40:
            return None
        p, _, _ = engine.walk_probability(d)
        bt = engine.run_backtest(d, p)
        return {
            "معامله": bt["n"],
            "نرخ برد": None if bt["win"] is None else round(bt["win"], 1),
            "PF": None if bt["pf"] is None else round(bt["pf"], 2),
            "افت (٪)": None if bt["dd"] is None else round(bt["dd"], 1),
            "بازده (٪)": None if bt["total"] is None else round(bt["total"], 1),
        }
    except Exception as e:
        print(f"  خطا در {overrides}: {type(e).__name__}")
        return None
    finally:
        engine.CFG.clear()
        engine.CFG.update(base)


def verdict(pf: pd.Series, dd: pd.Series) -> str:
    if pf.empty:
        return "هیچ ترکیبی معامله‌ای تولید نکرد؛ با این داده نمی‌شود قضاوت کرد."
    share = float((pf > 1.3).mean() * 100)
    med_pf = float(median(pf))
    med_dd = float(median(dd)) if not dd.empty else 0.0
    if med_pf >= 1.3 and share >= 60 and med_dd > -15:
        return "پایدار: لبه در بیشتر ترکیب‌ها می‌مانَد."
    if med_pf >= 1.15 and share >= 40:
        return "نیمه‌پایدار: لبه هست، ولی به تنظیمات وابسته است."
    return "شکننده: لبه احتمالاً حاصلِ تنظیم دقیق است، نه بازار."


def main() -> int:
    engine = load_engine()
    hist = get_history(engine)
    if hist is None:
        print("تاریخ روزانه به دست نیامد. اتصال شبکه را بررسی کن.")
        return 1

    base_cfg = {k: engine.CFG.get(k) for k in GRID}
    print("آزمون پایداری Gold18K")
    print(f"  پنجرهٔ تاریخ: {len(hist)} روز")
    print("  پیکربندی پایه: " + " · ".join(f"{PARAM_FA[k]}={v}" for k, v in base_cfg.items()))
    print(f"  ترکیب‌ها: {len(list(itertools.product(*GRID.values())))}\n")

    rows = []
    keys = list(GRID)
    for combo in itertools.product(*GRID.values()):
        cfg = dict(zip(keys, combo))
        out = run_one(engine, hist, cfg)
        if out is None:
            continue
        row = {PARAM_FA[k]: cfg[k] for k in keys}
        row.update(out)
        rows.append(row)

    if not rows:
        print("هیچ ترکیبی نتیجه نداد.")
        return 1

    df = pd.DataFrame(rows)
    with pd.option_context("display.max_rows", 200, "display.width", 130):
        print(df.to_string(index=False))

    ok = df.dropna(subset=["PF"])
    pf = ok["PF"].astype(float)
    wr = ok["نرخ برد"].dropna().astype(float)
    dd = ok["افت (٪)"].dropna().astype(float)

    print("\n──────── خلاصه ────────")
    print(f"  ترکیب‌های معامله‌دار: {len(ok)} از {len(df)}")
    if not wr.empty:
        print(f"  نرخ برد   : میانه {median(wr):.1f}٪ (بازهٔ {wr.min():.1f} تا {wr.max():.1f})")
    if not pf.empty:
        print(f"  Profit Factor: میانه {median(pf):.2f} (بازهٔ {pf.min():.2f} تا {pf.max():.2f})")
        print(f"  سهم ترکیب‌های با PF>1.3: {100 * (pf > 1.3).mean():.0f}٪")
    if not dd.empty:
        print(f"  حداکثر افت: میانه {median(dd):.1f}٪ (بدترین {dd.min():.1f}٪)")

    print("\n──────── حساسیت به هر پارامتر ────────")
    for k in keys:
        col = PARAM_FA[k]
        if col not in df.columns:
            continue
        grp = df.groupby(col)["PF"].median()
        parts = " | ".join(f"{idx} → {val:.2f}" if pd.notna(val) else f"{idx} → —"
                           for idx, val in grp.items())
        print(f"  {col}: {parts}")

    print(f"\nحکم: {verdict(pf, dd)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())