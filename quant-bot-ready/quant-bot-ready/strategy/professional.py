import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from statsmodels.tsa.stattools import adfuller


def z_score_momentum(price: pd.Series, lookback: int = 20) -> pd.Series:
    """
    Replace RSI - statistically grounded mean reversion.
    Z-score of returns vs rolling distribution.
    """
    rolling_mean = price.rolling(lookback).mean()
    rolling_std = price.rolling(lookback).std()
    return (price - rolling_mean) / rolling_std


def cross_sectional_z(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Cross-sectional momentum Z-score.
    How much better/worse did this asset perform vs universe (in std units).
    """
    mean = returns.mean(axis=1)
    std = returns.std(axis=1)
    return (returns.sub(mean, axis=0)).div(std, axis=0)


def kalman_filter(y: np.ndarray, delta: float = 1e-4, Ve: float = 1e-3) -> Tuple[np.ndarray, np.ndarray]:
    """
    Replace MACD - optimal adaptive Bayesian trend.
    
    Args:
        y: observations (price)
        delta: state transition covariance
        Ve: observation noise variance
    
    Returns:
        theta: filtered state estimates
        P: error covariance
    """
    n = len(y)
    theta = np.zeros(n)
    P = np.zeros(n)
    
    theta[0] = y[0]
    P[0] = 1
    
    for t in range(1, n):
        theta_pred = theta[t-1]
        P_pred = P[t-1] + delta
        
        e = y[t] - theta_pred
        P_pred_ve = P_pred + Ve
        
        K = P_pred / P_pred_ve
        
        theta[t] = theta_pred + K * e
        P[t] = (1 - K) * P_pred
    
    return theta, P


def garch_volatility(returns: pd.Series, p: int = 1, q: int = 1) -> pd.Series:
    """
    GARCH(1,1) volatility forecasting.
    σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
    
    Use arch package:
        from arch import arch_model
        garch = arch_model(returns, vol='Garch', p=1, q=1)
        result = garch.fit()
        vol_forecast = result.forecast(horizon=1)
    """
    returns_arr = returns.values
    returns_arr = returns_arr[~np.isnan(returns_arr)]
    
    omega = np.var(returns_arr) * 0.1
    alpha = 0.08
    beta = 0.9
    
    sigma2 = np.zeros(len(returns_arr))
    sigma2[0] = np.var(returns_arr)
    
    for t in range(1, len(returns_arr)):
        eps = returns_arr[t-1]
        sigma2[t] = omega + alpha * (eps**2) + beta * sigma2[t-1]
    
    return pd.Series(np.sqrt(sigma2), index=returns.index)


def order_flow_imbalance(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Replace volume spike - actual buy/sell pressure.
    Measures true buying vs selling at bid/ask.
    """
    returns = df['close'].diff()
    volume = df['volume']
    
    buy_volume = returns.apply(lambda x: max(x, 0)) * volume
    sell_volume = returns.apply(lambda x: max(-x, 0)) * volume
    
    ofi = buy_volume.rolling(period).sum() - sell_volume.rolling(period).sum()
    return ofi / volume.rolling(period).sum()


def half_life_mean_reversion(spread: pd.Series) -> float:
    """
    Measure signal half-life using ADF test.
    How long before the edge disappears?
    """
    try:
        returns = spread.diff().dropna()
        y = returns.values
        x = spread.shift(1).diff().dropna().values
        
        if len(x) < 20 or len(y) < 20:
            return 0
        
        min_len = min(len(x), len(y))
        x = x[:min_len]
        y = y[:min_len]
        
        if len(x) < 20:
            return 0
        
        from numpy.linalg import lstsq
        coef, _, _, _ = lstsq(x.reshape(-1, 1), y, rcond=None)
        
        beta = coef[0] if len(coef) > 0 else 0
        
        if beta >= 0 or np.isnan(beta):
            return 0
        
        half_life = -np.log(2) / np.log(1 + beta)
        return half_life if half_life > 0 else 0
    except:
        return 0


def cointegration_test(asset1: pd.Series, asset2: pd.Series) -> Dict:
    """
    Test if two assets are cointegrated.
    Statistical Arbitrage foundation.
    """
    from statsmodels.tsa.stattools import coint
    
    x = asset1.dropna().values
    y = asset2.dropna().values
    
    min_len = min(len(x), len(y))
    x, y = x[:min_len], y[:min_len]
    
    score, pvalue, _ = coint(x, y)
    
    spread = asset1 - asset2
    adf_result = adfuller(spread.dropna())
    
    return {
        'score': score,
        'pvalue': pvalue,
        'adf_pvalue': adf_result[1],
        'cointegrated': pvalue < 0.05,
        'stationary': adf_result[1] < 0.05
    }


def cointegrated_spread_zscore(asset1: pd.Series, asset2: pd.Series, lookback: int = 60) -> pd.Series:
    """
    Z-score of cointegrated spread.
    Trade when spread > 2σ → mean revert.
    """
    from statsmodels.regression.linear_model import OLS
    
    df = pd.DataFrame({'y': asset1, 'x': asset2}).dropna()
    
    model = OLS(df['y'], df['x']).fit()
    beta = model.params['x']
    
    spread = df['y'] - beta * df['x']
    
    rolling_mean = spread.rolling(lookback).mean()
    rolling_std = spread.rolling(lookback).std()
    
    return (spread - rolling_mean) / rolling_std


def compute_vrp(returns: pd.Series, iv: Optional[pd.Series] = None) -> pd.Series:
    """
    Volatility Risk Premium.
    VRP = Implied Vol - Realized Vol
    
    If IV > HV consistently → sell vol (collect premium)
    If IV < HV → buy vol
    
    Requires options data (optional).
    """
    realized_vol = returns.rolling(20).std() * np.sqrt(252)
    
    if iv is None:
        realized_vol_60 = returns.rolling(60).std() * np.sqrt(252)
        implied = realized_vol_60 * 1.1
    else:
        implied = iv
    
    return implied - realized_vol


def signal_half_life_test(price: pd.Series) -> float:
    """
    Test half-life of mean reversion signal.
    If half-life > 3 weeks → tradeable systematically.
    """
    spread = (price - price.rolling(20).mean()) / price.rolling(20).std()
    return half_life_mean_reversion(spread)


def generate_professional_signal(
    df: pd.DataFrame,
    benchmark: Optional[pd.Series] = None,
    gold_silver_spread: Optional[pd.Series] = None
) -> Dict:
    """
    Professional signal stack combining:
    - Z-score momentum (mean reversion)
    - Kalman trend
    - Order flow
    - Cointegration (if gold/silver spread provided)
    - GARCH volatility regime
    """
    
    close = df['close']
    volume = df['volume']
    
    scores = {}
    
    z_mom = z_score_momentum(close, 20)
    z = z_mom.iloc[-1]
    if z > 2:
        scores['mean_reversion'] = -1
    elif z < -2:
        scores['mean_reversion'] = 1
    
    kf, _ = kalman_filter(close.values)
    trend = kf[-1] - kf[-5] if len(kf) >= 5 else 0
    if trend > 0:
        scores['kalman_trend'] = 1
    elif trend < 0:
        scores['kalman_trend'] = -1
    
    ofi = order_flow_imbalance(df)
    ofi_val = ofi.iloc[-1]
    if ofi_val > 0.5:
        scores['order_flow'] = 1
    elif ofi_val < -0.5:
        scores['order_flow'] = -1
    
    try:
        from arch import arch_model
        returns = close.pct_change().dropna()
        if len(returns) > 30:
            garch = arch_model(returns[-60:], vol='Garch', p=1, q=1)
            result = garch.fit(disp='off')
            vol_forecast = result.forecast(horizon=1).variance.iloc[-1, 0]
            realized = returns[-20:].std() * np.sqrt(252)
            if vol_forecast > realized * 1.5:
                scores['volatility_regime'] = 1
            elif vol_forecast < realized * 0.7:
                scores['volatility_regime'] = -1
    except:
        pass
    
    if gold_silver_spread is not None:
        try:
            cs_z = cointegrated_spread_zscore(df['close'], gold_silver_spread)
            cs = cs_z.iloc[-1]
            if cs > 2:
                scores['cointegration'] = -1
            elif cs < -2:
                scores['cointegration'] = 1
        except:
            pass
    
    total_score = sum(scores.values())
    confidence = min(abs(total_score) / 5, 1.0)
    
    if total_score >= 2:
        action = "BUY"
    elif total_score <= -2:
        action = "SELL"
    else:
        action = "HOLD"
    
    half_life = signal_half_life_test(close)
    
    return {
        'action': action,
        'confidence': confidence,
        'scores': scores,
        'total_score': total_score,
        'half_life_hours': half_life,
        'z_momentum': z,
        'kalman_trend': trend,
        'order_flow': ofi_val,
        'tradeable': half_life > 24 if half_life > 0 else True
    }