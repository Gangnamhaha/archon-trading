## [2026-03-18] 알려진 이슈

### Issue 1: views/*.py 모듈 레벨 실행 + 임포트 충돌
- 현상: views/home.py 하단에 `render_home()` 호출 → python -c "from views.home import render_home" 시 st.session_state KeyError
- 이유: Streamlit 컨텍스트 없이 실행 시 require_auth()가 st.session_state['user'] 접근 실패
- 해결방법: QA 테스트는 실질적으로 `python3 -m pytest tests/ -v`와 `python3 -m compileall -q .`로 대체 가능
  OR 임포트 테스트용으로 하단 호출을 try/except st.errors.StreamlitAPIException으로 감싸기
  OR conftest.py에 session_state mock 추가 (pytest 실행 시에만 효과 있음)

### Issue 2: views/portfolio.py 300줄 초과 (479줄)
- 원본 pages/9_포트폴리오.py의 내용이 그대로 이동된 것으로 보임
- 리팩토링 필요: 헬퍼 함수를 portfolio/ 모듈로 이동 또는 views/portfolio/ 서브패키지화

### Issue 3: views/settings/payment.py 713줄 심각 초과
- Stripe 결제 로직, 플랜 비교, 이용 약관, 결제 폼 등 모두 포함
- 반드시 분리 필요: payment_core.py (로직), payment_ui.py (폼), payment.py (진입점 <100줄)

### Issue 4: views/settings/admin.py 346줄 초과
- 약간만 초과, 헬퍼 함수 2-3개를 별도 파일로 이동하면 해결 가능

### Issue 5: pages/ 21개 파일 중복 존재
- 새로운 views/ 구조와 중복 - Task 15에서 정리 예정
- autopilot_engine.py의 pages.util_ap_us 참조 때문에 pages/ 폴더 자체는 유지 필수
