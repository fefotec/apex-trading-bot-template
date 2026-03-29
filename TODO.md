# TODO - APEX Trading Bot

## Hoch 🔴

- [ ] Python venv auf Server reparieren (linuxbrew Python 3.14 fehlt)
- [ ] Pruefen ob WeekendMomo Cron Jobs korrekt im OpenClaw Scheduling laufen
- [ ] 30-Tage Testphase auswerten (bis 24.04.2026)
- [ ] Profitabilitaets-Analyse inkl. Fees erstellen
- [ ] Kill-Switch implementieren (50% Drawdown → Pause + Benachrichtigung)

## Mittel 🟡

- [ ] WeekendMomo Cron Jobs auf ClawdBot einrichten (Fr 23:00, Sa 00:05 UTC, So 21:00)
- [ ] WeekendMomo erstes Live-Wochenende auswerten
- [ ] Slippage-Erfahrungen dokumentieren (ERKENNTNISSE.md)
- [ ] Typische Spreads pro Asset erfassen
- [ ] Position Monitor optimieren (aktuell alle 30 Min)

## Niedrig 🟢

- [ ] Statistische Auswertung nach 20+ Trades
- [ ] Pattern-Analyse (welche Setups performen am besten)
- [ ] Tages-Analyse (welche Wochentage sind am besten)
- [ ] Backtest-Framework aufbauen

## Erledigt ✅

- [x] Hyperliquid SDK installiert & getestet (2026-03-24)
- [x] Autonome Trading-Scripts deployed (2026-03-24)
- [x] 12 Cron Jobs konfiguriert - EU + US Sessions (2026-03-24)
- [x] P&L Tracking implementiert (2026-03-24)
- [x] Erster vollautomatischer Trade (2026-03-25)
- [x] Tokyo-Session hinzugefuegt (2026-03-26)
- [x] GitHub Auto-Pull via n8n + Cloudflare Tunnel eingerichtet (2026-03-27)
- [x] Telegram DevOps Bot (@fefotec_devops_bot) fuer Notifications (2026-03-27)
- [x] WeekendMomo-Strategie Script erstellt (weekend_momo.py) (2026-03-27)
