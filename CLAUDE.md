# APEX Trading Bot - Projektsteuerung

## Pflichtanweisungen

1. **Bei jedem relevanten Prompt** folgende Dateien lesen:
   - PROJEKT.md (Strategie, Regeln, Setup)
   - FORTSCHRITT.md (Trade-Log, P&L, aktueller Stand)
   - ERKENNTNISSE.md (Learnings, Marktbeobachtungen)
   - TODO.md (offene Aufgaben)
   - ARBEITSWEISE.md (Zusammenarbeitsregeln)

2. **Alle Dokumentationsdateien selbststaendig pflegen** - ohne Aufforderung aktualisieren wenn sich etwas aendert

3. **Kommunikation auf Deutsch**

## Projektinfo

| Feld | Wert |
|------|------|
| **Name** | APEX Trading Bot |
| **Beschreibung** | Autonomer ORB-Trading-Bot fuer Hyperliquid Perpetuals (BTC, ETH, SOL, AVAX) + Weekend Momentum (AVAX) |
| **Stack** | Python 3, Hyperliquid SDK, Telegram Bot API |
| **Platform** | Hyperliquid (Non-Custodial DEX) |
| **Automation** | OpenClaw Scheduling (isolierter Agent `apex-trading`, Gemini Flash) |
| **Server** | Hostinger VPS (76.13.157.140) |
| **Erstelldatum** | 2026-03-22 |
| **Arbeitsumgebung erstellt** | 2026-03-27 |

---

## Server-Zugriff: ClawdBot vs. Direct Claude

Auf dem Hostinger-Server (76.13.157.140) gibt es zwei Moeglichkeiten:

| | ClawdBot (OpenClaw Agent) | Direct Claude auf Server |
|---|---|---|
| **Wann nutzen** | Trading-Status, Cron Jobs verwalten, Telegram-Nachrichten | System-Admin, Pakete installieren, venv reparieren |
| **Zugang** | Telegram Chat mit dem ClawdBot | Claude direkt im Terminal auf dem Server starten |
| **Rechte** | OpenClaw Sandbox (kann Cron Jobs einrichten!) | Voller Zugriff (sudo, apt, pip, systemd) |
| **Kosten** | Gemini Flash (guenstig) | Claude API (teurer, sparsam nutzen) |

**Faustregel:**
- Cron Jobs einrichten/aendern → **ClawdBot** (laufen ueber OpenClaw Scheduling, NICHT system-crontab!)
- `sudo`, `pip install`, systemd, Netzwerk-Config → **Direct Claude**
- Trading-Fragen, Status-Checks → **ClawdBot**

**WICHTIG:** `crontab -l` auf dem Server zeigt KEINE Trading-Cron-Jobs an! Die laufen ueber OpenClaws eigenes Scheduling-System. Niemals system-crontab fuer Trading-Jobs verwenden!

---

## Strategien

### 1. Opening Range Breakout (ORB) - Wochentags Mo-Fr

- **Assets:** BTC, ETH, SOL, AVAX (Prioritaet: BTC > ETH > SOL > AVAX)
- **Sessions:** Tokyo (02:00), EU (09:00), US (21:30) - alle Berlin-Zeit
- **Regeln:** Max 1 Trade pro Session, 2% Risk, 2:1 R:R
- **Scripts:** `pre_market.py`, `save_opening_range.py`, `autonomous_trade.py`

### 2. Weekend Momentum Carry (WeekendMomo) - Wochenende

- **Asset:** Nur AVAX
- **Ablauf:** Fr 23:00 Check → Sa 00:05 UTC Entry → So 21:00 Exit
- **Signal:** 3-Tage-Momentum (Fr-Close / Di-Close) >= ±3%
- **Risk:** SL 1.5x ATR(14, 4h), TP 3x ATR, R:R 2:1, 2% Kontorisiko
- **Script:** `weekend_momo.py`

---

## OpenClaw Cron Jobs (26 aktiv)

### Wochentags (Mo-Fr) - 20 Jobs

**Pre-Market (2):**
| Zeit (Berlin) | Command | Job ID |
|---|---|---|
| 08:30 | `pre_market.py eu` | `0593f7e6` |
| 21:00 | `pre_market.py us` | `ead826b7` |

**Opening Range (3):**
| Zeit (Berlin) | Command | Job ID |
|---|---|---|
| 02:00 (taeglich) | `save_opening_range.py` Tokyo | `2ef09c52` |
| 09:00 | `save_opening_range.py` EU | `219fa7ef` |
| 21:30 | `save_opening_range.py` US | `ac9c9bea` |

**Autonomous Trading - EU (4):**
| Zeit | Job ID |
|---|---|
| 09:15, 09:30, 09:45, 10:00 | `55ae830e`, `1c2b188c`, `4ca50c8b`, `e6b46ccf` |

**Autonomous Trading - US (4):**
| Zeit | Job ID |
|---|---|
| 21:45, 22:00, 22:15, 22:30 | `c97909ce`, `2320742e`, `0fa26c02`, `085da488` |

**Autonomous Trading - Tokyo (4):**
| Zeit | Job ID |
|---|---|
| 02:15, 02:30, 02:45, 03:00 | `096d2f7d`, `880174ab`, `19537347`, `34356bc7` |

**Session Summaries (3):**
| Zeit | Command | Job ID |
|---|---|---|
| 03:30 (taeglich) | `session_summary.py tokyo` | `764415a4` |
| 10:30 | `session_summary.py eu` | `6408fe5c` |
| 22:45 | `session_summary.py us` | `2b4b373a` |

**Position Monitor (1):**
| Intervall | Command | Job ID |
|---|---|---|
| Alle 30 Min | `position_monitor.py` | `58dc090d` |

**Daily Closeout (1):**
| Zeit | Command | Job ID |
|---|---|---|
| 23:00 | `daily_closeout.py` | `5cb9cd4b` |

### Wochenende - 3 Jobs

| Zeit (UTC) | Zeit (Berlin CEST) | Command | Job ID |
|---|---|---|---|
| Fr 21:00 | Fr 23:00 | `weekend_momo.py --check` | `34384153` |
| Sa 00:05 | Sa 02:05 | `weekend_momo.py --entry` | `ccac8185` |
| So 19:00 | So 21:00 | `weekend_momo.py --exit` | `80fb6e0b` |

### Einmalige Reminder (3)

| Datum | Erinnerung | Job ID |
|---|---|---|
| 03.04.2026 | Hybrid-Strategie aktivieren | `aee61b72` |
| 09.04.2026 | 2-Wochen Trading Review | `7ee97cd2` |
| 24.04.2026 | 30-Tage Profitabilitaets-Check | `631838bd` |

**Alle Jobs nutzen:** `agentId: "apex-trading"`, `payload.kind: "agentTurn"`, `sessionTarget: "isolated"`

---

## Telegram Bots (3 separate)

| Bot | Username | Zweck | Wo konfiguriert |
|---|---|---|---|
| **Apex Trading Monitor** | `@apex_monitor_fefotec_bot` | Trading-Nachrichten (Entry, Exit, P&L, Summaries) | `.env.telegram` auf Server |
| **fefotec DevOps** | `@fefotec_devops_bot` | Git Auto-Pull Notifications via n8n | n8n Credential `mbQ9juUcGXMwDpIg` |
| **Fexobox Social Agent** | - | Social Media Workflow (anderes Projekt) | n8n Credential `ebvIIR1AK02T3T52` |

### Trading Bot Details
- **Token:** Siehe `.env.telegram` auf Server
- **Chat ID:** Siehe `.env.telegram` auf Server
- **Config auf Server:** `/data/.openclaw/workspace/projects/apex-trading/.env.telegram`

### DevOps Bot Details
- **Token:** Siehe n8n Credentials
- **Chat ID:** Siehe n8n Credentials
- **n8n Credential ID:** `mbQ9juUcGXMwDpIg`

---

## n8n Cloud (Auto-Pull Pipeline)

- **Instance:** https://fexon.app.n8n.cloud
- **API Key:** Siehe ~/.zshrc (N8N_API_KEY)
- **API Header:** `X-N8N-API-KEY`

### Auto-Pull Workflow

| Feld | Wert |
|------|------|
| **Workflow ID** | `up6CQr2rBPG6Aan9` |
| **Workflow Name** | APEX Trading Bot - GitHub Auto-Pull |
| **Status** | Aktiv |
| **GitHub Webhook URL** | `https://fexon.app.n8n.cloud/webhook/apex-trading-git-pull` |
| **GitHub Webhook ID** | `603085077` |

**Ablauf:** GitHub Push auf `main` → n8n Webhook → HTTP Request an ClawdBot → git pull → Telegram Notification (DevOps Bot)

### ClawdBot Webhook (Git Pull)

| Feld | Wert |
|------|------|
| **Permanente URL** | `https://apex-webhook.lisa-assistant.work` |
| **Bearer Token** | Siehe .env auf Server |
| **Service** | systemd `apex-webhook.service` auf Port 8888 |
| **Repo-Pfad auf Server** | `/data/.openclaw/workspace/projects/apex-trading` |
| **Cloudflare Tunnel** | `openclaw` (ID: `0d3f6961-db08-4825-8013-ad6558bbdede`) |
| **Domain** | `lisa-assistant.work` |

### n8n Workflow-Details (technisch)

n8n Webhook wrapped den POST-Body unter `$json.body`, nicht direkt unter `$json`. Daher:
- IF-Condition: `$json.body.ref` (nicht `$json.ref`)
- Commit-Daten: `$json.body.head_commit`, `$json.body.pusher` etc.

---

## Wichtige Dateien

### Scripts (`scripts/`)
| Script | Zweck |
|---|---|
| `autonomous_trade.py` | ORB Breakout-Erkennung + Order-Ausfuehrung |
| `weekend_momo.py` | Weekend Momentum Strategie (AVAX) |
| `pre_market.py` | Pre-Session System-Check |
| `save_opening_range.py` | Opening Range Box erfassen |
| `place_order.py` | Order-Platzierung via Hyperliquid SDK |
| `position_monitor.py` | Erkennt geschlossene Positionen, P&L |
| `monitor.py` | Trailing Stop-Loss (60s Loop) |
| `session_summary.py` | Session-Abschluss Report |
| `daily_closeout.py` | Tages-Abschluss Report |
| `telegram_sender.py` | Telegram-Nachrichten senden |
| `alerts.py` | Formatierte Trade-Alerts |
| `hyperliquid_client.py` | Production API Client |
| `orb_strategy.py` | ORB-Strategie Logik |

### Daten (`data/` auf Server)
| Datei | Inhalt |
|---|---|
| `trades.json` | Alle Trades (inkl. Session + Strategy) |
| `opening_range_boxes.json` | Aktuelle ORB-Boxen |
| `pnl_tracker.json` | P&L, Win-Rate, Milestones |
| `capital_tracking.json` | Startkapital, Einzahlungen |
| `monitor_state.json` | Position Monitor Status |
| `weekend_momo_state.json` | WeekendMomo Signal + Trade State |
| `weekend_momo.log` | WeekendMomo Cron Log |

### Config (`config/`)
- `.env.hyperliquid` - Hyperliquid Private Key + Wallet (NICHT in Git!)

## Kernregeln

- Max 1 Trade pro Session (ORB) / 1 Trade pro Wochenende (WeekendMomo)
- 2% Risk pro Trade
- Minimum 2:1 Risk-Reward Ratio
- Kill-Switch bei 50% Drawdown
