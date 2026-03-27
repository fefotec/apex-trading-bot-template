#!/usr/bin/env python3
"""
APEX - Autonomous Trading Script
=================================
Wird von Cron Jobs aufgerufen, checkt Breakouts, platziert Orders autonom.
"""

import os
import sys
import json
from datetime import datetime
from place_order import place_market_order, place_stop_loss, place_take_profit, load_credentials
from telegram_sender import send_telegram_message

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.hyperliquid_client import HyperliquidClient

# Config
CAPITAL = 2300  # Total USDC
MAX_RISK_PCT = 0.02  # 2% risk per trade
MAX_RISK_USD = CAPITAL * MAX_RISK_PCT  # ~$46

# Opening Range Boxes (werden von Opening Range Cron aktualisiert)
BOXES_FILE = "/data/.openclaw/workspace/projects/apex-trading/data/opening_range_boxes.json"

# Trade Log
TRADES_FILE = "/data/.openclaw/workspace/projects/apex-trading/data/trades.json"


def load_boxes():
    """Lade Opening Range Boxen"""
    if not os.path.exists(BOXES_FILE):
        return {}
    
    with open(BOXES_FILE, 'r') as f:
        return json.load(f)


def save_boxes(boxes):
    """Speichere Opening Range Boxen"""
    os.makedirs(os.path.dirname(BOXES_FILE), exist_ok=True)
    with open(BOXES_FILE, 'w') as f:
        json.dump(boxes, f, indent=2)


def get_current_session():
    """Determine current trading session based on time"""
    now = datetime.now()
    hour = now.hour
    
    if 2 <= hour < 4:
        return "tokyo"
    elif 9 <= hour < 11:
        return "eu"
    elif 21 <= hour < 23:
        return "us"
    return None


def has_traded_today_in_session(session):
    """Check if we already traded today in this session"""
    if not os.path.exists(TRADES_FILE):
        return False
    
    with open(TRADES_FILE, 'r') as f:
        trades = json.load(f)
    
    today = datetime.now().date().isoformat()
    
    for trade in trades:
        trade_date = trade["timestamp"][:10]  # Get YYYY-MM-DD
        
        # If no session field, derive from timestamp
        if "session" in trade:
            trade_session = trade["session"]
        else:
            # Parse timestamp to get hour
            trade_time = datetime.fromisoformat(trade["timestamp"])
            trade_hour = trade_time.hour
            
            if 2 <= trade_hour < 4:
                trade_session = "tokyo"
            elif 9 <= trade_hour < 11:
                trade_session = "eu"
            elif 21 <= trade_hour < 23:
                trade_session = "us"
            else:
                trade_session = "unknown"
        
        if trade_date == today and trade_session == session:
            return True
    
    return False


def log_trade(trade_data):
    """Logge Trade"""
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    
    trades = []
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, 'r') as f:
            trades = json.load(f)
    
    trades.append({
        **trade_data,
        "timestamp": datetime.now().isoformat(),
        "session": get_current_session()
    })
    
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)


def check_breakout(asset, current_price, box_high, box_low, threshold=50):
    """
    Check ob Asset aus Box ausgebrochen ist
    
    Returns:
        str: "long" | "short" | None
    """
    if current_price > box_high + threshold:
        return "long"
    elif current_price < box_low - threshold:
        return "short"
    return None


def calculate_position_size(risk_usd, entry_price, stop_loss_price):
    """Berechne Position Size basierend auf Risk"""
    risk_per_unit = abs(entry_price - stop_loss_price)
    if risk_per_unit == 0:
        return 0
    
    size = risk_usd / risk_per_unit
    return size


def execute_breakout_trade(asset, direction, entry_price, box_high, box_low):
    """
    Platziere Breakout Trade mit Stop-Loss und Take-Profit
    
    Returns:
        dict: Trade result
    """
    # Calculate SL
    if direction == "long":
        stop_loss = box_low - 10  # $10 below box
    else:
        stop_loss = box_high + 10  # $10 above box
    
    # Calculate position size
    size = calculate_position_size(MAX_RISK_USD, entry_price, stop_loss)
    
    # Round size appropriately
    if asset in ["BTC", "ETH"]:
        size = round(size, 5)  # 5 decimals
    else:
        size = round(size, 4)
    
    # Minimum size check
    if asset == "BTC" and size < 0.00001:
        return {"success": False, "error": "Size too small"}
    
    # Place market order
    is_buy = (direction == "long")
    order_result = place_market_order(asset, is_buy, size, reduce_only=False)
    
    if not order_result["success"]:
        return order_result
    
    actual_entry = order_result["avg_price"]
    
    # Calculate Take-Profit (2:1 Risk/Reward ratio)
    risk_per_coin = abs(actual_entry - stop_loss)
    reward_per_coin = risk_per_coin * 2  # Conservative 2:1
    
    if direction == "long":
        take_profit = actual_entry + reward_per_coin
    else:
        take_profit = actual_entry - reward_per_coin
    
    # Place stop-loss
    sl_result = place_stop_loss(asset, stop_loss, size)
    
    # Place take-profit
    tp_result = place_take_profit(asset, take_profit, size)
    
    # Log trade
    log_trade({
        "asset": asset,
        "direction": direction,
        "entry_price": actual_entry,
        "size": size,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_usd": MAX_RISK_USD,
        "reward_usd": MAX_RISK_USD * 2,
        "ratio": "2:1",
        "order_result": order_result,
        "sl_result": sl_result,
        "tp_result": tp_result
    })
    
    return {
        "success": True,
        "asset": asset,
        "direction": direction,
        "entry": actual_entry,
        "size": size,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sl_placed": sl_result["success"],
        "tp_placed": tp_result["success"]
    }


def scan_for_breakouts():
    """
    Scanne alle Assets auf Breakouts
    Berücksichtigt offene Positionen: Asset mit Position wird geskippt
    
    Returns:
        dict: Best breakout opportunity oder None
    """
    boxes = load_boxes()
    
    if not boxes:
        return {"success": False, "error": "No boxes loaded"}
    
    client = HyperliquidClient()
    
    # Check which assets already have positions
    positions = client.get_positions()
    position_assets = [p.coin for p in positions]
    
    # Priority: BTC > ETH > SOL > AVAX
    priority = ["BTC", "ETH", "SOL", "AVAX"]
    
    best_breakout = None
    
    for asset in priority:
        # Skip if asset already has a position
        if asset in position_assets:
            print(f"   ⏭️  {asset}: Skipped (position already open)")
            continue
        
        if asset not in boxes:
            continue
        
        box = boxes[asset]
        current_price = client.get_price(asset)
        
        # Check breakout
        threshold = 50 if asset in ["BTC", "ETH"] else (current_price * 0.02)
        direction = check_breakout(asset, current_price, box["high"], box["low"], threshold)
        
        if direction:
            # Found breakout!
            best_breakout = {
                "asset": asset,
                "direction": direction,
                "current_price": current_price,
                "box_high": box["high"],
                "box_low": box["low"],
                "breakout_size": abs(current_price - (box["high"] if direction == "long" else box["low"]))
            }
            break  # Take first (highest priority)
    
    return best_breakout


def main():
    """Main execution"""
    print("=" * 60)
    print("APEX - Autonomous Trade Check")
    print("=" * 60)
    
    # Check current session
    session = get_current_session()
    if not session:
        print("⚠️  Not in a trading session window!")
        print("NO_REPLY")
        return {"success": True, "skipped": True, "reason": "Outside trading hours"}
    
    print(f"📍 Current Session: {session.upper()}")
    
    # Check if already traded today in this session
    if has_traded_today_in_session(session):
        print(f"\n✅ SKIP: Already traded today in {session.upper()} session!")
        print("   Max 1 trade per session - no additional trades allowed.")
        send_telegram_message(f"⏭️ APEX {session.upper()}: Skip - bereits getradet in dieser Session")
        print("NO_REPLY")
        return {"success": True, "skipped": True, "reason": f"Already traded in {session} session today"}
    
    # Check for existing positions (just for logging)
    client = HyperliquidClient()
    positions = client.get_positions()
    
    if positions:
        position_list = ", ".join([f"{p.coin} {'LONG' if p.size > 0 else 'SHORT'}" for p in positions])
        print(f"\n📊 Existing positions: {position_list}")
        print("   Will skip those assets, check others...")
    
    # Scan for breakouts (automatically skips assets with positions)
    print("\n🔍 Scanning for breakouts...")
    breakout = scan_for_breakouts()
    
    if not breakout:
        print("   No valid breakouts found.")
        send_telegram_message(f"🔍 APEX {session.upper()}: Kein Breakout gefunden - kein Trade")
        print("NO_REPLY")
        return {"success": False, "reason": "No breakout"}
    
    print(f"\n🎯 BREAKOUT DETECTED!")
    print(f"   Asset: {breakout['asset']}")
    print(f"   Direction: {breakout['direction'].upper()}")
    print(f"   Current: ${breakout['current_price']:,.2f}")
    print(f"   Box: ${breakout['box_low']:,.2f} - ${breakout['box_high']:,.2f}")
    print(f"   Breakout Size: ${breakout['breakout_size']:,.2f}")
    
    # Execute trade
    print(f"\n🚀 Executing {breakout['direction']} trade...")
    
    result = execute_breakout_trade(
        breakout['asset'],
        breakout['direction'],
        breakout['current_price'],
        breakout['box_high'],
        breakout['box_low']
    )
    
    if result["success"]:
        print(f"\n✅ TRADE EXECUTED!")
        print(f"   Entry: ${result['entry']:,.2f}")
        print(f"   Size: {result['size']}")
        print(f"   Stop-Loss: ${result['stop_loss']:,.2f} (Risk: ${MAX_RISK_USD:.0f})")
        print(f"   Take-Profit: ${result['take_profit']:,.2f} (Reward: ${MAX_RISK_USD * 2:.0f})")
        print(f"   Ratio: 2:1")
        print(f"   SL Placed: {result['sl_placed']} | TP Placed: {result['tp_placed']}")
        print(f"\n💡 Position Monitor läuft automatisch alle 30 Min")

        direction_emoji = "🟢" if result["direction"] == "long" else "🔴"
        msg = (
            f"🚀 APEX TRADE EXECUTED!\n\n"
            f"{direction_emoji} {result['asset']} {result['direction'].upper()}\n"
            f"Entry: ${result['entry']:,.2f}\n"
            f"Size: {result['size']}\n"
            f"Stop-Loss: ${result['stop_loss']:,.2f} (Risk: ${MAX_RISK_USD:.0f})\n"
            f"Take-Profit: ${result['take_profit']:,.2f} (Reward: ${MAX_RISK_USD * 2:.0f})\n"
            f"Ratio: 2:1\n"
            f"SL: {'✅' if result['sl_placed'] else '❌'} | TP: {'✅' if result['tp_placed'] else '❌'}"
        )
        send_telegram_message(msg)

    else:
        print(f"\n❌ TRADE FAILED: {result.get('error')}")
        send_telegram_message(f"❌ APEX TRADE FAILED: {result.get('error')}")

    print("NO_REPLY")
    return result


if __name__ == "__main__":
    try:
        result = main()
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message(f"💥 APEX autonomous_trade.py ERROR: {e}")
        print("NO_REPLY")
        sys.exit(1)
