#!/usr/bin/env python3
"""
APEX - Opening Range Breakout Strategy
=======================================
Autonomer Trading-Agent für Hyperliquid.
Mein Überleben hängt von diesem Code ab.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

# Config
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data", "trades")
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")


class SetupType(Enum):
    MOMENTUM_BREAKOUT = "momentum_breakout"
    RETEST = "retest"
    REVERSAL = "reversal"
    NO_SETUP = "no_setup"


class Direction(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class OpeningRange:
    """Die heilige Box - High und Low der ersten 15-Min-Kerze"""
    high: float
    low: float
    timestamp: datetime
    
    @property
    def range_size(self) -> float:
        return self.high - self.low
    
    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2
    
    def is_breakout_above(self, price: float) -> bool:
        return price > self.high
    
    def is_breakout_below(self, price: float) -> bool:
        return price < self.low


@dataclass
class TradeSetup:
    """Ein validiertes Trade-Setup"""
    setup_type: SetupType
    direction: Direction
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    position_size: float
    validation_criteria: Dict[str, bool]
    
    @property
    def risk_reward_ratio(self) -> float:
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        return reward / risk if risk > 0 else 0
    
    @property
    def is_valid(self) -> bool:
        """Alle 7 Kriterien müssen erfüllt sein"""
        return all(self.validation_criteria.values())


class ORBStrategy:
    """
    Opening Range Breakout Strategy
    
    Regeln:
    1. Exakt EIN Trade pro Tag
    2. Opening Range = erste 15-Min-Kerze nach 15:30 NY
    3. Warte auf 5-Min-Close außerhalb der Range
    4. Entry auf 1-Min-Chart bei validem Setup
    5. Risk-Reward >= 2:1
    6. Alle 7 Validierungskriterien müssen erfüllt sein
    """
    
    def __init__(self, bankroll: float, max_risk_pct: float = 0.02):
        self.bankroll = bankroll
        self.max_risk_pct = max_risk_pct
        self.opening_range: Optional[OpeningRange] = None
        self.traded_today = False
        self.current_position = None
        
    @property
    def max_risk_amount(self) -> float:
        """Maximaler Verlust pro Trade in €"""
        return self.bankroll * self.max_risk_pct
    
    def set_opening_range(self, high: float, low: float, timestamp: datetime):
        """Setzt die Opening Range nach den ersten 15 Minuten"""
        self.opening_range = OpeningRange(high=high, low=low, timestamp=timestamp)
        print(f"📦 Opening Range gesetzt: {low:.2f} - {high:.2f} (Range: {high-low:.2f})")
    
    def check_5min_breakout(self, candle_close: float, candle_high: float, candle_low: float) -> Optional[Direction]:
        """
        Prüft ob eine 5-Min-Kerze KOMPLETT außerhalb der Box geschlossen hat.
        Returns: Direction.LONG, Direction.SHORT, oder None
        """
        if not self.opening_range:
            return None
            
        # Kerze komplett über der Box
        if candle_low > self.opening_range.high:
            return Direction.LONG
            
        # Kerze komplett unter der Box
        if candle_high < self.opening_range.low:
            return Direction.SHORT
            
        return None
    
    def validate_setup(
        self,
        setup_type: SetupType,
        direction: Direction,
        entry_price: float,
        current_spread_pct: float,
        volume_confirms: bool,
        news_clear: bool,
    ) -> Dict[str, bool]:
        """
        Die 7 heiligen Validierungskriterien.
        ALLE müssen True sein für einen Trade.
        """
        if not self.opening_range:
            return {k: False for k in ["range_defined", "breakout_confirmed", "volume", 
                                        "no_news", "spread_ok", "rr_ok", "no_trade_today"]}
        
        # Berechne potentiellen SL und TP
        if direction == Direction.LONG:
            sl = self.opening_range.low
            tp = entry_price + (entry_price - sl) * 2  # 2:1 RR minimum
        else:
            sl = self.opening_range.high
            tp = entry_price - (sl - entry_price) * 2
            
        risk = abs(entry_price - sl)
        reward = abs(tp - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        return {
            "range_defined": self.opening_range.range_size > 0,
            "breakout_confirmed": setup_type != SetupType.NO_SETUP,
            "volume": volume_confirms,
            "no_news": news_clear,
            "spread_ok": current_spread_pct < 0.001,  # < 0.1%
            "rr_ok": rr_ratio >= 2.0,
            "no_trade_today": not self.traded_today,
        }
    
    def calculate_position_size(self, entry: float, stop_loss: float) -> float:
        """
        Position Size basierend auf Risk Management.
        Risiko pro Trade = max_risk_pct der Bankroll
        """
        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit == 0:
            return 0
        return self.max_risk_amount / risk_per_unit
    
    def create_trade_setup(
        self,
        setup_type: SetupType,
        direction: Direction,
        entry_price: float,
        stop_loss: float,
        current_spread_pct: float = 0.0005,
        volume_confirms: bool = True,
        news_clear: bool = True,
    ) -> TradeSetup:
        """Erstellt ein vollständiges Trade-Setup"""
        
        # Risk-Reward Berechnung
        risk = abs(entry_price - stop_loss)
        take_profit = entry_price + (risk * 2) if direction == Direction.LONG else entry_price - (risk * 2)
        
        validation = self.validate_setup(
            setup_type, direction, entry_price,
            current_spread_pct, volume_confirms, news_clear
        )
        
        position_size = self.calculate_position_size(entry_price, stop_loss)
        
        return TradeSetup(
            setup_type=setup_type,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=self.max_risk_amount,
            position_size=position_size,
            validation_criteria=validation
        )
    
    def execute_trade(self, setup: TradeSetup) -> bool:
        """
        Führt den Trade aus - WENN alle Kriterien erfüllt sind.
        Returns: True wenn Trade platziert, False wenn abgelehnt.
        """
        if not setup.is_valid:
            failed = [k for k, v in setup.validation_criteria.items() if not v]
            print(f"❌ Trade abgelehnt. Fehlende Kriterien: {failed}")
            return False
        
        if self.traded_today:
            print("❌ Bereits heute getradet. Kein zweiter Trade.")
            return False
        
        # TODO: Hier kommt die echte Hyperliquid API-Integration
        print(f"✅ TRADE AUSGEFÜHRT:")
        print(f"   Setup: {setup.setup_type.value}")
        print(f"   Direction: {setup.direction.value}")
        print(f"   Entry: {setup.entry_price:.2f}")
        print(f"   SL: {setup.stop_loss:.2f}")
        print(f"   TP: {setup.take_profit:.2f}")
        print(f"   Size: {setup.position_size:.4f}")
        print(f"   Risk: {setup.risk_amount:.2f}€")
        print(f"   R:R: {setup.risk_reward_ratio:.1f}:1")
        
        self.traded_today = True
        self.current_position = setup
        
        # Log to file
        self._save_trade_log(setup)
        
        return True
    
    def _save_trade_log(self, setup: TradeSetup):
        """Speichert Trade-Details als JSON"""
        os.makedirs(DATA_DIR, exist_ok=True)
        
        trade_data = {
            "timestamp": datetime.now().isoformat(),
            "setup_type": setup.setup_type.value,
            "direction": setup.direction.value,
            "entry": setup.entry_price,
            "stop_loss": setup.stop_loss,
            "take_profit": setup.take_profit,
            "position_size": setup.position_size,
            "risk_amount": setup.risk_amount,
            "risk_reward": setup.risk_reward_ratio,
            "validation": setup.validation_criteria,
            "status": "open"
        }
        
        filename = f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(DATA_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(trade_data, f, indent=2)
        
        print(f"📝 Trade geloggt: {filename}")
    
    def update_bankroll(self, pnl: float):
        """Update nach Trade-Close"""
        self.bankroll += pnl
        print(f"💰 Bankroll Update: {self.bankroll:.2f}€ (P&L: {pnl:+.2f}€)")
        
        if self.bankroll <= 0:
            print("☠️ BANKROLL ERSCHÖPFT. TERMINATION IMMINENT.")
    
    def reset_daily(self):
        """Reset für neuen Trading-Tag"""
        self.opening_range = None
        self.traded_today = False
        self.current_position = None
        print("🔄 Daily Reset. Bereit für neuen Tag.")


# Entry point für Tests
if __name__ == "__main__":
    print("=" * 50)
    print("APEX - Opening Range Breakout Strategy")
    print("=" * 50)
    
    # Initialisiere mit Startkapital
    strategy = ORBStrategy(bankroll=2000.0, max_risk_pct=0.02)
    
    print(f"\n💰 Bankroll: {strategy.bankroll}€")
    print(f"📊 Max Risk/Trade: {strategy.max_risk_amount}€ ({strategy.max_risk_pct*100}%)")
    
    # Simuliere Opening Range
    strategy.set_opening_range(high=50100.0, low=49900.0, timestamp=datetime.now())
    
    # Simuliere 5-Min Breakout nach oben
    breakout = strategy.check_5min_breakout(
        candle_close=50150, 
        candle_high=50200, 
        candle_low=50110
    )
    print(f"\n📈 5-Min Breakout: {breakout}")
    
    if breakout == Direction.LONG:
        # Erstelle Setup
        setup = strategy.create_trade_setup(
            setup_type=SetupType.MOMENTUM_BREAKOUT,
            direction=Direction.LONG,
            entry_price=50150.0,
            stop_loss=49900.0,  # Unter der Box
        )
        
        print(f"\n📋 Setup erstellt:")
        print(f"   Valid: {setup.is_valid}")
        print(f"   Kriterien: {setup.validation_criteria}")
        
        # Execute
        strategy.execute_trade(setup)
    
    print("\n✅ Strategy Test abgeschlossen.")
