import os
import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from telegram import Bot

app = Flask(__name__)

TELEGRAM_TOKEN = "8680074762:AAFB6QAOx6xMJytKtLWc93xUUDpExxHQ_vg"
CHAT_ID = "8745736212"

def send_signal_telegram(action, price, conf, sl=None, tp=None):
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        bot = Bot(token=TELEGRAM_TOKEN)
        
        msg = f"XAUUSD\n{action}\nEntry: {price:.2f}\nConf: {conf}%"
        if sl and tp:
            msg += f"\nSL: {sl:.2f}\nTP: {tp:.2f}"
        
        async def send():
            await bot.send_message(chat_id=CHAT_ID, text=msg)
        
        loop.run_until_complete(send())
        loop.close()
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

@app.route('/')
def home():
    return "Quant Bot Running. Use /signal"

@app.route('/signal')
def get_signal():
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
            
            send_signal_telegram(action, price, conf, result['sl'], result['tp'])
            result['telegram'] = 'sent'
        
        return result
        
    except Exception as e:
        return {'error': str(e)}

@app.route('/ping')
def ping():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)