import os
import sys
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Quant Bot Running"

@app.route('/signal')
def get_signal():
    from data.fetcher import fetch_data
    from strategy.professional import generate_professional_signal
    
    df = fetch_data('XAUUSD', interval='1h', period='7d')
    df = df.dropna()
    signal = generate_professional_signal(df)
    price = df['close'].iloc[-1]
    
    return {
        'action': signal['action'],
        'price': price,
        'confidence': signal['confidence'],
        'scores': signal.get('scores', {})
    }

# For Render.com - keep alive
@app.route('/ping')
def ping():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)