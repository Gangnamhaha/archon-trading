import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(
    page_title="Archon - Trading Terminal",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .main-header {
        background: linear-gradient(135deg, #0E1117 0%, #1A1F2E 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border: 1px solid #2D3748;
        margin-bottom: 1.5rem;
    }
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin: 1.5rem 0;
    }
    .feature-item {
        background: #1A1F2E;
        padding: 1.2rem;
        border-radius: 10px;
        border: 1px solid #2D3748;
        transition: border-color 0.3s;
    }
    .feature-item:hover { border-color: #00D4AA; }
    .feature-item h4 { color: #00D4AA; margin: 0 0 0.5rem 0; }
    .feature-item p { color: #A0AEC0; font-size: 0.85rem; margin: 0; }
    .pro-badge {
        display: inline-block;
        background: linear-gradient(135deg, #00D4AA, #00B894);
        color: #0E1117;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        margin-left: 0.5rem;
    }
    .stMetric { background: #1A1F2E; padding: 1rem; border-radius: 8px; }

    @media(max-width:768px){
        .main .block-container{padding:0.5rem 0.8rem !important}
        [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;gap:0.3rem !important}
        [data-testid="stHorizontalBlock"]>div{flex:1 1 100% !important;min-width:100% !important}
        .feature-grid{grid-template-columns:1fr !important}
        .main-header h1{font-size:1.3rem !important}
        .main-header p{font-size:0.85rem !important}
        .feature-item h4{font-size:0.95rem}
        .feature-item p{font-size:0.8rem}
    }
    @media(max-width:1024px) and (min-width:769px){
        .feature-grid{grid-template-columns:repeat(2,1fr) !important}
    }
    @media(max-width:480px){
        .main .block-container{padding:0.3rem 0.5rem !important}
        .feature-grid{grid-template-columns:1fr !important;gap:0.6rem !important}
        .feature-item{padding:0.8rem}
        .main-header{padding:1rem}
        .main-header h1{font-size:1.1rem !important}
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1 style="color: #00D4AA; margin: 0;">Archon Trading Terminal</h1>
    <p style="color: #A0AEC0; margin: 0.3rem 0 0 0;">
        AI-Powered Stock Analysis & Trading Platform
        <span class="pro-badge">PRO</span>
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="feature-grid">
    <div class="feature-item">
        <h4>Data Analysis</h4>
        <p>Real-time price data, candlestick charts, multi-stock comparison for KR & US markets</p>
    </div>
    <div class="feature-item">
        <h4>Technical Analysis</h4>
        <p>15+ indicators: SMA, RSI, MACD, Bollinger, Ichimoku, ATR, OBV, ADX, CCI, Williams %R</p>
    </div>
    <div class="feature-item">
        <h4>Backtesting Engine</h4>
        <p>Strategy testing with equity curves, Sharpe ratio, MDD, win rate analysis</p>
    </div>
    <div class="feature-item">
        <h4>AI Prediction</h4>
        <p>Ensemble forecasting: Holt-Winters, ARIMA, ML Regression with confidence intervals</p>
    </div>
    <div class="feature-item">
        <h4>Risk Analytics</h4>
        <p>VaR, CVaR, Sortino, Beta/Alpha, Efficient Frontier portfolio optimization</p>
    </div>
    <div class="feature-item">
        <h4>Monte Carlo</h4>
        <p>1000+ path simulations, probability distributions, confidence intervals</p>
    </div>
    <div class="feature-item">
        <h4>Stock Screener</h4>
        <p>Multi-condition filtering, preset strategies, RSI/MACD/volume-based screening</p>
    </div>
    <div class="feature-item">
        <h4>News Sentiment</h4>
        <p>RSS news aggregation, keyword-based sentiment analysis, market mood tracking</p>
    </div>
    <div class="feature-item">
        <h4>Auto Trading Bot</h4>
        <p>KIS API integration, strategy-based orders, real-time signal monitoring</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### Navigation")
st.sidebar.info(
    "KR: KRX (KOSPI/KOSDAQ)\n\n"
    "US: NYSE / NASDAQ"
)
st.sidebar.markdown("---")
st.sidebar.markdown("**Archon** v2.0 | Python 3.9+")
