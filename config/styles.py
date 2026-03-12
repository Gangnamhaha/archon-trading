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
    [data-testid="stSidebar"]{min-width:85vw !important;max-width:85vw !important}
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
    [data-testid="stSidebar"]{min-width:100vw !important;max-width:100vw !important}
}

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


def inject_pro_css():
    st.markdown(_PWA_META, unsafe_allow_html=True)
    st.markdown(_PRO_CSS, unsafe_allow_html=True)
