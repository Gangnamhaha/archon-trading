# Archon 앱 전체 리빌드

## TL;DR

> **Quick Summary**: 21개 페이지 Streamlit 트레이딩 앱을 5개 페이지로 재구조화. 초보 투자자 UX 최적화, 새 디자인 시스템, TDD 도입, God파일 분해.
> 
> **Deliverables**:
> - 5개 통합 페이지 (홈/매매/분석/포트폴리오/설정)
> - st.navigation() 기반 라우팅
> - 새 디자인 토큰 시스템
> - pytest 기반 테스트 인프라
> - views/ 서브모듈 아키텍처
> 
> **Estimated Effort**: XL
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Test infra → God file decomposition → Navigation → Page consolidation → Design system

---

## Context

### Original Request
사용자가 "처음부터 다시 계획을 수립해줘"를 요청. 현재 앱의 21개 페이지, 과도한 사이드바, 복잡한 UX를 전면 재설계하고 싶음.

### Interview Summary
**Key Discussions**:
- 범위: 앱 전체 리빌드 (기능 유지, 구조·UX·코드 전면 재설계)
- 타겟: 투자 초보자 (간단하고 직관적 UX 최우선)
- 페이지: 21개 → 5개 (홈, 매매, 분석, 포트폴리오, 설정)
- 분석 페이지: 3탭 (차트분석, AI판단, 투자도구) — 9탭은 성능 위험
- 테스트: TDD (characterization test → move → verify)
- 디자인: 완전 새로 (기존 Institutional Pro 폐기)
- DB: 클린 스타트

**Research Findings**:
- config/styles.py (785줄): CSS+PWA+Analytics+DeviceManager+AppSearch+GuideChatbot+Preferences+PlanGating 혼합
- config/auth.py (703줄): DB연결+테이블생성+패스워드해싱+세션토큰+로그인UI+JS주입 혼합
- st.set_page_config() 22개 파일에서 개별 호출 → st.navigation()에서는 app.py 1곳만 가능
- st.tabs()는 ALL 탭 내용을 동시 렌더 → lazy loading 필수
- autopilot_engine.py는 DB 통신만 사용 → 구조변경 영향 없음

### Metis Review
**Identified Gaps** (addressed):
- 분석 9탭 성능 문제 → 3탭으로 압축 + lazy loading
- styles.py God파일 → 6개 파일 분해 후 디자인 적용
- auth.py God파일 → 3개 파일 분해
- st.set_page_config() 충돌 → 중앙화
- Stripe 결제 콜백 → query_params 처리 보존
- 탭 상태 리셋 → session_state 기반 탭 유지

---

## Work Objectives

### Core Objective
21개 페이지 트레이딩 앱을 5개 페이지로 통합하고, 투자 초보자가 3클릭 안에 핵심 기능에 도달하는 간단한 UX를 만든다.

### Concrete Deliverables
- `app.py`: st.navigation() 기반 5페이지 라우팅
- `views/home.py`, `views/trading/`, `views/analysis/`, `views/portfolio.py`, `views/settings/`: 서브모듈
- `styles/tokens.py`, `styles/layout.py`, `styles/components.py`: 새 디자인 시스템
- `auth/core.py`, `auth/session.py`, `auth/ui.py`: 인증 분해
- `tests/`: pytest 기반 characterization + integration tests

### Definition of Done
- [ ] 5개 페이지 모두 렌더링 성공 (stException 없음)
- [ ] 모든 pytest 통과
- [ ] 모바일(375px) + 데스크탑(1440px) 스크린샷 정상
- [ ] Stripe 결제 콜백 동작
- [ ] 오토파일럿 시작/중지 동작
- [ ] 로그인/로그아웃/세션유지 동작

### Must Have
- 모든 기존 기능이 새 구조에서 접근 가능
- 페이지 파일 300줄 이하
- 3탭 이하 per 페이지
- lazy loading으로 5초 이내 페이지 로드

### Must NOT Have (Guardrails)
- autopilot_engine.py 수정 금지 (단, pages/ 정리 시 `pages/util_ap_us.py` shim은 유지 필수 — 이 파일은 존재하지 않지만 autopilot_engine.py:85가 `importlib.import_module("pages.util_ap_us")`로 참조함. pages/ 폴더 자체는 유지하되 내부 페이지 파일만 정리하거나, `util_ap_us.py`를 `trading/` 하위로 이동 후 autopilot_engine.py의 import 경로를 함께 수정)
- autopilot_engine.py는 `analysis.recommender`도 직접 import (line 92, 95) — `analysis/` 디렉토리 구조 변경 금지
- database.py 스키마 변경 금지
- 구조변경 중 기능 수정/개선 금지
- 디자인 변경과 구조 변경을 한 커밋에 혼합 금지
- 500줄 이상 단일 파일 금지

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (unittest 기반 14개 테스트)
- **Automated tests**: TDD (characterization test → move → verify)
- **Framework**: pytest (신규), 기존 unittest 테스트 유지

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Frontend/UI**: Playwright — Navigate, interact, assert DOM, screenshot
- **Backend**: Bash (python -c) — Import, call functions, compare output
- **Integration**: pytest — Run test suite, verify zero failures

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — test infra + version pinning):
├── Task 1: pytest 인프라 설정 + conftest.py [quick]
├── Task 2: Streamlit 버전 핀 + st.navigation() 검증 [quick]
├── Task 3: 21개 페이지 characterization tests 작성 [deep]
└── Task 4: 새 디자인 토큰 정의 (styles/tokens.py) [quick]

Wave 2 (God파일 분해 — 병렬 가능):
├── Task 5: config/styles.py → styles/ 6파일 분해 [deep]
├── Task 6: config/auth.py → auth/ 3파일 분해 [deep]
├── Task 7: sys.path 해킹 제거 + import 정리 [unspecified-high]
└── Task 8: views/ 디렉토리 구조 생성 + 빈 모듈 [quick]

Wave 3 (Navigation + 페이지 통합 Tier 1~2):
├── Task 9: app.py에 st.navigation() 적용 [deep]
├── Task 10: 설정 페이지 통합 (결제+FAQ+약관+문의+공지+관리자+마케팅) [deep]
├── Task 11: 홈 페이지 최종화 [quick]
└── Task 12: 포트폴리오 페이지 통합 [unspecified-high]

Wave 4 (페이지 통합 Tier 3~4 — 고위험):
├── Task 13: 분석 페이지 통합 (3탭: 차트/AI/도구) [deep]
├── Task 14: 매매 페이지 통합 (3탭: 국내/외환/코인) [deep]
└── Task 15: 구 pages/ 파일 정리 + 라우팅 최종 검증 [unspecified-high]

Wave 5 (Design + Final QA):
├── Task 16: 새 디자인 시스템 전체 적용 [visual-engineering]
├── Task 17: 모바일 최적화 + 하단 네비 업데이트 [visual-engineering]
├── Task 18: 통합 테스트 + 결제 플로우 검증 [deep]
└── Task 19: 최종 스크린샷 비교 + 배포 [unspecified-high]

Critical Path: Task 1 → Task 3 → Task 5,6 → Task 9 → Task 13,14 → Task 16 → Task 18
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Waves 1, 2)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 3 |
| 2 | — | 9 |
| 3 | 1 | 5,6,9,10,12,13,14 |
| 4 | — | 16 |
| 5 | 3 | 9,16 |
| 6 | 3 | 9 |
| 7 | 3 | 9 |
| 8 | — | 10,11,12,13,14 |
| 9 | 2,5,6,7 | 10,11,12,13,14 |
| 10 | 8,9 | 15 |
| 11 | 9 | 15 |
| 12 | 8,9 | 15 |
| 13 | 8,9 | 15 |
| 14 | 8,9 | 15 |
| 15 | 10,11,12,13,14 | 16 |
| 16 | 4,15 | 17 |
| 17 | 16 | 18 |
| 18 | 17 | 19 |
| 19 | 18 | — |

---

## TODOs

- [x] 1. pytest 인프라 설정 + conftest.py

  **What to do**:
  - `pip install pytest` 후 `requirements.txt` 업데이트 (pytest-streamlit은 존재하지 않는 패키지이므로 사용하지 않음)
  - `tests/conftest.py` 생성: 공통 fixture (임시 DB, mock session_state)
  - `pytest.ini` 또는 `pyproject.toml`에 pytest 설정 추가
  - 기존 unittest 14개가 `pytest tests/` 로도 실행되는지 확인

  **Must NOT do**: 기존 unittest 파일 수정

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: Wave 1 | Blocks: Task 3 | Blocked By: None

  **QA Scenarios**:
  ```
  Scenario: pytest 실행 확인
    Tool: Bash
    Steps:
      1. cd /Users/cpeoy/stock-platform && pytest tests/ -v
      2. 기존 14개 테스트 모두 PASS 확인
    Expected Result: 14 passed, 0 failed
    Evidence: .sisyphus/evidence/task-1-pytest-setup.txt
  ```

- [x] 2. Streamlit 버전 핀 + st.navigation() 검증

  **What to do**:
  - `requirements.txt`에서 `streamlit>=1.31.0` → `streamlit==1.44.0` (또는 현재 설치 버전) 핀
  - `python3 -c "import streamlit as st; pg = st.Page(lambda: None, title='test'); print('OK')"`로 API 존재 확인
  - `st.navigation()` 기본 사용법 검증 스크립트 작성

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: Wave 1 | Blocks: Task 9 | Blocked By: None

  **QA Scenarios**:
  ```
  Scenario: st.navigation API 존재 확인
    Tool: Bash
    Steps:
      1. python3 -c "import streamlit as st; print(hasattr(st, 'navigation'), hasattr(st, 'Page'))"
    Expected Result: True True
    Evidence: .sisyphus/evidence/task-2-nav-api.txt
  ```

- [x] 3. 21개 페이지 characterization tests 작성

  **What to do**:
  - `tests/test_pages_characterization.py` 생성
  - 각 페이지 파일이 import 에러 없이 로드되는지 테스트
  - 핵심 함수(require_auth, inject_pro_css, KISApi 등)의 시그니처 검증
  - `python3 -m compileall -q .`로 전체 컴파일 성공 확인

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**: Wave 1 | Blocks: Tasks 5,6,9,10,12,13,14 | Blocked By: Task 1

  **QA Scenarios**:
  ```
  Scenario: 전체 페이지 컴파일 + characterization 통과
    Tool: Bash
    Steps:
      1. pytest tests/test_pages_characterization.py -v
      2. python3 -m compileall -q .
    Expected Result: All tests PASS, compile 0 errors
    Evidence: .sisyphus/evidence/task-3-characterization.txt
  ```

- [x] 4. 새 디자인 토큰 정의 (styles/tokens.py)

  **What to do**:
  - `styles/` 디렉토리 생성 + `__init__.py`
  - `styles/tokens.py`에 CSS 변수 정의: 색상/타이포/간격/반경/그림자
  - 초보자 친화 디자인: 밝은 배경 + 높은 대비 + 큰 터치 타겟
  - 기존 _PRO_CSS 토큰과 독립적 (이 단계에서는 적용 안 함)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**: Wave 1 | Blocks: Task 16 | Blocked By: None

  **QA Scenarios**:
  ```
  Scenario: 토큰 파일 import 성공
    Tool: Bash
    Steps:
      1. python3 -c "from styles.tokens import DESIGN_TOKENS; print(type(DESIGN_TOKENS))"
    Expected Result: <class 'dict'> (or similar)
    Evidence: .sisyphus/evidence/task-4-tokens.txt
  ```

- [x] 5. config/styles.py → styles/ 6파일 분해

  **What to do**:
  - `styles/layout.py`: CSS 레이아웃/반응형/모바일 규칙
  - `styles/components.py`: 버튼/카드/메트릭/탭 등 컴포넌트 스타일
  - `components/device_manager.py`: 내 기기 관리 사이드바 위젯
  - `components/app_search.py`: 앱 검색 사이드바 위젯
  - `components/guide_chatbot.py`: AI 가이드 챗봇
  - `config/styles.py`는 위 모듈들을 import하는 facade로 유지
  - 모든 기존 테스트 통과 확인

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**: Wave 2 | Blocks: Tasks 9, 16 | Blocked By: Task 3

  **QA Scenarios**:
  ```
  Scenario: styles 분해 후 기능 유지
    Tool: Bash
    Steps:
      1. pytest tests/ -v
      2. python3 -c "from config.styles import inject_pro_css; print('OK')"
    Expected Result: All tests PASS, import OK
    Evidence: .sisyphus/evidence/task-5-styles-decompose.txt
  ```

- [x] 6. config/auth.py → auth/ 3파일 분해

  **What to do**:
  - `auth/core.py`: 패스워드 해싱, 사용자 생성/검증, 플랜 체크
  - `auth/session.py`: 세션 토큰, 기기 추적, 만료 관리
  - `auth/ui.py`: 로그인/회원가입 폼, JS 주입 (components.html)
  - `config/auth.py`는 위 모듈들을 re-export하는 facade
  - 모든 기존 테스트 통과 확인

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**: Wave 2 | Blocks: Task 9 | Blocked By: Task 3

  **QA Scenarios**:
  ```
  Scenario: auth 분해 후 기능 유지
    Tool: Bash
    Steps:
      1. pytest tests/ -v
      2. python3 -c "from config.auth import require_auth, logout; print('OK')"
    Expected Result: All tests PASS, import OK
    Evidence: .sisyphus/evidence/task-6-auth-decompose.txt
  ```

- [x] 7. sys.path 해킹 제거 + import 정리

  **What to do**:
  - 모든 페이지 파일 상단의 `sys.path.insert(0, ...)` 제거
  - 대신 프로젝트 루트에서 실행 기준 import 통일
  - `pyproject.toml` 또는 `setup.py`에 패키지 구성 추가 (필요시)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: Wave 2 | Blocks: Task 9 | Blocked By: Task 3

  **QA Scenarios**:
  ```
  Scenario: sys.path 해킹 제거 후 import 동작
    Tool: Bash
    Steps:
      1. grep -r "sys.path.insert" pages/ config/ --include="*.py" | wc -l (trading/ 제외 — autopilot_engine.py:83이 sys.path.insert를 사용하나 수정 금지 대상)
      2. python3 -m compileall -q .
    Expected Result: grep count = 0, compile success
    Evidence: .sisyphus/evidence/task-7-syspath.txt
  ```

- [x] 8. views/ 디렉토리 구조 생성

  **What to do**:
  - `views/__init__.py`
  - `views/home.py` (빈 placeholder)
  - `views/trading/__init__.py`, `views/trading/stock.py`, `views/trading/fx.py`, `views/trading/crypto.py`
  - `views/analysis/__init__.py`, `views/analysis/charts.py`, `views/analysis/ai.py`, `views/analysis/tools.py`
  - `views/portfolio.py`
  - `views/settings/__init__.py`, `views/settings/payment.py`, `views/settings/account.py`, `views/settings/support.py`, `views/settings/admin.py`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: Wave 2 | Blocks: Tasks 10-14 | Blocked By: None

  **QA Scenarios**:
  ```
  Scenario: views 구조 import 확인
    Tool: Bash
    Steps:
      1. python3 -c "import views; import views.trading; import views.analysis; import views.settings; print('OK')"
    Expected Result: OK
    Evidence: .sisyphus/evidence/task-8-views.txt
  ```

- [x] 9. app.py에 st.navigation() 적용

  **What to do**:
  - app.py를 st.navigation() + st.Page() 기반으로 재작성
  - 5개 페이지 등록: Home, Trading, Analysis, Portfolio, Settings
  - st.set_page_config()를 app.py 한 곳에서만 호출
  - 기존 pages/ 파일의 st.set_page_config() 호출 모두 제거
  - require_auth() + inject_pro_css()를 각 페이지 진입점에서 호출

  **Must NOT do**: pages/ 폴더 삭제 (autopilot_engine.py 의존성 때문에 폴더는 유지)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**: Wave 3 | Blocks: Tasks 10-14 | Blocked By: Tasks 2,5,6,7

  **QA Scenarios**:
  ```
  Scenario: 5페이지 네비게이션 동작
    Tool: Bash
    Steps:
      1. python3 -m compileall -q .
      2. pytest tests/ -v
    Expected Result: compile OK, all tests PASS
    Evidence: .sisyphus/evidence/task-9-navigation.txt
  ```

- [x] 10. 설정 페이지 통합

  **What to do**:
  - `views/settings/` 서브모듈에 기존 페이지 코드 이동:
    - 14_결제.py → views/settings/payment.py
    - 17_고객문의.py → views/settings/support.py (문의+FAQ+약관+공지 통합)
    - 11_AI채팅.py → views/settings/ai_chat.py (AI 어시스턴트)
    - 99_관리자.py → views/settings/admin.py (관리자 전용)
    - 13_마케팅도구.py → views/settings/marketing.py (Pro 전용)
  - 설정 페이지 진입점에서 st.radio 사용: ["결제", "AI어시스턴트", "고객지원", "관리자", "마케팅"]
  - 관리자/마케팅 탭은 role/plan 기반 조건부 표시
  - AI어시스턴트는 모든 플랜에서 접근 가능 (API 키 필요)
  - Stripe 결제 콜백 (query_params) 동작 보존

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**: Wave 3 | Blocks: Task 15 | Blocked By: Tasks 8, 9

  **QA Scenarios**:
  ```
  Scenario: 설정 페이지 탭 렌더링 + 결제 콜백 보존
    Tool: Bash
    Steps:
      1. python3 -c "from views.settings.payment import render_payment; print('OK')"
      2. pytest tests/ -v
    Expected Result: import OK, all tests PASS
    Evidence: .sisyphus/evidence/task-10-settings.txt
  ```

- [x] 11. 홈 페이지 최종화

  **What to do**: views/home.py에 현재 app.py 홈 콘텐츠 이동 (시장 요약 + 3단계 가이드 + Quick Access)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**: Wave 3 | Blocks: Task 15 | Blocked By: Task 9

  **QA Scenarios**:
  ```
  Scenario: 홈 페이지 렌더
    Tool: Bash
    Steps:
      1. python3 -c "from views.home import render_home; print('OK')"
    Expected Result: OK
    Evidence: .sisyphus/evidence/task-11-home.txt
  ```

- [x] 12. 포트폴리오 페이지 통합

  **What to do**: 9_포트폴리오.py → views/portfolio.py 이동. 기존 기능 유지.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: Wave 3 | Blocks: Task 15 | Blocked By: Tasks 8, 9

  **QA Scenarios**:
  ```
  Scenario: 포트폴리오 import + 컴파일
    Tool: Bash
    Steps:
      1. python3 -c "from views.portfolio import render_portfolio; print('OK')"
      2. python3 -m compileall -q views/
    Expected Result: OK
    Evidence: .sisyphus/evidence/task-12-portfolio.txt
  ```

- [x] 13. 분석 페이지 통합 (3탭: 차트/AI/도구)

  **What to do**:
  - views/analysis/charts.py: 데이터분석 + 글로벌마켓 + 기술적분석 통합
  - views/analysis/ai.py: AI예측 + 종목추천 + 종목스크리너 통합
  - views/analysis/tools.py: 백테스팅 + 리스크분석 + 뉴스감성분석 통합
  - lazy loading: `st.radio("섹션", [...], horizontal=True)` + `if selected == X:` 조건부 렌더링 (st.tabs는 모든 탭을 동시 렌더하므로 사용하지 않음)
  - 진입점에서 `st.radio` 또는 `st.segmented_control`로 섹션 전환 구현

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**: Wave 4 | Blocks: Task 15 | Blocked By: Tasks 8, 9

  **QA Scenarios**:
  ```
  Scenario: 분석 3탭 import + 컴파일
    Tool: Bash
    Steps:
      1. python3 -c "from views.analysis.charts import render_charts; from views.analysis.ai import render_ai; from views.analysis.tools import render_tools; print('OK')"
      2. pytest tests/ -v
    Expected Result: OK, all tests PASS
    Evidence: .sisyphus/evidence/task-13-analysis.txt
  ```

- [x] 14. 매매 페이지 통합 (3탭: 국내/외환/코인)

  **What to do**:
  - views/trading/stock.py: 10_자동매매.py 핵심 코드 이동 (주문+오토파일럿)
  - views/trading/fx.py: 19_외환자동매매.py 이동
  - views/trading/crypto.py: 20_코인자동매매.py 이동
  - 진입점에서 st.tabs(["🇰🇷 국내주식", "💱 외환", "🪙 코인"]) 사용
  - pages/ 폴더에 util_ap_us.py 호환 shim 유지 (autopilot_engine.py 의존성)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**: Wave 4 | Blocks: Task 15 | Blocked By: Tasks 8, 9

  **QA Scenarios**:
  ```
  Scenario: 매매 3탭 import + autopilot 호환
    Tool: Bash
    Steps:
      1. python3 -c "from views.trading.stock import render_stock; from views.trading.fx import render_fx; from views.trading.crypto import render_crypto; print('OK')"
      2. python3 -c "from trading.autopilot_engine import start_background_autopilot; print('OK')"
      3. pytest tests/ -v
    Expected Result: All OK, all tests PASS
    Evidence: .sisyphus/evidence/task-14-trading.txt
  ```

- [x] 15. 구 pages/ 파일 정리 + 라우팅 최종 검증

  **What to do**:
  - 구 pages/ 파일들 중 views/로 이전 완료된 것들을 삭제 (단, pages/ 폴더 자체 + util_ap_us.py shim은 유지)
  - st.navigation() 기반 5페이지 라우팅 최종 검증
  - 기존 URL 경로(`/자동매매` 등)는 지원하지 않음 — 새 네비게이션 경로만 사용. 기존 북마크는 깨질 수 있으나 이는 리빌드의 예상된 결과임

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**: Wave 4 | Blocks: Task 16 | Blocked By: Tasks 10-14

  **QA Scenarios**:
  ```
  Scenario: 구 파일 정리 + 라우팅 검증
    Tool: Bash
    Steps:
      1. ls pages/*.py | wc -l (최소한의 shim 파일만 남아야 함)
      2. pytest tests/ -v
      3. python3 -m compileall -q .
    Expected Result: pages/ 최소화, all tests PASS, compile OK
    Evidence: .sisyphus/evidence/task-15-cleanup.txt
  ```

- [x] 16. 새 디자인 시스템 전체 적용

  **What to do**:
  - styles/tokens.py의 새 디자인 토큰을 styles/layout.py, styles/components.py에 적용
  - 기존 Institutional Pro 네이비+블루 토큰 완전 교체
  - 초보자 친화 디자인: 밝은 배경, 높은 대비, 큰 버튼, 명확한 레이블
  - 5개 페이지 모두에 새 디자인 적용

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**: Wave 5 | Blocks: Task 17 | Blocked By: Tasks 4, 15

  **QA Scenarios**:
  ```
  Scenario: 새 디자인 적용 확인
    Tool: Playwright + Bash
    Preconditions: 앱이 배포됨 (https://archon-pro.streamlit.app) 또는 로컬 실행 (`streamlit run app.py` → http://localhost:8501)
    Steps:
      1. npx playwright screenshot --browser chromium --viewport-size "1440,980" --wait-for-timeout 8000 https://archon-pro.streamlit.app /tmp/task-16-desktop.png
      2. grep -rn "#0B1220\|#2F6BFF\|--archon-bg\|--archon-primary" styles/ config/styles.py (구 토큰 미사용 확인)
    Expected Result: 새 색상 체계 스크린샷, 구 토큰 grep 결과 0
    Evidence: .sisyphus/evidence/task-16-design-desktop.png
  ```

- [x] 17. 모바일 최적화 + 하단 네비 업데이트

  **What to do**:
  - 모바일 하단 네비의 5개 링크를 새 페이지 경로로 업데이트
  - 터치 타겟 48px 이상 보장
  - 모바일 뷰포트(375px) 기준 전 페이지 테스트

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**: Wave 5 | Blocks: Task 18 | Blocked By: Task 16

  **QA Scenarios**:
  ```
  Scenario: 모바일 UI 검증
    Tool: Playwright (npx playwright CLI)
    Preconditions: 로컬에서 `streamlit run app.py` 실행 → http://localhost:8501
    Steps:
      1. npx playwright screenshot --browser chromium --device "iPhone 13" --wait-for-timeout 10000 --full-page http://localhost:8501 /tmp/task-17-mobile.png
      2. 하단 네비 5개 링크 경로가 새 페이지 구조와 일치하는지 `grep "archonNav" styles/` 로 확인
    Expected Result: 모바일 스크린샷에 깨짐 없음, 네비 링크 5개 모두 새 경로
    Evidence: .sisyphus/evidence/task-17-mobile.png
  ```

- [x] 18. 통합 테스트 + 결제 플로우 검증

  **What to do**:
  - 로그인 → 페이지 전환 → 로그아웃 E2E 흐름 테스트
  - Stripe 결제 콜백 시뮬레이션
  - 오토파일럿 시작/중지 테스트
  - 플랜 게이팅 동작 확인

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`playwright`]

  **Parallelization**: Wave 5 | Blocks: Task 19 | Blocked By: Task 17

  **QA Scenarios**:
  ```
  Scenario: E2E 통합 검증
    Tool: Playwright + Bash
    Preconditions: 로컬에서 `streamlit run app.py` 실행 → http://localhost:8501, 테스트 계정 `any001004@gmail.com / chkim1004`
    Steps:
      1. Playwright로 http://localhost:8501 접속 → 약관 동의 → 로그인
      2. 5페이지 사이드바 네비게이션 순회 (각 3초 대기 + snapshot 확인)
      3. 매매 페이지 → API 연결 → 005930 종목코드 입력 → 매수 버튼 클릭 → 결과 메시지 확인
      4. 설정 페이지 → 결제 탭 렌더링 확인
      5. pytest tests/ -v (전체 통과 확인)
    Expected Result: 5페이지 정상 렌더, 로그인 유지, 매수 응답 수신, pytest PASS
    Evidence: .sisyphus/evidence/task-18-e2e.txt
  ```

- [ ] 19. 최종 스크린샷 비교 + 배포

  **What to do**:
  - 데스크탑/모바일 전 페이지 최종 스크린샷
  - git add + commit + push (자동배포 트리거)
  - 배포된 앱에서 최종 동작 확인

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: [`playwright`]

  **Parallelization**: Wave 5 | Blocks: None | Blocked By: Task 18

  **QA Scenarios**:
  ```
  Scenario: 배포 후 실 동작 확인
    Tool: Playwright
    Steps:
      1. https://archon-pro.streamlit.app 접속
      2. 테스트 계정 `any001004@gmail.com / chkim1004` 로그인
      3. 5페이지 네비게이션 순회 (각 3초 대기)
      4. 매매 페이지 API 연결 → 005930 종목 시장가 매수 1주 시도 (장중이면 체결, 장외면 MARKET_CLOSED_LOCAL 에러 확인)
      5. 오토파일럿 시작 → 동작 중 표시 확인 → 즉시 중지
    Expected Result: 전체 정상 동작, 에러 없음
    Evidence: .sisyphus/evidence/task-19-deployed.png
  ```

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Tool: Bash + Read
  Steps:
    1. 각 "Must Have" 항목에 대해 해당 파일/함수 존재 확인 (`python3 -c "from views.X import Y"`)
    2. 각 "Must NOT Have" 항목에 대해 `grep -r` 으로 금지 패턴 미사용 확인
    3. evidence 파일 존재 확인: `ls .sisyphus/evidence/task-*.txt`
  Expected Result: Must Have 전체 충족, Must NOT Have 전체 미검출, evidence 파일 존재
  Evidence: .sisyphus/evidence/final-f1-compliance.txt

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Tool: Bash
  Steps:
    1. `python3 -m compileall -q .` (컴파일 에러 0)
    2. `pytest tests/ -v` (전체 PASS)
    3. `grep -rn "as any\|@ts-ignore\|# type: ignore" --include="*.py" | wc -l` (0이어야 함)
    4. `wc -l views/*.py views/**/*.py` (300줄 이하 확인)
  Expected Result: compile OK, tests PASS, type suppression 0, 파일 300줄 이하
  Evidence: .sisyphus/evidence/final-f2-quality.txt

- [ ] F3. **Real Manual QA** — `unspecified-high` + `playwright`
  Tool: Playwright
  Steps:
    1. https://archon-pro.streamlit.app 접속
    2. 테스트 계정 `any001004@gmail.com / chkim1004`으로 로그인
    3. 5개 페이지 순회 (각 페이지 3초 대기 + 스크린샷)
    4. 매매 페이지에서 API 연결 → 종목코드 005930 입력 (장중이면 매수 실행, 장외면 에러메시지 확인)
    5. 설정 페이지 결제 탭 렌더링 확인
  Expected Result: 전 페이지 정상 렌더, 로그인 유지, 에러 없음
  Evidence: .sisyphus/evidence/final-f3-qa-desktop.png, .sisyphus/evidence/final-f3-qa-mobile.png

- [ ] F4. **Scope Fidelity Check** — `deep`
  Tool: Bash + Read
  Steps:
    1. `git diff --stat HEAD~1` 로 변경 범위 확인
    2. autopilot_engine.py 변경 여부 확인: `git diff HEAD~1 -- trading/autopilot_engine.py | wc -l` (0이어야 함)
    3. database.py 스키마 변경 여부: `git diff HEAD~1 -- data/database.py` 에서 CREATE TABLE/ALTER TABLE 변경 없음 확인
    4. views/ 파일 300줄 제한 확인
  Expected Result: autopilot 미변경, DB 스키마 미변경, views 300줄 이하
  Evidence: .sisyphus/evidence/final-f4-scope.txt

---

## Commit Strategy

- Wave 1: `test: add pytest infrastructure and characterization tests`
- Wave 2: `refactor(styles): decompose god file into modules` / `refactor(auth): decompose into core/session/ui`
- Wave 3: `refactor(nav): implement st.navigation() routing` / `refactor(settings): consolidate into unified page`
- Wave 4: `refactor(analysis): consolidate 9 pages into 3-tab view` / `refactor(trading): consolidate stock/fx/crypto`
- Wave 5: `style: apply new design system` / `fix: mobile optimization`

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -v
python3 -m compileall -q .
npx playwright screenshot --device "iPhone 13" https://archon-pro.streamlit.app /tmp/mobile.png
npx playwright screenshot --viewport-size "1440,980" https://archon-pro.streamlit.app /tmp/desktop.png
```

### Final Checklist
- [ ] 사이드바에 5개 메뉴만 표시
- [ ] 모든 기존 기능 접근 가능
- [ ] 페이지 로드 5초 이내
- [ ] 모바일 UI 깨짐 없음
- [ ] Stripe 결제 동작
- [ ] 오토파일럿 동작
- [ ] pytest 전체 통과
