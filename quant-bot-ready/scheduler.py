#!/usr/bin/env python3
import asyncio
import json
import sys
import os

base_dir = os.path.dirname(os.path.abspath(__file__))

async def run_scheduler():
    from telegram import Bot
    from data.fetcher import fetch_data
    from strategy.professional import generate_professional_signal
    
    config_path = os.path.join(base_dir, 'config', 'schedule.json')
    config = json.load(open(config_path)) if os.path.exists(config_path) else {}
    
    token = "8680074762:AAFB6QAOx6xMJytKtLWc93xUUDpExxHQ_vg"
    bot = Bot(token=token)
    chat_id = 8745736212
    
    print("Auto-scheduler started - 15 min interval")
    print("Use Ctrl+C to stop")
    
    while True:
        if os.path.exists(config_path):
            config = json.load(open(config_path))
        
        interval = config.get('interval_minutes', 15) * 60
        
        try:
            if not config.get('enabled', True):
                await asyncio.sleep(60)
                continue
            
            df = fetch_data('XAUUSD', interval='1h', period='7d')
            df = df.dropna()
            
            signal = generate_professional_signal(df)
            price = df['close'].iloc[-1]
            action = signal['action']
            conf = int(signal['confidence'] * 100)
            scores = signal.get('scores', {})
            
            min_conf = config.get('min_confidence', 0.3) * 100
            
            if action == "HOLD" and conf < min_conf:
                print(f"HOLD @ {conf}% - skipping (low conf)")
            else:
                atr = price * 0.008
                
                from datetime import datetime
                now = datetime.now().strftime("%d %H:%M")
                
                if action == "HOLD":
                    msg = f"XAUUSD | {now}\n=======================\nHOLD\nConf: {conf}%\nPrice: {price:.2f}\nWaiting..."
                else:
                    if action == "BUY":
                        sl = price - (atr * 2)
                        tp = price + (atr * 3)
                    else:
                        sl = price + (atr * 2)
                        tp = price - (atr * 3)
                    
                    msg = f"XAUUSD | {now}\n=======================\n{action}\nENTRY: {price:.2f}\nSL: {sl:.2f}\nTP: {tp:.2f}\nConf: {conf}%\nR:R 1:1.5"
                
                await bot.send_message(chat_id=chat_id, text=msg)
                print(f"Sent: {action} @ {price:.2f}")
                
                config['last_signal'] = {'action': action, 'time': now, 'price': price}
                json.dump(config, open(config_path, 'w'))
            
        except Exception as e:
            print(f"Error: {e}")
        
        await asyncio.sleep(interval)

if __name__ == "__main__":
    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        print("\nStopped")