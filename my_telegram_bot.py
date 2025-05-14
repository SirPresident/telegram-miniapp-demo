# my_telegram_bot.py (relevant changes)
import logging
import httpx
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ... (logging setup) ...
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BOT_TOKEN = "YOUR_HTTP_API_TOKEN_HERE" # Replace
MINI_APP_URL = "https://yourusername.github.io/your-repo-name/" # Replace
# !! URL for your Django backend's NEW note processing endpoint !!
DJANGO_PROCESS_NOTE_URL = "https://your-localtunnel-subdomain.loca.lt/api/process_note/" # Replace
# DJANGO_BOT_SECRET = "your_very_secret_shared_string" # For future security

timeout = httpx.Timeout(15.0, read=15.0) # Increased timeout slightly for Gemini processing
django_client = httpx.AsyncClient(timeout=timeout)

# ... (start_command, myid_command as before, but maybe update start_command text) ...
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    keyboard = [[
        InlineKeyboardButton(text="📊 View My Logs", web_app=WebAppInfo(url=MINI_APP_URL)) # Updated button text
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm your personal AI logger. "
        rf"Send me a note about your day, mood, health, diet, or activities, and I'll process it. "
        rf"Click the button below or use the menu button to view your logs.",
        reply_markup=reply_markup
    )

# This replaces the old save_note_message_handler
async def process_user_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: return

    message = update.message
    user = message.from_user
    note_text = message.text

    logger.info(f"Received note from {user.username or user.id} for AI processing: {note_text[:30]}")
    await message.reply_text("🤖 Processing your note with AI, please wait a moment...") # Acknowledge receipt

    payload = {
        "telegram_user_id": user.id,
        "telegram_username": user.username, # Optional, but can be useful
        "note_text": note_text
    }
    headers = {'Content-Type': 'application/json'} # Add 'X-Bot-Secret': DJANGO_BOT_SECRET later

    try:
        if "your-localtunnel-subdomain" in DJANGO_PROCESS_NOTE_URL:
             await message.reply_text("Config error processing note."); return

        response = await django_client.post(DJANGO_PROCESS_NOTE_URL, json=payload, headers=headers)
        response.raise_for_status()
        
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
        
        await message.reply_text("\n".join(reply_parts))

    except httpx.HTTPStatusError as e:
        error_detail = "Could not process note."
        try: error_detail = e.response.json().get("error", error_detail)
        except: pass
        logger.error(f"HTTP error processing note: {e.response.status_code} - {error_detail if e.response else str(e)}")
        await message.reply_text(f"⚠️ Error processing note: {error_detail}")
    except httpx.RequestError as e: # Covers network errors, timeouts
        logger.error(f"Request error processing note: {e}")
        await message.reply_text("⚠️ Network error: Could not connect to the AI processing server. Please try again later.")
    except Exception as e:
        logger.error(f"Unexpected error processing note: {e}", exc_info=True)
        await message.reply_text("⚠️ An unexpected error occurred while processing your note.")

# ... (error_handler as before) ...

def main() -> None:
    # ... (Update config checks for DJANGO_PROCESS_NOTE_URL) ...
    if any(val in BOT_TOKEN for val in ["YOUR_", "HERE"]) or \
       any(val in MINI_APP_URL for val in ["yourusername", "your-repo-name"]) or \
       any(val in DJANGO_PROCESS_NOTE_URL for val in ["your-localtunnel-subdomain"]): # Updated check
        logger.error("FATAL: BOT_TOKEN, MINI_APP_URL, or DJANGO_PROCESS_NOTE_URL not configured properly!")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("myid", myid_command)) # Keep if useful
    # This handler will now process notes using Gemini
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_note_handler))
    application.add_error_handler(error_handler)
    logger.info("AI Note Logger Bot starting...")
    # ... (application.run_polling() and finally block as before) ...
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        logger.info("Bot stopped.")

if __name__ == "__main__":
    main()