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

# Verify Token exists
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    log.error("CRITICAL ERROR: BOT_TOKEN not found in environment variables!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# 2. CONFIGURATION
BANNED_WORDS = ["fuck", "shit", "scam", "nigger", "retard", "slut", "nigga", "ass", "motherfucker", "mf"]
FAQ_DATA = {
    "website?": "🌐 <b>Our Website:</b> https://killshill.ai/",
    "x?": "🐦 <b>Follow us on X:</b> https://x.com/killshillAI",
    "instagram?": "📸 <b>Instagram:</b> https://www.instagram.com/killshillai/",
    "linkedin?": "💼 <b>LinkedIn:</b> https://www.linkedin.com/company/killshillai",
    "social?": "🔗 <b>Official Socials:</b>\n- X: https://x.com/killshillAI\n- IG: https://www.instagram.com/killshillai\n- Dashboard: https://killshill.ai/"
}

msg_history = {}
sticker_history = {}
last_welcome = {} 

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
    def _delete():
        time.sleep(delay)
        safe_delete(chat_id, message_id)
    threading.Thread(target=_delete, daemon=True).start()

# 4. PILLAR 1: JOIN/LEAVE & VERIFY
@bot.message_handler(content_types=["left_chat_member"])
def on_user_leave(message):
    safe_delete(message.chat.id, message.message_id)

@bot.message_handler(content_types=["new_chat_members"])
def on_user_join(message):
    chat_id = message.chat.id
    safe_delete(chat_id, message.message_id)
    for user in message.new_chat_members:
        if user.is_bot: continue
        try:
            bot.restrict_chat_member(chat_id, user.id, can_send_messages=False)
        except Exception as e:
            log.warning(f"Could not mute user: {e}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Verify I'm Human", callback_data=f"verify_{user.id}"))
        welcome_text = (
            f"👋 Welcome <b>{user.first_name}</b> to the community!\n\n"
            "🛡️ <b>KillShill Security:</b> Please click below to verify and start chatting."
        )
        msg = bot.send_message(chat_id, welcome_text, reply_markup=markup)
        delayed_delete(chat_id, msg.message_id, 300)

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_"))
def handle_verification(call):
    user_id = int(call.data.split("_")[1])
    chat_id = call.message.chat.id
    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "❌ This button is for the new member!")
        return
    try:
        bot.restrict_chat_member(chat_id, user_id, can_send_messages=True, can_send_media_messages=True, 
                                 can_send_other_messages=True, can_add_web_page_previews=True)
    except Exception as e:
        log.warning(f"Could not unmute user: {e}")
    safe_delete(chat_id, call.message.message_id)
    global last_welcome
    if chat_id in last_welcome:
        safe_delete(chat_id, last_welcome[chat_id])
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
        msg = bot.send_message(chat_id, welcome_text, reply_markup=markup, disable_web_page_preview=True)
        last_welcome[chat_id] = msg.message_id
    except Exception as e:
        log.error(f"Failed to send welcome: {e}")

# 5. PILLAR 2 & 3: MONITOR
@bot.message_handler(func=lambda m: True, content_types=['text', 'sticker'])
def monitor_chat(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    now = time.time()
    if is_admin(chat_id, user_id): return
    if message.text:
        msg_lower = message.text.lower()
        if any(word in msg_lower for word in BANNED_WORDS):
            safe_delete(chat_id, message.message_id)
            return
        for key, response in FAQ_DATA.items():
            if key in msg_lower:
                bot.reply_to(message, response)
                return
    if message.content_type == 'sticker':
        user_stickers = sticker_history.get(user_id, [])
        user_stickers = [t for t in user_stickers if now - t < 30]
        user_stickers.append(now)
        sticker_history[user_id] = user_stickers
        if len(user_stickers) > 4:
            safe_delete(chat_id, message.message_id)
            return
    if message.text:
        user_msgs = msg_history.get(user_id, [])
        user_msgs = [t for t in user_msgs if now - t < 10]
        user_msgs.append(now)
        msg_history[user_id] = user_msgs
        if len(user_msgs) > 5:
            safe_delete(chat_id, message.message_id)
            try:
                bot.restrict_chat_member(chat_id, user_id, can_send_messages=False, until_date=int(now + 300))
                bot.send_message(chat_id, f"🔇 <b>{message.from_user.first_name}</b> muted for 5m due to flooding.")
            except: pass
            return

# 6. KEEP ALIVE (FOR RENDER)
app = Flask(__name__)
@app.route('/')
def home(): 
    return "🛡️ KillShill Ultimate is Online!", 200

def run_bot():
    log.info("🚀 Starting Telegram Bot polling...")
    bot.infinity_polling(none_stop=True)

if __name__ == "__main__":
    # Start the Bot in a background thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Start Flask in the MAIN thread (This is what Render monitors)
    port = int(os.environ.get("PORT", 10000))
    log.info(f"🌐 Starting Web Server on port {port}...")
    app.run(host="0.0.0.0", port=port)
