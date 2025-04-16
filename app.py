import os
import logging
import qrcode
import asyncio
from flask import Flask
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import psycopg2  # Changed from SQLite to PostgreSQL

load_dotenv()

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# PostgreSQL setup
conn = psycopg2.connect(DATABASE_URL)
with conn.cursor() as cur:
    cur.execute('''
        CREATE TABLE IF NOT EXISTS owners (
            qr_id TEXT PRIMARY KEY,
            chat_id INTEGER
        )
    ''')
conn.commit()

# Telegram bot setup
bot = Bot(token=TOKEN)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        qr_id = context.args[0]
        
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO owners (qr_id, chat_id)
                VALUES (%s, %s)
                ON CONFLICT (qr_id) DO UPDATE
                SET chat_id = EXCLUDED.chat_id
            ''', (qr_id, chat_id))
            conn.commit()
        
        # Generate QR with Render URL
        url = f"{os.getenv('RENDER_EXTERNAL_URL')}/alert/{qr_id}"
        img = qrcode.make(url)
        img.save(f"{qr_id}.png")
        
        await update.message.reply_photo(
            photo=open(f"{qr_id}.png", 'rb'),
            caption=f"✅ Registered QR: {qr_id}"
        )
        os.remove(f"{qr_id}.png")
        
    except Exception as e:
        logging.error(f"Error: {e}")

@app.route('/alert/<qr_id>')
def alert(qr_id):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_id FROM owners WHERE qr_id = %s", (qr_id,))
            chat_id = cur.fetchone()[0]
            
            async def send_alert():
                await bot.send_message(chat_id, "🚨 Please move your car!")
            
            asyncio.run(send_alert())
            return "Alert sent!"
    except:
        return "QR not registered"

def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("register", register))
    application.run_polling()

if __name__ == '__main__':
    import threading
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
