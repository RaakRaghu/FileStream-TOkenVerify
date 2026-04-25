import os
import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from Adarsh.bot import StreamBot

OWNER_ID = 8202330446
DATABASE_URL = os.environ.get('DATABASE_URL', 'mongodb+srv://raakraghu:raakraghu@streamingrr.ym8sc0p.mongodb.net/?appName=streamingrr')

# DB
_client = AsyncIOMotorClient(DATABASE_URL)
_db = _client['verify-db']
premium_col = _db['premium_users']


# ─── HELPERS ──────────────────────────────────────────────

def parse_duration(duration_str: str):
    """
    Parse duration string to seconds.
    Examples: 1h, 12h, 1d, 7d, 30d, 1m (1 month)
    """
    duration_str = duration_str.lower().strip()
    try:
        if duration_str.endswith('h'):
            return int(duration_str[:-1]) * 3600
        elif duration_str.endswith('d'):
            return int(duration_str[:-1]) * 86400
        elif duration_str.endswith('m'):
            return int(duration_str[:-1]) * 2592000  # 30 days
        elif duration_str.endswith('w'):
            return int(duration_str[:-1]) * 604800  # 7 days
        else:
            return None
    except ValueError:
        return None


def get_readable_time(seconds: int):
    seconds = int(seconds)
    periods = [
        ('month', 2592000),
        ('week', 604800),
        ('day', 86400),
        ('hour', 3600),
        ('minute', 60),
        ('second', 1)
    ]
    result = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            if period_value > 1:
                result.append(f"{int(period_value)} {period_name}s")
            else:
                result.append(f"{int(period_value)} {period_name}")
    return ', '.join(result[:2]) if result else '0 seconds'


async def add_premium(user_id: int, seconds: int, first_name: str = "Unknown"):
    expiry = datetime.now() + timedelta(seconds=seconds)
    await premium_col.update_one(
        {'user_id': user_id},
        {'$set': {
            'user_id': user_id,
            'first_name': first_name,
            'expiry': expiry,
            'expiry_str': expiry.strftime('%Y-%m-%d %H:%M:%S'),
            'plan': get_readable_time(seconds),
            'added_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }},
        upsert=True
    )


async def remove_premium(user_id: int):
    await premium_col.delete_one({'user_id': user_id})


async def is_premium(user_id: int):
    doc = await premium_col.find_one({'user_id': user_id})
    if not doc:
        return False
    expiry = doc.get('expiry')
    if not expiry:
        return False
    if datetime.now() > expiry:
        # Auto remove expired premium
        await premium_col.delete_one({'user_id': user_id})
        return False
    return True


async def get_premium_info(user_id: int):
    doc = await premium_col.find_one({'user_id': user_id})
    if not doc:
        return None
    expiry = doc.get('expiry')
    if expiry and datetime.now() > expiry:
        await premium_col.delete_one({'user_id': user_id})
        return None
    return doc


async def get_all_premium():
    docs = await premium_col.find().to_list(length=500)
    active = []
    for doc in docs:
        expiry = doc.get('expiry')
        if expiry and datetime.now() < expiry:
            active.append(doc)
        else:
            await premium_col.delete_one({'user_id': doc['user_id']})
    return active


# ─── AUTO EXPIRY CHECKER ──────────────────────────────────

async def check_expired_premium():
    """Runs in background, notifies users when premium expires."""
    while True:
        try:
            docs = await premium_col.find().to_list(length=500)
            for doc in docs:
                expiry = doc.get('expiry')
                user_id = doc.get('user_id')
                if expiry and datetime.now() > expiry:
                    # Notify user
                    try:
                        await StreamBot.send_message(
                            chat_id=user_id,
                            text=(
                                "⏰ **Your Premium Has Expired!**\n\n"
                                "Your premium access has ended.\n"
                                "You will need to verify via ads token again.\n\n"
                                "Contact the owner to renew your premium. 💎"
                            )
                        )
                    except Exception:
                        pass
                    # Remove from DB
                    await premium_col.delete_one({'user_id': user_id})
                    print(f"Premium expired for user {user_id}")
        except Exception as e:
            print(f"Premium checker error: {e}")
        await asyncio.sleep(3600)  # check every 1 hour


# Start background checker when bot starts
asyncio.get_event_loop().create_task(check_expired_premium())


# ─── COMMANDS ─────────────────────────────────────────────

@StreamBot.on_message(filters.command("addpremium") & filters.private)
async def add_premium_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")

    args = message.text.split()
    if len(args) != 3:
        return await message.reply(
            "**👑 Add Premium User**\n\n"
            "**Usage:** `/addpremium USER_ID DURATION`\n\n"
            "**Duration formats:**\n"
            "`1h` — 1 hour\n"
            "`12h` — 12 hours\n"
            "`1d` — 1 day\n"
            "`7d` — 7 days\n"
            "`1w` — 1 week\n"
            "`1m` — 1 month\n"
            "`30d` — 30 days\n\n"
            "**Examples:**\n"
            "`/addpremium 1234567890 7d`\n"
            "`/addpremium 1234567890 1m`\n"
            "`/addpremium 1234567890 12h`"
        )

    if not args[1].isdigit():
        return await message.reply("❌ Invalid user ID. Must be a number.")

    user_id = int(args[1])
    duration_str = args[2]
    seconds = parse_duration(duration_str)

    if not seconds:
        return await message.reply(
            "❌ Invalid duration format.\n\n"
            "Use: `1h`, `1d`, `7d`, `1w`, `1m`"
        )

    # Try to get user first name
    try:
        user = await client.get_users(user_id)
        first_name = user.first_name
    except Exception:
        first_name = "Unknown"

    await add_premium(user_id, seconds, first_name)
    expiry = datetime.now() + timedelta(seconds=seconds)

    # Notify owner
    await message.reply(
        f"✅ **Premium Added!**\n\n"
        f"👤 **User:** [{first_name}](tg://user?id={user_id})\n"
        f"🆔 **User ID:** `{user_id}`\n"
        f"⏱ **Plan:** `{get_readable_time(seconds)}`\n"
        f"📅 **Expires:** `{expiry.strftime('%Y-%m-%d %H:%M:%S')}`"
    )

    # Notify user
    try:
        await client.send_message(
            chat_id=user_id,
            text=(
                f"🎉 **You Got Premium Access!**\n\n"
                f"💎 **Plan:** `{get_readable_time(seconds)}`\n"
                f"📅 **Expires:** `{expiry.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"You can now use the bot without ads verification!\n"
                f"Enjoy your premium access 😊"
            )
        )
    except Exception:
        pass


@StreamBot.on_message(filters.command("removepremium") & filters.private)
async def remove_premium_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")

    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return await message.reply("**Usage:** `/removepremium USER_ID`")

    user_id = int(args[1])
    doc = await get_premium_info(user_id)

    if not doc:
        return await message.reply(f"❌ User `{user_id}` is not a premium user.")

    await remove_premium(user_id)

    await message.reply(f"✅ Premium removed for user `{user_id}`.")

    # Notify user
    try:
        await client.send_message(
            chat_id=user_id,
            text=(
                "❌ **Your Premium Has Been Removed.**\n\n"
                "You will need to verify via ads token to use the bot.\n"
                "Contact the owner for more info."
            )
        )
    except Exception:
        pass


@StreamBot.on_message(filters.command("premiumlist") & filters.private)
async def premium_list_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can view this.")

    active = await get_all_premium()

    if not active:
        return await message.reply("No active premium users.")

    text = f"**👑 Active Premium Users ({len(active)}):**\n\n"
    for doc in active:
        expiry = doc.get('expiry')
        remaining = expiry - datetime.now() if expiry else None
        remaining_str = get_readable_time(int(remaining.total_seconds())) if remaining else "Unknown"
        text += (
            f"👤 [{doc.get('first_name', 'Unknown')}](tg://user?id={doc['user_id']})\n"
            f"🆔 `{doc['user_id']}`\n"
            f"⏱ Remaining: `{remaining_str}`\n"
            f"📅 Expires: `{doc.get('expiry_str', 'Unknown')}`\n\n"
        )

    await message.reply(text)


@StreamBot.on_message(filters.command("mypremium") & filters.private)
async def my_premium_cmd(client, message):
    user_id = message.from_user.id
    doc = await get_premium_info(user_id)

    if not doc:
        return await message.reply(
            "❌ **You are not a premium user.**\n\n"
            "Contact the owner to get premium access. 💎"
        )

    expiry = doc.get('expiry')
    remaining = expiry - datetime.now() if expiry else None
    remaining_str = get_readable_time(int(remaining.total_seconds())) if remaining else "Unknown"

    await message.reply(
        f"💎 **Your Premium Info:**\n\n"
        f"✅ **Status:** Active\n"
        f"⏱ **Plan:** `{doc.get('plan', 'Unknown')}`\n"
        f"⏳ **Remaining:** `{remaining_str}`\n"
        f"📅 **Expires:** `{doc.get('expiry_str', 'Unknown')}`"
    )
