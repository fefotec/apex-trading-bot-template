#!/usr/bin/env python3
"""
APEX - Capital.com Position Monitor
=====================================
Checkt ob Gold-Positionen auf Capital.com geschlossen wurden und meldet Ergebnisse.

Capital.com Vorteil: SL/TP sind direkt an der Position -- keine verwaisten Orders,
kein Orphan-Cleanup noetig!

WICHTIG: Bestehende position_monitor.py (Hyperliquid) wird NICHT angefasst.
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capitalcom_client import CapitalComClient, GOLD_EPIC
from telegram_sender import send_telegram_message

# Files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
if os.path.exists("/data/.openclaw/workspace/projects/apex-trading/data"):
    DATA_DIR = "/data/.openclaw/workspace/projects/apex-trading/data"

GOLD_STATE_FILE = os.path.join(DATA_DIR, "gold_monitor_state.json")
GOLD_CAPITAL_FILE = os.path.join(DATA_DIR, "gold_capital_tracking.json")
PNL_TRACKER_FILE = os.path.join(DATA_DIR, "pnl_tracker.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")


def load_state():
    """Load last known Capital.com state"""
    if not os.path.exists(GOLD_STATE_FILE):
        return {"last_position_count": 0, "last_deal_ids": [], "last_check": None}

    with open(GOLD_STATE_FILE, 'r') as f:
        return json.load(f)


def save_state(state):
    """Save current state"""
    os.makedirs(os.path.dirname(GOLD_STATE_FILE), exist_ok=True)
    with open(GOLD_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def update_trade_exit(coin, exit_price, pnl, exit_reason="sl_or_tp"):
    """Ergaenze den letzten offenen Capital.com-Trade mit Exit-Daten"""
    if not os.path.exists(TRADES_FILE):
        return

    try:
        with open(TRADES_FILE, 'r') as f:
            trades = json.load(f)

        updated = False
        for trade in reversed(trades):
            if (trade.get("asset") == coin
                    and trade.get("exchange") == "capitalcom"
                    and "exit_price" not in trade):
                trade["exit_price"] = exit_price
                trade["exit_pnl"] = round(pnl, 2)
                trade["exit_reason"] = exit_reason
                trade["exit_time"] = datetime.now().isoformat()

                try:
                    entry_time = datetime.fromisoformat(trade["timestamp"])
                    duration = datetime.now() - entry_time
                    trade["duration_minutes"] = round(duration.total_seconds() / 60, 1)
                except (KeyError, ValueError):
                    pass

                updated = True
                print(f"   Trade-Exit geloggt: {coin} -> ${pnl:+.2f} ({exit_reason})")
                break

        if updated:
            with open(TRADES_FILE, 'w') as f:
                json.dump(trades, f, indent=2)

    except Exception as e:
        print(f"   Trade-Exit Logging Fehler: {e}")


def update_pnl_tracker(pnl):
    """Update P&L tracker"""
    if not os.path.exists(PNL_TRACKER_FILE):
        return

    with open(PNL_TRACKER_FILE, 'r') as f:
        tracker = json.load(f)

    tracker["realized_pnl"] = tracker.get("realized_pnl", 0) + pnl
    tracker["total_pnl"] = tracker["realized_pnl"] + tracker.get("unrealized_pnl", 0)

    if pnl > 0:
        tracker["winning_trades"] = tracker.get("winning_trades", 0) + 1
    else:
        tracker["losing_trades"] = tracker.get("losing_trades", 0) + 1

    tracker["total_trades"] = tracker.get("total_trades", 0) + 1
    tracker["last_updated"] = datetime.now().isoformat()

    for milestone_name, milestone in tracker.get("milestones", {}).items():
        if not milestone.get("reached", False):
            if tracker["total_pnl"] >= milestone["target"]:
                milestone["reached"] = True

    with open(PNL_TRACKER_FILE, 'w') as f:
        json.dump(tracker, f, indent=2)


def main():
    """Main Capital.com monitoring logic"""
    client = CapitalComClient()

    if not client.is_ready:
        print("  Capital.com nicht verbunden -- Monitor idle")
        return 0

    # Get current positions (nur Gold)
    all_positions = client.get_positions()
    gold_positions = [p for p in all_positions if p.epic == GOLD_EPIC]
    current_count = len(gold_positions)

    # Load last state
    state = load_state()
    last_count = state.get("last_position_count", 0)

    # Quick exit if nothing to do
    if current_count == 0 and last_count == 0:
        print("\n  Capital.com Gold: Keine Positionen - Monitor idle")
        return current_count

    # Position was closed
    if last_count > 0 and current_count == 0:
        print("\n" + "=" * 60)
        print("  CAPITAL.COM GOLD POSITION GESCHLOSSEN!")
        print("=" * 60)

        # Capital.com Vorteil: Kein Orphan-Cleanup noetig!
        # SL/TP sind an der Position gebunden und werden automatisch entfernt.

        # P&L aus Account-Info berechnen
        # Da die Position gerade geschlossen wurde, koennen wir die letzte P&L-Aenderung
        # aus dem trade log lesen oder die Account-Balance-Differenz nutzen
        last_balance = state.get("last_balance", 0)
        current_balance = client.get_balance()

        if last_balance > 0:
            pnl = current_balance - last_balance
        else:
            pnl = 0

        # Gold-Preis als Referenz
        gold_price = client.get_price(GOLD_EPIC)

        print(f"\n  RESULT:")
        print(f"   Asset: XAUUSD (Gold)")
        print(f"   Current Gold Price: ${gold_price:,.2f}")
        print(f"   P&L (Balance-Diff): ${pnl:,.2f}")
        print(f"   Neue Balance: ${current_balance:,.2f}")

        if pnl > 0:
            result_text = f"GEWINN: +${pnl:.2f}"
        elif pnl < 0:
            result_text = f"VERLUST: ${pnl:.2f}"
        else:
            result_text = "BREAKEVEN"

        message = (
            f"  APEX GOLD TRADE GESCHLOSSEN (Capital.com)!\n\n"
            f"{result_text}\n\n"
            f"Asset: XAUUSD (Gold)\n"
            f"Gold Preis: ${gold_price:,.2f}\n\n"
            f"Balance: ${current_balance:,.2f}"
        )

        send_telegram_message(message)

        # Exit-Daten in trades.json
        exit_reason = "tp" if pnl > 0 else "sl"
        update_trade_exit("XAUUSD", gold_price, pnl, exit_reason)

        # P&L Tracker
        if pnl != 0:
            update_pnl_tracker(pnl)

    elif current_count > 0:
        pos = gold_positions[0]
        direction = "LONG" if pos.direction == "BUY" else "SHORT"
        print(f"\n  Capital.com Gold-Position laeuft:")
        print(f"   {pos.epic} {direction}")
        print(f"   Entry: ${pos.entry_price:,.2f}")
        print(f"   P&L: ${pos.unrealized_pnl:+,.2f}")
        if pos.stop_loss:
            print(f"   SL: ${pos.stop_loss:,.2f}")
        if pos.take_profit:
            print(f"   TP: ${pos.take_profit:,.2f}")

        # === BREAK-EVEN STOP ===
        # Wenn der Trade >= 1x Risk im Plus ist, SL auf Entry-Preis ziehen.
        # Das macht den Trade risikofrei und schuetzt gegen Gold-Reversals.
        if pos.stop_loss and pos.entry_price:
            risk_per_unit = abs(pos.entry_price - pos.stop_loss)
            current_price = client.get_price(GOLD_EPIC)
            already_at_breakeven = state.get("breakeven_set", False)

            if not already_at_breakeven and risk_per_unit > 0 and current_price > 0:
                if direction == "LONG":
                    profit_distance = current_price - pos.entry_price
                else:
                    profit_distance = pos.entry_price - current_price

                if profit_distance >= risk_per_unit:
                    # Trade ist >= 1x Risk im Plus -- SL auf Entry ziehen
                    print(f"\n   BREAK-EVEN: Trade {profit_distance:,.2f} im Plus (>= Risk {risk_per_unit:,.2f})")
                    print(f"   Ziehe SL von ${pos.stop_loss:,.2f} auf Entry ${pos.entry_price:,.2f}")

                    success = client.update_position(
                        pos.deal_id,
                        stop_loss=pos.entry_price
                    )

                    if success:
                        print(f"   SL auf Break-Even gesetzt!")
                        send_telegram_message(
                            f"  APEX Gold: BREAK-EVEN!\n\n"
                            f"SL auf Entry ${pos.entry_price:,.2f} gezogen\n"
                            f"Trade ist jetzt risikofrei\n"
                            f"P&L: ${pos.unrealized_pnl:+,.2f}"
                        )
                        # Merken dass BE schon gesetzt ist
                        state["breakeven_set"] = True
                    else:
                        print(f"   BE-Update fehlgeschlagen")
    else:
        print("\n  Capital.com Gold: Keine offenen Positionen")

    # === DEPOSIT-ERKENNUNG ===
    try:
        current_balance = client.get_balance()
        last_balance = state.get("last_balance", 0)

        if last_balance > 0 and not (last_count > 0 and current_count == 0):
            diff = current_balance - last_balance
            if diff > 50:
                if os.path.exists(GOLD_CAPITAL_FILE):
                    with open(GOLD_CAPITAL_FILE, 'r') as f:
                        cap = json.load(f)

                    deposit_amount = round(diff, 2)
                    cap.setdefault("deposits", []).append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "amount": deposit_amount,
                        "reason": "Automatisch erkannt",
                    })
                    cap["total_deposits"] = round(cap.get("total_deposits", 0) + deposit_amount, 2)
                    cap["adjusted_start_capital"] = round(
                        cap.get("adjusted_start_capital", 500) + deposit_amount, 2)

                    with open(GOLD_CAPITAL_FILE, 'w') as f:
                        json.dump(cap, f, indent=2)

                    msg = (
                        f"  Capital.com EINZAHLUNG ERKANNT!\n\n"
                        f"Betrag: ${deposit_amount:,.2f}\n"
                        f"Neues Gold Start-Kapital: ${cap['adjusted_start_capital']:,.2f}"
                    )
                    send_telegram_message(msg)
    except Exception as e:
        print(f"  Deposit-Check Fehler: {e}")

    # Save state (breakeven_set zuruecksetzen wenn keine Position offen)
    deal_ids = [p.deal_id for p in gold_positions]
    new_state = {
        "last_position_count": current_count,
        "last_deal_ids": deal_ids,
        "last_balance": client.get_balance(),
        "last_check": datetime.now().isoformat(),
        "breakeven_set": state.get("breakeven_set", False) if current_count > 0 else False,
    }
    save_state(new_state)

    return current_count


if __name__ == "__main__":
    try:
        count = main()
        try:
            from healthcheck import ping
            ping("gold_monitor")
        except Exception:
            pass
        print("NO_REPLY")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        try:
            from healthcheck import ping
            ping("gold_monitor", "fail")
        except Exception:
            pass
        print("NO_REPLY")
        sys.exit(1)
