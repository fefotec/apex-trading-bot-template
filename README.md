# APEX Trading Bot Template

Öffentlicher, bereinigter Doku-Snapshot des privaten APEX-Trading-Bots.

Dieses Repo ist **kein 1:1-Live-Mirror**, sondern ein technischer Template-/Dokustand:
- keine Secrets
- keine Live-Daten
- keine produktionsspezifischen Server-Details
- Fokus auf Architektur, Guardrails und Script-Aufbau

## Überblick

APEX handelt primär **Opening Range Breakouts (ORB)** auf Hyperliquid Perpetuals.

Aktueller strategischer Stand:
- Wochentags: Tokyo, Europa und USA Session
- Assets: `BTC`, `SOL`, `AVAX`
- `ETH` ist aus dem aktiven ORB-Set entfernt
- Tokyo ist auf `BTC` begrenzt
- Zusätzlich existiert eine Wochenend-Strategie `WeekendMomo` für `AVAX`

Risikoregeln:
- max. `1` Trade pro Session
- ca. `2%` Risiko pro Trade
- Kill-Switch bei tiefem Drawdown

## Was dieses Repo zeigt

- wie der Bot logisch aufgebaut ist
- welche Scripts welche Rolle haben
- welche Schutzmechanismen vor Live-Trades greifen
- welche Daten-Dateien für Journal, P&L und Kapital-Tracking genutzt werden

## Was sich architektonisch geändert hat

Der aktuelle Live-Stand ist robuster als frühe öffentliche Snapshots:

- Schutz-Gates laufen **fail-closed**
  Wenn Regime-, Market-, Candle- oder Spread-Checks fehlschlagen, wird nicht blind weitergetradet.
- Exit-Logging läuft über ein sauberes Journal-Modell
  Neue Trades arbeiten mit `trade_id`, `log_version` und `status`.
- `pnl_tracker.json` wird aus den echten geschlossenen Trades rekonstruiert
  Nicht mehr nur inkrementell hochgezählt.
- Einzahlungserkennung ist defensiver
  Verdächtige Einzahlungen landen als `suspected_deposits` zur manuellen Prüfung statt still das Startkapital zu verschieben.
- Order-Platzierung ist zentralisiert
  Die Trading-Session für SDK/Exchange wird wiederverwendet, statt bei jedem Schritt neu aufgebaut zu werden.
- Trailing-Kommunikation ist klarer
  Profit-Lock läuft live, ATR-Trailing wird weiterhin als Dry-Run evaluiert.

## Kern-Workflow

### 1. Opening Range erfassen
`save_opening_range.py`

- speichert High/Low der Opening-Range
- aktualisiert das Box-Archiv
- stößt ein Markt-/Regime-Update an

### 2. Breakout prüfen
`autonomous_trade.py`

- scannt die freigegebenen Assets
- prüft ORB-Setup, ATR-Threshold, Candle-Close und Spread
- blockt Trades bei schlechtem Tages-Regime
- platziert Entry, SL und TP

### 3. Position überwachen
`position_monitor.py`

- erkennt echte Closings
- matched Exits auf offene Journal-Trades
- zieht den Profit-Lock nach
- räumt verwaiste Orders auf
- synchronisiert den P&L-Tracker

### 4. Wochenend-Setup
`weekend_momo.py`

- prüft Freitags das Momentum
- eröffnet Samstags optional eine AVAX-Position
- schließt Sonntags sauber gegen den ursprünglichen Entry-Trade

## Datenmodell

Wichtige Dateien im Live-System:
- `trades.json` für Entry-/Exit-Journal
- `pnl_tracker.json` für aggregierte Stats
- `capital_tracking.json` für Startkapital, Ein-/Auszahlungen und Review-Fälle
- `opening_range_boxes.json` für aktuelle ORB-Boxen
- `market_regime.json` für Tages-Regime und Bias

## Automation

Die produktive Ausführung läuft heute über **System-Cron + Python-Skripte**.

Wichtig:
- nicht mehr über OpenClaw-Scheduling
- keine Trading-Entscheidungen in OpenClaw
- die Python-Skripte sind die produktive Entscheidungs- und Ausführungsschicht

## Sicherheit

- keine Keys im Repo
- keine Live-Wallets im Public Template
- keine echten Produktivdaten
- Fokus auf nachvollziehbare Guardrails statt Marketing

## Setup

Beispiel-Dateien:
- `config/.env.hyperliquid.example`
- `config/.env.telegram.example`

Typischer Startpunkt:
```bash
python3 scripts/pre_market.py eu
python3 scripts/save_opening_range.py eu
python3 scripts/autonomous_trade.py eu
python3 scripts/position_monitor.py
```

## Dokumente

- `PROJEKT.md` erklärt Architektur und Entscheidungslogik
- `CHANGELOG.md` hält größere Entwicklungsstände fest
- `ERKENNTNISSE.md` sammelt Learnings
- `FORTSCHRITT.md` ist im Public Repo nur als bereinigte Referenz zu verstehen

## Hinweis

Wenn du den echten Live-Bot nachbauen willst, reicht dieses Repo allein nicht aus.
Es dokumentiert den Ansatz, aber nicht die komplette private Betriebsumgebung.
