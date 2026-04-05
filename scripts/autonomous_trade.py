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
MAX_RISK_PCT = 0.02  # 2% risk per trade
KILL_SWITCH_DRAWDOWN = 0.50  # 50% drawdown = stop trading

# Pfade (dynamisch mit Server-Fallback)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
if os.path.exists("/data/.openclaw/workspace/projects/apex-trading/data"):
    DATA_DIR = "/data/.openclaw/workspace/projects/apex-trading/data"

BOXES_FILE = os.path.join(DATA_DIR, "opening_range_boxes.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")
CAPITAL_TRACKING_FILE = os.path.join(DATA_DIR, "capital_tracking.json")


def get_adjusted_start_capital():
    """Hole adjusted start capital aus capital_tracking.json (Startkapital + Einzahlungen)"""
    if os.path.exists(CAPITAL_TRACKING_FILE):
        try:
            with open(CAPITAL_TRACKING_FILE, 'r') as f:
                tracking = json.load(f)
            return tracking.get("adjusted_start_capital", tracking.get("start_capital", 2300))
        except (json.JSONDecodeError, KeyError):
            pass
    return 2300  # Fallback


def get_total_account_value(client):
    """
    Hole den GESAMTEN Kontowert: Spot-Balance + Margin-Account-Value.

    Wichtig: Beim Perpetual-Trading wandert Kapital vom Spot-Account
    in den Margin-Account als Collateral. get_balance() allein wuerde
    bei offenen Positionen faelschlich ~0 zeigen.
    """
    spot = client.get_balance()

    # Margin Account Value (Collateral + unrealized PnL)
    margin_value = 0.0
    try:
        state = client.get_account_state()
        if "error" not in state:
            margin_summary = state.get("marginSummary", {})
            margin_value = float(margin_summary.get("accountValue", 0))
    except Exception:
        pass

    return spot + margin_value


def check_kill_switch(client):
    """
    Kill-Switch: Pruefe ob Drawdown > 50% -- wenn ja, NICHT traden.

    Nutzt Spot + Margin Balance um den echten Kontowert zu ermitteln.

    Returns:
        tuple: (is_safe, balance, start_capital)
    """
    balance = get_total_account_value(client)
    start_capital = get_adjusted_start_capital()

    if balance <= 0:
        return False, 0, start_capital

    drawdown = 1 - (balance / start_capital)

    if drawdown >= KILL_SWITCH_DRAWDOWN:
        msg = (
            f"🚨 APEX KILL-SWITCH AKTIVIERT!\n\n"
            f"Drawdown: {drawdown*100:.1f}%\n"
            f"Balance: ${balance:,.2f}\n"
            f"Start-Kapital: ${start_capital:,.2f}\n\n"
            f"⛔ Alle Trades gestoppt!\n"
            f"Manuelles Eingreifen erforderlich."
        )
        print(f"\n🚨 KILL-SWITCH: Drawdown {drawdown*100:.1f}% >= {KILL_SWITCH_DRAWDOWN*100:.0f}%")
        send_telegram_message(msg)
        return False, balance, start_capital

    return True, balance, start_capital


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


def execute_breakout_trade(asset, direction, entry_price, box_high, box_low, risk_usd):
    """
    Platziere Breakout Trade mit Stop-Loss und Take-Profit

    SICHERHEIT: Wenn SL-Platzierung fehlschlaegt, wird die Position
    sofort per Market Order geschlossen (Rollback).

    Returns:
        dict: Trade result
    """
    # Calculate SL: Prozentual statt flat $10 (funktioniert fuer alle Assets)
    box_range = box_high - box_low
    sl_buffer = max(box_range * 0.1, entry_price * 0.001)  # 10% der Box oder 0.1% vom Preis
    if direction == "long":
        stop_loss = box_low - sl_buffer
    else:
        stop_loss = box_high + sl_buffer

    # Calculate position size
    size = calculate_position_size(risk_usd, entry_price, stop_loss)

    # Size runden ueber place_order Regeln (zentral definiert)
    from place_order import round_size, ASSET_RULES
    size = round_size(asset, size)
    rules = ASSET_RULES.get(asset, {"min_size": 0.01})

    # Minimum size + Max position value check
    if size < rules["min_size"]:
        return {"success": False, "error": f"Size too small ({size} < {rules['min_size']})"}

    max_position_value = entry_price * size
    balance = risk_usd / MAX_RISK_PCT  # Rueckrechnung aus Risk
    if max_position_value > balance * 25:  # Max 25x Leverage (Hyperliquid erlaubt bis 50x)
        return {"success": False, "error": f"Position too large (${max_position_value:.0f} > 25x ${balance:.0f})"}

    # Place market order
    is_buy = (direction == "long")
    order_result = place_market_order(asset, is_buy, size, reduce_only=False)

    if not order_result["success"]:
        return order_result

    actual_entry = order_result["avg_price"]

    # === SPLIT TAKE-PROFIT ===
    # TP1: Halbe Position bei 1:1 R:R (sichert das Risiko ab)
    # TP2: Andere Haelfte bei 3:1 R:R (der "Runner" fuer grosse Moves)
    # Der Monitor uebernimmt danach ATR-Trailing fuer den Runner.
    risk_per_coin = abs(actual_entry - stop_loss)

    if direction == "long":
        take_profit_1 = actual_entry + risk_per_coin * 1.0   # 1:1
        take_profit_2 = actual_entry + risk_per_coin * 3.0   # 3:1
    else:
        take_profit_1 = actual_entry - risk_per_coin * 1.0   # 1:1
        take_profit_2 = actual_entry - risk_per_coin * 3.0   # 3:1

    # Halbe Position pro TP
    from place_order import round_size as _round_size
    size_tp1 = _round_size(asset, size / 2)
    size_tp2 = _round_size(asset, size - size_tp1)  # Rest (vermeidet Rundungsfehler)

    # Place stop-loss (volle Position)
    sl_result = place_stop_loss(asset, stop_loss, size)

    # KRITISCH: Wenn SL fehlschlaegt, Position sofort schliessen!
    if not sl_result["success"]:
        print(f"\n🚨 SL-PLATZIERUNG FEHLGESCHLAGEN! Schliesse Position sofort...")

        # 3 Versuche fuer Rollback
        rollback = {"success": False}
        for attempt in range(1, 4):
            print(f"   Rollback-Versuch {attempt}/3...")
            rollback = place_market_order(asset, not is_buy, size, reduce_only=True)
            if rollback["success"]:
                break
            if attempt < 3:
                import time
                time.sleep(2)

        msg = (
            f"🚨 APEX SL-ROLLBACK!\n\n"
            f"Stop-Loss fuer {asset} {direction.upper()} konnte nicht platziert werden.\n"
            f"SL-Fehler: {sl_result.get('error', 'unbekannt')}\n\n"
            f"Position geschlossen: {'Erfolg' if rollback['success'] else '⛔ FEHLGESCHLAGEN nach 3 Versuchen!'}\n"
            f"Entry: ${actual_entry:,.2f}"
        )
        if not rollback["success"]:
            msg += "\n\n⛔ ACHTUNG: UNGESICHERTE POSITION! Sofort manuell eingreifen!"
        send_telegram_message(msg)

        log_trade({
            "asset": asset,
            "direction": direction,
            "entry_price": actual_entry,
            "size": size,
            "stop_loss": stop_loss,
            "risk_usd": risk_usd,
            "order_result": order_result,
            "sl_result": sl_result,
            "rollback": True,
            "rollback_result": rollback
        })

        return {
            "success": False,
            "error": f"SL placement failed - position rolled back ({'OK' if rollback['success'] else 'ROLLBACK FAILED - MANUAL ACTION NEEDED'})",
            "rollback": rollback
        }

    # Place Take-Profits (Split: 2 separate Orders)
    tp1_result = place_take_profit(asset, take_profit_1, size_tp1)
    tp2_result = place_take_profit(asset, take_profit_2, size_tp2)

    # Log trade
    log_trade({
        "asset": asset,
        "direction": direction,
        "entry_price": actual_entry,
        "size": size,
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "size_tp1": size_tp1,
        "size_tp2": size_tp2,
        "risk_usd": risk_usd,
        "reward_usd_tp1": risk_usd * 1,
        "reward_usd_tp2": risk_usd * 3,
        "ratio": "Split 1:1 + 3:1",
        "order_result": order_result,
        "sl_result": sl_result,
        "tp1_result": tp1_result,
        "tp2_result": tp2_result
    })

    return {
        "success": True,
        "asset": asset,
        "direction": direction,
        "entry": actual_entry,
        "size": size,
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "size_tp1": size_tp1,
        "size_tp2": size_tp2,
        "risk_usd": risk_usd,
        "sl_placed": sl_result["success"],
        "tp1_placed": tp1_result["success"],
        "tp2_placed": tp2_result["success"]
    }


def calculate_atr(client, asset, interval="15m", periods=14):
    """
    Berechne ATR (Average True Range) fuer ein Asset.
    Misst die durchschnittliche Volatilitaet -- wird als Breakout-Threshold genutzt.

    Returns:
        float: ATR Wert oder None bei Fehler
    """
    try:
        candles = client.get_candles(asset, interval=interval, limit=periods + 1)
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
        print(f"   ⚠️  ATR-Berechnung fehlgeschlagen fuer {asset}: {e}")
        return None


# Minimum Box-Groesse: Wenn die Opening Range kleiner als 0.6x ATR ist,
# ist sie zu eng und Breakouts sind wahrscheinlich Noise.
# (1.0 war zu konservativ -- filterte BTC Tokyo Sessions fast immer raus)
MIN_BOX_ATR_RATIO = 0.6

# Breakout-Threshold: Preis muss mindestens 0.5x ATR ueber/unter der Box sein
BREAKOUT_ATR_MULTIPLIER = 0.5


DEFAULT_PRIORITY = ["BTC", "ETH", "SOL", "AVAX"]
MIN_TRADES_FOR_RANKING = 3  # Mindestens 3 Trades bevor ein Coin umpriorisiert wird
RANKING_LOOKBACK = 20  # Letzte 20 Trades pro Coin betrachten


def get_dynamic_priority():
    """
    Sortiere Assets nach Performance der letzten Trades.
    Coins mit besserer Win-Rate kommen zuerst.
    Coins mit weniger als MIN_TRADES_FOR_RANKING Trades behalten ihren Default-Platz.
    """
    if not os.path.exists(TRADES_FILE):
        print(f"   📊 Prioritaet: {' > '.join(DEFAULT_PRIORITY)} (Default, keine Trades)")
        return DEFAULT_PRIORITY

    try:
        with open(TRADES_FILE, 'r') as f:
            all_trades = json.load(f)
    except (json.JSONDecodeError, IOError):
        return DEFAULT_PRIORITY

    # Nur geschlossene Trades mit Exit-Daten
    closed = [t for t in all_trades if "exit_pnl" in t]

    # Stats pro Coin berechnen (nur letzte RANKING_LOOKBACK Trades)
    coin_stats = {}
    for coin in DEFAULT_PRIORITY:
        coin_trades = [t for t in closed if t.get("asset") == coin]
        recent = coin_trades[-RANKING_LOOKBACK:]

        if len(recent) < MIN_TRADES_FOR_RANKING:
            coin_stats[coin] = {"win_rate": 0, "pnl": 0, "trades": len(recent), "ranked": False}
        else:
            wins = sum(1 for t in recent if t["exit_pnl"] > 0)
            total_pnl = sum(t["exit_pnl"] for t in recent)
            coin_stats[coin] = {
                "win_rate": wins / len(recent) * 100,
                "pnl": total_pnl,
                "trades": len(recent),
                "ranked": True,
            }

    # Sortieren: gerankte Coins nach Win-Rate (absteigend), dann nach P&L
    # Ungerankte Coins behalten ihre Default-Position
    ranked = [c for c in DEFAULT_PRIORITY if coin_stats[c]["ranked"]]
    unranked = [c for c in DEFAULT_PRIORITY if not coin_stats[c]["ranked"]]

    ranked.sort(key=lambda c: (coin_stats[c]["win_rate"], coin_stats[c]["pnl"]), reverse=True)

    # Zusammenfuegen: gerankte zuerst, dann ungerankte in Default-Reihenfolge
    priority = ranked + unranked

    # Log
    parts = []
    for c in priority:
        s = coin_stats[c]
        if s["ranked"]:
            parts.append(f"{c}({s['win_rate']:.0f}%/{s['trades']}T)")
        else:
            parts.append(f"{c}(neu)")
    print(f"   📊 Prioritaet: {' > '.join(parts)}")

    return priority


def scan_for_breakouts():
    """
    Scanne alle Assets auf Breakouts.
    Nutzt ATR-basierte Thresholds statt fester Dollar-Betraege.
    Filtert zu enge Boxen automatisch raus.

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

    # Dynamische Prioritaet basierend auf den letzten 20 Trades pro Coin
    priority = get_dynamic_priority()

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
        box_size = box["high"] - box["low"]

        # Minimum Box-Groesse: mindestens 0.2% vom Preis (absolute Untergrenze)
        min_box_pct = current_price * 0.002
        if box_size < min_box_pct:
            print(f"   ⏭️  {asset}: Box zu eng (${box_size:.4f} < 0.2% ${min_box_pct:.4f}) -- Skip")
            continue

        # ATR-basierter Threshold
        atr = calculate_atr(client, asset)
        if atr and atr > 0:
            threshold = atr * BREAKOUT_ATR_MULTIPLIER

            # Box zu eng? (kleiner als 0.6x ATR = wahrscheinlich Noise)
            if box_size < atr * MIN_BOX_ATR_RATIO:
                print(f"   ⏭️  {asset}: Box zu eng (${box_size:.4f} < ATR ${atr:.4f}) -- Skip")
                continue

            print(f"   📐 {asset}: ATR=${atr:.4f}, Threshold=${threshold:.4f}, Box=${box_size:.4f}")
        else:
            # Fallback wenn ATR nicht berechnet werden kann
            threshold = current_price * 0.005  # 0.5% als Minimum
            print(f"   ⚠️  {asset}: ATR nicht verfuegbar, Fallback ${threshold:,.2f}")

        direction = check_breakout(asset, current_price, box["high"], box["low"], threshold)

        if direction:
            # === CANDLE-CLOSE CONFIRMATION ===
            # Nicht nur Mid-Price checken: der letzte abgeschlossene 5m-Candle
            # muss komplett ausserhalb der Box geschlossen haben.
            try:
                candles_5m = client.get_candles(asset, interval="5m", limit=2)
                if candles_5m and len(candles_5m) >= 2:
                    last_closed = candles_5m[-2]  # Vorletzte = letzte abgeschlossene
                    candle_close = last_closed["close"]

                    if direction == "long" and candle_close <= box["high"]:
                        print(f"   ⏭️  {asset}: Mid-Price ueber Box, aber 5m-Candle Close ${candle_close:,.2f} <= Box High ${box['high']:,.2f} -- Skip")
                        continue
                    elif direction == "short" and candle_close >= box["low"]:
                        print(f"   ⏭️  {asset}: Mid-Price unter Box, aber 5m-Candle Close ${candle_close:,.2f} >= Box Low ${box['low']:,.2f} -- Skip")
                        continue
                    print(f"   ✅ {asset}: Candle-Close bestaetigt (${candle_close:,.2f})")
            except Exception as e:
                print(f"   ⚠️  Candle-Check fehlgeschlagen: {e} -- fahre fort")

            # === SPREAD-CHECK ===
            # Zu hoher Spread = versteckte Kosten. Abbrechen wenn > 0.1%
            try:
                book = client.get_orderbook(asset)
                spread = book.get("spread_pct", 0)
                if spread > 0.1:
                    print(f"   ⏭️  {asset}: Spread zu hoch ({spread:.3f}% > 0.1%) -- Skip")
                    continue
                print(f"   ✅ {asset}: Spread OK ({spread:.4f}%)")
            except Exception as e:
                print(f"   ⚠️  Spread-Check fehlgeschlagen: {e} -- fahre fort")

            # Alle Checks bestanden!
            best_breakout = {
                "asset": asset,
                "direction": direction,
                "current_price": current_price,
                "box_high": box["high"],
                "box_low": box["low"],
                "breakout_size": abs(current_price - (box["high"] if direction == "long" else box["low"])),
                "atr": atr,
                "threshold": threshold
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

    # Initialize client
    client = HyperliquidClient()

    # === KILL-SWITCH ===
    is_safe, balance, start_capital = check_kill_switch(client)
    if not is_safe:
        print("NO_REPLY")
        return {"success": False, "reason": "Kill-switch activated"}

    # Dynamic risk calculation based on current balance
    risk_usd = balance * MAX_RISK_PCT
    print(f"💰 Balance: ${balance:,.2f} | Risk: ${risk_usd:,.2f} ({MAX_RISK_PCT*100:.0f}%)")

    # Check if already traded today in this session
    if has_traded_today_in_session(session):
        print(f"\n✅ SKIP: Already traded today in {session.upper()} session!")
        print("   Max 1 trade per session - no additional trades allowed.")
        send_telegram_message(f"⏭️ APEX {session.upper()}: Skip - bereits getradet in dieser Session")
        print("NO_REPLY")
        return {"success": True, "skipped": True, "reason": f"Already traded in {session} session today"}

    # Check for existing positions (just for logging)
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
    if breakout.get('atr'):
        print(f"   ATR: ${breakout['atr']:,.2f} | Threshold: ${breakout['threshold']:,.2f}")

    # Execute trade (mit dynamischem Risk)
    print(f"\n🚀 Executing {breakout['direction']} trade (Risk: ${risk_usd:,.2f})...")

    result = execute_breakout_trade(
        breakout['asset'],
        breakout['direction'],
        breakout['current_price'],
        breakout['box_high'],
        breakout['box_low'],
        risk_usd
    )

    if result["success"]:
        print(f"\n✅ TRADE EXECUTED!")
        print(f"   Entry: ${result['entry']:,.2f}")
        print(f"   Size: {result['size']}")
        print(f"   Stop-Loss: ${result['stop_loss']:,.2f} (Risk: ${risk_usd:.0f})")
        print(f"   TP1 (50%): ${result['take_profit_1']:,.2f} @ {result['size_tp1']} (1:1)")
        print(f"   TP2 (50%): ${result['take_profit_2']:,.2f} @ {result['size_tp2']} (3:1 Runner)")
        print(f"   SL: {result['sl_placed']} | TP1: {result['tp1_placed']} | TP2: {result['tp2_placed']}")
        print(f"\n💡 Position Monitor + ATR-Trailing aktiv")

        direction_emoji = "🟢" if result["direction"] == "long" else "🔴"
        msg = (
            f"🚀 APEX TRADE EXECUTED!\n\n"
            f"{direction_emoji} {result['asset']} {result['direction'].upper()}\n"
            f"Entry: ${result['entry']:,.2f}\n"
            f"Size: {result['size']}\n"
            f"Stop-Loss: ${result['stop_loss']:,.2f} (Risk: ${risk_usd:.0f})\n\n"
            f"📊 Split Take-Profit:\n"
            f"  TP1: ${result['take_profit_1']:,.2f} @ {result['size_tp1']} (1:1)\n"
            f"  TP2: ${result['take_profit_2']:,.2f} @ {result['size_tp2']} (3:1 Runner)\n\n"
            f"SL: {'✅' if result['sl_placed'] else '❌'} | "
            f"TP1: {'✅' if result['tp1_placed'] else '❌'} | "
            f"TP2: {'✅' if result['tp2_placed'] else '❌'}"
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
        # Ping basierend auf aktueller Session
        try:
            from healthcheck import ping
            session = get_current_session()
            if session:
                ping(f"session_{session}")
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message(f"💥 APEX autonomous_trade.py ERROR: {e}")
        try:
            from healthcheck import ping
            ping("session_error", "fail")
        except Exception:
            pass
        print("NO_REPLY")
        sys.exit(1)
