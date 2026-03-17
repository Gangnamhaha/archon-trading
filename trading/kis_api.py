"""
한국투자증권 KIS Open API 연동 모듈
- 인증, 현재가 조회, 주문, 잔고 조회
"""
import requests
import json
import re
from typing import Mapping
from config.settings import (
    KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO,
    KIS_ACCOUNT_PRODUCT_CODE, KIS_BASE_URL, TRADING_MODE
)


class KISApi:
    """한국투자증권 Open API 클라이언트"""

    LIVE_URL = "https://openapi.koreainvestment.com:9443"
    PAPER_URL = "https://openapivts.koreainvestment.com:29443"

    def __init__(self, app_key: str = "", app_secret: str = "",
                 account_no: str = "", base_url: str = ""):
        self.app_key = app_key or KIS_APP_KEY
        self.app_secret = app_secret or KIS_APP_SECRET
        _raw_account = account_no or KIS_ACCOUNT_NO or ""
        self.account_no = _raw_account.replace("-", "").strip()
        self.product_code = KIS_ACCOUNT_PRODUCT_CODE
        self.base_url = base_url or KIS_BASE_URL
        self.is_live = self.base_url == self.LIVE_URL
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

    def _get_headers(self, tr_id: str) -> dict[str, str]:
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

    def _account_parts(self) -> tuple[str, str]:
        cano = self.account_no[:8]
        acnt_prdt_cd = self.account_no[8:10] if len(self.account_no) >= 10 else self.product_code
        return cano, acnt_prdt_cd

    def _get_hashkey(self, body: Mapping[str, object]) -> str:
        url = f"{self.base_url}/uapi/hashkey"
        headers = {
            "content-type": "application/json",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            res.raise_for_status()
            return str(res.json().get("HASH", "") or "")
        except Exception:
            return ""

    def _normalize_domestic_ticker(self, ticker: str) -> str:
        code = str(ticker or "").strip().upper()
        if code.startswith("A") and len(code) == 7 and code[1:].isdigit():
            return code[1:]
        if code.isdigit() and len(code) == 6:
            return code
        m = re.search(r"(\d{6})", code)
        if m:
            return m.group(1)
        return code

    def get_price(self, ticker: str) -> dict[str, object]:
        """현재가 조회"""
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        norm_ticker = self._normalize_domestic_ticker(ticker)
        if not (norm_ticker.isdigit() and len(norm_ticker) == 6):
            return {"error": "종목코드는 국내주식 6자리 숫자여야 합니다. 예: 005930"}

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        # 모의투자: FHKST01010100, 실전: FHKST01010100
        headers = self._get_headers("FHKST01010100")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": norm_ticker,
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("rt_cd") == "0":
                output = data.get("output", {})
                return {
                    "ticker": ticker,
                    "종목코드": norm_ticker,
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

    def buy_order(self, ticker: str, quantity: int, price: int = 0) -> dict[str, object]:
        """매수 주문"""
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        tr_id = "TTTC0802U" if self.is_live else "VTTC0802U"
        norm_ticker = self._normalize_domestic_ticker(ticker)
        if not (norm_ticker.isdigit() and len(norm_ticker) == 6):
            return {
                "status": "fail",
                "error": "종목코드는 국내주식 6자리 숫자여야 합니다. 예: 005930",
                "msg_cd": "INVALID_PDNO_LOCAL",
                "tr_id": tr_id,
                "mode": "실전" if self.is_live else "모의투자",
            }

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        # 모의투자: VTTC0802U, 실전: TTTC0802U

        cano, acnt_prdt_cd = self._account_parts()

        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": norm_ticker,
            "ORD_DVSN": "00" if price > 0 else "01",  # 00: 지정가, 01: 시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price if price > 0 else 0),
        }

        headers = self._get_headers(tr_id)
        headers["custtype"] = "P"
        hashkey = self._get_hashkey(body)
        if hashkey:
            headers["hashkey"] = hashkey

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            data = res.json()
            if not res.ok:
                return {
                    "status": "fail",
                    "error": data.get("msg1") or f"HTTP {res.status_code}",
                    "msg_cd": data.get("msg_cd", ""),
                    "rt_cd": data.get("rt_cd", ""),
                    "tr_id": tr_id,
                    "mode": "실전" if self.is_live else "모의투자",
                }
            if data.get("rt_cd") == "0":
                return {
                    "status": "success",
                    "주문번호": data.get("output", {}).get("ODNO", ""),
                    "message": "매수 주문 완료",
                }
            return {
                "status": "fail",
                "error": data.get("msg1", "주문 실패"),
                "msg_cd": data.get("msg_cd", ""),
                "rt_cd": data.get("rt_cd", ""),
                "tr_id": tr_id,
                "mode": "실전" if self.is_live else "모의투자",
            }
        except Exception as e:
            return {"status": "fail", "error": str(e)}

    def sell_order(self, ticker: str, quantity: int, price: int = 0) -> dict[str, object]:
        """매도 주문"""
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        tr_id = "TTTC0801U" if self.is_live else "VTTC0801U"
        norm_ticker = self._normalize_domestic_ticker(ticker)
        if not (norm_ticker.isdigit() and len(norm_ticker) == 6):
            return {
                "status": "fail",
                "error": "종목코드는 국내주식 6자리 숫자여야 합니다. 예: 005930",
                "msg_cd": "INVALID_PDNO_LOCAL",
                "tr_id": tr_id,
                "mode": "실전" if self.is_live else "모의투자",
            }

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        # 모의투자: VTTC0801U, 실전: TTTC0801U

        cano, acnt_prdt_cd = self._account_parts()

        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": norm_ticker,
            "ORD_DVSN": "00" if price > 0 else "01",
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price if price > 0 else 0),
        }

        headers = self._get_headers(tr_id)
        headers["custtype"] = "P"
        hashkey = self._get_hashkey(body)
        if hashkey:
            headers["hashkey"] = hashkey

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            data = res.json()
            if not res.ok:
                return {
                    "status": "fail",
                    "error": data.get("msg1") or f"HTTP {res.status_code}",
                    "msg_cd": data.get("msg_cd", ""),
                    "rt_cd": data.get("rt_cd", ""),
                    "tr_id": tr_id,
                    "mode": "실전" if self.is_live else "모의투자",
                }
            if data.get("rt_cd") == "0":
                return {
                    "status": "success",
                    "주문번호": data.get("output", {}).get("ODNO", ""),
                    "message": "매도 주문 완료",
                }
            return {
                "status": "fail",
                "error": data.get("msg1", "주문 실패"),
                "msg_cd": data.get("msg_cd", ""),
                "rt_cd": data.get("rt_cd", ""),
                "tr_id": tr_id,
                "mode": "실전" if self.is_live else "모의투자",
            }
        except Exception as e:
            return {"status": "fail", "error": str(e)}

    def get_balance(self) -> dict[str, object]:
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        tr_id = "VTTC8434R" if not self.is_live else "TTTC8434R"
        headers = self._get_headers(tr_id)

        cano, acnt_prdt_cd = self._account_parts()

        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=15)
            res.raise_for_status()
            data = res.json()

            if data.get("rt_cd") == "0":
                holdings = []
                for item in data.get("output1", []):
                    qty = int(item.get("hldg_qty", 0) or 0)
                    if qty > 0:
                        holdings.append({
                            "종목코드": item.get("pdno", ""),
                            "종목명": item.get("prdt_name", ""),
                            "보유수량": qty,
                            "매수평균가": int(float(item.get("pchs_avg_pric", 0) or 0)),
                            "현재가": int(item.get("prpr", 0) or 0),
                            "평가금액": int(item.get("evlu_amt", 0) or 0),
                            "평가손익": int(item.get("evlu_pfls_amt", 0) or 0),
                            "수익률": float(item.get("evlu_pfls_rt", 0) or 0),
                        })

                output2 = data.get("output2", [])
                summary = output2[0] if output2 else {}

                def _int(v: object) -> int:
                    try:
                        return int(str(v).replace(",", "").strip() or "0")
                    except Exception:
                        return 0

                return {
                    "holdings": holdings,
                    "총평가금액": _int(summary.get("tot_evlu_amt", 0)),
                    "총매입금액": _int(summary.get("pchs_amt_smtl_amt", 0)),
                    "총평가손익": _int(summary.get("evlu_pfls_smtl_amt", 0)),
                    "예수금": _int(summary.get("dnca_tot_amt", 0)),
                    "mode": "실전" if self.is_live else "모의투자",
                    "tr_id": tr_id,
                    "cano": cano,
                    "acnt_prdt_cd": acnt_prdt_cd,
                    "_raw_output2": summary,
                }

            return {
                "error": data.get("msg1", "잔고 조회 실패"),
                "rt_cd": data.get("rt_cd"),
                "msg_cd": data.get("msg_cd"),
                "mode": "실전" if self.is_live else "모의투자",
                "tr_id": tr_id,
            }
        except Exception as e:
            return {"error": str(e), "tr_id": tr_id}

    def get_status(self) -> dict[str, object]:
        """API 연결 상태 확인"""
        return {
            "configured": self._is_configured(),
            "mode": TRADING_MODE,
            "base_url": self.base_url,
            "has_token": self.access_token is not None,
            "account": self.account_no[:4] + "****" if self.account_no else "미설정",
        }
