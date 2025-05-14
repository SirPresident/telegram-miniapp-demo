import logging
import httpx # For making HTTP requests to Django backend
import json # For constructing JSON payload
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo # Ensure WebAppInfo is imported
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging to see errors and bot activity
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# !! IMPORTANT: Replace these with YOUR actual values !!
BOT_TOKEN = "8015169379:AAE13t1c1123g2qgydVf3za2y3ZmINMw1kc"
MINI_APP_URL = "https://sirpresident.github.io/note-app-1/" # e.g., tma-status-app
DJANGO_PROCESS_NOTE_URL = "https://finarfin-bot-subdomain.loca.lt/api/process_note/" # e.g., finarfin-bot-subdomain
# DJANGO_BOT_SECRET = "your_very_secret_shared_string" # For future security: a shared secret

# --- HTTP Client for Django ---
# Configure timeout (e.g., 15 seconds for connect and read, as Gemini can take time)
timeout = httpx.Timeout(15.0, connect=15.0, read=15.0)
django_client = httpx.AsyncClient(timeout=timeout)


# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Sends a welcome message and an inline button to launch the Mini App
    when the /start command is issued.
    """
    user = update.effective_user

    # Create the inline keyboard button
    keyboard = [[
        InlineKeyboardButton(
            text="📊 View My Logs", # Updated button text
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the welcome message with the button
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm your personal AI logger. "
        rf"Send me a note about your day, mood, health, diet, or activities, and I'll process it. "
        rf"Click the button below or use the menu button to view your logs. "
        rf"You can also type /myid to see your Telegram User ID.",
        reply_markup=reply_markup
    )

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the user their Telegram ID."""
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram User ID is: {user_id}")


# --- MESSAGE HANDLER FOR PROCESSING NOTES ---
async def process_user_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles non-command text messages to process them with AI via Django backend."""
    if not update.message or not update.message.text: # Should not happen with TEXT filter
        return

    message = update.message
    user = message.from_user
    note_text = message.text

    logger.info(f"Received note from {user.username or user.id} for AI processing: {note_text[:30]}")
    # Acknowledge receipt and indicate processing
    try:
        processing_msg = await message.reply_text("🤖 Processing your note with AI, please wait a moment...")
    except Exception as e:
        logger.warning(f"Could not send 'processing' message: {e}")
        processing_msg = None # Continue even if this fails

    payload = {
        "telegram_user_id": user.id,
        "telegram_username": user.username, # Can be None
        "note_text": note_text
    }
    headers = {
        'Content-Type': 'application/json',
        # 'X-Bot-Secret': DJANGO_BOT_SECRET # Add this header if you implement secret key auth in Django
    }

    final_reply_text = "⚠️ An unexpected error occurred while processing your note." # Default error

    try:
        # Basic check for placeholder URL
        if "your-localtunnel-subdomain" in DJANGO_PROCESS_NOTE_URL or \
           "YOUR_HTTP_API_TOKEN_HERE" in BOT_TOKEN or \
           "yourusername" in MINI_APP_URL :
            logger.error("CRITICAL: Bot configuration (TOKEN, MINI_APP_URL, or DJANGO_PROCESS_NOTE_URL) is not set correctly!")
            final_reply_text = "Sorry, there's a configuration issue on my end. Please contact the admin."
            return # Exit early

        response = await django_client.post(DJANGO_PROCESS_NOTE_URL, json=payload, headers=headers)
        response.raise_for_status()  # Raises an exception for 4XX/5XX responses

        response_data = response.json()
        logger.info(f"Django response for process_note: {response_data}")

        # Construct a more informative reply based on processed data
        reply_parts = ["📝 Note processed!"]
        if response_data.get('mood'):
            reply_parts.append(f"Mood: {response_data.get('mood')}")
        if response_data.get('health_count', 0) > 0:
            reply_parts.append(f"{response_data.get('health_count')} health item(s) logged.")
        if response_data.get('activity_count', 0) > 0:
            reply_parts.append(f"{response_data.get('activity_count')} activit(y/ies) logged.")
        
        final_reply_text = "\n".join(reply_parts)

    except httpx.HTTPStatusError as e: # Handles 4xx/5xx errors from Django
        error_detail = "Could not process your note due to a server issue."
        try:
            # Try to get a more specific error from Django's JSON response
            error_detail = e.response.json().get("error", error_detail)
        except (json.JSONDecodeError, AttributeError): # If response isn't JSON or no 'error' key
            pass # Keep the generic error_detail
        logger.error(f"HTTP error processing note via Django: {e.response.status_code} - Response: {e.response.text}")
        final_reply_text = f"⚠️ Error processing note: {error_detail}"
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error connecting to Django for note processing: {e}")
        final_reply_text = "⚠️ The processing server took too long to respond. Please try sending your note again later."
    except httpx.RequestError as e: # Covers other network errors (connection refused, DNS failure)
        logger.error(f"Network request error connecting to Django for note processing: {e}")
        final_reply_text = "⚠️ Network error: Could not connect to the AI processing server. Please try again later."
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"Unexpected error in process_user_note_handler: {e}", exc_info=True)
        # final_reply_text is already set to a generic error
    finally:
        if processing_msg:
            try:
                await context.bot.edit_message_text(chat_id=message.chat_id, message_id=processing_msg.message_id, text=final_reply_text)
            except Exception as edit_e:
                logger.warning(f"Could not edit 'processing' message, sending new reply: {edit_e}")
                await message.reply_text(final_reply_text) # Fallback to new message if edit fails
        else:
            await message.reply_text(final_reply_text)


# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)


# --- MAIN BOT LOGIC ---
def main() -> None:
    """Start the bot."""
    # More robust configuration check
    if any(val in BOT_TOKEN for val in ["YOUR_", "HERE", "TOKEN"]) or not BOT_TOKEN or \
       any(val in MINI_APP_URL for val in ["yourusername", "your-repo-name", "URL"]) or not MINI_APP_URL or \
       any(val in DJANGO_PROCESS_NOTE_URL for val in ["your-localtunnel-subdomain", "URL"]) or not DJANGO_PROCESS_NOTE_URL:
        logger.error("FATAL: BOT_TOKEN, MINI_APP_URL, or DJANGO_PROCESS_NOTE_URL is not configured properly in the script! Please check the constants at the top.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("myid", myid_command)) # Ensure this is correctly added

    # Register a message handler for processing notes
    # This will handle any text message that isn't a command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_note_handler))

    # Register the error handler
    application.add_error_handler(error_handler)

    logger.info("AI Note Logger Bot is starting...")

    # Run the bot until the user presses Ctrl-C
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"An error occurred during polling: {e}", exc_info=True)
    finally:
        logger.info("Bot has stopped.")
        # To properly close the httpx.AsyncClient when using run_polling,
        # it's usually managed by the Application's lifecycle if it were to use it internally,
        # or you'd need a more complex async main structure to use `await django_client.aclose()`.
        # For this script's simplicity, we are not explicitly closing it on Ctrl+C here.

if __name__ == "__main__":
    main()