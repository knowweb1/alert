# app.py
import logging
import sqlite3
import qrcode
import os
import asyncio
from flask import Flask
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import threading

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load environment variables first!
load_dotenv()

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_TOKEN")
DOMAIN = os.getenv("PYTHONANYWHERE_DOMAIN", "tahaafifi08.pythonanywhere.com")

# Database setup
conn = sqlite3.connect('car_owners.db', check_same_thread=False)
conn.execute('''CREATE TABLE IF NOT EXISTS owners
             (qr_id TEXT PRIMARY KEY, chat_id INTEGER)''')

# Telegram bot setup
bot = Bot(token=TOKEN)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        if not context.args:
            await update.message.reply_text("Usage: /register <QR_CODE_ID>")
            return

        qr_id = context.args[0]
        
        # Save to database
        with conn:
            conn.execute("INSERT OR REPLACE INTO owners VALUES (?, ?)", (qr_id, chat_id))
        
        # Generate QR code
        url = f"https://{DOMAIN}/alert/{qr_id}"
        img = qrcode.make(url)
        img.save(f"{qr_id}.png")
        
        await update.message.reply_photo(
            photo=open(f"{qr_id}.png", 'rb'),
            caption=f"✅ Registered QR: {qr_id}"
        )
        os.remove(f"{qr_id}.png")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Error! Usage: /register <QR_ID>")

@app.route('/')
def home():
    return "Car Alert System - Use /register in Telegram"

@app.route('/alert/<qr_id>')
def send_alert(qr_id):
    try:
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM owners WHERE qr_id=?", (qr_id,))
        chat_id = cur.fetchone()[0]
        
        # Create new event loop for Flask thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            bot.send_message(chat_id, "🚨 Please move your car!")
        )
        return "Alert sent!", 200
    except:
        return "QR code not registered", 404

def run_bot():
    # Create separate event loop for bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("register", register))
    
    loop.run_until_complete(application.run_polling())

if __name__ == '__main__':
    # Start bot in daemon thread
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Start Flask
    app.run(host='0.0.0.0', port=5000)
