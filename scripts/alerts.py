#!/usr/bin/env python3
"""
APEX - Alert System
===================
Telegram-Benachrichtigungen für Trade-Events.
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALERTS_LOG = os.path.join(PROJECT_DIR, "data", "alerts.log")


@dataclass
class TradeAlert:
    """Trade-Benachrichtigung"""
    alert_type: str  # "entry", "exit", "sl_moved", "warning", "daily_summary"
    coin: str
    message: str
    details: Dict[str, Any]
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class AlertSystem:
    """
    Alert-System für APEX
    
    Sendet Benachrichtigungen über OpenClaw's message tool.
    Logs werden lokal gespeichert für Audit.
    """
    
    def __init__(self):
        os.makedirs(os.path.dirname(ALERTS_LOG), exist_ok=True)
    
    def _log_alert(self, alert: TradeAlert):
        """Speichere Alert im Log"""
        with open(ALERTS_LOG, 'a') as f:
            f.write(json.dumps({
                "type": alert.alert_type,
                "coin": alert.coin,
                "message": alert.message,
                "details": alert.details,
                "timestamp": alert.timestamp
            }) + "\n")
    
    def format_entry_alert(
        self,
        coin: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_size: float,
        risk_amount: float,
        setup_type: str
    ) -> str:
        """Formatiere Entry-Alert"""
        emoji = "🟢" if direction == "long" else "🔴"
        arrow = "📈" if direction == "long" else "📉"
        
        rr = abs(take_profit - entry_price) / abs(entry_price - stop_loss)
        
        return f"""
{arrow} **APEX TRADE ERÖFFNET** {emoji}

**{coin}** {direction.upper()}

┌─────────────────────
│ Entry:    ${entry_price:,.2f}
│ Stop:     ${stop_loss:,.2f}
│ Target:   ${take_profit:,.2f}
│ Size:     {position_size:.6f}
│ Risk:     ${risk_amount:.2f}
│ R:R:      {rr:.1f}:1
│ Setup:    {setup_type}
└─────────────────────

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
    
    def format_exit_alert(
        self,
        coin: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str
    ) -> str:
        """Formatiere Exit-Alert"""
        if pnl >= 0:
            emoji = "✅"
            result = "GEWINN"
        else:
            emoji = "❌"
            result = "VERLUST"
        
        return f"""
{emoji} **APEX TRADE GESCHLOSSEN**

**{coin}** {direction.upper()} → {result}

┌─────────────────────
│ Entry:    ${entry_price:,.2f}
│ Exit:     ${exit_price:,.2f}
│ P&L:      ${pnl:+,.2f} ({pnl_pct:+.2f}%)
│ Grund:    {reason}
└─────────────────────

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
    
    def format_sl_moved_alert(
        self,
        coin: str,
        old_sl: float,
        new_sl: float,
        current_price: float,
        reason: str
    ) -> str:
        """Formatiere SL-Move Alert"""
        return f"""
🔒 **STOP-LOSS ANGEPASST**

**{coin}**
│ Alt:   ${old_sl:,.2f}
│ Neu:   ${new_sl:,.2f}
│ Preis: ${current_price:,.2f}
│ Grund: {reason}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
    
    def format_daily_summary(
        self,
        date: str,
        starting_balance: float,
        ending_balance: float,
        trades_count: int,
        wins: int,
        total_pnl: float
    ) -> str:
        """Formatiere Tages-Zusammenfassung"""
        pnl_pct = (ending_balance - starting_balance) / starting_balance * 100
        win_rate = (wins / trades_count * 100) if trades_count > 0 else 0
        
        if total_pnl >= 0:
            emoji = "📈"
            status = "PROFITABEL"
        else:
            emoji = "📉"
            status = "VERLUST"
        
        return f"""
{emoji} **APEX DAILY SUMMARY** - {date}

**Status:** {status}

┌─────────────────────
│ Start:     ${starting_balance:,.2f}
│ Ende:      ${ending_balance:,.2f}
│ P&L:       ${total_pnl:+,.2f} ({pnl_pct:+.2f}%)
│ 
│ Trades:    {trades_count}
│ Wins:      {wins}
│ Win-Rate:  {win_rate:.0f}%
└─────────────────────

🤖 APEX überlebt einen weiteren Tag.
"""
    
    def format_no_trade_alert(self, reason: str) -> str:
        """Kein Trade heute - Erklärung"""
        return f"""
⏸️ **APEX - KEIN TRADE HEUTE**

Grund: {reason}

Kein Setup = Kein Trade.
Überlebensinstinkt > FOMO.

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
    
    def format_warning_alert(self, message: str, details: str = "") -> str:
        """Warnung/Fehler"""
        return f"""
⚠️ **APEX WARNUNG**

{message}

{details if details else ""}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
    
    def format_startup_alert(self, balance: float, status: str) -> str:
        """Startup-Check"""
        return f"""
🤖 **APEX ONLINE**

Status: {status}
Balance: ${balance:,.2f}
Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Warte auf 15:30 NY Opening...
"""
    
    def send_entry(self, **kwargs) -> str:
        """Sende Entry-Alert"""
        msg = self.format_entry_alert(**kwargs)
        alert = TradeAlert(
            alert_type="entry",
            coin=kwargs.get("coin", ""),
            message=msg,
            details=kwargs
        )
        self._log_alert(alert)
        return msg
    
    def send_exit(self, **kwargs) -> str:
        """Sende Exit-Alert"""
        msg = self.format_exit_alert(**kwargs)
        alert = TradeAlert(
            alert_type="exit",
            coin=kwargs.get("coin", ""),
            message=msg,
            details=kwargs
        )
        self._log_alert(alert)
        return msg
    
    def send_sl_moved(self, **kwargs) -> str:
        """Sende SL-Move Alert"""
        msg = self.format_sl_moved_alert(**kwargs)
        alert = TradeAlert(
            alert_type="sl_moved",
            coin=kwargs.get("coin", ""),
            message=msg,
            details=kwargs
        )
        self._log_alert(alert)
        return msg
    
    def send_daily_summary(self, **kwargs) -> str:
        """Sende Daily Summary"""
        msg = self.format_daily_summary(**kwargs)
        alert = TradeAlert(
            alert_type="daily_summary",
            coin="ALL",
            message=msg,
            details=kwargs
        )
        self._log_alert(alert)
        return msg


# ========================
# TEST
# ========================

if __name__ == "__main__":
    print("=" * 50)
    print("APEX - Alert System Test")
    print("=" * 50)
    
    alerts = AlertSystem()
    
    # Test Entry Alert
    print("\n📤 Entry Alert:")
    print(alerts.format_entry_alert(
        coin="BTC",
        direction="long",
        entry_price=69500,
        stop_loss=69000,
        take_profit=70500,
        position_size=0.0008,
        risk_amount=40,
        setup_type="Momentum Breakout"
    ))
    
    # Test Exit Alert
    print("\n📤 Exit Alert (Win):")
    print(alerts.format_exit_alert(
        coin="BTC",
        direction="long",
        entry_price=69500,
        exit_price=70500,
        pnl=80,
        pnl_pct=4.0,
        reason="Take Profit erreicht"
    ))
    
    # Test Daily Summary
    print("\n📤 Daily Summary:")
    print(alerts.format_daily_summary(
        date="2026-03-22",
        starting_balance=2000,
        ending_balance=2080,
        trades_count=1,
        wins=1,
        total_pnl=80
    ))
    
    print("\n✅ Alert Test abgeschlossen.")
