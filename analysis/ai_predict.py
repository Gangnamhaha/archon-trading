"""
AI 주가 예측 모듈
- Exponential Smoothing (Holt-Winters)
- ARIMA 기반 예측
- Linear Regression 기반 예측
- 앙상블 예측 (평균)
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")


def predict_holt_winters(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    """Holt-Winters 지수 평활법 예측"""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        close = df["Close"].dropna()
        if len(close) < 60:
            return {"error": "최소 60일 데이터 필요"}

        model = ExponentialSmoothing(
            close, trend="mul", seasonal=None,
            damped_trend=True
        ).fit(optimized=True)

        forecast = model.forecast(forecast_days)
        fitted = model.fittedvalues

        # 잔차 기반 신뢰 구간
        residuals = close - fitted
        std_resid = residuals.std()
        forecast_idx = pd.date_range(close.index[-1], periods=forecast_days + 1, freq="B")[1:]
        upper = forecast + 1.96 * std_resid
        lower = forecast - 1.96 * std_resid

        return {
            "model": "Holt-Winters",
            "forecast": forecast.values,
            "forecast_index": forecast_idx,
            "upper": upper.values,
            "lower": lower.values,
            "fitted": fitted.values,
            "last_price": float(close.iloc[-1]),
            "predicted_price": round(float(forecast.iloc[-1]), 0),
            "predicted_return": round(float((forecast.iloc[-1] / close.iloc[-1] - 1) * 100), 2),
        }
    except Exception as e:
        return {"error": str(e)}


def predict_arima(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    """ARIMA 기반 예측"""
    try:
        from statsmodels.tsa.arima.model import ARIMA
        close = df["Close"].dropna()
        if len(close) < 60:
            return {"error": "최소 60일 데이터 필요"}

        model = ARIMA(close, order=(5, 1, 0)).fit()
        forecast = model.forecast(steps=forecast_days)
        forecast_idx = pd.date_range(close.index[-1], periods=forecast_days + 1, freq="B")[1:]

        # 신뢰 구간
        pred = model.get_forecast(steps=forecast_days)
        conf = pred.conf_int(alpha=0.05)

        return {
            "model": "ARIMA(5,1,0)",
            "forecast": forecast.values,
            "forecast_index": forecast_idx,
            "upper": conf.iloc[:, 1].values,
            "lower": conf.iloc[:, 0].values,
            "last_price": float(close.iloc[-1]),
            "predicted_price": round(float(forecast.iloc[-1]), 0),
            "predicted_return": round(float((forecast.iloc[-1] / close.iloc[-1] - 1) * 100), 2),
        }
    except Exception as e:
        return {"error": str(e)}


def predict_ml_regression(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    """머신러닝 회귀 기반 예측 (특성 엔지니어링 + LinearRegression)"""
    try:
        close = df["Close"].dropna()
        if len(close) < 60:
            return {"error": "최소 60일 데이터 필요"}

        # 특성 생성
        data = pd.DataFrame(index=close.index)
        data["close"] = close.values
        data["sma_5"] = close.rolling(5).mean()
        data["sma_20"] = close.rolling(20).mean()
        data["sma_60"] = close.rolling(60).mean()
        data["return_1d"] = close.pct_change()
        data["return_5d"] = close.pct_change(5)
        data["return_20d"] = close.pct_change(20)
        data["volatility"] = close.pct_change().rolling(20).std()
        data["rsi"] = _calc_rsi_series(close, 14)
        data["day_of_week"] = pd.Series(close.index).dt.dayofweek.values

        # 타겟: n일 후 수익률
        data["target"] = close.shift(-forecast_days) / close - 1
        data = data.dropna()

        if len(data) < 30:
            return {"error": "데이터 부족"}

        features = ["sma_5", "sma_20", "sma_60", "return_1d", "return_5d",
                     "return_20d", "volatility", "rsi", "day_of_week"]
        X = data[features].values
        y = data["target"].values

        # 학습 (마지막 행 제외)
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X[:-1])
        y_train = y[:-1]

        model = LinearRegression()
        model.fit(X_train, y_train)

        # 예측
        X_latest = scaler.transform(X[-1:])
        predicted_return = model.predict(X_latest)[0]
        predicted_price = close.iloc[-1] * (1 + predicted_return)

        # 훈련 R2
        train_score = model.score(X_train, y_train)

        # 단순 일별 예측 경로
        forecast_prices = np.linspace(close.iloc[-1], predicted_price, forecast_days)
        forecast_idx = pd.date_range(close.index[-1], periods=forecast_days + 1, freq="B")[1:]

        # 신뢰구간 (변동성 기반)
        daily_vol = close.pct_change().std()
        std_range = daily_vol * np.sqrt(np.arange(1, forecast_days + 1)) * close.iloc[-1]
        upper = forecast_prices + 1.96 * std_range
        lower = forecast_prices - 1.96 * std_range

        return {
            "model": "ML Regression",
            "forecast": forecast_prices,
            "forecast_index": forecast_idx,
            "upper": upper,
            "lower": lower,
            "last_price": float(close.iloc[-1]),
            "predicted_price": round(float(predicted_price), 0),
            "predicted_return": round(float(predicted_return * 100), 2),
            "r2_score": round(float(train_score), 4),
            "feature_importance": dict(zip(features, np.round(model.coef_, 4).tolist())),
        }
    except Exception as e:
        return {"error": str(e)}


def predict_gradient_boosting(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        close = df["Close"].dropna()
        if len(close) < 60:
            return {"error": "최소 60일 데이터 필요"}

        data = pd.DataFrame(index=close.index)
        data["close"] = close.values
        data["sma_5"] = close.rolling(5).mean()
        data["sma_20"] = close.rolling(20).mean()
        data["sma_60"] = close.rolling(60).mean()
        data["return_1d"] = close.pct_change()
        data["return_5d"] = close.pct_change(5)
        data["return_20d"] = close.pct_change(20)
        data["volatility"] = close.pct_change().rolling(20).std()
        data["rsi"] = _calc_rsi_series(close, 14)
        data["macd"] = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        data["bb_width"] = (close.rolling(20).std() * 2) / close.rolling(20).mean()
        data["day_of_week"] = pd.Series(close.index).dt.dayofweek.values

        data["target"] = close.shift(-forecast_days) / close - 1
        data = data.dropna()

        if len(data) < 30:
            return {"error": "데이터 부족"}

        features = ["sma_5", "sma_20", "sma_60", "return_1d", "return_5d",
                     "return_20d", "volatility", "rsi", "macd", "bb_width", "day_of_week"]
        X = data[features].values
        y = data["target"].values

        scaler = StandardScaler()
        X_train = scaler.fit_transform(X[:-1])
        y_train = y[:-1]

        model = GradientBoostingRegressor(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, random_state=42
        )
        model.fit(X_train, y_train)

        X_latest = scaler.transform(X[-1:])
        predicted_return = model.predict(X_latest)[0]
        predicted_price = close.iloc[-1] * (1 + predicted_return)
        train_score = model.score(X_train, y_train)

        forecast_prices = np.linspace(close.iloc[-1], predicted_price, forecast_days)
        forecast_idx = pd.date_range(close.index[-1], periods=forecast_days + 1, freq="B")[1:]

        daily_vol = close.pct_change().std()
        std_range = daily_vol * np.sqrt(np.arange(1, forecast_days + 1)) * close.iloc[-1]
        upper = forecast_prices + 1.96 * std_range
        lower = forecast_prices - 1.96 * std_range

        importance = dict(zip(features, np.round(model.feature_importances_, 4).tolist()))

        return {
            "model": "Gradient Boosting",
            "forecast": forecast_prices,
            "forecast_index": forecast_idx,
            "upper": upper,
            "lower": lower,
            "last_price": float(close.iloc[-1]),
            "predicted_price": round(float(predicted_price), 0),
            "predicted_return": round(float(predicted_return * 100), 2),
            "r2_score": round(float(train_score), 4),
            "feature_importance": importance,
        }
    except Exception as e:
        return {"error": str(e)}


def predict_mlp_neural(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    try:
        from sklearn.neural_network import MLPRegressor
        close = df["Close"].dropna()
        if len(close) < 60:
            return {"error": "최소 60일 데이터 필요"}

        data = pd.DataFrame(index=close.index)
        data["close"] = close.values
        for lag in [1, 2, 3, 5, 10, 20]:
            data[f"lag_{lag}"] = close.pct_change(lag)
        data["sma_5"] = close.rolling(5).mean() / close - 1
        data["sma_20"] = close.rolling(20).mean() / close - 1
        data["sma_60"] = close.rolling(60).mean() / close - 1
        data["volatility"] = close.pct_change().rolling(20).std()
        data["rsi"] = _calc_rsi_series(close, 14) / 100
        data["macd_norm"] = (close.ewm(span=12).mean() - close.ewm(span=26).mean()) / close

        data["target"] = close.shift(-forecast_days) / close - 1
        data = data.dropna()

        if len(data) < 30:
            return {"error": "데이터 부족"}

        features = [c for c in data.columns if c not in ["close", "target"]]
        X = data[features].values
        y = data["target"].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_train = X_scaled[:-1]
        y_train = y[:-1]

        model = MLPRegressor(
            hidden_layer_sizes=(64, 32, 16), activation="relu",
            solver="adam", max_iter=500, early_stopping=True,
            validation_fraction=0.15, random_state=42,
            learning_rate="adaptive", alpha=0.001
        )
        model.fit(X_train, y_train)

        X_latest = X_scaled[-1:]
        predicted_return = model.predict(X_latest)[0]
        predicted_price = close.iloc[-1] * (1 + predicted_return)
        train_score = model.score(X_train, y_train)

        forecast_prices = np.linspace(close.iloc[-1], predicted_price, forecast_days)
        forecast_idx = pd.date_range(close.index[-1], periods=forecast_days + 1, freq="B")[1:]

        daily_vol = close.pct_change().std()
        std_range = daily_vol * np.sqrt(np.arange(1, forecast_days + 1)) * close.iloc[-1]
        upper = forecast_prices + 1.96 * std_range
        lower = forecast_prices - 1.96 * std_range

        return {
            "model": "MLP Neural Net",
            "forecast": forecast_prices,
            "forecast_index": forecast_idx,
            "upper": upper,
            "lower": lower,
            "last_price": float(close.iloc[-1]),
            "predicted_price": round(float(predicted_price), 0),
            "predicted_return": round(float(predicted_return * 100), 2),
            "r2_score": round(float(train_score), 4),
        }
    except Exception as e:
        return {"error": str(e)}


def predict_lstm(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    try:
        close = df["Close"].dropna().astype(float)
        if len(close) < 120:
            return {"error": "최소 120일 데이터 필요"}

        volume = df["Volume"].reindex(close.index).astype(float)

        feature_df = pd.DataFrame(index=close.index)
        feature_df["ret_1d"] = close.pct_change()
        feature_df["ret_5d"] = close.pct_change(5)
        feature_df["ret_20d"] = close.pct_change(20)
        feature_df["sma_5_ratio"] = close.rolling(5).mean() / close - 1
        feature_df["sma_20_ratio"] = close.rolling(20).mean() / close - 1
        feature_df["sma_60_ratio"] = close.rolling(60).mean() / close - 1
        feature_df["rsi"] = _calc_rsi_series(close, 14) / 100
        feature_df["vol_ratio"] = volume / volume.rolling(20).mean()

        feature_df = feature_df.replace([np.inf, -np.inf], np.nan).dropna()
        if len(feature_df) < 100:
            return {"error": "특성 데이터 부족"}

        target = (close.shift(-forecast_days) / close - 1).reindex(feature_df.index)
        train_df = feature_df.copy()
        train_df["target"] = target
        train_df = train_df.dropna()

        lookback_window = 60
        if len(train_df) <= lookback_window + 10:
            return {"error": "학습 데이터 부족"}
        if len(feature_df) < lookback_window:
            return {"error": "최근 시퀀스 데이터 부족"}

        features = [
            "ret_1d", "ret_5d", "ret_20d",
            "sma_5_ratio", "sma_20_ratio", "sma_60_ratio",
            "rsi", "vol_ratio",
        ]

        X_raw = train_df[features].values.astype(np.float64)
        y_raw = train_df["target"].values.astype(np.float64)

        x_mean = X_raw.mean(axis=0)
        x_std = X_raw.std(axis=0)
        x_std[x_std == 0] = 1.0
        X_scaled = (X_raw - x_mean) / x_std

        y_mean = float(y_raw.mean())
        y_std = float(y_raw.std())
        if y_std == 0:
            y_std = 1.0
        y_scaled = (y_raw - y_mean) / y_std

        sequences = []
        targets = []
        for i in range(lookback_window, len(train_df)):
            sequences.append(X_scaled[i - lookback_window:i])
            targets.append(y_scaled[i])

        if len(sequences) < 20:
            return {"error": "시퀀스 학습 샘플 부족"}

        X_seq = np.asarray(sequences, dtype=np.float64)
        y_seq = np.asarray(targets, dtype=np.float64)

        n_features = X_seq.shape[2]
        hidden_size = 32
        rng = np.random.default_rng(42)

        Wxh = rng.normal(0, 0.08, (n_features, hidden_size))
        Whh = rng.normal(0, 0.08, (hidden_size, hidden_size))
        bh = np.zeros(hidden_size, dtype=np.float64)
        Why = rng.normal(0, 0.08, (hidden_size, 1))
        by = np.zeros(1, dtype=np.float64)

        def forward(seq: np.ndarray):
            h_states = []
            h_prev = np.zeros(hidden_size, dtype=np.float64)
            for t in range(seq.shape[0]):
                x_t = seq[t]
                h_prev = np.tanh(x_t @ Wxh + h_prev @ Whh + bh)
                h_states.append(h_prev.copy())
            out = float(h_prev @ Why[:, 0] + by[0])
            return out, h_states

        epochs = 40
        learning_rate = 0.008
        max_samples = min(80, len(X_seq))

        for _ in range(epochs):
            order = rng.permutation(len(X_seq))[:max_samples]

            dWxh = np.zeros_like(Wxh)
            dWhh = np.zeros_like(Whh)
            dbh = np.zeros_like(bh)
            dWhy = np.zeros_like(Why)
            dby = np.zeros_like(by)

            for idx in order:
                seq = X_seq[idx]
                target_val = y_seq[idx]

                pred, h_states = forward(seq)
                grad_out = 2.0 * (pred - target_val)

                dWhy[:, 0] += h_states[-1] * grad_out
                dby[0] += grad_out

                dh_next = Why[:, 0] * grad_out
                for t in range(seq.shape[0] - 1, -1, -1):
                    h_t = h_states[t]
                    h_prev = h_states[t - 1] if t > 0 else np.zeros(hidden_size, dtype=np.float64)
                    x_t = seq[t]

                    dtanh = dh_next * (1.0 - h_t ** 2)
                    dWxh += np.outer(x_t, dtanh)
                    dWhh += np.outer(h_prev, dtanh)
                    dbh += dtanh
                    dh_next = dtanh @ Whh.T

            scale = 1.0 / max(1, len(order))
            for grad in (dWxh, dWhh, dbh, dWhy, dby):
                np.clip(grad, -1.0, 1.0, out=grad)
                grad *= scale

            Wxh -= learning_rate * dWxh
            Whh -= learning_rate * dWhh
            bh -= learning_rate * dbh
            Why -= learning_rate * dWhy
            by -= learning_rate * dby

        train_pred_scaled = np.array([forward(seq)[0] for seq in X_seq], dtype=np.float64)
        train_pred = train_pred_scaled * y_std + y_mean
        train_true = y_seq * y_std + y_mean

        ss_res = float(np.sum((train_true - train_pred) ** 2))
        ss_tot = float(np.sum((train_true - train_true.mean()) ** 2))
        r2_score = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        latest_seq_raw = feature_df[features].tail(lookback_window).values.astype(np.float64)
        latest_seq = (latest_seq_raw - x_mean) / x_std
        pred_scaled, _ = forward(latest_seq)
        predicted_return = pred_scaled * y_std + y_mean
        predicted_return = float(np.clip(predicted_return, -0.8, 1.5))

        last_price = float(close.iloc[-1])
        predicted_price = last_price * (1 + predicted_return)

        forecast_prices = np.linspace(last_price, predicted_price, forecast_days)
        forecast_idx = pd.date_range(close.index[-1], periods=forecast_days + 1, freq="B")[1:]

        daily_vol = float(close.pct_change().dropna().std())
        if not np.isfinite(daily_vol):
            daily_vol = 0.02
        std_range = daily_vol * np.sqrt(np.arange(1, forecast_days + 1)) * last_price
        upper = forecast_prices + 1.96 * std_range
        lower = forecast_prices - 1.96 * std_range

        return {
            "model": "Numpy LSTM-like",
            "forecast": forecast_prices,
            "forecast_index": forecast_idx,
            "upper": upper,
            "lower": lower,
            "last_price": last_price,
            "predicted_price": round(float(predicted_price), 0),
            "predicted_return": round(float(predicted_return * 100), 2),
            "r2_score": round(float(r2_score), 4),
        }
    except Exception as e:
        return {"error": str(e)}


def predict_ensemble(df: pd.DataFrame, forecast_days: int = 30) -> dict:
    results = {}
    models = {
        "Holt-Winters": predict_holt_winters,
        "ARIMA": predict_arima,
        "ML Regression": predict_ml_regression,
        "Gradient Boosting": predict_gradient_boosting,
        "MLP Neural Net": predict_mlp_neural,
        "Numpy LSTM-like": predict_lstm,
    }

    valid_predictions = []
    for name, func in models.items():
        pred = func(df, forecast_days)
        results[name] = pred
        if "error" not in pred:
            valid_predictions.append(pred)

    if not valid_predictions:
        return {"models": results, "ensemble": {"error": "모든 모델 실패"}}

    # 앙상블 평균
    avg_price = np.mean([p["predicted_price"] for p in valid_predictions])
    avg_return = np.mean([p["predicted_return"] for p in valid_predictions])
    last_price = valid_predictions[0]["last_price"]

    # 앙상블 예측 경로
    forecast_arrays = [p["forecast"] for p in valid_predictions if len(p["forecast"]) == forecast_days]
    if forecast_arrays:
        ensemble_forecast = np.mean(forecast_arrays, axis=0)
    else:
        ensemble_forecast = np.linspace(last_price, avg_price, forecast_days)

    results["ensemble"] = {
        "model": f"앙상블 ({len(valid_predictions)}개 모델)",
        "forecast": ensemble_forecast,
        "last_price": last_price,
        "predicted_price": round(float(avg_price), 0),
        "predicted_return": round(float(avg_return), 2),
        "models_used": [p.get("model", "unknown") for p in valid_predictions],
    }

    return results


def _calc_rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI 계산 (내부용)"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
