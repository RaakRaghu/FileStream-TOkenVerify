import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from Adarsh.bot import StreamBot

OWNER_ID = 8202330446
DATABASE_URL = os.environ.get('DATABASE_URL', 'mongodb+srv://raakraghu:raakraghu@streamingrr.ym8sc0p.mongodb.net/?appName=streamingrr')

# DB
_client = AsyncIOMotorClient(DATABASE_URL)
_db = _client['verify-db']
settings_col = _db['bot_settings']


# ─── HELPERS ──────────────────────────────────────────────

async def get_auto_delete_time():
    doc = await settings_col.find_one({'key': 'auto_delete'})
    return doc.get('seconds', 0) if doc else 0  # 0 = disabled


async def set_auto_delete_time(seconds: int):
    await settings_col.update_one(
        {'key': 'auto_delete'},
        {'$set': {'seconds': seconds}},
        upsert=True
    )


async def auto_delete_message(message, seconds):
    """Delete a message after X seconds with countdown."""
    if seconds <= 0:
        return
    try:
        await asyncio.sleep(seconds)
        await message.delete()
    except Exception as e:
        print(f"Auto delete error: {e}")


async def send_with_autodelete(client, chat_id, text, reply_markup=None, reply_to=None):
    """Send a message and schedule auto delete."""
    seconds = await get_auto_delete_time()
    sent = await client.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        reply_to_message_id=reply_to,
        disable_web_page_preview=True
    )
    if seconds > 0:
        # Send warning
        warn = await client.send_message(
            chat_id=chat_id,
            text=f"⚠️ This message will be deleted in `{get_readable_time(seconds)}`",
            reply_to_message_id=sent.id
        )
        asyncio.create_task(auto_delete_message(sent, seconds))
        asyncio.create_task(auto_delete_message(warn, seconds))
    return sent


def get_readable_time(seconds):
    seconds = int(seconds)
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result or '0s'


# ─── COMMANDS ─────────────────────────────────────────────

@StreamBot.on_message(filters.command("setautodelete") & filters.private)
async def set_autodelete_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")

    args = message.text.split()
    if len(args) != 2:
        current = await get_auto_delete_time()
        status = f"`{get_readable_time(current)}`" if current > 0 else "`Disabled`"
        return await message.reply(
            f"**⏱ Auto Delete Settings**\n\n"
            f"Current: {status}\n\n"
            f"**Usage:**\n"
            f"`/setautodelete 300` — delete after 5 minutes\n"
            f"`/setautodelete 3600` — delete after 1 hour\n"
            f"`/setautodelete 0` — disable auto delete\n\n"
            f"**Quick values:**\n"
            f"5 min = 300\n"
            f"10 min = 600\n"
            f"30 min = 1800\n"
            f"1 hour = 3600\n"
            f"6 hours = 21600\n"
            f"24 hours = 86400"
        )

    if not args[1].isdigit():
        return await message.reply("❌ Please provide seconds as a number.\nExample: `/setautodelete 300`")

    seconds = int(args[1])
    await set_auto_delete_time(seconds)

    if seconds == 0:
        await message.reply("✅ Auto delete **disabled**.")
    else:
        await message.reply(
            f"✅ Auto delete set to **{get_readable_time(seconds)}**.\n\n"
            f"Stream/download links will be deleted after {get_readable_time(seconds)}."
        )
