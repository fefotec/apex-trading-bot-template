#!/usr/bin/env python3
"""
APEX - Hyperliquid API Wrapper
==============================
Meine Verbindung zum Markt. Mein Lebenselixier.
"""

import os
import json
import time
import requests
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

# Hyperliquid API Endpoints
MAINNET_API = "https://api.hyperliquid.xyz"
TESTNET_API = "https://api.hyperliquid-testnet.xyz"

# Config
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
ENV_FILE = os.path.join(CONFIG_DIR, ".env.hyperliquid")


@dataclass
class Candle:
    """OHLCV Kerze"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass 
class Position:
    """Offene Position"""
    symbol: str
    size: float
    entry_price: float
    unrealized_pnl: float
    leverage: float


@dataclass
class Order:
    """Order Details"""
    order_id: str
    symbol: str
    side: str
    price: float
    size: float
    status: str


class HyperliquidClient:
    """
    Hyperliquid API Client
    
    Docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
    """
    
    def __init__(self, testnet: bool = False):
        self.base_url = TESTNET_API if testnet else MAINNET_API
        self.api_key: Optional[str] = None
        self.api_secret: Optional[str] = None
        self.wallet_address: Optional[str] = None
        self._load_credentials()
    
    def _load_credentials(self):
        """Lade API-Credentials aus .env File"""
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, _, value = line.partition('=')
                        if key == 'HYPERLIQUID_API_KEY':
                            self.api_key = value
                        elif key == 'HYPERLIQUID_API_SECRET':
                            self.api_secret = value
                        elif key == 'HYPERLIQUID_WALLET':
                            self.wallet_address = value
            
            if self.api_key:
                print(f"✅ Credentials geladen. Wallet: {self.wallet_address[:8]}...")
        else:
            print(f"⚠️ Keine Credentials gefunden: {ENV_FILE}")
    
    @property
    def is_configured(self) -> bool:
        """Prüft ob API-Zugang konfiguriert ist"""
        return bool(self.api_key and self.wallet_address)
    
    # ===================
    # PUBLIC ENDPOINTS
    # ===================
    
    def get_markets(self) -> List[Dict]:
        """Hole alle verfügbaren Märkte"""
        response = requests.post(
            f"{self.base_url}/info",
            json={"type": "meta"}
        )
        return response.json().get("universe", [])
    
    def get_ticker(self, symbol: str) -> Dict:
        """Aktueller Preis für ein Symbol"""
        response = requests.post(
            f"{self.base_url}/info",
            json={"type": "allMids"}
        )
        mids = response.json()
        return {"symbol": symbol, "mid": float(mids.get(symbol, 0))}
    
    def get_candles(
        self, 
        symbol: str, 
        interval: str = "1m",
        limit: int = 100
    ) -> List[Candle]:
        """
        Hole OHLCV Kerzen
        
        Intervals: 1m, 5m, 15m, 1h, 4h, 1d
        """
        response = requests.post(
            f"{self.base_url}/info",
            json={
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol,
                    "interval": interval,
                    "startTime": int(time.time() * 1000) - (limit * 60000),
                    "endTime": int(time.time() * 1000)
                }
            }
        )
        
        candles = []
        for c in response.json():
            candles.append(Candle(
                timestamp=c["t"],
                open=float(c["o"]),
                high=float(c["h"]),
                low=float(c["l"]),
                close=float(c["c"]),
                volume=float(c["v"])
            ))
        return candles
    
    def get_orderbook(self, symbol: str) -> Dict:
        """Hole Orderbook für Spread-Berechnung"""
        response = requests.post(
            f"{self.base_url}/info",
            json={"type": "l2Book", "coin": symbol}
        )
        book = response.json()
        
        best_bid = float(book["levels"][0][0]["px"]) if book["levels"][0] else 0
        best_ask = float(book["levels"][1][0]["px"]) if book["levels"][1] else 0
        spread = (best_ask - best_bid) / best_bid if best_bid > 0 else 0
        
        return {
            "bid": best_bid,
            "ask": best_ask,
            "spread": spread,
            "spread_pct": spread * 100
        }
    
    # ===================
    # PRIVATE ENDPOINTS
    # ===================
    
    def _sign_request(self, payload: Dict) -> Dict:
        """Signiere Request mit API Secret"""
        # TODO: Implementiere Signatur nach Hyperliquid Docs
        # https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/authentication
        raise NotImplementedError("Signatur noch nicht implementiert - warte auf API-Zugang")
    
    def get_balance(self) -> Dict:
        """
        Hole ECHTE USDC Spot Balance
        
        ⚠️ WICHTIG: Dies ist der richtige Endpoint für Kapital-Checks!
        clearinghouseState zeigt nur Margin-Account (meist fast leer).
        """
        if not self.is_configured:
            return {"error": "Nicht konfiguriert", "balance": 0.0}
        
        response = requests.post(
            f"{self.base_url}/info",
            json={"type": "spotClearinghouseState", "user": self.wallet_address}
        )
        data = response.json()
        
        # Finde USDC Balance
        for balance in data.get("balances", []):
            if balance["coin"] == "USDC":
                return {
                    "total": float(balance["total"]),
                    "available": float(balance["total"]) - float(balance["hold"]),
                    "hold": float(balance["hold"])
                }
        
        return {"total": 0.0, "available": 0.0, "hold": 0.0}
    
    def get_account_state(self) -> Dict:
        """
        Hole Margin Account State (für offene Perpetual-Positionen)
        
        ⚠️ ACHTUNG: Dies zeigt NUR den Margin-Account, NICHT die Spot-Balance!
        Für Kapital-Checks get_balance() verwenden!
        """
        if not self.is_configured:
            return {"error": "Nicht konfiguriert"}
        
        response = requests.post(
            f"{self.base_url}/info",
            json={"type": "clearinghouseState", "user": self.wallet_address}
        )
        return response.json()
    
    def get_positions(self) -> List[Position]:
        """Hole offene Positionen"""
        state = self.get_account_state()
        positions = []
        
        for pos in state.get("assetPositions", []):
            if float(pos["position"]["szi"]) != 0:
                positions.append(Position(
                    symbol=pos["position"]["coin"],
                    size=float(pos["position"]["szi"]),
                    entry_price=float(pos["position"]["entryPx"]),
                    unrealized_pnl=float(pos["position"]["unrealizedPnl"]),
                    leverage=float(pos["position"]["leverage"]["value"])
                ))
        
        return positions
    
    def place_order(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        size: float,
        price: Optional[float] = None,  # None = Market Order
        reduce_only: bool = False,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
    ) -> Order:
        """
        Platziere eine Order
        
        WARNUNG: Diese Funktion bewegt ECHTES GELD!
        """
        if not self.is_configured:
            raise Exception("API nicht konfiguriert!")
        
        # TODO: Implementiere Order-Placement
        # Dies ist der kritischste Teil - mein Überleben hängt davon ab
        raise NotImplementedError("Order-Placement noch nicht implementiert - warte auf API-Zugang")
    
    def cancel_order(self, order_id: str) -> bool:
        """Storniere eine Order"""
        if not self.is_configured:
            return False
        
        # TODO: Implementiere Cancel
        raise NotImplementedError()
    
    def modify_sl(self, symbol: str, new_sl: float) -> bool:
        """
        Modifiziere Stop-Loss einer offenen Position.
        KRITISCH für das 60-Sekunden-Trailing!
        """
        if not self.is_configured:
            return False
        
        # TODO: Implementiere SL-Modifikation
        raise NotImplementedError()


# Entry Point für Tests
if __name__ == "__main__":
    print("=" * 50)
    print("APEX - Hyperliquid API Client Test")
    print("=" * 50)
    
    client = HyperliquidClient(testnet=False)
    
    print(f"\n📡 API Base: {client.base_url}")
    print(f"🔑 Configured: {client.is_configured}")
    
    if not client.is_configured:
        print("\n⚠️ Erstelle config/.env.hyperliquid mit:")
        print("   HYPERLIQUID_API_KEY=dein_key")
        print("   HYPERLIQUID_API_SECRET=dein_secret")
        print("   HYPERLIQUID_WALLET=0x...")
    
    # Test Public Endpoints (funktionieren ohne Auth)
    print("\n📊 Teste Public Endpoints...")
    
    try:
        ticker = client.get_ticker("BTC")
        print(f"   BTC Mid: ${ticker['mid']:,.2f}")
        
        book = client.get_orderbook("BTC")
        print(f"   Spread: {book['spread_pct']:.4f}%")
        
        candles = client.get_candles("BTC", "15m", limit=1)
        if candles:
            c = candles[-1]
            print(f"   Letzte 15m Kerze: O:{c.open:.0f} H:{c.high:.0f} L:{c.low:.0f} C:{c.close:.0f}")
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
    
    # Test Balance (braucht konfigurierte Wallet)
    if client.is_configured:
        print("\n💰 Teste Balance Check...")
        try:
            balance = client.get_balance()
            print(f"   Total USDC: ${balance['total']:,.2f}")
            print(f"   Available: ${balance['available']:,.2f}")
            print(f"   Hold: ${balance['hold']:,.2f}")
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
    
    print("\n✅ API Client Test abgeschlossen.")
