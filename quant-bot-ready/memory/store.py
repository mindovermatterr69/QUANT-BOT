import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class MemoryStore:
    def __init__(self, base_path: str = "./memory"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        self.trades_file = self.base_path / "trades.json"
        self.signals_file = self.base_path / "signals.json"
        self.context_file = self.base_path / "context.json"
        self.analysis_file = self.base_path / "analysis.json"
        
        self._init_files()
    
    def _init_files(self):
        for f in [self.trades_file, self.signals_file, self.context_file, self.analysis_file]:
            if not f.exists():
                f.write_text("[]")
    
    def save_trade(self, trade: Dict):
        trades = self._load_json(self.trades_file)
        trade['id'] = len(trades) + 1
        trade['timestamp'] = datetime.now().isoformat()
        trades.append(trade)
        self._save_json(self.trades_file, trades)
    
    def get_trades(self, limit: int = 100) -> List[Dict]:
        trades = self._load_json(self.trades_file)
        return trades[-limit:]
    
    def save_signal(self, signal: Dict):
        signals = self._load_json(self.signals_file)
        signal['timestamp'] = datetime.now().isoformat()
        signals.append(signal)
        self._save_json(self.signals_file, signals[-1000:])
    
    def get_signals(self, limit: int = 100) -> List[Dict]:
        signals = self._load_json(self.signals_file)
        return signals[-limit:]
    
    def save_context(self, context: Dict):
        context['updated_at'] = datetime.now().isoformat()
        self._save_json(self.context_file, [context])
    
    def get_context(self) -> Dict:
        contexts = self._load_json(self.context_file)
        return contexts[0] if contexts else {}
    
    def save_analysis(self, analysis: Dict):
        analysis_data = self._load_json(self.analysis_file)
        analysis['timestamp'] = datetime.now().isoformat()
        analysis_data.append(analysis)
        self._save_json(self.analysis_file, analysis_data[-100:])
    
    def get_analysis(self, limit: int = 10) -> List[Dict]:
        analysis_data = self._load_json(self.analysis_file)
        return analysis_data[-limit:]
    
    def _load_json(self, path: Path) -> List[Any]:
        try:
            return json.loads(path.read_text())
        except:
            return []
    
    def _save_json(self, path: Path, data: List[Any]):
        path.write_text(json.dumps(data, indent=2))
    
    def clear_old_data(self, days: int = 90):
        """Clear data older than specified days."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        
        for file_path in [self.trades_file, self.signals_file, self.analysis_file]:
            data = self._load_json(file_path)
            filtered = [
                d for d in data 
                if datetime.fromisoformat(d['timestamp']).timestamp() > cutoff
            ]
            self._save_json(file_path, filtered)


_store = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store