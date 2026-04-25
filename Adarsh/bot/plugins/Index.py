# (c) adarsh-goel | auto-index on forward by RaakRaghu
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from Adarsh.bot import StreamBot
from Adarsh.database.files_db import db
from Adarsh.vars import Var


def is_media(message: Message):
    return message.document or message.video or message.audio


def extract_media(message: Message):
    if message.document:
        return message.document, "document"
    elif message.video:
        return message.video, "video"
    elif message.audio:
        return message.audio, "audio"
    return None, None


# ── Owner forwards a file → index it + return stream link ──────────────────
@StreamBot.on_message(
    filters.private
    & filters.forwarded
    & filters.user(list(Var.OWNER_ID))
)
async def owner_forward_index(client: Client, message: Message):
    if not is_media(message):
        return  # forwarded text/sticker etc — ignore

    media, media_type = extract_media(message)
    file_name = getattr(media, "file_name", None) or f"{media_type}_{message.id}"

    file_doc = {
        "file_id": media.file_id,
        "file_ref": media.file_reference,
        "file_name": file_name,
        "file_size": media.file_size,
        "file_type": media_type,
        "mime_type": getattr(media, "mime_type", ""),
        "caption": str(message.caption) if message.caption else "",
    }

    is_new = await db.save_file(file_doc)
    size_mb = round(media.file_size / (1024 * 1024), 2) if media.file_size else 0
    stream_link = f"{Var.URL}watch/{media.file_id}"
    download_link = f"{Var.URL}{media.file_id}"

    status = "🆕 **Indexed & saved!**" if is_new else "🔁 **Already in DB.**"

    await message.reply(
        f"{status}\n\n"
        f"📄 **{file_name}**\n"
        f"📦 Size: `{size_mb} MB`\n\n"
        f"🔗 **Stream:** {stream_link}\n"
        f"⬇️ **Download:** {download_link}",
        disable_web_page_preview=True
    )


# ── Anyone else sends a file → normal stream link only, no indexing ─────────
@StreamBot.on_message(
    filters.private
    & ~filters.user(list(Var.OWNER_ID))
)
async def user_file_stream(client: Client, message: Message):
    if not is_media(message):
        return

    media, media_type = extract_media(message)
    file_name = getattr(media, "file_name", None) or f"{media_type}_{message.id}"
    size_mb = round(media.file_size / (1024 * 1024), 2) if media.file_size else 0
    stream_link = f"{Var.URL}watch/{media.file_id}"
    download_link = f"{Var.URL}{media.file_id}"

    await message.reply(
        f"📄 **{file_name}**\n"
        f"📦 Size: `{size_mb} MB`\n\n"
        f"🔗 **Stream:** {stream_link}\n"
        f"⬇️ **Download:** {download_link}",
        disable_web_page_preview=True
    )
