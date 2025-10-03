import logging
import sys
import os
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Validate environment before importing other modules
from app.config import settings

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.conversational_agent import create_conversational_agent
from app.agents.coach_agent import login_app
from app.tools.profiling_tools import analyze_and_summarize_user_activities
from app.tools.garmin_tools import get_activities
from app.tools.user_tools import delete_user_data

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Use validated token from settings
TOKEN = settings.telegram_bot_token

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    if not update.message:
        return
    await update.message.reply_text(
        "Hallo! Ik ben je AI Sportcoach. Log in met je Garmin account om te beginnen:\n\n"
        "/login <email> <password>\n\n"
        "⚠️ Let op: Je login bericht wordt automatisch verwijderd voor beveiliging.\n\n"
        "Andere commando's:\n"
        "/delete_my_data - Verwijder al je gegevens"
    )

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Login to Garmin."""
    if not update.message:
        return
    user_id = update.message.from_user.id

    try:
        # Delete the message containing credentials immediately for security
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete login message: {e}")

    try:
        # The command is /login <email> <password>, so we split the message and take the last two parts
        args = update.message.text.split()
        if len(args) != 3:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Gebruik het formaat: /login <email> <wachtwoord>\n\n⚠️ Let op: Je bericht wordt automatisch verwijderd voor beveiliging."
            )
            return

        email = args[1]
        password = args[2]

        inputs = {"user_id": user_id, "messages": [f"{email} {password}"]}
        response = login_app.invoke(inputs)

        # Check if login was successful
        if "Bedankt!" in response["messages"][-1]:
            context.user_data['logged_in'] = True
            keyboard = [[InlineKeyboardButton("Analyseer mijn profiel", callback_data='create_profile')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response["messages"][-1] + "\n\nWil je dat ik een profiel voor je aanmaak op basis van je activiteiten?",
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response["messages"][-1]
            )

    except Exception as e:
        logger.error(f"Error in /login: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Er is een fout opgetreden bij het inloggen."
        )

async def delete_my_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask for confirmation to delete user data."""
    if not update.message:
        return
    keyboard = [
        [InlineKeyboardButton("Ja, verwijder alles", callback_data='delete_data_confirm')],
        [InlineKeyboardButton("Nee, annuleer", callback_data='delete_data_cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Weet je zeker dat je al je gegevens wilt verwijderen? Dit kan niet ongedaan gemaakt worden.", reply_markup=reply_markup)

async def start_profiling(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches activities, analyzes them, and sends the summary."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    await query.edit_message_text(text="Ik ben je profiel aan het aanmaken, een ogenblik geduld...")

    # Fetch activities for the last 3 months
    today = datetime.date.today()
    three_months_ago = today - datetime.timedelta(days=90)
    get_activities(user_id, three_months_ago.isoformat(), today.isoformat())

    # Analyze and summarize
    summary = analyze_and_summarize_user_activities(user_id)
    await query.edit_message_text(text=summary)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    if query.data == 'create_profile':
        await start_profiling(update, context)
    elif query.data == 'delete_data_confirm':
        user_id = query.from_user.id
        delete_user_data(user_id)
        context.user_data['logged_in'] = False
        await query.edit_message_text(text="Al je gegevens zijn verwijderd.")
    elif query.data == 'delete_data_cancel':
        await query.edit_message_text(text="Verwijdering geannuleerd.")

async def conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle conversation."""
    if not update.message:
        return
    if not context.user_data.get('logged_in'):
        await update.message.reply_text("Gelieve eerst in te loggen met het /login commando.")
        return

    user_id = update.message.from_user.id
    message = update.message.text
    
    if "chat_history" not in context.user_data:
        context.user_data["chat_history"] = []
        
    agent_executor = create_conversational_agent(user_id)
    
    result = agent_executor.invoke({"input": message, "chat_history": context.user_data["chat_history"]})
    
    context.user_data["chat_history"].append(HumanMessage(content=message))
    context.user_data["chat_history"].append(AIMessage(content=result["output"]))
    
    fit_file_path = None
    for action, observation in result.get("intermediate_steps", []):
        if action.tool == "create_fit_file":
            fit_file_path = observation
            break
            
    if fit_file_path:
        await update.message.reply_document(document=open(fit_file_path, 'rb'), filename="workout.fit")
        os.remove(fit_file_path)
        await update.message.reply_text(result["output"])
    else:
        await update.message.reply_text(result["output"])

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("delete_my_data", delete_my_data_command))
    application.add_handler(CallbackQueryHandler(button))
    
    # Add conversation handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
