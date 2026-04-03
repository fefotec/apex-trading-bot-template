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

## 🐛 Bug-Learnings

### monitor.py SL-Trailing war MOCK - SL wurde nie tatsaechlich nachgezogen (2026-04-01)
- **Problem:** Der Position-Monitor zog den SL scheinbar nach - in den Logs stand "SL nachgezogen", aber auf Hyperliquid passierte nichts
- **Ursache:** `_update_sl()` war nur ein `print()`-Statement ohne Exchange-Aufruf (bewusster Platzhalter, nie fertiggestellt)
- **Loesung:** Alte SL-Orders stornieren (TP-Orders dabei unberuehrt lassen!), neuen SL via `place_stop_loss()` setzen, Telegram-Bestaetigung senden
- **Merke:** Wenn eine Funktion "MOCK" oder nur Print-Statements enthaelt, MUSS das sichtbar im Code dokumentiert sein (z.B. `# TODO: MOCK - nicht live`). Stumme Mocks in kritischen Funktionen (SL-Management) sind gefaehrlicher als fehlende Features, weil sie funktionierendes Verhalten vortaeuschen.

### session_summary.py und autonomous_trade.py waren nicht synchron (2026-04-01)
- **Problem:** session_summary.py zeigte "Breakout erkannt, Grund: Unbekannt" obwohl kein Trade ausgefuehrt wurde, und verwendete eigene hardcodierte $50-Breakout-Logik statt der ATR-basierten Logik
- **Ursache:** session_summary.py war ein fruehes Script aus der Entwicklungsphase und wurde nicht zusammen mit autonomous_trade.py weiterentwickelt - die Strategielogik war dupliziert und lief auseinander
- **Loesung:** session_summary.py verwendet jetzt dieselbe ATR-basierte Auswertungslogik wie autonomous_trade.py
- **Merke:** Auswertungs- und Reporting-Scripts muessen bei jeder Aenderung der Strategie-Logik MITGEPFLEGT werden. Wenn Strategie-Parameter oder Filter-Logik in mehreren Scripts vorkommen, diese in eine gemeinsame Funktion/Modul auslagern, um Drift zu vermeiden.

### Balance-Anzeige zeigte bei offener Position falschen Wert (2026-04-01)
- **Problem:** session_summary.py und daily_closeout.py zeigten z.B. $800, obwohl das Konto tatsaechlich $2.300+ hatte - weil eine Position offen war
- **Ursache:** Balance wurde nur als Spot-Balance abgefragt. Bei einer offenen Margin-Position ist ein Grossteil des Kapitals als Margin gebunden und taucht nicht in der Spot-Balance auf
- **Loesung:** Balance = Spot + Margin (beide Werte addieren)
- **Merke:** Bei Exchanges mit Margin-Trading IMMER beide Werte summieren. Nur Spot anzuzeigen ist bei laufenden Positionen irreführend und kann als Verlust missverstanden werden.

### Position Monitor: Nur 1 von N Closes benachrichtigt (2026-03-31)
- **Problem:** `sorted(closed_trades.values(), ...)[0]` nimmt nur den neuesten Close
- **Ursache:** Script war fuer Single-Position-Close designt, nicht fuer Multi-Close
- **Loesung:** Schleife ueber alle closed_trades
- **Merke:** Wenn ein Monitor mehrere Events gleichzeitig erkennen kann, IMMER alle verarbeiten — nicht nur das neueste. Betrifft auch trades.json und pnl_tracker (beide wurden falsch gezaehlt).

---

## 🎯 Strategie-Entscheidungen

### Strategie-Entscheidung: Split Take-Profit statt Single TP (2026-03-31)

- **Kontext:** Der Bot hatte bisher einen einzelnen TP bei 2:1 R:R. In Backtests und Live-Beobachtungen zeigte sich: Viele Trades kamen nah an 2:1 heran, drehten aber vorher um. Die Win-Rate liess sich verbessern, wenn fruehzeitig Gewinne gesichert werden.
- **Entscheidung:** Zwei Teil-Exits: TP1 bei 1:1 (50% der Position), TP2 bei 3:1 (verbleibende 50%)
- **Alternativen:** Einzelner TP bei 2:1 (einfacher, aber kein Teilgewinn bei Umkehr), TP bei 1.5:1 (zu konservativ, laesst zu viel Potenzial liegen)
- **Begruendung:** TP1 sichert das eingesetzte Risiko — nach dem ersten Hit ist der Trade Break-Even oder besser. TP2 laesst den "Runner" laufen, falls der Markt wirklich Momentum zeigt. Das verbessert die psychologische Stabilitaet und die Erwartungswert-Mathematik gleichzeitig.
- **Merke:** Bei ORB-Setups in Krypto ist ein einzelner 2:1 TP oft suboptimal — die Haelfte fruehzeitig sichern und den Rest laufen lassen fuehrt zu besserer durchschnittlicher Trefferquote bei aehnlichem Erwartungswert.

---

### Strategie-Entscheidung: ATR-basiertes Trailing statt prozentualen Trailing (2026-03-31)

- **Kontext:** Der Monitor zog den SL bisher bei 50% des maximalen Profits nach — ein fester prozentualer Abstand ohne Ruecksicht auf die aktuelle Marktvolatilitaet.
- **Entscheidung:** Ab 4% Profit: SL folgt mit 2x ATR Abstand (statt festem Prozentsatz)
- **Alternativen:** Fester Trailing bei 50% des Max-Profits, fester Trailing bei z.B. 1.5% Abstand, kein Trailing (nur TP1/TP2)
- **Begruendung:** ATR misst die tatschaechliche Schwankungsbreite des Assets im aktuellen Marktumfeld. Ein 2x ATR Trailing ist bei ruhigen Maerkten enger (weniger Gewinne zurueckgeben) und bei volatilen Maerkten weiter (kein vorzeitiger Rauswurf durch normale Schwingungen).
- **Merke:** In Krypto variiert die Volatilitaet stark — ein festes Prozent-Trailing ignoriert diese Realitaet. ATR-basiertes Trailing ist adaptiv und verhindert sowohl zu fruehes Ausgestoppt-werden als auch zu viel Gewinn-Rueckgabe.

---

### Strategie-Entscheidung: Break-Even-Regel auf 3% Profit-Schwelle angehoben (2026-03-31)

- **Kontext:** Die bisherige BE-Regel zog den SL ab 1% Profit auf Break-Even. In der Praxis haben Liquidity Grabs — kurze Kursausschlaege unter/ueber den aktuellen Kurs, die Stops auslosen bevor der eigentliche Trend weiterlaeuft — Trades vorzeitig beendet.
- **Entscheidung:** BE-Trigger angehoben auf 3% Profit, SL wird auf +1% gesetzt (nicht auf 0%)
- **Alternativen:** BE bei 1% belassen, BE erst bei 5%, BE komplett abschaffen (nur Trailing nutzen)
- **Begruendung:** Krypto-Liquidity-Grabs tauchen typischerweise 0.5-2% unter/ueber den Spread. Ein 1%-Trigger war zu nah — der Trade wurde ausgestoppt, obwohl das Setup noch intakt war. Bei 3% ist der Trade signifikant im Gewinn und ein Liquidity-Grab unter BE unwahrscheinlicher. +1% statt exakt BE gibt auch bei einem kleinen Gegenschwung noch einen minimalen Gewinn.
- **Merke:** In Krypto sollte die BE-Schwelle deutlich hoeher angesetzt werden als in Tradfi — Liquidity Grabs sind ein strukturelles Merkmal des Marktes, keine Ausnahme.

---

## 💡 Trade-Learnings

### Gewonnene Trades
*(nach jedem Win: Was hat funktioniert?)*

---

### Verlorene Trades
*(nach jedem Loss: Was ist schiefgelaufen?)*

---

## 🔧 Technische Learnings

### Technologie-Entscheidung: OKX fuer Gold-Trading geplant - GESCHEITERT (EU-Sperre)

- **Kontext:** Erweiterung des APEX-Bots um Gold (XAUUSD) als zweite Asset-Klasse. OKX wurde als MiCA-zertifizierte Exchange ausgewaehlt.
- **Entscheidung (urspruenglich):** OKX via ccxt
- **Warum gescheitert:** OKX sperrt in der EU ALLE Perpetuals und Rohstoffe fuer Privatkunden (Error 51155 "local compliance restrictions"). Das betrifft nicht nur Gold - USDT ist auf OKX fuer EU-Konten komplett gesperrt, auch der Convert Service bietet kein USDT fuer EU.
- **Loesung:** Wechsel zu Capital.com (siehe naechsten Eintrag)
- **Merke:** MiCA-Zertifizierung einer Exchange bedeutet NICHT, dass alle Instrumente fuer EU-Nutzer zugaenglich sind. OKX ist MiCA-zertifiziert, hat aber trotzdem EU-Perpetual-Sperren. Immer konkret pruefen, welche Instrumente in der EU handelbar sind - NICHT nur den MiCA-Status der Exchange!

---

### Technologie-Entscheidung: Capital.com statt OKX fuer Gold (XAUUSD)

- **Kontext:** Nach dem Scheitern von OKX (EU-Sperre fuer alle Perpetuals und USDT) wurde ein neuer Anbieter fuer Gold-CFD/Futures benoetigt, der in der EU fuer Privatkunden zugaenglich ist.
- **Entscheidung:** Capital.com via direktem REST API (`requests`-Library, kein ccxt)
- **Alternativen:** Bitget (kein MiCA-Zertifikat), Binance (kein EU-Futures-Zugang fuer Private), Interactive Brokers (kein Krypto-Trading), OANDA (nur Forex)
- **Begruendung:**
  - Capital.com ist CySEC-reguliert (EU-konform) und erlaubt EU-Privatkunden XAUUSD als CFD
  - SL/TP direkt bei der Position setzbar - vereinfacht die Architektur (kein separates SL/TP Placement, kein Orphan-Cleanup)
  - Einfacher REST API ohne komplexe Signatur-Logik - direkt mit `requests` anbindbar
  - Demo-Account verfuegbar fuer Tests ohne echtes Kapital
- **Merke:** Fuer EU-konforme Rohstoff-CFDs (Gold, Silber, Oel) ist Capital.com (CySEC) ein praktikabler Weg. Die direkte REST-API-Integration via `requests` ist bei einfachen APIs oft besser als eine Abstraktions-Library wie ccxt.

---

### Technologie-Entscheidung: ccxt als Abstraktions-Library - fuer Capital.com nicht benoetigt

- **Kontext:** ccxt wurde urspruenglich fuer OKX eingeplant. Nach dem Wechsel zu Capital.com wurde geprueft, ob ccxt Capital.com unterstuetzt.
- **Entscheidung:** ccxt wird nicht verwendet. Capital.com-Integration direkt via `requests`.
- **Alternativen:** ccxt (unterstuetzt Capital.com nicht vollstaendig), python-capitalcom (Community-Package, unzureichend gepflegt)
- **Begruendung:**
  - Capital.com hat einen einfachen, gut dokumentierten REST API
  - Direkter `requests`-Call ist transparenter, weniger Abhaengigkeiten
  - ccxt bringt fuer einen einzigen REST-API-Anbieter keinen Mehrwert
- **Merke:** ccxt lohnt sich nur wenn mehrere ccxt-kompatible Exchanges gleichzeitig genutzt werden. Fuer einzelne REST APIs ist `requests` direkter und einfacher zu debuggen.

---

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

### Dashboard: Position Close via SSH vs. direktem API-Call (2026-04-01)

- **Kontext:** Das Hyperliquid Dashboard benoetigt einen "Position schliessen"-Button, der eine Market-Order (reduce_only) ausloest. Das Dashboard laeuft im Browser, hat aber keinen direkten Zugriff auf den Hyperliquid Private Key.
- **Entscheidung:** Hyperliquid-Close laeuft via SSH auf den VPS → `place_order.py` (wie alle anderen Trading-Calls). Bitget-Close geht direkt via API (close-positions Endpoint), weil Bitget-Credentials im Dashboard-Backend liegen.
- **Alternativen:** Private Key direkt im Dashboard speichern (zu unsicher), einen separaten API-Endpunkt im Dashboard-Backend aufbauen (Mehraufwand)
- **Begruendung:** Die SSH-Loesung fuer Hyperliquid ist konsistent mit der bestehenden Architektur (alle Hyperliquid-Orders laufen ueber den VPS). Den Key ins Frontend zu legen ist ein Sicherheitsrisiko.
- **Merke:** Wenn der Private Key nur auf dem Server liegt, muessen alle signierungspflichtigen Calls ueber den Server laufen — auch Dashboard-Aktionen.

---

### Strategie-Entscheidung: MIN_BOX_ATR_RATIO von 1.0 auf 0.6 gesenkt (2026-04-01)

- **Kontext:** Der Filter prueft, ob die Opening-Range-Box gross genug im Verhaeltnis zum ATR ist (Box-Breite / ATR >= Schwellwert). Bei 1.0 wurde eine Box nur akzeptiert, wenn ihre Breite mindestens dem vollen ATR entsprach. In der Praxis filterte das BTC in der Tokyo-Session fast durchgaengig raus - BTC bildet dort oft sehr enge, aber technisch valide Boxen.
- **Entscheidung:** Schwellwert von 1.0 auf 0.6 gesenkt
- **Alternativen:** 0.5 (zu permissiv, auch wirklich noise-hafte Boxen durchgelassen), 0.8 (weniger Faelle, noch einige Tokyo BTC weggefiltert), 1.0 belassen (zu wenige Trades, Tokyo BTC de facto ausgesperrt)
- **Begruendung:** 0.6 entspricht einer Box, die 60% des ATR abdeckt - das ist eng, aber nicht rauschig. Tokyo BTC bildet strukturell engere Boxen als EU/US, weil weniger Volumen und Aktivitaet. Den Filter fuer alle Sessions pauschal auf 1.0 zu setzen ignoriert diese Realitaet.
- **Merke:** Session-spezifische Volatilitaetsmuster beeinflussen die Box-Qualitaet. Ein einheitlicher ATR-Ratio-Schwellwert fuer alle Sessions kann bestimmte Sessions systematisch ausschliessen, ohne dass die Setups schlechter sind.

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

*Letzte Aktualisierung: 2026-04-01*
