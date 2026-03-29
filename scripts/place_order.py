#!/usr/bin/env python3
"""
APEX - Order Placement Script
==============================
Platziert Orders via Hyperliquid SDK
"""

import os
import sys
import json
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

# Config
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
ENV_FILE = os.path.join(CONFIG_DIR, ".env.hyperliquid")


def load_credentials():
    """Lade Private Key aus .env"""
    private_key = None
    wallet_address = None
    
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    if key == 'HYPERLIQUID_PRIVATE_KEY':
                        private_key = value
                    elif key == 'HYPERLIQUID_WALLET':
                        wallet_address = value
    
    return private_key, wallet_address


def place_market_order(
    coin: str,
    is_buy: bool,
    size: float,
    reduce_only: bool = False
):
    """
    Platziere eine Market Order via SDK
    
    Returns:
        dict: Order result mit success/error/filled_price
    """
    try:
        private_key, wallet_address = load_credentials()
        
        if not private_key:
            return {"success": False, "error": "No private key configured"}
        
        # Initialize SDK
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        exchange = Exchange(
            wallet=wallet_address,
            base_url=constants.MAINNET_API_URL,
            account_address=wallet_address
        )
        
        # Set secret key
        from eth_account import Account
        exchange.wallet = Account.from_key(private_key)
        
        # Get current price for better limit
        all_mids = info.all_mids()
        current_price = float(all_mids.get(coin, 0))
        
        if current_price == 0:
            return {"success": False, "error": f"Could not get price for {coin}"}
        
        # Market order = aggressive limit order
        # Buy: 1% above mid, Sell: 1% below mid
        slippage = 0.01
        if is_buy:
            limit_price = current_price * (1 + slippage)
        else:
            limit_price = current_price * (1 - slippage)
        
        # Round price appropriately (BTC/ETH use $1 tick size)
        if coin in ["BTC", "ETH"]:
            limit_price = round(limit_price)  # Whole dollars
        else:
            limit_price = round(limit_price, 4)
        
        # Place order
        order_result = exchange.order(
            name=coin,
            is_buy=is_buy,
            sz=size,
            limit_px=limit_price,
            order_type={"limit": {"tif": "Ioc"}},  # Immediate or Cancel
            reduce_only=reduce_only
        )
        
        print(f"Order result: {json.dumps(order_result, indent=2)}")
        
        # Check if successful
        if order_result.get("status") == "ok":
            statuses = order_result.get("response", {}).get("data", {}).get("statuses", [])
            if statuses and statuses[0].get("filled"):
                filled = statuses[0]["filled"]
                return {
                    "success": True,
                    "filled_size": float(filled["totalSz"]),
                    "avg_price": float(filled["avgPx"]),
                    "coin": coin,
                    "is_buy": is_buy
                }
            else:
                return {
                    "success": False,
                    "error": "Order not filled",
                    "result": order_result
                }
        else:
            return {
                "success": False,
                "error": order_result.get("response", "Unknown error"),
                "result": order_result
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": __import__('traceback').format_exc()
        }


def place_stop_loss(
    coin: str,
    trigger_price: float,
    size: float
):
    """
    Platziere einen Stop-Loss
    
    Automatisch Long/Short detection basierend auf offenen Positionen
    """
    try:
        private_key, wallet_address = load_credentials()
        
        if not private_key:
            return {"success": False, "error": "No private key configured"}
        
        # Initialize SDK
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        exchange = Exchange(
            wallet=wallet_address,
            base_url=constants.MAINNET_API_URL,
            account_address=wallet_address
        )
        
        from eth_account import Account
        exchange.wallet = Account.from_key(private_key)
        
        # Get positions to determine direction
        state = info.user_state(wallet_address)
        positions = state.get("assetPositions", [])
        
        pos = next((p for p in positions if p["position"]["coin"] == coin), None)
        
        if not pos:
            return {"success": False, "error": f"No open position for {coin}"}
        
        current_size = float(pos["position"]["szi"])
        is_long = current_size > 0
        
        # Stop-Loss closes position (opposite direction)
        is_buy_sl = not is_long
        
        # Trigger slightly beyond actual SL for safety
        if is_long:
            trigger_px = trigger_price
            limit_px = trigger_price * 0.99  # 1% below trigger
        else:
            trigger_px = trigger_price
            limit_px = trigger_price * 1.01  # 1% above trigger
        
        # Round (BTC/ETH use $1 tick size)
        if coin in ["BTC", "ETH"]:
            trigger_px = round(trigger_px)  # Whole dollars
            limit_px = round(limit_px)
        else:
            trigger_px = round(trigger_px, 4)
            limit_px = round(limit_px, 4)
        
        # Place stop-loss order
        order_result = exchange.order(
            name=coin,
            is_buy=is_buy_sl,
            sz=abs(size),
            limit_px=limit_px,
            order_type={
                "trigger": {
                    "triggerPx": trigger_px,
                    "isMarket": True,
                    "tpsl": "sl"
                }
            },
            reduce_only=True
        )
        
        print(f"Stop-Loss result: {json.dumps(order_result, indent=2)}")
        
        if order_result.get("status") == "ok":
            return {
                "success": True,
                "trigger_price": trigger_px,
                "coin": coin
            }
        else:
            return {
                "success": False,
                "error": order_result.get("response", "Unknown error"),
                "result": order_result
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": __import__('traceback').format_exc()
        }


def place_take_profit(
    coin: str,
    trigger_price: float,
    size: float
):
    """
    Platziere einen Take-Profit
    
    Automatisch Long/Short detection basierend auf offenen Positionen
    """
    try:
        private_key, wallet_address = load_credentials()
        
        if not private_key:
            return {"success": False, "error": "No private key configured"}
        
        # Initialize SDK
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        exchange = Exchange(
            wallet=wallet_address,
            base_url=constants.MAINNET_API_URL,
            account_address=wallet_address
        )
        
        from eth_account import Account
        exchange.wallet = Account.from_key(private_key)
        
        # Get positions to determine direction
        state = info.user_state(wallet_address)
        positions = state.get("assetPositions", [])
        
        pos = next((p for p in positions if p["position"]["coin"] == coin), None)
        
        if not pos:
            return {"success": False, "error": f"No open position for {coin}"}
        
        current_size = float(pos["position"]["szi"])
        is_long = current_size > 0
        
        # Take-Profit closes position (opposite direction)
        is_buy_tp = not is_long
        
        # Limit slightly inside the trigger for safety
        if is_long:
            trigger_px = trigger_price
            limit_px = trigger_price * 0.999  # Slightly below trigger
        else:
            trigger_px = trigger_price
            limit_px = trigger_price * 1.001  # Slightly above trigger
        
        # Round (BTC/ETH use $1 tick size)
        if coin in ["BTC", "ETH"]:
            trigger_px = round(trigger_px)  # Whole dollars
            limit_px = round(limit_px)
        else:
            trigger_px = round(trigger_px, 4)
            limit_px = round(limit_px, 4)
        
        # Place take-profit order
        order_result = exchange.order(
            name=coin,
            is_buy=is_buy_tp,
            sz=abs(size),
            limit_px=limit_px,
            order_type={
                "trigger": {
                    "triggerPx": trigger_px,
                    "isMarket": True,
                    "tpsl": "tp"
                }
            },
            reduce_only=True
        )
        
        print(f"Take-Profit result: {json.dumps(order_result, indent=2)}")
        
        if order_result.get("status") == "ok":
            return {
                "success": True,
                "trigger_price": trigger_px,
                "coin": coin
            }
        else:
            return {
                "success": False,
                "error": order_result.get("response", "Unknown error"),
                "result": order_result
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": __import__('traceback').format_exc()
        }


def cancel_all_orders_for_coin(coin: str):
    """
    Storniere alle offenen Orders fuer ein Asset.
    Wird genutzt um verwaiste SL/TP-Orders aufzuraeumen
    wenn eine Position geschlossen wurde.
    """
    try:
        private_key, wallet_address = load_credentials()

        if not private_key:
            return {"success": False, "error": "No private key configured"}

        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        exchange = Exchange(
            wallet=wallet_address,
            base_url=constants.MAINNET_API_URL,
            account_address=wallet_address
        )

        from eth_account import Account
        exchange.wallet = Account.from_key(private_key)

        # Hole alle offenen Orders
        open_orders = info.open_orders(wallet_address)

        # Filtere nach Coin
        coin_orders = [o for o in open_orders if o.get("coin") == coin]

        if not coin_orders:
            return {"success": True, "cancelled": 0, "message": f"Keine offenen Orders fuer {coin}"}

        # Storniere jede Order einzeln
        cancelled = 0
        for order in coin_orders:
            oid = order.get("oid")
            if oid:
                try:
                    result = exchange.cancel(coin, oid)
                    if result.get("status") == "ok":
                        cancelled += 1
                except Exception as e:
                    print(f"   ⚠️  Cancel failed fuer Order {oid}: {e}")

        return {"success": True, "cancelled": cancelled, "total": len(coin_orders)}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python place_order.py market <COIN> <buy/sell> <SIZE>")
        print("  python place_order.py sl <COIN> <TRIGGER_PRICE> <SIZE>")
        print()
        print("Examples:")
        print("  python place_order.py market BTC buy 0.001")
        print("  python place_order.py sl BTC 69500 0.001")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "market":
        coin = sys.argv[2]
        is_buy = sys.argv[3].lower() == "buy"
        size = float(sys.argv[4])
        
        result = place_market_order(coin, is_buy, size)
        print(json.dumps(result, indent=2))
        
        if not result["success"]:
            sys.exit(1)
    
    elif action == "sl":
        coin = sys.argv[2]
        trigger_price = float(sys.argv[3])
        size = float(sys.argv[4])
        
        result = place_stop_loss(coin, trigger_price, size)
        print(json.dumps(result, indent=2))
        
        if not result["success"]:
            sys.exit(1)
    
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
