#!/usr/bin/env python3
"""
APEX - Healthcheck Ping
=========================
Pingt healthchecks.io (oder kompatiblen Dienst) nach erfolgreichem Script-Lauf.
Wenn der Ping ausbleibt, sendet healthchecks.io einen Alarm per Telegram.

Setup:
  1. Account auf healthchecks.io erstellen (kostenlos, 20 Checks)
  2. Checks anlegen (z.B. "apex-position-monitor", Period: 35 Min)
  3. Telegram-Integration in healthchecks.io einrichten
  4. Ping-URLs in /data/.openclaw/.../healthcheck_urls.json eintragen

Format healthcheck_urls.json:
{
  "position_monitor": "https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "session_tokyo": "https://hc-ping.com/...",
  "session_eu": "https://hc-ping.com/...",
  "session_us": "https://hc-ping.com/...",
  "daily_heartbeat": "https://hc-ping.com/...",
  "weekend_momo": "https://hc-ping.com/...",
  "data_sync": "https://hc-ping.com/..."
}
"""

import os
import json
import requests

# Config-Datei fuer Ping-URLs
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
if os.path.exists("/data/.openclaw/workspace/projects/apex-trading/data"):
    DATA_DIR = "/data/.openclaw/workspace/projects/apex-trading/data"

URLS_FILE = os.path.join(DATA_DIR, "healthcheck_urls.json")


def ping(check_name, status="ok"):
    """
    Sende Ping an healthchecks.io fuer einen bestimmten Check.

    Args:
        check_name: Key aus healthcheck_urls.json (z.B. "position_monitor")
        status: "ok" (success) oder "fail" (error)
    """
    try:
        if not os.path.exists(URLS_FILE):
            return  # Keine URLs konfiguriert -- still ignorieren

        with open(URLS_FILE) as f:
            urls = json.load(f)

        url = urls.get(check_name)
        if not url:
            return  # Kein URL fuer diesen Check

        # /fail anhaengen fuer Fehler-Signal
        if status == "fail":
            url = url.rstrip("/") + "/fail"

        requests.get(url, timeout=5)
    except Exception:
        pass  # Healthcheck-Fehler sollen nie den Trading-Betrieb stoeren
