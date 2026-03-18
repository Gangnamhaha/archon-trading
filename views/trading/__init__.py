import streamlit as st

from config.auth import require_auth
from config.styles import inject_pro_css


def render_trading() -> None:
    user = require_auth()
    inject_pro_css()

    st.title("⚡ 매매")

    selected = st.radio(
        "섹션",
        ["🇰🇷 국내주식", "💱 외환", "🪙 코인"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if selected == "🇰🇷 국내주식":
        from views.trading.stock import render_stock

        render_stock(user)
    elif selected == "💱 외환":
        from views.trading.fx import render_fx

        render_fx(user)
    elif selected == "🪙 코인":
        from views.trading.crypto import render_crypto

        render_crypto(user)
