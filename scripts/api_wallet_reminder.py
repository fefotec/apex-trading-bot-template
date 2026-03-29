#!/usr/bin/env python3
"""
APEX - API Wallet Ablauf-Reminder
==================================
Warnt per Telegram wenn die API-Wallet bald ablaeuft.

Cron: 1x taeglich im Heartbeat oder separat
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_sender import send_telegram_message

# API Wallet Ablaufdatum
API_WALLET_EXPIRY = datetime(2026, 6, 27, 21, 21, 9, tzinfo=timezone.utc)
API_WALLET_NAME = "apex-bot"


def check_expiry():
    now = datetime.now(timezone.utc)
    days_left = (API_WALLET_EXPIRY - now).days

    if days_left <= 0:
        send_telegram_message(
            f"🚨 APEX API-Wallet '{API_WALLET_NAME}' ist ABGELAUFEN!\n\n"
            f"⛔ Bot kann nicht mehr traden!\n"
            f"Jetzt erneuern: app.hyperliquid.xyz → Portfolio → API"
        )
    elif days_left <= 3:
        send_telegram_message(
            f"🚨 APEX API-Wallet laeuft in {days_left} Tag(en) ab!\n\n"
            f"⛔ Ohne neue Wallet stoppt der Bot!\n"
            f"Jetzt erneuern: app.hyperliquid.xyz → Portfolio → API"
        )
    elif days_left <= 14:
        send_telegram_message(
            f"⚠️ APEX API-Wallet '{API_WALLET_NAME}' laeuft in {days_left} Tagen ab "
            f"({API_WALLET_EXPIRY.strftime('%d.%m.%Y')})\n\n"
            f"Bitte rechtzeitig erneuern."
        )
    else:
        print(f"API-Wallet OK: {days_left} Tage verbleibend")

    print("NO_REPLY")


if __name__ == "__main__":
    check_expiry()
