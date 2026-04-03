#!/usr/bin/env python3
"""
APEX - Capital.com Autonomous Gold Trading Script
==================================================
Wird von Cron Jobs aufgerufen, checkt Gold-Breakouts auf Capital.com, platziert Orders autonom.
Identische ORB-Strategie wie autonomous_trade.py, aber nur fuer XAUUSD.

Session: London Open (09:30-11:00 Berlin / 07:30-09:00 UTC)
30m Opening Range (09:00-09:30 Berlin), Breakout-Checks ab 09:45

Capital.com Besonderheit: SL und TP werden direkt beim Eroeffnen der Position gesetzt,
nicht als separate Trigger-Orders. Das vereinfacht die Logik erheblich und eliminiert
das Risiko einer fehlgeschlagenen SL-Platzierung.

WICHTIG: Bestehende autonomous_trade.py (Hyperliquid) wird NICHT angefasst.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capitalcom_client import CapitalComClient, GOLD_EPIC
from capitalcom_place_order import place_market_order, close_position
from telegram_sender import send_telegram_message

# Config
MAX_RISK_PCT = 0.02  # 2% risk per trade
KILL_SWITCH_DRAWDOWN = 0.50  # 50% drawdown = stop trading
SPREAD_LIMIT = 0.05  # 0.05% max spread (Gold hat enge Spreads)

# ATR-Parameter (identisch zu Krypto)
MIN_BOX_ATR_RATIO = 0.6
BREAKOUT_ATR_MULTIPLIER = 0.5

# Pfade
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
if os.path.exists("/data/.openclaw/workspace/projects/apex-trading/data"):
    DATA_DIR = "/data/.openclaw/workspace/projects/apex-trading/data"

GOLD_BOXES_FILE = os.path.join(DATA_DIR, "gold_opening_range_boxes.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")
GOLD_CAPITAL_FILE = os.path.join(DATA_DIR, "gold_capital_tracking.json")


def get_adjusted_start_capital():
    """Hole adjusted start capital aus gold_capital_tracking.json"""
    if os.path.exists(GOLD_CAPITAL_FILE):
        try:
            with open(GOLD_CAPITAL_FILE, 'r') as f:
                tracking = json.load(f)
            return tracking.get("adjusted_start_capital", tracking.get("start_capital", 500))
        except (json.JSONDecodeError, KeyError):
            pass
    return 500  # Fallback


def check_kill_switch(client):
    """
    Kill-Switch: Pruefe ob Drawdown > 50% -- wenn ja, NICHT traden.

    Returns:
        tuple: (is_safe, balance, start_capital)
    """
    balance = client.get_balance()
    start_capital = get_adjusted_start_capital()

    if balance <= 0:
        return False, 0, start_capital

    drawdown = 1 - (balance / start_capital)

    if drawdown >= KILL_SWITCH_DRAWDOWN:
        msg = (
            f"  APEX GOLD KILL-SWITCH AKTIVIERT!\n\n"
            f"Exchange: Capital.com\n"
            f"Drawdown: {drawdown*100:.1f}%\n"
            f"Balance: ${balance:,.2f}\n"
            f"Start-Kapital: ${start_capital:,.2f}\n\n"
            f"  Alle Gold-Trades gestoppt!\n"
            f"Manuelles Eingreifen erforderlich."
        )
        print(f"\n  KILL-SWITCH: Drawdown {drawdown*100:.1f}% >= {KILL_SWITCH_DRAWDOWN*100:.0f}%")
        send_telegram_message(msg)
        return False, balance, start_capital

    return True, balance, start_capital


def load_gold_boxes():
    """Lade Gold Opening Range Boxen"""
    if not os.path.exists(GOLD_BOXES_FILE):
        return {}

    with open(GOLD_BOXES_FILE, 'r') as f:
        return json.load(f)


def is_gold_session():
    """Pruefe ob wir in der London Gold Session sind (07:00-09:00 UTC = 09:00-11:00 Berlin CEST)"""
    now = datetime.now(timezone.utc)
    return 7 <= now.hour < 9 and now.weekday() < 5  # Mo-Fr, UTC


def has_traded_today_gold():
    """Check ob heute bereits ein Gold-Trade stattgefunden hat"""
    if not os.path.exists(TRADES_FILE):
        return False

    with open(TRADES_FILE, 'r') as f:
        trades = json.load(f)

    today = datetime.now().date().isoformat()

    for trade in trades:
        trade_date = trade["timestamp"][:10]
        if (trade_date == today
                and trade.get("exchange") == "capitalcom"
                and trade.get("session") == "gold_london"):
            return True

    return False


def log_trade(trade_data):
    """Logge Trade in gemeinsame trades.json"""
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)

    trades = []
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, 'r') as f:
            trades = json.load(f)

    trades.append({
        **trade_data,
        "exchange": "capitalcom",
        "session": "gold_london",
        "strategy": "ORB",
        "timestamp": datetime.now().isoformat()
    })

    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)


def check_breakout(current_price, box_high, box_low, threshold):
    """Check ob Gold aus Box ausgebrochen ist"""
    if current_price > box_high + threshold:
        return "long"
    elif current_price < box_low - threshold:
        return "short"
    return None


def calculate_atr(client, epic=GOLD_EPIC, interval="15m", periods=14):
    """Berechne ATR (Average True Range) fuer Gold"""
    try:
        candles = client.get_candles(epic, interval=interval, limit=periods + 1)
        if not candles or len(candles) < periods + 1:
            return None

        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]["high"]
            low = candles[i]["low"]
            prev_close = candles[i - 1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return sum(true_ranges[-periods:]) / min(periods, len(true_ranges))
    except Exception as e:
        print(f"   ATR-Berechnung fehlgeschlagen: {e}")
        return None


def scan_for_gold_breakout(client):
    """
    Scanne Gold auf Breakout.
    Nutzt ATR-basierte Thresholds, Candle-Close Confirmation, Spread-Check.
    """
    boxes = load_gold_boxes()

    if not boxes or "XAUUSD" not in boxes:
        print("   Keine Gold-Box vorhanden")
        return None

    box = boxes["XAUUSD"]

    # Check ob bereits eine Gold-Position offen ist
    positions = client.get_positions()
    gold_positions = [p for p in positions if p.epic == GOLD_EPIC]
    if gold_positions:
        print(f"   Gold-Position bereits offen -- Skip")
        return None

    current_price = client.get_price(GOLD_EPIC)
    if current_price <= 0:
        print("   Gold-Preis nicht verfuegbar")
        return None

    box_size = box["high"] - box["low"]

    # ATR-basierter Threshold
    atr = calculate_atr(client, GOLD_EPIC)
    if atr and atr > 0:
        threshold = atr * BREAKOUT_ATR_MULTIPLIER

        if box_size < atr * MIN_BOX_ATR_RATIO:
            print(f"   Gold: Box zu eng (${box_size:,.2f} < ATR ${atr:,.2f}) -- Skip")
            return None

        print(f"   Gold: ATR=${atr:,.2f}, Threshold=${threshold:,.2f}, Box=${box_size:,.2f}")
    else:
        threshold = current_price * 0.003
        print(f"   Gold: ATR nicht verfuegbar, Fallback ${threshold:,.2f}")

    direction = check_breakout(current_price, box["high"], box["low"], threshold)

    if not direction:
        print(f"   Gold: Kein Breakout (Preis ${current_price:,.2f} in Box ${box['low']:,.2f}-${box['high']:,.2f})")
        return None

    # === DOPPELTE CANDLE-CLOSE CONFIRMATION ===
    # Gold macht haeufiger Fake-Breakouts als Krypto ("Turtle Soups").
    # Deshalb muessen die LETZTEN ZWEI abgeschlossenen 5m-Candles
    # ausserhalb der Box geschlossen haben -- nicht nur eine.
    try:
        candles_5m = client.get_candles(GOLD_EPIC, interval="5m", limit=3)
        if candles_5m and len(candles_5m) >= 3:
            # Die letzten 2 abgeschlossenen Candles (nicht die aktuelle)
            candle_1 = candles_5m[-3]  # vorvorletzte = zweitletzte abgeschlossene
            candle_2 = candles_5m[-2]  # vorletzte = letzte abgeschlossene

            if direction == "long":
                if candle_1["close"] <= box["high"] or candle_2["close"] <= box["high"]:
                    print(f"   Gold: Doppel-Confirmation FEHLT -- "
                          f"C1=${candle_1['close']:,.2f} C2=${candle_2['close']:,.2f} vs Box High ${box['high']:,.2f} -- Skip")
                    return None
            elif direction == "short":
                if candle_1["close"] >= box["low"] or candle_2["close"] >= box["low"]:
                    print(f"   Gold: Doppel-Confirmation FEHLT -- "
                          f"C1=${candle_1['close']:,.2f} C2=${candle_2['close']:,.2f} vs Box Low ${box['low']:,.2f} -- Skip")
                    return None

            print(f"   Gold: Doppelte Candle-Confirmation OK "
                  f"(C1=${candle_1['close']:,.2f} C2=${candle_2['close']:,.2f})")
    except Exception as e:
        print(f"   Candle-Check fehlgeschlagen: {e} -- fahre fort")

    # === SPREAD-CHECK ===
    try:
        book = client.get_orderbook(GOLD_EPIC)
        spread = book.get("spread_pct", 0)
        if spread > SPREAD_LIMIT:
            print(f"   Gold: Spread zu hoch ({spread:.3f}% > {SPREAD_LIMIT}%) -- Skip")
            return None
        print(f"   Gold: Spread OK ({spread:.4f}%)")
    except Exception as e:
        print(f"   Spread-Check fehlgeschlagen: {e} -- fahre fort")

    return {
        "asset": "XAUUSD",
        "epic": GOLD_EPIC,
        "direction": direction,
        "current_price": current_price,
        "box_high": box["high"],
        "box_low": box["low"],
        "breakout_size": abs(current_price - (box["high"] if direction == "long" else box["low"])),
        "atr": atr,
        "threshold": threshold
    }


def execute_gold_trade(client, breakout, risk_usd):
    """
    Platziere Gold Breakout Trade mit SL und TP.

    Capital.com Vorteil: SL und TP werden direkt bei der Position gesetzt.
    Kein separates SL/TP-Placement noetig = kein Rollback-Risiko!
    """
    direction = breakout["direction"]
    entry_price = breakout["current_price"]
    box_high = breakout["box_high"]
    box_low = breakout["box_low"]

    # Calculate SL
    if direction == "long":
        stop_loss = box_low - 2  # $2 unter Box
    else:
        stop_loss = box_high + 2  # $2 ueber Box

    # Position Size
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit == 0:
        return {"success": False, "error": "Risk per unit is 0"}

    size = risk_usd / risk_per_unit

    # Min-Size pruefen
    info = client.get_market_info(GOLD_EPIC)
    min_size = info.get("min_size", 0.01)

    # Runden auf 2 Dezimalen
    size = round(size, 2)

    if size < min_size:
        return {"success": False, "error": f"Size {size} unter Min-Size {min_size}"}

    # Calculate Take-Profit (2:1 Risk/Reward)
    reward_per_unit = risk_per_unit * 2
    if direction == "long":
        take_profit = entry_price + reward_per_unit
    else:
        take_profit = entry_price - reward_per_unit

    # Place order MIT SL und TP direkt dabei!
    is_buy = (direction == "long")
    order_result = place_market_order(
        GOLD_EPIC, is_buy, size,
        stop_loss=stop_loss,
        take_profit=take_profit
    )

    if not order_result["success"]:
        return order_result

    actual_entry = order_result.get("avg_price", entry_price)

    # Log trade
    log_trade({
        "asset": "XAUUSD",
        "direction": direction,
        "entry_price": actual_entry,
        "size": size,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_usd": risk_usd,
        "reward_usd": risk_usd * 2,
        "ratio": "2:1",
        "deal_id": order_result.get("deal_id"),
        "deal_reference": order_result.get("deal_reference"),
    })

    return {
        "success": True,
        "asset": "XAUUSD",
        "direction": direction,
        "entry": actual_entry,
        "size": size,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_usd": risk_usd,
        "sl_placed": True,  # Bei Capital.com immer zusammen mit Order
        "tp_placed": True,
    }


def main():
    """Main execution"""
    print("=" * 60)
    print("APEX - Gold Autonomous Trade Check (Capital.com)")
    print("=" * 60)

    # Check session
    if not is_gold_session():
        print("  Nicht in der Gold-Session (London Open 07:00-09:00 UTC)!")
        print("NO_REPLY")
        return {"success": True, "skipped": True, "reason": "Outside gold trading hours"}

    print("  Session: GOLD LONDON OPEN")

    # Initialize client
    client = CapitalComClient()
    if not client.is_ready:
        print("  Capital.com nicht verbunden!")
        send_telegram_message("  APEX Gold: Capital.com nicht verbunden!")
        print("NO_REPLY")
        return {"success": False, "reason": "Capital.com not connected"}

    # === KILL-SWITCH ===
    is_safe, balance, start_capital = check_kill_switch(client)
    if not is_safe:
        print("NO_REPLY")
        return {"success": False, "reason": "Kill-switch activated"}

    # Dynamic risk
    risk_usd = balance * MAX_RISK_PCT
    print(f"  Balance: {balance:,.2f} | Risk: {risk_usd:,.2f} ({MAX_RISK_PCT*100:.0f}%)")

    # Check ob heute bereits getradet
    if has_traded_today_gold():
        print(f"\n  SKIP: Bereits einen Gold-Trade heute!")
        send_telegram_message("  APEX Gold: Skip - bereits getradet heute")
        print("NO_REPLY")
        return {"success": True, "skipped": True, "reason": "Already traded gold today"}

    # Scan for gold breakout
    print("\n  Scanning Gold fuer Breakout...")
    breakout = scan_for_gold_breakout(client)

    if not breakout:
        print("   Kein Gold-Breakout gefunden.")
        send_telegram_message("  APEX Gold London: Kein Breakout - kein Trade")
        print("NO_REPLY")
        return {"success": False, "reason": "No breakout"}

    print(f"\n  GOLD BREAKOUT DETECTED!")
    print(f"   Direction: {breakout['direction'].upper()}")
    print(f"   Current: ${breakout['current_price']:,.2f}")
    print(f"   Box: ${breakout['box_low']:,.2f} - ${breakout['box_high']:,.2f}")

    # Execute trade
    print(f"\n  Executing Gold {breakout['direction']} trade (Risk: {risk_usd:,.2f})...")

    result = execute_gold_trade(client, breakout, risk_usd)

    if result["success"]:
        print(f"\n  GOLD TRADE EXECUTED!")
        print(f"   Entry: ${result['entry']:,.2f}")
        print(f"   Size: {result['size']}")
        print(f"   SL: ${result['stop_loss']:,.2f} | TP: ${result['take_profit']:,.2f}")

        msg = (
            f"  APEX GOLD TRADE (Capital.com)!\n\n"
            f"{'LONG' if result['direction'] == 'long' else 'SHORT'} XAUUSD\n"
            f"Entry: ${result['entry']:,.2f}\n"
            f"Size: {result['size']}\n"
            f"Stop-Loss: ${result['stop_loss']:,.2f} (Risk: {risk_usd:.0f})\n"
            f"Take-Profit: ${result['take_profit']:,.2f} (Reward: {risk_usd * 2:.0f})\n"
            f"Ratio: 2:1 | SL+TP: gesetzt"
        )
        send_telegram_message(msg)
    else:
        print(f"\n  GOLD TRADE FAILED: {result.get('error')}")
        send_telegram_message(f"  APEX GOLD TRADE FAILED: {result.get('error')}")

    print("NO_REPLY")
    return result


if __name__ == "__main__":
    try:
        result = main()
        try:
            from healthcheck import ping
            ping("gold_london")
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message(f"  APEX capitalcom_autonomous_trade.py ERROR: {e}")
        try:
            from healthcheck import ping
            ping("gold_london", "fail")
        except Exception:
            pass
        print("NO_REPLY")
        sys.exit(1)
