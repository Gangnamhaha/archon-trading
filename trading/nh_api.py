import requests
import json


class NHApi:
    """
    NH투자증권 API 클라이언트.
    현재 NH는 공식 REST API가 없고 QV Open API(Windows COM)만 제공합니다.
    향후 REST API 출시 시 URL/파라미터만 변경하면 동작하도록 구조화되어 있습니다.
    """
    LIVE_URL = "https://openapi.nhqv.com"
    MOCK_URL = "https://sandbox.nhqv.com"

    def __init__(self, app_key: str, app_secret: str, account_no: str, base_url: str = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no
        self.base_url = base_url or self.MOCK_URL
        self.access_token = None

    def get_access_token(self) -> str:
        res = requests.post(
            f"{self.base_url}/oauth2/token",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            }),
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        self.access_token = data.get("access_token", data.get("token", ""))
        return self.access_token

    def _headers(self, tr_id: str = "") -> dict:
        if not self.access_token:
            self.get_access_token()
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

    def get_price(self, ticker: str) -> dict:
        return {"error": "NH REST API 미지원 — QV Open API(Windows)만 사용 가능합니다."}

    def buy_order(self, ticker: str, quantity: int, price: int = 0) -> dict:
        return {"status": "fail", "error": "NH REST API 미지원 — QV Open API(Windows)만 사용 가능합니다."}

    def sell_order(self, ticker: str, quantity: int, price: int = 0) -> dict:
        return {"status": "fail", "error": "NH REST API 미지원 — QV Open API(Windows)만 사용 가능합니다."}

    def get_balance(self) -> dict:
        return {"error": "NH REST API 미지원 — QV Open API(Windows)만 사용 가능합니다."}

    def get_status(self) -> dict:
        return {
            "configured": bool(self.app_key and self.app_secret and self.account_no),
            "mode": "sandbox" if "sandbox" in self.base_url else "live",
            "base_url": self.base_url,
            "has_token": self.access_token is not None,
            "account": self.account_no[:4] + "****" if self.account_no else "미설정",
            "notice": "NH는 현재 QV Open API(Windows COM)만 지원. REST 출시 시 업데이트 예정.",
        }
