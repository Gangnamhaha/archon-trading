import streamlit as st

from views.home import render_home
from views.trading import render_trading
from views.analysis import render_analysis
from views.portfolio import render_portfolio
from views.settings import render_settings

st.set_page_config(
    page_title="Archon",
    page_icon="📈",
    layout="wide",
)

home_page = st.Page(render_home, title="홈", icon="🏠", default=True)
trading_page = st.Page(render_trading, title="매매", icon="⚡")
analysis_page = st.Page(render_analysis, title="분석", icon="📊")
portfolio_page = st.Page(render_portfolio, title="포트폴리오", icon="📁")
settings_page = st.Page(render_settings, title="설정", icon="⚙️")

pages = [home_page, trading_page, analysis_page, portfolio_page, settings_page]
pg = st.navigation(pages)
pg.run()
