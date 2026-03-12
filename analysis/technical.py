"""
기술적 분석 지표 모듈 (Pro Edition)
- 기본: SMA, EMA, RSI, MACD, 볼린저밴드, 스토캐스틱
- 고급: Ichimoku, ATR, OBV, Williams %R, CCI, VWAP, ADX
- 특수: Heikin-Ashi 캔들 변환
"""
import pandas as pd
import numpy as np


# ============================
# 기본 지표
# ============================

def calc_sma(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    if periods is None:
        periods = [5, 20, 60, 120]
    result = df.copy()
    for p in periods:
        result[f"SMA_{p}"] = result["Close"].rolling(window=p).mean()
    return result


def calc_ema(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    if periods is None:
        periods = [5, 20, 60, 120]
    result = df.copy()
    for p in periods:
        result[f"EMA_{p}"] = result["Close"].ewm(span=p, adjust=False).mean()
    return result


def calc_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    result = df.copy()
    delta = result["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    for i in range(period, len(avg_gain)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period
    rs = avg_gain / avg_loss
    result["RSI"] = 100 - (100 / (1 + rs))
    return result


def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    result = df.copy()
    ema_fast = result["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = result["Close"].ewm(span=slow, adjust=False).mean()
    result["MACD"] = ema_fast - ema_slow
    result["MACD_Signal"] = result["MACD"].ewm(span=signal, adjust=False).mean()
    result["MACD_Hist"] = result["MACD"] - result["MACD_Signal"]
    return result


def calc_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    result = df.copy()
    sma = result["Close"].rolling(window=period).mean()
    std = result["Close"].rolling(window=period).std()
    result["BB_Upper"] = sma + (std * std_dev)
    result["BB_Middle"] = sma
    result["BB_Lower"] = sma - (std * std_dev)
    result["BB_Width"] = (result["BB_Upper"] - result["BB_Lower"]) / result["BB_Middle"]
    result["BB_PctB"] = (result["Close"] - result["BB_Lower"]) / (result["BB_Upper"] - result["BB_Lower"])
    return result


def calc_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    result = df.copy()
    low_min = result["Low"].rolling(window=k_period).min()
    high_max = result["High"].rolling(window=k_period).max()
    result["Stoch_K"] = 100 * (result["Close"] - low_min) / (high_max - low_min)
    result["Stoch_D"] = result["Stoch_K"].rolling(window=d_period).mean()
    return result


# ============================
# 고급 지표 (신규)
# ============================

def calc_ichimoku(df: pd.DataFrame, tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> pd.DataFrame:
    """일목균형표 (Ichimoku Cloud)"""
    result = df.copy()
    high = result["High"]
    low = result["Low"]

    # 전환선 (Tenkan-sen)
    result["Ichi_Tenkan"] = (high.rolling(window=tenkan).max() + low.rolling(window=tenkan).min()) / 2
    # 기준선 (Kijun-sen)
    result["Ichi_Kijun"] = (high.rolling(window=kijun).max() + low.rolling(window=kijun).min()) / 2
    # 선행스팬A (Senkou Span A) - 26일 후방 이동
    result["Ichi_SpanA"] = ((result["Ichi_Tenkan"] + result["Ichi_Kijun"]) / 2).shift(kijun)
    # 선행스팬B (Senkou Span B) - 26일 후방 이동
    result["Ichi_SpanB"] = ((high.rolling(window=senkou_b).max() + low.rolling(window=senkou_b).min()) / 2).shift(kijun)
    # 후행스팬 (Chikou Span) - 26일 전방 이동
    result["Ichi_Chikou"] = result["Close"].shift(-kijun)
    return result


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ATR (Average True Range) - 변동성 지표"""
    result = df.copy()
    high = result["High"]
    low = result["Low"]
    close = result["Close"]
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    result["TR"] = tr
    result["ATR"] = tr.rolling(window=period).mean()
    return result


def calc_obv(df: pd.DataFrame) -> pd.DataFrame:
    """OBV (On-Balance Volume) - 거래량 지표"""
    result = df.copy()
    obv = [0]
    for i in range(1, len(result)):
        if result["Close"].iloc[i] > result["Close"].iloc[i - 1]:
            obv.append(obv[-1] + result["Volume"].iloc[i])
        elif result["Close"].iloc[i] < result["Close"].iloc[i - 1]:
            obv.append(obv[-1] - result["Volume"].iloc[i])
        else:
            obv.append(obv[-1])
    result["OBV"] = obv
    result["OBV_SMA"] = result["OBV"].rolling(window=20).mean()
    return result


def calc_williams_r(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Williams %R"""
    result = df.copy()
    high_max = result["High"].rolling(window=period).max()
    low_min = result["Low"].rolling(window=period).min()
    result["Williams_R"] = -100 * (high_max - result["Close"]) / (high_max - low_min)
    return result


def calc_cci(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """CCI (Commodity Channel Index)"""
    result = df.copy()
    tp = (result["High"] + result["Low"] + result["Close"]) / 3
    sma_tp = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    result["CCI"] = (tp - sma_tp) / (0.015 * mad)
    return result


def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ADX (Average Directional Index) - 추세 강도"""
    result = df.copy()
    high = result["High"]
    low = result["Low"]
    close = result["Close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[(plus_dm > 0) & (plus_dm <= minus_dm)] = 0
    minus_dm[(minus_dm > 0) & (minus_dm <= plus_dm)] = 0

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

    result["ADX"] = dx.rolling(window=period).mean()
    result["DI_Plus"] = plus_di
    result["DI_Minus"] = minus_di
    return result


def calc_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """VWAP (Volume Weighted Average Price)"""
    result = df.copy()
    tp = (result["High"] + result["Low"] + result["Close"]) / 3
    result["VWAP"] = (tp * result["Volume"]).cumsum() / result["Volume"].cumsum()
    return result


def calc_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Heikin-Ashi 캔들 변환"""
    ha = pd.DataFrame(index=df.index)
    ha["HA_Close"] = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
    ha["HA_Open"] = 0.0
    ha["HA_Open"].iloc[0] = (df["Open"].iloc[0] + df["Close"].iloc[0]) / 2
    for i in range(1, len(ha)):
        ha["HA_Open"].iloc[i] = (ha["HA_Open"].iloc[i - 1] + ha["HA_Close"].iloc[i - 1]) / 2
    ha["HA_High"] = pd.concat([df["High"], ha["HA_Open"], ha["HA_Close"]], axis=1).max(axis=1)
    ha["HA_Low"] = pd.concat([df["Low"], ha["HA_Open"], ha["HA_Close"]], axis=1).min(axis=1)
    ha["Volume"] = df["Volume"]
    return ha


# ============================
# 통합 함수
# ============================

def calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """모든 기술적 지표를 한번에 계산"""
    result = df.copy()
    result = calc_sma(result, [5, 20, 60, 120])
    result = calc_ema(result, [12, 26])
    result = calc_rsi(result)
    result = calc_macd(result)
    result = calc_bollinger(result)
    result = calc_stochastic(result)
    result = calc_ichimoku(result)
    result = calc_atr(result)
    result = calc_obv(result)
    result = calc_williams_r(result)
    result = calc_cci(result)
    result = calc_adx(result)
    result = calc_vwap(result)
    return result


def get_signal_summary(df: pd.DataFrame) -> dict:
    """현재 기술적 지표 기반 시그널 요약 (강화 버전)"""
    if df.empty or len(df) < 2:
        return {"signal": "데이터 부족", "details": {}, "score": 0}

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    signals = {}
    score = 0  # -100 ~ +100

    # RSI
    if "RSI" in latest.index and not pd.isna(latest["RSI"]):
        rsi_val = latest["RSI"]
        if rsi_val < 30:
            signals["RSI"] = "과매도 (매수 고려)"
            score += 20
        elif rsi_val > 70:
            signals["RSI"] = "과매수 (매도 고려)"
            score -= 20
        else:
            signals["RSI"] = f"중립 ({rsi_val:.1f})"

    # MACD
    if "MACD" in latest.index and "MACD_Signal" in latest.index:
        if not pd.isna(latest["MACD"]) and not pd.isna(latest["MACD_Signal"]):
            if latest["MACD"] > latest["MACD_Signal"] and prev["MACD"] <= prev["MACD_Signal"]:
                signals["MACD"] = "골든크로스 (강한 매수)"
                score += 25
            elif latest["MACD"] < latest["MACD_Signal"] and prev["MACD"] >= prev["MACD_Signal"]:
                signals["MACD"] = "데드크로스 (강한 매도)"
                score -= 25
            elif latest["MACD"] > latest["MACD_Signal"]:
                signals["MACD"] = "상승 추세"
                score += 10
            else:
                signals["MACD"] = "하락 추세"
                score -= 10

    # 이동평균
    if "SMA_5" in latest.index and "SMA_20" in latest.index:
        if not pd.isna(latest["SMA_5"]) and not pd.isna(latest["SMA_20"]):
            if latest["SMA_5"] > latest["SMA_20"] and prev["SMA_5"] <= prev["SMA_20"]:
                signals["MA"] = "골든크로스 (매수)"
                score += 20
            elif latest["SMA_5"] < latest["SMA_20"] and prev["SMA_5"] >= prev["SMA_20"]:
                signals["MA"] = "데드크로스 (매도)"
                score -= 20
            elif latest["SMA_5"] > latest["SMA_20"]:
                signals["MA"] = "단기 상승"
                score += 5
            else:
                signals["MA"] = "단기 하락"
                score -= 5

    # 볼린저밴드
    if "BB_PctB" in latest.index and not pd.isna(latest["BB_PctB"]):
        pctb = latest["BB_PctB"]
        if pctb < 0:
            signals["볼린저밴드"] = "하단 이탈 (매수 고려)"
            score += 15
        elif pctb > 1:
            signals["볼린저밴드"] = "상단 이탈 (매도 고려)"
            score -= 15
        elif pctb < 0.2:
            signals["볼린저밴드"] = "하단 접근"
            score += 5
        elif pctb > 0.8:
            signals["볼린저밴드"] = "상단 접근"
            score -= 5
        else:
            signals["볼린저밴드"] = "중립"

    # Ichimoku
    if "Ichi_Tenkan" in latest.index and "Ichi_Kijun" in latest.index:
        if not pd.isna(latest["Ichi_Tenkan"]) and not pd.isna(latest["Ichi_Kijun"]):
            if latest["Close"] > latest["Ichi_SpanA"] and latest["Close"] > latest["Ichi_SpanB"]:
                signals["일목균형표"] = "구름 위 (매수)"
                score += 15
            elif latest["Close"] < latest["Ichi_SpanA"] and latest["Close"] < latest["Ichi_SpanB"]:
                signals["일목균형표"] = "구름 아래 (매도)"
                score -= 15
            else:
                signals["일목균형표"] = "구름 내 (중립)"

    # ADX
    if "ADX" in latest.index and not pd.isna(latest["ADX"]):
        adx_val = latest["ADX"]
        if adx_val > 25:
            signals["ADX"] = f"강한 추세 ({adx_val:.1f})"
        else:
            signals["ADX"] = f"약한 추세 ({adx_val:.1f})"

    # Williams %R
    if "Williams_R" in latest.index and not pd.isna(latest["Williams_R"]):
        wr = latest["Williams_R"]
        if wr > -20:
            signals["Williams %R"] = "과매수"
            score -= 10
        elif wr < -80:
            signals["Williams %R"] = "과매도"
            score += 10
        else:
            signals["Williams %R"] = "중립"

    # 종합 판단 (점수 기반)
    score = max(-100, min(100, score))
    if score >= 30:
        overall = "강한 매수"
    elif score >= 10:
        overall = "매수 우세"
    elif score <= -30:
        overall = "강한 매도"
    elif score <= -10:
        overall = "매도 우세"
    else:
        overall = "중립"

    return {"signal": overall, "details": signals, "score": score}
