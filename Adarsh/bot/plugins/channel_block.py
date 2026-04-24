from Adarsh.bot import StreamBot
from pyrogram import filters

OWNER_ID = 8202330446

# Add your allowed channel/group IDs here later
ALLOWED_CHATS = [
    # -1001234567890,  # My Movies Channel
    # -1009876543210,  # My Group
]

@StreamBot.on_chat_member_updated(filters.channel | filters.group)
async def bot_added_handler(client, chat_member_updated):
    try:
        chat = chat_member_updated.chat
        new_member = chat_member_updated.new_chat_member
        added_by = chat_member_updated.from_user

        # Check if it's the bot being added
        me = await client.get_me()
        if not new_member or new_member.user.id != me.id:
            return

        # Allow if added by owner OR chat is in allowed list
        if (added_by and added_by.id == OWNER_ID) or (chat.id in ALLOWED_CHATS):
            print(f"Authorized chat: {chat.title} ({chat.id})")
            return

        # Otherwise leave
        await client.send_message(
            chat.id,
            "⛔ **This bot is private!**\n\nOnly the owner can add this bot to channels/groups.\n\nLeaving now..."
        )
        await client.leave_chat(chat.id)
        print(f"Left unauthorized chat: {chat.title} ({chat.id})")

    except Exception as e:
        print(f"Error in channel block: {e}")
        try:
            await client.leave_chat(chat_member_updated.chat.id)
        except:
            pass
