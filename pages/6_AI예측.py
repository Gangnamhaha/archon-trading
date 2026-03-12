import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from data.fetcher import fetch_stock
from analysis.ai_predict import predict_ensemble
from config.styles import inject_pro_css
from config.auth import require_auth

st.set_page_config(page_title="AI Prediction", page_icon="", layout="wide")
require_auth()
inject_pro_css()
st.title("AI Price Prediction")

st.sidebar.header("Settings")
market = st.sidebar.selectbox("Market", ["US", "KR"])
ticker = st.sidebar.text_input("Ticker", value="005930" if market == "KR" else "AAPL")
period = st.sidebar.selectbox("Training Period", ["6mo", "1y", "2y"], index=1)
forecast_days = st.sidebar.slider("Forecast Days", 5, 90, 30)

if st.sidebar.button("Run Prediction", type="primary", use_container_width=True):
    with st.spinner("Running AI models..."):
        df = fetch_stock(ticker, market, period)

    if df.empty:
        st.error("Failed to fetch data.")
    else:
        with st.spinner("Training models..."):
            results = predict_ensemble(df, forecast_days)

        ensemble = results.get("ensemble", {})
        if "error" in ensemble:
            st.error(f"Prediction failed: {ensemble['error']}")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"{ensemble['last_price']:,.0f}")
            predicted = ensemble['predicted_price']
            ret = ensemble['predicted_return']
            col2.metric("Predicted Price", f"{predicted:,.0f}", f"{ret:+.2f}%")
            col3.metric("Models Used", ensemble.get("model", ""))

            st.markdown("---")

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"],
                name="Historical", line=dict(color="#00D4AA", width=2)
            ))

            model_colors = {"Holt-Winters": "#FF6B6B", "ARIMA": "#4ECDC4", "ML Regression": "#FFE66D"}
            for model_name, pred in results.items():
                if model_name == "ensemble" or "error" in pred:
                    continue
                if "forecast_index" in pred and "forecast" in pred:
                    color = model_colors.get(model_name, "#888")
                    fig.add_trace(go.Scatter(
                        x=pred["forecast_index"], y=pred["forecast"],
                        name=model_name, line=dict(color=color, width=1, dash="dash")
                    ))
                    if "upper" in pred and "lower" in pred:
                        fig.add_trace(go.Scatter(
                            x=pred["forecast_index"], y=pred["upper"],
                            name=f"{model_name} Upper", line=dict(width=0),
                            showlegend=False
                        ))
                        fig.add_trace(go.Scatter(
                            x=pred["forecast_index"], y=pred["lower"],
                            name=f"{model_name} CI", fill="tonexty",
                            fillcolor=color.replace(")", ",0.1)").replace("rgb", "rgba") if "rgb" in color else f"rgba(200,200,200,0.1)",
                            line=dict(width=0), showlegend=False
                        ))

            if "forecast" in ensemble and hasattr(ensemble["forecast"], '__len__'):
                forecast_idx = pd.date_range(df.index[-1], periods=forecast_days + 1, freq="B")[1:]
                fig.add_trace(go.Scatter(
                    x=forecast_idx, y=ensemble["forecast"],
                    name="Ensemble", line=dict(color="#FFFFFF", width=3)
                ))

            fig.update_layout(
                height=600, title=f"{ticker} AI Price Forecast ({forecast_days} days)",
                xaxis_title="Date", yaxis_title="Price",
                template="plotly_dark", hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Model Results")
            model_table = []
            for name, pred in results.items():
                if name == "ensemble":
                    continue
                if "error" in pred:
                    model_table.append({"Model": name, "Status": "Failed", "Predicted": "-", "Return": "-"})
                else:
                    model_table.append({
                        "Model": pred.get("model", name),
                        "Status": "OK",
                        "Predicted": f"{pred['predicted_price']:,.0f}",
                        "Return (%)": f"{pred['predicted_return']:+.2f}",
                        "R2": pred.get("r2_score", "-"),
                    })
            st.dataframe(pd.DataFrame(model_table), use_container_width=True, hide_index=True)

            st.warning("AI predictions are for reference only and do not guarantee future returns.")
else:
    st.info("Set parameters and click 'Run Prediction'.")
