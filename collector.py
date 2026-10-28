# ========== Gold18K Pro · collector.py ==========
# 📂 مسیر ریپو: collector.py
# جمع‌آورِ کندلِ ۵ دقیقه‌ای: هر ۳۰ ثانیه قیمت را می‌خواند و در سطلِ ۵ دقیقه‌ای OHLC می‌سازد.
# اجرا: python collector.py            → حلقهٔ بی‌پایان
#       python collector.py --once     → یک چرخه و خروج (مناسبِ cron هر دقیقه)

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sqlite3
import time
from datetime import datetime, timezone

import requests

LIVE_API = "https://raw.githubusercontent.com/iran-market/iran-market.github.io/main/data/popular.json"
METAL_API = "https://api.gold-api.com/price/{}"
LIVE_SYMBOLS = ("GOLD_18K_IRR", "USD_IRR_FREE")
METAL_SYMBOLS = ("XAU",)
BUCKET_MIN = 5
UA = {"User-Agent": "Gold18K-Collector/1.0", "Cache-Control": "no-cache", "Pragma": "no-cache"}

log = logging.getLogger("bars5")


# ─────────── ابزار ───────────


def bucket(dt: datetime) -> datetime:
    """شروعِ سطلِ ۵ دقیقه‌ای جاری."""
    return dt.replace(minute=dt.minute - dt.minute % BUCKET_MIN, second=0, microsecond=0)


def _num(v):
    try:
        if v is None:
            return None
        f = float(str(v).replace(",", "").strip())
        return None if (math.isnan(f) or math.isinf(f) or f <= 0) else f
    except Exception:
        return None


def _short(e) -> str:
    import re

    return re.sub(r"https?://[^\s'\"]+", "<url>", str(e))[:160]


# ─────────── انبار ───────────


def open_db(path: str) -> sqlite3.Connection:
    fp = os.path.abspath(path)
    os.makedirs(os.path.dirname(fp) or ".", exist_ok=True)
    con = sqlite3.connect(fp, timeout=15)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        "CREATE TABLE IF NOT EXISTS bars5("
        "symbol TEXT NOT NULL, ts TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL,"
        " n INTEGER DEFAULT 0, PRIMARY KEY(symbol, ts))"
    )
    con.execute("CREATE INDEX IF NOT EXISTS ix_bars5_ts ON bars5(ts)")
    con.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    con.commit()
    return con


def upsert(con: sqlite3.Connection, symbol: str, ts: str, price: float) -> bool:
    """درج یا به‌روزرسانیِ کندلِ همان سطل. True یعنی کندل تازه ساخته شد."""
    row = con.execute(
        "SELECT open, high, low, close, n FROM bars5 WHERE symbol=? AND ts=?", (symbol, ts)
    ).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO bars5(symbol, ts, open, high, low, close, n) VALUES(?,?,?,?,?,?,1)",
            (symbol, ts, price, price, price, price),
        )
        return True
    o, h, l, c, n = row
    con.execute(
        "UPDATE bars5 SET high=?, low=?, close=?, n=? WHERE symbol=? AND ts=?",
        (max(h, price), min(l, price), price, (n or 0) + 1, symbol, ts),
    )
    return False


def put_meta(con, key: str, value: str):
    con.execute(
        "INSERT INTO meta(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, value)
    )


# ─────────── دریافت ───────────


def fetch_prices(session: requests.Session) -> dict:
    out: dict[str, float] = {}
    try:
        r = session.get(LIVE_API, params={"_": int(time.time())}, timeout=(5, 12))
        r.raise_for_status()
        for it in (r.json().get("data") or []):
            sym = str(it.get("symbol", ""))
            if sym in LIVE_SYMBOLS:
                p = _num(it.get("price"))
                if p:
                    out[sym] = p
    except Exception as e:
        log.warning("iran-market: %s", _short(e))

    for sym in METAL_SYMBOLS:
        try:
            r = session.get(METAL_API.format(sym), params={"_": int(time.time())}, timeout=(4, 8))
            r.raise_for_status()
            p = _num(r.json().get("price"))
            if p:
                out[sym] = p
        except Exception as e:
            log.warning("gold-api/%s: %s", sym, _short(e))
    return out


# ─────────── حلقه ───────────


def run(db: str, interval: float, once: bool, quiet: bool):
    con = open_db(db)
    session = requests.Session()
    session.headers.update(UA)

    log.info("مقصد: %s | سطل: %d دقیقه | فاصلهٔ نمونه‌گیری: %.0f ثانیه", db, BUCKET_MIN, interval)
    last = {}
    cycles = saved = dup = 0

    try:
        while True:
            now = datetime.now(timezone.utc)
            ts = bucket(now).isoformat(timespec="seconds")
            prices = fetch_prices(session)
            cycles += 1

            if prices:
                for sym, price in prices.items():
                    unchanged = last.get(sym) == price
                    if unchanged:
                        dup += 1
                    if upsert(con, sym, ts, float(price)):
                        saved += 1
                    last[sym] = price
                put_meta(con, "last_ok", now.isoformat(timespec="seconds"))
                put_meta(con, "last_prices", json.dumps({k: round(v, 2) for k, v in prices.items()}))
                put_meta(con, "cycles", str(cycles))
                con.commit()
                if not quiet:
                    log.info(
                        "%s | %s",
                        ts[11:16],
                        "  ".join(f"{k}={v:,.0f}" for k, v in prices.items()),
                    )
            else:
                log.warning("در این چرخه قیمتی دریافت نشد")

            if once:
                break
            time.sleep(max(5.0, interval))
    except KeyboardInterrupt:
        log.info("متوقف شد")
    finally:
        try:
            put_meta(con, "stopped_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
            con.commit()
            con.close()
        except Exception:
            pass
        if not quiet:
            log.info("چرخه‌ها: %d | کندلِ تازه: %d | نمونهٔ تکراری: %d", cycles, saved, dup)


def main():
    ap = argparse.ArgumentParser(description="جمع‌آورِ کندلِ ۵ دقیقه‌ای طلا و دلار")
    ap.add_argument("--db", default=os.getenv("GOLD18K_BARS", "data/bars5.db"), help="مسیر فایل دیتابیس")
    ap.add_argument("--interval", type=float, default=30.0, help="ثانیه بین نمونه‌گیری‌ها")
    ap.add_argument("--once", action="store_true", help="یک چرخه و خروج")
    ap.add_argument("--quiet", action="store_true", help="بدون لاگِ هر چرخه")
    a = ap.parse_args()
    logging.basicConfig(
        level=logging.WARNING if a.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    run(a.db, a.interval, a.once, a.quiet)


if __name__ == "__main__":
    main()