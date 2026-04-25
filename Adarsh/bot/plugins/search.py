# (c) adarsh-goel | search & index by RaakRaghu
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from urllib.parse import quote_plus
from Adarsh.bot import StreamBot
from Adarsh.utils.file_properties import get_name, get_hash, get_media_file_size
from Adarsh.utils.human_readable import humanbytes
from Adarsh.vars import Var

# ── Pull everything from Var — no hardcoding ──────────────
OWNER_ID = list(Var.OWNER_ID)[0]  # Var.OWNER_ID is a set
BASE_URL = Var.URL                 # already "http://144.24.147.39:8099/"

# Channels to auto-index (add more with /addindexchannel)
ALLOWED_INDEX_CHANNELS = [
    int(Var.BIN_CHANNEL),          # -1003613344939 from your Var
]

# ── DB setup using Var.DATABASE_URL ───────────────────────
_client = AsyncIOMotorClient(Var.DATABASE_URL)
_db = _client['verify-db']
files_col = _db['indexed_files']


# ─── DB HELPERS ───────────────────────────────────────────

async def save_file(file_id, file_name, file_size, msg_id, channel_id):
    await files_col.update_one(
        {'file_id': file_id},
        {'$set': {
            'file_id': file_id,
            'file_name': file_name,
            'file_name_lower': file_name.lower(),
            'file_size': file_size,
            'msg_id': msg_id,
            'channel_id': channel_id,
        }},
        upsert=True
    )


async def search_files(query: str, limit: int = 10):
    keywords = query.lower().split()
    regex = ''.join([f'(?=.*{kw})' for kw in keywords])
    cursor = files_col.find(
        {'file_name_lower': {'$regex': regex}}
    ).limit(limit)
    return await cursor.to_list(length=limit)


async def get_total_indexed():
    return await files_col.count_documents({})


# ─── BUILD LINKS — uses Var.URL ───────────────────────────

def build_links(msg_id, file_name):
    encoded = quote_plus(file_name)
    stream   = f"{BASE_URL}watch/{msg_id}/{encoded}"
    download = f"{BASE_URL}{msg_id}/{encoded}"
    return stream, download


# ─── AUTO INDEX — listens to allowed channels ─────────────

@StreamBot.on_message(
    filters.channel
    & (filters.document | filters.video | filters.audio | filters.photo)
    & ~filters.forwarded,
    group=5
)
async def auto_index_handler(client, message):
    if message.chat.id not in ALLOWED_INDEX_CHANNELS:
        return
    try:
        log_msg = await message.forward(chat_id=Var.BIN_CHANNEL)
        file_name = get_name(log_msg)
        file_size = get_media_file_size(message)
        file_id = (
            message.document.file_id  if message.document else
            message.video.file_id     if message.video    else
            message.audio.file_id     if message.audio    else
            message.photo.file_id     if message.photo    else None
        )
        if not file_id:
            return
        await save_file(
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            msg_id=log_msg.id,
            channel_id=message.chat.id
        )
        print(f"[AutoIndex] {file_name}")
    except Exception as e:
        print(f"[AutoIndex Error] {e}")


# ─── FORWARD INDEX — owner forwards files to bot ──────────

@StreamBot.on_message(
    filters.private
    & filters.forwarded
    & (filters.document | filters.video | filters.audio | filters.photo)
    & filters.user(OWNER_ID),
    group=5
)
async def forward_index_handler(client, message):
    try:
        log_msg = await message.forward(chat_id=Var.BIN_CHANNEL)
        file_name = get_name(log_msg)
        file_size = get_media_file_size(message)
        file_id = (
            message.document.file_id  if message.document else
            message.video.file_id     if message.video    else
            message.audio.file_id     if message.audio    else
            message.photo.file_id     if message.photo    else None
        )
        if not file_id:
            return
        await save_file(
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            msg_id=log_msg.id,
            channel_id=message.forward_from_chat.id if message.forward_from_chat else 0
        )
        total = await get_total_indexed()
        stream_link, download_link = build_links(log_msg.id, file_name)
        await message.reply(
            f"✅ **Indexed & Saved!**\n\n"
            f"📂 `{file_name}`\n"
            f"📦 Size: `{humanbytes(file_size)}`\n"
            f"🗃 Total in DB: `{total}`\n\n"
            f"🔗 **Stream:** {stream_link}\n"
            f"⬇️ **Download:** {download_link}",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[ForwardIndex Error] {e}")
        await message.reply(f"❌ Error: `{e}`")


# ─── MANUAL /index COMMAND ────────────────────────────────

@StreamBot.on_message(filters.command("index") & filters.private)
async def manual_index_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can run indexing.")
    total = await get_total_indexed()
    await message.reply(
        "**📡 How To Index Files:**\n\n"
        "**Method 1 — Forward files to me:**\n"
        "1. Go to your channel\n"
        "2. Select files → Forward them here\n"
        "3. I will index each one automatically ✅\n\n"
        "**Method 2 — Auto index:**\n"
        "Post new files directly to your index channel.\n"
        "I will index them automatically ✅\n\n"
        f"📦 **Currently Indexed:** `{total}` files\n\n"
        "Use /indexstats for details."
    )


# ─── ADD / REMOVE / LIST INDEX CHANNELS ──────────────────

@StreamBot.on_message(filters.command("addindexchannel") & filters.private)
async def add_index_channel_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")
    args = message.text.split()
    if len(args) != 2:
        current = '\n'.join([f'`{ch}`' for ch in ALLOWED_INDEX_CHANNELS])
        return await message.reply(
            f"**📡 Allowed Index Channels:**\n{current}\n\n"
            f"**Usage:** `/addindexchannel -1001234567890`"
        )
    try:
        channel_id = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid channel ID.")
    if channel_id in ALLOWED_INDEX_CHANNELS:
        return await message.reply(f"✅ `{channel_id}` already in list.")
    ALLOWED_INDEX_CHANNELS.append(channel_id)
    await message.reply(f"✅ `{channel_id}` added to index channels!")


@StreamBot.on_message(filters.command("removeindexchannel") & filters.private)
async def remove_index_channel_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")
    args = message.text.split()
    if len(args) != 2:
        return await message.reply("**Usage:** `/removeindexchannel -1001234567890`")
    try:
        channel_id = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid channel ID.")
    if channel_id not in ALLOWED_INDEX_CHANNELS:
        return await message.reply(f"❌ `{channel_id}` not in list.")
    ALLOWED_INDEX_CHANNELS.remove(channel_id)
    await message.reply(f"✅ `{channel_id}` removed from index channels.")


@StreamBot.on_message(filters.command("indexchannels") & filters.private)
async def list_index_channels_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can view this.")
    current = '\n'.join([f'• `{ch}`' for ch in ALLOWED_INDEX_CHANNELS])
    await message.reply(
        f"**📡 Index Channels:**\n\n{current}\n\n"
        f"Total: `{len(ALLOWED_INDEX_CHANNELS)}` channels"
    )


# ─── /search COMMAND ──────────────────────────────────────

@StreamBot.on_message(filters.command("search") & filters.private)
async def search_cmd(client, message):
    args = message.text.split(None, 1)
    if len(args) < 2:
        total = await get_total_indexed()
        return await message.reply(
            f"**🔍 Search Files**\n\n"
            f"**Usage:** `/search Movie Name`\n\n"
            f"📦 **Total Indexed:** `{total}` files"
        )
    query = args[1].strip()
    if len(query) < 2:
        return await message.reply("❌ Query too short. Use at least 2 characters.")

    searching_msg = await message.reply(f"🔍 Searching for `{query}`...")
    results = await search_files(query, limit=10)

    if not results:
        return await searching_msg.edit(
            f"❌ **No results for:** `{query}`\n\nTry different keywords."
        )

    buttons = []
    for i, file in enumerate(results, 1):
        stream_link, download_link = build_links(file['msg_id'], file['file_name'])
        size = humanbytes(file['file_size']) if file['file_size'] else "Unknown"
        buttons.append([
            InlineKeyboardButton(
                f"🎬 {i}. {file['file_name'][:40]} [{size}]",
                callback_data=f"search_info_{file['msg_id']}"
            )
        ])
        buttons.append([
            InlineKeyboardButton("🖥 STREAM", url=stream_link),
            InlineKeyboardButton("📥 DOWNLOAD", url=download_link)
        ])

    await searching_msg.edit(
        f"🔍 **Results for:** `{query}`\n"
        f"📊 Found `{len(results)}` file(s)\n\n"
        f"👇 Select a file:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ─── SEARCH INFO CALLBACK ─────────────────────────────────

@StreamBot.on_callback_query(filters.regex(r"^search_info_(\d+)$"))
async def search_info_callback(client, callback: CallbackQuery):
    msg_id = int(callback.data.split("_")[2])
    doc = await files_col.find_one({'msg_id': msg_id})
    if not doc:
        return await callback.answer("File info not found.", show_alert=True)
    size = humanbytes(doc['file_size']) if doc['file_size'] else "Unknown"
    await callback.answer(
        f"📂 {doc['file_name']}\n📦 {size}",
        show_alert=True
    )


# ─── /indexstats ──────────────────────────────────────────

@StreamBot.on_message(filters.command("indexstats") & filters.private)
async def index_stats_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can view this.")
    total = await get_total_indexed()
    await message.reply(
        f"**📊 Index Statistics**\n\n"
        f"📦 **Total Files:** `{total}`\n"
        f"📡 **Channels:** `{len(ALLOWED_INDEX_CHANNELS)}`\n\n"
        + '\n'.join([f'• `{ch}`' for ch in ALLOWED_INDEX_CHANNELS])
    )


# ─── /deleteindex ─────────────────────────────────────────

@StreamBot.on_message(filters.command("deleteindex") & filters.private)
async def delete_index_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply("**Usage:** `/deleteindex File Name`")
    results = await search_files(args[1].strip(), limit=5)
    if not results:
        return await message.reply(f"❌ No files found matching `{args[1].strip()}`")
    buttons = [[
        InlineKeyboardButton(
            f"🗑 {f['file_name'][:40]}",
            callback_data=f"delfile_{f['file_id'][:20]}"
        )
    ] for f in results]
    await message.reply(
        f"Found `{len(results)}` file(s). Tap to delete:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@StreamBot.on_callback_query(filters.regex(r"^delfile_(.+)$"))
async def delete_file_callback(client, callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return await callback.answer("⛔ Unauthorized!", show_alert=True)
    partial_id = callback.data.split("_")[1]
    doc = await files_col.find_one({'file_id': {'$regex': f'^{partial_id}'}})
    if not doc:
        return await callback.answer("File not found.", show_alert=True)
    await files_col.delete_one({'file_id': doc['file_id']})
    await callback.answer("🗑 Deleted!", show_alert=True)
    await callback.message.edit_text(f"✅ Deleted: `{doc['file_name']}` from index.")
