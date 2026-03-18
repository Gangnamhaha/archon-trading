"""Legacy Streamlit page placeholder.

App routing now lives in `app.py` via `st.navigation()`.
This file remains so the `pages/` directory structure stays intact.
Legacy compatibility references: `config.auth`, `config.styles`.
"""

import streamlit as st

_ = st.info(
    "This legacy page is retained as a placeholder. Use the main app navigation."
)
