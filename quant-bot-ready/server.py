#!/usr/bin/env python3
import os
import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

TOKEN = "8680074762:AAFB6QAOx6xMJytKtLWc93xUUDpExxHQ_vg"
CHAT_ID = "8745736212"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Quant Bot Running - /signal")
        
        elif self.path == '/signal':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                from data.fetcher import fetch_data
                from strategy.professional import generate_professional_signal
                
                df = fetch_data('XAUUSD', interval='1h', period='7d')
                df = df.dropna()
                signal = generate_professional_signal(df)
                price = float(df['close'].iloc[-1])
                
                action = signal['action']
                conf = int(signal['confidence'] * 100)
                atr = price * 0.008
                
                result = {
                    'symbol': 'XAUUSD',
                    'action': action,
                    'price': price,
                    'confidence': conf,
                }
                
                if action != 'HOLD':
                    if action == 'BUY':
                        result['sl'] = round(price - (atr * 2), 2)
                        result['tp'] = round(price + (atr * 3), 2)
                    else:
                        result['sl'] = round(price + (atr * 2), 2)
                        result['tp'] = round(price - (atr * 3), 2)
                    
                    # Send telegram
                    try:
                        import asyncio
                        from telegram import Bot
                        
                        bot = Bot(token=TOKEN)
                        msg = f"XAUUSD\n{action}\nEntry: {price:.2f}\nConf: {conf}%\nSL: {result['sl']:.2f}\nTP: {result['tp']:.2f}"
                        
                        async def send_msg():
                            await bot.send_message(chat_id=CHAT_ID, text=msg)
                        
                        asyncio.run(send_msg())
                        result['telegram'] = 'sent'
                    except Exception as e:
                        result['telegram_error'] = str(e)
                
                self.wfile.write(json.dumps(result).encode())
                
            except Exception as e:
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
        print(f"{self.address[0]} - {format % args}")

port = int(os.environ.get('PORT', 5000))
print(f"Starting on port {port}")
server = HTTPServer(('0.0.0.0', port), Handler)
server.serve_forever()