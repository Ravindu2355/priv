import os
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, BadRequest, FloodWait
from pyrogram.types import Message

# Environment variables for secure credentials
BOT_API_TOKEN = os.getenv("tk")
API_ID = int(os.getenv("apiid"))
API_HASH = os.getenv("apihash")

bot = Client("bot_client", bot_token=BOT_API_TOKEN, api_id=API_ID, api_hash=API_HASH)
user_client = None
session_name = "user_session"


async def login_user_client(phone_number: str, chat: Message):
    """
    Initiates the user client login process.
    """
    global user_client
    user_client = Client(session_name, api_id=API_ID, api_hash=API_HASH)

    try:
        async with user_client:
            await user_client.connect()
            await user_client.send_code_request(phone_number)
            await chat.reply("📩 Enter the OTP sent to your phone:")

            @bot.on_message(filters.text & filters.private)
            async def handle_otp(client, message: Message):
                otp = message.text
                try:
                    await user_client.sign_in(phone_number, otp)
                    await chat.reply("✅ Successfully logged in.")
                    bot.remove_handler(handle_otp)
                except SessionPasswordNeeded:
                    await chat.reply("🔐 2FA is enabled. Enter your password:")
                    bot.remove_handler(handle_otp)
                    bot.add_handler(handle_2fa)

            @bot.on_message(filters.text & filters.private)
            async def handle_2fa(client, message: Message):
                password = message.text
                try:
                    await user_client.check_password(password)
                    await chat.reply("✅ Successfully logged in with 2FA.")
                    bot.remove_handler(handle_2fa)
                except BadRequest as e:
                    await chat.reply(f"❌ Error during 2FA login: {e}")
                    bot.remove_handler(handle_2fa)

    except Exception as e:
        await chat.reply(f"❌ Error: {e}")


@bot.on_message(filters.command("login") & filters.private)
async def login_command(client, message: Message):
    try:
        phone_number = message.text.split(" ", 1)[1]
        await login_user_client(phone_number, message)
    except IndexError:
        await message.reply("❌ Please provide a phone number. Usage: `/login <phone_number>`")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")


@bot.on_message(filters.command("clone_channel") & filters.private)
async def clone_channel(client, message: Message):
    global user_client
    if not user_client:
        await message.reply("❌ User client not logged in. Use `/login` first.")
        return

    try:
        args = message.text.split(" ", 2)
        source_chat_id = args[1]
        destination_chat_id = args[2] if len(args) > 2 else message.chat.id
    except IndexError:
        await message.reply("❌ Usage: `/clone_channel <source_chat_id> [<destination_chat_id>]`")
        return

    download_dir = "./downloads"
    os.makedirs(download_dir, exist_ok=True)

    try:
        await message.reply(f"📥 Cloning videos from `{source_chat_id}` to `{destination_chat_id}`...")

        async with user_client:
            async for msg in user_client.get_chat_history(source_chat_id):
                if msg.video or (msg.document and "video" in msg.document.mime_type):
                    try:
                        file_path = await user_client.download_media(msg, file_name=download_dir)
                        caption = msg.caption or "Cloned via Bot"
                        await client.send_video(destination_chat_id, video=file_path, caption=caption, supports_streaming=True)
                        os.remove(file_path)
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                    except Exception as e:
                        await message.reply(f"❌ Error cloning message {msg.id}: {e}")

        await message.reply("✅ Cloning completed.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        if os.path.exists(download_dir):
            for file in os.listdir(download_dir):
                os.remove(os.path.join(download_dir, file))
            os.rmdir(download_dir)

@bot.on_message(filters.command("get_chats") & filters.private)
async def get_chats(client, message: Message):
    """
    Retrieves a list of all chats (with names and IDs) the user account is a member of.
    """
    global user_client
    if not user_client:
        await message.reply("❌ User client is not logged in. Use `/login` first.")
        return

    try:
        async with user_client:
            chats = []
            async for dialog in user_client.get_dialogs():
                chat_name = dialog.chat.title or dialog.chat.first_name or "Unnamed Chat"
                chats.append(f"📌 {chat_name} (ID: `{dialog.chat.id}`)")

            # Join chat list into text and split into smaller chunks if necessary
            chat_list = "\n".join(chats)
            if len(chat_list) >= 4096:
                # Save to a text file if the content is too large
                file_path = "./chats_list.txt"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(chat_list)

                await message.reply_document(
                    document=file_path,
                    caption="📄 Here's the list of all chats (too long for a single message)."
                )
                os.remove(file_path)  # Clean up the file after sending
            else:
                await message.reply(f"**Chats List:**\n{chat_list}")

    except Exception as e:
        await message.reply(f"❌ Error fetching chats: {e}")

if __name__ == "__main__":
    print("🤖 Bot is running...")
    bot.run()
