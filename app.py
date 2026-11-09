from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError
import base64
import threading
import telebot

app = Flask(__name__)

# === توكن البوت الجديد ===
TELEGRAM_TOKEN = '8967315640:AAHEKUmkNHZhOX2b8gbaa-oqvpFFAd4ncaA'
bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "🔥 **أهلاً بك في بوت إرسال لايكات فري فاير!**\n\n"
        "استخدم الأمر بالشكل التالي (بدون حد أقصى للاستخدام):\n"
        "`/like mn [الآيدي]`\n\n"
        "مثال:\n"
        "`/like mn 12345678`", 
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['like'])
def handle_telegram_like(message):
    try:
        args = message.text.split()
        if len(args) < 3:
            bot.reply_to(
                message, 
                "⚠️ **خطأ في الصيغة!**\n"
                "يرجى كتابة الأمر هكذا:\n"
                "`/like mn [الآيدي]`\n\n"
                "مثال: `/like mn 12345678`", 
                parse_mode='Markdown'
            )
            return

        server_name = args[1].upper()
        uid = args[2]

        processing_msg = bot.reply_to(
            message, 
            f"⏳ **جاري معالجة وإرسال اللايكات...**\n"
            f"- السيرفر: `{server_name}`\n"
            f"- الآيدي: `{uid}`", 
            parse_mode='Markdown'
        )

        # استدعاء دالة إرسال اللايكات الفعليه
        result, status_code = process_like_logic(uid, server_name)

        if status_code == 200:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=processing_msg.message_id,
                text=f"✅ **تم إرسال اللايكات بنجاح!**\n\n"
                     f"👤 **الاسم:** `{result.get('PlayerNickname')}`\n"
                     f"🆔 **الآيدي:** `{result.get('UID')}`\n"
                     f"🌍 **السيرفر:** `{result.get('Region')}`\n"
                     f"👍 **اللايكات السابقة:** `{result.get('LikesbeforeCommand')}`\n"
                     f"🚀 **اللايكات الجديدة:** `{result.get('LikesafterCommand')}`\n"
                     f"📈 **المضاف:** `{result.get('LikesGivenByAPI')}`",
                parse_mode='Markdown'
            )
        else:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=processing_msg.message_id,
                text=f"❌ **فشل إرسال اللايكات!**\nالسبب: `{result.get('error', 'خطأ غير معروف')}`",
                parse_mode='Markdown'
            )

    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ غير متوقع: `{str(e)}`", parse_mode='Markdown')


# === الدوال البرمجية الأساسية ===

def load_tokens():
    try:
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading tokens: {e}")
        return None

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Error encrypting message: {e}")
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating protobuf message: {e}")
        return None

async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'X-GA-SV': "1789638359",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.12f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB55"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                if response.status != 200:
                    return response.status
                return await response.text()
    except Exception as e:
        return None

async def send_multiple_requests(uid, server_name, url):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            return None
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            return None
        tasks = []
        tokens = load_tokens()
        if tokens is None:
            return None
        for i in range(100):
            token = tokens[i % len(tokens)]["token"]
            tasks.append(send_request(encrypted_uid, token, url))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    except Exception as e:
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

def make_request(encrypt, server_name, token):
    try:
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        else:
            url = "https://clientbp.ppmainecoonghj.com/GetPlayerPersonalShow"
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'X-GA-SV': "1789638359",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.12f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB55"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False)
        hex_data = response.content.hex()
        binary = bytes.fromhex(hex_data)
        decode = decode_protobuf(binary)
        return decode
    except Exception as e:
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except Exception as e:
        return None

def process_like_logic(uid, server_name):
    tokens = load_tokens()
    if tokens is None or not tokens:
        return {"error": "Failed to load tokens."}, 500
    token = tokens[0]['token']
    
    if not server_name:
        try:
            payload = token.split('.')[1]
            payload += '=' * (-len(payload) % 4)
            decoded_payload = base64.urlsafe_b64decode(payload).decode('utf-8')
            parsed_payload = json.loads(decoded_payload)
            server_name = parsed_payload.get('lock_region', '').upper()
        except Exception as e:
            pass
    
    if not server_name:
        return {"error": "server_name could not be determined"}, 400
    
    encrypted_uid = enc(uid)
    if encrypted_uid is None:
        return {"error": "Encryption of UID failed."}, 500

    before = make_request(encrypted_uid, server_name, token)
    if before is None:
        return {"error": "Failed to retrieve player info. Please update tokens.json"}, 500
    
    data_before = json.loads(MessageToJson(before))
    before_like = int(data_before.get('AccountInfo', {}).get('Likes', 0) or 0)

    if server_name == "IND":
        url = "https://client.ind.freefiremobile.com/LikeProfile"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        url = "https://client.us.freefiremobile.com/LikeProfile"
    else:
        url = "https://clientbp.ppmainecoonghj.com/LikeProfile"

    asyncio.run(send_multiple_requests(uid, server_name, url))

    after = make_request(encrypted_uid, server_name, token)
    if after is None:
        return {"error": "Failed to retrieve player info after likes."}, 500
    
    data_after = json.loads(MessageToJson(after))
    account_info = data_after.get('AccountInfo', {})
    after_like = int(account_info.get('Likes', 0) or 0)
    player_uid = int(account_info.get('UID', 0) or 0)
    player_name = str(account_info.get('PlayerNickname', ''))
    
    like_given = after_like - before_like
    
    return {
        "credit": "https://t.me/paglu_dev",
        "LikesGivenByAPI": like_given,
        "LikesafterCommand": after_like,
        "LikesbeforeCommand": before_like,
        "PlayerNickname": player_name,
        "Region": server_name,
        "UID": player_uid,
        "status": 1 if like_given > 0 else 2
    }, 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "credit": "https://t.me/paglu_dev",
        "message": "Welcome to the Free Fire Like API & Telegram Bot",
        "status": "API is running",
        "endpoints": "/like?uid=<uid>&server_name=<server_name>"
    })

@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "UID is required"}), 400
    server_name = request.args.get("server_name", "").upper()
    
    result, status_code = process_like_logic(uid, server_name)
    return jsonify(result), status_code

def run_telegram_bot():
    try:
        print("Telegram Bot started polling...")
        bot.infinity_polling(none_stop=True)
    except Exception as e:
        print(f"Telegram Bot error: {e}")

if __name__ == '__main__':
    t = threading.Thread(target=run_telegram_bot)
    t.daemon = True
    t.start()

    app.run(host='0.0.0.0', port=5000, debug=False)
