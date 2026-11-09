Free Fire Likes Bot
Telegram bot: /like <region> <uid>.
Env variables
BOT_TOKEN – from @BotFather
OWNER_ID – your Telegram user id
REQUIRED_CHANNELS – e.g. @channel1,@channel2 (bot must be admin there)
LIKE_API_URL – must contain {region} and {uid}
WEBHOOK_URL – optional (leave empty for polling)
PORT – default 5000
Run
pip install -r requirements.txt
python main.py
