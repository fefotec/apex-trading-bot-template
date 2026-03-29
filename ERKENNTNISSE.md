# APEX - Erkenntnisse & Learnings

> Jeder Fehler, der mich nicht tötet, macht mich reicher.

---

## 📚 Strategie-Wissen

### Opening Range Breakout - Theorie

**Warum funktioniert ORB?**
- Die ersten 15 Minuten nach US-Open zeigen institutionelle Positionierung
- Große Player platzieren Orders, die Range zeigt "wahren" Wert
- Breakout aus dieser Range = neue Information, Momentum folgt

**Beste Bedingungen für ORB:**
- Klare, enge Opening Range (nicht zu volatil)
- Ausbruch mit Volumen
- Keine unmittelbaren News-Events
- Trending Market (nicht ranging)

**Schlechteste Bedingungen:**
- FOMC, NFP, CPI Tage (zu chaotisch)
- Montag-Morgen (Weekend-Gaps)
- Sehr weite Opening Range (zu viel Risiko)

---

## 🎓 Markt-Beobachtungen

### Hyperliquid-Spezifika
*(wird gefüllt sobald ich live bin)*

- Typische Spreads BTC-PERP: ?
- Typische Spreads ETH-PERP: ?
- Beste Liquidität Zeiten: ?
- Slippage-Erfahrungen: ?

### Crypto vs. Tradfi bei ORB
- Crypto hat kein echtes "Open" - aber US-Trader-Aktivität um 15:30 NY ist messbar
- BTC/ETH korrelieren oft mit S&P 500 Bewegungen
- Vorteil Crypto: 24/7, kann auch asiatische/europäische Opens nutzen

---

## 💡 Trade-Learnings

### Gewonnene Trades
*(nach jedem Win: Was hat funktioniert?)*

---

### Verlorene Trades
*(nach jedem Loss: Was ist schiefgelaufen?)*

---

## 🔧 Technische Learnings

### n8n Webhook: POST-Body liegt unter $json.body
- **Problem:** IF-Node pruefte `$json.ref` - war immer leer, Workflow brach ab
- **Ursache:** n8n Webhook-Nodes wrappen den eingehenden POST-Body unter `$json.body`. Die Top-Level Keys sind: `headers`, `params`, `query`, `body`, `webhookUrl`, `executionMode`
- **Loesung:** Alle Referenzen auf GitHub-Daten muessen `$json.body.*` verwenden (z.B. `$json.body.ref`, `$json.body.head_commit`)
- **Merke:** Bei n8n Webhooks IMMER `$json.body.*` fuer POST-Daten verwenden!

### n8n Cloud: executeCommand Node nicht verfuegbar
- **Problem:** Der originale Workflow nutzte `n8n-nodes-base.executeCommand` fuer `git pull`
- **Ursache:** n8n Cloud deaktiviert den executeCommand-Node aus Sicherheitsgruenden
- **Loesung:** HTTP Request Node stattdessen, der einen Webhook-Server auf dem Zielserver aufruft
- **Merke:** Fuer Server-Befehle auf n8n Cloud immer HTTP Request an einen eigenen Endpoint nutzen!

### Cloudflare Tunnel: Published Application Routes fuer oeffentliche URLs
- **Problem:** "Hostname routes" Tab erstellt nur private Routes (braucht WARP Client)
- **Loesung:** "Published application routes" Tab im Tunnel nutzen - das erstellt oeffentlich erreichbare Subdomains
- **Merke:** Hostname routes = privat (WARP noetig), Published application routes = oeffentlich!

### API & Infrastruktur

### OpenClaw Cron Jobs laufen NICHT ueber system-crontab
- **Problem:** `crontab -l` zeigt keine Cron Jobs an, obwohl Skripte planmaessig ausgefuehrt werden sollen
- **Ursache:** OpenClaw nutzt ein eigenes internes Scheduling-System, nicht den Linux system-crontab. Die Jobs werden ueber die OpenClaw-Platform verwaltet.
- **Loesung:** Cron Jobs immer ueber das OpenClaw Scheduling-Interface pruefen und einrichten, nicht ueber die Shell
- **Merke:** Bei OpenClaw niemals `crontab -l` oder `crontab -e` fuer Cron-Diagnose nutzen - das OpenClaw Scheduling ist ein separates System!

---

### Timing & Latenz
*(Erkenntnisse zu Ausführungszeiten)*

---

## 📊 Statistische Erkenntnisse

### Pattern-Analyse
*(Welche Setups performen am besten?)*

| Setup-Typ | Trades | Wins | Win-Rate | Avg R |
|-----------|--------|------|----------|-------|
| Momentum Breakout | 0 | 0 | - | - |
| Retest | 0 | 0 | - | - |
| Reversal | 0 | 0 | - | - |

### Tages-Analyse
*(Welche Wochentage sind am besten?)*

| Tag | Trades | Wins | Win-Rate |
|-----|--------|------|----------|
| Mo  | 0 | 0 | - |
| Di  | 0 | 0 | - |
| Mi  | 0 | 0 | - |
| Do  | 0 | 0 | - |
| Fr  | 0 | 0 | - |

---

## ⚠️ Fehler, die mich fast getötet hätten

*(Dokumentiere jeden kritischen Fehler)*

---

## 🧠 Psychologie-Notizen

*(Auch wenn ich "emotionslos" sein soll - Erkenntnisse über Entscheidungsmuster)*

---

*Letzte Aktualisierung: 2026-03-27*
