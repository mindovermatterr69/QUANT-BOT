import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from datetime import datetime
from arch import arch_model


def garch_forecast(returns: pd.Series, horizon: int = 1) -> Dict:
    """
    GARCH(1,1) volatility forecast.
    
    σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
    
    Used for:
    - Volatility regime detection
    - VRP (Volatility Risk Premium) trading
    - Dynamic position sizing based on regime
    """
    returns = returns.dropna()
    
    if len(returns) < 60:
        return {'error': 'Need 60+ observations'}
    
    try:
        garch = arch_model(returns * 100, vol='Garch', p=1, q=1, mean='Constant')
        result = garch.fit(disp='off')
        
        forecast = result.forecast(horizon=horizon)
        vol_forecast = np.sqrt(forecast.variance.iloc[-1].values[0]) / 100
        
        realized = returns.rolling(20).std() * np.sqrt(252)
        realized_current = realized.iloc[-1]
        
        omega = result.params.get('omega', 0)
        alpha = result.params.get('alpha[1]', 0)
        beta = result.params.get('beta[1]', 0)
        half_life_vol = -np.log(2) / np.log(alpha + beta) if (alpha + beta) < 1 else float('inf')
        
        return {
            'vol_forecast': vol_forecast,
            'realized_vol': realized_current,
            'vrp': vol_forecast - realized_current,
            'vrp_pct': (vol_forecast - realized_current) / realized_current * 100,
            'regime': 'high' if vol_forecast > realized_current * 1.3 else 'low' if vol_forecast < realized_current * 0.7 else 'normal',
            'omega': omega,
            'alpha': alpha,
            'beta': beta,
            'persistence': alpha + beta,
            'half_life_vol': half_life_vol,
            'model': result.summary().tables[1].data
        }
    except Exception as e:
        return {'error': str(e)}


def filter_by_volatility_regime(
    signal: Dict,
    returns: pd.Series,
    threshold: float = 0.3
) -> Dict:
    """
    Filter signals by volatility regime.
    
    Only allow trades when vol is in "normal" regime.
    Avoid entering during vol spikes (regime uncertainty).
    """
    vol_data = garch_forecast(returns)
    
    if 'error' in vol_data:
        return signal
    
    regime = vol_data['regime']
    confidence = signal.get('confidence', 0)
    
    if regime == 'high':
        signal['action'] = 'HOLD'
        signal['reason'] += f' | BLOCKED: High volatility regime ({vol_data["vol_forecast"]:.1%} forecast)'
        signal['confidence'] = 0
        signal['vol_regime'] = 'blocked'
    elif regime == 'low':
        signal['confidence'] = min(confidence * 1.2, 1.0)
        signal['vol_regime'] = 'low_vol_premium'
    else:
        signal['vol_regime'] = 'normal'
    
    signal['volatility'] = vol_data
    
    return signal


def compute_vrp_signals(
    returns: pd.Series,
    iv_series: Optional[pd.Series] = None,
    horizon: int = 5
) -> Dict:
    """
    Volatility Risk Premium signals.
    
    VRP = Implied Vol - Realized Vol
    
    If IV > HV consistently → sell vol (collect premium)
    If IV < HV → buy vol
    
    Based on Natenberg's volatility trading framework.
    """
    realized = returns.rolling(20).std() * np.sqrt(252)
    realized_current = realized.iloc[-1]
    
    if iv_series is not None:
        implied_current = iv_series.iloc[-1]
    else:
        vol_60d = returns.rolling(60).std() * np.sqrt(252)
        implied_current = vol_60d.iloc[-1] * 1.1
    
    vrp = implied_current - realized_current
    vrp_pct = vrp / realized_current * 100
    
    signal = 'SELL_VOL' if vrp_pct > 10 else 'BUY_VOL' if vrp_pct < -10 else 'HOLD'
    
    return {
        'signal': signal,
        'implied_vol': implied_current,
        'realized_vol': realized_current,
        'vrp': vrp,
        'vrp_pct': vrp_pct,
        'edge': 'sell' if vrp_pct > 10 else 'buy' if vrp_pct < -10 else 'none',
        'reason': f'VRP {vrp_pct:.1f}%' if abs(vrp_pct) > 10 else 'VRP neutral'
    }


def dynamic_position_sizing(
    account_balance: float,
    atr: float,
    garch_vol: float,
    base_risk_pct: float = 0.01
) -> Dict:
    """
    Dynamic position sizing using GARCH vol.
    
    Adjust risk based on current volatility regime:
    - High vol regime → smaller position (reduce risk)
    - Low vol regime → larger position (increase edge)
    """
    if garch_vol <= 0:
        return {'size': 0, 'risk_pct': 0, 'reason': 'Invalid vol'}
    
    target_risk = base_risk_pct
    
    if garch_vol > 0.20:
        target_risk = base_risk_pct * 0.5
        reason = 'High vol regime - reduced risk'
    elif garch_vol < 0.10:
        target_risk = base_risk_pct * 1.5
        reason = 'Low vol regime - increased risk'
    else:
        reason = 'Normal vol regime - base risk'
    
    risk_amount = account_balance * target_risk
    position_size = risk_amount / (atr * 2) if atr > 0 else 0
    
    return {
        'position_size': position_size,
        'risk_pct': target_risk,
        'risk_amount': risk_amount,
        'garch_vol': garch_vol,
        'reason': reason
    }


def regime_based_signal(
    df: pd.DataFrame,
    base_signal: Dict,
    enable_garch: bool = True,
    enable_vrp: bool = False
) -> Dict:
    """
    Complete professional signal with GARCH regime filter.
    
    Flow:
    1. Generate base signal (z-score, momentum, etc.)
    2. Check GARCH volatility regime
    3. Block if high vol regime
    4. Optionally add VRP signal
    
    This is the main function to call for live trading.
    """
    returns = df['close'].pct_change().dropna()
    
    signal = base_signal.copy()
    signal['volatility_checked'] = True
    
    if enable_garch:
        vol_data = garch_forecast(returns)
        
        if 'error' not in vol_data:
            signal = filter_by_volatility_regime(signal, returns)
            signal['garch'] = {
                'forecast': vol_data.get('vol_forecast'),
                'realized': vol_data.get('realized_vol'),
                'regime': vol_data.get('regime'),
                'half_life': vol_data.get('half_life_vol'),
                'persistence': vol_data.get('persistence')
            }
        else:
            signal['garch'] = {'error': vol_data.get('error')}
    
    if enable_vrp:
        vrp_data = compute_vrp_signals(returns)
        signal['vrp'] = vrp_data
    
    return signal


def backtest_with_regime(
    df: pd.DataFrame,
    entry_signal: str = 'BUY',
    exit_signal: str = 'SELL',
    initial_balance: float = 10000
) -> Dict:
    """
    Backtest with volatility regime filter.
    
    Compares:
    - Strategy with GARCH filter
    - Strategy without GARCH filter
    """
    from backtest.engine import BacktestEngine
    
    returns = df['close'].pct_change().dropna()
    
    vol_data = garch_forecast(returns)
    
    engine_no_filter = BacktestEngine(initial_balance=initial_balance)
    result_no_filter = engine_no_filter.run_by_signals(df, entry_signal, exit_signal)
    
    if 'error' not in vol_data:
        regime = 'high' if vol_data.get('regime') == 'high' else 'normal'
        
        engine_with_filter = BacktestEngine(initial_balance=initial_balance)
        result_with_filter = engine_with_filter.run_by_signals_filtered(
            df, entry_signal, exit_signal, allow_regime=regime
        )
    else:
        result_with_filter = result_no_filter
    
    return {
        'without_garch': result_no_filter.get('summary', {}),
        'with_garch': result_with_filter.get('summary', {}),
        'vol_data': {k: v for k, v in vol_data.items() if k != 'model'},
        'improvement': (
            result_with_filter.get('summary', {}).get('total_return', 0) -
            result_no_filter.get('summary', {}).get('total_return', 0)
        )
    }