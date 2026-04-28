import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from strategy.signals import calculate_rsi, calculate_ema, calculate_atr, calculate_macd, calculate_volume_sma


SUPPORTED_ASSETS = {
    'XAUUSD': 'GC=F',       # Gold Futures
    'XAUUSD_SPOT': 'XAUUSD=X',  # Spot Gold
    'GLD': 'GLD',          # GLD ETF
    'EURUSD': 'EURUSD=X',
    'BTCUSD': 'BTC-USD',
    'AAPL': 'AAPL',
    'TSLA': 'TSLA',
    'SPY': 'SPY',
    'XAGUSD': 'XAGUSD=X'   # Silver
}


def fetch_data(
    symbol: str,
    interval: str = '1h',
    period: str = '30d',
    source: str = 'yfinance'
) -> pd.DataFrame:
    """
    Fetch historical data for a symbol.
    
    Args:
        symbol: Asset symbol (e.g., 'XAUUSD', 'EURUSD')
        interval: Timeframe ('1m', '5m', '15m', '1h', '1d')
        period: Lookback period ('1d', '7d', '30d', '90d', '1y')
        source: Data source ('yfinance', 'ccxt')
    
    Returns:
        DataFrame with OHLCV columns
    """
    yf_symbol = SUPPORTED_ASSETS.get(symbol, symbol)
    
    ticker = yf.Ticker(yf_symbol)
    df = ticker.history(interval=interval, period=period)
    
    if df.empty:
        raise ValueError(f"No data returned for {symbol}")
    
    df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    })
    
    df.index = df.index.tz_localize(None)
    
    return df


def fetch_live_price(symbol: str) -> float:
    """Fetch current price for a symbol."""
    yf_symbol = SUPPORTED_ASSETS.get(symbol, symbol)
    ticker = yf.Ticker(yf_symbol)
    return ticker.fast_info.get('last_price', 0)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators to the dataframe."""
    df = df.copy()
    
    df['rsi'] = calculate_rsi(df['close'], period=14)
    df['ema_50'] = calculate_ema(df['close'], period=50)
    df['ema_200'] = calculate_ema(df['close'], period=200)
    df['atr'] = calculate_atr(df['high'], df['low'], df['close'], period=14)
    df['volume_sma'] = calculate_volume_sma(df['volume'], period=20)
    
    macd, signal, hist = calculate_macd(df['close'])
    df['macd'] = macd
    df['macd_signal'] = signal
    df['macd_hist'] = hist
    
    return df


def get_latest_signal(symbol: str, interval: str = '1h') -> Dict:
    """
    Get the latest signal for a symbol.
    
    Returns: {
        'symbol': str,
        'signal': Dict from generate_signal,
        'timestamp': datetime,
        'price': float
    }
    """
    from strategy.signals import generate_signal
    
    df = fetch_data(symbol, interval=interval, period='30d')
    df = add_indicators(df)
    df = df.dropna()
    
    if df.empty:
        return {'error': 'No data available'}
    
    signal = generate_signal(df, {})
    price = df['close'].iloc[-1]
    
    return {
        'symbol': symbol,
        'signal': signal,
        'timestamp': datetime.now(),
        'price': price,
        'data': df.tail(5).to_dict()
    }


def get_latest_professional_signal(symbol: str, interval: str = '1h', compare_with: Optional[str] = None) -> Dict:
    """
    Get professional-grade signal using institutional alpha factors.
    
    Args:
        symbol: Primary asset (e.g., 'XAUUSD')
        interval: Timeframe
        compare_with: Secondary asset for cointegration (e.g., 'XAGUSD')
    """
    from strategy.professional import generate_professional_signal
    from strategy.professional import z_score_momentum, kalman_filter, order_flow_imbalance
    
    df = fetch_data(symbol, interval=interval, period='90d')
    compare_df = None
    
    if compare_with:
        compare_df = fetch_data(compare_with, interval=interval, period='90d')
    
    df = df.dropna()
    if df.empty:
        return {'error': 'No data available'}
    
    signal = generate_professional_signal(df, gold_silver_spread=compare_df['close'] if compare_df is not None else None)
    price = df['close'].iloc[-1]
    
    kf, _ = kalman_filter(df['close'].values)
    z = z_score_momentum(df['close'], 20).iloc[-1]
    ofi = order_flow_imbalance(df).iloc[-1]
    
    return {
        'symbol': symbol,
        'signal': signal,
        'timestamp': datetime.now(),
        'price': price,
        'z_momentum': z,
        'kalman_trend': kf[-1] - kf[-5] if len(kf) >= 5 else 0,
        'order_flow': ofi,
        'half_life': signal.get('half_life_hours', 0),
        'tradeable': signal.get('tradeable', True)
    }


def get_cointegration_status(symbol1: str = 'XAUUSD', symbol2: str = 'XAGUSD') -> Dict:
    """
    Test cointegration between two assets for stat arb.
    """
    from strategy.professional import cointegration_test
    
    df1 = fetch_data(symbol1, interval='1d', period='1y')
    df2 = fetch_data(symbol2, interval='1d', period='1y')
    
    result = cointegration_test(df1['close'], df2['close'])
    
    return result


def validate_data(df: pd.DataFrame) -> Dict[str, any]:
    """
    Validate data quality.
    
    Returns: {
        'valid': bool,
        'issues': List[str],
        'gaps': int
    }
    """
    issues = []
    gaps = 0
    
    if df.empty:
        return {'valid': False, 'issues': ['No data'], 'gaps': 0}
    
    if df.isnull().any().any():
        null_cols = df.isnull().sum()
        null_cols = null_cols[null_cols > 0]
        issues.append(f"Null values in: {list(null_cols.index)}")
    
    price_changes = df['close'].pct_change()
    outliers = (price_changes.abs() > 0.5).sum()
    if outliers > 0:
        issues.append(f"Found {outliers} potential outliers (>50% change)")
    
    gap_period = df.index.to_series().diff()
    large_gaps = (gap_period > pd.Timedelta(days=1)).sum()
    gaps = large_gaps
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'gaps': gaps
    }