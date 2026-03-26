import os
import re
import time
import logging
import threading
import telebot
from telebot import types
from flask import Flask

# 1. SETUP & LOGGING
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# 2. CONFIGURATION
BANNED_WORDS = ["fuck", "shit", "scam", "nigger", "retard", "slut", "Nigga", "ass", "Motherfucker", "MF"] # Add more here
FAQ_DATA = {
    "website?": "🌐 <b>Our Website:</b> https://killshill.ai/",
    "x?": "🐦 <b>Follow us on X:</b> https://x.com/killshillAI",
    "instagram?": "📸 <b>Instagram:</b> https://www.instagram.com/killshillai/",
    "linkedin?": "💼 <b>LinkedIn:</b> https://www.linkedin.com/company/killshillai",
    "social?": "🔗 <b>Official Socials:</b>\n- X: https://x.com/killshillAI\n- IG: https://www.instagram.com/killshillai\n- dashboard: https://killshill.ai/"
}

# Tracking for Flood Control { user_id: [timestamps] }
msg_history = {}
sticker_history = {}
last_welcome = {} # Added: Tracks the last welcome message so we can keep the chat clean

# 3. HELPERS
def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except: return False

def safe_delete(chat_id, message_id):
    try: bot.delete_message(chat_id, message_id)
    except: pass

def delayed_delete(chat_id, message_id, delay):
    """Deletes a message after X seconds."""
    def _delete():
        time.sleep(delay)
        safe_delete(chat_id, message_id)
    threading.Thread(target=_delete, daemon=True).start()

# 4. PILLAR 1: JOIN & VERIFY
@bot.message_handler(content_types=["new_chat_members"])
def on_user_join(message):
    chat_id = message.chat.id
    safe_delete(chat_id, message.message_id) # Remove "X joined" notification

    for user in message.new_chat_members:
        if user.is_bot: continue
        
        # Mute user immediately
        bot.restrict_chat_member(chat_id, user.id, can_send_messages=False)

        # Welcome + Verify Button
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Verify I'm Human", callback_data=f"verify_{user.id}"))
        
        welcome_text = (
            f"👋 Welcome <b>{user.first_name}</b> to the community!\n\n"
            "🛡️ <b>KillShill Security:</b> Please click below to verify and start chatting."
        )
        msg = bot.send_message(chat_id, welcome_text, reply_markup=markup)
        
        # Self-destruct welcome message after 5 minutes (300s)
        delayed_delete(chat_id, msg.message_id, 300)

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_"))
def handle_verification(call):
    user_id = int(call.data.split("_")[1])
    chat_id = call.message.chat.id
    
    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "❌ This button is for the new member!")
        return

    # Unmute user
    bot.restrict_chat_member(chat_id, user_id, can_send_messages=True, can_send_media_messages=True, 
                             can_send_other_messages=True, can_add_web_page_previews=True)
    
    # Delete the welcome/verify message
    safe_delete(chat_id, call.message.message_id)

    # --- Clean Chat Logic: Delete previous welcome message ---
    global last_welcome
    if chat_id in last_welcome:
        safe_delete(chat_id, last_welcome[chat_id])

    # --- NEW ULTIMATE WELCOME SYSTEM ---
    markup = types.InlineKeyboardMarkup()
    btn_dash = types.InlineKeyboardButton("🌐 KillShill Dashboard", url="https://killshill.ai/")
    btn_submit = types.InlineKeyboardButton("🎯 Submit Influencer", url="https://killshill.ai/") 
    btn_x = types.InlineKeyboardButton("✖️ X (Twitter)", url="https://x.com/killshillAI")
    btn_ig = types.InlineKeyboardButton("📸 Instagram", url="https://www.instagram.com/killshillai")
    btn_in = types.InlineKeyboardButton("💼 LinkedIn", url="https://www.linkedin.com/company/killshillai")
    
    markup.row(btn_dash, btn_submit)
    markup.row(btn_x, btn_ig, btn_in)

    first_name = call.from_user.first_name
    welcome_text = (
        f"Welcome to the community, <b>{first_name}</b>! 🛡️\n\n"
        f"Tired of influencers deleting bad calls and hiding losses? So are we.\n\n"
        f"<b>KillShill</b> is the ultimate AI Truth Engine. We bring radical transparency to Stocks, Crypto, Forex, and Options.\n\n"
        f"<b>What we do:</b>\n"
        f"✅ Live track Win Rates, ROI, & Risk/Reward\n"
        f"✅ AI detection of deleted/edited posts\n"
        f"✅ Unbiased, data-backed Leaderboards\n\n"
        f"<i>(Note: We are an independent auditing platform, not a trading group or crypto project.)</i>\n\n"
        f"⚠️ <b>WARNING:</b> Zero tolerance for shilling. If you drop promo links, the KillShill bot will permanently kick you.\n\n"
        f"👇 <b>Explore the Truth Engine:</b>"
    )

    try:
        msg = bot.send_message(
            chat_id, 
            welcome_text, 
            reply_markup=markup, 
            disable_web_page_preview=True
        )
        # Save ID to delete next time someone joins
        last_welcome[chat_id] = msg.message_id
    except Exception as e:
        log.error(f"Failed to send welcome: {e}")

# 5. PILLAR 2 & 3: FLOOD, BANNED WORDS, FAQ, STICKERS
@bot.message_handler(func=lambda m: True, content_types=['text', 'sticker'])
def monitor_chat(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    now = time.time()

    if is_admin(chat_id, user_id): return

    # --- BANNED WORDS CHECK ---
    if message.text:
        if any(word in message.text.lower() for word in BANNED_WORDS):
            safe_delete(chat_id, message.message_id)
            return

        # --- FAQ KEYWORDS ---
        for key, response in FAQ_DATA.items():
            if key in message.text.lower():
                bot.reply_to(message, response)
                return

    # --- STICKER FLOOD (4 per 30s) ---
    if message.content_type == 'sticker':
        user_stickers = sticker_history.get(user_id, [])
        user_stickers = [t for t in user_stickers if now - t < 30]
        user_stickers.append(now)
        sticker_history[user_id] = user_stickers
        
        if len(user_stickers) > 4:
            safe_delete(chat_id, message.message_id)
            return

    # --- MESSAGE FLOOD (5 per 10s) ---
    if message.text:
        user_msgs = msg_history.get(user_id, [])
        user_msgs = [t for t in user_msgs if now - t < 10]
        user_msgs.append(now)
        msg_history[user_id] = user_msgs
        
        if len(user_msgs) > 5:
            safe_delete(chat_id, message.message_id)
            # Mute for 5 minutes
            bot.restrict_chat_member(chat_id, user_id, can_send_messages=False, until_date=int(now + 300))
            bot.send_message(chat_id, f"🔇 {message.from_user.first_name} muted for 5m due to flooding.")
            return

# 6. KEEP ALIVE (FOR RENDER/REPLIT)
app = Flask(__name__)
@app.route('/')
def home(): return "KillShill Ultimate is Online!", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    log.info("🚀 KillShill Ultimate Live...")
    bot.infinity_polling(none_stop=True)
