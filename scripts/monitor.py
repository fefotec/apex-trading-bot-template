#!/usr/bin/env python3
"""
APEX - Trade Monitor (60-Sekunden Loop)
========================================
Überwacht offene Positionen und zieht SL nach.
Läuft als Daemon während eines aktiven Trades.
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Optional

# Imports aus dem Projekt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hyperliquid_api import HyperliquidClient, Position

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "monitor_state.json")


class TradeMonitor:
    """
    60-Sekunden Monitoring Loop
    
    Aufgaben:
    1. Prüfe aktuellen Preis
    2. Berechne unrealized P&L
    3. Ziehe SL nach wenn im Profit
    4. Sende Alerts bei wichtigen Events
    """
    
    def __init__(self, client: HyperliquidClient):
        self.client = client
        self.state = self._load_state()
    
    def _load_state(self) -> dict:
        """Lade letzten State"""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {
            "active_trade": None,
            "entry_price": 0,
            "original_sl": 0,
            "current_sl": 0,
            "break_even_moved": False,
            "last_check": None
        }
    
    def _save_state(self):
        """Speichere State"""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def start_monitoring(
        self,
        symbol: str,
        direction: str,  # "long" or "short"
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ):
        """Starte Monitoring für einen neuen Trade"""
        self.state = {
            "active_trade": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "original_sl": stop_loss,
            "current_sl": stop_loss,
            "take_profit": take_profit,
            "break_even_moved": False,
            "trail_active": False,
            "started_at": datetime.now().isoformat(),
            "last_check": None,
            "checks_count": 0
        }
        self._save_state()
        print(f"🎯 Monitoring gestartet für {symbol} {direction.upper()}")
        print(f"   Entry: {entry_price:.2f}")
        print(f"   SL: {stop_loss:.2f}")
        print(f"   TP: {take_profit:.2f}")
    
    def check_and_trail(self) -> dict:
        """
        Hauptlogik: Prüfe Position und passe SL an.
        Sollte alle 60 Sekunden aufgerufen werden.
        """
        if not self.state.get("active_trade"):
            return {"status": "no_active_trade"}
        
        symbol = self.state["active_trade"]
        direction = self.state["direction"]
        entry = self.state["entry_price"]
        current_sl = self.state["current_sl"]
        tp = self.state["take_profit"]
        
        # Hole aktuellen Preis
        try:
            ticker = self.client.get_ticker(symbol)
            current_price = ticker["mid"]
        except Exception as e:
            return {"status": "error", "error": str(e)}
        
        # Berechne P&L
        if direction == "long":
            pnl_pct = (current_price - entry) / entry * 100
            distance_to_sl = (current_price - current_sl) / current_price * 100
            distance_to_tp = (tp - current_price) / current_price * 100
        else:
            pnl_pct = (entry - current_price) / entry * 100
            distance_to_sl = (current_sl - current_price) / current_price * 100
            distance_to_tp = (current_price - tp) / current_price * 100
        
        result = {
            "status": "active",
            "symbol": symbol,
            "direction": direction,
            "current_price": current_price,
            "entry": entry,
            "pnl_pct": pnl_pct,
            "current_sl": current_sl,
            "distance_to_sl": distance_to_sl,
            "distance_to_tp": distance_to_tp,
            "action": None
        }
        
        # === TRAILING LOGIC ===
        
        # 1. Move to Break-Even wenn >1% im Profit
        if not self.state["break_even_moved"] and pnl_pct > 1.0:
            new_sl = entry  # Break-Even
            if self._update_sl(symbol, new_sl):
                self.state["break_even_moved"] = True
                self.state["current_sl"] = new_sl
                result["action"] = "moved_to_break_even"
                print(f"🔒 SL auf Break-Even verschoben: {new_sl:.2f}")
        
        # 2. Trail SL wenn >2% im Profit
        elif self.state["break_even_moved"] and pnl_pct > 2.0:
            # Trail: SL = Entry + 50% des aktuellen Profits
            if direction == "long":
                new_sl = entry + (current_price - entry) * 0.5
                if new_sl > current_sl:
                    if self._update_sl(symbol, new_sl):
                        self.state["current_sl"] = new_sl
                        self.state["trail_active"] = True
                        result["action"] = f"trailed_sl_to_{new_sl:.2f}"
                        print(f"📈 SL nachgezogen: {new_sl:.2f}")
            else:
                new_sl = entry - (entry - current_price) * 0.5
                if new_sl < current_sl:
                    if self._update_sl(symbol, new_sl):
                        self.state["current_sl"] = new_sl
                        self.state["trail_active"] = True
                        result["action"] = f"trailed_sl_to_{new_sl:.2f}"
                        print(f"📈 SL nachgezogen: {new_sl:.2f}")
        
        # Update State
        self.state["last_check"] = datetime.now().isoformat()
        self.state["checks_count"] = self.state.get("checks_count", 0) + 1
        self._save_state()
        
        return result
    
    def _update_sl(self, symbol: str, new_sl: float) -> bool:
        """Update Stop-Loss auf der Exchange"""
        try:
            # TODO: Echte API-Implementierung
            # return self.client.modify_sl(symbol, new_sl)
            print(f"   [MOCK] SL würde auf {new_sl:.2f} gesetzt")
            return True
        except Exception as e:
            print(f"   ❌ SL Update fehlgeschlagen: {e}")
            return False
    
    def stop_monitoring(self, final_pnl: float):
        """Beende Monitoring nach Trade-Close"""
        print(f"🏁 Trade beendet. P&L: {final_pnl:+.2f}€")
        print(f"   Checks durchgeführt: {self.state.get('checks_count', 0)}")
        
        self.state = {
            "active_trade": None,
            "last_trade_pnl": final_pnl,
            "last_trade_ended": datetime.now().isoformat()
        }
        self._save_state()
    
    def run_loop(self, interval_seconds: int = 60):
        """
        Endlos-Loop für kontinuierliches Monitoring.
        ACHTUNG: Blockiert den Thread!
        """
        print(f"🔄 Monitor-Loop gestartet (Interval: {interval_seconds}s)")
        print("   Drücke Ctrl+C zum Beenden")
        
        try:
            while self.state.get("active_trade"):
                result = self.check_and_trail()
                
                # Status-Ausgabe
                if result["status"] == "active":
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"{result['symbol']} | "
                          f"Price: {result['current_price']:.2f} | "
                          f"P&L: {result['pnl_pct']:+.2f}% | "
                          f"SL: {result['current_sl']:.2f}")
                    
                    if result.get("action"):
                        print(f"   🎯 Action: {result['action']}")
                
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n⏹️ Monitor manuell gestoppt.")


# Entry Point
if __name__ == "__main__":
    print("=" * 50)
    print("APEX - Trade Monitor")
    print("=" * 50)
    
    client = HyperliquidClient()
    monitor = TradeMonitor(client)
    
    # Simuliere einen Trade zum Testen
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("\n🧪 Test-Modus: Simuliere Trade...")
        
        monitor.start_monitoring(
            symbol="BTC",
            direction="long",
            entry_price=50000.0,
            stop_loss=49500.0,
            take_profit=51000.0
        )
        
        # Einmal checken
        result = monitor.check_and_trail()
        print(f"\n📊 Check Result: {json.dumps(result, indent=2)}")
        
    elif len(sys.argv) > 1 and sys.argv[1] == "--loop":
        print("\n🔄 Starte Monitor-Loop...")
        monitor.run_loop(interval_seconds=60)
        
    else:
        print("\nUsage:")
        print("  python monitor.py --test    # Einmal testen")
        print("  python monitor.py --loop    # Endlos-Loop starten")
        print("\nAktueller State:")
        print(json.dumps(monitor.state, indent=2))
