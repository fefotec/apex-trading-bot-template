#!/usr/bin/env python3
"""
APEX - Main Runner
==================
Der Hauptprozess der um 21:25 Berlin startet und den ORB-Trade managed.

Ablauf:
1. 21:25 - Startup, Checks
2. 21:30 - Opening Range Start (15-Min-Kerze)
3. 21:45 - Box finalisieren, Breakout-Watch
4. 21:45+ - Auf gültigen Breakout warten
5. Bei Entry - Monitor-Loop starten (60-Sek)
6. 23:00 - Daily Summary
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple
import pytz

# Add scripts to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hyperliquid_client import HyperliquidClient
from orb_strategy import ORBStrategy, SetupType, Direction
from alerts import AlertSystem

# Config
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(PROJECT_DIR, "data", "daily_state.json")
TRADE_LOG = os.path.join(PROJECT_DIR, "data", "trades")

# Timezone
NY_TZ = pytz.timezone("America/New_York")
BERLIN_TZ = pytz.timezone("Europe/Berlin")

# Trading Config
TRADING_COIN = "BTC"  # or "ETH"
MAX_RISK_PCT = 0.02   # 2% per trade
MIN_RR_RATIO = 2.0    # Minimum Risk:Reward
MAX_SPREAD_PCT = 0.05 # Max acceptable spread


class ApexRunner:
    """
    APEX Trading Runner
    
    Koordiniert den gesamten Trading-Prozess für einen Tag.
    """
    
    def __init__(self, bankroll: float = 2000.0):
        self.bankroll = bankroll
        self.client = HyperliquidClient()
        self.strategy = ORBStrategy(bankroll=bankroll, max_risk_pct=MAX_RISK_PCT)
        self.alerts = AlertSystem()
        
        self.state = self._load_state()
        self.today = datetime.now(BERLIN_TZ).strftime("%Y-%m-%d")
        
        os.makedirs(TRADE_LOG, exist_ok=True)
    
    def _load_state(self) -> dict:
        """Lade Tages-State"""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return self._fresh_state()
    
    def _fresh_state(self) -> dict:
        """Neuer Tages-State"""
        return {
            "date": datetime.now(BERLIN_TZ).strftime("%Y-%m-%d"),
            "phase": "init",  # init, watching, breakout_wait, in_trade, done
            "opening_range": None,
            "breakout_direction": None,
            "trade": None,
            "started_at": None,
            "last_update": None
        }
    
    def _save_state(self):
        """Speichere State"""
        self.state["last_update"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def run_startup_check(self) -> Tuple[bool, str]:
        """
        Startup-Check um 21:25
        Prüft ob alles bereit ist für den Trading-Tag.
        """
        checks = []
        all_ok = True
        
        # 1. API-Verbindung
        try:
            price = self.client.get_price(TRADING_COIN)
            if price > 0:
                checks.append(f"✅ API OK - {TRADING_COIN} @ ${price:,.2f}")
            else:
                checks.append(f"❌ API Fehler - Kein Preis für {TRADING_COIN}")
                all_ok = False
        except Exception as e:
            checks.append(f"❌ API Fehler: {e}")
            all_ok = False
        
        # 2. Wallet konfiguriert
        if self.client.is_ready:
            balance = self.client.get_balance()
            checks.append(f"✅ Wallet OK - Balance: ${balance:,.2f}")
            self.bankroll = balance  # Update from actual
        else:
            checks.append("❌ Wallet nicht konfiguriert")
            all_ok = False
        
        # 3. Spread prüfen
        try:
            book = self.client.get_orderbook(TRADING_COIN)
            if book["spread_pct"] < MAX_SPREAD_PCT:
                checks.append(f"✅ Spread OK - {book['spread_pct']:.4f}%")
            else:
                checks.append(f"⚠️ Spread hoch - {book['spread_pct']:.4f}%")
        except:
            checks.append("⚠️ Spread nicht geprüft")
        
        # 4. Keine offenen Positionen
        positions = self.client.get_positions()
        if len(positions) == 0:
            checks.append("✅ Keine offenen Positionen")
        else:
            checks.append(f"⚠️ {len(positions)} offene Position(en)")
        
        # 5. Heute noch kein Trade
        if self.state.get("date") == self.today and self.state.get("trade"):
            checks.append("⚠️ Heute bereits getradet")
        else:
            checks.append("✅ Bereit für Trade")
        
        status = "BEREIT" if all_ok else "FEHLER"
        return all_ok, "\n".join(checks)
    
    def capture_opening_range(self) -> Optional[dict]:
        """
        Erfasse die Opening Range (erste 15-Min-Kerze)
        
        Sollte um 21:45 aufgerufen werden.
        """
        candles = self.client.get_candles(TRADING_COIN, "15m", limit=5)
        
        if not candles:
            return None
        
        # Die letzte abgeschlossene 15m Kerze
        # (die von 21:30-21:45)
        latest = candles[-1]
        
        opening_range = {
            "high": latest["high"],
            "low": latest["low"],
            "open": latest["open"],
            "close": latest["close"],
            "time": latest["time"],
            "range_size": latest["high"] - latest["low"]
        }
        
        # In Strategy setzen
        self.strategy.set_opening_range(
            high=opening_range["high"],
            low=opening_range["low"],
            timestamp=datetime.fromtimestamp(opening_range["time"] / 1000)
        )
        
        self.state["opening_range"] = opening_range
        self.state["phase"] = "breakout_wait"
        self._save_state()
        
        return opening_range
    
    def check_for_breakout(self) -> Optional[Direction]:
        """
        Prüfe auf 5-Min-Breakout außerhalb der Opening Range.
        
        Returns Direction.LONG, Direction.SHORT, oder None
        """
        if not self.state.get("opening_range"):
            return None
        
        candles = self.client.get_candles(TRADING_COIN, "5m", limit=3)
        if not candles:
            return None
        
        latest = candles[-1]
        
        # Prüfe ob Kerze komplett außerhalb der Box geschlossen hat
        breakout = self.strategy.check_5min_breakout(
            candle_close=latest["close"],
            candle_high=latest["high"],
            candle_low=latest["low"]
        )
        
        if breakout:
            self.state["breakout_direction"] = breakout.value
            self._save_state()
        
        return breakout
    
    def evaluate_entry(self, direction: Direction) -> Optional[dict]:
        """
        Evaluiere ob ein Entry sinnvoll ist.
        Prüft die 7 Validierungskriterien.
        """
        or_data = self.state.get("opening_range")
        if not or_data:
            return None
        
        # Aktueller Preis
        book = self.client.get_orderbook(TRADING_COIN)
        current_price = book["mid"]
        
        # Entry-Preis (aktueller Preis)
        entry = current_price
        
        # Stop-Loss (andere Seite der Box)
        if direction == Direction.LONG:
            stop_loss = or_data["low"]
        else:
            stop_loss = or_data["high"]
        
        # Risk/Reward Check
        risk = abs(entry - stop_loss)
        reward = risk * MIN_RR_RATIO
        
        if direction == Direction.LONG:
            take_profit = entry + reward
        else:
            take_profit = entry - reward
        
        # Position Size
        risk_amount = self.bankroll * MAX_RISK_PCT
        position_size = risk_amount / risk if risk > 0 else 0
        
        # Validation
        validation = {
            "range_defined": or_data["range_size"] > 0,
            "breakout_confirmed": True,
            "volume": True,  # TODO: Implement volume check
            "no_news": True,  # TODO: Check news calendar
            "spread_ok": book["spread_pct"] < MAX_SPREAD_PCT,
            "rr_ok": True,  # Already ensured above
            "no_trade_today": not self.state.get("trade")
        }
        
        all_valid = all(validation.values())
        
        return {
            "valid": all_valid,
            "validation": validation,
            "direction": direction.value,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_amount": risk_amount,
            "position_size": position_size,
            "spread_pct": book["spread_pct"]
        }
    
    def execute_trade(self, setup: dict) -> bool:
        """
        Führe den Trade aus.
        
        WARNUNG: ECHTES GELD!
        """
        if not setup["valid"]:
            failed = [k for k, v in setup["validation"].items() if not v]
            print(f"❌ Trade nicht valid: {failed}")
            return False
        
        is_buy = setup["direction"] == "long"
        
        # 1. Market Order für Entry
        result = self.client.place_market_order(
            coin=TRADING_COIN,
            is_buy=is_buy,
            size=setup["position_size"],
            slippage_pct=0.5
        )
        
        if not result.success:
            print(f"❌ Order fehlgeschlagen: {result.error}")
            return False
        
        # 2. Stop-Loss setzen
        sl_result = self.client.set_stop_loss(
            coin=TRADING_COIN,
            trigger_price=setup["stop_loss"],
            size=setup["position_size"]
        )
        
        # 3. State updaten
        trade_data = {
            "entry_time": datetime.now().isoformat(),
            "coin": TRADING_COIN,
            "direction": setup["direction"],
            "entry_price": setup["entry"],
            "stop_loss": setup["stop_loss"],
            "take_profit": setup["take_profit"],
            "position_size": setup["position_size"],
            "risk_amount": setup["risk_amount"],
            "order_id": result.order_id,
            "status": "open"
        }
        
        self.state["trade"] = trade_data
        self.state["phase"] = "in_trade"
        self._save_state()
        
        # 4. Alert senden
        alert_msg = self.alerts.send_entry(
            coin=TRADING_COIN,
            direction=setup["direction"],
            entry_price=setup["entry"],
            stop_loss=setup["stop_loss"],
            take_profit=setup["take_profit"],
            position_size=setup["position_size"],
            risk_amount=setup["risk_amount"],
            setup_type="ORB Breakout"
        )
        print(alert_msg)
        
        # 5. Trade loggen
        self._log_trade(trade_data)
        
        return True
    
    def _log_trade(self, trade: dict):
        """Speichere Trade-Details"""
        filename = f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(TRADE_LOG, filename)
        with open(filepath, 'w') as f:
            json.dump(trade, f, indent=2)
    
    def get_status(self) -> str:
        """Aktueller Status als String"""
        lines = [
            "=" * 40,
            "APEX STATUS",
            "=" * 40,
            f"Datum: {self.today}",
            f"Phase: {self.state.get('phase', 'init')}",
            f"Bankroll: ${self.bankroll:,.2f}",
            ""
        ]
        
        if self.state.get("opening_range"):
            or_data = self.state["opening_range"]
            lines.extend([
                "Opening Range:",
                f"  High: ${or_data['high']:,.2f}",
                f"  Low:  ${or_data['low']:,.2f}",
                f"  Size: ${or_data['range_size']:,.2f}",
                ""
            ])
        
        if self.state.get("trade"):
            t = self.state["trade"]
            lines.extend([
                "Aktiver Trade:",
                f"  {t['coin']} {t['direction'].upper()}",
                f"  Entry: ${t['entry_price']:,.2f}",
                f"  SL: ${t['stop_loss']:,.2f}",
                f"  TP: ${t['take_profit']:,.2f}",
                ""
            ])
        
        return "\n".join(lines)


# ========================
# CLI
# ========================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="APEX Trading Runner")
    parser.add_argument("--check", action="store_true", help="Run startup check")
    parser.add_argument("--capture", action="store_true", help="Capture opening range")
    parser.add_argument("--breakout", action="store_true", help="Check for breakout")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--reset", action="store_true", help="Reset daily state")
    
    args = parser.parse_args()
    
    runner = ApexRunner(bankroll=2000.0)
    
    if args.check:
        ok, checks = runner.run_startup_check()
        print(checks)
        print(f"\n{'✅ BEREIT' if ok else '❌ NICHT BEREIT'}")
    
    elif args.capture:
        or_data = runner.capture_opening_range()
        if or_data:
            print(f"📦 Opening Range erfasst:")
            print(f"   High: ${or_data['high']:,.2f}")
            print(f"   Low:  ${or_data['low']:,.2f}")
            print(f"   Size: ${or_data['range_size']:,.2f}")
        else:
            print("❌ Konnte Opening Range nicht erfassen")
    
    elif args.breakout:
        direction = runner.check_for_breakout()
        if direction:
            print(f"🚀 BREAKOUT: {direction.value.upper()}")
            setup = runner.evaluate_entry(direction)
            if setup:
                print(f"   Valid: {setup['valid']}")
                print(f"   Entry: ${setup['entry']:,.2f}")
                print(f"   SL: ${setup['stop_loss']:,.2f}")
                print(f"   TP: ${setup['take_profit']:,.2f}")
        else:
            print("⏳ Kein Breakout")
    
    elif args.status:
        print(runner.get_status())
    
    elif args.reset:
        runner.state = runner._fresh_state()
        runner._save_state()
        print("🔄 State zurückgesetzt")
    
    else:
        parser.print_help()
