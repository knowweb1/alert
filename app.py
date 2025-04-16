import os
import logging
import asyncio
import qrcode
import psycopg2
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Initialize Flask
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize PostgreSQL connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# Create tables
with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS owners (
                qr_id TEXT PRIMARY KEY,
                chat_id BIGINT NOT NULL
            )
        """)
        conn.commit()

# Telegram command handlers
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        if not context.args:
            await update.message.reply_text("Usage: /register <QR_CODE_ID>")
            return

        qr_id = context.args[0]
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO owners (qr_id, chat_id)
                    VALUES (%s, %s)
                    ON CONFLICT (qr_id) DO UPDATE
                    SET chat_id = EXCLUDED.chat_id
                """, (qr_id, chat_id))
                conn.commit()

        await update.message.reply_text(f"✅ Registered QR: {qr_id}")
        logger.info(f"Registered QR: {qr_id} for chat: {chat_id}")

    except Exception as e:
        logger.error(f"Registration error: {e}")
        await update.message.reply_text("⚠️ Registration failed. Please try again.")

# Flask routes
@app.route('/alert/<qr_id>')
def alert_owner(qr_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT chat_id FROM owners WHERE qr_id = %s", (qr_id,))
                result = cur.fetchone()
                
        if not result:
            return "QR not registered", 404

        chat_id = result[0]
        async def send_alert():
            await app.bot.send_message(
                chat_id=chat_id,
                text="🚨 Please move your car!"
            )
        asyncio.run(send_alert())
        return "Notification sent", 200

    except Exception as e:
        logger.error(f"Alert error: {e}")
        return "Server error", 500

@app.route('/generate_qr/<qr_id>')
def generate_qr(qr_id):
    try:
        # Use your Render/Supabase URL here
        url = f"https://your-app-name.onrender.com/alert/{qr_id}"
        img = qrcode.make(url)
        img.save(f"qr_{qr_id}.png")
        return f"QR generated: qr_{qr_id}.png"
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        return "QR generation failed", 500

@app.route('/')
def home():
    return "Car Alert System - Operational"

# Telegram webhook setup
def setup_telegram(app):
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("register", register))
    
    # Store bot reference in Flask app context
    app.bot = application.bot
    
    # Set webhook in production
    if os.environ.get('ENVIRONMENT') == 'production':
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 5000)),
            webhook_url=webhook_url
        )
    else:
        application.run_polling()

if __name__ == '__main__':
    setup_telegram(app)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))