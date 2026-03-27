#!/usr/bin/env python3
"""
APEX - Position Monitor
=======================
Checkt ob Positionen geschlossen wurden und meldet Ergebnisse.
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.hyperliquid_client import HyperliquidClient

# Files
STATE_FILE = "/data/.openclaw/workspace/projects/apex-trading/data/monitor_state.json"
PNL_TRACKER_FILE = "/data/.openclaw/workspace/projects/apex-trading/data/pnl_tracker.json"


def load_state():
    """Load last known state"""
    if not os.path.exists(STATE_FILE):
        return {"last_position_count": 0, "last_check": None}
    
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def save_state(state):
    """Save current state"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def send_telegram_notification(message):
    """Send notification via telegram_sender module"""
    try:
        from telegram_sender import send_telegram_message
        send_telegram_message(message)
    except Exception as e:
        print(f"⚠️  Telegram notification error: {e}")


def update_pnl_tracker(pnl):
    """Update P&L tracker with realized profit"""
    if not os.path.exists(PNL_TRACKER_FILE):
        return
    
    with open(PNL_TRACKER_FILE, 'r') as f:
        tracker = json.load(f)
    
    # Update realized P&L
    tracker["realized_pnl"] = tracker.get("realized_pnl", 0) + pnl
    tracker["total_pnl"] = tracker["realized_pnl"] + tracker.get("unrealized_pnl", 0)
    
    # Update trade counts
    if pnl > 0:
        tracker["winning_trades"] = tracker.get("winning_trades", 0) + 1
    else:
        tracker["losing_trades"] = tracker.get("losing_trades", 0) + 1
    
    tracker["total_trades"] = tracker.get("total_trades", 0) + 1
    tracker["last_updated"] = datetime.now().isoformat()
    
    # Check milestones
    for milestone_name, milestone in tracker.get("milestones", {}).items():
        if not milestone.get("reached", False):
            if tracker["total_pnl"] >= milestone["target"]:
                milestone["reached"] = True
                print(f"\n🎉 MILESTONE REACHED: +${milestone['target']} → Bonus: +${milestone['bonus']} USDC!")
    
    with open(PNL_TRACKER_FILE, 'w') as f:
        json.dump(tracker, f, indent=2)


def main():
    """Main monitoring logic"""
    client = HyperliquidClient()
    
    # Get current positions FIRST (fast check)
    positions = client.get_positions()
    current_count = len(positions)
    
    # Load last state
    state = load_state()
    last_count = state.get("last_position_count", 0)
    
    # Quick exit if no positions and wasn't tracking any
    if current_count == 0 and last_count == 0:
        print("\n⏸️  Keine Positionen - Monitor idle")
        return current_count
    
    # Check if position was closed
    if last_count > 0 and current_count == 0:
        print("\n" + "=" * 60)
        print("🎯 POSITION GESCHLOSSEN!")
        print("=" * 60)
        
        # Get recent fills from last 24h and find the closing trade
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        wallet = os.getenv('HYPERLIQUID_WALLET', '0x537f283E5145a53a9A9e53a5570ED225D7E62a8B')
        fills = info.user_fills(wallet)
        
        # Filter to last 24h and find Close trades
        yesterday = (datetime.now() - timedelta(hours=24)).timestamp() * 1000
        recent_fills = [f for f in fills if f['time'] > yesterday]
        
        # Group by closedPnl to find the complete closed position
        closed_trades = {}
        for fill in recent_fills:
            if fill.get('closedPnl') and fill['closedPnl'] != '0.0':
                coin = fill['coin']
                direction = fill['dir']
                if 'Close' in direction:
                    key = f"{coin}_{direction}_{fill['time']}"
                    if key not in closed_trades:
                        closed_trades[key] = {
                            'coin': coin,
                            'direction': direction,
                            'price': float(fill['px']),
                            'size': 0,
                            'pnl': 0,
                            'time': fill['time']
                        }
                    closed_trades[key]['size'] += float(fill['sz'])
                    closed_trades[key]['pnl'] += float(fill['closedPnl'])
        
        if closed_trades:
            # Get the most recent closed trade
            latest_trade = sorted(closed_trades.values(), key=lambda x: x['time'], reverse=True)[0]
            
            coin = latest_trade['coin']
            direction = latest_trade['direction']
            exit_price = latest_trade['price']
            total_size = latest_trade['size']
            total_pnl = latest_trade['pnl']
            
            print(f"\n💰 FINAL RESULT:")
            print(f"   Asset: {coin}")
            print(f"   Direction: {direction}")
            print(f"   Exit: ${exit_price:,.2f}")
            print(f"   Size: {total_size}")
            print(f"   P&L: ${total_pnl:,.2f}")
            
            # Get current balance
            balance = client.get_balance()
            print(f"\nAktuelle Balance: ${balance:,.2f}")
            
            # Build notification message
            if total_pnl > 0:
                emoji = "✅"
                result_text = f"GEWINN: +${total_pnl:.2f}"
            else:
                emoji = "❌"
                result_text = f"VERLUST: ${total_pnl:.2f}"
            
            message = f"""🎯 APEX TRADE GESCHLOSSEN!

{emoji} {result_text}

Asset: {coin}
Exit: ${exit_price:,.2f}
Size: {total_size:.5f}

💰 Neue Balance: ${balance:,.2f}"""
            
            print(f"\n{emoji} {result_text}")
            print("\n📢 Sende Telegram-Benachrichtigung...")
            send_telegram_notification(message)
            
            # Update P&L tracker
            update_pnl_tracker(total_pnl)
                
        else:
            print("⚠️  Keine geschlossenen Trades in letzten 24h gefunden")
            send_telegram_notification("🎯 APEX: Position geschlossen, aber keine Trade-Details gefunden.")
        
    elif current_count > 0:
        # Position still running
        pos = positions[0]
        print(f"\n✅ Position läuft weiter:")
        print(f"   {pos.coin} {('LONG' if pos.size > 0 else 'SHORT')}")
        print(f"   P&L: ${pos.unrealized_pnl:.2f}")
    else:
        print("\n⏸️  Keine offenen Positionen")
    
    # Save new state
    save_state({
        "last_position_count": current_count,
        "last_check": datetime.now().isoformat()
    })
    
    return current_count


if __name__ == "__main__":
    try:
        count = main()
        print("NO_REPLY")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("NO_REPLY")
        sys.exit(1)
