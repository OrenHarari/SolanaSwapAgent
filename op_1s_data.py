#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
op_1s_data.py
--------------
A) Historical: Downloads 1s klines from Binance Data Portal for OPUSDT for a given date, extracts and saves CSV.
B) Live: Connects to Binance WebSocket (aggTrade) and generates/updates 1-second candles in real-time to CSV file.

Usage:
  Historical (one day):
    python op_1s_data.py history --date 2025-08-15 --out op_1s_2025-08-15.csv

  Live (accumulates to rolling file):
    python op_1s_data.py live --out op_live_1s.csv
"""

import os, io, zipfile, argparse, signal, sys, time, json
from datetime import datetime, timezone
import pandas as pd
import requests

# ---------- Settings ----------

SYMBOL = "OPUSDT"
DATA_BASE = "https://data.binance.vision/data/spot/daily/klines"
CSV_COLS = [
    "open_time","open","high","low","close","volume",
    "close_time","quote_asset_volume","number_of_trades",
    "taker_buy_base_asset_volume","taker_buy_quote_asset_volume","ignore"
]
# Safe writing: every N live trades we write to disk
FLUSH_EVERY_TRADES = 200

# ---------- Part A: Historical 1s from archive ----------

def _infer_epoch_unit(val: int) -> str:
    """Determines if the time comes from microseconds (us) or milliseconds (ms)."""
    return "us" if int(val) >= 10**15 else "ms"

def _to_datetime(col, unit):
    if unit == "ms":
        return pd.to_datetime(col, unit="ms", utc=True)
    else:
        return pd.to_datetime(col, unit="us", utc=True)

def download_daily_1s_to_csv(date_str: str, out_csv: str) -> str:
    """Downloads ZIP of 1s klines for given date, extracts, fixes timestamps, and saves CSV."""
    url = f"{DATA_BASE}/{SYMBOL}/1s/{SYMBOL}-1s-{date_str}.zip"
    print(f"[INFO] Downloading: {url}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
    with zf.open(csv_name) as f:
        df = pd.read_csv(f, header=None, names=CSV_COLS)

    unit = _infer_epoch_unit(df.iloc[0]["open_time"])
    df["open_time"]  = _to_datetime(df["open_time"], unit)
    df["close_time"] = _to_datetime(df["close_time"], unit)

    # Numeric types
    num_cols = ["open","high","low","close","volume","quote_asset_volume",
                "taker_buy_base_asset_volume","taker_buy_quote_asset_volume"]
    df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce")

    # Order and write
    df.insert(0, "symbol", SYMBOL)
    df = df[["symbol","open_time","open","high","low","close","volume",
             "close_time","quote_asset_volume","number_of_trades",
             "taker_buy_base_asset_volume","taker_buy_quote_asset_volume"]]
    df.to_csv(out_csv, index=False)
    print(f"[OK] Saved {out_csv} rows={len(df)}")
    return out_csv

# ---------- Part B: Live from aggTrade to 1s aggregation ----------

# We'll use websocket-client (pip install websocket-client)
try:
    import websocket  # websocket-client
except ImportError:
    websocket = None

class OneSecondAggregator:
    """
    1s candle aggregator from aggTrade:
    - For each UTC second: OHLCV
    - Last trade price -> close
    - open from first trade price in that second
    - high/low max/min in that second
    - volume sum of base quantity (qty) in that second
    """
    def __init__(self, out_csv: str):
        self.out_csv = out_csv
        self.bars = {}  # key: second_ts (int) -> dict
        self.last_flushed_count = 0
        # If existing file exists, load it to continue (optional)
        if os.path.exists(out_csv):
            print(f"[INFO] Resuming from existing {out_csv}")
            try:
                self.existing_df = pd.read_csv(out_csv)
            except Exception:
                self.existing_df = None
        else:
            self.existing_df = None

    def _flush_to_disk(self):
        if not self.bars:
            return
        rows = []
        for sec, bar in sorted(self.bars.items()):
            rows.append({
                "symbol": SYMBOL,
                "open_time": datetime.fromtimestamp(sec, tz=timezone.utc).isoformat(),
                "open":  bar["open"],
                "high":  bar["high"],
                "low":   bar["low"],
                "close": bar["close"],
                "volume":bar["volume"]
            })
        df = pd.DataFrame(rows)
        if os.path.exists(self.out_csv):
            df.to_csv(self.out_csv, mode="a", header=False, index=False)
        else:
            df.to_csv(self.out_csv, index=False)
        print(f"[FLUSH] wrote {len(df)} rows -> {self.out_csv}")
        self.bars.clear()
        self.last_flushed_count = 0

    def add_trade(self, price: float, qty: float, trade_ts_ms: int):
        sec = trade_ts_ms // 1000
        bar = self.bars.get(sec)
        if bar is None:
            self.bars[sec] = {
                "open": price, "high": price, "low": price, "close": price,
                "volume": qty
            }
        else:
            bar["close"] = price
            if price > bar["high"]:
                bar["high"] = price
            if price < bar["low"]:
                bar["low"] = price
            bar["volume"] += qty

        self.last_flushed_count += 1
        if self.last_flushed_count >= FLUSH_EVERY_TRADES:
            self._flush_to_disk()

    def close(self):
        self._flush_to_disk()

def run_live(out_csv: str):
    if websocket is None:
        print("ERROR: missing dependency. Install: pip install websocket-client")
        sys.exit(1)

    stream = f"wss://stream.binance.com:9443/ws/{SYMBOL.lower()}@aggTrade"
    agg = OneSecondAggregator(out_csv=out_csv)
    stop_flag = {"stop": False}

    def on_message(ws, message):
        try:
            data = json.loads(message)
            # aggTrade fields: p=price, q=qty, T=trade time (ms)
            price = float(data["p"])
            qty   = float(data["q"])
            t_ms  = int(data["T"])
            agg.add_trade(price, qty, t_ms)
        except Exception as e:
            print("[WARN] parse error:", e)

    def on_error(ws, error):
        print("[WS-ERROR]", error)

    def on_close(ws, close_status_code, close_msg):
        print("[WS] closed", close_status_code, close_msg)
        agg.close()

    def on_open(ws):
        print("[WS] connected to", stream)

    def handle_sigint(sig, frame):
        print("\n[SIG] stopping...")
        stop_flag["stop"] = True
        ws.close()

    signal.signal(signal.SIGINT, handle_sigint)

    ws = websocket.WebSocketApp(
        stream, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open
    )

    # Run loop with reconnection attempts
    while not stop_flag["stop"]:
        ws.run_forever(ping_interval=20, ping_timeout=10, reconnect=5)
        if not stop_flag["stop"]:
            print("[WS] reconnecting in 3s...")
            time.sleep(3)

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)

    ap_hist = sub.add_parser("history", help="Download historical 1s file for given date")
    ap_hist.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap_hist.add_argument("--out", required=True, help="path/to/output.csv")

    ap_live = sub.add_parser("live", help="Build 1s file in real-time from aggTrade")
    ap_live.add_argument("--out", required=True, help="path/to/output.csv")

    args = ap.parse_args()

    if args.mode == "history":
        download_daily_1s_to_csv(args.date, args.out)
    elif args.mode == "live":
        run_live(args.out)

if __name__ == "__main__":
    main()
