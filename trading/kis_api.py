"""
한국투자증권 KIS Open API 연동 모듈
- 인증, 현재가 조회, 주문, 잔고 조회
- 주문 안전장치: 장중/장외 자동판별, 사전검증, 실패 재시도
"""
import requests
import json
import re
import time
import traceback
from datetime import datetime, timedelta
from typing import Mapping, Optional
from config.settings import (
    KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO,
    KIS_ACCOUNT_PRODUCT_CODE, KIS_BASE_URL, TRADING_MODE
)
from data.database import log_app_error

_MARKET_OPEN_H, _MARKET_OPEN_M = 9, 0
_MARKET_CLOSE_H, _MARKET_CLOSE_M = 15, 30

_RETRYABLE_MSG_CDS: set[str] = {
    "IGW00003", "IGW00121", "APBK0000",
}

_NON_RETRYABLE_MSG_CDS: set[str] = {
    "APBK0918", "APBK0400", "IGW00017", "APBK0630", "APBK0631",
}

_MAX_RETRIES = 2
_RETRY_DELAY_SEC = 0.8


def is_market_open() -> bool:
    """현재 국내 주식시장 정규장 시간인지 판별 (KST 기준)"""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Seoul"))
    except Exception:
        now = datetime.utcnow() + timedelta(hours=9)
    wd = now.weekday()
    if wd >= 5:  # 토/일
        return False
    t = now.hour * 60 + now.minute
    return (_MARKET_OPEN_H * 60 + _MARKET_OPEN_M) <= t < (_MARKET_CLOSE_H * 60 + _MARKET_CLOSE_M)


def market_status_text() -> str:
    """현재 장 상태를 한 줄 텍스트로 반환"""
    if is_market_open():
        return "🟢 정규장 운영 중"
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Seoul"))
    except Exception:
        now = datetime.utcnow() + timedelta(hours=9)
    wd = now.weekday()
    if wd >= 5:
        return "🔴 주말 휴장"
    h = now.hour
    if h < _MARKET_OPEN_H:
        return "🟡 장전 (09:00 개장)"
    return "🔴 장 마감 (15:30 종료)"


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

    def _validate_order_preconditions(
        self, ticker: str, quantity: int, side: str,
    ) -> Optional[dict[str, object]]:
        tr_id = ("TTTC0802U" if side == "buy" else "TTTC0801U") if self.is_live else (
            "VTTC0802U" if side == "buy" else "VTTC0801U"
        )
        mode = "실전" if self.is_live else "모의투자"

        norm_ticker = self._normalize_domestic_ticker(ticker)
        if not (norm_ticker.isdigit() and len(norm_ticker) == 6):
            return {
                "status": "fail",
                "error": "종목코드는 국내주식 6자리 숫자여야 합니다. 예: 005930",
                "msg_cd": "INVALID_PDNO_LOCAL", "tr_id": tr_id, "mode": mode,
            }
        if quantity <= 0:
            return {
                "status": "fail",
                "error": f"주문 수량은 1 이상이어야 합니다. (입력: {quantity})",
                "msg_cd": "INVALID_QTY_LOCAL", "tr_id": tr_id, "mode": mode,
            }
        if not is_market_open():
            return {
                "status": "fail",
                "error": f"현재 장 운영시간이 아닙니다. ({market_status_text()})",
                "msg_cd": "MARKET_CLOSED_LOCAL", "tr_id": tr_id, "mode": mode,
            }
        return None

    def _execute_order_with_retry(
        self, tr_id: str, norm_ticker: str, quantity: int, price: int, label: str,
    ) -> dict[str, object]:
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        cano, acnt_prdt_cd = self._account_parts()
        mode = "실전" if self.is_live else "모의투자"

        def _safe_log_final_failure(result: dict[str, object], stack_trace: str = ""):
            try:
                username = "unknown"
                try:
                    import streamlit as st

                    session_user = st.session_state.get("user", {})
                    username = str(session_user.get("username", "unknown") or "unknown")
                except Exception:
                    pass

                error_code = str(result.get("msg_cd") or result.get("rt_cd") or "ORDER_FAILED")
                error_message = str(result.get("error") or "주문 처리 실패")
                detail = (
                    f"{label} 주문 실패 | ticker={norm_ticker}, qty={quantity}, price={price}, "
                    f"tr_id={tr_id}, mode={mode}, error={error_message}"
                )
                log_app_error(
                    username=username,
                    page="자동매매",
                    error_type="KIS_ORDER_FINAL_FAILURE",
                    error_code=error_code,
                    message=detail,
                    stack_trace=stack_trace,
                )
            except Exception:
                pass

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

        last_result: dict[str, object] = {}
        for attempt in range(_MAX_RETRIES + 1):
            try:
                res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
                data = res.json()
                msg_cd = str(data.get("msg_cd", ""))

                if res.ok and data.get("rt_cd") == "0":
                    return {
                        "status": "success",
                        "주문번호": data.get("output", {}).get("ODNO", ""),
                        "message": f"{label} 주문 완료",
                    }

                last_result = {
                    "status": "fail",
                    "error": data.get("msg1") or f"HTTP {res.status_code}",
                    "msg_cd": msg_cd,
                    "rt_cd": data.get("rt_cd", ""),
                    "tr_id": tr_id,
                    "mode": mode,
                }

                if msg_cd in _NON_RETRYABLE_MSG_CDS:
                    _safe_log_final_failure(last_result)
                    return last_result
                if msg_cd in _RETRYABLE_MSG_CDS and attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY_SEC)
                    continue
                _safe_log_final_failure(last_result)
                return last_result
            except requests.exceptions.Timeout:
                last_result = {"status": "fail", "error": "요청 시간 초과", "tr_id": tr_id, "mode": mode}
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY_SEC)
                    continue
            except Exception as e:
                failed: dict[str, object] = {
                    "status": "fail",
                    "error": str(e),
                    "tr_id": tr_id,
                    "mode": mode,
                    "attempt": attempt,
                }
                _safe_log_final_failure(failed, traceback.format_exc())
                return failed
        _safe_log_final_failure(last_result)
        return last_result

    def buy_order(self, ticker: str, quantity: int, price: int = 0) -> dict[str, object]:
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        pre = self._validate_order_preconditions(ticker, quantity, "buy")
        if pre is not None:
            return pre

        tr_id = "TTTC0802U" if self.is_live else "VTTC0802U"
        norm_ticker = self._normalize_domestic_ticker(ticker)
        return self._execute_order_with_retry(tr_id, norm_ticker, quantity, price, "매수")

    def sell_order(self, ticker: str, quantity: int, price: int = 0) -> dict[str, object]:
        if not self._is_configured():
            return {"error": "API 키 미설정"}

        pre = self._validate_order_preconditions(ticker, quantity, "sell")
        if pre is not None:
            return pre

        tr_id = "TTTC0801U" if self.is_live else "VTTC0801U"
        norm_ticker = self._normalize_domestic_ticker(ticker)
        return self._execute_order_with_retry(tr_id, norm_ticker, quantity, price, "매도")

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
            "mode": "실전" if self.is_live else "모의투자",
            "base_url": self.base_url,
            "has_token": self.access_token is not None,
            "account": self.account_no[:4] + "****" if self.account_no else "미설정",
        }
