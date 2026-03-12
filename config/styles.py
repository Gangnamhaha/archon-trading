import streamlit as st

_PRO_CSS = """<style>
.stMetric{background:#1A1F2E;padding:1rem;border-radius:8px;border:1px solid #2D3748}
.stMetric label{color:#A0AEC0 !important}
.stMetric [data-testid="stMetricValue"]{color:#00D4AA !important}
div[data-testid="stExpander"]{background:#1A1F2E;border:1px solid #2D3748;border-radius:8px}
h1,h2,h3{color:#E2E8F0 !important}

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
    .stTabs [data-baseweb="tab-list"]{gap:0 !important}
    .stTabs [data-baseweb="tab"]{padding:0.5rem 0.8rem !important;font-size:0.85rem !important}
    .stDataFrame{font-size:0.75rem !important}
    .js-plotly-plot .plotly .modebar{display:none !important}
    .stPlotlyChart{margin-left:-0.5rem;margin-right:-0.5rem}
    div[data-testid="stSidebarNav"]{padding-top:1rem}
    .feature-grid{grid-template-columns:1fr !important}
    .main-header h1{font-size:1.3rem !important}
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
}
</style>"""


def inject_pro_css():
    st.markdown(_PRO_CSS, unsafe_allow_html=True)
