import logging
import httpx  # For making HTTP requests to Django backend
import json   # For constructing JSON payload
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging to see errors and bot activity
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BOT_TOKEN = "8015169379:AAE13t1c1123g2qgydVf3za2y3ZmINMw1kc"
MINI_APP_URL = "https://sirpresident.github.io/telegram-miniapp-demo/"
# !! URL for your Django backend's new endpoint !!
DJANGO_SAVE_MESSAGE_URL = "https://finarfin-bot-subdomain.loca.lt/api/save_message/"
# !! A shared secret between bot and Django backend for security (RECOMMENDED) !!
# DJANGO_BOT_SECRET = "your_very_secret_shared_string"

# --- HTTP Client for Django ---
# Create a persistent client for better performance
# Configure timeout (e.g., 10 seconds for connect and read)
timeout = httpx.Timeout(10.0, read=10.0)
django_client = httpx.AsyncClient(timeout=timeout)

# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Sends a welcome message and an inline button to launch the Mini App
    when the /start command is issued.
    """
    user = update.effective_user
    keyboard = [[
        InlineKeyboardButton(
            text="🚀 Open My Status App",
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm your friendly status bot. "
        rf"Send me any message to save it as a note. "
        rf"Click the button below or use the menu button to open the status Mini App. "
        rf"You can also type  to see your Telegram User ID.",
        reply_markup=reply_markup
    )

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the user their Telegram ID."""
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram User ID is: {user_id}")

# --- MESSAGE HANDLER FOR SAVING NOTES ---
async def save_note_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles non-command text messages to save them as notes."""
    if not update.message or not update.message.text:
        return  # Should not happen with TEXT filter, but good practice

    message = update.message
    user = message.from_user

    logger.info(f"Received message from {user.username or user.id}: {message.text[:30]}")

    payload = {
        "message_id": message.message_id,
        "user_id": user.id,
        "username": user.username,  # Can be None if user has no username
        "text": message.text
    }

    headers = {
        'Content-Type': 'application/json',
        # 'X-Bot-Secret': DJANGO_BOT_SECRET # Add this if you implement secret key auth
    }

    try:
        # Make sure DJANGO_SAVE_MESSAGE_URL is correctly configured
        if "your-localtunnel-subdomain" in DJANGO_SAVE_MESSAGE_URL:  # Basic check
            logger.error("DJANGO_SAVE_MESSAGE_URL is not configured correctly!")
            await message.reply_text("Sorry, there's a configuration issue with saving notes. Please contact admin.")
            return

        response = await django_client.post(DJANGO_SAVE_MESSAGE_URL, json=payload, headers=headers)
        response.raise_for_status()  # Raises an exception for 4XX/5XX responses

        response_data = response.json()
        logger.info(f"Django response for save_message: {response_data}")
        await message.reply_text(f"📝 Note saved! ({response_data.get('message', 'Done')})")

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error saving note to Django: {e.response.status_code} - {e.response.text}")
        try:
            error_detail = e.response.json().get("error", "Could not save note.")
        except:
            error_detail = "Could not save note due to a server error."
        await message.reply_text(f"⚠️ Error saving note: {error_detail}")
    except httpx.RequestError as e:
        logger.error(f"Request error saving note to Django: {e}")
        await message.reply_text("⚠️ Network error: Could not connect to the note server. Please try again later.")
    except Exception as e:
        logger.error(f"Unexpected error saving note: {e}", exc_info=True)
        await message.reply_text("⚠️ An unexpected error occurred while saving your note.")

# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

# --- MAIN BOT LOGIC ---
def main() -> None:
    """Start the bot."""
    if BOT_TOKEN == "YOUR_HTTP_API_TOKEN_HERE" or not BOT_TOKEN:
        logger.error("FATAL: Please replace YOUR_HTTP_API_TOKEN_HERE with your actual bot token in the script!")
        return
    if MINI_APP_URL == "https://yourusername.github.io/tma-status-app/" or not MINI_APP_URL:
        logger.error("FATAL: Please replace MINI_APP_URL with your actual Mini App URL in the script!")
        return
    if "your-localtunnel-subdomain" in DJANGO_SAVE_MESSAGE_URL:
        logger.error("FATAL: DJANGO_SAVE_MESSAGE_URL is not configured. Please set it.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("myid", myid_command))

    # Add the new message handler for saving notes
    # This will handle any text message that isn't a command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_note_message_handler))

    application.add_error_handler(error_handler)
    logger.info("Bot is starting with note saving capability...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"An error occurred during polling: {e}", exc_info=True)
    finally:
        logger.info("Bot has stopped.")
        # Gracefully close the httpx client when the application stops
        # This needs to be done in an async context if main were async,
        # or use atexit, or manage the client's lifecycle with application.initialize/shutdown
        # For simplicity here, we're not explicitly closing it on Ctrl+C, but in a robust app, you would.

if __name__ == "__main__":
    main()

# To properly close the httpx.AsyncClient, you might consider this structure:
# async def actual_main():
#     # ... application setup ...
#     try:
#         await application.initialize() # Initialize application (and its internal components)
#         await application.start()      # Start bot components
#         await application.updater.start_polling(allowed_updates=Update.ALL_TYPES) # Start polling
#         # Keep it running, e.g., with an asyncio Event or just let it run
#         while True:
#             await asyncio.sleep(3600) # Or some other way to keep alive
#     except (KeyboardInterrupt, SystemExit):
#         logger.info("Bot stopping on interrupt...")
#     except Exception as e:
#         logger.error(f"Critical error in bot's main loop: {e}", exc_info=True)
#     finally:
#         if application.updater and application.updater.running:
#             await application.updater.stop()
#         await application.stop()
#         await application.shutdown() # Shutdown application (and its internal components)
#         await django_client.aclose() # Close the httpx client
#         logger.info("Bot fully stopped and client closed.")

# if __name__ == "__main__":
#     # If using the async main structure:
#     # import asyncio
#     # try:
#     #     asyncio.run(actual_main())
#     # except KeyboardInterrupt:
#     #     logger.info("Bot shutdown by user (KeyboardInterrupt in asyncio.run).")
#     main() # Sticking to the simpler main for now.