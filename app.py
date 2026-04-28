#!/usr/bin/env python3
import os, sys, json, urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# Hardcoded for simplicity
TOKEN = "8680074762:AAFB6QAOx6xMJytKtLWc93xUUDpExxHQ_vg"
CHAT = "8745736212"

class QHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/": self.send("Quant Bot Running - /signal")
        elif self.path == "/ping": self.send("OK")
        elif self.path == "/signal": self.signal()
        else: self.send404()
    
    def send(self, data):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(data.encode())
    
    def send404(self):
        self.send_response(404)
        self.end_headers()
    
    def signal(self):
        try:
            # Get XAUUSD price
            url = "https://query1.finance.yahoo.com/v8/finance/chart/XAUUSD?interval=1h&range=7d"
            resp = urllib.request.urlopen(url, timeout=10).read()
            data = json.loads(resp)
            close = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            p = close[-1]
            pp = close[-2] if len(close) > 1 else p
            chg = (p-pp)/pp*100
            
            # Simple signal
            act = "BUY" if chg < -0.5 else "SELL" if chg > 0.5 else "HOLD"
            conf = min(abs(chg)*50, 100)
            a = p * 0.008
            
            r = {"action": act, "price": round(p,2), "change": round(chg,2), "conf": conf}
            
            if act != "HOLD":
                r["sl"] = round(p - 2*a, 2) if act == "BUY" else round(p + 2*a, 2)
                r["tp"] = round(p + 3*a, 2) if act == "BUY" else round(p - 3*a, 2)
            
            # Send to Telegram
            msg = f"XAUUSD\n{act}\nEntry: {p:.2f}\nConf: {conf}%"
            if act != "HOLD":
                msg += f"\nSL: {r['sl']:.2f}\nTP: {r['tp']:.2f}"
            
            tg_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT}&text={urllib.parse.quote(msg)}"
            try:
                urllib.request.urlopen(tg_url, timeout=5)
                r["telegram"] = "sent"
            except Exception as e:
                r["telegram_error"] = str(e)
                
        except Exception as e:
            r = {"error": str(e)}
        
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(r).encode())

port = int(os.environ.get("PORT", 5000))
print(f"Starting on port {port}")
HTTPServer(("0.0.0.0", port), QHandler).serve_forever()