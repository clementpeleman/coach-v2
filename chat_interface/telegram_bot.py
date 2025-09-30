import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.conversational_agent import create_conversational_agent
from app.agents.coach_agent import login_app
from app.tools.profiling_tools import analyze_and_summarize_user_activities

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get the token from the environment variable
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hallo! Ik ben je AI Sportcoach. Log in met je Garmin account om te beginnen:\n\n"
        "/login <email> <password>\n\n"
        "Je kunt ook je profiel aanmaken met /profile"
    )

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Login to Garmin."""
    user_id = update.message.from_user.id
    try:
        # The command is /login <email> <password>, so we split the message and take the last two parts
        args = update.message.text.split()
        if len(args) != 3:
            await update.message.reply_text("Gebruik het formaat: /login <email> <wachtwoord>")
            return
        
        email = args[1]
        password = args[2]

        inputs = {"user_id": user_id, "messages": [f"{email} {password}"]}
        response = login_app.invoke(inputs)
        
        # Check if login was successful
        if "Bedankt!" in response["messages"][-1]:
            context.user_data['logged_in'] = True
        
        await update.message.reply_text(response["messages"][-1])

    except Exception as e:
        logger.error(f"Error in /login: {e}")
        await update.message.reply_text("Er is een fout opgetreden bij het inloggen.")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and display user profile."""
    if not context.user_data.get('logged_in'):
        await update.message.reply_text("Gelieve eerst in te loggen met het /login commando.")
        return

    user_id = update.message.from_user.id
    summary = analyze_and_summarize_user_activities(user_id)
    await update.message.reply_text(summary)

async def conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle conversation."""
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
    application.add_handler(CommandHandler("profile", profile))
    
    # Add conversation handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
