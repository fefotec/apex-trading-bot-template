#!/usr/bin/env python3
"""
APEX - Session Summary Reporter
================================
Sendet freundliche Session-Zusammenfassungen an Christian.
Wird von Final-Check Crons aufgerufen.
"""

import os
import sys
import json
from datetime import datetime
from hyperliquid_client import HyperliquidClient

# Config
BOXES_FILE = "/data/.openclaw/workspace/projects/apex-trading/data/opening_range_boxes.json"
TRADES_FILE = "/data/.openclaw/workspace/projects/apex-trading/data/trades.json"
CAPITAL_FILE = "/data/.openclaw/workspace/projects/apex-trading/data/capital_tracking.json"

ASSETS = ["BTC", "ETH", "SOL", "AVAX"]
ASSET_PRIORITY = {asset: i for i, asset in enumerate(ASSETS)}

SESSION_NAMES = {
    "tokyo": "🌏 Tokyo",
    "eu": "🇪🇺 Europa", 
    "us": "🇺🇸 USA"
}

SESSION_EMOJIS = {
    "tokyo": "🌏",
    "eu": "🇪🇺",
    "us": "🇺🇸"
}


def load_boxes():
    """Lade Opening Range Boxen"""
    if not os.path.exists(BOXES_FILE):
        return {}
    
    with open(BOXES_FILE, 'r') as f:
        return json.load(f)


def get_balance():
    """Hole aktuelle Balance"""
    client = HyperliquidClient()
    return client.get_balance()


def get_capital_tracking():
    """Lade Capital Tracking (Einzahlungen/Abhebungen)"""
    if not os.path.exists(CAPITAL_FILE):
        return {
            "start_capital": 1721.80,
            "adjusted_start_capital": 2300.54,
            "total_deposits": 578.74,
            "total_withdrawals": 0
        }
    
    with open(CAPITAL_FILE, 'r') as f:
        return json.load(f)


def calculate_pnl(current_balance):
    """Berechne P&L (bereinigt um Einzahlungen/Abhebungen)"""
    capital = get_capital_tracking()
    
    # P&L = Current Balance - (Start + Deposits - Withdrawals)
    adjusted_start = capital["adjusted_start_capital"]
    
    pnl = current_balance - adjusted_start
    pnl_pct = (pnl / adjusted_start) * 100
    
    return {
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "start_capital": capital["start_capital"],
        "adjusted_start": adjusted_start,
        "total_deposits": capital["total_deposits"]
    }


def check_breakout(asset, price, box_high, box_low):
    """
    Check ob Breakout vorliegt
    Returns: "long", "short", or None
    """
    if asset in ["BTC", "ETH"]:
        threshold = 50
    else:
        threshold = price * 0.02  # 2%
    
    if price > box_high + threshold:
        return "long"
    elif price < box_low - threshold:
        return "short"
    return None


def has_traded_in_session(session):
    """Check ob in dieser Session bereits getradet wurde"""
    if not os.path.exists(TRADES_FILE):
        return False, None
    
    with open(TRADES_FILE, 'r') as f:
        trades = json.load(f)
    
    today = datetime.now().date().isoformat()
    
    for trade in trades:
        trade_date = trade["timestamp"][:10]
        trade_session = trade.get("session", "unknown")
        
        if trade_date == today and trade_session == session:
            return True, trade
    
    return False, None


def get_session_breakouts():
    """Scanne alle Assets auf Breakouts"""
    boxes = load_boxes()
    
    if not boxes:
        return {}
    
    client = HyperliquidClient()
    breakouts = {}
    
    for asset in ASSETS:
        if asset not in boxes:
            breakouts[asset] = {"status": "no_box", "direction": None}
            continue
        
        box = boxes[asset]
        current_price = client.get_price(asset)
        
        direction = check_breakout(asset, current_price, box["high"], box["low"])
        
        if direction:
            breakout_size = abs(current_price - (box["high"] if direction == "long" else box["low"]))
            breakouts[asset] = {
                "status": "breakout",
                "direction": direction,
                "price": current_price,
                "box_high": box["high"],
                "box_low": box["low"],
                "breakout_size": breakout_size
            }
        else:
            breakouts[asset] = {
                "status": "no_breakout",
                "direction": None,
                "price": current_price
            }
    
    return breakouts


def format_summary(session):
    """Erstelle freundliche Zusammenfassung"""
    emoji = SESSION_EMOJIS.get(session, "📊")
    name = SESSION_NAMES.get(session, session.upper())
    
    # Check ob getradet wurde
    traded, trade_data = has_traded_in_session(session)
    
    # Hole Breakouts
    breakouts = get_session_breakouts()
    
    # Balance
    balance = get_balance()
    
    # Header
    lines = [
        f"{emoji} **{name} Session Abschluss**",
        ""
    ]
    
    # Breakouts
    lines.append("**Breakout-Check:**")
    any_breakout = False
    
    for asset in ASSETS:
        if asset not in breakouts:
            lines.append(f"  • {asset}: ⚠️ Keine Box-Daten")
            continue
        
        b = breakouts[asset]
        
        if b["status"] == "breakout":
            any_breakout = True
            direction_icon = "🔴" if b["direction"] == "long" else "🔵"
            direction_text = b["direction"].upper()
            lines.append(f"  • {asset}: {direction_icon} **{direction_text}** Breakout (${b['breakout_size']:.2f})")
        else:
            lines.append(f"  • {asset}: ✅ Kein Breakout")
    
    lines.append("")
    
    # Trade Status
    if traded:
        asset = trade_data.get("asset", "?")
        direction = trade_data.get("direction", "?").upper()
        entry = trade_data.get("entry_price", 0)
        lines.append(f"**Trade:** ✅ **{asset} {direction}** @ ${entry:,.2f}")
    else:
        if any_breakout:
            # Warum nicht getradet?
            client = HyperliquidClient()
            positions = client.get_positions()
            
            if positions:
                lines.append(f"**Trade:** ❌ Nicht ausgeführt")
                lines.append(f"**Grund:** Position bereits offen ({positions[0].coin} {('LONG' if positions[0].size > 0 else 'SHORT')})")
            else:
                lines.append(f"**Trade:** ❌ Nicht ausgeführt")
                lines.append(f"**Grund:** Unbekannt (Script-Check nötig!)")
        else:
            lines.append(f"**Trade:** ✅ Korrekt geskippt (kein Breakout)")
    
    lines.append("")
    
    # Balance & P&L
    lines.append(f"**Balance:** ${balance:,.2f}")
    
    pnl_data = calculate_pnl(balance)
    pnl = pnl_data["pnl"]
    pnl_pct = pnl_data["pnl_pct"]
    
    if pnl >= 0:
        pnl_icon = "📈"
        pnl_text = f"+${pnl:.2f}"
    else:
        pnl_icon = "📉"
        pnl_text = f"-${abs(pnl):.2f}"
    
    lines.append(f"**Gesamt P&L:** {pnl_icon} {pnl_text} ({pnl_pct:+.2f}%)")
    lines.append(f"_(Start: ${pnl_data['adjusted_start']:,.2f})_")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: session_summary.py <tokyo|eu|us>")
        sys.exit(1)
    
    session = sys.argv[1].lower()
    
    if session not in ["tokyo", "eu", "us"]:
        print(f"Invalid session: {session}")
        sys.exit(1)
    
    summary = format_summary(session)
    print(summary)

    # Send directly to Telegram
    try:
        from telegram_sender import send_telegram_message
        send_telegram_message(summary)
    except Exception as e:
        print(f"⚠️  Failed to send to Telegram: {e}")

    print("NO_REPLY")


if __name__ == "__main__":
    main()
