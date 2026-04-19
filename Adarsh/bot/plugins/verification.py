import os
import string
import random

from time import time
from urllib3 import disable_warnings
from cloudscraper import create_scraper
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from Adarsh.bot import StreamBot  # ← use your actual bot instance

verify_dict = {}

# CONFIG
VERIFY_PHOTO     = os.environ.get('VERIFY_PHOTO', 'https://i.pinimg.com/1200x/c5/9f/d2/c59fd21f87ecdc683f7c68813b601aa6.jpg')
SHORTLINK_SITE   = os.environ.get('SHORTLINK_SITE', 'urlshortx.com')
SHORTLINK_API    = os.environ.get('SHORTLINK_API', '')
VERIFY_EXPIRE    = int(os.environ.get('VERIFY_EXPIRE', 3600))   # ← always int
VERIFY_TUTORIAL  = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/tutorialll566565')
DATABASE_URL     = os.environ.get('DATABASE_URL', '')
COLLECTION_NAME  = os.environ.get('COLLECTION_NAME', 'streamingg')
PREMIUM_USERS    = list(map(int, os.environ.get('PREMIUM_USERS', '').split())) if os.environ.get('PREMIUM_USERS') else []


# DATABASE
class VerifyDB():
    def __init__(self):
        try:
            self._dbclient = AsyncIOMotorClient(DATABASE_URL)
            self._db = self._dbclient['verify-db']
            self._verifydb = self._db[COLLECTION_NAME]
            print('Database Connected ✅')
        except Exception as e:
            print(f'Failed To Connect To Database ❌\nError: {str(e)}')

    async def get_verify_status(self, user_id):
        if status := await self._verifydb.find_one({'id': user_id}):
            return status.get('verify_status', 0)
        return 0

    async def update_verify_status(self, user_id):
        await self._verifydb.update_one(
            {'id': user_id},
            {'$set': {'verify_status': time()}},
            upsert=True
        )

verifydb = VerifyDB()


# HELPER FUNCTIONS
def get_readable_time(seconds):
    seconds = int(seconds)
    periods = [('ᴅ', 86400), ('ʜ', 3600), ('ᴍ', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result or '0s'


async def is_user_verified(user_id):
    if not VERIFY_EXPIRE or (user_id in PREMIUM_USERS):
        return True
    isveri = await verifydb.get_verify_status(user_id)
    if not isveri or (time() - float(isveri)) >= float(VERIFY_EXPIRE):
        return False
    return True


async def get_short_url(longurl):
    cget = create_scraper().request
    disable_warnings()
    try:
        url = f'https://{SHORTLINK_SITE}/api'
        params = {'api': SHORTLINK_API, 'url': longurl, 'format': 'text'}
        res = cget('GET', url, params=params)
        if res.status_code == 200 and res.text.strip():
            return res.text.strip()
        # fallback: try json format
        params['format'] = 'json'
        res = cget('GET', url, params=params)
        data = res.json()                          # ← parse to dict first
        if res.status_code == 200:
            return data.get('shortenedUrl', longurl)  # ← use longurl not long_url
    except Exception as e:
        print(f"Shortener error: {e}")
    return longurl


async def get_verify_token(bot, userid, link):
    vdict = verify_dict.setdefault(userid, {})
    short_url = vdict.get('short_url')
    if not short_url:
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        long_link = f"{link}verify-{userid}-{token}"
        short_url = await get_short_url(long_link)
        vdict.update({'token': token, 'short_url': short_url})
    return short_url


async def send_verification(client, message, text=None, buttons=None):
    username = (await client.get_me()).username
    if await is_user_verified(message.from_user.id):
        text = f'<b>Hi 👋 {message.from_user.mention},\nYou Are Already Verified Enjoy 😄</b>'
        buttons = None
    else:
        verify_token = await get_verify_token(client, message.from_user.id, f"https://telegram.me/{username}?start=")
        if not buttons:
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton('🔗 Get Token', url=verify_token)],
                [InlineKeyboardButton('🎬 Tutorial 🎬', url=VERIFY_TUTORIAL)]
            ])
    if not text:
        text = (
            f"<b>Hi 👋 {message.from_user.mention},\n"
            f"<blockquote expandable>Your Ads Token Has Expired.\n"
            f"Get a new token to continue using this bot.\n\n"
            f"Validity: {get_readable_time(VERIFY_EXPIRE)}\n"
            f"#Verification...⌛</blockquote></b>"
        )
    msg = message if isinstance(message, Message) else message.message
    await client.send_photo(
        chat_id=msg.chat.id,
        photo=VERIFY_PHOTO,
        caption=text,
        reply_markup=buttons,
        reply_to_message_id=msg.id,
    )


async def validate_token(client, message, data):
    user_id = message.from_user.id
    vdict = verify_dict.setdefault(user_id, {})
    dict_token = vdict.get('token', None)
    if await is_user_verified(user_id):
        return await message.reply("<b>You Are Already Verified 🤓</b>")
    if not dict_token:
        return await send_verification(client, message, text="<b>That's Not Your Verify Token 🥲\n\nTap On Verify To Generate Yours.</b>")
    try:
        _, uid, token = data.split("-")
    except ValueError:
        return await send_verification(client, message, text="<b>Invalid Token Format. Tap Verify to try again.</b>")
    if uid != str(user_id):
        return await send_verification(client, message, text="<b>Token Did Not Match 😕\n\nTap Verify To Generate Again.</b>")
    if dict_token != token:
        return await send_verification(client, message, text="<b>Invalid Or Expired Token 🔗</b>")
    verify_dict.pop(user_id, None)
    await verifydb.update_verify_status(user_id)
    await client.send_photo(
        chat_id=message.from_user.id,
        photo=VERIFY_PHOTO,
        caption=f'<b>Welcome Back 😁, You Can Now Use Me For {get_readable_time(VERIFY_EXPIRE)}.\n\nEnjoy ❤️</b>',
        reply_to_message_id=message.id,
    )


# GLOBAL FILTER — intercepts all messages if not verified
async def token_system_filter(_, __, message):
    if not message.from_user:
        return False
    return not await is_user_verified(message.from_user.id)


@StreamBot.on_message(
    (filters.private | filters.group)
    & filters.incoming
    & filters.create(token_system_filter)
    & ~filters.bot
)
async def global_verify_function(client, message):
    if message.text:
        cmd = message.text.split()
        if len(cmd) == 2 and cmd[1].startswith("verify"):
            await validate_token(client, message, cmd[1])
            return
    await send_verification(client, message)
