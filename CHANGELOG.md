# Changelog

Alle wichtigen Aenderungen am APEX Trading Bot.

---

## 2026-04-19

### Documentation
- **Public template refreshed:** README und PROJEKT spiegeln jetzt den aktuellen Architektur-Stand als bereinigten Doku-Snapshot wider.
- **Public/private boundary clarified:** Das Template ist jetzt explizit als Dokumentations-Repo beschrieben, nicht als 1:1-Live-Mirror.

### Architecture
- **Aktiver ORB-Stand dokumentiert:** BTC, SOL und AVAX aktiv; ETH entfernt; Tokyo nur BTC.
- **Execution path aktualisiert:** System-Cron + Python-Skripte dokumentiert statt OpenClaw-Scheduling.
- **WeekendMomo ergaenzt:** Wochenend-Strategie als eigener Lifecycle im Oeffentlichkeitsstand beschrieben.

### Hardening
- **Fail-Closed Gates dokumentiert:** Regime-, Market-, Candle- und Spread-Checks blocken Trades bei Fehlern.
- **Trade-Journal dokumentiert:** `trade_id`, `log_version` und `status` als Grundlage fuer sauberes Entry-/Exit-Matching erwaehnt.
- **P&L-Rebuild dokumentiert:** Aggregierte Kennzahlen werden aus geschlossenen Trades rekonstruiert.
- **Deposit-Review dokumentiert:** Balance-Spruenge werden als `suspected_deposits` zur manuellen Pruefung markiert.
- **Order-Layer dokumentiert:** Wiederverwendete SDK-/Exchange-Initialisierung statt mehrfacher Re-Initialisierung.

## 2026-04-05

### Features
- **Dynamische Asset-Prioritaet:** Assets werden nach Win-Rate der letzten 20 Trades sortiert. Bessere Coins werden zuerst gescannt und bevorzugt getradet. Coins mit weniger als 3 Trades behalten ihren Default-Platz.
- **Rest-Positions-Erkennung:** 3 Sicherheitsstufen gegen "versteckte" alte Positionen ohne SL/TP:
  1. Vor Trade: Exchange pruefen ob Coin frei ist
  2. Nach Close: Verifizieren ob Position wirklich weg ist
  3. Laufend: Rest erkennen wenn Size > erwartet, automatisch schliessen

### Fixes
- **Max-Leverage 5x auf 25x erhoeht:** Bei engen BTC-Boxen war die Position zu gross fuer 5x, Trade wurde abgelehnt. 25x ist sicher da SL das echte Risiko auf 2% begrenzt.
- **Minimale Box-Groesse 0.2% vom Preis:** AVAX-Boxen von $0.01 bei $9 (= 0.11%) rutschten durch den ATR-Filter wegen Rundung. Neuer absoluter Filter verhindert Trades auf Noise.
- **Deposit-Erkennung:** Early Return bei "idle" verhinderte Erkennung. Schwellwert auf $500 erhoeht, 30-Min-Puffer nach Trade-Close.
- **Log-Ausgabe:** 4 Nachkommastellen fuer kleine Assets (AVAX, SOL) statt 2.

### Backtesting
- Eigenes Python-Backtest-Script mit exakter Live-Logik (nicht Freqtrade)
- 6 Monate Binance-Daten (Okt 2025 - Apr 2026)
- Ergebnis: EU Session profitabel (+$1.609), Tokyo Session unprofitabel (-$3.864)

---

## 2026-04-03

### Features
- **Trade-Auswertung fuer Finanzamt:** Neuer Menuepunkt im Dashboard mit Zeitraum-Filter, Summary-Karten (Netto P&L, Fees, Win-Rate), Trade-Tabelle, CSV/PDF-Export. Funktioniert fuer Hyperliquid und Bitget.
- **Position schliessen per Button:** Close-Button im Dashboard mit Bestaetigungs-Dialog. Hyperliquid via SSH, Bitget via API.
- **Box-Archiv:** Opening Range Boxen werden vor dem Ueberschreiben in `box_archive.json` archiviert (max 200 Eintraege).

### Fixes
- **Lock-Marker:** Zeigt jetzt den Trigger-Preis (+3% Profit), wird ausgeblendet wenn hinter TP.
- **Balance-Anzeige:** Spot + Margin in Session Summary und Daily Closeout.

---

## 2026-04-01

### Features
- **SL-Trailing scharf geschaltet:** Ab +3% Profit wird SL auf Entry +1% nachgezogen (position_monitor.py). ATR-Trail als Dry-Run Logging.
- **Session Summary synchronized:** Gleiche ATR-basierte Breakout-Logik wie autonomous_trade.py.

### Fixes
- **MIN_BOX_ATR_RATIO 1.0 auf 0.6 gesenkt:** BTC Tokyo Sessions wurden fast immer als "Box zu eng" gefiltert.
- **Preis-Rundung:** Auf offizielle Hyperliquid SDK-Logik umgestellt.
- **OKX komplett entfernt:** EU-Sperre, Gold laeuft ueber Capital.com.
- **monitor.py entfernt:** Logik in position_monitor.py integriert.

---

## 2026-03-31

### Features
- **Split Take-Profit:** 50% bei 1:1 R:R (TP1), 50% bei 3:1 R:R (TP2 Runner).
- **ATR-basiertes Trailing:** Ab 4% Profit, 2x ATR Abstand.
- **Break-Even entschaerft:** SL erst ab 3% Profit auf +1% (statt 1% auf Break-Even). Verhindert Rauswurf durch Krypto-Liquidity-Grabs.

---

## 2026-03-30

### Features
- **ATR-basierte Breakout-Thresholds:** Statt fester $50 wird 0.5x ATR(14, 15m) als Threshold genutzt.
- **Candle-Close Confirmation:** Letzte 5m-Kerze muss ausserhalb der Box schliessen.
- **Spread-Check:** Trade wird uebersprungen wenn Spread > 0.1%.
- **Capital.com Gold-Integration:** 5 neue Scripts fuer XAUUSD CFD Trading (noch nicht live).

---

## 2026-03-24 - 2026-03-27

- Erster vollautomatischer Trade (25.03.)
- Hyperliquid SDK Integration
- 3 Sessions: Tokyo, EU, US
- Telegram Bot Notifications
- Position Monitor mit Orphan-Order Cleanup
- WeekendMomo Strategie (AVAX, Wochenende)
