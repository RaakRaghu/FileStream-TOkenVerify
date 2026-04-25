import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from urllib.parse import quote_plus
from Adarsh.bot import StreamBot
from Adarsh.utils.file_properties import get_name, get_hash, get_media_file_size
from Adarsh.utils.human_readable import humanbytes
from Adarsh.vars import Var

OWNER_ID = 8202330446
DATABASE_URL = os.environ.get('DATABASE_URL', 'mongodb+srv://raakraghu:raakraghu@streamingrr.ym8sc0p.mongodb.net/?appName=streamingrr')

# Channels to index
INDEX_CHANNEL   = -1001782965073
LOGS_CHANNEL    = -1003189494068
FQDN            = os.environ.get('FQDN', '144.24.147.39:8099')
BASE_URL        = f"http://{FQDN}/"

# Extra channels allowed to share/index files
ALLOWED_INDEX_CHANNELS = [
    INDEX_CHANNEL,
    LOGS_CHANNEL,
    # Add more channel IDs here later
]

# DB
_client = AsyncIOMotorClient(DATABASE_URL)
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
    # All keywords must appear in file name
    regex = ''.join([f'(?=.*{kw})' for kw in keywords])
    cursor = files_col.find(
        {'file_name_lower': {'$regex': regex}}
    ).limit(limit)
    return await cursor.to_list(length=limit)


async def get_total_indexed():
    return await files_col.count_documents({})


async def delete_file(file_id):
    await files_col.delete_one({'file_id': file_id})


# ─── BUILD LINKS ──────────────────────────────────────────

def build_links(msg_id, file_name):
    encoded = quote_plus(file_name)
    stream = f"{BASE_URL}watch/{msg_id}/{encoded}"
    download = f"{BASE_URL}{msg_id}/{encoded}"
    return stream, download


# ─── AUTO INDEX — listen to index & allowed channels ──────

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
        # Forward to BIN_CHANNEL to get a permanent msg_id for links
        log_msg = await message.forward(chat_id=Var.BIN_CHANNEL)
        file_name = get_name(log_msg)
        file_size = get_media_file_size(message)
        file_id = (
            message.document.file_id if message.document else
            message.video.file_id if message.video else
            message.audio.file_id if message.audio else
            message.photo.file_id if message.photo else None
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
        print(f"Auto indexed: {file_name}")
    except Exception as e:
        print(f"Auto index error: {e}")


# ─── MANUAL INDEX COMMAND ─────────────────────────────────

@StreamBot.on_message(filters.command("index") & filters.private)
async def manual_index_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can run indexing.")

    args = message.text.split()
    channel_id = int(args[1]) if len(args) > 1 else INDEX_CHANNEL

    status_msg = await message.reply(
        f"🔄 **Starting Manual Index...**\n\n"
        f"Channel: `{channel_id}`\n"
        f"Please wait, this may take a while..."
    )

    count = 0
    errors = 0

    try:
        async for msg in client.get_chat_history(channel_id):
            if msg.document or msg.video or msg.audio or msg.photo:
                try:
                    log_msg = await msg.forward(chat_id=Var.BIN_CHANNEL)
                    file_name = get_name(log_msg)
                    file_size = get_media_file_size(msg)
                    file_id = (
                        msg.document.file_id if msg.document else
                        msg.video.file_id if msg.video else
                        msg.audio.file_id if msg.audio else
                        msg.photo.file_id if msg.photo else None
                    )
                    if file_id:
                        await save_file(
                            file_id=file_id,
                            file_name=file_name,
                            file_size=file_size,
                            msg_id=log_msg.id,
                            channel_id=channel_id
                        )
                        count += 1
                        if count % 20 == 0:
                            await status_msg.edit(
                                f"🔄 **Indexing...**\n\n"
                                f"✅ Indexed: `{count}`\n"
                                f"❌ Errors: `{errors}`"
                            )
                        await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as ex:
                    errors += 1
                    print(f"Index error: {ex}")
    except Exception as e:
        await status_msg.edit(f"❌ Error: `{e}`")
        return

    total = await get_total_indexed()
    await status_msg.edit(
        f"✅ **Indexing Complete!**\n\n"
        f"✅ Indexed: `{count}`\n"
        f"❌ Errors: `{errors}`\n"
        f"📦 Total in DB: `{total}`"
    )


# ─── ADD ALLOWED INDEX CHANNEL ────────────────────────────

@StreamBot.on_message(filters.command("addindexchannel") & filters.private)
async def add_index_channel_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")

    args = message.text.split()
    if len(args) != 2:
        current = '\n'.join([f'`{ch}`' for ch in ALLOWED_INDEX_CHANNELS])
        return await message.reply(
            f"**📡 Allowed Index Channels:**\n\n{current}\n\n"
            f"**Usage:** `/addindexchannel CHANNEL_ID`\n"
            f"Example: `/addindexchannel -1001234567890`"
        )

    try:
        channel_id = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid channel ID.")

    if channel_id in ALLOWED_INDEX_CHANNELS:
        return await message.reply(f"✅ Channel `{channel_id}` is already in the list.")

    ALLOWED_INDEX_CHANNELS.append(channel_id)
    await message.reply(
        f"✅ Channel `{channel_id}` added to index list!\n\n"
        f"Files posted in this channel will now be auto-indexed."
    )


@StreamBot.on_message(filters.command("removeindexchannel") & filters.private)
async def remove_index_channel_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")

    args = message.text.split()
    if len(args) != 2:
        return await message.reply("**Usage:** `/removeindexchannel CHANNEL_ID`")

    try:
        channel_id = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid channel ID.")

    if channel_id not in ALLOWED_INDEX_CHANNELS:
        return await message.reply(f"❌ Channel `{channel_id}` is not in the list.")

    ALLOWED_INDEX_CHANNELS.remove(channel_id)
    await message.reply(f"✅ Channel `{channel_id}` removed from index list.")


@StreamBot.on_message(filters.command("indexchannels") & filters.private)
async def list_index_channels_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can view this.")

    current = '\n'.join([f'• `{ch}`' for ch in ALLOWED_INDEX_CHANNELS])
    await message.reply(
        f"**📡 Currently Indexed Channels:**\n\n{current}\n\n"
        f"Total: `{len(ALLOWED_INDEX_CHANNELS)}` channels"
    )


# ─── SEARCH COMMAND ───────────────────────────────────────

@StreamBot.on_message(filters.command("search") & filters.private)
async def search_cmd(client, message):
    args = message.text.split(None, 1)
    if len(args) < 2:
        total = await get_total_indexed()
        return await message.reply(
            f"**🔍 Search Files**\n\n"
            f"**Usage:** `/search Movie Name`\n\n"
            f"**Examples:**\n"
            f"`/search Pushpa 2`\n"
            f"`/search Avengers`\n"
            f"`/search KGF Hindi`\n\n"
            f"📦 **Total Indexed Files:** `{total}`"
        )

    query = args[1].strip()
    if len(query) < 2:
        return await message.reply("❌ Search query too short. Use at least 2 characters.")

    searching_msg = await message.reply(f"🔍 Searching for `{query}`...")

    results = await search_files(query, limit=10)

    if not results:
        await searching_msg.edit(
            f"❌ **No results found for:** `{query}`\n\n"
            f"Try different keywords or check spelling."
        )
        return

    # Build inline buttons — 1 result per row with stream+download
    buttons = []
    for i, file in enumerate(results, 1):
        stream_link, download_link = build_links(file['msg_id'], file['file_name'])
        size = humanbytes(file['file_size']) if file['file_size'] else "Unknown"

        # File name button (non-clickable label)
        buttons.append([
            InlineKeyboardButton(
                f"🎬 {i}. {file['file_name'][:40]} [{size}]",
                callback_data=f"search_info_{file['msg_id']}"
            )
        ])
        # Stream + Download buttons
        buttons.append([
            InlineKeyboardButton("🖥 STREAM", url=stream_link),
            InlineKeyboardButton("📥 DOWNLOAD", url=download_link)
        ])

    await searching_msg.edit(
        f"🔍 **Results for:** `{query}`\n"
        f"📊 Found `{len(results)}` results\n\n"
        f"👇 Select a file below:",
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
        f"📂 {doc['file_name']}\n📦 Size: {size}",
        show_alert=True
    )


# ─── INDEX STATS ──────────────────────────────────────────

@StreamBot.on_message(filters.command("indexstats") & filters.private)
async def index_stats_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can view this.")

    total = await get_total_indexed()
    channels = len(ALLOWED_INDEX_CHANNELS)

    await message.reply(
        f"**📊 Index Statistics**\n\n"
        f"📦 **Total Indexed Files:** `{total}`\n"
        f"📡 **Indexed Channels:** `{channels}`\n\n"
        f"**Channels:**\n" +
        '\n'.join([f'• `{ch}`' for ch in ALLOWED_INDEX_CHANNELS])
    )


# ─── DELETE FROM INDEX ────────────────────────────────────

@StreamBot.on_message(filters.command("deleteindex") & filters.private)
async def delete_index_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Only owner can do this.")

    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply(
            "**Usage:** `/deleteindex FILE_NAME`\n\n"
            "Example: `/deleteindex Pushpa 2 Hindi`"
        )

    query = args[1].strip()
    results = await search_files(query, limit=5)

    if not results:
        return await message.reply(f"❌ No files found matching `{query}`")

    buttons = []
    for file in results:
        buttons.append([
            InlineKeyboardButton(
                f"🗑 {file['file_name'][:40]}",
                callback_data=f"delfile_{file['file_id'][:20]}"
            )
        ])

    await message.reply(
        f"Found {len(results)} files. Tap to delete from index:",
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
    await callback.answer("🗑 Deleted from index!", show_alert=True)
    await callback.message.edit_text(f"✅ Deleted: `{doc['file_name']}` from index.")
