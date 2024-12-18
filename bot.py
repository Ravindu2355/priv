import asyncio
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, BadRequest
from pyrogram.types import Message

# Bot Client Configuration
BOT_API_TOKEN = "YOUR_BOT_TOKEN"  # Get this from @BotFather
API_ID = "YOUR_API_ID"           # Get this from https://my.telegram.org/apps
API_HASH = "YOUR_API_HASH"       # Get this from https://my.telegram.org/apps

# Bot Client (used to issue commands)
bot = Client("bot_client", bot_token=BOT_API_TOKEN, api_id=API_ID, api_hash=API_HASH)

# User Client (for login and channel cloning)
user_client = None
session_name = "user_session"  # Session name for the user client


async def start_user_client(phone_number: str, chat: Message):
    """
    Initiates user client login based on the phone number provided by the bot command.
    """
    global user_client
    try:
        user_client = Client(session_name, api_id=API_ID, api_hash=API_HASH)

        async with user_client:
            # Send login code to the phone number
            await user_client.connect()
            await user_client.send_code(phone_number)

            await chat.reply("📩 Enter the OTP sent to your phone:")

            @bot.on_message(filters.text & filters.private)
            async def handle_otp(client, message: Message):
                otp = message.text
                try:
                    # Attempt to sign in
                    await user_client.sign_in(phone_number, otp)
                    await chat.reply("✅ Successfully logged in as a user.")
                    await bot.remove_handler(*bot.handlers[filters.text & filters.private])
                except SessionPasswordNeeded:
                    await chat.reply("🔐 This account has 2FA enabled. Please enter the password:")
                except BadRequest as e:
                    await chat.reply(f"❌ Error during login: {e}")

            # Handle 2FA password
            @bot.on_message(filters.text & filters.private)
            async def handle_2fa(client, message: Message):
                password = message.text
                try:
                    await user_client.check_password(password)
                    await chat.reply("✅ Successfully logged in with 2FA.")
                    await bot.remove_handler(*bot.handlers[filters.text & filters.private])
                except BadRequest as e:
                    await chat.reply(f"❌ Error during 2FA login: {e}")

    except Exception as e:
        await chat.reply(f"❌ Error initiating login: {e}")


@bot.on_message(filters.command("login") & filters.private)
async def login_command(client, message: Message):
    """
    Handles the /login command to start the user client login process.
    """
    try:
        phone_number = message.text.split(" ", 1)[1]  # Extract the phone number
        await message.reply("📞 Starting login process...")
        await start_user_client(phone_number, message)
    except IndexError:
        await message.reply("❌ Please provide a phone number. Usage: `/login <phone_number>`")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@bot.on_message(filters.command("clone_channel") & filters.private)
async def clone_channel(client, message: Message):
    """
    Clones videos from a source channel to a destination chat.
    Usage: /clone_channel <source_chat_id> [<destination_chat_id>]
    """
    global user_client
    if not user_client:
        await message.reply("❌ User client is not logged in. Use `/login` first.")
        return

    # Parse command arguments
    try:
        args = message.text.split(" ", 2)
        source_chat_id = args[1]  # Required
        destination_chat_id = args[2] if len(args) > 2 else message.chat.id  # Optional
    except IndexError:
        await message.reply("❌ Please provide the source channel ID. Usage: `/clone_channel <source_chat_id> [<destination_chat_id>]`")
        return

    # Create a folder for downloaded media
    download_dir = "./downloads"
    os.makedirs(download_dir, exist_ok=True)

    try:
        await message.reply(f"📥 Starting to clone videos from `{source_chat_id}` to `{destination_chat_id}`...")

        async with user_client:
            async for msg in user_client.get_chat_history(source_chat_id):
                # Process only video or document media
                if msg.video or (msg.document and "video" in msg.document.mime_type):
                    try:
                        # Download the media using the user client
                        await message.reply(f"📥 Downloading video message {msg.id}...")
                        file_path = await user_client.download_media(msg, file_name=download_dir)

                        # Upload the media using the bot client
                        await message.reply(f"📤 Uploading video message {msg.id}...")
                        caption = msg.caption or "Cloned via Bot"
                        await client.send_video(
                            chat_id=destination_chat_id,
                            video=file_path,
                            caption=caption,
                            supports_streaming=True
                        )

                        # Clean up the downloaded file
                        os.remove(file_path)

                    except FloodWait as e:
                        # Handle flood wait errors
                        await message.reply(f"⚠️ FloodWait detected: Waiting for {e.value} seconds...")
                        await asyncio.sleep(e.value)
                    except Exception as e:
                        await message.reply(f"❌ Error processing message {msg.id}: {e}")

        await message.reply("✅ Cloning completed successfully!")
    except Exception as e:
        await message.reply(f"❌ An error occurred: {e}")
    finally:
        # Clean up any remaining downloaded files
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
                chat_name = dialog.chat.title or dialog.chat.first_name
                chats.append(f"📌 {chat_name} (ID: `{dialog.chat.id}`)")

            chat_list = "\n".join(chats)
            await message.reply(f"**Chats List:**\n{chat_list}")
    except Exception as e:
        await message.reply(f"❌ Error fetching chats: {e}")


if __name__ == "__main__":
    print("🤖 Bot is running...")
    bot.run()
