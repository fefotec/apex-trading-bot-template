#!/usr/bin/env python3
"""
APEX - Daily Heartbeat
========================
Sendet taeglich eine Status-Nachricht per Telegram.
Beweist: Server laeuft, Crontab aktiv, API erreichbar.

Cron: Taeglich 07:00 Berlin (05:00 UTC)
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_sender import send_telegram_message
from hyperliquid_client import HyperliquidClient

# Pfade
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
if os.path.exists("/data/.openclaw/workspace/projects/apex-trading/data"):
    DATA_DIR = "/data/.openclaw/workspace/projects/apex-trading/data"


def main():
    client = HyperliquidClient()

    # Balance (Spot + Margin)
    spot = client.get_balance()
    margin_value = 0.0
    try:
        state = client.get_account_state()
        if "error" not in state:
            margin_value = float(state.get("marginSummary", {}).get("accountValue", 0))
    except Exception:
        pass
    total = spot + margin_value

    # Positionen
    positions = client.get_positions()
    pos_text = "Keine"
    if positions:
        lines = []
        for p in positions:
            d = "LONG" if p.size > 0 else "SHORT"
            emoji = "+" if p.unrealized_pnl >= 0 else ""
            lines.append(f"  {p.coin} {d} | PnL: {emoji}${p.unrealized_pnl:.2f}")
        pos_text = "\n".join(lines)

    # PnL Tracker
    pnl_text = ""
    pnl_file = os.path.join(DATA_DIR, "pnl_tracker.json")
    if os.path.exists(pnl_file):
        import json
        with open(pnl_file) as f:
            pnl = json.load(f)
        total_pnl = pnl.get("realized_pnl", 0)
        wins = pnl.get("winning_trades", 0)
        losses = pnl.get("losing_trades", 0)
        total_trades = pnl.get("total_trades", 0)
        pnl_text = (
            f"\nRealisiert: ${total_pnl:+.2f}"
            f"\nTrades: {total_trades} ({wins}W/{losses}L)"
        )

    # Wochentag
    weekday = datetime.utcnow().strftime("%A")
    date_str = datetime.utcnow().strftime("%d.%m.%Y")

    msg = (
        f"*APEX Heartbeat*\n"
        f"{date_str} ({weekday})\n\n"
        f"Kontowert: ${total:,.2f}\n"
        f"Spot: ${spot:,.2f} | Margin: ${margin_value:,.2f}"
        f"{pnl_text}\n\n"
        f"Positionen:\n{pos_text}\n\n"
        f"System: Crontab aktiv"
    )

    send_telegram_message(msg)
    print(msg.replace("*", ""))
    print("NO_REPLY")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Heartbeat ERROR: {e}")
        send_telegram_message(f"Heartbeat ERROR: {e}")
        print("NO_REPLY")
        sys.exit(1)
