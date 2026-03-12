import requests
import json


class KiwoomApi:
    LIVE_URL = "https://api.kiwoom.com"
    MOCK_URL = "https://mockapi.kiwoom.com"

    def __init__(self, app_key: str, secret_key: str, account_no: str, base_url: str = None):
        self.app_key = app_key
        self.secret_key = secret_key
        self.account_no = account_no
        self.base_url = base_url or self.MOCK_URL
        self.access_token = None

    def get_access_token(self) -> str:
        res = requests.post(
            f"{self.base_url}/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "appkey": self.app_key, "secretkey": self.secret_key},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        self.access_token = data["token"]
        return self.access_token

    def _headers(self, api_id: str) -> dict:
        if not self.access_token:
            self.get_access_token()
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "secretkey": self.secret_key,
            "api-id": api_id,
        }

    def get_price(self, ticker: str) -> dict:
        try:
            res = requests.post(
                f"{self.base_url}/api/dostk/sise",
                headers=self._headers("ka10002"),
                data=json.dumps({"stk_cd": ticker}),
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            if data.get("return_code") == "0":
                out = data.get("output", {})
                return {
                    "ticker": ticker,
                    "현재가": int(out.get("curprc", 0)),
                    "전일대비": int(out.get("ydif", 0)),
                    "등락률": float(out.get("ydrate", 0)),
                    "거래량": int(out.get("trdvol", 0)),
                }
            return {"error": data.get("return_msg", "조회 실패")}
        except Exception as e:
            return {"error": str(e)}

    def buy_order(self, ticker: str, quantity: int, price: int = 0) -> dict:
        return self._order("kt10000", ticker, quantity, price)

    def sell_order(self, ticker: str, quantity: int, price: int = 0) -> dict:
        return self._order("kt10001", ticker, quantity, price)

    def _order(self, api_id: str, ticker: str, quantity: int, price: int) -> dict:
        try:
            body = {
                "acnt_no": self.account_no,
                "stk_cd": ticker,
                "ord_qty": str(quantity),
                "ord_uv": str(price),
                "trde_tp": "0" if price > 0 else "3",
                "dmst_stex_tp": "KRX",
            }
            res = requests.post(
                f"{self.base_url}/api/dostk/ordr",
                headers=self._headers(api_id),
                data=json.dumps(body),
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            if data.get("return_code") == "0":
                return {"status": "success", "message": data.get("return_msg", "주문 완료")}
            return {"status": "fail", "error": data.get("return_msg", "주문 실패")}
        except Exception as e:
            return {"status": "fail", "error": str(e)}

    def get_balance(self) -> dict:
        try:
            body = {"acnt_no": self.account_no}
            res = requests.post(
                f"{self.base_url}/api/dostk/acnt",
                headers=self._headers("kt00005"),
                data=json.dumps(body),
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            if data.get("return_code") == "0":
                holdings = []
                for item in data.get("output", []):
                    if int(item.get("hldg_qty", "0")) > 0:
                        holdings.append({
                            "종목코드": item.get("stk_cd", ""),
                            "종목명": item.get("stk_nm", ""),
                            "보유수량": int(item.get("hldg_qty", "0")),
                            "매수평균가": int(float(item.get("avg_prc", "0"))),
                            "현재가": int(item.get("cur_prc", "0")),
                            "평가금액": int(item.get("evlt_amt", "0")),
                            "평가손익": int(item.get("evlt_pfls", "0")),
                            "수익률": float(item.get("pfls_rate", "0")),
                        })
                summary = data.get("output2", {})
                return {
                    "holdings": holdings,
                    "총평가금액": int(summary.get("tot_evlt_amt", 0)),
                    "총매입금액": int(summary.get("tot_pchs_amt", 0)),
                    "총평가손익": int(summary.get("tot_evlt_pfls", 0)),
                    "예수금": int(summary.get("dps_amt", 0)),
                }
            return {"error": data.get("return_msg", "잔고 조회 실패")}
        except Exception as e:
            return {"error": str(e)}

    def get_status(self) -> dict:
        return {
            "configured": bool(self.app_key and self.secret_key and self.account_no),
            "mode": "모의" if "mock" in self.base_url else "실전",
            "base_url": self.base_url,
            "has_token": self.access_token is not None,
            "account": self.account_no[:4] + "****" if self.account_no else "미설정",
        }
