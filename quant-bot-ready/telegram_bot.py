import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CONFIG_FILE = "C:/Users/Admin/combined-llm-bot/config/trading_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        return json.load(open(CONFIG_FILE))
    return {}

config = load_config()
TELEGRAM_TOKEN = config.get('telegram_bot_token', os.getenv('TELEGRAM_TOKEN', ''))
ALLOWED_USERS = os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")
STATE_FILE = "C:/Users/Admin/combined-llm-bot/memory/telegram_state.json"


def test_telegram_connection(token: str) -> bool:
    """Test Telegram bot connection."""
    from telegram import Bot
    try:
        bot = Bot(token=token)
        bot.get_me()
        return True
    except:
        return False


async def send_alert(message: str, token: str, chat_id: str):
    """Send alert to Telegram."""
    from telegram import Bot
    try:
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 Quant Bot Ready\n\n"
        "Commands:\n"
        "/signal XAUUSD - Get current signal\n"
        "/status - Check open positions\n"
        "/balance - Account balance\n"
        "/stop - Stop all trading\n\n"
        "Reply to alerts: execute / skip"
    )


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from data.fetcher import get_latest_signal
    
    symbol = " ".join(context.args) or "XAUUSD"
    
    try:
        result = get_latest_signal(symbol)
        
        if "error" in result:
            await update.message.reply_text(f"Error: {result['error']}")
            return
        
        signal = result["signal"]
        price = result["price"]
        
        emoji = "🟢" if signal["action"] == "BUY" else "🔴" if signal["action"] == "SELL" else "⚪"
        
        msg = f"{emoji} {signal['action']} {symbol} @ ${price:.2f}\n\n"
        msg += f"RSI: {signal.get('rsi', 'N/A'):.1f}\n"
        msg += f"ATR: {signal.get('atr', 'N/A'):.4f}\n"
        msg += f"Confidence: {signal['confidence']*100:.0f}%\n\n"
        msg += f"__{signal['reason']}__"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from memory.store import get_store
    
    store = get_store()
    trades = store.get_trades(limit=5)
    
    if not trades:
        await update.message.reply_text("No open positions")
        return
    
    msg = "💼 Open Positions:\n\n"
    for trade in trades:
        msg += f"{trade.get('side', 'N/A')} @ ${trade.get('entry_price', 0):.2f}\n"
        msg += f"P&L: ${trade.get('pnl', 0):.2f}\n\n"
    
    await update.message.reply_text(msg)


async def signal_pro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Professional signal with GARCH regime filter."""
    from data.fetcher import get_latest_professional_signal
    
    symbol = " ".join(context.args) or "XAUUSD"
    
    try:
        result = get_latest_professional_signal(symbol)
        
        if "error" in result:
            await update.message.reply_text(f"Error: {result['error']}")
            return
        
        signal = result["signal"]
        price = result["price"]
        
        action = signal.get("action", "HOLD")
        emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
        
        conf = int(signal.get('confidence', 0) * 100)
        
        # Calculate Entry/SL/TP
        atr = price * 0.008  # ~0.8%
        
        if action == "HOLD":
            msg = f"⚪ HOLD {symbol}\n\nNo clear signal\nConfidence: {conf}%"
        else:
            if action == "BUY":
                entry = price
                sl = price - (atr * 2)
                tp = price + (atr * 3)
            else:
                entry = price
                sl = price + (atr * 2)
                tp = price - (atr * 3)
            
            msg = f"{emoji} {action} {symbol}\n\n"
            msg += f"Entry: {entry:.2f}\n"
            msg += f"SL: {sl:.2f}\n"
            msg += f"TP: {tp:.2f}\n\n"
            msg += f"Price: {price:.2f}\n"
            msg += f"ATR: {atr:.2f}\n"
            msg += f"Confidence: {conf}%\n\n"
        
        msg += "📊 Factors:\n"
        
        scores = signal.get("scores", {})
        for factor, score in scores.items():
            sign = "+" if score > 0 else ""
            msg += f"  {factor}: {sign}{score}\n"
        
        if result.get("half_life"):
            msg += f"\n⏱️ Half-life: {result['half_life']:.1f}h\n"
        
        if result.get("tradeable"):
            msg += f"✅ Tradeable"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def vol_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GARCH volatility status."""
    from data.fetcher import fetch_data
    from strategy.volatility import garch_forecast
    
    symbol = " ".join(context.args) or "XAUUSD"
    
    try:
        df = fetch_data(symbol, interval='1h', period='30d')
        returns = df['close'].pct_change().dropna()
        
        vol_data = garch_forecast(returns)
        
        if "error" in vol_data:
            await update.message.reply_text(f"Error: {vol_data['error']}")
            return
        
        msg = f"📈 Volatility: {symbol}\n\n"
        msg += f"Forecast: {vol_data['vol_forecast']:.1%}\n"
        msg += f"Realized: {vol_data['realized_vol']:.1%}\n"
        msg += f"VRP: {vol_data['vrp']:.2%}\n"
        msg += f"Regime: {vol_data['regime']}\n"
        msg += f"Alpha: {vol_data['alpha']:.4f}\n"
        msg += f"Beta: {vol_data['beta']:.4f}\n"
        msg += f"Half-life: {vol_data['half_life_vol']:.1f} periods"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from memory.store import get_store
    
    store = get_store()
    trades = store.get_trades(limit=100)
    
    if not trades:
        await update.message.reply_text("Account Balance: $10,000 (default)")
        return
    
    trades_df = trades
    total_pnl = sum(t.get("pnl", 0) for t in trades_df)
    balance = 10000 + total_pnl
    
    await update.message.reply_text(f"💰 Balance: ${balance:.2f}\nP&L: ${total_pnl:.2f}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_state("trading_enabled", False)
    await update.message.reply_text("🛑 Trading stopped. Use /start to resume.")


async def start_trading_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_state("trading_enabled", True)
    await update.message.reply_text("▶️ Trading enabled.")


async def handle_alert_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if text in ["execute", "yes", "y"]:
        await update.message.reply_text("✅ Executing trade...")
    elif text in ["skip", "no", "n"]:
        await update.message.reply_text("⏭️ Trade skipped.")
    else:
        await update.message.reply_text("Reply: execute / skip")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Available commands:\n"
        "/signal [symbol] - Get signal\n"
        "/status - Open positions\n"
        "/balance - Account balance\n"
        "/stop - Stop trading\n"
        "/start - Start trading\n"
        "/help - This help"
    )


def load_state():
    try:
        return json.load(open(STATE_FILE)) if os.path.exists(STATE_FILE) else {}
    except:
        return {}


def save_state(key, value):
    state = load_state()
    state[key] = value
    os.makedirs("memory", exist_ok=True)
    json.dump(state, open(STATE_FILE, "w"))


def run():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set")
        return
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("signal_pro", signal_pro_command))
    app.add_handler(CommandHandler("vol", vol_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("start_trading", start_trading_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_alert_response))
    
    logger.info("🤖 Telegram bot started")
    app.run_polling(poll_interval=5)


if __name__ == "__main__":
    run()