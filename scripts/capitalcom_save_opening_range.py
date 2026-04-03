#!/usr/bin/env python3
"""
APEX - Save Gold Opening Range via Capital.com
================================================
Speichert High/Low der ersten 15 Min fuer Gold (XAUUSD).
Wird um 07:30 UTC (09:30 Berlin CEST) aufgerufen = 30 Min nach London Open.

WICHTIG: Bestehende save_opening_range.py (Hyperliquid) wird NICHT angefasst.
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capitalcom_client import CapitalComClient, GOLD_EPIC
from telegram_sender import send_telegram_message

# Gold Opening Range Box File
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
if os.path.exists("/data/.openclaw/workspace/projects/apex-trading/data"):
    DATA_DIR = "/data/.openclaw/workspace/projects/apex-trading/data"

GOLD_BOXES_FILE = os.path.join(DATA_DIR, "gold_opening_range_boxes.json")


def save_opening_range():
    """Hole und speichere Opening Range fuer Gold via Capital.com"""
    client = CapitalComClient()

    if not client.is_ready:
        print("  Capital.com Client nicht verbunden!")
        send_telegram_message("  Capital.com save_opening_range: Client nicht verbunden!")
        return {}

    boxes = {}

    print("=" * 60)
    print("APEX - Gold Opening Range Capture (Capital.com)")
    print("=" * 60)

    # 30m Opening Range: Hole zwei 15m-Candles und bilde die Gesamt-Range
    # Gold braucht eine breitere Box als Krypto (weniger Fake-Breakouts)
    candles = client.get_candles(GOLD_EPIC, "15m", limit=2)

    if not candles:
        print(f"  Keine Candles fuer Gold")
        send_telegram_message("  APEX Gold: Keine Candle-Daten von Capital.com!")
        return {}

    # Aus 2x 15m-Candles die 30m-Range bilden
    if len(candles) >= 2:
        combined_high = max(candles[0]["high"], candles[1]["high"])
        combined_low = min(candles[0]["low"], candles[1]["low"])
        combined_open = candles[0]["open"]
        combined_close = candles[1]["close"]
    else:
        # Fallback: nur 1 Candle verfuegbar
        combined_high = candles[0]["high"]
        combined_low = candles[0]["low"]
        combined_open = candles[0]["open"]
        combined_close = candles[0]["close"]

    boxes["XAUUSD"] = {
        "high": combined_high,
        "low": combined_low,
        "open": combined_open,
        "close": combined_close,
        "epic": GOLD_EPIC,
        "range_minutes": 30,
        "timestamp": datetime.now().isoformat()
    }

    box_range = combined_high - combined_low
    print(f"\n  XAUUSD (30m Range):")
    print(f"   High: ${combined_high:,.2f}")
    print(f"   Low:  ${combined_low:,.2f}")
    print(f"   Range: ${box_range:,.2f}")

    # Save
    os.makedirs(os.path.dirname(GOLD_BOXES_FILE), exist_ok=True)
    with open(GOLD_BOXES_FILE, 'w') as f:
        json.dump(boxes, f, indent=2)

    print(f"\n  Gold Box saved to {GOLD_BOXES_FILE}")

    # Telegram
    msg = (
        f"  APEX Gold Opening Range (Capital.com / London Open)\n\n"
        f"XAUUSD 30m: ${combined_high:,.2f} / ${combined_low:,.2f} (Range: ${box_range:,.2f})"
    )
    send_telegram_message(msg)

    return boxes


if __name__ == "__main__":
    try:
        boxes = save_opening_range()
        try:
            from healthcheck import ping
            ping("gold_opening_range")
        except Exception:
            pass
        print("NO_REPLY")
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message(f"  APEX capitalcom_save_opening_range.py ERROR: {e}")
        try:
            from healthcheck import ping
            ping("gold_opening_range", "fail")
        except Exception:
            pass
        print("NO_REPLY")
        sys.exit(1)
