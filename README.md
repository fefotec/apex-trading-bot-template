# APEX Trading Bot 🚀

**Opening Range Breakout (ORB) Strategy** für Hyperliquid Perpetuals (BTC, ETH, SOL, AVAX)

---

## 📊 Überblick

Automatisierter Trading-Bot der auf **Opening Range Breakouts** in 3 Sessions/Tag tradet:
- **Tokyo Session:** 02:00 - 03:30 Berlin Time
- **Europa Session:** 09:00 - 10:30 Berlin Time  
- **USA Session:** 21:30 - 22:45 Berlin Time

**Max 1 Trade pro Session** - konservativer Ansatz mit 2:1 Risk/Reward Ratio.

---

## 🎯 Performance

- **Startkapital:** $2,300.54 USDC (24.03.2026)
- **Aktuelles P&L:** Siehe `FORTSCHRITT.md`
- **Watchlist:** BTC > ETH > SOL > AVAX (nach Liquidität)

---

## 🛠 Tech Stack

- **Platform:** Hyperliquid (Non-Custodial DEX)
- **Agent:** OpenClaw isolated agent mit Gemini Flash
- **Scripts:** Python 3
- **Notifications:** Telegram Bot (direkt via HTTP)
- **Automation:** OpenClaw Cron Jobs

---

## 📁 Struktur

```
apex-trading/
├── scripts/              # Trading-Scripts
│   ├── pre_market.py        # Pre-Market Setup
│   ├── save_opening_range.py # Opening Range speichern
│   ├── autonomous_trade.py   # Breakout-Check & Trade-Execution
│   ├── position_monitor.py   # Position-Monitoring
│   ├── session_summary.py    # Session-Summary Report
│   └── telegram_sender.py    # Telegram-Benachrichtigungen
├── config/               # Config & Credentials (NICHT IN GIT!)
│   └── .env.hyperliquid.example
├── data/                 # Trading-Daten
│   ├── trades/              # Trade-History
│   ├── positions/           # Position-Tracking
│   └── sessions/            # Session-Logs
├── PROJEKT.md           # Projekt-Dokumentation
├── FORTSCHRITT.md       # Trading-Log & P&L
├── ERKENNTNISSE.md      # Lessons Learned
├── UMBAU-PLAN.md        # Isolierter Agent Setup
└── README.md            # Diese Datei
```

---

## ⚙️ Setup

### 1. Credentials

Erstelle `config/.env.hyperliquid`:
```bash
HYPERLIQUID_PRIVATE_KEY=your_private_key_here
HYPERLIQUID_WALLET=0xYourWalletAddress
```

Erstelle `.env.telegram`:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 2. Dependencies

```bash
pip install requests python-dotenv
```

### 3. Test

```bash
# Balance checken
python3 scripts/position_monitor.py

# Pre-Market Setup testen
python3 scripts/pre_market.py eu
```

---

## 🤖 Automation

Der Bot läuft über **OpenClaw Cron Jobs** (alle via isolated agent `apex-trading`).

**Session-Schedule (Mo-Fr):**
- 02:00: Tokyo Opening Range Start
- 02:15-03:30: Tokyo Breakout-Checks (4x)
- 09:00: EU Opening Range Start
- 09:15-10:30: EU Breakout-Checks (4x)
- 21:30: US Opening Range Start
- 21:45-22:45: US Breakout-Checks (4x)

**Position Monitor:** Alle 30 Min (auto on/off bei offenen Positionen)

---

## 📊 Trading-Logik

### Opening Range Breakout (ORB)
1. **Pre-Market:** 30 Min vorher Setup
2. **Opening:** 15 Min Opening Range festlegen (High/Low)
3. **Breakout:** Preis bricht über High (LONG) oder unter Low (SHORT)
4. **Entry:** Sofort Market Order
5. **Stop-Loss:** Unterhalb Box (dynamisch)
6. **Take-Profit:** 2:1 R/R automatisch

### Asset-Priorisierung
Bei mehreren gleichzeitigen Breakouts → Trade nur das Asset mit höchster Liquidität:
1. BTC-PERP (beste Liquidität)
2. ETH-PERP
3. SOL-PERP
4. AVAX-PERP

---

## 📈 Performance-Tracking

Alle Trades werden in `FORTSCHRITT.md` dokumentiert:
- Entry/Exit Prices
- P&L ($ und %)
- Win/Loss
- Session (Tokyo/EU/US)

**Capital Tracking:** `data/capital_tracking.json` - trackt Einzahlungen für korrektes P&L

---

## 🔐 Security

- **Private Keys:** Niemals in Git committen!
- **Read-Only Monitoring:** Scripts nutzen nur Public API wo möglich
- **Non-Custodial:** Funds bleiben auf deiner Wallet (Hyperliquid)

---

## 📝 Dokumentation

- **PROJEKT.md** - Vollständige Projekt-Doku
- **FORTSCHRITT.md** - Alle Trades & Erkenntnisse
- **ERKENNTNISSE.md** - Lessons Learned & Optimierungen
- **UMBAU-PLAN.md** - Isolated Agent Migration

---

## 🚀 Next Steps

- [ ] 30-Tage Testphase (bis 24.04.2026)
- [ ] Profitabilitäts-Analyse inkl. Fees
- [ ] Hybrid-Strategie testen (Woche 2)
- [ ] Wochenend-Trading evaluieren

---

## 📞 Support

Bei Fragen: Siehe `PROJEKT.md`

---

**⚡ APEX - Always Profitable, Extremely Xciting!**
