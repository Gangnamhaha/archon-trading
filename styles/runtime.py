# pyright: basic
import inspect
import json
import os
from collections.abc import Callable
from typing import Any, Optional

import streamlit as st
import streamlit.components.v1 as components

from components.app_search import render_app_search
from components.device_manager import render_device_manager
from components.guide_chatbot import render_guide_chatbot
from styles.components import COMPONENTS_CSS
from styles.layout import LAYOUT_CSS
from styles.tokens import generate_css

_PWA_META = """
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Archon">
<meta name="theme-color" content="#FFFFFF">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<link rel="manifest" href="app/static/manifest.json">
<link rel="apple-touch-icon" sizes="192x192" href="app/static/icon-192.png">
<meta name="description" content="Archon - AI 기반 주식 자동매매 플랫폼. 종목추천, 오토파일럿, 백테스팅, 리스크분석.">
<meta name="keywords" content="주식,자동매매,AI,종목추천,오토파일럿,한국투자증권,키움증권">
<meta property="og:title" content="Archon - AI 주식 자동매매 플랫폼">
<meta property="og:description" content="AI가 종목 추천부터 매매까지 자동화합니다.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://archon-pro.streamlit.app">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Archon - AI 주식 자동매매 플랫폼">
<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/app/static/sw.js').catch(()=>{});}</script>
"""

_ANALYTICS_CODE = """
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-XXXXXXXXXX');</script>
"""

_HIDE_GITHUB_ONLY = """<style>
/* GitHub 아이콘만 숨김 (일반 사용자) */
[data-testid="stToolbarActions"] a[href*="github"],
[data-testid="stToolbarActions"] button[title*="GitHub"],
[data-testid="stToolbarActions"] [aria-label*="GitHub"],
[data-testid="stToolbarActions"] [aria-label*="github"],
.stToolbarActions a[href*="github"] {
    display: none !important;
    visibility: hidden !important;
}
/* 앱매니저(Manage app)는 모두에게 표시 */
[data-testid="manage-app-button"],
.stDeployButton {
    display: flex !important;
    visibility: visible !important;
}
</style>"""

_SHOW_ALL_UI = """<style>
/* 관리자 페이지: GitHub 포함 전체 표시 */
[data-testid="stToolbarActions"],
[data-testid="stToolbarActions"] a,
[data-testid="stToolbarActions"] button,
[data-testid="manage-app-button"],
.stDeployButton {
    display: flex !important;
    visibility: visible !important;
}
</style>"""


def inject_pro_css(hide_toolbar: bool = True, show_logout: bool = True):
    st.markdown(_PWA_META, unsafe_allow_html=True)
    st.markdown(generate_css(), unsafe_allow_html=True)
    st.markdown(LAYOUT_CSS, unsafe_allow_html=True)
    st.markdown(COMPONENTS_CSS, unsafe_allow_html=True)
    _viewer = st.session_state.get("user")
    _is_admin = bool(_viewer and _viewer.get("role") == "admin")
    _caller_file = ""
    try:
        import traceback as _tb

        for _frame in _tb.extract_stack():
            if "pages/" in _frame.filename:
                _caller_file = _frame.filename
                break
    except Exception:
        pass
    _is_admin_page = "관리자" in _caller_file or "99_" in _caller_file
    if hide_toolbar:
        if _is_admin and _is_admin_page:
            st.markdown(_SHOW_ALL_UI, unsafe_allow_html=True)
        else:
            st.markdown(_HIDE_GITHUB_ONLY, unsafe_allow_html=True)

    user = _viewer
    if not user:
        return

    st.markdown(_ANALYTICS_CODE, unsafe_allow_html=True)
    st.markdown(
        """
<div class="mobile-bottom-nav">
<div class="nav-items">
<a onclick="archonNav('/')" class="nav-item" style="cursor:pointer"><span class="nav-icon">🏠</span>홈</a>
<a onclick="archonNav('/매매')" class="nav-item" style="cursor:pointer"><span class="nav-icon">📈</span>매매</a>
<a onclick="archonNav('/분석')" class="nav-item" style="cursor:pointer"><span class="nav-icon">📊</span>분석</a>
<a onclick="archonNav('/포트폴리오')" class="nav-item" style="cursor:pointer"><span class="nav-icon">💼</span>포트폴리오</a>
<a onclick="archonNav('/설정')" class="nav-item" style="cursor:pointer"><span class="nav-icon">⚙️</span>설정</a>
</div>
</div>
""",
        unsafe_allow_html=True,
    )

    components.html(
        """
<script>
(function syncArchonMobileOverlay(){
    var rootWindow = window.parent || window;
    var rootDocument = rootWindow.document;

    function archonWithAuth(url) {
        try {
            var token = rootWindow.localStorage.getItem('archon_auth_token') || '';
            if (!token) { return url; }
            var u = new URL(url, rootWindow.location.origin);
            u.searchParams.set('_auth', token);
            return u.pathname + u.search + u.hash;
        } catch (e) {
            return url;
        }
    }

    rootWindow.archonNav = function(path) {
        try {
            rootWindow.location.href = archonWithAuth(path);
        } catch (e) {
            rootWindow.location.href = path;
        }
    };

    function patchSidebarLinks() {
        try {
            var links = rootDocument.querySelectorAll('[data-testid="stSidebarNav"] a[href], [data-testid="stSidebarUserContent"] a[href]');
            links.forEach(function(link) {
                if (link.dataset.archonAuthPatched === '1') {
                    return;
                }
                link.dataset.archonAuthPatched = '1';
                var href = link.getAttribute('href') || '';
                if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.indexOf('mailto:') === 0) {
                    return;
                }
                link.setAttribute('href', archonWithAuth(href));
                link.addEventListener('click', function() {
                    var latest = link.getAttribute('href') || href;
                    link.setAttribute('href', archonWithAuth(latest));
                });
            });
        } catch (e) {}
    }

    function applySidebarState() {
        var sidebar = rootDocument.querySelector('[data-testid="stSidebar"]');
        var opened = !!(sidebar && sidebar.getAttribute('aria-expanded') === 'true');
        rootDocument.body.classList.toggle('archon-sidebar-open', opened);

        var isMobile = rootWindow.matchMedia('(max-width: 768px)').matches;
        var manageBtn = rootDocument.querySelector('[data-testid="manage-app-button"]');
        var deployBtn = rootDocument.querySelector('.stDeployButton');
        var hideFloating = isMobile && opened;

        if (manageBtn) {
            manageBtn.style.opacity = hideFloating ? '0' : '1';
            manageBtn.style.pointerEvents = hideFloating ? 'none' : 'auto';
        }
        if (deployBtn) {
            deployBtn.style.opacity = hideFloating ? '0' : '1';
            deployBtn.style.pointerEvents = hideFloating ? 'none' : 'auto';
        }
    }

    function bindObserver() {
        applySidebarState();
        patchSidebarLinks();
        var sidebar = rootDocument.querySelector('[data-testid="stSidebar"]');
        if (!sidebar || sidebar.dataset.archonObserved === '1') {
            return;
        }
        sidebar.dataset.archonObserved = '1';
        var observer = new MutationObserver(function() {
            applySidebarState();
            patchSidebarLinks();
        });
        observer.observe(sidebar, { attributes: true, childList: true, subtree: true, attributeFilter: ['aria-expanded', 'href'] });
    }

    bindObserver();
    rootWindow.setTimeout(bindObserver, 350);
    rootWindow.setTimeout(bindObserver, 1000);
    rootWindow.setTimeout(patchSidebarLinks, 1500);
})();
</script>
""",
        height=0,
        width=0,
    )

    from data.database import log_activity

    _caller = inspect.stack()[1].filename
    _page_name = os.path.basename(_caller).replace(".py", "")
    _last_page = st.session_state.get("_last_logged_page", "")
    if _page_name != _last_page:
        log_activity(user["username"], "page_visit", _page_name)
        st.session_state["_last_logged_page"] = _page_name

    with st.sidebar:
        if show_logout:
            st.markdown("---")
            if st.button("Logout", key="_global_logout", use_container_width=True):
                from config.auth import logout as _auth_logout

                _auth_logout()

        with st.expander("내 기기 관리", expanded=False):
            render_device_manager(user)

        st.markdown("---")
        from config.i18n import show_lang_selector, t as _t

        with st.expander("🌐 " + _t("language"), expanded=False):
            show_lang_selector()

        render_app_search()

        with st.expander("🤖 앱 가이드", expanded=False):
            render_guide_chatbot(user)


def show_toast(message: str, toast_type: str = "success"):
    st.markdown(
        f'<div class="archon-toast {toast_type}">{message}</div>',
        unsafe_allow_html=True,
    )


def show_skeleton(count: int = 3):
    for _ in range(count):
        st.markdown('<div class="skeleton-loader"></div>', unsafe_allow_html=True)


def show_share_buttons():
    _url = "https://archon-pro.streamlit.app"
    _c1, _c2, _c3 = st.columns(3)
    with _c1:
        st.link_button("💬 카카오톡 공유", f"https://sharer.kakao.com/talk/friends/picker/link?url={_url}", use_container_width=True)
    with _c2:
        st.link_button("🐦 트위터 공유", f"https://twitter.com/intent/tweet?text=Archon%20AI&url={_url}", use_container_width=True)
    with _c3:
        if st.button("🔗 링크 복사", use_container_width=True, key="_share_copy"):
            st.code(_url)
            st.toast("링크가 표시되었습니다!")


def save_user_preferences(username: str, page: str, settings: dict[str, Any]):
    from data.database import save_user_setting

    save_user_setting(username, f"page_{page}", json.dumps(settings))


def load_user_preferences(username: str, page: str) -> dict[str, Any]:
    from data.database import load_user_setting

    raw = load_user_setting(username, f"page_{page}")
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def show_legal_disclaimer():
    st.caption("⚠️ 본 서비스는 투자 참고용이며 투자자문에 해당하지 않습니다. 투자 결과의 책임은 이용자에게 있으며, 원금 손실이 발생할 수 있습니다.")


def require_plan(user: dict[str, Any], min_plan: str, feature_name: str) -> bool:
    plan_order = {"free": 0, "plus": 1, "pro": 2}
    required_plan = str(min_plan).lower()
    if required_plan not in plan_order:
        required_plan = "free"

    role = str((user or {}).get("role", ""))
    current_plan = str((user or {}).get("plan", "free")).lower()
    if current_plan not in plan_order:
        current_plan = "free"

    if role == "admin" or plan_order[current_plan] >= plan_order[required_plan]:
        return True

    required_label = {"free": "Free", "plus": "Plus", "pro": "Pro"}[required_plan]
    st.markdown(
        f"""
        <div style="
            margin: 1.25rem 0;
            padding: 1.25rem;
            border-radius: 14px;
            border: 1px solid rgba(56, 189, 248, 0.35);
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(10, 14, 25, 0.95));
        ">
            <div style="font-size: 1.2rem; font-weight: 700; color: #E2E8F0; margin-bottom: 0.45rem;">
                🔒 {feature_name}
            </div>
            <div style="color: #94A3B8; font-size: 0.96rem;">
                이 기능은 <b style=\"color:#38BDF8;\">{required_label}</b> 플랜 이상에서 이용할 수 있습니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button("업그레이드", "/결제", use_container_width=False)
    return False


def safe_run(func: Callable[[], Any], fallback_msg: str = "일시적 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") -> Optional[Any]:
    try:
        return func()
    except Exception as e:
        st.error(f"{fallback_msg}")
        with st.expander("오류 상세"):
            st.code(str(e))
        return None


def safe_fetch(fetch_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Optional[Any]:
    try:
        result = fetch_func(*args, **kwargs)
        if result is None:
            st.warning("데이터를 가져올 수 없습니다. 잠시 후 다시 시도해주세요.")
        return result
    except ConnectionError:
        st.error("네트워크 연결을 확인해주세요.")
        return None
    except TimeoutError:
        st.error("서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.")
        return None
    except Exception as e:
        st.error(f"데이터 로딩 실패: {type(e).__name__}")
        return None
