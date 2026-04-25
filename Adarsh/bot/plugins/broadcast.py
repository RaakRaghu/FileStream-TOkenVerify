import asyncio
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from Adarsh.bot import StreamBot

OWNER_ID = 8202330446
DATABASE_URL = os.environ.get('DATABASE_URL', 'mongodb+srv://raakraghu:raakraghu@streamingrr.ym8sc0p.mongodb.net/?appName=streamingrr')

# DB
_client = AsyncIOMotorClient(DATABASE_URL)
_db = _client['verify-db']
users_col = _db['users']
stats_col = _db['bot_stats']


# ─── HELPERS ──────────────────────────────────────────────

async def add_user(user_id: int, first_name: str):
    await users_col.update_one(
        {'user_id': user_id},
        {'$set': {
            'user_id': user_id,
            'first_name': first_name,
            'joined': datetime.now().strftime('%Y-%m-%d'),
            'last_active': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }},
        upsert=True
    )

async def update_last_active(user_id: int):
    await users_col.update_one(
        {'user_id': user_id},
        {'$set': {'last_active': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}},
        upsert=True
    )

async def get_all_users():
    return await users_col.find().to_list(length=100000)

async def get_total_users():
    return await users_col.count_documents({})

async def increment_files_shared():
    await stats_col.update_one(
        {'key': 'total_files'},
        {'$inc': {'count': 1}},
        upsert=True
    )

async def get_files_shared():
    doc = await stats_col.find_one({'key': 'total_files'})
    return doc.get('count', 0) if doc else 0

async def get_today_active():
    today = datetime.now().strftime('%Y-%m-%d')
    return await users_col.count_documents({'last_active': {'$regex': f'^{today}'}})


# ─── TRACK USERS AUTOMATICALLY ────────────────────────────

@StreamBot.on_message(filters.private & filters.incoming & ~filters.bot, group=2)
async def track_user(client, message):
    if message.from_user:
        await add_user(message.from_user.id, message.from_user.first_name)


# ─── STATS COMMAND ────────────────────────────────────────

@StreamBot.on_message(filters.command("stats") & filters.private)
async def stats_handler(client, message):
    if message.from_user.id != OWNER_ID:
        # Show basic stats to normal users
        total = await get_total_users()
        files = await get_files_shared()
        await message.reply(
            f"**📊 Bot Statistics**\n\n"
            f"👥 **Total Users:** `{total}`\n"
            f"📁 **Total Files Shared:** `{files}`\n"
        )
        return

    # Full stats for owner
    total = await get_total_users()
    today_active = await get_today_active()
    files = await get_files_shared()
    premium_col = _db['premium_users']
    premium_count = await premium_col.count_documents({})

    await message.reply(
        f"**📊 Full Bot Statistics**\n\n"
        f"👥 **Total Users:** `{total}`\n"
        f"🟢 **Active Today:** `{today_active}`\n"
        f"📁 **Total Files Shared:** `{files}`\n"
        f"👑 **Premium Users:** `{premium_count}`\n"
        f"🗓 **Date:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )


# ─── BROADCAST COMMAND ────────────────────────────────────

@StreamBot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_handler(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can broadcast.")

    # Must reply to a message to broadcast it
    if not message.reply_to_message:
        return await message.reply(
            "**📢 How to Broadcast:**\n\n"
            "Reply to any message with `/broadcast` to send it to all users.\n\n"
            "Example:\n"
            "1. Type your message\n"
            "2. Reply to it with `/broadcast`"
        )

    broadcast_msg = message.reply_to_message
    users = await get_all_users()
    total = len(users)

    if total == 0:
        return await message.reply("No users found in database.")

    status_msg = await message.reply(
        f"**📢 Broadcasting...**\n\n"
        f"Total Users: `{total}`\n"
        f"Please wait..."
    )

    success = 0
    failed = 0
    blocked = 0

    for user in users:
        try:
            await broadcast_msg.copy(user['user_id'])
            success += 1
            await asyncio.sleep(0.05)  # avoid flood
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await broadcast_msg.copy(user['user_id'])
                success += 1
            except:
                failed += 1
        except (UserIsBlocked, InputUserDeactivated):
            blocked += 1
        except Exception:
            failed += 1

        # Update status every 50 users
        if (success + failed + blocked) % 50 == 0:
            try:
                await status_msg.edit(
                    f"**📢 Broadcasting...**\n\n"
                    f"Total: `{total}`\n"
                    f"✅ Success: `{success}`\n"
                    f"❌ Failed: `{failed}`\n"
                    f"🚫 Blocked: `{blocked}`"
                )
            except:
                pass

    # Final status
    await status_msg.edit(
        f"**📢 Broadcast Complete!**\n\n"
        f"Total: `{total}`\n"
        f"✅ Success: `{success}`\n"
        f"❌ Failed: `{failed}`\n"
        f"🚫 Blocked/Deleted: `{blocked}`"
    )
