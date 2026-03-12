"""
한국투자증권 KIS Open API 연동 모듈
- 인증, 현재가 조회, 주문, 잔고 조회
"""
import requests
import json
from datetime import datetime
from config.settings import (
    KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO,
    KIS_ACCOUNT_PRODUCT_CODE, KIS_BASE_URL, TRADING_MODE
)


class KISApi:
    """한국투자증권 Open API 클라이언트"""

    def __init__(self, app_key: str = None, app_secret: str = None,
                 account_no: str = None, base_url: str = None):
        self.app_key = app_key or KIS_APP_KEY
        self.app_secret = app_secret or KIS_APP_SECRET
        self.account_no = account_no or KIS_ACCOUNT_NO
        self.product_code = KIS_ACCOUNT_PRODUCT_CODE
        self.base_url = base_url or KIS_BASE_URL
        self.access_token = None
        self.token_expires = None

    def _is_configured(self) -> bool:
        """API 키가 설정되어 있는지 확인"""
        return bool(self.app_key and self.app_secret and self.account_no
                     and self.app_key != "your_app_key_here")

    def get_access_token(self) -> str:
        """OAuth 액세스 토큰 발급"""
        if not self._is_configured():
            raise ValueError("KIS API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            res.raise_for_status()
            data = res.json()
            self.access_token = data["access_token"]
            self.token_expires = data.get("access_token_token_expired")
            return self.access_token
        except Exception as e:
            raise ConnectionError(f"토큰 발급 실패: {e}")

    def _get_headers(self, tr_id: str) -> dict:
        """API 요청 헤더 생성"""
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
        """현재가 조회"""
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        # 모의투자: FHKST01010100, 실전: FHKST01010100
        headers = self._get_headers("FHKST01010100")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("rt_cd") == "0":
                output = data.get("output", {})
                return {
                    "ticker": ticker,
                    "현재가": int(output.get("stck_prpr", 0)),
                    "전일대비": int(output.get("prdy_vrss", 0)),
                    "등락률": float(output.get("prdy_ctrt", 0)),
                    "거래량": int(output.get("acml_vol", 0)),
                    "고가": int(output.get("stck_hgpr", 0)),
                    "저가": int(output.get("stck_lwpr", 0)),
                    "시가": int(output.get("stck_oprc", 0)),
                }
            return {"error": data.get("msg1", "조회 실패")}
        except Exception as e:
            return {"error": str(e)}

    def buy_order(self, ticker: str, quantity: int, price: int = 0) -> dict:
        """매수 주문"""
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        # 모의투자: VTTC0802U, 실전: TTTC0802U
        tr_id = "VTTC0802U" if TRADING_MODE == "paper" else "TTTC0802U"
        headers = self._get_headers(tr_id)

        body = {
            "CANO": self.account_no[:8],
            "ACNT_PRDT_CD": self.account_no[8:] if len(self.account_no) > 8 else self.product_code,
            "PDNO": ticker,
            "ORD_DVSN": "01" if price > 0 else "06",  # 01: 지정가, 06: 시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price),
        }

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("rt_cd") == "0":
                return {
                    "status": "success",
                    "주문번호": data.get("output", {}).get("ODNO", ""),
                    "message": "매수 주문 완료",
                }
            return {"status": "fail", "error": data.get("msg1", "주문 실패")}
        except Exception as e:
            return {"status": "fail", "error": str(e)}

    def sell_order(self, ticker: str, quantity: int, price: int = 0) -> dict:
        """매도 주문"""
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        # 모의투자: VTTC0801U, 실전: TTTC0801U
        tr_id = "VTTC0801U" if TRADING_MODE == "paper" else "TTTC0801U"
        headers = self._get_headers(tr_id)

        body = {
            "CANO": self.account_no[:8],
            "ACNT_PRDT_CD": self.account_no[8:] if len(self.account_no) > 8 else self.product_code,
            "PDNO": ticker,
            "ORD_DVSN": "01" if price > 0 else "06",
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price),
        }

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("rt_cd") == "0":
                return {
                    "status": "success",
                    "주문번호": data.get("output", {}).get("ODNO", ""),
                    "message": "매도 주문 완료",
                }
            return {"status": "fail", "error": data.get("msg1", "주문 실패")}
        except Exception as e:
            return {"status": "fail", "error": str(e)}

    def get_balance(self) -> dict:
        """잔고 조회"""
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        # 모의투자: VTTC8434R, 실전: TTTC8434R
        tr_id = "VTTC8434R" if TRADING_MODE == "paper" else "TTTC8434R"
        headers = self._get_headers(tr_id)

        params = {
            "CANO": self.account_no[:8],
            "ACNT_PRDT_CD": self.account_no[8:] if len(self.account_no) > 8 else self.product_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("rt_cd") == "0":
                holdings = []
                for item in data.get("output1", []):
                    if int(item.get("hldg_qty", 0)) > 0:
                        holdings.append({
                            "종목코드": item.get("pdno", ""),
                            "종목명": item.get("prdt_name", ""),
                            "보유수량": int(item.get("hldg_qty", 0)),
                            "매수평균가": int(float(item.get("pchs_avg_pric", 0))),
                            "현재가": int(item.get("prpr", 0)),
                            "평가금액": int(item.get("evlu_amt", 0)),
                            "평가손익": int(item.get("evlu_pfls_amt", 0)),
                            "수익률": float(item.get("evlu_pfls_rt", 0)),
                        })

                output2 = data.get("output2", [{}])
                summary = output2[0] if output2 else {}

                return {
                    "holdings": holdings,
                    "총평가금액": int(summary.get("tot_evlu_amt", 0)),
                    "총매입금액": int(summary.get("pchs_amt_smtl_amt", 0)),
                    "총평가손익": int(summary.get("evlu_pfls_smtl_amt", 0)),
                    "예수금": int(summary.get("dnca_tot_amt", 0)),
                }
            return {"error": data.get("msg1", "잔고 조회 실패")}
        except Exception as e:
            return {"error": str(e)}

    def get_status(self) -> dict:
        """API 연결 상태 확인"""
        return {
            "configured": self._is_configured(),
            "mode": TRADING_MODE,
            "base_url": self.base_url,
            "has_token": self.access_token is not None,
            "account": self.account_no[:4] + "****" if self.account_no else "미설정",
        }
