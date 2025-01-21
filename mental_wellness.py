import sys
import codecs
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import json
import logging
import sqlite3
from wellness_bot_class import WellnessBot
import os
from dotenv import load_dotenv

load_dotenv()

# Load config
def load_config():
    try:
        with open('config.json', 'r') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        logger.error("config.json not found")
        return {}
    except json.JSONDecodeError:
        logger.error("Invalid JSON in config.json")
        return {}

config = load_config()

# Dictionary to track user states (consider persistent storage)
user_states = {}

sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

app = Flask(__name__)


# Single logging setup (already well-structured)
def setup_logging():
    """Configure logging with proper encoding and no duplicates"""
    # Clear any existing handlers from the root logger
    root = logging.getLogger()
    if root.handlers:
        root.handlers.clear()

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    if logger.handlers:
        logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File handler
    file_handler = logging.FileHandler('wellness_bot.log', encoding='utf-8')
    file_handler.setFormatter(formatter)

    # Stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger

logger = setup_logging()

# Database initialization function (already well-structured)
def init_db():
    conn = sqlite3.connect('wellness.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS active_meditations
                     (user_phone TEXT PRIMARY KEY, meditation_type TEXT, start_time DATETIME, paused INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (phone_number TEXT PRIMARY KEY, name TEXT, joined_date DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mood_logs
                 (id INTEGER PRIMARY KEY, user_phone TEXT, mood TEXT, 
                  intensity INTEGER, timestamp DATETIME, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS meditation_sessions
                 (id INTEGER PRIMARY KEY, user_phone TEXT, duration INTEGER, 
                  type TEXT, completed_at DATETIME)''')
    conn.commit()
    conn.close()

@app.route('/', methods=['POST'])
def webhook():
    incoming_msg = request.form.get('Body', '').strip().lower()
    sender = request.form.get('From', '')
    logger.info(f"Received message from {sender}: {incoming_msg}")

    bot = WellnessBot()  # Create an instance of WellnessBot
    response = MessagingResponse()

    try:
        if sender not in user_states:
            user_states[sender] = {"state": "initial"}

        current_state = user_states[sender]["state"]
        command, args = bot.get_command_and_args(incoming_msg)

        with open('commands.json', 'r') as f:
            command_map = json.load(f)

        msg = ""
        next_state = current_state

        if current_state == "initial":
            if command in command_map: #Handle commands from commands.json
                command_func = getattr(bot, command_map[command]) #If it was another command
                msg = command_func(args, sender)
                if command == "/meditate": # Update state for meditation
                    user_states[sender]["state"] = "meditating"
                    user_states[sender]["type"] = args.lower()
                elif command in ["/mood", "/breathe", "/affirmation"]: # Update state for short commands
                    next_state = "initial"
                else:
                    next_state = "initial" #If no specific state change after the command

            elif command:
                msg = "Invalid command. Type /help for available commands."
            else:
                msg = "Use /start, /meditate, or /help." # Guide the user towards the available commands

        elif current_state == "meditating":
            msg = bot.handle_meditation_progress(incoming_msg, sender)
            if msg.endswith("passed]"):
                next_state = "initial"

        elif next_state == "choose_meditation":
            msg = "Choose your meditation duration: /meditate quick | medium | long"

        else: #handle unexpected transitions
            msg = "An unexpected error occurred. Please try again."
            logger.error(f"Unexpected state transition from: {current_state} to {next_state}")

        user_states[sender]["state"] = next_state  # Update user state
        response.message(msg)
        logger.info(f"Sending response to {sender}: {msg}")
        return str(response)

    except Exception as e:
        logger.exception(f"Error processing message: {e}") #This logs the error with the full traceback
        error_response = MessagingResponse()
        error_response.message("Sorry, an unexpected error occurred. Please try again later.")
        return str(error_response)

@app.route('/', methods=['GET'])
def health_check():
    return "Mental Wellness Bot is running!"

if __name__ == '__main__':
    try:
        # CORRECT:  Uses environment variables and load_config
        twilio_account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')

        if not all([twilio_account_sid, twilio_auth_token, twilio_phone_number]):
            raise ValueError("Missing Twilio configurations")
        # Verify config loading

        # Database initialization
        init_db()
        logger.info("Database initialized successfully")
        app.run(debug=True, port=5000)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)  # Exit with error code 1
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        sys.exit(1)  # Exit with error code 1