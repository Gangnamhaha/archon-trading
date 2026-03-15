import hashlib
import hmac
import time
import uuid
from typing import Optional
from urllib.parse import urlencode

import requests


class UpbitAPI:
    BASE = "https://api.upbit.com/v1"

    def __init__(self, access_key: str = "", secret_key: str = ""):
        self.access_key = access_key
        self.secret_key = secret_key

    def _auth_header(self, query: dict = None):
        import jwt as pyjwt
        payload = {"access_key": self.access_key, "nonce": str(uuid.uuid4())}
        if query:
            query_str = urlencode(query).encode()
            query_hash = hashlib.sha512(query_str).hexdigest()
            payload["query_hash"] = query_hash
            payload["query_hash_alg"] = "SHA512"
        token = pyjwt.encode(payload, self.secret_key, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def get_balance(self) -> list[dict]:
        if not self.access_key:
            return []
        try:
            r = requests.get(f"{self.BASE}/accounts", headers=self._auth_header(), timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[Upbit] get_balance error: {e}")
            return []

    def get_ticker(self, market: str = "KRW-BTC") -> dict:
        try:
            r = requests.get(f"{self.BASE}/ticker", params={"markets": market}, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data[0] if data else {}
        except Exception as e:
            print(f"[Upbit] get_ticker error: {e}")
            return {}

    def get_candles(self, market: str = "KRW-BTC", count: int = 200, unit: int = 60) -> list[dict]:
        try:
            r = requests.get(
                f"{self.BASE}/candles/minutes/{unit}",
                params={"market": market, "count": count},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[Upbit] get_candles error: {e}")
            return []

    def place_buy_order(self, market: str, amount_krw: float) -> dict:
        if not self.access_key:
            return {"error": "API key not set", "simulation": True}
        try:
            body = {
                "market": market,
                "side": "bid",
                "price": str(int(amount_krw)),
                "ord_type": "price",
            }
            r = requests.post(
                f"{self.BASE}/orders",
                json=body,
                headers=self._auth_header(body),
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def place_sell_order(self, market: str, volume: float) -> dict:
        if not self.access_key:
            return {"error": "API key not set", "simulation": True}
        try:
            body = {
                "market": market,
                "side": "ask",
                "volume": str(volume),
                "ord_type": "market",
            }
            r = requests.post(
                f"{self.BASE}/orders",
                json=body,
                headers=self._auth_header(body),
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def get_orderbook(self, market: str = "KRW-BTC") -> dict:
        try:
            r = requests.get(f"{self.BASE}/orderbook", params={"markets": market}, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data[0] if data else {}
        except Exception as e:
            print(f"[Upbit] get_orderbook error: {e}")
            return {}


class BinanceAPI:
    BASE = "https://api.binance.com"

    def __init__(self, api_key: str = "", secret_key: str = ""):
        self.api_key = api_key
        self.secret_key = secret_key

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(self.secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self.api_key}

    def get_ticker(self, symbol: str = "BTCUSDT") -> dict:
        try:
            r = requests.get(
                f"{self.BASE}/api/v3/ticker/24hr",
                params={"symbol": symbol},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[Binance] get_ticker error: {e}")
            return {}

    def get_klines(self, symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 200) -> list:
        try:
            r = requests.get(
                f"{self.BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[Binance] get_klines error: {e}")
            return []

    def get_balance(self) -> dict:
        if not self.api_key:
            return {}
        try:
            params = self._sign({})
            r = requests.get(
                f"{self.BASE}/api/v3/account",
                params=params,
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[Binance] get_balance error: {e}")
            return {}

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        if not self.api_key:
            return {"error": "API key not set", "simulation": True}
        try:
            params = self._sign({
                "symbol": symbol,
                "side": side.upper(),
                "type": "MARKET",
                "quantity": quantity,
            })
            r = requests.post(
                f"{self.BASE}/api/v3/order",
                params=params,
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def get_orderbook(self, symbol: str = "BTCUSDT", limit: int = 10) -> dict:
        try:
            r = requests.get(
                f"{self.BASE}/api/v3/depth",
                params={"symbol": symbol, "limit": limit},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[Binance] get_orderbook error: {e}")
            return {}
