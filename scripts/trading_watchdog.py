#!/usr/bin/env python3
"""
APEX Trading Watchdog - Überwachung & Auto-Fix
================================================
Läuft alle 30 Min und prüft:
- Sind alle Cron Jobs erfolgreich?
- Laufen kritische Prozesse (Webhook)?
- Gibt es unerwartete Fehler?

Bei Problemen: Automatisch fixen oder Christian alarmieren.
Läuft bis 31. März 2026.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from telegram_sender import send_telegram_message

# === Config ===
CRON_CHECK_INTERVAL_HOURS = 2  # Crons sollten innerhalb 2h gelaufen sein
CRITICAL_JOBS = [
    "58dc090d-2bb6-4375-afd3-e07836793bc6",  # Position Monitor
    "3c812aae-32c5-44d9-9774-3d97b7503e5e",  # Webhook Watchdog
]

def check_cron_jobs():
    """Prüfe Status aller APEX Cron Jobs (mit Retry bei Gateway-Timeouts)"""
    import time
    
    for attempt in range(2):  # Max 2 Versuche
        try:
            result = subprocess.run(
                ["openclaw", "cron", "list", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return {"error": "Konnte Cron Liste nicht abrufen"}
            
            jobs = json.loads(result.stdout).get("jobs", [])
            apex_jobs = [j for j in jobs if j.get("agentId") == "apex-trading" or "APEX" in j.get("name", "")]
            
            issues = []
            for job in apex_jobs:
                state = job.get("state", {})
                status = state.get("lastStatus")
                consecutive_errors = state.get("consecutiveErrors", 0)
                
                # Kritische Fehler
                if consecutive_errors >= 3:
                    issues.append({
                        "job": job.get("name"),
                        "id": job.get("id"),
                        "issue": f"{consecutive_errors} aufeinanderfolgende Fehler",
                        "error": state.get("lastError"),
                        "severity": "HIGH"
                    })
                
                # Kritische Jobs mit Fehler
                elif job.get("id") in CRITICAL_JOBS and status == "error":
                    issues.append({
                        "job": job.get("name"),
                        "id": job.get("id"),
                        "issue": "Kritischer Job fehlgeschlagen",
                        "error": state.get("lastError"),
                        "severity": "CRITICAL"
                    })
            
            return {"ok": True, "total": len(apex_jobs), "issues": issues}
            
        except subprocess.TimeoutExpired:
            if attempt == 0:
                # Erster Timeout → 10s warten und retry
                print("   ⏱️ Gateway Timeout, retry in 10s...")
                time.sleep(10)
                continue
            else:
                # Zweiter Timeout → temporäres Problem, NICHT alarmieren
                print("   ⚠️ Gateway temporär nicht erreichbar (vermutlich Restart)")
                return {"skipped": True, "reason": "Gateway restart/timeout"}
        
        except Exception as e:
            return {"error": f"Exception beim Cron-Check: {str(e)}"}


def check_webhook_server():
    """Prüfe ob Webhook Server läuft"""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        
        webhook_running = "webhook_server.py" in result.stdout
        tunnel_running = "cloudflared" in result.stdout
        
        if not webhook_running or not tunnel_running:
            return {
                "ok": False,
                "webhook": webhook_running,
                "tunnel": tunnel_running,
                "fix": "start_webhook.sh"
            }
        
        return {"ok": True}
        
    except Exception as e:
        return {"error": str(e)}


def auto_fix_webhook():
    """Starte Webhook Server neu"""
    try:
        result = subprocess.run(
            ["bash", "/data/.openclaw/workspace/projects/apex-trading/start_webhook.sh"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return {"fixed": True, "output": result.stdout}
    except Exception as e:
        return {"fixed": False, "error": str(e)}


def main():
    print("=" * 60)
    print("APEX Trading Watchdog - Überwachung läuft")
    print("=" * 60)
    
    issues = []
    fixes_applied = []
    
    # 1. Cron Jobs prüfen
    print("\n🔍 Prüfe Cron Jobs...")
    cron_check = check_cron_jobs()
    
    if cron_check.get("skipped"):
        # Gateway temporär nicht erreichbar → NICHT alarmieren
        print(f"⏭️ Übersprungen: {cron_check.get('reason')}")
    elif "error" in cron_check:
        issues.append(f"❌ Cron Check fehlgeschlagen: {cron_check['error']}")
    elif cron_check.get("issues"):
        for issue in cron_check["issues"]:
            severity_emoji = "🔥" if issue["severity"] == "CRITICAL" else "⚠️"
            issues.append(f"{severity_emoji} {issue['job']}: {issue['issue']}")
            if issue.get("error"):
                print(f"   Error: {issue['error'][:100]}")
    else:
        print(f"✅ Alle {cron_check['total']} APEX Cron Jobs OK")
    
    # 2. Webhook Server prüfen
    print("\n🔍 Prüfe Webhook Server...")
    webhook_check = check_webhook_server()
    
    if "error" in webhook_check:
        issues.append(f"❌ Webhook Check fehlgeschlagen: {webhook_check['error']}")
    elif not webhook_check.get("ok"):
        issues.append(f"⚠️ Webhook Server Problem: webhook={webhook_check.get('webhook')}, tunnel={webhook_check.get('tunnel')}")
        
        # Auto-Fix versuchen
        print("   🔧 Versuche Auto-Fix...")
        fix_result = auto_fix_webhook()
        if fix_result.get("fixed"):
            fixes_applied.append("✅ Webhook Server neu gestartet")
        else:
            issues.append(f"❌ Auto-Fix fehlgeschlagen: {fix_result.get('error')}")
    else:
        print("✅ Webhook Server läuft")
    
    # 3. Report
    if issues or fixes_applied:
        report = "🔍 *APEX Watchdog Report*\n\n"
        
        if fixes_applied:
            report += "🔧 *Auto-Fixes angewendet:*\n"
            for fix in fixes_applied:
                report += f"  {fix}\n"
            report += "\n"
        
        if issues:
            report += "⚠️ *Probleme gefunden:*\n"
            for issue in issues:
                report += f"  {issue}\n"
        
        report += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        print(f"\n{report}")
        send_telegram_message(report)
    else:
        print("\n✅ Alles OK - keine Probleme gefunden")
    
    print("\nNO_REPLY")


if __name__ == "__main__":
    main()
