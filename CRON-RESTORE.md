# APEX Cron Jobs - Restore Guide

**Backup-Datei:** `CRON-BACKUP.json`  
**Erstellt:** 2026-03-28 07:56  
**Jobs:** 28 APEX Cron Jobs

## 📋 Übersicht

**Daily Trading Sessions:**
- **Tokyo** (02:00-03:30 Berlin): 6 Crons
- **EU** (08:30-10:30 Berlin): 5 Crons
- **US** (21:00-23:00 Berlin): 7 Crons

**Weekend Momentum:**
- Check (Fr 23:00 Berlin)
- Entry (Sa 00:05 UTC)
- Exit (So 21:00 Berlin)

**Monitoring:**
- Position Monitor (alle 30 Min)
- Webhook Watchdog (alle 5 Min)

**Reviews:**
- 2-Wochen Review (9. April)
- 30-Tage Review (24. April)
- Hybrid-Strategie Switch (3. April)

## 🔧 Wichtige Konfiguration

**Alle apex-trading Crons:**
```json
{
  "sessionTarget": "isolated",
  "agentId": "apex-trading",
  "delivery": {
    "mode": "none"
  }
}
```

**Warum `delivery.mode: "none"`?**
- Scripts senden selbst via Telegram HTTP
- Kein OpenClaw delivery routing nötig
- Vermeidet "delivery target missing" Fehler

## ⚠️ API Key Workaround

Isolated Crons mit `agentId: "apex-trading"` suchen API Keys im falschen Verzeichnis (OpenClaw Bug).

**Fix:**
```bash
cp /data/.openclaw/agents/apex-trading/agent/auth-profiles.json \
   /data/.openclaw/agents/main/agent/auth-profiles.json
```

## 🚀 Restore (manuell)

Die Crons müssen über OpenClaw CLI oder API einzeln neu erstellt werden:

```bash
openclaw cron add \
  --name "APEX Position Monitor" \
  --schedule "*/30 * * * *" \
  --tz "Europe/Berlin" \
  --session-target isolated \
  --agent apex-trading \
  --payload-kind agentTurn \
  --message "Execute: python3 /data/.openclaw/workspace/projects/apex-trading/scripts/position_monitor.py" \
  --delivery-mode none
```

**Tipp:** Für Batch-Import via OpenClaw API nutzen.

## 📱 Telegram-Benachrichtigungen

**Bot:** `@apex_monitor_fefotec_bot`  
**Config:** `projects/apex-trading/.env.telegram`

Scripts senden direkt via HTTP:
```python
import requests
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')
requests.post(f'https://api.telegram.org/bot{bot_token}/sendMessage', ...)
```

## ✅ Testing

Nach Restore **IMMER testen:**

```bash
# Position Monitor
openclaw cron run <job-id> --force

# Tokyo Opening Range
openclaw cron run <job-id> --force

# US Pre-Market
openclaw cron run <job-id> --force
```

Telegram-Benachrichtigungen prüfen!
