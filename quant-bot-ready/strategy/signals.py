import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    return prices.ewm(span=period, adjust=False).mean()


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()
    
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    return volume.rolling(window=period).mean()


def generate_signal(df: pd.DataFrame, config: Dict) -> Dict:
    """
    Generate trading signal based on RSI + EMA + Volume strategy.
    
    Returns: {
        'action': 'BUY' | 'SELL' | 'HOLD',
        'confidence': 0.0-1.0,
        'reason': str
    }
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    rsi = latest.get('rsi')
    ema_50 = latest.get('ema_50')
    ema_200 = latest.get('ema_200')
    volume = latest.get('volume')
    volume_sma = latest.get('volume_sma')
    close = latest.get('close')
    atr = latest.get('atr')
    
    buy_conditions = []
    sell_conditions = []
    reasons = []
    
    if rsi and rsi < 30:
        buy_conditions.append(True)
        reasons.append(f"RSI oversold ({rsi:.1f})")
    elif rsi and rsi > 70:
        sell_conditions.append(True)
        reasons.append(f"RSI overbought ({rsi:.1f})")
    
    if ema_50 and ema_200:
        if close > ema_50 > ema_200:
            buy_conditions.append(True)
            reasons.append("Uptrend (price > EMA50 > EMA200)")
        elif close < ema_50 < ema_200:
            sell_conditions.append(True)
            reasons.append("Downtrend (price < EMA50 < EMA200)")
    
    if volume and volume_sma:
        if volume > volume_sma * 1.5:
            if buy_conditions:
                reasons.append("Volume spike confirmed")
            elif sell_conditions:
                reasons.append("Volume spike confirmed")
    
    action = "HOLD"
    confidence = 0.0
    
    if buy_conditions and len(buy_conditions) >= 2:
        action = "BUY"
        confidence = min(0.7 + (len(buy_conditions) * 0.1), 0.95)
    elif sell_conditions and len(sell_conditions) >= 2:
        action = "SELL"
        confidence = min(0.7 + (len(sell_conditions) * 0.1), 0.95)
    
    return {
        'action': action,
        'confidence': confidence,
        'reason': '; '.join(reasons) if reasons else 'No signal',
        'rsi': rsi,
        'atr': atr,
        'price': close
    }


def calculate_position_size(account_balance: float, atr: float, risk_pct: float = 0.01) -> float:
    """
    Calculate position size based on ATR risk.
    
    Formula: position_size = (account_balance * risk_pct) / (ATR * 2)
    """
    if atr is None or atr <= 0:
        return 0
    
    risk_amount = account_balance * risk_pct
    position_size = risk_amount / (atr * 2)
    
    return position_size


def calculate_trailing_stop(entry_price: float, atr: float, multiplier: float = 2.0) -> float:
    """
    Calculate trailing stop price.
    """
    return entry_price - (atr * multiplier)