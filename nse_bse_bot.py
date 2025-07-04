import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import requests
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from datetime import datetime
import os
import json

# ... rest of your code


# ✅ Replace with your tokens
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY')

# ✅ Replace this with your own chat ID (get it using /start)
YOUR_CHAT_ID = None  # We'll set this dynamically on /start

# File to persist tracked companies
TRACKED_COMPANIES_FILE = 'tracked_companies.json'

def load_tracked_companies():
    if os.path.exists(TRACKED_COMPANIES_FILE):
        with open(TRACKED_COMPANIES_FILE, 'r') as f:
            return json.load(f)
    return ['TCS', 'RELIANCE', 'INFY']

def save_tracked_companies(companies):
    with open(TRACKED_COMPANIES_FILE, 'w') as f:
        json.dump(companies, f)

STOCK_LIST = load_tracked_companies()

# Store last sent prices for each stock symbol
last_sent_prices = {}

bot = Bot(token=TELEGRAM_TOKEN)

def get_stock_price(symbol):
    for exchange in ['NS', 'BSE']:
        full_symbol = f"{symbol}.{exchange}"
        url = f'https://finnhub.io/api/v1/quote?symbol={full_symbol}&token={FINNHUB_API_KEY}'
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            if data['c'] > 0:
                return (full_symbol, data)
    return (None, None)

def send_daily_stock_alert(context: CallbackContext):
    message = "📢 *Daily Stock Prices (NSE/BSE)*\n\n"
    for symbol in STOCK_LIST:
        stock_symbol, data = get_stock_price(symbol)
        if stock_symbol:
            message += (
                f"📈 *{stock_symbol}*\n"
                f"💰 Price: ₹{data['c']}\n"
                f"🔼 High: ₹{data['h']}\n"
                f"🔽 Low: ₹{data['l']}\n\n"
            )
        else:
            message += f"❌ Could not fetch {symbol}\n\n"

    context.bot.send_message(chat_id=YOUR_CHAT_ID, text=message, parse_mode='Markdown')

def send_realtime_stock_alert(context: CallbackContext):
    global last_sent_prices
    message = ""
    updated = False
    for symbol in STOCK_LIST:
        stock_symbol, data = get_stock_price(symbol)
        if stock_symbol and data['c'] > 0:
            last_price = last_sent_prices.get(stock_symbol)
            if last_price != data['c']:
                # Price changed, update and prepare message
                last_sent_prices[stock_symbol] = data['c']
                message += (
                    f"📈 *{stock_symbol}*\n"
                    f"💰 Price: ₹{data['c']}\n"
                    f"🔼 High: ₹{data['h']}\n"
                    f"🔽 Low: ₹{data['l']}\n\n"
                )
                updated = True
        else:
            message += f"❌ Could not fetch {symbol}\n\n"
    if updated and YOUR_CHAT_ID:
        context.bot.send_message(chat_id=YOUR_CHAT_ID, text=message, parse_mode='Markdown')

def start(update: Update, context: CallbackContext):
    global YOUR_CHAT_ID
    YOUR_CHAT_ID = update.effective_chat.id
    update.message.reply_text("✅ Bot activated!\nYou'll receive daily stock alerts at 9:00 AM IST.")

def add_company(update: Update, context: CallbackContext):
    global STOCK_LIST
    if not context.args:
        update.message.reply_text('Usage: /add <COMPANY_SYMBOL>')
        return
    symbol = context.args[0].upper()
    if symbol not in STOCK_LIST:
        STOCK_LIST.append(symbol)
        save_tracked_companies(STOCK_LIST)
        update.message.reply_text(f'✅ {symbol} added to tracking list.')
    else:
        update.message.reply_text(f'ℹ️ {symbol} is already being tracked.')

def remove_company(update: Update, context: CallbackContext):
    global STOCK_LIST
    if not context.args:
        update.message.reply_text('Usage: /remove <COMPANY_SYMBOL>')
        return
    symbol = context.args[0].upper()
    if symbol in STOCK_LIST:
        STOCK_LIST.remove(symbol)
        save_tracked_companies(STOCK_LIST)
        update.message.reply_text(f'❌ {symbol} removed from tracking list.')
    else:
        update.message.reply_text(f'ℹ️ {symbol} is not in the tracking list.')

def list_companies(update: Update, context: CallbackContext):
    if STOCK_LIST:
        update.message.reply_text('Currently tracking: ' + ', '.join(STOCK_LIST))
    else:
        update.message.reply_text('No companies are being tracked.')

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_company))
    dp.add_handler(CommandHandler("remove", remove_company))
    dp.add_handler(CommandHandler("list", list_companies))

    # 🕒 Scheduler for daily stock alerts at 9:00 AM IST
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))
    scheduler.add_job(lambda: send_daily_stock_alert(updater.bot), trigger='cron', hour=9, minute=0)
    # 🕒 Scheduler for real-time polling every minute
    scheduler.add_job(lambda: send_realtime_stock_alert(updater.bot), trigger='interval', minutes=1)
    scheduler.start()

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
