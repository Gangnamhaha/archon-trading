LAYOUT_CSS = """<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&display=swap');

/* CSS custom properties are now defined in tokens.py via generate_css() */

html{-webkit-text-size-adjust:100%}
body{-webkit-tap-highlight-color:transparent;overscroll-behavior-y:contain;font-family:var(--font-family) !important}
[data-testid="stAppViewContainer"],.stApp,section[data-testid="stMain"]{background:var(--color-bg) !important;color:var(--color-text) !important}

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
    [data-testid="stSidebar"][aria-expanded="true"]{min-width:85vw !important;max-width:85vw !important;transform:translateX(0) !important;box-shadow:4px 0 20px rgba(0,0,0,0.15) !important}
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
    background:linear-gradient(90deg,var(--color-primary-light),transparent) !important;
    border-left:3px solid var(--color-primary) !important;
    font-weight:600 !important;
}
[data-testid="stSidebarNav"] a{
    padding:0.4rem 0.8rem !important;border-radius:4px;transition:background 0.2s;
    border-left:3px solid transparent !important;
}
[data-testid="stSidebarNav"] a:hover{background:var(--color-primary-light) !important}

@media(hover:none) and (pointer:coarse){
    .stButton>button{min-height:3rem;padding:0.6rem 1rem}
    .stSelectbox>div>div{min-height:2.8rem}
    .stTextInput>div>div{min-height:2.8rem}
    .stNumberInput>div>div{min-height:2.8rem}
    a,button{cursor:default}
    .stSlider [role="slider"]{width:24px !important;height:24px !important}
    .stCheckbox label{padding:0.4rem 0 !important}
}

.mobile-bottom-nav{display:none;position:fixed;bottom:0;left:0;right:0;background:var(--color-surface);border-top:1px solid var(--color-border);z-index:2147483647;padding:0.3rem 0 env(safe-area-inset-bottom,0.3rem);box-shadow:0 -4px 16px rgba(0,0,0,0.1)}
.mobile-bottom-nav .nav-items{display:flex;justify-content:space-around;align-items:center;max-width:500px;margin:0 auto}
.mobile-bottom-nav .nav-item{display:flex;flex-direction:column;align-items:center;justify-content:center;text-decoration:none;color:var(--color-text-secondary);font-size:0.65rem;padding:0.5rem 0.75rem;min-height:var(--mobile-min-touch-target);min-width:var(--mobile-min-touch-target);transition:color 0.2s}
.mobile-bottom-nav .nav-item:hover{color:var(--color-primary)}
.mobile-bottom-nav .nav-icon{font-size:1.2rem;margin-bottom:0.15rem}
@media(max-width:768px){
.mobile-bottom-nav{display:block !important}
.mobile-bottom-nav{min-height:var(--mobile-bottom-nav-height) !important}
.main .block-container{padding-bottom:calc(var(--mobile-bottom-nav-height) + 2.6rem) !important}
[data-testid="manage-app-button"]{position:fixed !important;right:0.75rem !important;bottom:calc(var(--mobile-bottom-nav-height) + 0.9rem) !important;z-index:2147483646 !important}
.stDeployButton{position:fixed !important;right:0.75rem !important;bottom:calc(var(--mobile-bottom-nav-height) + 4.9rem) !important;z-index:2147483646 !important}
iframe[title="streamlitApp"] ~ * [data-testid="manage-app-button"]{bottom:calc(var(--mobile-bottom-nav-height) + 0.9rem) !important}
@media(max-width:560px){
[data-testid="manage-app-button"]{top:0.8rem !important;bottom:auto !important;right:0.6rem !important}
.stDeployButton{top:4.3rem !important;bottom:auto !important;right:0.6rem !important}
iframe[title="streamlitApp"] ~ * [data-testid="manage-app-button"]{top:0.8rem !important;bottom:auto !important}
}
body.archon-sidebar-open .mobile-bottom-nav{opacity:0.22 !important;pointer-events:none !important}
body.archon-sidebar-open [data-testid="manage-app-button"],
body.archon-sidebar-open .stDeployButton{opacity:0 !important;pointer-events:none !important}
}

/* Page transition */
.main .block-container{
    animation:fadeInUp 0.3s ease-out !important;
}
@keyframes fadeInUp{
    from{opacity:0;transform:translateY(10px)}
    to{opacity:1;transform:translateY(0)}
}
</style>"""
