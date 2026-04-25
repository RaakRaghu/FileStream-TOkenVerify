import os
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from Adarsh.bot import StreamBot

OWNER_ID = 8202330446
DATABASE_URL = os.environ.get('DATABASE_URL', 'mongodb+srv://raakraghu:raakraghu@streamingrr.ym8sc0p.mongodb.net/?appName=streamingrr')

# DB
_client = AsyncIOMotorClient(DATABASE_URL)
_db = _client['verify-db']
requests_col = _db['file_requests']


# ─── HELPERS ──────────────────────────────────────────────

async def save_request(user_id, first_name, username, request_text):
    result = await requests_col.insert_one({
        'user_id': user_id,
        'first_name': first_name,
        'username': username or 'No username',
        'request': request_text,
        'status': 'pending',
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    return result.inserted_id

async def get_pending_requests():
    return await requests_col.find({'status': 'pending'}).to_list(length=100)

async def update_request_status(request_id, status):
    from bson import ObjectId
    await requests_col.update_one(
        {'_id': ObjectId(request_id)},
        {'$set': {'status': status}}
    )

async def get_user_pending_count(user_id):
    return await requests_col.count_documents({
        'user_id': user_id,
        'status': 'pending'
    })


# ─── USER: REQUEST FILE ───────────────────────────────────

@StreamBot.on_message(filters.command("request") & filters.private)
async def request_file_cmd(client, message):
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply(
            "**📩 File Request System**\n\n"
            "Use this command to request a movie or file.\n\n"
            "**Usage:**\n"
            "`/request Movie Name (Year)`\n\n"
            "**Examples:**\n"
            "`/request Avengers Endgame 2019`\n"
            "`/request Pushpa 2 Hindi`\n\n"
            "⚠️ Max 3 pending requests at a time."
        )

    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    request_text = args[1].strip()

    # Check pending request limit
    pending_count = await get_user_pending_count(user_id)
    if pending_count >= 3:
        return await message.reply(
            "⚠️ **You already have 3 pending requests!**\n\n"
            "Please wait for your existing requests to be processed before adding more.\n\n"
            "Use /myrequests to see your pending requests."
        )

    # Save request
    request_id = await save_request(user_id, first_name, username, request_text)

    # Notify user
    await message.reply(
        f"✅ **Request Submitted!**\n\n"
        f"📋 **Your Request:** `{request_text}`\n"
        f"🕐 **Status:** Pending\n\n"
        f"You will be notified when your request is fulfilled or rejected."
    )

    # Notify owner
    await client.send_message(
        chat_id=OWNER_ID,
        text=(
            f"📩 **New File Request!**\n\n"
            f"👤 **User:** [{first_name}](tg://user?id={user_id})\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"👤 **Username:** @{username or 'None'}\n"
            f"📋 **Request:** `{request_text}`\n"
            f"🕐 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🔑 **Request ID:** `{request_id}`"
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Fulfill", callback_data=f"req_fulfill_{request_id}_{user_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"req_reject_{request_id}_{user_id}")
            ],
            [
                InlineKeyboardButton("📋 All Requests", callback_data="req_viewall")
            ]
        ])
    )


# ─── USER: MY REQUESTS ────────────────────────────────────

@StreamBot.on_message(filters.command("myrequests") & filters.private)
async def my_requests_cmd(client, message):
    user_id = message.from_user.id
    requests = await requests_col.find(
        {'user_id': user_id}
    ).sort('date', -1).to_list(length=10)

    if not requests:
        return await message.reply("You haven't made any requests yet.\n\nUse `/request Movie Name` to request a file.")

    text = "**📋 Your Requests:**\n\n"
    for req in requests:
        status_emoji = "⏳" if req['status'] == 'pending' else "✅" if req['status'] == 'fulfilled' else "❌"
        text += (
            f"{status_emoji} **{req['request']}**\n"
            f"   Status: `{req['status'].capitalize()}`\n"
            f"   Date: `{req['date']}`\n\n"
        )

    await message.reply(text)


# ─── OWNER: VIEW ALL PENDING REQUESTS ─────────────────────

@StreamBot.on_message(filters.command("requests") & filters.private)
async def view_requests_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can view all requests.")

    pending = await get_pending_requests()

    if not pending:
        return await message.reply("✅ No pending requests!")

    text = f"**📋 Pending Requests ({len(pending)}):**\n\n"
    for i, req in enumerate(pending[:10], 1):
        text += (
            f"**{i}.** `{req['request']}`\n"
            f"   👤 [{req['first_name']}](tg://user?id={req['user_id']})\n"
            f"   🔑 ID: `{req['_id']}`\n\n"
        )

    buttons = []
    for req in pending[:5]:
        buttons.append([
            InlineKeyboardButton(
                f"✅ {req['request'][:20]}",
                callback_data=f"req_fulfill_{req['_id']}_{req['user_id']}"
            ),
            InlineKeyboardButton(
                "❌",
                callback_data=f"req_reject_{req['_id']}_{req['user_id']}"
            )
        ])

    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)


# ─── CALLBACKS: FULFILL / REJECT ──────────────────────────

@StreamBot.on_callback_query(filters.regex(r"^req_fulfill_(.+)_(\d+)$"))
async def fulfill_request(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)

    data = callback.data.split("_")
    request_id = data[2]
    user_id = int(data[3])

    await update_request_status(request_id, "fulfilled")

    # Notify user
    try:
        await client.send_message(
            chat_id=user_id,
            text=(
                "✅ **Your Request Has Been Fulfilled!**\n\n"
                "The file you requested has been uploaded.\n"
                "Check the bot or channel for your file. 🎉"
            )
        )
    except Exception:
        pass

    await callback.answer("✅ Marked as fulfilled!", show_alert=True)
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Fulfilled", callback_data="req_done")]
        ])
    )


@StreamBot.on_callback_query(filters.regex(r"^req_reject_(.+)_(\d+)$"))
async def reject_request(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)

    data = callback.data.split("_")
    request_id = data[2]
    user_id = int(data[3])

    await update_request_status(request_id, "rejected")

    # Notify user
    try:
        await client.send_message(
            chat_id=user_id,
            text=(
                "❌ **Your Request Has Been Rejected.**\n\n"
                "Sorry, we couldn't fulfill your request at this time.\n"
                "You can try requesting something else using /request"
            )
        )
    except Exception:
        pass

    await callback.answer("❌ Marked as rejected!", show_alert=True)
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Rejected", callback_data="req_done")]
        ])
    )


@StreamBot.on_callback_query(filters.regex("^req_viewall$"))
async def view_all_callback(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)
    await callback.answer()
    pending = await get_pending_requests()
    if not pending:
        return await callback.message.reply("✅ No pending requests!")
    text = f"**📋 Pending Requests ({len(pending)}):**\n\n"
    for i, req in enumerate(pending[:10], 1):
        text += (
            f"**{i}.** `{req['request']}`\n"
            f"   👤 [{req['first_name']}](tg://user?id={req['user_id']})\n\n"
        )
    await callback.message.reply(text)


@StreamBot.on_callback_query(filters.regex("^req_done$"))
async def req_done(client, callback: CallbackQuery):
    await callback.answer("Already processed!", show_alert=True)
