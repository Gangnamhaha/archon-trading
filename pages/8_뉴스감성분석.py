import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data.news import fetch_and_analyze, get_market_sentiment, NEWS_SOURCES
from config.styles import inject_pro_css

st.set_page_config(page_title="News Sentiment", page_icon="", layout="wide")
inject_pro_css()
st.title("News & Sentiment Analysis")

st.sidebar.header("Settings")
sources = st.sidebar.multiselect(
    "News Sources",
    list(NEWS_SOURCES.keys()),
    default=list(NEWS_SOURCES.keys())[:4]
)
keyword = st.sidebar.text_input("Keyword Filter", placeholder="e.g. Samsung, NVIDIA")

if st.sidebar.button("Fetch News", type="primary", use_container_width=True):
    with st.spinner("Fetching news and analyzing sentiment..."):
        sentiment_summary = get_market_sentiment(sources)
        news_df = fetch_and_analyze(sources, keyword if keyword else None)

    col1, col2, col3, col4 = st.columns(4)
    overall_color = "#00D4AA" if "긍정" in sentiment_summary["overall"] else (
        "#FF6B6B" if "부정" in sentiment_summary["overall"] else "#A0AEC0"
    )
    col1.markdown(f"### Market Mood\n<h2 style='color:{overall_color}'>{sentiment_summary['overall']}</h2>",
                  unsafe_allow_html=True)
    col2.metric("Positive", f"{sentiment_summary['positive_pct']}%")
    col3.metric("Negative", f"{sentiment_summary['negative_pct']}%")
    col4.metric("Total Articles", sentiment_summary["total"])

    st.markdown("---")

    if not news_df.empty:
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            sentiment_counts = news_df["감성"].value_counts()
            colors = {"긍정": "#00D4AA", "부정": "#FF6B6B", "중립": "#A0AEC0"}
            fig_pie = px.pie(
                values=sentiment_counts.values,
                names=sentiment_counts.index,
                color=sentiment_counts.index,
                color_discrete_map=colors,
                title="Sentiment Distribution"
            )
            fig_pie.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_chart2:
            source_sentiment = news_df.groupby(["출처", "감성"]).size().reset_index(name="count")
            fig_bar = px.bar(
                source_sentiment, x="출처", y="count", color="감성",
                color_discrete_map=colors, title="Sentiment by Source",
                barmode="group"
            )
            fig_bar.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader(f"News Articles ({len(news_df)})")
        for _, row in news_df.iterrows():
            sent_color = "#00D4AA" if row["감성"] == "긍정" else ("#FF6B6B" if row["감성"] == "부정" else "#A0AEC0")
            st.markdown(f"""
            <div style="background:#1A1F2E; padding:1rem; border-radius:8px; border-left: 3px solid {sent_color}; margin-bottom:0.5rem;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="color:#E0E0E0;">{row['제목'][:80]}</strong>
                    <span style="color:{sent_color}; font-weight:700;">{row['감성']} ({row['점수']:+.0f})</span>
                </div>
                <div style="color:#718096; font-size:0.8rem; margin-top:0.3rem;">
                    {row['출처']} | {row.get('발행일', '')[:25]}
                    {f" | <a href='{row['링크']}' target='_blank' style='color:#00D4AA;'>Link</a>" if row.get('링크') else ""}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("No articles found.")
else:
    st.info("Select news sources and click 'Fetch News'.")
