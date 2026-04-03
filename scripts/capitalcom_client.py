#!/usr/bin/env python3
"""
APEX - Capital.com Client
==========================
REST API Client fuer Capital.com CFD Trading.
Genutzt fuer Gold (XAUUSD) ORB-Strategie.

Capital.com API Docs: https://open-api.capital.com/

WICHTIG: Bestehende Hyperliquid-Integration wird NICHT angefasst.
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

# Paths
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
DATA_DIR = os.path.join(PROJECT_DIR, "data")

# Capital.com Gold Epic
GOLD_EPIC = "GOLD"

# Base URLs
LIVE_URL = "https://api-capital.backend-capital.com"
DEMO_URL = "https://demo-api-capital.backend-capital.com"


@dataclass
class OrderResult:
    success: bool
    deal_reference: Optional[str] = None
    deal_id: Optional[str] = None
    filled_size: float = 0.0
    avg_price: float = 0.0
    error: Optional[str] = None


@dataclass
class Position:
    deal_id: str
    epic: str
    direction: str  # "BUY" or "SELL"
    size: float
    entry_price: float
    unrealized_pnl: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class CapitalComClient:
    """
    Capital.com REST API Client

    Features:
    - Session-basierte Auth (CST + X-SECURITY-TOKEN)
    - Market & Limit Orders mit SL/TP
    - Position Management
    - Historische OHLCV-Daten
    """

    def __init__(self, email: Optional[str] = None, api_key: Optional[str] = None,
                 password: Optional[str] = None, demo: bool = True):
        self.base_url = DEMO_URL if demo else LIVE_URL
        self.demo = demo
        self.session = requests.Session()
        self.cst = None
        self.security_token = None
        self._authenticated = False

        if email and api_key and password:
            self._authenticate(email, api_key, password)
        else:
            self._load_from_env()

    def _load_from_env(self):
        """Lade Credentials aus .env.capitalcom"""
        env_file = os.path.join(CONFIG_DIR, ".env.capitalcom")

        if not os.path.exists(env_file):
            print("  .env.capitalcom nicht gefunden")
            return

        config = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    config[key.strip()] = value.strip()

        email = config.get('CAPITALCOM_EMAIL')
        api_key = config.get('CAPITALCOM_API_KEY')
        password = config.get('CAPITALCOM_PASSWORD')
        demo = config.get('CAPITALCOM_DEMO', 'true').lower() == 'true'

        if demo:
            self.base_url = DEMO_URL
            self.demo = True
        else:
            self.base_url = LIVE_URL
            self.demo = False

        if email and api_key and password:
            self._authenticate(email, api_key, password)
        else:
            print("  Capital.com Credentials unvollstaendig in .env.capitalcom")

    def _authenticate(self, email: str, api_key: str, password: str):
        """Starte Capital.com Session"""
        try:
            resp = self.session.post(
                f"{self.base_url}/api/v1/session",
                headers={
                    "X-CAP-API-KEY": api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "identifier": email,
                    "password": password
                },
                timeout=10
            )

            if resp.status_code == 200:
                self.cst = resp.headers.get("CST")
                self.security_token = resp.headers.get("X-SECURITY-TOKEN")
                self._authenticated = True
                mode = "DEMO" if self.demo else "LIVE"
                print(f"  Capital.com Session gestartet ({mode})")
            else:
                error = resp.json() if resp.text else {"status": resp.status_code}
                print(f"  Capital.com Auth fehlgeschlagen: {error}")

        except Exception as e:
            print(f"  Capital.com Auth Fehler: {e}")

    def _headers(self) -> Dict:
        """Standard-Headers fuer authentifizierte Requests"""
        return {
            "X-SECURITY-TOKEN": self.security_token or "",
            "CST": self.cst or "",
            "Content-Type": "application/json"
        }

    def _get(self, path: str, params: Dict = None) -> Optional[Dict]:
        """Authentifizierter GET Request"""
        try:
            resp = self.session.get(
                f"{self.base_url}{path}",
                headers=self._headers(),
                params=params,
                timeout=15
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"  GET {path} Fehler {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"  GET {path} Exception: {e}")
            return None

    def _post(self, path: str, data: Dict = None) -> Optional[Dict]:
        """Authentifizierter POST Request"""
        try:
            resp = self.session.post(
                f"{self.base_url}{path}",
                headers=self._headers(),
                json=data,
                timeout=15
            )
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                print(f"  POST {path} Fehler {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"  POST {path} Exception: {e}")
            return None

    def _delete(self, path: str) -> bool:
        """Authentifizierter DELETE Request"""
        try:
            resp = self.session.delete(
                f"{self.base_url}{path}",
                headers=self._headers(),
                timeout=15
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"  DELETE {path} Exception: {e}")
            return False

    @property
    def is_ready(self) -> bool:
        return self._authenticated

    # ========================
    # MARKET DATA
    # ========================

    def get_price(self, epic: str = GOLD_EPIC) -> float:
        """Aktueller Mid-Preis fuer ein Instrument"""
        if not self.is_ready:
            return 0.0

        data = self._get(f"/api/v1/markets/{epic}")
        if not data:
            return 0.0

        snapshot = data.get("snapshot", {})
        bid = float(snapshot.get("bid", 0))
        offer = float(snapshot.get("offer", 0))
        return (bid + offer) / 2 if bid and offer else 0.0

    def get_market_info(self, epic: str = GOLD_EPIC) -> Dict:
        """Detaillierte Markt-Informationen"""
        if not self.is_ready:
            return {}

        data = self._get(f"/api/v1/markets/{epic}")
        if not data:
            return {}

        snapshot = data.get("snapshot", {})
        instrument = data.get("instrument", {})
        dealing = data.get("dealingRules", {})

        bid = float(snapshot.get("bid", 0))
        offer = float(snapshot.get("offer", 0))
        mid = (bid + offer) / 2 if bid and offer else 0

        return {
            "epic": epic,
            "name": instrument.get("name", ""),
            "bid": bid,
            "offer": offer,
            "mid": mid,
            "spread": offer - bid if bid and offer else 0,
            "spread_pct": (offer - bid) / mid * 100 if mid > 0 else 0,
            "min_size": float(dealing.get("minDealSize", {}).get("value", 0)),
            "max_leverage": instrument.get("maxLeverage", 1),
            "status": snapshot.get("marketStatus", ""),
        }

    def get_candles(self, epic: str = GOLD_EPIC, resolution: str = "MINUTE_15",
                    limit: int = 100) -> List[Dict]:
        """
        Historische OHLCV Kerzen

        Resolutions: MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK
        """
        if not self.is_ready:
            return []

        # Resolution mapping (Kurzform -> Capital.com Format)
        res_map = {
            "1m": "MINUTE", "5m": "MINUTE_5", "15m": "MINUTE_15",
            "30m": "MINUTE_30", "1h": "HOUR", "4h": "HOUR_4",
            "1d": "DAY", "1w": "WEEK"
        }
        res = res_map.get(resolution, resolution)

        data = self._get(f"/api/v1/prices/{epic}", params={
            "resolution": res,
            "max": limit
        })

        if not data or "prices" not in data:
            return []

        candles = []
        for p in data["prices"]:
            # Capital.com liefert bid/ask OHLC separat -- wir nutzen den Durchschnitt
            open_bid = float(p.get("openPrice", {}).get("bid", 0))
            open_ask = float(p.get("openPrice", {}).get("ask", 0))
            high_bid = float(p.get("highPrice", {}).get("bid", 0))
            high_ask = float(p.get("highPrice", {}).get("ask", 0))
            low_bid = float(p.get("lowPrice", {}).get("bid", 0))
            low_ask = float(p.get("lowPrice", {}).get("ask", 0))
            close_bid = float(p.get("closePrice", {}).get("bid", 0))
            close_ask = float(p.get("closePrice", {}).get("ask", 0))

            candles.append({
                "time": p.get("snapshotTime", ""),
                "open": (open_bid + open_ask) / 2,
                "high": (high_bid + high_ask) / 2,
                "low": (low_bid + low_ask) / 2,
                "close": (close_bid + close_ask) / 2,
                "volume": float(p.get("lastTradedVolume", 0))
            })

        return candles

    def get_orderbook(self, epic: str = GOLD_EPIC) -> Dict:
        """Spread-Berechnung (bid/ask aus Marktdaten)"""
        info = self.get_market_info(epic)
        return {
            "bid": info.get("bid", 0),
            "ask": info.get("offer", 0),
            "mid": info.get("mid", 0),
            "spread_pct": info.get("spread_pct", 0)
        }

    def search_markets(self, term: str) -> List[Dict]:
        """Suche nach Instrumenten"""
        if not self.is_ready:
            return []

        data = self._get("/api/v1/markets", params={"searchTerm": term})
        if not data:
            return []

        results = []
        for m in data.get("markets", []):
            results.append({
                "epic": m.get("epic", ""),
                "name": m.get("instrumentName", ""),
                "type": m.get("instrumentType", ""),
                "status": m.get("marketStatus", ""),
            })
        return results

    # ========================
    # ACCOUNT DATA
    # ========================

    def get_balance(self) -> float:
        """Verfuegbares Kapital"""
        if not self.is_ready:
            return 0.0

        data = self._get("/api/v1/accounts")
        if not data:
            return 0.0

        accounts = data.get("accounts", [])
        if accounts:
            balance = accounts[0].get("balance", {})
            return float(balance.get("available", 0))
        return 0.0

    def get_account_info(self) -> Dict:
        """Detaillierte Konto-Informationen"""
        if not self.is_ready:
            return {}

        data = self._get("/api/v1/accounts")
        if not data:
            return {}

        accounts = data.get("accounts", [])
        if accounts:
            acc = accounts[0]
            balance = acc.get("balance", {})
            return {
                "account_id": acc.get("accountId", ""),
                "account_name": acc.get("accountName", ""),
                "currency": acc.get("currency", ""),
                "balance": float(balance.get("balance", 0)),
                "available": float(balance.get("available", 0)),
                "deposit": float(balance.get("deposit", 0)),
                "profit_loss": float(balance.get("profitLoss", 0)),
            }
        return {}

    def get_positions(self) -> List[Position]:
        """Alle offenen Positionen"""
        if not self.is_ready:
            return []

        data = self._get("/api/v1/positions")
        if not data:
            return []

        positions = []
        for p in data.get("positions", []):
            pos = p.get("position", {})
            market = p.get("market", {})

            direction = pos.get("direction", "")
            size = float(pos.get("size", 0))
            # Capital.com: size ist immer positiv, direction gibt die Richtung
            if direction == "SELL":
                size = -size

            positions.append(Position(
                deal_id=pos.get("dealId", ""),
                epic=market.get("epic", ""),
                direction=direction,
                size=size,
                entry_price=float(pos.get("level", 0)),
                unrealized_pnl=float(pos.get("profit", 0)),
                stop_loss=float(pos.get("stopLevel", 0)) if pos.get("stopLevel") else None,
                take_profit=float(pos.get("limitLevel", 0)) if pos.get("limitLevel") else None,
            ))

        return positions

    def get_open_orders(self) -> List[Dict]:
        """Alle offenen Working Orders"""
        if not self.is_ready:
            return []

        data = self._get("/api/v1/workingorders")
        if not data:
            return []

        return data.get("workingOrders", [])

    # ========================
    # TRADING
    # ========================

    def confirm_deal(self, deal_reference: str) -> Dict:
        """Bestaetigung eines Deals abrufen (MUSS nach jeder Order aufgerufen werden!)"""
        if not self.is_ready:
            return {}

        data = self._get(f"/api/v1/confirms/{deal_reference}")
        return data or {}

    def open_position(self, epic: str, direction: str, size: float,
                      stop_loss: float = None, take_profit: float = None) -> OrderResult:
        """
        Position eroeffnen (Market Order mit optionalem SL/TP)

        WARNUNG: Dies bewegt ECHTES GELD im LIVE-Modus!

        Args:
            epic: z.B. "GOLD"
            direction: "BUY" oder "SELL"
            size: Position Size
            stop_loss: Absoluter SL-Preis (optional)
            take_profit: Absoluter TP-Preis (optional)
        """
        if not self.is_ready:
            return OrderResult(success=False, error="Capital.com not authenticated")

        payload = {
            "epic": epic,
            "direction": direction,
            "size": size,
        }

        if stop_loss:
            payload["stopLevel"] = stop_loss
        if take_profit:
            payload["profitLevel"] = take_profit

        result = self._post("/api/v1/positions", payload)

        if not result:
            return OrderResult(success=False, error="Position open failed - no response")

        deal_ref = result.get("dealReference", "")

        if not deal_ref:
            return OrderResult(success=False, error="No deal reference returned")

        # Bestaetigung abrufen
        time.sleep(0.5)  # Kurz warten bis Deal verarbeitet
        confirm = self.confirm_deal(deal_ref)

        deal_status = confirm.get("dealStatus", "")
        if deal_status == "ACCEPTED":
            return OrderResult(
                success=True,
                deal_reference=deal_ref,
                deal_id=confirm.get("dealId", ""),
                filled_size=float(confirm.get("size", size)),
                avg_price=float(confirm.get("level", 0)),
            )
        else:
            reason = confirm.get("reason", "Unknown")
            return OrderResult(
                success=False,
                deal_reference=deal_ref,
                error=f"Deal {deal_status}: {reason}"
            )

    def close_position(self, deal_id: str) -> OrderResult:
        """Position schliessen"""
        if not self.is_ready:
            return OrderResult(success=False, error="Capital.com not authenticated")

        success = self._delete(f"/api/v1/positions/{deal_id}")

        if success:
            return OrderResult(success=True, deal_id=deal_id)
        else:
            return OrderResult(success=False, error=f"Close position {deal_id} failed")

    def update_position(self, deal_id: str, stop_loss: float = None,
                        take_profit: float = None) -> bool:
        """Stop-Loss und/oder Take-Profit einer offenen Position aendern"""
        if not self.is_ready:
            return False

        payload = {}
        if stop_loss:
            payload["stopLevel"] = stop_loss
        if take_profit:
            payload["profitLevel"] = take_profit

        if not payload:
            return False

        try:
            resp = self.session.put(
                f"{self.base_url}/api/v1/positions/{deal_id}",
                headers=self._headers(),
                json=payload,
                timeout=15
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"  Update Position Fehler: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """Alle offenen Working Orders stornieren"""
        if not self.is_ready:
            return False

        orders = self.get_open_orders()
        cancelled = 0
        for order in orders:
            deal_id = order.get("workingOrderData", {}).get("dealId", "")
            if deal_id:
                if self._delete(f"/api/v1/workingorders/{deal_id}"):
                    cancelled += 1

        print(f"   {cancelled}/{len(orders)} Orders storniert")
        return True

    # ========================
    # UTILITY
    # ========================

    def calculate_position_size(self, risk_amount: float, entry_price: float,
                                stop_loss: float) -> float:
        """Berechne Position Size basierend auf Risk"""
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit == 0:
            return 0

        return risk_amount / risk_per_unit

    def format_status(self) -> str:
        """Formatierter Account-Status"""
        if not self.is_ready:
            return "  Capital.com nicht verbunden"

        info = self.get_account_info()
        positions = self.get_positions()

        lines = [
            f"  Capital.com ({info.get('currency', '?')})",
            f"   Balance: {info.get('balance', 0):,.2f}",
            f"   Verfuegbar: {info.get('available', 0):,.2f}",
            f"   P&L: {info.get('profit_loss', 0):+,.2f}",
            f"   Positionen: {len(positions)}"
        ]

        for pos in positions:
            direction = "LONG" if pos.direction == "BUY" else "SHORT"
            lines.append(
                f"   {pos.epic}: {direction} {abs(pos.size)} @ {pos.entry_price:,.2f} "
                f"P&L: {pos.unrealized_pnl:+,.2f}"
            )

        return "\n".join(lines)


# ========================
# TEST
# ========================

if __name__ == "__main__":
    print("=" * 50)
    print("APEX - Capital.com Client Test")
    print("=" * 50)

    client = CapitalComClient()

    print(f"\n  Capital.com Ready: {client.is_ready}")

    if not client.is_ready:
        print("\n  Bitte .env.capitalcom konfigurieren")
        print("  Siehe config/.env.capitalcom.example")
        exit(1)

    # Suche Gold
    print("\n  Suche Gold-Instrument...")
    results = client.search_markets("gold")
    for r in results[:5]:
        print(f"   {r['epic']}: {r['name']} ({r['type']}) - {r['status']}")

    # Gold-Preis
    print(f"\n  Gold Preis: ${client.get_price(GOLD_EPIC):,.2f}")

    # Markt-Info
    info = client.get_market_info(GOLD_EPIC)
    if info:
        print(f"   Spread: {info['spread_pct']:.4f}%")
        print(f"   Min Size: {info['min_size']}")
        print(f"   Status: {info['status']}")

    # Candles
    candles = client.get_candles(GOLD_EPIC, "15m", limit=2)
    if candles:
        c = candles[-1]
        print(f"   Last 15m: O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f}")

    # Account
    print(f"\n{client.format_status()}")

    print("\n  Test abgeschlossen.")
