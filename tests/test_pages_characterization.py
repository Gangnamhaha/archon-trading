import importlib
import py_compile
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT_DIR / "pages"
APP_FILE = ROOT_DIR / "app.py"

PAGE_FILES = [
    "1_데이터분석.py",
    "2_글로벌마켓.py",
    "3_기술적분석.py",
    "4_종목스크리너.py",
    "5_종목추천.py",
    "6_AI예측.py",
    "7_백테스팅.py",
    "8_리스크분석.py",
    "9_포트폴리오.py",
    "10_자동매매.py",
    "11_AI채팅.py",
    "12_뉴스감성분석.py",
    "13_마케팅도구.py",
    "14_결제.py",
    "15_공지사항.py",
    "16_약관.py",
    "17_고객문의.py",
    "18_자주하는질문.py",
    "19_외환자동매매.py",
    "20_코인자동매매.py",
    "99_관리자.py",
]

KEY_IMPORT_MODULES = ("config.auth", "config.styles")


def _compile_file(file_path: Path) -> None:
    _ = py_compile.compile(str(file_path), doraise=True)


@pytest.mark.parametrize("page_file", PAGE_FILES, ids=PAGE_FILES)
def test_page_file_compiles(page_file: str) -> None:
    page_path = PAGES_DIR / page_file
    assert page_path.exists(), f"Missing page file: {page_file}"
    _compile_file(page_path)


def test_app_file_compiles() -> None:
    assert APP_FILE.exists(), "Missing app.py"
    _compile_file(APP_FILE)


@pytest.mark.parametrize("target_file", PAGE_FILES, ids=PAGE_FILES)
def test_page_references_key_config_imports(target_file: str) -> None:
    file_path = PAGES_DIR / target_file
    source = file_path.read_text(encoding="utf-8")

    for module_name in KEY_IMPORT_MODULES:
        assert module_name in source, f"{target_file} should reference {module_name}"
        _ = importlib.import_module(module_name)


@pytest.mark.parametrize("name", ["require_auth", "logout", "is_paid", "is_pro"])
def test_config_auth_exports_are_importable(name: str) -> None:
    module = importlib.import_module("config.auth")
    assert hasattr(module, name), f"config.auth is missing export: {name}"


@pytest.mark.parametrize("name", ["inject_pro_css", "require_plan"])
def test_config_styles_exports_are_importable(name: str) -> None:
    module = importlib.import_module("config.styles")
    assert hasattr(module, name), f"config.styles is missing export: {name}"


@pytest.mark.parametrize("name", ["init_db", "get_connection"])
def test_data_database_exports_are_importable(name: str) -> None:
    module = importlib.import_module("data.database")
    assert hasattr(module, name), f"data.database is missing export: {name}"


@pytest.mark.parametrize("name", ["KISApi", "is_market_open", "market_status_text"])
def test_trading_kis_api_exports_are_importable(name: str) -> None:
    module = importlib.import_module("trading.kis_api")
    assert hasattr(module, name), f"trading.kis_api is missing export: {name}"
