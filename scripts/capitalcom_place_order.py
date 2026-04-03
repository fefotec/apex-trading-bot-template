#!/usr/bin/env python3
"""
APEX - Capital.com Order Placement Script
==========================================
Platziert Orders auf Capital.com fuer Gold-Trading.
Analog zu place_order.py (Hyperliquid).

Capital.com Besonderheit: SL und TP werden direkt beim Eroeffnen
der Position gesetzt (nicht als separate Orders).
Position schliessen = DELETE /positions/{dealId}.

WICHTIG: Bestehende Hyperliquid place_order.py wird NICHT angefasst.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capitalcom_client import CapitalComClient, GOLD_EPIC


def place_market_order(
    epic: str,
    is_buy: bool,
    size: float,
    stop_loss: float = None,
    take_profit: float = None,
    reduce_only: bool = False
):
    """
    Platziere eine Market Order auf Capital.com (mit SL/TP direkt dabei)

    Bei Capital.com werden SL und TP direkt beim Eroeffnen gesetzt.
    reduce_only wird ignoriert -- Position schliessen geht per close_position().

    Returns:
        dict: Order result mit success/error/filled_price
    """
    try:
        client = CapitalComClient()

        if not client.is_ready:
            return {"success": False, "error": "Capital.com not connected"}

        if reduce_only:
            # Capital.com: Position schliessen per Deal-ID
            positions = client.get_positions()
            gold_pos = [p for p in positions if p.epic == epic]
            if gold_pos:
                result = client.close_position(gold_pos[0].deal_id)
                return {
                    "success": result.success,
                    "deal_id": result.deal_id,
                    "error": result.error
                }
            return {"success": False, "error": f"No position to close for {epic}"}

        direction = "BUY" if is_buy else "SELL"
        result = client.open_position(epic, direction, size, stop_loss, take_profit)

        if result.success:
            return {
                "success": True,
                "filled_size": result.filled_size,
                "avg_price": result.avg_price,
                "deal_id": result.deal_id,
                "deal_reference": result.deal_reference,
                "epic": epic,
                "is_buy": is_buy
            }
        else:
            return {
                "success": False,
                "error": result.error
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": __import__('traceback').format_exc()
        }


def update_stop_loss(epic: str, stop_loss: float):
    """
    Aktualisiere den Stop-Loss einer offenen Position.
    Bei Capital.com wird SL per PUT /positions/{dealId} geaendert.
    """
    try:
        client = CapitalComClient()

        if not client.is_ready:
            return {"success": False, "error": "Capital.com not connected"}

        positions = client.get_positions()
        pos = next((p for p in positions if p.epic == epic), None)

        if not pos:
            return {"success": False, "error": f"No open position for {epic}"}

        success = client.update_position(pos.deal_id, stop_loss=stop_loss)

        if success:
            return {"success": True, "stop_loss": stop_loss, "deal_id": pos.deal_id}
        else:
            return {"success": False, "error": "Update SL failed"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def update_take_profit(epic: str, take_profit: float):
    """
    Aktualisiere den Take-Profit einer offenen Position.
    """
    try:
        client = CapitalComClient()

        if not client.is_ready:
            return {"success": False, "error": "Capital.com not connected"}

        positions = client.get_positions()
        pos = next((p for p in positions if p.epic == epic), None)

        if not pos:
            return {"success": False, "error": f"No open position for {epic}"}

        success = client.update_position(pos.deal_id, take_profit=take_profit)

        if success:
            return {"success": True, "take_profit": take_profit, "deal_id": pos.deal_id}
        else:
            return {"success": False, "error": "Update TP failed"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def close_position(epic: str):
    """Schliesse die offene Position fuer ein Instrument"""
    try:
        client = CapitalComClient()

        if not client.is_ready:
            return {"success": False, "error": "Capital.com not connected"}

        positions = client.get_positions()
        pos = next((p for p in positions if p.epic == epic), None)

        if not pos:
            return {"success": True, "message": f"No position to close for {epic}"}

        result = client.close_position(pos.deal_id)
        return {
            "success": result.success,
            "deal_id": pos.deal_id,
            "error": result.error
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python capitalcom_place_order.py market <EPIC> <buy/sell> <SIZE> [SL] [TP]")
        print("  python capitalcom_place_order.py close <EPIC>")
        print()
        print("Examples:")
        print(f"  python capitalcom_place_order.py market {GOLD_EPIC} buy 0.5 3050 3150")
        print(f"  python capitalcom_place_order.py close {GOLD_EPIC}")
        sys.exit(1)

    action = sys.argv[1]

    if action == "market":
        epic = sys.argv[2]
        is_buy = sys.argv[3].lower() == "buy"
        size = float(sys.argv[4])
        sl = float(sys.argv[5]) if len(sys.argv) > 5 else None
        tp = float(sys.argv[6]) if len(sys.argv) > 6 else None

        result = place_market_order(epic, is_buy, size, sl, tp)
        print(json.dumps(result, indent=2))

    elif action == "close":
        epic = sys.argv[2]
        result = close_position(epic)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
