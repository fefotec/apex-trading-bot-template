# TODO - APEX Trading Bot

## Hoch 🔴

- [x] Capital.com Account erstellt (31.03.2026, Verifizierung laeuft)
- [x] Capital.com API Key generiert + Live-Verbindung getestet (31.03.2026)
- [x] `.env.capitalcom` auf Server angelegt + Gold-Preis abrufbar (31.03.2026)
- [ ] Capital.com Verifizierung abwarten + Geld einzahlen
- [ ] Capital.com Demo-Test oder erster Mini-Trade mit Live-Konto
- [ ] Python venv auf Server reparieren (linuxbrew Python 3.14 fehlt)
- [ ] Pruefen ob WeekendMomo Cron Jobs korrekt im OpenClaw Scheduling laufen
- [ ] 30-Tage Testphase auswerten (bis 24.04.2026)
- [x] Profitabilitaets-Analyse inkl. Fees erstellen → Finanzamt-Auswertung im Dashboard implementiert (01.04.2026)
- [x] Kill-Switch implementieren (50% Drawdown → Pause + Benachrichtigung) → bereits in autonomous_trade.py

## Mittel 🟡

- [ ] Position Close-Button testen (Hyperliquid + Bitget) — Close via Dashboard, Bestaetungs-Modal, reduce_only Order + Dashboard-Refresh pruefen
- [ ] REVIEW: Gold-Strategie nach 10+ Trades pruefen (30m Range vs 60m, Doppel-Confirmation, Break-Even Stop) -- Reminder setzen via ClawdBot!
- [ ] Capital.com Cron Jobs einrichten (London Open 09:30 Berlin, Breakout-Checks ab 09:45, OpenClaw Scheduling)
- [ ] Capital.com erstes Live-Trading auswerten (nach Demo-Phase)
- [x] Alte OKX Scripts lokal loeschen → komplett entfernt (01.04.2026)
- [ ] WeekendMomo Cron Jobs auf ClawdBot einrichten (Fr 23:00, Sa 00:05 UTC, So 21:00)
- [ ] WeekendMomo erstes Live-Wochenende auswerten
- [ ] Slippage-Erfahrungen dokumentieren (ERKENNTNISSE.md)
- [ ] Typische Spreads pro Asset erfassen
- [x] Position Monitor Intervall verkuerzen → auf 2 Min (01.04.2026)
- [ ] Exit-Strategie nach 10+ Live-Trades auswerten (Split-TP Effekt messen: TP1-Hitrate vs. TP2-Hitrate)
- [x] Git Pull auf VPS einrichten → funktioniert via SSH git fetch+reset (01.04.2026)

## Niedrig 🟢

- [ ] Statistische Auswertung nach 20+ Trades
- [ ] Pattern-Analyse (welche Setups performen am besten)
- [ ] Tages-Analyse (welche Wochentage sind am besten)
- [ ] Backtest-Framework aufbauen

## Erledigt ✅

- [x] Capital.com Gold-Integration Code geschrieben - Phase 1 komplett (capitalcom_*.py) (2026-03-30)
- [x] OKX EU-Sperre erkannt und dokumentiert, Wechsel zu Capital.com vollzogen (2026-03-30)
- [x] OKX Gold-Integration Code geschrieben - Phase 1 (obsolet, durch Capital.com ersetzt) (2026-03-30)
- [x] Hyperliquid SDK installiert & getestet (2026-03-24)
- [x] Autonome Trading-Scripts deployed (2026-03-24)
- [x] 12 Cron Jobs konfiguriert - EU + US Sessions (2026-03-24)
- [x] P&L Tracking implementiert (2026-03-24)
- [x] Erster vollautomatischer Trade (2026-03-25)
- [x] Tokyo-Session hinzugefuegt (2026-03-26)
- [x] GitHub Auto-Pull via n8n + Cloudflare Tunnel eingerichtet (2026-03-27)
- [x] Telegram DevOps Bot (@your_devops_bot) fuer Notifications (2026-03-27)
- [x] WeekendMomo-Strategie Script erstellt (weekend_momo.py) (2026-03-27)
- [x] Position Monitor Bug gefixt: Alle geschlossenen Positionen benachrichtigen, nicht nur die neueste (2026-03-31)
- [x] Krypto-optimierte Exit-Strategie: Split-TP (1:1 + 3:1), ATR-Trailing ab 4% Profit, BE-Schwelle auf 3% angehoben (2026-03-31)
- [x] MIN_BOX_ATR_RATIO auf 0.6 gesenkt (Tokyo BTC Box-Filter war zu konservativ, filterte valide Boxen raus) (2026-04-01)
- [x] session_summary.py: ATR-basierte Auswertung + korrekter "Box zu eng" Status + Spot+Margin Balance (2026-04-01)
- [x] daily_closeout.py: Balance-Anzeige auf Spot+Margin umgestellt (2026-04-01)
- [x] save_opening_range.py: Box-Archiv (box_archive.json) eingefuehrt (2026-04-01)
- [x] monitor.py: SL-Trailing von MOCK auf echte Hyperliquid-Anbindung umgestellt (2026-04-01)
