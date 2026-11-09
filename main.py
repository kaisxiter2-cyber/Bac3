import os
import telebot
import requests
import time
import threading
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
import logging
import sys
# ╔══════════════════════════════════════════════════════════════════╗
# ║  CREATOR: TARIKUL ISLAM
# ║  TELEGRAN: https://t.me/paglu_dev
# ║  PERSONAL TELEGRAM: https://t.me/itzpaglu
# ╚══════════════════════════════════════════════════════════════════╝

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8967315640:AAHEKUmkNHZhOX2b8gbaa-oqvpFFAd4ncaA")

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found! Please set your bot token in environment variables.")
    sys.exit(1)

REQUIRED_CHANNELS = []                       # مثال: ["@mychannel"]  (فاضية = بدون تحقق اشتراك)
GROUP_JOIN_LINK = "https://t.me/your_group_link"
OWNER_ID = 0                                 # ايدي تيليغرام تبعك (رقم)، مثال: 6282811167
OWNER_USERNAME = "@your_username"

# رابط الـ API: لازم يحتوي {uid} و {region}
LIKE_API_URL = "https://your-free-fire-like-api-domain/like?uid={uid}&server_name={region}"

bot = telebot.TeleBot(BOT_TOKEN)
like_tracker = {}   # in-memory cache

# Flask app for webhook
app = Flask(__name__)

# === DATA RESET ===

def reset_limits():
    """Daily reset of usage stats (in-memory only)."""
    while True:
        try:
            now_utc = datetime.utcnow()
            next_reset = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            sleep_seconds = (next_reset - now_utc).total_seconds()

            time.sleep(sleep_seconds)
            like_tracker.clear()
            logger.info("✅ Daily stats reset at 00:00 UTC (in-memory).")
        except Exception as e:
            logger.error(f"Error in reset_limits thread: {e}")


# === UTILS ===

def is_user_in_channel(user_id):
    try:
        for channel in REQUIRED_CHANNELS:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except Exception as e:
        logger.error(f"Join check failed: {e}")
        return False


def call_api(region, uid):
    url = LIKE_API_URL.format(uid=uid, region=region)
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            return {"⚠️Invalid": " Maximum likes reached for today. Please try again tomorrow."}
        return response.json()
    except requests.exceptions.RequestException:
        return {"error": "API Failed. Please try again later."}
    except ValueError:
        return {"error": "Invalid JSON response."}


# Start background thread
threading.Thread(target=reset_limits, daemon=True).start()

# === FLASK ROUTES ===

@app.route('/')
def home():
    return jsonify({
        'status': 'Bot is running',
        'bot': 'Free Fire Likes Bot',
        'health': 'OK'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return '', 500


# === TELEGRAM COMMANDS

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if not is_user_in_channel(user_id):
        markup = InlineKeyboardMarkup()
        for channel in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"🔗 Join {channel}", url=f"https://t.me/{channel.strip('@')}"))
        bot.reply_to(message, "📢 Channel Membership Required\nTo use this bot, you must join all our channels first", reply_markup=markup, parse_mode="Markdown")
        return
    if user_id not in like_tracker:
        like_tracker[user_id] = {"used": 0, "last_used": datetime.now() - timedelta(days=1)}
    bot.reply_to(message, "✅ You're verified! Use /like to send likes.", parse_mode="Markdown")


@bot.message_handler(commands=['like'])
def handle_like(message):
    user_id = message.from_user.id
    args = message.text.split()

    # Only allow in groups, not in private messages (except owner)
    if message.chat.type == "private" and message.from_user.id != OWNER_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔗 Join Official Group", url=GROUP_JOIN_LINK))
        bot.reply_to(message, "❌ Sorry! command is not allowed here.\n\nJoin our official group:", reply_markup=markup)
        return

    if not is_user_in_channel(user_id):
        markup = InlineKeyboardMarkup()
        for channel in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"🔗 Join {channel}", url=f"https://t.me/{channel.strip('@')}"))
        bot.reply_to(message, "❌ You must join all our channels to use this command.", reply_markup=markup, parse_mode="Markdown")
        return

    if len(args) != 3:
        bot.reply_to(message, "❌ Format: `/like server_name uid`", parse_mode="Markdown")
        return

    region, uid = args[1], args[2]
    if not region.isalpha() or not uid.isdigit():
        bot.reply_to(message, "⚠️ Invalid input. Use: `/like server_name uid`", parse_mode="Markdown")
        return

    threading.Thread(target=process_like, args=(message, region, uid)).start()


def process_like(message, region, uid):
    user_id = message.from_user.id
    now_utc = datetime.utcnow()
    usage = like_tracker.get(user_id, {"used": 0, "last_used": now_utc - timedelta(days=1)})

    # New day -> reset the counter (stats only, no limit)
    if now_utc.date() > usage["last_used"].date():
        usage["used"] = 0

    processing_msg = bot.reply_to(message, "⏳ Please wait... Sending likes...")
    response = call_api(region, uid)

    if "error" in response:
        try:
            bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text=f"⚠️ API Error: {response['error']}"
            )
        except Exception:
            bot.reply_to(message, f"⚠️ API Error: {response['error']}")
        return

    if not isinstance(response, dict) or response.get("status") != 1:
        try:
            bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text="❌ UID has already received its max amount of likes. Limit reached for today, try another UID or after 24 hrs."
            )
        except Exception:
            bot.reply_to(message, "⚠️ Invalid UID or unable to fetch data.")
        return

    try:
        player_uid = str(response.get("UID", uid)).strip()
        player_name = response.get("PlayerNickname", "N/A")
        region = str(response.get("Region", "N/A"))
        likes_before = str(response.get("LikesbeforeCommand", "N/A"))
        likes_after = str(response.get("LikesafterCommand", "N/A"))
        likes_given = str(response.get("LikesGivenByAPI", "N/A"))

        usage["used"] += 1
        usage["last_used"] = now_utc
        like_tracker[user_id] = usage

        response_text = (
            f"✅ *Request Processed Successfully*\n\n"
            f"👤 *Name:* `{player_name}`\n"
            f"🆔 *UID:* `{player_uid}`\n"
            f"🌍 *Region:* `{region}`\n"
            f"🤡 *Likes Before:* `{likes_before}`\n"
            f"📈 *Likes Added:* `{likes_given}`\n"
            f"🗿 *Total Likes Now:* `{likes_after}`\n"
            f"♾️ *Daily Limit:* `Unlimited`"
        )

        bot.edit_message_text(
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
            text=response_text,
            reply_markup=InlineKeyboardMarkup(),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in process_like: {e}")
        bot.reply_to(message, "⚠️ Something went wrong. Likes Send, I can't decode your info.")


@bot.message_handler(commands=["remain"])
def owner_commands(message):
    if message.from_user.id != OWNER_ID:
        return

    lines = ["📊 *Requests Used Today Per User:*"]
    if not like_tracker:
        lines.append("❌ No users have used the bot yet today.")
    else:
        for uid, usage in like_tracker.items():
            lines.append(f"👤 `{uid}` ➜ {usage.get('used', 0)} (Unlimited)")
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id

    if user_id == OWNER_ID:
        help_text = (
            f"📖 *Bot Commands:*\n\n"
            f"🧑‍💻 `/like <region> <uid>` - Send likes to Free Fire UID\n"
            f"🔰 `/start` - Start or verify\n"
            f"🆘 `/help` - Show this help menu\n\n"
            f"👑 *Owner Commands:*\n"
            f"📈 `/remain` - Show all users' usage & stats\n\n"
            f"📞 *Support:* {OWNER_USERNAME}"
        )
        bot.reply_to(message, help_text, parse_mode="Markdown")
        return

    if not is_user_in_channel(user_id):
        markup = InlineKeyboardMarkup()
        for channel in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"🔗 Join {channel}", url=f"https://t.me/{channel.strip('@')}"))
        bot.reply_to(message, "❌ You must join all our channels to use this command.", reply_markup=markup, parse_mode="Markdown")
        return

    help_text = (
        f"📖 *Bot Commands:*\n\n"
        f"🧑‍💻 `/like <region> <uid>` - Send likes to Free Fire UID\n"
        f"🔰 `/start` - Start or verify\n"
        f"🆘 `/help` - Show this help menu\n\n"
        f"📞 *Support:* {OWNER_USERNAME}\n"
        f"🔗 Join our channels for updates!"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")


# === RUN (Webhook if WEBHOOK_URL is set, otherwise Polling) ===
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    webhook_url = os.getenv("WEBHOOK_URL")

    bot.remove_webhook()
    if webhook_url:
        bot.set_webhook(url=webhook_url.rstrip("/") + "/webhook")
        logger.info("Webhook mode")
        app.run(host="0.0.0.0", port=port)
    else:
        logger.info("Polling mode")
        threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()
        bot.infinity_polling()
