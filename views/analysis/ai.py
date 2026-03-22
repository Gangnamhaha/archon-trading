from datetime import datetime, timedelta
from typing import Any, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pykrx import stock as krx

from analysis.ai_predict import predict_ensemble
from analysis.recommender import recommend_aggressive_stocks, recommend_stocks
from analysis.technical import calc_rsi
from config.auth import is_pro
from config.styles import load_user_preferences, require_plan, save_user_preferences, show_legal_disclaimer
from data.fetcher import fetch_stock
from data.screener import PRESETS, get_krx_market_data, screen_stocks


def render_ai(user: dict[str, Any]) -> None:
    section = st.radio("하위 섹션", ["🔎 종목스크리너", "🏆 종목추천", "🤖 AI예측"], horizontal=True, key="ai_subsection")
    if section == "🔎 종목스크리너":
        _render_screener()
    elif section == "🏆 종목추천":
        _render_recommendations()
    else:
        _render_prediction(user)


@st.cache_data(ttl=300)
def _get_momentum_scalping_signals(market: str) -> pd.DataFrame:
    columns = pd.Index(["종목코드", "종목명", "현재가", "등락률(%)", "거래량비율", "RSI"])
    today = datetime.now()
    frames: list[pd.DataFrame] = []
    cursor = today
    while len(frames) < 21:
        try:
            daily = krx.get_market_ohlcv_by_ticker(cursor.strftime("%Y%m%d"), market=market)
        except Exception:
            daily = pd.DataFrame()
        required = {"시가", "고가", "저가", "종가", "거래량"}
        if not daily.empty and required.issubset(set(daily.columns.astype(str).tolist())):
            frames.append(daily)
        cursor -= timedelta(days=1)
        if (today - cursor).days > 45:
            break
    if len(frames) < 2:
        return pd.DataFrame(columns=columns)

    current = frames[0].copy()
    avg_volume_obj = pd.concat([f["거래량"] for f in frames[1:]], axis=1).mean(axis=1)
    if not isinstance(avg_volume_obj, pd.Series):
        return pd.DataFrame(columns=columns)
    avg_volume = avg_volume_obj.mask(avg_volume_obj == 0)
    current["거래량비율"] = current["거래량"] / avg_volume
    current["등락률(%)"] = (current["종가"] / current["시가"] - 1) * 100
    candidates = current[(current["거래량비율"] > 3) & (current["등락률(%)"] > 2)].copy()
    if candidates.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    start = (today - timedelta(days=120)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    for ticker, row in candidates.iterrows():
        try:
            ohlcv = krx.get_market_ohlcv(start, end, ticker)
            if ohlcv.empty or len(ohlcv) < 15:
                continue
            close_df: pd.DataFrame = ohlcv.rename(columns={"종가": "Close"}).loc[:, ["Close"]].copy()
            rsi_val = calc_rsi(close_df)["RSI"].iloc[-1]
            if pd.isna(rsi_val) or rsi_val >= 70:
                continue
            rows.append({
                "종목코드": ticker,
                "종목명": krx.get_market_ticker_name(str(ticker)),
                "현재가": int(row["종가"]),
                "등락률(%)": round(float(row["등락률(%)"]), 2),
                "거래량비율": round(float(row["거래량비율"]), 2),
                "RSI": round(float(rsi_val), 2),
            })
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values("등락률(%)", ascending=False).reset_index(drop=True) if rows else pd.DataFrame(columns=columns)


def _render_screener() -> None:
    st.subheader("🔎 종목 스크리너")
    user_is_pro = is_pro()
    market = str(st.sidebar.selectbox("Market", ["KOSPI", "KOSDAQ"], key="scr_market") or "KOSPI")
    top_n = int(st.sidebar.slider("Scan Top N Stocks", 20, 200, 50, key="scr_top_n"))
    preset = str(st.sidebar.selectbox("Preset", ["Custom"] + list(PRESETS.keys()), key="scr_preset") or "Custom")
    rsi_range = st.sidebar.slider("RSI Range", 0, 100, (20, 80), key="scr_rsi")
    macd_filter = st.sidebar.selectbox("MACD", ["All", "Golden Cross", "Dead Cross"], key="scr_macd")
    sma_filter = st.sidebar.selectbox("SMA 5/20 Trend", ["All", "Uptrend", "Downtrend"], key="scr_sma")
    vol_ratio_min = st.sidebar.slider("Min Volume Ratio", 0.0, 10.0, 0.0, 0.5, key="scr_vol") if user_is_pro else 0.0
    ret_range = st.sidebar.slider("1-Day Return Range (%)", -30.0, 30.0, (-10.0, 10.0), key="scr_ret") if user_is_pro else (-10.0, 10.0)
    if not user_is_pro:
        st.sidebar.caption("🔒 Volume Ratio, Return Range, 모멘텀 시그널은 Pro 전용")

    if st.sidebar.button("Run Screener", type="primary", use_container_width=True, key="run_screener"):
        raw_data = get_krx_market_data(market, top_n)
        if raw_data.empty:
            st.error("Failed to fetch market data.")
            return
        filters: dict[str, Any] = dict(PRESETS[preset]) if preset != "Custom" else {
            "RSI_min": rsi_range[0],
            "RSI_max": rsi_range[1],
            "return_1d_min": ret_range[0],
            "return_1d_max": ret_range[1],
        }
        if preset == "Custom":
            if macd_filter == "Golden Cross":
                filters["MACD_cross"] = "golden"
            elif macd_filter == "Dead Cross":
                filters["MACD_cross"] = "dead"
            if sma_filter == "Uptrend":
                filters["SMA_trend"] = "up"
            elif sma_filter == "Downtrend":
                filters["SMA_trend"] = "down"
            if vol_ratio_min > 0:
                filters["vol_ratio_min"] = vol_ratio_min

        filtered_df = pd.DataFrame(screen_stocks(raw_data, filters))
        st.session_state["screener_result"] = {
            "raw_count": len(raw_data),
            "filtered_df": filtered_df,
        }

    screener_result = st.session_state.get("screener_result")
    if isinstance(screener_result, dict):
        filtered_df = screener_result.get("filtered_df", pd.DataFrame())
        raw_count = int(screener_result.get("raw_count", 0))
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Scanned", raw_count)
        c2.metric("Filtered Results", len(filtered_df))
        c3.metric("Pass Rate", f"{len(filtered_df) / raw_count * 100:.1f}%" if raw_count else "0%")
        if filtered_df.empty:
            st.warning("No stocks matched the filters.")
        else:
            st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=500)

    st.markdown("---")
    st.caption("모멘텀 스캘핑 시그널")
    if user_is_pro:
        mdf = _get_momentum_scalping_signals(market)
        st.dataframe(mdf, use_container_width=True, hide_index=True) if not mdf.empty else st.info("조건을 만족하는 종목이 없습니다.")
    else:
        st.caption("Pro 전용")


def _render_recommendations() -> None:
    st.subheader("🏆 AI 종목추천")
    if not is_pro():
        st.warning("🔒 Pro 전용 기능입니다.")
        show_legal_disclaimer()
        return

    rec_mode = st.radio("추천 모드", ["📊 일반 추천", "🔥 공격적 추천"], horizontal=True, key="rec_mode")
    c1, c2, c3 = st.columns(3)
    market = str(c1.selectbox("시장", ["KOSPI", "KOSDAQ"], key="rec_market") or "KOSPI")
    scan_count = int(c2.selectbox("스캔 종목 수", [30, 50, 100, 200], index=2 if rec_mode == "🔥 공격적 추천" else 1, key="rec_scan") or 50)
    result_count = int(c3.selectbox("추천 표시 수", [10, 20, 30], index=1, key="rec_result_count") or 20)

    if st.button("종목 추천 시작", type="primary", use_container_width=True, key="run_recommend"):
        with st.spinner("종목 추천 분석 중..."):
            result = recommend_aggressive_stocks(market=market, top_n=scan_count, result_count=result_count) if rec_mode == "🔥 공격적 추천" else recommend_stocks(market=market, top_n=scan_count, result_count=result_count)
        st.session_state["recommend_result_key"] = "aggressive_result" if rec_mode == "🔥 공격적 추천" else "recommend_result"
        st.session_state[st.session_state["recommend_result_key"]] = result

    result_key = st.session_state.get("recommend_result_key", "recommend_result")
    if result_key in st.session_state:
        df = st.session_state[result_key]
        if isinstance(df, pd.DataFrame) and not df.empty:
            st.dataframe(df, use_container_width=True, height=600)
        else:
            st.warning("추천 결과가 없습니다.")
    show_legal_disclaimer()


def _render_prediction(user: dict[str, Any]) -> None:
    st.subheader("🤖 AI 예측")
    if not require_plan(user, "plus", "AI 예측"):
        show_legal_disclaimer()
        return

    market = st.sidebar.selectbox("Market", ["US", "KR"], key="pred_market")
    username = str((user or {}).get("username") or "")
    if username:
        saved_pred_auto = bool(load_user_preferences(username, "analysis").get("pred_auto_rerun", False))
        st.session_state.setdefault("_pred_auto_saved", saved_pred_auto)

    def _persist_pred_toggle() -> None:
        if not username:
            return
        pref = load_user_preferences(username, "analysis")
        pref["pred_auto_rerun"] = bool(st.session_state.get("pred_auto_rerun", False))
        save_user_preferences(username, "analysis", pref)
        st.session_state["_pred_auto_saved"] = pref["pred_auto_rerun"]

    if st.session_state.get("_prev_pred_market") != market:
        st.session_state["pred_ticker"] = "005930" if market == "KR" else "AAPL"
        st.session_state["_prev_pred_market"] = market

    ticker = st.sidebar.text_input("Ticker", value="005930" if market == "KR" else "AAPL", key="pred_ticker")
    period = st.sidebar.selectbox("Training Period", ["6mo", "1y", "2y"], index=1, key="pred_period")
    forecast_days = int(st.sidebar.slider("Forecast Days", 5, 90, 30, key="pred_days"))
    auto_predict = bool(
        st.sidebar.toggle(
            "입력 변경 시 자동 예측",
            value=bool(st.session_state.get("pred_auto_rerun", st.session_state.get("_analysis_pref_last", {}).get("pred_auto_rerun", False))),
            key="pred_auto_rerun",
            on_change=_persist_pred_toggle,
        )
    )
    current_signature = {
        "market": market,
        "ticker": str(ticker or "").strip().upper() if market == "US" else str(ticker or "").strip(),
        "period": period,
        "forecast_days": forecast_days,
    }

    def _run_prediction(clean_ticker: str, market_code: str, train_period: str, days: int) -> bool:
        df = fetch_stock(clean_ticker, market_code, train_period)
        if df.empty:
            st.error("Failed to fetch data.")
            return False
        results = predict_ensemble(df, days)
        if not isinstance(results, dict):
            st.error("Prediction failed: invalid model output")
            return False
        ensemble = results.get("ensemble", {})
        if not isinstance(ensemble, dict):
            st.error("Prediction failed: invalid ensemble output")
            return False
        if "error" in ensemble:
            st.error(f"Prediction failed: {ensemble['error']}")
            return False
        st.session_state["ai_prediction_result"] = {
            "ticker": clean_ticker,
            "forecast_days": days,
            "market": market_code,
            "period": train_period,
            "df": df,
            "results": results,
        }
        return True

    if st.sidebar.button("Run Prediction", type="primary", use_container_width=True, key="run_predict"):
        clean_ticker = str(ticker or "").strip().upper() if market == "US" else str(ticker or "").strip()
        _run_prediction(clean_ticker, market, period, forecast_days)

    prediction_result = st.session_state.get("ai_prediction_result")
    if isinstance(prediction_result, dict):
        previous_signature = {
            "market": str(prediction_result.get("market") or ""),
            "ticker": str(prediction_result.get("ticker") or ""),
            "period": str(prediction_result.get("period") or ""),
            "forecast_days": int(prediction_result.get("forecast_days", forecast_days)),
        }
        if previous_signature != current_signature:
            if auto_predict and current_signature["ticker"]:
                with st.spinner("입력 변경 감지: 예측 자동 재실행 중..."):
                    reran = _run_prediction(
                        str(current_signature["ticker"]),
                        str(current_signature["market"]),
                        str(current_signature["period"]),
                        int(current_signature["forecast_days"]),
                    )
                if not reran:
                    show_legal_disclaimer()
                    return
                prediction_result = st.session_state.get("ai_prediction_result")
                if not isinstance(prediction_result, dict):
                    show_legal_disclaimer()
                    return
            else:
                st.info("입력 조건이 변경되었습니다. 최신 예측을 보려면 'Run Prediction'을 다시 실행하세요.")
                show_legal_disclaimer()
                return

        current_result = cast(dict[str, Any], prediction_result)
        df = current_result.get("df", pd.DataFrame())
        results = current_result.get("results", {})
        ticker = str(current_result.get("ticker", ticker))
        forecast_days = int(current_result.get("forecast_days", forecast_days))
        ensemble = results.get("ensemble", {})
        if isinstance(df, pd.DataFrame) and not df.empty and isinstance(ensemble, dict) and "error" not in ensemble:
            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price", f"{ensemble['last_price']:,.0f}")
            c2.metric("Predicted Price", f"{ensemble['predicted_price']:,.0f}", f"{ensemble['predicted_return']:+.2f}%")
            c3.metric("Models Used", len(ensemble.get("models_used", [])))

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Historical", line=dict(color="#00D4AA", width=2)))
            for model_name, pred in results.items():
                if model_name == "ensemble" or not isinstance(pred, dict) or "error" in pred or "forecast_index" not in pred:
                    continue
                fig.add_trace(go.Scatter(x=pred["forecast_index"], y=pred["forecast"], name=model_name, line=dict(width=1, dash="dash")))
            if "forecast" in ensemble:
                forecast_index = pd.date_range(df.index[-1], periods=forecast_days + 1, freq="B")[1:]
                fig.add_trace(go.Scatter(x=forecast_index, y=ensemble["forecast"], name="Ensemble", line=dict(color="#FFFFFF", width=3)))
            fig.update_layout(height=600, title=f"{ticker} AI Price Forecast", xaxis_title="Date", yaxis_title="Price", template="plotly_dark", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
    show_legal_disclaimer()
