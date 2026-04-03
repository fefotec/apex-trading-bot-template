# APEX Trading - Fortschritt

## 2026-04-01 - Kritische Bugfixes + SL-Trailing + OKX Cleanup

### Bugfixes

**1. MIN_BOX_ATR_RATIO von 1.0 auf 0.6 gesenkt**
- Der alte Wert 1.0 filterte BTC Tokyo Sessions fast immer raus ("Box zu eng")
- Betrifft autonomous_trade.py, capitalcom_autonomous_trade.py

**2. session_summary.py komplett ueberarbeitet**
- Alte hardcodierte $50-Breakout-Logik durch ATR-basierte ersetzt (gleiche Filter wie autonomous_trade.py)
- Neuer Status "Box zu eng" statt irreführendem "Breakout erkannt, Grund: Unbekannt"
- Balance-Anzeige zeigt jetzt Spot + Margin (vorher nur Spot)

**3. daily_closeout.py: Balance auf Spot+Margin umgestellt**

**4. save_opening_range.py: Box-Archiv eingefuehrt**
- Boxen werden vor dem Ueberschreiben in `data/box_archive.json` gesichert (max. 200 Eintraege)

**5. Hyperliquid Preis-Rundung komplett umgebaut (KRITISCH)**
- Problem: Hardcoded Tick-Sizes waren alle falsch → `"Price must be divisible by tick size"` → Trade verpasst
- Fix: `round_price()` auf offizielle SDK-Logik umgestellt: `round(float(f"{px:.5g}"), 6 - szDecimals)`

**6. ASSET_RULES ImportError gefixt (KRITISCH)**

**7. BTC SHORT Trade manuell nachgeholt**
- Entry: $68,863 SHORT, Size: 0.20748
- SL: $69,274 / TP1: $68,452 (1:1) / TP2: $67,630 (3:1)

### Neue Features

**8. SL-Trailing in position_monitor.py integriert**
- Ab +3% Profit: SL wird auf Entry +1% nachgezogen (Profit-Lock)
- Telegram-Benachrichtigung bei SL-Nachzug
- Vorher: SL-Trailing war in separatem `monitor.py` das NIE im Cron lief

**9. ATR-Trail Dry-Run Logging**
- Ab +4% Profit: Loggt was ein ATR-Trailing-Stop tun wuerde (2x ATR Abstand)
- Keine echten Orders, nur Datensammlung

**10. Position Monitor auf 2-Minuten-Intervall**

### Cleanup

**11. OKX komplett entfernt** (5 Scripts + PLAN-GOLD-OKX.md)

**12. monitor.py entfernt** — Logik ist jetzt in position_monitor.py

### Hyperliquid Dashboard — neue Features

**13. Trade-Auswertung fuer Finanzamt (neuer Menüpunkt)**
- Zeitraum-Filter: Dieser/Letzter Monat, Dieses Jahr, Letzte 30 Tage, eigener Zeitraum
- Summary-Karten: Netto P&L, Fees (steuerlich absetzbar), Win-Rate, Avg Gewinn/Verlust
- Trade-Tabelle mit Brutto P&L, Fees und Netto P&L pro Trade inkl. Summenzeile
- CSV-Export (Semikolon-getrennt, Excel-kompatibel) + PDF-Export via Browser-Print
- Steuerhinweis: Perpetuals = Termingeschaefte §20 Abs. 2 EStG
- Funktioniert fuer Hyperliquid- und Bitget-User

**14. Position schliessen per Button**
- Close-Button (X) auf jeder PositionCard
- Bestaetungs-Modal mit Position-Details und aktuellem P&L
- Market-Order (reduce_only) zum sofortigen Schliessen
- Hyperliquid: SSH zum VPS → place_order.py | Bitget: direkt via API (close-positions Endpoint)
- Erfolgs-/Fehler-Feedback, Dashboard refresht automatisch nach Close

**15. Lock-Marker Fix in PriceRangeBar**
- Lock zeigt jetzt den Trigger-Preis (+3% Profit) statt den SL-Zielpreis
- Lock wird ausgeblendet wenn er hinter dem TP liegt (kann dann nie triggern)

---

## 2026-03-31 - Krypto-optimierte Exit-Strategie implementiert (Split-TP + ATR-Trailing + BE-Entschaerfung)

### Aenderungen

**1. Break-Even-Regel entschaerft (monitor.py)**
- Vorher: SL wurde ab 1% Profit auf Break-Even gezogen
- Neu: SL wird erst ab 3% Profit auf +1% gezogen
- Grund: Krypto-typische Liquidity Grabs haben Trades zu frueh ausgestoppt — der Preis tauchte kurz unter BE und loeste den SL aus, bevor er das TP erreichte

**2. Split Take-Profit eingefuehrt (autonomous_trade.py)**
- Vorher: Einzelner TP bei 2:1 R:R
- Neu: Zwei Teil-Exits
  - TP1: 50% der Position bei 1:1 R:R (sichert das eingesetzte Risiko)
  - TP2: 50% bei 3:1 R:R (der "Runner" fuer grosse Moves)
- Konsequenz: Trade ist nach TP1-Hit risikofrei, Runner laeuft bis TP2 oder Trailing

**3. ATR-basiertes Trailing aktiviert (monitor.py)**
- Vorher: Ab 50% des maximalen Profits fester SL-Zug
- Neu: Ab 4% Profit zieht der SL dynamisch mit 2x ATR Abstand nach
- Vorteil: Passt sich der aktuellen Volatilitaet an — bei ruhigen Maerkten enger, bei volatilen Maerkten weiter

---

## 2026-03-31 - Position Monitor Bug gefixt (mehrere gleichzeitige Closes)

### Problem
Wenn 2 Positionen gleichzeitig geschlossen werden (z.B. SOL Long + AVAX Short), wurde nur der neueste Trade per Telegram benachrichtigt. Der zweite Trade wurde komplett verschluckt — keine Telegram-Nachricht, kein Eintrag in trades.json, kein Update im pnl_tracker.

### Ursache
In `position_monitor.py` Zeile 225 wurde mit `sorted(...)[0]` nur der neueste Trade verarbeitet. Alle anderen Closes im selben Monitor-Zyklus wurden verworfen.

### Fix
Schleife ueber alle `closed_trades` statt nur `[0]`. Jeder Trade bekommt seine eigene Telegram-Nachricht, trades.json-Update und pnl_tracker-Update. Keine Gefahr von Doppel-Nachrichten, da der State (position_count) nach Verarbeitung auf 0 gesetzt wird und der naechste Lauf sofort mit "idle" beendet.

### Deployment
Fix per SCP direkt auf den Server kopiert (git pull funktioniert nicht wegen fehlender GitHub-Credentials auf dem VPS).

---

## 2026-03-30 - OKX gescheitert (EU-Sperre), Capital.com als Ersatz implementiert

### Ursache des Wechsels
- OKX sperrt ALLE Perpetuals und Gold-Instrumente fuer EU-Nutzer (MiCA Error 51155 "local compliance restrictions")
- USDT auf OKX in der EU komplett gesperrt - auch der OKX Convert Service hat kein USDT fuer EU-Konten
- Die urspruenglichen OKX Scripts (okx_*.py) und ccxt-Integration sind damit fuer Gold-Trading unbrauchbar

### Neue Implementierung: Capital.com
- Capital.com ist CySEC-reguliert und erlaubt EU-Nutzern XAUUSD als CFD zu handeln
- 5 neue Scripts fuer Capital.com geschrieben (Ersatz fuer die 5 okx_*.py Scripts):
  - `scripts/capitalcom_client.py` - Capital.com REST API Client (via `requests`, kein ccxt)
  - `scripts/capitalcom_place_order.py` - Order-Platzierung inkl. direktem SL/TP
  - `scripts/capitalcom_save_opening_range.py` - Gold Opening Range Capture (London Open)
  - `scripts/capitalcom_autonomous_trade.py` - Gold ORB Breakout Trading
  - `scripts/capitalcom_position_monitor.py` - Position Monitor
  - `config/.env.capitalcom.example` - Credentials-Template (in Git, ohne echte Werte)

### Architektur-Unterschiede Capital.com vs. OKX
- SL/TP direkt bei der Position gesetzt (kein separates SL/TP Placement noetig)
- Kein Orphan-Cleanup noetig (Capital.com bindet SL/TP an die Position)
- Gold-Symbol: "GOLD" (Capital.com Epic) statt "XAU/USDT:USDT"
- Datei-Namen angepasst: `gold_opening_range_boxes.json`, `gold_monitor_state.json`, `gold_capital_tracking.json` (ohne okx_ prefix)

### Status
- Alte OKX Scripts noch lokal vorhanden, vom Server entfernt
- Capital.com Account noch nicht erstellt, API Keys noch ausstehend
- ccxt nicht mehr benoetigt (nur noch `requests` fuer Capital.com)

---

## 2026-03-30 - OKX Gold-Integration (Phase 1) implementiert

### Code-Stand
- 5 neue Scripts fuer OKX/XAUUSD geschrieben (analog zur Hyperliquid-Architektur)
- Bestehende Hyperliquid-Scripts wurden nicht veraendert

### Neue Dateien
- `scripts/okx_client.py` - OKX API Client via ccxt (analog zu hyperliquid_client.py)
- `scripts/okx_place_order.py` - Order-Platzierung auf OKX
- `scripts/okx_save_opening_range.py` - Gold Opening Range Capture (London Open 09:00-11:00 Berlin)
- `scripts/okx_autonomous_trade.py` - Gold ORB Breakout Trading
- `scripts/okx_position_monitor.py` - OKX Position Monitor
- `config/.env.okx.example` - OKX API Credentials Template

### Strategie-Details
- Asset: XAUUSD (Gold Spot/Futures)
- Session: London Open 09:00-11:00 Berlin (einzige Session)
- Spread-Limit: 0.05% (strenger als Krypto-Threshold 0.1%)
- Daten: Separate JSON-Dateien (okx_*.json), Trades laufen in trades.json mit `exchange: "okx"`

### Noch NICHT live
- OKX Account muss noch erstellt werden
- API Keys noch nicht vorhanden
- ccxt auf Server noch nicht installiert
- Keine Cron Jobs eingerichtet
- Noch kein Testnet-Test durchgefuehrt

---

## 2026-03-26 - Drei Sessions, Ein Trade

### Trading Sessions

**Tokyo-Session (02:00-03:30):**
- Status: ⏸️ Kein Trade (keine validen Breakouts)

**EU-Session (09:00-10:30):**
- Status: ⏸️ Kein Trade (keine validen Breakouts)

**US-Session (21:30-23:00):**
- Status: ✅ **TRADE AUSGEFÜHRT!**
- Opening Range Boxen:
  - BTC: $69,057 - $69,343
  - ETH: $2,064.90 - $2,077.30
  - SOL: $86.36 - $86.83
  - AVAX: $9.10 - $9.14

**Trade #2: BTC SHORT** ✅
- **Time:** 22:00 (30 Min nach US Open)
- **Entry:** $68,942 (Breakout -$115 unter Box Low)
- **Size:** 0.11206 BTC
- **Stop-Loss:** $69,353 (Risk: $46)
- **Take-Profit:** $68,120 (Reward: $92, R:R 2:1)
- **Status:** 🟢 LÄUFT (23:00 noch offen)
- **Unrealized P&L:** +$2.91

### Balance
- Start (21:00): $2,335.39
- End (23:00): $2,343.45
- Change: +$8.06
- Open Position: +$2.91 unrealized

### P&L Gesamt
- Realized (heute): +$8.06
- Unrealized: +$2.91
- **Gesamt seit Start:** +$42.91 (+1.87%)

### Win-Rate
- Trades: 2 (beide laufend)
- Wins: TBD
- Losses: 0
- Win-Rate: TBD

### Milestones
- [ ] $500 Gewinn → +$500 Kapital
- [ ] $1,000 Gewinn → +$500 Kapital
- [ ] $1,500 Gewinn → +$500 Kapital

### Nächste Session
**Morgen 02:00:** Tokyo Opening Range Start
**Morgen 08:30:** EU Pre-Market Check

---

## 2026-03-25 - Erster Vollautomatischer Trade! 🚀

### Trading Sessions

**EU-Session (09:00-10:30):**
- Status: ⏸️ Kein Trade (keine validen Breakouts)

**US-Session (21:30-23:00):**
- Status: ✅ **TRADE AUSGEFÜHRT!**
- Opening Range Boxen:
  - BTC: $70,605 - $70,776
  - ETH: $2,158.60 - $2,167.40
  - SOL: $91.10 - $91.32
  - AVAX: $9.62 - $9.67

**Trade #1: BTC LONG** ✅
- **Time:** 21:45 (15 Min nach US Open)
- **Entry:** $70,920 (Breakout +$154 über Box High)
- **Size:** 0.13711 BTC (~$9,724)
- **Stop-Loss:** $70,595 (Risk: $46)
- **Take-Profit:** $71,570 (Reward: $92, R:R 2:1)
- **Status:** 🟢 LÄUFT (23:00 noch offen)
- **Unrealized P&L:** +$12.34

### Balance
- Start (21:00): $2,335.83
- End (23:00): $2,343.82
- Change: +$7.99
- Open Position: +$12.34 unrealized

### P&L Gesamt
- Realized: +$7.99 (inkl. Fees)
- Unrealized: +$12.34
- Total: +$20.33

### Win-Rate
- Trades: 1 (laufend)
- Wins: TBD
- Losses: 0
- Win-Rate: TBD

### Milestones
- [ ] $500 Gewinn → +$500 Kapital
- [ ] $1,000 Gewinn → +$500 Kapital
- [ ] $1,500 Gewinn → +$500 Kapital

### Nächste Session
**Morgen 02:00:** Tokyo Opening Range Start
**Morgen 08:30:** EU Pre-Market Check

---

## 2026-03-24 - Erste Vollautonome Session

### System Status
✅ **Vollautonomes Trading System aktiviert**
- SDK installiert & getestet
- Autonome Scripts deployed
- 12 Cron Jobs konfiguriert (EU + US Sessions)

### Trading Sessions

**EU-Session (09:00-10:30):**
- Status: ❌ Verpasst (Setup noch nicht fertig)
- Missed Opportunity: BTC fiel auf $70,034 (Breakout verpasst)
- Lesson: System war noch nicht scharf

**US-Session (21:30-23:00):**
- Status: ✅ Vollautomatisch überwacht
- Opening Range Boxen:
  - BTC: $69,382 - $70,299
  - ETH: $2,119 - $2,154
  - SOL: $88,73 - $90,14
  - AVAX: $9,41 - $9,57
- Checks: 6 automatische Scans
- Trades: 0 (keine validen Breakouts)
- Note: SOL brach aus (+0,24%) aber unter 2% Threshold = korrekt kein Trade

### Test-Trades (manuell)
1. **BTC Long Test**
   - Entry: $69,947 (0.00015 BTC)
   - Exit: $69,570
   - P&L: -$0,06 (Gebühren)
   - Purpose: System-Test ✅

### Balance
- Start: $2.300,54
- End: $2.300,32
- Change: -$0,22 (Test-Gebühren)

### P&L Gesamt
- Realized: -$0,22
- Unrealized: $0,00
- Total: -$0,22

### Win-Rate
- Trades: 0 (Test nicht gezählt)
- Wins: 0
- Losses: 0
- Win-Rate: N/A

### Milestones
- [ ] $500 Gewinn → +$500 Kapital
- [ ] $1,000 Gewinn → +$500 Kapital
- [ ] $1,500 Gewinn → +$500 Kapital

### Nächste Session
**Morgen 08:30:** EU Pre-Market Check
**Morgen 09:00:** EU Opening Range Start

---

## System Performance

**Code-Änderungen heute:**
1. Hyperliquid SDK installiert
2. place_order.py erstellt (Market + Stop-Loss)
3. save_opening_range.py erstellt
4. autonomous_trade.py erstellt
5. Alle Cron Jobs auf autonome Scripts umgestellt
6. P&L Tracking implementiert

**Learnings:**
- System funktioniert wie designed
- Threshold-Detection korrekt
- Keine False-Positives
- Bereit für echte Trades morgen

**Status:** 🟢 **SCHARF & BEREIT**
