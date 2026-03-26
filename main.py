import os
import re
import logging
import threading
import telebot
from telebot import types
from flask import Flask

# 1. LOGGING SETUP
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# 2. BOT INITIALIZATION
# Get token from Render Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    log.error("❌ BOT_TOKEN not found! Add it in Render -> Environment Variables.")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# 3. STATE TRACKING
# Stores { chat_id: last_welcome_message_id } to keep chat clean
last_welcome = {}

# 4. HELPERS
LINK_PATTERN = re.compile(r"(https?://|t\.me/|www\.)", re.IGNORECASE)

def is_admin(chat_id, user_id):
    """Checks if a user is an admin or owner."""
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def safe_delete(chat_id, message_id):
    """Deletes a message without crashing if it's already gone."""
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass

# 5. FEATURE: CLEAN SERVICE (Delete Join/Leave)
@bot.message_handler(content_types=["new_chat_members", "left_chat_member"])
def clean_service_messages(message):
    # Delete the "X joined" or "X left" notification immediately
    safe_delete(message.chat.id, message.message_id)
    
    # If it's a new member, trigger the Welcome message
    if message.content_type == "new_chat_members":
        for user in message.new_chat_members:
            if not user.is_bot:
                send_welcome(message.chat.id, user.first_name)

# 6. FEATURE: CLEAN WELCOME
def send_welcome(chat_id, name):
    # Delete the previous welcome message if it exists
    if chat_id in last_welcome:
        safe_delete(chat_id, last_welcome[chat_id])

    text = (
        f"👋 Welcome <b>{name}</b> to the community! 🛡️\n\n"
        "No shilling allowed or <b>KillShill bot</b> will kick you."
    )
    
    try:
        sent_msg = bot.send_message(chat_id, text)
        last_welcome[chat_id] = sent_msg.message_id
    except Exception as e:
        log.error(f"Error sending welcome: {e}")

# 7. FEATURE: ANTI-SHILL (Link Killer)
@bot.message_handler(func=lambda msg: msg.text and LINK_PATTERN.search(msg.text))
def link_killer(message):
    # Allow admins to post links
    if is_admin(message.chat.id, message.from_user.id):
        return

    # Delete links from normal members
    safe_delete(message.chat.id, message.message_id)
    log.info(f"🚫 Deleted link from {message.from_user.first_name}")

# 8. KEEP-ALIVE SERVER (Flask)
app = Flask(__name__)

@app.route('/')
def home():
    return "🛡️ KillShill Bot is active!", 200

def run_flask():
    # Render provides a 'PORT' environment variable automatically
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# 9. STARTUP
if __name__ == "__main__":
    # Start Flask in a background thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    log.info("🚀 KillShill Bot is starting...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)