# APEX - Projektüberblick

> Öffentlicher Architektur- und Doku-Stand. Bereinigt, nicht identisch zur privaten Produktivinstanz.

## Mission

APEX ist ein skriptgesteuerter Trading-Bot für Hyperliquid Perpetuals.
Das Ziel ist nicht maximale Aktivität, sondern kontrollierte Teilnahme:

- wenige Trades
- klare Session-Logik
- harte Schutzfilter
- nachvollziehbares Trade-Journal

## Aktueller Strategie-Stand

### Wochentags: Opening Range Breakout

Sessions:
- Tokyo
- Europa
- USA

Aktive Assets:
- `BTC`
- `SOL`
- `AVAX`

Einschränkungen:
- `ETH` ist aus dem aktiven ORB-Handel entfernt
- Tokyo ist auf `BTC` begrenzt

Grundidee:
- Opening Range erfassen
- Breakout nur außerhalb klar definierter Boxen handeln
- nur dann handeln, wenn Marktregime, Candle-Close und Spread passen

### Wochenende: WeekendMomo

Zusatzstrategie:
- Momentum-basierter Wochenend-Trade auf `AVAX`
- eigener Entry-/Exit-Lebenszyklus
- Exit wird dem ursprünglichen Entry-Trade sauber zugeordnet

## Risikomodell

- max. `1` Trade pro Session
- ca. `2%` Risiko pro Trade
- Kill-Switch bei großem Drawdown
- Positionen werden nicht ungesichert offen gelassen, wenn SL/TP-Platzierung fehlschlägt

## Produktionslogik

Die private Live-Instanz läuft über Python-Skripte und System-Cron.

Wichtig:
- OpenClaw trifft keine Trading-Entscheidungen mehr
- die Python-Skripte sind die produktive Logik
- Ausführung und Überwachung sind getrennt

## Script-Rollen

### `save_opening_range.py`
- speichert die Opening-Range pro Session
- archiviert alte Boxen
- aktualisiert Markt-/Regime-Snapshot

### `autonomous_trade.py`
- scannt Breakouts
- wendet Session-Whitelist und Priorisierung an
- blockt Trades bei fehlerhaften oder negativen Guardrails
- eröffnet Positionen und platziert Schutzorders

### `place_order.py`
- zentrale Order-Schicht
- bündelt Preis-/Size-Rundung
- nutzt wiederverwendete SDK-/Exchange-Initialisierung
- reduziert unnötige Re-Initialisierung zwischen Entry, SL und TP

### `position_monitor.py`
- erkennt geschlossene Positionen
- matched Exits auf offene Journal-Einträge
- führt Profit-Lock live aus
- hält P&L-Tracking und Orphan-Cleanup konsistent

### `weekend_momo.py`
- verwaltet die Wochenendstrategie getrennt
- schreibt in dasselbe Journal-Modell

## Guardrails

Der aktuelle Stand setzt auf mehrere defensive Ebenen:

### Fail-Closed Gates

Wenn ein zentraler Filter fehlschlägt, wird der Trade blockiert:
- Tages-Regime
- Market-Filter
- Candle-Close-Bestätigung
- Spread-Check

### Journal statt losem Logging

Neuere Trades arbeiten mit:
- `trade_id`
- `log_version`
- `status`

Dadurch lassen sich Exits zuverlässiger auf den richtigen Entry zurückschreiben.

### Deterministisches P&L

`pnl_tracker.json` wird aus den geschlossenen Journal-Trades rekonstruiert.
Das verhindert Drift zwischen Einzeltrades und aggregierten Kennzahlen.

### Defensive Einzahlungserkennung

Verdächtige Balance-Sprünge werden nicht automatisch als neues Startkapital verbucht.
Sie landen als Review-Fälle in `suspected_deposits`.

### Klare Trailing-Semantik

- Profit-Lock läuft live
- ATR-Trailing wird weiterhin nur als Dry-Run ausgewertet

## Daten-Dateien

Wichtige Datenobjekte im privaten System:

- `trades.json`
  Entry-/Exit-Journal
- `pnl_tracker.json`
  Aggregierte Kennzahlen
- `capital_tracking.json`
  Startkapital, Einzahlungen, Review-Fälle
- `opening_range_boxes.json`
  Aktive Session-Boxen
- `market_regime.json`
  Bias und Asset-Freigaben

## Öffentliche Repo-Grenze

Dieses Repo ist absichtlich begrenzt:

- keine privaten Wallet-Daten
- keine Server-Zugangsdaten
- keine produktiven Logs
- keine 1:1-Garantie auf jeden aktuellen Implementierungsstand

Es soll nachvollziehbar machen, **wie** der Bot gebaut ist und **welche Probleme zuletzt gehärtet wurden**, nicht die komplette private Betriebsumgebung offenlegen.
