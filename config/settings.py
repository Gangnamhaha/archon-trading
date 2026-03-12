"""
프로젝트 설정 파일
환경변수 및 상수 관리
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === 한국투자증권 KIS API 설정 ===
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "")
KIS_ACCOUNT_PRODUCT_CODE = os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "01")
TRADING_MODE = os.getenv("TRADING_MODE", "paper")  # paper / live

# KIS API Base URL
KIS_BASE_URL = os.getenv(
    "KIS_BASE_URL",
    "https://openapivts.koreainvestment.com:29443"  # 기본: 모의투자
)
KIS_LIVE_URL = "https://openapi.koreainvestment.com:9443"
KIS_PAPER_URL = "https://openapivts.koreainvestment.com:29443"

# === 기본 상수 ===
DEFAULT_PERIOD = "1y"  # 기본 조회 기간
DEFAULT_MA_PERIODS = [5, 20, 60, 120]  # 이동평균 기간
DEFAULT_RSI_PERIOD = 14
DEFAULT_BOLLINGER_PERIOD = 20
DEFAULT_BOLLINGER_STD = 2
DEFAULT_INITIAL_CAPITAL = 10_000_000  # 백테스팅 기본 자본금 (1천만원)
DEFAULT_COMMISSION = 0.00015  # 기본 수수료율 0.015%

# === 시장 설정 ===
MARKETS = {
    "KR": "한국 (KRX)",
    "US": "미국 (NYSE/NASDAQ)",
}

# === DB 설정 ===
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "portfolio.db")
