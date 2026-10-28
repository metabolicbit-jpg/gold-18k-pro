# ========== Gold18K Pro · stability.py ==========
# 📂 مسیر ریپو: stability.py
# دو آزمون در یک اجرا:
#   ۱) پایداری: همان موتور روی ۱۰۸ ترکیب تنظیمات (کل پنجره)
#   ۲) پیش‌آزمون/پس‌آزمون: تنظیمات را روی ۷۰٪ اول انتخاب می‌کند و روی ۳۰٪ آخر که ندیده قضاوت می‌کند
# اجرا: python stability.py   (فایل app.py باید کنارش باشد)

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
TRAIN_SHARE = 0.70
MIN_TRAIN_TRADES = 12


def load_engine():
    for name in ("app", "app_v3", "gold18k"):
        try:
            return __import__(name)
        except Exception:
            continue
    print("فایل app پیدا نشد. app.py باید کنار stability.py باشد.")
    sys.exit(1)


def get_history(engine):
    func = getattr(engine.fetch_history, "__wrapped__", engine.fetch_history)
    for candidate in (func, engine.fetch_history):
        try:
            hist = candidate()
            if hist is not None and len(hist) > 120:
                return hist
        except Exception:
            continue
    return None


def metrics(trades, horizon: int = 3) -> dict:
    if trades is None or len(trades) == 0:
        return {"n": 0, "win": None, "pf": None, "dd": None, "total": None, "exp": None}
    r = trades["ret"].astype(float)
    eq = (1 + r / 100).cumprod()
    dd = float(((eq / eq.cummax()) - 1).min() * 100)
    wins, losses = r[r > 0], r[r <= 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else None
    return {"n": len(r), "win": float((r > 0).mean() * 100), "pf": pf,
            "dd": dd, "total": float(eq.iloc[-1] - 1) * 100, "exp": float(r.mean())}


def run_config(engine, hist, overrides: dict):
    """یک ترکیب را می‌آزماید و فهرست معاملات را برمی‌گرداند (بدون تغییر ماندگار در CFG)."""
    base = dict(engine.CFG)
    try:
        engine.CFG.update(overrides)
        d = engine.build_panel(hist)
        d = d.dropna(subset=["composite"]).reset_index(drop=True)
        if len(d) < 60:
            return None
        p, _, _ = engine.walk_probability(d)
        bt = engine.run_backtest(d, p)
        return bt["trades"]
    except Exception as e:
        print(f"  خطا در {overrides}: {type(e).__name__}")
        return None
    finally:
        engine.CFG.clear()
        engine.CFG.update(base)


def fmt(v, d: int = 2, suffix: str = "") -> str:
    if v is None:
        return "—"
    return f"{v:.{d}f}{suffix}"


def main() -> int:
    engine = load_engine()
    hist = get_history(engine)
    if hist is None:
        print("تاریخ روزانه به دست نیامد. اتصال شبکه را بررسی کن.")
        return 1

    split_day = hist["day"].iloc[int(len(hist) * TRAIN_SHARE)]
    train_days = int((hist["day"] < split_day).sum())
    test_days = len(hist) - train_days

    print("آزمون Gold18K")
    print(f"  پنجرهٔ کل: {len(hist)} روز")
    print(f"  آموزش (انتخاب تنظیمات): {train_days} روز تا {str(split_day)[:10]}")
    print(f"  آزمون (دادهٔ ندیده):    {test_days} روز پس از آن")
    print("  پیکربندی پایه: " + " · ".join(f"{PARAM_FA[k]}={engine.CFG.get(k)}" for k in GRID))
    print(f"  ترکیب‌ها: {len(list(itertools.product(*GRID.values())))}\n")

    keys = list(GRID)
    rows, store = [], {}
    for combo in itertools.product(*GRID.values()):
        cfg = dict(zip(keys, combo))
        trades = run_config(engine, hist, cfg)
        if trades is None:
            continue
        tr = trades[trades["day"] < split_day] if len(trades) else trades
        te = trades[trades["day"] >= split_day] if len(trades) else trades
        m_all, m_tr, m_te = metrics(trades), metrics(tr), metrics(te)

        row = {PARAM_FA[k]: cfg[k] for k in keys}
        row.update({
            "معامله": m_all["n"],
            "نرخ برد": None if m_all["win"] is None else round(m_all["win"], 1),
            "PF کل": None if m_all["pf"] is None else round(m_all["pf"], 2),
            "افت کل": None if m_all["dd"] is None else round(m_all["dd"], 1),
            "PF آموزش": None if m_tr["pf"] is None else round(m_tr["pf"], 2),
            "معاملهٔ آموزش": m_tr["n"],
            "PF آزمون": None if m_te["pf"] is None else round(m_te["pf"], 2),
            "معاملهٔ آزمون": m_te["n"],
            "نرخ برد آزمون": None if m_te["win"] is None else round(m_te["win"], 1),
        })
        rows.append(row)
        store[tuple(combo)] = {"cfg": cfg, "train": m_tr, "test": m_te}

    if not rows:
        print("هیچ ترکیبی نتیجه نداد.")
        return 1

    df = pd.DataFrame(rows)
    with pd.option_context("display.max_rows", 200, "display.width", 180):
        print(df.to_string(index=False))

    ok = df.dropna(subset=["PF کل"])
    pf = ok["PF کل"].astype(float)
    wr = ok["نرخ برد"].dropna().astype(float)
    dd = ok["افت کل"].dropna().astype(float)

    print("\n──────── خلاصهٔ پایداری (کل پنجره) ────────")
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
        grp = df.groupby(col)["PF کل"].median()
        parts = " | ".join(f"{idx} → {val:.2f}" if pd.notna(val) else f"{idx} → —"
                           for idx, val in grp.items())
        print(f"  {col}: {parts}")

    # ─────── پیش‌آزمون / پس‌آزمون ───────
    print("\n════════ پیش‌آزمون / پس‌آزمون ════════")
    print("  تنظیمات با دادهٔ آموزش انتخاب می‌شوند و روی دادهٔ آزمون قضاوت می‌شوند.\n")

    eligible = [(k, v) for k, v in store.items()
                if v["train"]["pf"] is not None and v["train"]["n"] >= MIN_TRAIN_TRADES]
    rows2 = []

    base_key = tuple(engine.CFG.get(k) for k in keys)
    base = store.get(base_key)
    if base is None:
        rounded = {}
        for kt, v in store.items():
            try:
                rounded[kt] = abs(v["cfg"]["cost_pct"] - engine.CFG["cost_pct"]) < 1e-9 and \
                              v["cfg"]["horizon_days"] == engine.CFG["horizon_days"] and \
                              v["cfg"]["z_win"] == engine.CFG["z_win"] and \
                              v["cfg"]["knn_k"] == engine.CFG["knn_k"]
            except Exception:
                rounded[kt] = False
        base = next((store[kt] for kt, ok_ in rounded.items() if ok_), None)

    if base:
        rows2.append(("تنظیم فعلی تو", base["cfg"], base["train"], base["test"]))

    if eligible:
        best_key, best = max(eligible, key=lambda kv: kv[1]["train"]["pf"])
        rows2.append(("بهترین در آموزش", best["cfg"], best["train"], best["test"]))

        med_pf = median([v["train"]["pf"] for _, v in eligible])
        near = [v for _, v in eligible if abs(v["train"]["pf"] - med_pf) < 0.08]
        if near:
            pick = near[0]
            rows2.append(("نزدیک به میانهٔ آموزش", pick["cfg"], pick["train"], pick["test"]))

    head = (f"{'انتخاب':<20} {'هزینه':>6} {'افق':>4} {'z':>4} {'k':>4} "
            f"{'PF آموزش':>9} {'PF آزمون':>9} {'برد آزمون':>10} {'افت آزمون':>10} {'معاملهٔ آزمون':>12}")
    print(head)
    print("─" * len(head))
    for title, cfg, tr, te in rows2:
        print(f"{title:<20} {cfg['cost_pct']:>6.2f} {cfg['horizon_days']:>4} {cfg['z_win']:>4} "
              f"{cfg['knn_k']:>4} {fmt(tr['pf']):>9} {fmt(te['pf']):>9} "
              f"{fmt(te['win'], 1, '٪'):>10} {fmt(te['dd'], 1, '٪'):>10} {te['n']:>12}")

    print()
    if not rows2:
        print("حکم: دادهٔ کافی برای این آزمون نبود.")
        return 0

    best_row = max(rows2, key=lambda r: (r[3]["pf"] or 0))
    te = best_row[3]
    if te["n"] < 8:
        print(f"حکم: در دورهٔ آزمون فقط {te['n']} معامله رخ داد؛ نمونه برای قضاوت کم است. "
              "پنجرهٔ تاریخ را بلندتر کن یا افق را کوتاه‌تر.")
    elif te["pf"] is None or te["pf"] < 1.0:
        print("حکم: لبه در دورهٔ ندیده بخار شد (PF آزمون زیر ۱). یعنی عددهای خوبِ آموزش "
              "حاصلِ تنظیم دقیق بودند، نه بازار. این موتور را فعلاً معیار تصمیم نگیر.")
    elif te["pf"] < 1.3:
        print(f"حکم: لبه در دورهٔ ندیده ضعیف شد ولی نمرد (PF آزمون {te['pf']:.2f}). "
              "یعنی سیگنال ارزش دیدن دارد، ولی حاشیهٔ امن ندارد؛ حجم کوچک و ریسک پایین.")
    else:
        print(f"حکم: لبه در دورهٔ ندیده هم ماند (PF آزمون {te['pf']:.2f}). "
              "این نخستین شاهد واقعی است که موتور چیزی می‌داند که در آینده هم تکرار می‌شود — "
              "ولی ۳۰٪ داده هنوز کم است؛ ادامهٔ ثبت سیگنال لازم است.")

    print("\nیادآوری: انتخاب تنظیمات با دادهٔ آموزش انجام شد و قضاوت با دادهٔ آزمون؛ "
          "پس این اعداد خوش‌بینانه نیستند.")
    return 0


if __name__ == "__main__":
    sys.exit(main())