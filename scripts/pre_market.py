#!/usr/bin/env python3
"""
APEX - Pre-Market Check
========================
Prueft Balance, API-Verbindung und offene Positionen vor Session-Start.
Sendet Status-Report direkt an Telegram.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.hyperliquid_client import HyperliquidClient
from telegram_sender import send_telegram_message


SESSION_NAMES = {
    "eu": "Europa (London Open)",
    "us": "USA (NY Open)",
    "tokyo": "Tokyo"
}

SESSION_EMOJIS = {
    "eu": "\U0001f1ea\U0001f1fa",
    "us": "\U0001f1fa\U0001f1f8",
    "tokyo": "\U0001f30f"
}


def run_pre_market(session):
    """Pre-Market System Check"""
    emoji = SESSION_EMOJIS.get(session, "\U0001f4ca")
    name = SESSION_NAMES.get(session, session.upper())

    lines = [f"{emoji} APEX Pre-Market: {name}\n"]

    # API Connection Check
    try:
        client = HyperliquidClient()
        if not client.is_ready:
            lines.append("\u274c Wallet: NICHT konfiguriert!")
            send_telegram_message("\n".join(lines))
            return
        lines.append(f"\u2705 Wallet: {client.address[:10]}...{client.address[-6:]}")
    except Exception as e:
        lines.append(f"\u274c API-Verbindung fehlgeschlagen: {e}")
        send_telegram_message("\n".join(lines))
        return

    # Balance
    try:
        balance = client.get_balance()
        lines.append(f"\U0001f4b0 Balance: ${balance:,.2f} USDC")
    except Exception as e:
        lines.append(f"\u26a0\ufe0f Balance-Check fehlgeschlagen: {e}")

    # Positions
    try:
        positions = client.get_positions()
        if positions:
            lines.append(f"\U0001f4ca Offene Positionen: {len(positions)}")
            for pos in positions:
                direction = "LONG" if pos.size > 0 else "SHORT"
                pnl_emoji = "\U0001f7e2" if pos.unrealized_pnl >= 0 else "\U0001f534"
                lines.append(
                    f"  {pos.coin} {direction} | Entry: ${pos.entry_price:,.2f} | "
                    f"{pnl_emoji} P&L: ${pos.unrealized_pnl:+,.2f}"
                )
        else:
            lines.append("\U0001f4ca Keine offenen Positionen")
    except Exception as e:
        lines.append(f"\u26a0\ufe0f Positions-Check fehlgeschlagen: {e}")

    # Price Check
    try:
        btc = client.get_price("BTC")
        eth = client.get_price("ETH")
        lines.append(f"\nBTC: ${btc:,.2f} | ETH: ${eth:,.2f}")
    except Exception as e:
        lines.append(f"\u26a0\ufe0f Preis-Check fehlgeschlagen: {e}")

    lines.append(f"\n\u2705 System bereit fuer {name}")

    msg = "\n".join(lines)
    print(msg)
    send_telegram_message(msg)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pre_market.py <eu|us|tokyo>")
        sys.exit(1)

    session = sys.argv[1].lower()
    if session not in ["eu", "us", "tokyo"]:
        print(f"Invalid session: {session}")
        sys.exit(1)

    try:
        run_pre_market(session)
    except Exception as e:
        print(f"\U0001f4a5 ERROR: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message(f"\U0001f4a5 APEX pre_market.py ERROR: {e}")
        sys.exit(1)

    print("NO_REPLY")
