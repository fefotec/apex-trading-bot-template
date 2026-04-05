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
DATA_DIR = "/data/.openclaw/workspace/projects/apex-trading/data"
STATE_FILE = os.path.join(DATA_DIR, "monitor_state.json")
PNL_TRACKER_FILE = os.path.join(DATA_DIR, "pnl_tracker.json")
CAPITAL_TRACKING_FILE = os.path.join(DATA_DIR, "capital_tracking.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")


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


def cleanup_orphan_orders(coin, current_positions):
    """
    Raeume verwaiste SL/TP-Orders auf fuer ein geschlossenes Asset.
    Wenn z.B. der TP getroffen hat, bleibt die SL-Order aktiv.
    Diese muss storniert werden, sonst koennte sie bei einer neuen Position triggern.

    SICHERHEIT: Prueft vorher ob fuer diesen Coin eine NEUE Position offen ist.
    Falls ja, werden Orders NICHT storniert (koennten zum neuen Trade gehoeren).
    """
    # Pruefen ob eine neue Position fuer diesen Coin existiert
    active_coins = [p.coin for p in current_positions]
    if coin in active_coins:
        print(f"   ⚠️  {coin} hat eine aktive Position -- Orders NICHT storniert (koennten zum neuen Trade gehoeren)")
        return

    try:
        from place_order import cancel_all_orders_for_coin
        result = cancel_all_orders_for_coin(coin)
        if result["success"]:
            cancelled = result.get("cancelled", 0)
            if cancelled > 0:
                print(f"   🧹 {cancelled} verwaiste Order(s) fuer {coin} storniert")
                send_telegram_notification(f"🧹 {cancelled} verwaiste Order(s) fuer {coin} aufgeraeumt")
            else:
                print(f"   ✅ Keine verwaisten Orders fuer {coin}")
        else:
            print(f"   ⚠️  Orphan-Cleanup Fehler: {result.get('error')}")
    except Exception as e:
        print(f"   ⚠️  Orphan-Cleanup Exception: {e}")


def update_trade_exit(coin, exit_price, pnl, exit_reason="sl_or_tp"):
    """
    Ergaenze den letzten offenen Trade fuer diesen Coin mit Exit-Daten.
    Damit ist der komplette Trade-Lifecycle in trades.json dokumentiert.
    """
    if not os.path.exists(TRADES_FILE):
        print(f"   ⚠️  trades.json nicht gefunden")
        return

    try:
        with open(TRADES_FILE, 'r') as f:
            trades = json.load(f)

        # Finde den letzten Trade fuer diesen Coin der noch keinen Exit hat
        updated = False
        for trade in reversed(trades):
            if trade.get("asset") == coin and "exit_price" not in trade:
                trade["exit_price"] = exit_price
                trade["exit_pnl"] = round(pnl, 2)
                trade["exit_reason"] = exit_reason
                trade["exit_time"] = datetime.now().isoformat()

                # Dauer berechnen
                try:
                    entry_time = datetime.fromisoformat(trade["timestamp"])
                    duration = datetime.now() - entry_time
                    trade["duration_minutes"] = round(duration.total_seconds() / 60, 1)
                except (KeyError, ValueError):
                    pass

                updated = True
                print(f"   📝 Trade-Exit geloggt: {coin} → ${pnl:+.2f} ({exit_reason})")
                break

        if updated:
            with open(TRADES_FILE, 'w') as f:
                json.dump(trades, f, indent=2)
        else:
            print(f"   ⚠️  Kein offener Trade fuer {coin} in trades.json gefunden")

    except Exception as e:
        print(f"   ⚠️  Trade-Exit Logging Fehler: {e}")


def update_stop_loss(client, coin, new_sl, size, is_long):
    """
    SL nachziehen: alte SL-Order stornieren, neue setzen.
    Storniert NUR SL-Orders (TP-Orders bleiben erhalten).
    """
    try:
        from place_order import place_stop_loss, load_credentials, round_price
        from hyperliquid.info import Info
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants
        from eth_account import Account

        private_key, wallet_address = load_credentials()
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        exchange = Exchange(
            wallet=wallet_address,
            base_url=constants.MAINNET_API_URL,
            account_address=wallet_address
        )
        exchange.wallet = Account.from_key(private_key)

        # Nur SL-Orders stornieren (TP behalten!)
        open_orders = info.open_orders(wallet_address)
        cancelled = 0
        for order in open_orders:
            if order.get("coin") == coin and order.get("orderType") == "Stop Market":
                oid = order.get("oid")
                if oid:
                    try:
                        exchange.cancel(coin, oid)
                        cancelled += 1
                    except Exception:
                        pass
        if cancelled > 0:
            print(f"   🔄 {cancelled} alte SL-Order(s) storniert")

        # Neue SL-Order setzen
        new_sl = round_price(coin, new_sl)
        sl_result = place_stop_loss(coin, new_sl, size)
        if sl_result["success"]:
            direction = "LONG" if is_long else "SHORT"
            print(f"   ✅ Neuer SL gesetzt: ${new_sl:,.2f}")
            send_telegram_notification(
                f"🔒 APEX SL nachgezogen\n\n"
                f"{coin} {direction}: SL → ${new_sl:,.2f}\n"
                f"Size: {size}"
            )
            return True
        else:
            print(f"   ❌ SL-Platzierung fehlgeschlagen: {sl_result.get('error')}")
            return False

    except Exception as e:
        print(f"   ❌ SL Update fehlgeschlagen: {e}")
        return False


def check_trailing_sl(client, positions, state):
    """
    Pruefe ob SL nachgezogen werden muss.
    Regel: Ab +3% Profit → SL auf Entry +1% (Profit-Lock).
    Laeuft alle 5 Min via Cron.
    """
    for pos in positions:
        coin = pos.coin
        is_long = pos.size > 0
        entry = pos.entry_price
        size = abs(pos.size)

        # Aktuellen Preis holen
        current_price = client.get_price(coin)
        if current_price <= 0:
            continue

        # P&L berechnen
        if is_long:
            pnl_pct = (current_price - entry) / entry * 100
        else:
            pnl_pct = (entry - current_price) / entry * 100

        # Trailing-State pro Coin aus dem State laden
        trail_key = f"trail_{coin}"
        trail_state = state.get(trail_key, {"profit_locked": False})

        # Ab +3% Profit: SL auf Entry +1% sichern (einmalig)
        if not trail_state.get("profit_locked") and pnl_pct > 3.0:
            if is_long:
                new_sl = entry * 1.01  # +1% ueber Entry
            else:
                new_sl = entry * 0.99  # -1% unter Entry

            print(f"\n🔒 {coin}: +{pnl_pct:.1f}% Profit → SL auf +1% sichern")
            if update_stop_loss(client, coin, new_sl, size, is_long):
                trail_state["profit_locked"] = True
                trail_state["locked_at"] = datetime.now().isoformat()
                trail_state["locked_sl"] = new_sl

        # === ATR-TRAIL DRY-RUN (nur Logging, keine echten Orders) ===
        # Loggt was ein ATR-Trailing-Stop tun wuerde, damit wir nach
        # 5-10 Trades echte Daten haben ob es sich lohnt.
        if trail_state.get("profit_locked") and pnl_pct > 4.0:
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from autonomous_trade import calculate_atr
                atr = calculate_atr(client, coin, interval="5m", periods=14)
                if atr and atr > 0:
                    trail_distance = atr * 2
                    if is_long:
                        simulated_sl = current_price - trail_distance
                    else:
                        simulated_sl = current_price + trail_distance

                    current_sl = trail_state.get("locked_sl", 0)
                    would_move = (is_long and simulated_sl > current_sl) or (not is_long and simulated_sl < current_sl)

                    # Nur loggen wenn sich was aendern wuerde
                    if would_move:
                        trail_state["dry_run_sl"] = round(simulated_sl, 2)
                        trail_state["dry_run_atr"] = round(atr, 2)
                        trail_state["dry_run_pnl_pct"] = round(pnl_pct, 2)
                        trail_state["dry_run_time"] = datetime.now().isoformat()
                        print(f"   📊 [DRY-RUN] ATR-Trail wuerde SL auf ${simulated_sl:,.2f} ziehen (ATR: ${atr:,.2f}, P&L: +{pnl_pct:.1f}%)")
            except Exception as e:
                print(f"   ⚠️  ATR Dry-Run Fehler: {e}")

        state[trail_key] = trail_state


def check_orphan_position(client, pos, state):
    """
    Pruefen ob die aktuelle Position groesser ist als der letzte Trade erwartet.
    Wenn ja, haengt eine alte Rest-Position ohne SL/TP mit drin.
    In dem Fall: Warnung per Telegram + Rest-Position sofort schliessen.
    """
    coin = pos.coin
    actual_size = abs(pos.size)

    # Schon gewarnt fuer diese Position?
    orphan_key = f"orphan_warned_{coin}"
    if state.get(orphan_key):
        return

    # Letzten Trade fuer diesen Coin aus trades.json holen
    if not os.path.exists(TRADES_FILE):
        return

    try:
        with open(TRADES_FILE, 'r') as f:
            trades = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    # Letzten offenen Trade fuer diesen Coin finden (ohne exit)
    last_trade = None
    for t in reversed(trades):
        if t.get("asset") == coin and "exit_price" not in t:
            last_trade = t
            break

    if not last_trade:
        return

    expected_size = last_trade.get("size", 0)
    if expected_size <= 0:
        return

    # Toleranz: 5% Abweichung ist OK (Teilfills, Rundung)
    if actual_size > expected_size * 1.05:
        orphan_size = actual_size - expected_size
        is_long = pos.size > 0
        direction = "LONG" if is_long else "SHORT"

        print(f"\n⚠️  REST-POSITION ERKANNT!")
        print(f"   {coin}: Erwartet {expected_size:.4f}, tatsaechlich {actual_size:.4f}")
        print(f"   Ueberschuss: {orphan_size:.4f} (alte Position ohne SL/TP!)")

        # Warnung per Telegram
        msg = (
            f"⚠️ APEX: Rest-Position erkannt!\n\n"
            f"{coin} {direction}: {actual_size:.4f} statt erwartet {expected_size:.4f}\n"
            f"Ueberschuss: {orphan_size:.4f}\n\n"
            f"Eine alte Position ohne SL/TP haengt mit drin.\n"
            f"Schliesse Rest-Position automatisch..."
        )
        send_telegram_notification(msg)

        # Rest-Position sofort schliessen (reduce_only Market Order)
        try:
            from place_order import place_market_order, round_size
            close_size = round_size(coin, orphan_size)
            is_buy = not is_long  # Gegenrichtung zum Schliessen
            result = place_market_order(coin, is_buy, close_size, reduce_only=True)

            if result["success"]:
                close_msg = (
                    f"✅ Rest-Position geschlossen!\n\n"
                    f"{coin}: {close_size} {direction} per Market geschlossen.\n"
                    f"Preis: ${result.get('avg_price', 0):,.2f}"
                )
                print(f"   ✅ Rest geschlossen: {close_size} @ ${result.get('avg_price', 0):,.2f}")
            else:
                close_msg = (
                    f"❌ Rest-Position konnte nicht geschlossen werden!\n\n"
                    f"Fehler: {result.get('error')}\n"
                    f"Bitte manuell schliessen!"
                )
                print(f"   ❌ Close fehlgeschlagen: {result.get('error')}")

            send_telegram_notification(close_msg)
        except Exception as e:
            print(f"   ❌ Close Exception: {e}")
            send_telegram_notification(f"❌ APEX: Rest-Position Close Fehler: {e}\nBitte manuell schliessen!")

        state[orphan_key] = True


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
    # NICHT returnen — Deposit-Erkennung muss trotzdem laufen!
    if current_count == 0 and last_count == 0:
        print("\n⏸️  Keine Positionen - Monitor idle")
    
    # Check if position was closed
    if last_count > 0 and current_count == 0:
        print("\n" + "=" * 60)
        print("🎯 POSITION GESCHLOSSEN!")
        print("=" * 60)

        # Verwaiste Orders aufraeumen (SL/TP die nicht mehr gebraucht werden)
        # positions = aktuelle Positionen (leer, weil gerade geschlossen)
        last_coins = state.get("last_position_coins", [])
        for coin in last_coins:
            cleanup_orphan_orders(coin, positions)

        # Get recent fills from last 24h and find the closing trade
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        # Wallet aus .env laden (kein hardcoded Fallback!)
        from place_order import load_credentials
        _, wallet = load_credentials()
        if not wallet:
            print("⚠️  Keine Wallet-Adresse konfiguriert")
            wallet = client.address  # Fallback auf Client-Wallet
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
            # Process ALL closed trades (nicht nur den neuesten)
            all_trades = sorted(closed_trades.values(), key=lambda x: x['time'], reverse=True)
            balance = client.get_balance()
            print(f"\nAktuelle Balance: ${balance:,.2f}")

            for trade in all_trades:
                coin = trade['coin']
                direction = trade['direction']
                exit_price = trade['price']
                total_size = trade['size']
                total_pnl = trade['pnl']

                print(f"\n💰 RESULT: {coin}")
                print(f"   Direction: {direction}")
                print(f"   Exit: ${exit_price:,.2f}")
                print(f"   Size: {total_size}")
                print(f"   P&L: ${total_pnl:,.2f}")

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

                # Exit-Daten in trades.json zurueckschreiben
                exit_reason = "sl_or_tp"  # Default
                if "Close Long" in direction:
                    exit_reason = "tp" if total_pnl > 0 else "sl"
                elif "Close Short" in direction:
                    exit_reason = "tp" if total_pnl > 0 else "sl"
                update_trade_exit(coin, exit_price, total_pnl, exit_reason)

                # Update P&L tracker
                update_pnl_tracker(total_pnl)
                
        else:
            print("⚠️  Keine geschlossenen Trades in letzten 24h gefunden")
            send_telegram_notification("🎯 APEX: Position geschlossen, aber keine Trade-Details gefunden.")

        # === CLOSE VERIFICATION ===
        # Nochmal pruefen ob die Position auf der Exchange WIRKLICH weg ist.
        # Wenn nicht: Rest sofort schliessen + Alarm.
        verify_positions = client.get_positions()
        for vpos in verify_positions:
            if vpos.coin in last_coins:
                remaining = abs(vpos.size)
                direction = "LONG" if vpos.size > 0 else "SHORT"
                print(f"\n⚠️  CLOSE VERIFICATION FAILED: {vpos.coin} hat noch {remaining} offen!")

                msg = (
                    f"⚠️ APEX: Position nicht vollstaendig geschlossen!\n\n"
                    f"{vpos.coin} {direction}: {remaining} noch offen\n"
                    f"Schliesse Rest automatisch..."
                )
                send_telegram_notification(msg)

                # Rest schliessen
                try:
                    from place_order import place_market_order, round_size
                    close_size = round_size(vpos.coin, remaining)
                    is_buy = vpos.size < 0  # Gegenrichtung
                    result = place_market_order(vpos.coin, is_buy, close_size, reduce_only=True)

                    if result["success"]:
                        print(f"   ✅ Rest geschlossen: {close_size} @ ${result.get('avg_price', 0):,.2f}")
                        send_telegram_notification(
                            f"✅ Rest-Position {vpos.coin} geschlossen!\n"
                            f"Size: {close_size} @ ${result.get('avg_price', 0):,.2f}"
                        )
                    else:
                        print(f"   ❌ Close fehlgeschlagen: {result.get('error')}")
                        send_telegram_notification(
                            f"❌ {vpos.coin} Rest konnte nicht geschlossen werden!\n"
                            f"Fehler: {result.get('error')}\n"
                            f"Bitte manuell schliessen!"
                        )
                except Exception as e:
                    print(f"   ❌ Close Exception: {e}")
                    send_telegram_notification(f"❌ {vpos.coin} Close Fehler: {e}\nBitte manuell schliessen!")

    elif current_count > 0:
        # Position still running
        pos = positions[0]
        is_long = pos.size > 0
        current_price = client.get_price(pos.coin)
        pnl_pct = ((current_price - pos.entry_price) / pos.entry_price * 100) if is_long else ((pos.entry_price - current_price) / pos.entry_price * 100)
        print(f"\n✅ Position läuft weiter:")
        print(f"   {pos.coin} {('LONG' if is_long else 'SHORT')}")
        print(f"   P&L: ${pos.unrealized_pnl:.2f} ({pnl_pct:+.1f}%)")

        # === REST-POSITIONS-CHECK ===
        # Pruefen ob die aktuelle Position groesser ist als erwartet
        # (= alte Rest-Position ohne SL/TP haengt mit drin)
        check_orphan_position(client, pos, state)

        # SL-Trailing pruefen (ab +3% → SL auf +1%)
        check_trailing_sl(client, positions, state)
    else:
        print("\n⏸️  Keine offenen Positionen")
    
    # === DEPOSIT-ERKENNUNG ===
    # Vergleiche Spot-Balance mit letztem bekannten Wert.
    # Wenn sie um >$50 gestiegen ist ohne dass ein Trade geschlossen wurde,
    # ist es wahrscheinlich eine Einzahlung.
    try:
        spot_balance = client.get_balance()
        last_spot = state.get("last_spot_balance", 0)

        # Position wurde gerade geschlossen ODER wurde kuerzlich geschlossen?
        # Wenn ja, ist der Balance-Anstieg kein Deposit sondern Margin-Rueckfluss + Gewinn
        position_just_closed = (last_count > 0 and current_count == 0)
        position_recently_closed = False
        last_close_time = state.get("last_position_closed_at")
        if last_close_time:
            try:
                closed_at = datetime.fromisoformat(last_close_time)
                minutes_since_close = (datetime.now() - closed_at).total_seconds() / 60
                position_recently_closed = minutes_since_close < 30  # 30 Min Puffer
            except (ValueError, TypeError):
                pass

        if last_spot > 0 and not position_just_closed and not position_recently_closed:
            diff = spot_balance - last_spot
            if diff > 500:  # Mehr als $500 Anstieg ohne Trade-Close = wahrscheinlich Deposit
                # Capital Tracking aktualisieren
                if os.path.exists(CAPITAL_TRACKING_FILE):
                    with open(CAPITAL_TRACKING_FILE, 'r') as f:
                        cap = json.load(f)

                    deposit_amount = round(diff, 2)
                    cap["deposits"].append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "amount": deposit_amount,
                        "reason": "Automatisch erkannt",
                        "new_total": round(cap["adjusted_start_capital"] + deposit_amount, 2)
                    })
                    cap["total_deposits"] = round(cap.get("total_deposits", 0) + deposit_amount, 2)
                    cap["adjusted_start_capital"] = round(cap["adjusted_start_capital"] + deposit_amount, 2)

                    with open(CAPITAL_TRACKING_FILE, 'w') as f:
                        json.dump(cap, f, indent=2)

                    msg = (
                        f"💰 EINZAHLUNG ERKANNT!\n\n"
                        f"Betrag: ${deposit_amount:,.2f}\n"
                        f"Neues Start-Kapital: ${cap['adjusted_start_capital']:,.2f}\n\n"
                        f"Automatisch angepasst - zaehlt nicht als Gewinn."
                    )
                    print(f"\n💰 Deposit erkannt: ${deposit_amount:,.2f}")
                    send_telegram_notification(msg)
    except Exception as e:
        print(f"  Deposit-Check Fehler: {e}")

    # Save new state (Trailing-State erhalten, Rest aktualisieren)
    position_coins = [p.coin for p in positions]
    state["last_position_count"] = current_count
    state["last_position_coins"] = position_coins
    state["last_spot_balance"] = client.get_balance()
    state["last_check"] = datetime.now().isoformat()

    # Zeitpunkt merken wenn Position gerade geschlossen wurde (fuer Deposit-Erkennung)
    if last_count > 0 and current_count == 0:
        state["last_position_closed_at"] = datetime.now().isoformat()

    # Trailing- und Orphan-State aufraeumen wenn Position geschlossen
    if current_count == 0:
        for key in list(state.keys()):
            if key.startswith("trail_") or key.startswith("orphan_"):
                del state[key]

    save_state(state)

    return current_count


if __name__ == "__main__":
    try:
        count = main()
        from healthcheck import ping
        ping("position_monitor")
        print("NO_REPLY")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        try:
            from healthcheck import ping
            ping("position_monitor", "fail")
        except Exception:
            pass
        print("NO_REPLY")
        sys.exit(1)
