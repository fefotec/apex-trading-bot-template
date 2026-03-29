#!/usr/bin/env python3
"""
APEX - Data Sync Script
========================
Kopiert Trading-Daten nach data-backup/ (git-tracked) und pusht zu GitHub.
Damit sind die Daten fuer lokale Reviews per git pull verfuegbar.

Cron: Taeglich um 23:45 Berlin (nach daily_closeout um 23:00)
"""

import os
import sys
import json
import shutil
import subprocess
from datetime import datetime, timezone

# Pfade
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
BACKUP_DIR = os.path.join(PROJECT_DIR, "data-backup")

# Server-Fallback
if os.path.exists("/data/.openclaw/workspace/projects/apex-trading/data"):
    DATA_DIR = "/data/.openclaw/workspace/projects/apex-trading/data"
    PROJECT_DIR = "/data/.openclaw/workspace/projects/apex-trading"
    BACKUP_DIR = os.path.join(PROJECT_DIR, "data-backup")

# Dateien die gesynct werden sollen
SYNC_FILES = [
    "trades.json",
    "pnl_tracker.json",
    "capital_tracking.json",
    "opening_range_boxes.json",
    "monitor_state.json",
    "weekend_momo_state.json",
]


def sync_data():
    """Kopiere Data-Files nach data-backup/"""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    synced = 0
    for filename in SYNC_FILES:
        src = os.path.join(DATA_DIR, filename)
        dst = os.path.join(BACKUP_DIR, filename)

        if os.path.exists(src):
            shutil.copy2(src, dst)
            synced += 1
            print(f"  ✅ {filename}")
        else:
            print(f"  ⏭️  {filename} (nicht vorhanden)")

    # Timestamp schreiben
    meta = {
        "last_sync": datetime.now(timezone.utc).isoformat(),
        "synced_files": synced,
        "source": DATA_DIR
    }
    with open(os.path.join(BACKUP_DIR, "_sync_meta.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    return synced


def git_push():
    """Git add, commit und push der Backup-Daten"""
    try:
        os.chdir(PROJECT_DIR)

        # Add backup dir
        subprocess.run(["git", "add", "data-backup/"], check=True, capture_output=True)

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True
        )

        if result.returncode == 0:
            print("  ℹ️  Keine Aenderungen zum Committen")
            return True

        # Commit
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        subprocess.run(
            ["git", "commit", "-m", f"data-backup: {date_str}"],
            check=True,
            capture_output=True
        )

        # Push
        subprocess.run(
            ["git", "push", "origin", "main"],
            check=True,
            capture_output=True
        )

        print("  ✅ Git push erfolgreich")
        return True

    except subprocess.CalledProcessError as e:
        print(f"  ❌ Git-Fehler: {e}")
        if e.stderr:
            print(f"     {e.stderr.decode()}")
        return False


def main():
    print("=" * 50)
    print("APEX - Data Sync")
    print("=" * 50)
    print(f"Quelle: {DATA_DIR}")
    print(f"Ziel:   {BACKUP_DIR}")
    print()

    synced = sync_data()
    print(f"\n{synced} Dateien synchronisiert")

    if synced > 0:
        print("\nGit Push...")
        git_push()

    print("\nDone.")
    print("NO_REPLY")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"💥 SYNC ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("NO_REPLY")
        sys.exit(1)
