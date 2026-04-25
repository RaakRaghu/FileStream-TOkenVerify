from Adarsh.bot import StreamBot
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
import os

OWNER_ID = 8202330446
DATABASE_URL = os.environ.get('DATABASE_URL', 'mongodb+srv://raakraghu:raakraghu@streamingrr.ym8sc0p.mongodb.net/?appName=streamingrr')

# DB setup
_client = AsyncIOMotorClient(DATABASE_URL)
_db = _client['verify-db']
settings_col = _db['bot_settings']
premium_col = _db['premium_users']


# ─── DB HELPERS ───────────────────────────────────────────

async def get_shortener_status():
    doc = await settings_col.find_one({'key': 'shortener'})
    return doc.get('enabled', True) if doc else True

async def set_shortener_status(enabled: bool):
    await settings_col.update_one(
        {'key': 'shortener'},
        {'$set': {'enabled': enabled}},
        upsert=True
    )

async def get_premium_users():
    docs = await premium_col.find().to_list(length=500)
    return [doc['user_id'] for doc in docs]

async def add_premium_user(user_id: int):
    await premium_col.update_one(
        {'user_id': user_id},
        {'$set': {'user_id': user_id}},
        upsert=True
    )

async def remove_premium_user(user_id: int):
    await premium_col.delete_one({'user_id': user_id})


# ─── SETTINGS MENU ────────────────────────────────────────

async def settings_menu(client, chat_id, message_id=None):
    shortener_on = await get_shortener_status()
    premium_users = await get_premium_users()

    shortener_btn = f"{'✅' if shortener_on else '❌'} Shortener — {'ON' if shortener_on else 'OFF'}"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(shortener_btn, callback_data="toggle_shortener")],
        [InlineKeyboardButton(f"👑 Premium Users ({len(premium_users)})", callback_data="view_premium")],
        [InlineKeyboardButton("➕ Add Premium User", callback_data="add_premium")],
        [InlineKeyboardButton("➖ Remove Premium User", callback_data="remove_premium")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_settings")]
    ])

    text = (
        f"**⚙️ Bot Settings**\n\n"
        f"**Shortener:** {'✅ ON' if shortener_on else '❌ OFF'}\n"
        f"**Premium Users:** {len(premium_users)}\n\n"
        f"_Only owner can change these settings._"
    )
    return text, buttons


@StreamBot.on_message(filters.command("settings") & filters.private)
async def settings_handler(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can access settings.")
    text, buttons = await settings_menu(client, message.chat.id)
    await message.reply(text, reply_markup=buttons)


# ─── CALLBACK HANDLERS ────────────────────────────────────

@StreamBot.on_callback_query(filters.regex("^refresh_settings$"))
async def refresh_settings(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)
    text, buttons = await settings_menu(client, callback.message.chat.id)
    await callback.message.edit_text(text, reply_markup=buttons)
    await callback.answer("Refreshed!")


@StreamBot.on_callback_query(filters.regex("^toggle_shortener$"))
async def toggle_shortener(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)
    current = await get_shortener_status()
    await set_shortener_status(not current)
    status = "ON ✅" if not current else "OFF ❌"
    await callback.answer(f"Shortener turned {status}", show_alert=True)
    text, buttons = await settings_menu(client, callback.message.chat.id)
    await callback.message.edit_text(text, reply_markup=buttons)


@StreamBot.on_callback_query(filters.regex("^view_premium$"))
async def view_premium(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)
    users = await get_premium_users()
    if not users:
        return await callback.answer("No premium users yet.", show_alert=True)
    text = "**👑 Premium Users:**\n\n" + "\n".join([f"• `{uid}`" for uid in users])
    await callback.answer()
    await callback.message.reply(text)


@StreamBot.on_callback_query(filters.regex("^add_premium$"))
async def add_premium_prompt(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)
    await callback.answer()
    await callback.message.reply(
        "**➕ Add Premium User**\n\nSend the user ID like this:\n`/addpremium 1234567890`"
    )


@StreamBot.on_callback_query(filters.regex("^remove_premium$"))
async def remove_premium_prompt(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)
    await callback.answer()
    await callback.message.reply(
        "**➖ Remove Premium User**\n\nSend the user ID like this:\n`/removepremium 1234567890`"
    )


# ─── ADD / REMOVE COMMANDS ────────────────────────────────

@StreamBot.on_message(filters.command("addpremium") & filters.private)
async def add_premium_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return await message.reply("Usage: `/addpremium 1234567890`")
    user_id = int(args[1])
    await add_premium_user(user_id)
    await message.reply(f"✅ User `{user_id}` added to premium!")


@StreamBot.on_message(filters.command("removepremium") & filters.private)
async def remove_premium_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return await message.reply("Usage: `/removepremium 1234567890`")
    user_id = int(args[1])
    await remove_premium_user(user_id)
    await message.reply(f"✅ User `{user_id}` removed from premium!")
