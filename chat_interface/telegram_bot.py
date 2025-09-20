import logging
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get the token from the user
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your bot's token

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text("Hi! I am your AI Sports Coach. How can I help you today?")

from app.agents.coach_agent import app as coach_app

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user's message."""
    # Here you would integrate with the LangGraph agent
    # For now, we just echo the message
    inputs = {"messages": [update.message.text]}
    response = None
    for output in coach_app.stream(inputs):
        response = output
    
    agent_response = response.get("agent", {}).get("messages", [])
    if agent_response:
        await update.message.reply_text(agent_response[-1])
    else:
        await update.message.reply_text("Sorry, I could not process your request.")

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
