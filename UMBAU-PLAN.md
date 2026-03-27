# APEX Bot Umbau - ABGESCHLOSSEN ✅

**Durchgeführt:** 2026-03-27 von Claude Code (nicht Lisa)
**Status:** Live, erster echter Test bei US Session 21:00

---

## Was wurde gemacht

### 1. Isolierter Agent "apex-trading" erstellt

```bash
openclaw agents add apex-trading \
  --model "google/gemini-3-flash-preview" \
  --workspace "/data/.openclaw/workspace/projects/apex-trading" \
  --non-interactive
```

- **Modell:** Google Gemini 3 Flash Preview (sehr günstig)
- **Identity:** "APEX Trading Bot" 📊
- **Workspace:** `/data/.openclaw/workspace/projects/apex-trading`
- **Google API Key:** In `/data/.openclaw/agents/apex-trading/agent/auth-profiles.json` unter `google:default`

**WICHTIG:** Agents werden über `openclaw agents add` erstellt, NICHT über `agents.entries` in openclaw.json! OpenClaw speichert sie unter `agents.list` in der Config.

### 2. Telegram-Benachrichtigungen

OpenClaw unterstützt **KEINE** mehreren Telegram-Kanäle. Stattdessen:

- Die Python-Scripts senden **direkt per HTTP** an die Telegram API via `scripts/telegram_sender.py`
- Bot-Token und Chat-ID stehen in `.env.telegram`
- **Trading-Bot:** `@apex_monitor_fefotec_bot` (Token: `8677948875:...`)
- **Lisa-Bot:** `@fexonLisa_bot` - bleibt für alles andere, hat mit Trading nichts mehr zu tun

Der apex-trading Agent hat **keine** Telegram-Delivery in OpenClaw. Alle Telegram-Nachrichten gehen direkt über die Scripts.

### 3. Alle 26 APEX Cron Jobs umgestellt

**Vorher:**
```json
{
  "agentId": "main",
  "sessionTarget": "main",
  "payload": {
    "kind": "systemEvent",
    "text": "cd ... && python3 scripts/..."
  }
}
```

**Nachher:**
```json
{
  "agentId": "apex-trading",
  "sessionTarget": "isolated",
  "payload": {
    "kind": "systemEvent",
    "text": "EXECUTE: cd ... && python3 scripts/..."
  }
}
```

### 4. BOOT.md als System-Prompt

In `/data/.openclaw/workspace/projects/apex-trading/BOOT.md` - weist den Gemini-Agent an, Befehle sofort mit exec auszuführen und nur Script-Output zurückzugeben.

---

## Architektur (Neu)

```
Cron Timer feuert
    ↓
apex-trading Agent (Gemini Flash) erhält systemEvent
    ↓
Agent führt Python-Script via exec aus
    ↓
Script läuft (API Calls an Hyperliquid, Trading-Logik)
    ↓
Script ruft send_telegram_message() auf
    ↓
HTTP POST direkt an Telegram API (Trading-Bot Token)
    ↓
Christian bekommt Nachricht von @apex_monitor_fefotec_bot
```

Lisa ist komplett raus aus dem Trading-Flow.

---

## Fallback

Falls was schiefgeht, alle APEX Crons zurück auf:
```json
{
  "agentId": "main",
  "sessionTarget": "main"
}
```
Und "EXECUTE: " Prefix aus payload.text entfernen.

---

## Bekannte Einschränkungen

- `openclaw cron run` CLI hat WebSocket-Timeout ("gateway closed") - betrifft nur Debug-CLI, nicht den internen Cron-Scheduler
- OpenClaw unterstützt keine zweiten Telegram-Kanäle (`telegram-trading` ist kein gültiger Channel-Typ)
- Die "Lessons Learned" in MEMORY.md sagen "Isolated + agentTurn = kein exec-Zugriff" - wir nutzen aber "isolated + systemEvent" was in Tests funktioniert hat
