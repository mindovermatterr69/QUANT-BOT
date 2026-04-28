import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from data.fetcher import fetch_data, add_indicators
from strategy.signals import generate_signal


class BacktestEngine:
    def __init__(
        self,
        initial_balance: float = 10000,
        commission: float = 0.0,
        slippage: float = 0.001
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission = commission
        self.slippage = slippage
        self.positions = []
        self.trades = []
        self.equity_curve = []
    
    def reset(self):
        self.balance = self.initial_balance
        self.positions = []
        self.trades = []
        self.equity_curve = []
    
    def run(
        self,
        symbol: str,
        interval: str = '1h',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = '90d'
    ) -> Dict:
        """
        Run backtest for a symbol.
        
        Returns: {
            'summary': {...},
            'trades': [...],
            'equity_curve': [...],
            'metrics': {...}
        }
        """
        self.reset()
        
        df = fetch_data(symbol, interval=interval, period=period)
        df = add_indicators(df)
        
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]
        
        df = df.dropna()
        
        if df.empty:
            return {'error': 'No data available after processing'}
        
        for i in range(20, len(df)):
            self._process_bar(df.iloc[:i+1])
        
        def run_by_signals_filtered(
        self,
        df: pd.DataFrame,
        entry_signal: str,
        exit_signal: str,
        allow_regime: str = 'normal',
        enable_garch: bool = True
    ) -> Dict:
        """
        Run backtest with GARCH volatility filter.
        
        Args:
            df: Price data
            entry_signal: Signal to enter (BUY/SELL)
            exit_signal: Signal to exit
            allow_regime: 'normal', 'high', 'any'
            enable_garch: Use GARCH regime filter
        """
        from strategy.volatility import garch_forecast
        
        returns = df['close'].pct_change().dropna()
        
        for i in range(20, len(df)):
            current_bar = df.iloc[i]
            current_price = current_bar['close']
            timestamp = df.index[i]
            
            equity = self.balance
            if self.positions:
                position = self.positions[-1]
                pnl = (current_price - position['entry_price']) * position['size']
                if position['side'] == 'SHORT':
                    pnl = -pnl
                equity += pnl
            
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': equity,
                'balance': self.balance,
                'price': current_price
            })
            
            if enable_garch and i > 60:
                try:
                    vol_data = garch_forecast(returns.iloc[:i])
                    regime = vol_data.get('regime', 'normal')
                    
                    if allow_regime != 'any' and regime == 'high' and allow_regime == 'normal':
                        continue
                except:
                    pass
            
            if len(self.positions) >= 1:
                continue
            
            signal_bar = df.iloc[:i+1]
            signal = generate_signal(signal_bar, {})
            
            if signal['action'] == entry_signal and not self.positions:
                self._enter_position('LONG' if entry_signal == 'BUY' else 'SHORT', current_price, timestamp)
            elif signal['action'] == exit_signal and self.positions:
                self._exit_position(current_price, timestamp, signal['reason'])
        
        return self._generate_results()
    
    def run_by_signals(
        self,
        df: pd.DataFrame,
        entry_signal: str,
        exit_signal: str
    ) -> Dict:
        """Run backtest with simple signal list."""
        for i in range(20, len(df)):
            current_bar = df.iloc[i]
            current_price = current_bar['close']
            timestamp = df.index[i]
            
            if len(self.positions) >= 1:
                signal_bar = df.iloc[:i+1]
                signal = generate_signal(signal_bar, {})
                
                if signal['action'] == exit_signal and self.positions:
                    self._exit_position(current_price, timestamp, signal['reason'])
            
            equity = self.balance
            if self.positions:
                position = self.positions[-1]
                pnl = (current_price - position['entry_price']) * position['size']
                if position['side'] == 'SHORT':
                    pnl = -pnl
                equity += pnl
            
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': equity,
                'balance': self.balance,
                'price': current_price
            })
        
        return self._generate_results()
    
    def _process_bar(self, df: pd.DataFrame):
        """Process a single bar."""
        current_bar = df.iloc[-1]
        current_price = current_bar['close']
        timestamp = df.index[-1]
        
        equity = self.balance
        if self.positions:
            position = self.positions[-1]
            pnl = (current_price - position['entry_price']) * position['size']
            if position['side'] == 'SHORT':
                pnl = -pnl
            equity += pnl
        
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': equity,
            'balance': self.balance,
            'price': current_price
        })
        
        if len(self.positions) >= 2:
            return
        
        signal = generate_signal(df, {})
        
        if signal['action'] == 'BUY' and not self.positions:
            self._enter_position('LONG', current_price, timestamp)
        elif signal['action'] == 'SELL' and not self.positions:
            self._enter_position('SHORT', current_price, timestamp)
        elif signal['action'] == 'SELL' and self.positions:
            self._exit_position(current_price, timestamp, signal['reason'])
    
    def _enter_position(self, side: str, price: float, timestamp: datetime):
        adjusted_price = price * (1 + self.slippage if side == 'BUY' else 1 - self.slippage)
        
        size = self.balance * 0.95 / adjusted_price
        
        self.positions.append({
            'side': side,
            'entry_price': adjusted_price,
            'size': size,
            'entry_time': timestamp
        })
    
    def _exit_position(self, price: float, timestamp: datetime, reason: str):
        if not self.positions:
            return
        
        position = self.positions.pop()
        adjusted_price = price * (1 - self.slippage if position['side'] == 'LONG' else 1 + self.slippage)
        
        pnl = (adjusted_price - position['entry_price']) * position['size']
        if position['side'] == 'SHORT':
            pnl = -pnl
        
        self.balance += pnl
        
        self.trades.append({
            'side': position['side'],
            'entry_price': position['entry_price'],
            'exit_price': adjusted_price,
            'size': position['size'],
            'pnl': pnl,
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'reason': reason,
            'return_pct': (pnl / position['entry_price']) / position['size'] * 100
        })
    
    def _generate_results(self) -> Dict:
        """Generate backtest results."""
        if not self.trades:
            return {
                'summary': {
                    'total_trades': 0,
                    'final_balance': self.balance,
                    'return_pct': 0,
                    'max_drawdown': 0
                },
                'trades': [],
                'equity_curve': self.equity_curve,
                'metrics': {}
            }
        
        returns = [t['pnl'] for t in self.trades]
        winning_trades = [r for r in returns if r > 0]
        losing_trades = [r for r in returns if r <= 0]
        
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak']
        max_drawdown = equity_df['drawdown'].min() * 100
        
        total_return = (self.balance - self.initial_balance) / self.initial_balance * 100
        
        return {
            'summary': {
                'initial_balance': self.initial_balance,
                'final_balance': self.balance,
                'total_return': total_return,
                'total_trades': len(self.trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': len(winning_trades) / len(self.trades) * 100 if self.trades else 0,
                'max_drawdown': max_drawdown,
                'profit_factor': abs(sum(winning_trades) / sum(losing_trades)) if losing_trades else float('inf')
            },
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'metrics': {
                'avg_win': np.mean(winning_trades) if winning_trades else 0,
                'avg_loss': np.mean(losing_trades) if losing_trades else 0,
                'largest_win': max(winning_trades) if winning_trades else 0,
                'largest_loss': min(losing_trades) if losing_trades else 0
            }
        }


def run_backtest(symbol: str, **kwargs) -> Dict:
    """Convenience function to run a backtest."""
    engine = BacktestEngine()
    return engine.run(symbol, **kwargs)