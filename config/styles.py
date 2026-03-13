import streamlit as st

_PWA_META = """
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Archon">
<meta name="theme-color" content="#0E1117">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<link rel="manifest" href="app/static/manifest.json">
<link rel="apple-touch-icon" sizes="192x192" href="app/static/icon-192.png">
"""

_PRO_CSS = """<style>
html{-webkit-text-size-adjust:100%}
body{-webkit-tap-highlight-color:transparent;overscroll-behavior-y:contain}

.stMetric{background:#1A1F2E;padding:1rem;border-radius:8px;border:1px solid #2D3748}
.stMetric label{color:#A0AEC0 !important}
.stMetric [data-testid="stMetricValue"]{color:#00D4AA !important}
div[data-testid="stExpander"]{background:#1A1F2E;border:1px solid #2D3748;border-radius:8px}
h1,h2,h3{color:#E2E8F0 !important}

input,select,textarea{font-size:16px !important}
.stButton>button{-webkit-tap-highlight-color:transparent;touch-action:manipulation}
.stSelectbox,.stTextInput,.stNumberInput{touch-action:manipulation}

@media(max-width:768px){
    .main .block-container{padding:0.5rem 0.8rem !important}
    [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;gap:0.3rem !important}
    [data-testid="stHorizontalBlock"]>div{flex:1 1 100% !important;min-width:100% !important}
    .stMetric{padding:0.5rem;margin-bottom:0.2rem}
    .stButton>button{min-height:2.8rem;font-size:1rem}
    h1{font-size:1.4rem !important}
    h2{font-size:1.15rem !important}
    h3{font-size:1rem !important}
    [data-testid="stForm"]{padding:0.5rem !important}
    .stTabs [data-baseweb="tab-list"]{gap:0 !important;overflow-x:auto;-webkit-overflow-scrolling:touch}
    .stTabs [data-baseweb="tab"]{padding:0.5rem 0.8rem !important;font-size:0.85rem !important;white-space:nowrap}
    .stDataFrame{font-size:0.75rem !important}
    .stDataFrame [data-testid="stDataFrameResizable"]{overflow-x:auto !important;-webkit-overflow-scrolling:touch}
    .js-plotly-plot .plotly .modebar{display:none !important}
    .stPlotlyChart{margin-left:-0.5rem;margin-right:-0.5rem}
    div[data-testid="stSidebarNav"]{padding-top:1rem}
    .feature-grid{grid-template-columns:1fr !important}
    .main-header h1{font-size:1.3rem !important}
    section[data-testid="stMain"]{margin-left:0 !important;width:100% !important}
    [data-testid="stSidebar"]{position:fixed !important;top:0 !important;left:0 !important;height:100vh !important;z-index:999999 !important;transition:transform 0.3s ease !important}
    [data-testid="stSidebar"][aria-expanded="true"]{min-width:85vw !important;max-width:85vw !important;transform:translateX(0) !important;box-shadow:4px 0 20px rgba(0,0,0,0.5) !important}
    [data-testid="stSidebar"][aria-expanded="false"]{min-width:0 !important;max-width:0 !important;transform:translateX(-100%) !important;overflow:hidden !important;box-shadow:none !important}
    [data-testid="stSidebar"] .block-container{padding:0.5rem !important}
}

@media(max-width:1024px) and (min-width:769px){
    .main .block-container{padding:1rem 1.5rem !important}
    [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important}
    [data-testid="stHorizontalBlock"]>div{flex:1 1 45% !important;min-width:45% !important}
    .feature-grid{grid-template-columns:repeat(2,1fr) !important}
}

@media(max-width:480px){
    .main .block-container{padding:0.3rem 0.5rem !important}
    .stMetric{padding:0.4rem;font-size:0.85rem}
    .stMetric [data-testid="stMetricValue"]{font-size:1.1rem !important}
    .stMetric [data-testid="stMetricDelta"]{font-size:0.7rem !important}
    h1{font-size:1.2rem !important}
    .stButton>button{min-height:3rem;font-size:1.05rem}
    .stSelectbox>div>div,.stTextInput>div>div,.stNumberInput>div>div{min-height:2.5rem}
    [data-testid="stSidebar"][aria-expanded="true"]{min-width:100vw !important;max-width:100vw !important}
}

[data-testid="stSidebarNav"] a[aria-current="page"]{
    background:linear-gradient(90deg,rgba(0,212,170,0.15),transparent) !important;
    border-left:3px solid #00D4AA !important;
    font-weight:600 !important;
}
[data-testid="stSidebarNav"] a{
    padding:0.4rem 0.8rem !important;border-radius:4px;transition:background 0.2s;
    border-left:3px solid transparent !important;
}
[data-testid="stSidebarNav"] a:hover{background:rgba(0,212,170,0.08) !important}

@keyframes skeleton-pulse{
    0%{background-position:-200px 0}
    100%{background-position:calc(200px + 100%) 0}
}
.skeleton-loader{
    background:linear-gradient(90deg,rgba(26,31,46,1) 25%,rgba(45,55,72,1) 50%,rgba(26,31,46,1) 75%);
    background-size:200px 100%;
    animation:skeleton-pulse 1.5s ease-in-out infinite;
    border-radius:8px;height:80px;margin:0.5rem 0;
}

@keyframes toast-in{0%{transform:translateX(100%);opacity:0}100%{transform:translateX(0);opacity:1}}
@keyframes toast-out{0%{opacity:1}100%{opacity:0;transform:translateY(-20px)}}
.archon-toast{
    position:fixed;top:1rem;right:1rem;z-index:99999;
    padding:0.8rem 1.2rem;border-radius:8px;
    font-size:0.9rem;font-weight:500;
    animation:toast-in 0.3s ease-out,toast-out 0.3s ease-in 2.7s forwards;
    box-shadow:0 4px 12px rgba(0,0,0,0.3);pointer-events:none;
}
.archon-toast.success{background:rgba(0,212,170,0.95);color:black}
.archon-toast.error{background:rgba(212,80,80,0.95);color:white}
.archon-toast.info{background:rgba(66,133,244,0.95);color:white}

@media(hover:none) and (pointer:coarse){
    .stButton>button{min-height:3rem;padding:0.6rem 1rem}
    .stSelectbox>div>div{min-height:2.8rem}
    .stTextInput>div>div{min-height:2.8rem}
    .stNumberInput>div>div{min-height:2.8rem}
    a,button{cursor:default}
    .stSlider [role="slider"]{width:24px !important;height:24px !important}
    .stCheckbox label{padding:0.4rem 0 !important}
}
</style>"""


_HIDE_ADMIN_UI = """<style>
.stAppToolbar,
.stToolbarActions,
.stMainMenu,
.stDeployButton,
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
[data-testid="stMainMenu"],
[data-testid="manage-app-button"],
#MainMenu {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    pointer-events: none !important;
}
</style>"""


def inject_pro_css():
    st.markdown(_PWA_META, unsafe_allow_html=True)
    st.markdown(_PRO_CSS, unsafe_allow_html=True)
    st.markdown(_HIDE_ADMIN_UI, unsafe_allow_html=True)


def show_toast(message: str, toast_type: str = "success"):
    st.markdown(
        f'<div class="archon-toast {toast_type}">{message}</div>',
        unsafe_allow_html=True,
    )


def show_skeleton(count: int = 3):
    for _ in range(count):
        st.markdown('<div class="skeleton-loader"></div>', unsafe_allow_html=True)
