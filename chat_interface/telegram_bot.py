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
from telegram.constants import ParseMode
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
    elif query.data == 'workout_send_garmin':
        await handle_workout_send_garmin(update, context)
    elif query.data == 'workout_download':
        await handle_workout_download(update, context)
    elif query.data == 'workout_cancel':
        await handle_workout_cancel(update, context)
    elif query.data == 'recovery_continue':
        await handle_recovery_continue(update, context)
    elif query.data == 'recovery_alternative':
        await handle_recovery_alternative(update, context)

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
            "⏳ Controleren database voor recent ontvangen data...\n\n"
            "📌 **Hoe Garmin data werkt:**\n"
            "• Data komt automatisch binnen via webhooks wanneer je sync't\n"
            "• Dit commando toont wat er AL in de database staat\n"
            "• Voor historische data, gebruik: `/garmin_backfill <dagen>`"
        )

        # Fetch data from database (populated by webhooks)
        client = GarminAPIClient(db, user_id)
        data = client.get_recent_data(days=7)  # Check last 7 days in database

        # Prepare summary
        num_dailies = len(data.get('dailies', []))
        num_sleeps = len(data.get('sleeps', []))
        num_activities = len(data.get('activities', []))
        num_stress = len(data.get('stress', []))

        if num_dailies == 0 and num_sleeps == 0 and num_activities == 0 and num_stress == 0:
            await update.message.reply_text(
                "📭 Geen data gevonden in database\n\n"
                "Dit kan betekenen:\n"
                "• Je hebt nog niet gesynchroniseerd sinds het verbinden\n"
                "• De webhooks zijn nog niet geconfigureerd\n\n"
                "**Wat kun je doen:**\n"
                "1. Synchroniseer je Garmin apparaat met Garmin Connect app\n"
                "2. Wacht 1-2 minuten op webhooks\n"
                "3. Voor oude data: `/garmin_backfill 30` (triggert webhooks)\n\n"
                "💡 Data wordt automatisch binnen gehaald bij elke sync!"
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


async def handle_workout_send_garmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle workout upload to Garmin Connect."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    workout_details = context.user_data.get('pending_workout')

    if not workout_details:
        await query.edit_message_text(text="❌ Geen workout gevonden. Probeer opnieuw.")
        return

    try:
        await query.edit_message_text(text="⏳ Bezig met uploaden naar Garmin Connect...")

        # Use the upload_workout_to_garmin tool
        from app.tools.garmin_workout_upload import upload_workout_to_garmin

        result = upload_workout_to_garmin(
            user_id=user_id,
            workout_type=workout_details['workout_type'],
            duration_minutes=workout_details['duration_minutes'],
            sport=workout_details['sport']
        )

        # Clean up the FIT file
        if os.path.exists(workout_details['file_path']):
            os.remove(workout_details['file_path'])

        # Clear pending workout
        context.user_data.pop('pending_workout', None)

        # Clear workout context from chat history to prevent re-creation
        if "chat_history" in context.user_data and context.user_data["chat_history"]:
            # Replace the last AI message with a simple confirmation
            for i in range(len(context.user_data["chat_history"]) - 1, -1, -1):
                if isinstance(context.user_data["chat_history"][i], AIMessage):
                    context.user_data["chat_history"][i] = AIMessage(
                        content="Workout succesvol geüpload naar Garmin Connect."
                    )
                    break

        await query.edit_message_text(text=f"✅ {result}", parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error uploading workout to Garmin: {e}")
        await query.edit_message_text(
            text=f"❌ Fout bij uploaden naar Garmin:\n{str(e)}",
            parse_mode=ParseMode.HTML
        )


async def handle_workout_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle workout FIT file download."""
    query = update.callback_query
    await query.answer()

    workout_details = context.user_data.get('pending_workout')

    if not workout_details:
        await query.edit_message_text(text="❌ Geen workout gevonden. Probeer opnieuw.")
        return

    try:
        fit_file_path = workout_details['file_path']

        if not os.path.exists(fit_file_path):
            await query.edit_message_text(text="❌ Workout bestand niet gevonden.")
            return

        # Send the FIT file
        await query.message.reply_document(
            document=open(fit_file_path, 'rb'),
            filename="workout.fit"
        )

        # Clean up
        os.remove(fit_file_path)
        context.user_data.pop('pending_workout', None)

        await query.edit_message_text(text="✅ Workout FIT bestand verzonden!")

    except Exception as e:
        logger.error(f"Error sending FIT file: {e}")
        await query.edit_message_text(text=f"❌ Fout bij versturen bestand: {str(e)}")


async def handle_workout_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle workout cancellation."""
    query = update.callback_query
    await query.answer()

    workout_details = context.user_data.get('pending_workout')

    if workout_details:
        # Clean up the FIT file
        if os.path.exists(workout_details['file_path']):
            os.remove(workout_details['file_path'])

        # Clear pending workout
        context.user_data.pop('pending_workout', None)

    await query.edit_message_text(text="❌ Workout geannuleerd.")


async def handle_recovery_continue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user choosing to continue with original intense workout despite recovery warning."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    original_request = context.user_data.get('original_request')

    if not original_request:
        await query.edit_message_text(text="❌ Originele vraag niet gevonden. Probeer opnieuw.")
        return

    await query.edit_message_text(text="✅ Oké, ik maak de workout met force mode...")

    # Re-invoke agent with force flag in message
    if "chat_history" not in context.user_data:
        context.user_data["chat_history"] = []

    # Set force mode flag to persist across messages
    context.user_data['force_mode_active'] = True
    context.user_data['force_mode_request'] = original_request

    current_date = datetime.date.today().isoformat()
    agent_executor = create_conversational_agent(user_id, current_date=current_date)

    # Add force keyword to bypass recovery check
    forced_message = f"Forceer: {original_request}"
    result = agent_executor.invoke({"input": forced_message, "chat_history": context.user_data["chat_history"]})

    context.user_data["chat_history"].append(HumanMessage(content=forced_message))
    context.user_data["chat_history"].append(AIMessage(content=result["output"]))

    # Check if workout was created
    fit_file_path = None
    workout_details = None
    for action, observation in result.get("intermediate_steps", []):
        if action.tool == "create_fit_file":
            fit_file_path = observation
            workout_details = {
                'file_path': fit_file_path,
                'workout_type': action.tool_input.get('workout_type'),
                'duration_minutes': action.tool_input.get('duration_minutes'),
                'sport': action.tool_input.get('sport'),
            }
            break

    if fit_file_path:
        context.user_data['pending_workout'] = workout_details

        keyboard = [
            [
                InlineKeyboardButton("📤 Verzend naar Garmin", callback_data='workout_send_garmin'),
                InlineKeyboardButton("💾 Download FIT file", callback_data='workout_download')
            ],
            [InlineKeyboardButton("❌ Annuleer", callback_data='workout_cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(result["output"], reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await query.message.reply_text(result["output"], parse_mode=ParseMode.HTML)

    # Clear original request
    context.user_data.pop('original_request', None)


async def handle_recovery_alternative(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user choosing recovery workout alternative."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    await query.edit_message_text(text="✅ Goed gekozen! Ik maak een hersteltraining voor je...")

    if "chat_history" not in context.user_data:
        context.user_data["chat_history"] = []

    current_date = datetime.date.today().isoformat()
    agent_executor = create_conversational_agent(user_id, current_date=current_date)

    # Request recovery workout
    recovery_message = "Maak een hersteltraining van 45 minuten"
    result = agent_executor.invoke({"input": recovery_message, "chat_history": context.user_data["chat_history"]})

    context.user_data["chat_history"].append(HumanMessage(content=recovery_message))
    context.user_data["chat_history"].append(AIMessage(content=result["output"]))

    # Check if workout was created
    fit_file_path = None
    workout_details = None
    for action, observation in result.get("intermediate_steps", []):
        if action.tool == "create_fit_file":
            fit_file_path = observation
            workout_details = {
                'file_path': fit_file_path,
                'workout_type': action.tool_input.get('workout_type'),
                'duration_minutes': action.tool_input.get('duration_minutes'),
                'sport': action.tool_input.get('sport'),
            }
            break

    if fit_file_path:
        context.user_data['pending_workout'] = workout_details

        keyboard = [
            [
                InlineKeyboardButton("📤 Verzend naar Garmin", callback_data='workout_send_garmin'),
                InlineKeyboardButton("💾 Download FIT file", callback_data='workout_download')
            ],
            [InlineKeyboardButton("❌ Annuleer", callback_data='workout_cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(result["output"], reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await query.message.reply_text(result["output"], parse_mode=ParseMode.HTML)

    # Clear original request
    context.user_data.pop('original_request', None)


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
        await update.message.reply_text("Gelieve eerst in te loggen met /garmin_connect.")
        return
    message = update.message.text

    if "chat_history" not in context.user_data:
        context.user_data["chat_history"] = []

    # Get current date for each message to ensure accuracy
    current_date = datetime.date.today().isoformat()

    # Check if force mode is active from button press
    force_mode_active = context.user_data.get('force_mode_active', False)
    if force_mode_active:
        # Append force keyword to message to bypass recovery checks
        original_message = message
        message = f"Forceer: {context.user_data.get('force_mode_request', message)} - {message}"

    agent_executor = create_conversational_agent(user_id, current_date=current_date)

    result = agent_executor.invoke({"input": message, "chat_history": context.user_data["chat_history"]})

    # Store original message in history if force mode was used
    if force_mode_active:
        context.user_data["chat_history"].append(HumanMessage(content=original_message))
    else:
        context.user_data["chat_history"].append(HumanMessage(content=message))

    context.user_data["chat_history"].append(AIMessage(content=result["output"]))

    # Limit chat history to last 20 messages (10 exchanges) to prevent context bleeding
    # This prevents old workout requests or conversations from interfering with new questions
    MAX_HISTORY_MESSAGES = 20
    if len(context.user_data["chat_history"]) > MAX_HISTORY_MESSAGES:
        context.user_data["chat_history"] = context.user_data["chat_history"][-MAX_HISTORY_MESSAGES:]
        logger.debug(f"Trimmed chat history to last {MAX_HISTORY_MESSAGES} messages")

    # Check for recovery warning in the output
    output_lower = result["output"].lower()
    is_recovery_warning = (
        ("herstelstatus" in output_lower or "herstelscore" in output_lower) and
        ("niet optimaal" in output_lower or "raad aan" in output_lower or "beter is om" in output_lower) and
        "hersteltraining" in output_lower
    )

    # Check if a workout was created or uploaded
    fit_file_path = None
    workout_details = None
    workout_uploaded = False

    for action, observation in result.get("intermediate_steps", []):
        if action.tool == "create_fit_file":
            fit_file_path = observation
            # Store workout details for later use
            workout_details = {
                'file_path': fit_file_path,
                'workout_type': action.tool_input.get('workout_type'),
                'duration_minutes': action.tool_input.get('duration_minutes'),
                'sport': action.tool_input.get('sport'),
            }
            break
        elif action.tool == "upload_workout_to_garmin":
            # Workout was uploaded directly to Garmin
            workout_uploaded = True
            # Don't break - keep looking for create_fit_file in case both were called

    # Show recovery warning buttons if detected
    if is_recovery_warning and not fit_file_path:
        # Store the original request for later
        context.user_data['original_request'] = message

        keyboard = [
            [
                InlineKeyboardButton("✅ Ga door met originele vraag", callback_data='recovery_continue'),
                InlineKeyboardButton("💆 Maak hersteltraining", callback_data='recovery_alternative')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(result["output"], reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    elif fit_file_path:
        # Store workout in context for callback
        context.user_data['pending_workout'] = workout_details

        # Clear force mode after successful workout creation
        context.user_data.pop('force_mode_active', None)
        context.user_data.pop('force_mode_request', None)

        # Create inline keyboard with action buttons
        keyboard = [
            [
                InlineKeyboardButton("📤 Verzend naar Garmin", callback_data='workout_send_garmin'),
                InlineKeyboardButton("💾 Download FIT file", callback_data='workout_download')
            ],
            [InlineKeyboardButton("❌ Annuleer", callback_data='workout_cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(result["output"], reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(result["output"], parse_mode=ParseMode.HTML)

    # If workout was uploaded to Garmin, clear the workout context from chat history
    # to prevent the agent from trying to recreate it on subsequent messages
    if workout_uploaded and not fit_file_path:
        # Replace the last AI message with a shorter version that doesn't include workout details
        if context.user_data["chat_history"]:
            last_message = context.user_data["chat_history"][-1]
            if isinstance(last_message, AIMessage):
                # Add a simple confirmation that workout is complete
                context.user_data["chat_history"][-1] = AIMessage(
                    content="Workout succesvol geüpload naar Garmin Connect."
                )

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
    application.add_handler(CommandHandler("garmin_auth", garmin_connect_command))  # Alias
    application.add_handler(CommandHandler("garmin_status", garmin_status_command))
    application.add_handler(CommandHandler("garmin_backfill", garmin_backfill_command))
    application.add_handler(CommandHandler("garmin_sync", garmin_sync_command))
    application.add_handler(CommandHandler("garmin_disconnect", garmin_disconnect_command))
    application.add_handler(CommandHandler("garmin_deauth", garmin_disconnect_command))  # Alias

    application.add_handler(CallbackQueryHandler(button))

    # Add conversation handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
