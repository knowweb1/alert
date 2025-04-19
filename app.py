import logging
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import sqlite3
import qrcode
import os
import asyncio
from dotenv import load_dotenv
import threading
from threading import Lock

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Global variables
application = None
loop = None
lock = Lock()

# Initialize database
def init_db():
    with sqlite3.connect('car_owners.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS owners 
                      (qr_id TEXT PRIMARY KEY, chat_id INTEGER)''')
init_db()

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        if not context.args:
            await update.message.reply_text("Usage: /register <QR_CODE_ID>")
            return

        qr_id = context.args[0]
        
        with sqlite3.connect('car_owners.db') as conn:
            conn.execute("INSERT OR REPLACE INTO owners VALUES (?, ?)", (qr_id, chat_id))
        
        url = f"http://localhost:5000/alert/{qr_id}"
        img = qrcode.make(url)
        qr_path = f"qr_codes/{qr_id}.png"
        img.save(qr_path)
        
        with open(qr_path, 'rb') as qr_file:
            await update.message.reply_photo(qr_file, caption=f"✅ Registered QR: {qr_id}")
        
        os.remove(qr_path)
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Operation failed. Please try again.")

@app.route('/alert/<qr_id>')
def alert_owner(qr_id):
    try:
        with sqlite3.connect('car_owners.db') as conn:
            cur = conn.execute("SELECT chat_id FROM owners WHERE qr_id=?", (qr_id,))
            result = cur.fetchone()
            chat_id = result[0] if result else None

        if not chat_id:
            return "QR code not registered", 404

        # Use thread-safe async execution
        with lock:
            future = asyncio.run_coroutine_threadsafe(
                application.bot.send_message(
                    chat_id=chat_id,
                    text="🚨 Please move your car!"
                ),
                loop
            )
            future.result(timeout=10)  # Wait for completion
        
        return "Notification sent", 200

    except Exception as e:
        logging.error(f"Error: {e}")
        return "Notification failed", 500

@app.route('/')
def home():
    return "Car Alert System - Use /register in Telegram"

def run_bot():
    global application, loop
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("register", register))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.run_polling())

if __name__ == '__main__':
    os.makedirs("qr_codes", exist_ok=True)
    
    # Start bot in separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
