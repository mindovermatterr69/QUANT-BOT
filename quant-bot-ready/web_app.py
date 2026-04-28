import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
import asyncio
from telegram import Bot

app = Flask(__name__)

def send_telegram_msg(msg):
    """Helper to send telegram message"""
    try:
        token = "8680074762:AAFB6QAOx6xMJytKtLWc93xUUDpExxHQ_vg"
        bot = Bot(token=token)
        # Run async in new loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.send_message(chat_id=8745736212, text=msg))
        loop.close()
        return True
    except:
        return False

@app.route('/')
def home():
    return "Quant Bot Running - /signal for signals"

@app.route('/signal')
def get_signal():
    try:
        from data.fetcher import fetch_data
        from strategy.professional import generate_professional_signal
        
        df = fetch_data('XAUUSD', interval='1h', period='7d')
        df = df.dropna()
        signal = generate_professional_signal(df)
        price = df['close'].iloc[-1]
        
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
        msg = f"XAUUSD\n{action}\nEntry: {price:.2f}\nConf: {conf}%"
        if action != 'HOLD':
            msg += f"\nSL: {result['sl']:.2f}\nTP: {result['tp']:.2f}"
        
        send_telegram_msg(msg)
        result['signal_sent'] = True
        
        return result
        
    except Exception as e:
        return {'error': str(e)}

@app.route('/ping')
def ping():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)