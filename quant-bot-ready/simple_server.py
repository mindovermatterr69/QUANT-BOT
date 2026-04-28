#!/usr/bin/env python3
# No external dependencies - uses only Python standard library
import os
import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import asyncio

TOKEN = "8680074762:AAFB6QAOx6xMJytKtLWc93xUUDpExxHQ_vg"
CHAT_ID = "8745736212"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Quant Bot Running - /signal")
        
        elif self.path == '/signal':
            try:
                import urllib.request
                import datetime
                
                # Fetch XAUUSD from yfinance
                with urllib.request.urlopen('https://query1.finance.yahoo.com/v8/finance/chart/XAUUSD?interval=1h&range=7d') as response:
                    data = json.loads(response.read())
                    result = data['chart']['result'][0]
                    quote = result['indicators']['quote'][0]
                    close = quote['close']
                    close = [c for c in close if c is not None]
                    price = close[-1]
                
                # Simple signal based on price
                prev_price = close[-2] if len(close) > 1 else price
                change = (price - prev_price) / prev_price * 100
                
                action = "BUY" if change < -0.5 else "SELL" if change > 0.5 else "HOLD"
                conf = min(abs(change) * 50, 100)
                
                atr = price * 0.008
                sl = price - (atr * 2) if action == "BUY" else price + (atr * 2)
                tp = price + (atr * 3) if action == "BUY" else price - (atr * 3)
                
                result = {
                    'symbol': 'XAUUSD',
                    'action': action,
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'confidence': int(conf),
                }
                
                if action != "HOLD":
                    result['sl'] = round(sl, 2)
                    result['tp'] = round(tp, 2)
                    
                    # Send telegram (simplified)
                    import urllib.parse
                    msg = f"XAUUSD\\n{action}\\nEntry: {price:.2f}\\nConf: {conf}%\\nSL: {sl:.2f}\\nTP: {tp:.2f}"
                    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={urllib.parse.quote(msg)}"
                    try:
                        urllib.request.urlopen(url, timeout=5)
                        result['telegram'] = 'sent'
                    except:
                        pass
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
                
            except Exception as e:
                self.send_response(500)
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        
        elif self.path == '/ping':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

port = int(os.environ.get('PORT', 5000))
server = HTTPServer(('0.0.0.0', port), Handler)
print(f"Server running on port {port}")
server.serve_forever()