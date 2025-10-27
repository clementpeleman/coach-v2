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
from app.tools.user_tools import delete_user_data
from app.tools.garmin_oauth import GarminOAuthService
from app.tools.garmin_client import GarminAPIClient
from app.database.database import get_db

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
        "Hallo! Ik ben je AI Sportcoach. Verbind je Garmin account om te beginnen:\n\n"
        "GARMIN OAUTH (AANBEVOLEN):\n"
        "/garmin_connect - Verbind via Garmin OAuth2\n"
        "/garmin_status - Check je Garmin verbinding\n"
        "/garmin_backfill <dagen> - Haal historische data op (bijv. /garmin_backfill 30)\n"
        "/garmin_sync - Check recent gesynchroniseerde data\n"
        "/garmin_disconnect - Verbreek Garmin verbinding\n\n"
        "LEGACY LOGIN (OUD):\n"
        "/login <email> <password> - Direct inloggen\n\n"
        "ANDERE COMMANDO'S:\n"
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
                text="Gebruik het formaat: /login <email> <wachtwoord>\n\nLet op: Je bericht wordt automatisch verwijderd voor beveiliging."
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

    # Note: This feature is currently only available for legacy login users
    # OAuth users should use the conversational agent to analyze their activities
    await query.edit_message_text(
        text="Deze functie is verplaatst naar de conversational agent.\n\n"
        "Gebruik /garmin_connect om je account te verbinden, "
        "en vraag me dan om je activiteiten te analyseren!"
    )

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
    elif query.data == 'garmin_disconnect_confirm':
        user_id = query.from_user.id
        try:
            db = next(get_db())
            oauth_service = GarminOAuthService()

            # Get access token and deregister
            access_token = oauth_service.get_valid_access_token(db, user_id)
            if access_token:
                try:
                    oauth_service.deregister_user(access_token)
                except Exception as e:
                    logger.warning(f"Garmin deregistration failed: {e}")

            # Delete local tokens
            oauth_service.delete_tokens(db, user_id)

            await query.edit_message_text(text="✅ Garmin verbinding verbroken.")
        except Exception as e:
            logger.error(f"Error disconnecting Garmin: {e}")
            await query.edit_message_text(text=f"❌ Fout bij verbreken: {str(e)}")
    elif query.data == 'garmin_disconnect_cancel':
        await query.edit_message_text(text="Verbreken geannuleerd.")

async def garmin_connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start Garmin OAuth2 flow."""
    if not update.message:
        return

    user_id = update.message.from_user.id

    try:
        import httpx

        # Call the API to start OAuth flow
        api_url = os.getenv("API_URL", "http://app:8000")  # Use docker service name

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/garmin/auth/start",
                params={"telegram_user_id": user_id},
                timeout=10.0
            )

            if response.status_code != 200:
                raise Exception(f"API returned {response.status_code}: {response.text}")

            data = response.json()
            auth_url = data["authorization_url"]

        await update.message.reply_text(
            "🔗 Verbind je Garmin account\n\n"
            f"Klik op de link hieronder om in te loggen bij Garmin:\n\n"
            f"{auth_url}\n\n"
            "Na het inloggen wordt je account automatisch verbonden!"
        )

    except Exception as e:
        logger.error(f"Error in /garmin_connect: {e}")
        await update.message.reply_text(f"❌ Fout bij het starten van Garmin OAuth: {str(e)}")


async def garmin_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check Garmin connection status."""
    if not update.message:
        return

    user_id = update.message.from_user.id

    try:
        db = next(get_db())
        oauth_service = GarminOAuthService()

        access_token = oauth_service.get_valid_access_token(db, user_id)

        if not access_token:
            await update.message.reply_text(
                "❌ Geen Garmin verbinding\n\n"
                "Gebruik /garmin_connect om je account te verbinden."
            )
            return

        # Get user info
        from app.database.models import GarminToken
        garmin_token = db.query(GarminToken).filter(GarminToken.user_id == user_id).first()

        # Get permissions
        permissions = oauth_service.get_user_permissions(access_token)

        permissions_text = "\n".join([f"✅ {perm}" for perm in permissions])

        await update.message.reply_text(
            f"✅ Garmin verbonden\n\n"
            f"Garmin User ID: {garmin_token.garmin_user_id}\n"
            f"Token verloopt: {garmin_token.expires_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Toegang:\n{permissions_text}"
        )

    except Exception as e:
        logger.error(f"Error in /garmin_status: {e}")
        await update.message.reply_text(f"❌ Fout bij het checken van status: {str(e)}")


async def garmin_sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check for newly synced Garmin data (from recent device sync)."""
    if not update.message:
        return

    user_id = update.message.from_user.id

    try:
        db = next(get_db())

        # Check if connected
        oauth_service = GarminOAuthService()
        access_token = oauth_service.get_valid_access_token(db, user_id)

        if not access_token:
            await update.message.reply_text(
                "❌ Geen Garmin verbinding. Gebruik /garmin_connect eerst."
            )
            return

        await update.message.reply_text(
            "⏳ Controleren op recent gesynchroniseerde data...\n\n"
            "Let op: Dit commando haalt alleen data op die je Garmin apparaat "
            "recent heeft gesynchroniseerd naar Garmin Connect.\n\n"
            "Voor historische data, gebruik: `/garmin_backfill <dagen>`"
        )

        # Fetch recently uploaded data (last hour)
        client = GarminAPIClient(db, user_id)
        data = client.get_recent_data(days=1)  # Check last 24 hours of uploads

        # Prepare summary
        num_dailies = len(data.get('dailies', []))
        num_sleeps = len(data.get('sleeps', []))
        num_activities = len(data.get('activities', []))
        num_stress = len(data.get('stress', []))

        if num_dailies == 0 and num_sleeps == 0 and num_activities == 0 and num_stress == 0:
            await update.message.reply_text(
                "📭 Geen nieuwe data gevonden\n\n"
                "Dit betekent dat je Garmin apparaat de afgelopen 24 uur "
                "niet heeft gesynchroniseerd met Garmin Connect.\n\n"
                "Wat kun je doen:\n"
                "1. Open de Garmin Connect app en synchroniseer je apparaat\n"
                "2. Gebruik `/garmin_backfill 30` om de laatste 30 dagen op te halen\n"
                "3. Wacht op automatische webhooks (gebeurt bij elke sync)"
            )
        else:
            await update.message.reply_text(
                f"✅ Recent gesynchroniseerde data!\n\n"
                f"📊 {num_dailies} dagelijkse samenvattingen\n"
                f"😴 {num_sleeps} slaap sessies\n"
                f"🏃 {num_activities} activiteiten\n"
                f"💆 {num_stress} stress metingen\n\n"
                f"Je kunt nu vragen stellen over je data!"
            )

        # Mark user as logged in
        context.user_data['logged_in'] = True

    except Exception as e:
        logger.error(f"Error in /garmin_sync: {e}")
        await update.message.reply_text(f"❌ Fout bij synchroniseren: {str(e)}")


async def garmin_backfill_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Backfill historical Garmin data."""
    if not update.message:
        return

    user_id = update.message.from_user.id

    try:
        db = next(get_db())

        # Check if connected
        oauth_service = GarminOAuthService()
        access_token = oauth_service.get_valid_access_token(db, user_id)

        if not access_token:
            await update.message.reply_text(
                "❌ Geen Garmin verbinding. Gebruik /garmin_connect eerst."
            )
            return

        # Parse number of days from command arguments
        args = update.message.text.split()
        if len(args) != 2:
            await update.message.reply_text(
                "Gebruik: `/garmin_backfill <dagen>`\n\n"
                "Voorbeelden:\n"
                "• `/garmin_backfill 7` - Laatste 7 dagen\n"
                "• `/garmin_backfill 30` - Laatste 30 dagen\n"
                "• `/garmin_backfill 90` - Laatste 90 dagen (maximum)\n\n"
                "Dit haalt historische data op van vóór je OAuth verbinding."
            )
            return

        try:
            days = int(args[1])
            if days < 1 or days > 90:
                await update.message.reply_text(
                    "❌ Aantal dagen moet tussen 1 en 90 zijn.\n\n"
                    "Garmin staat maximaal 90 dagen backfill toe."
                )
                return
        except ValueError:
            await update.message.reply_text("❌ Ongeldig aantal dagen. Gebruik een nummer tussen 1 en 90.")
            return

        await update.message.reply_text(
            f"⏳ Backfill gestart voor {days} dagen...\n\n"
            f"Dit kan enkele minuten duren. De data wordt asynchroon opgehaald "
            f"en komt binnen via webhooks.\n\n"
            f"Je ontvangt een bericht zodra het klaar is."
        )

        # Calculate date range
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Request backfill
        client = GarminAPIClient(db, user_id)

        try:
            client.backfill_dailies(start_date, end_date)
            logger.info(f"Backfill dailies requested for user {user_id}: {start_date} to {end_date}")
        except Exception as e:
            logger.error(f"Backfill dailies failed: {e}")

        try:
            client.backfill_activities(start_date, end_date)
            logger.info(f"Backfill activities requested for user {user_id}: {start_date} to {end_date}")
        except Exception as e:
            logger.error(f"Backfill activities failed: {e}")

        await update.message.reply_text(
            f"✅ Backfill aangevraagd!\n\n"
            f"Garmin verwerkt nu je data van de afgelopen {days} dagen.\n\n"
            f"Wat gebeurt er nu:\n"
            f"1. Garmin verzamelt je historische data\n"
            f"2. Data wordt naar onze webhooks gestuurd\n"
            f"3. Je kunt over 5-10 minuten vragen stellen over je data\n\n"
            f"Je hoeft niets te doen - het gebeurt automatisch op de achtergrond!"
        )

        # Mark user as logged in
        context.user_data['logged_in'] = True

    except Exception as e:
        logger.error(f"Error in /garmin_backfill: {e}")
        await update.message.reply_text(f"❌ Fout bij backfill: {str(e)}")


async def garmin_disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disconnect Garmin account."""
    if not update.message:
        return

    keyboard = [
        [InlineKeyboardButton("Ja, verbreek verbinding", callback_data='garmin_disconnect_confirm')],
        [InlineKeyboardButton("Nee, annuleer", callback_data='garmin_disconnect_cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚠️ Garmin verbinding verbreken?\n\n"
        "Dit zal je toegang tot Garmin data verwijderen. Je kunt later opnieuw verbinden.",
        reply_markup=reply_markup
    )


async def conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle conversation."""
    if not update.message:
        return

    user_id = update.message.from_user.id

    # Check if user is logged in (either legacy or OAuth)
    is_logged_in = context.user_data.get('logged_in', False)

    # If not logged in via legacy, check OAuth tokens in database
    if not is_logged_in:
        try:
            db = next(get_db())
            oauth_service = GarminOAuthService()
            access_token = oauth_service.get_valid_access_token(db, user_id)
            if access_token:
                is_logged_in = True
                context.user_data['logged_in'] = True  # Cache for future
        except Exception as e:
            logger.debug(f"OAuth check failed: {e}")

    if not is_logged_in:
        await update.message.reply_text("Gelieve eerst in te loggen met het /login commando of /garmin_connect voor OAuth.")
        return
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

    # Garmin OAuth commands
    application.add_handler(CommandHandler("garmin_connect", garmin_connect_command))
    application.add_handler(CommandHandler("garmin_status", garmin_status_command))
    application.add_handler(CommandHandler("garmin_backfill", garmin_backfill_command))
    application.add_handler(CommandHandler("garmin_sync", garmin_sync_command))
    application.add_handler(CommandHandler("garmin_disconnect", garmin_disconnect_command))

    application.add_handler(CallbackQueryHandler(button))

    # Add conversation handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
