import json
import os
from dotenv import load_dotenv
import logging
from twilio.rest import Client
from datetime import datetime
import random
import sqlite3
import threading
import time

logger = logging.getLogger(__name__)

load_dotenv() # Load environment variables from .env file
class WellnessBot:
    def __init__(self, config_file='config.json'):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.twilio_account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
                self.twilio_auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
                self.twilio_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
                self.admin_numbers = config.get('admin_numbers', [])
                self.timezone = config.get('timezone', 'UTC')

                # Check if environment variables are set, handle missing variables appropriately.
                if not all([self.twilio_account_sid, self.twilio_auth_token, self.twilio_phone_number]):
                    raise ValueError("Missing Twilio environment variables")

        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            logger.error(f"Error loading config from {config_file}: {e}")
            # Handle the error appropriately (e.g., use default values or exit)
            raise  #Re-raise the exception to be handled at a higher level if needed.

        self.client = Client(self.twilio_account_sid, self.twilio_auth_token)

        # Load JSON data with improved error handling
        self._load_json_data()


    def _load_json_data(self):
        self.meditations = {}
        self.vent_instructions = {}
        self.breathing_patterns = {}
        json_files = ['meditations.json', 'vent_instructions.json', 'breathing_exercises.json']

        for file in json_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if file == 'meditations.json':
                        self.meditations = data
                    elif file == 'vent_instructions.json':
                        self.vent_instructions = data
                    elif file == 'breathing_exercises.json':
                        self.breathing_patterns = data

            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error loading JSON file {file}: {e}")

        self.affirmations = [
            "You are capable of amazing things.",
            "Every day is a fresh start.",
            "You have the power to create change.",
            "Your mental health matters.",
            "You are worthy of peace and happiness."
        ]


    def start_command(self, args, sender):
        self._add_user_to_db(sender)  # Add user to the database
        return ("Welcome to your Mental Wellness Buddy! 🌟\n\n"
                "I'm here to support your mental well-being. Here's how I can help:\n"
                "- Track your mood with /mood\n"
                "- Get guided breathing exercises with /breathe\n"
                "- Receive daily affirmations with /affirmation\n"
                "- Start a meditation session with /meditate\n"
                "- Share your feelings with /vent\n"
                "Type /help anytime to see all commands.")

    def _add_user_to_db(self, phone_number):
        try:
            conn = sqlite3.connect('wellness.db')
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO users (phone_number, joined_date) VALUES (?, ?)',
                      (phone_number, datetime.now()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error adding user to DB: {e}")

    def log_mood(self, args, sender):
        try:
            parts = args.split(' ', 1)
            intensity = int(parts[0])
            notes = parts[1] if len(parts) > 1 else ""
            if 1 <= intensity <=10:
                conn = sqlite3.connect('wellness.db')
                c = conn.cursor()
                c.execute('''INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes)
                             VALUES (?, ?, ?, ?, ?)''', (sender, "mood", intensity, datetime.now(), notes))
                conn.commit()
                conn.close()
                return "Mood logged successfully!"
            else:
                return "Please enter a mood intensity between 1 and 10."
        except ValueError:
            return "Invalid input. Please enter a number between 1 and 10 followed by optional notes."
        except Exception as e:
            logger.error(f"Error logging mood: {e}")
            return "Sorry, there was an error logging your mood. Please try again later."



    def breathing_exercise(self, args, sender):
      pattern_name = args.lower() or 'calm' # Default to 'calm' if no pattern specified.
      if pattern_name not in self.breathing_patterns:
          return "Breathing pattern not found. Try 'calm', 'relaxation', or 'energize'."
      pattern = self.breathing_patterns[pattern_name]
      instructions = f"Inhale for {pattern['inhale']} seconds, hold for {pattern['hold']} seconds, exhale for {pattern['exhale']} seconds. Repeat for {pattern['rounds']} rounds."
      return instructions

    def meditation_guide(self, args, sender):
        if not args:
            # Improved menu with duration information
            options = [f"/meditate {key} - {value['duration']} minutes" for key, value in self.meditations.items()]
            return "Choose your meditation duration:\n" + "\n".join(options)

        meditation_type = args.lower()
        if meditation_type not in self.meditations:
            return "Invalid meditation type. Choose from: quick, medium, long"

        selected_meditation = self.meditations[meditation_type]

        # Log the meditation session (requires database setup as described in Step 4)
        conn = sqlite3.connect('wellness.db')  # Assumes 'wellness.db' is set up
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO meditation_sessions (user_phone, duration, type, started_at)
                VALUES (?, ?, ?, ?)''',
                      (sender, selected_meditation['duration'], meditation_type, datetime.now()))
            conn.commit()
            logger.info(f"Meditation session started for {sender}: {meditation_type}")  # Log the event
        except sqlite3.Error as e:
            logger.error(f"Database error logging meditation session: {e}")
            conn.rollback()  # Rollback in case of error
        finally:
            conn.close()

        # Add to active meditations (in the WellnessBot class)
        self.active_meditations[sender] = {
            'type': meditation_type,
            'start_time': None,
            'current_interval': 0
        }

        # Return the first instruction
        return selected_meditation['script']['0']

    def handle_meditation_progress(self, message, sender):
        conn = sqlite3.connect('wellness.db')
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT meditation_type, start_time, paused FROM active_meditations WHERE user_phone = ?",
                           (sender,))
            row = cursor.fetchone()

            if row is None:
                return "You haven't started a meditation session yet. Use /meditate to begin."

            meditation_type, start_time, paused = row

            if message.lower() == 'ready':
                meditation_data['start_time'] = datetime.now()
                meditation_type = meditation_data['type']
                meditation = self.meditations.get(meditation_type)  # Added error checking

                if not meditation:
                    del self.active_meditations[sender]  # Clean up if meditation type is invalid
                    return f"Error: Meditation type '{meditation_type}' not found."

                thread = threading.Thread(target=self._run_meditation_timer, args=(sender, meditation_type))
                thread.daemon = True
                thread.start()
                return meditation['script'][0]  # Start the meditation


            elif message.lower() == 'end':

                cursor.execute("DELETE FROM active_meditations WHERE user_phone = ?", (sender,))

                conn.commit()

                self._log_meditation_session(sender, meditation_type)  # Assuming you have this function

                return "Meditation session ended. Thank you."


            elif message.lower() == 'pause':

                cursor.execute("UPDATE active_meditations SET paused = 1 WHERE user_phone = ?", (sender,))

                conn.commit()

                return "Meditation paused. Type 'resume' to continue."


            elif message.lower() == 'resume':

                cursor.execute("UPDATE active_meditations SET paused = 0 WHERE user_phone = ?", (sender,))

                conn.commit()

                return "Meditation resumed."

            return "Type 'ready' to start, 'pause' to pause, 'resume' to resume, or 'end' to stop the meditation."
        except sqlite3.Error as e:
            logger.error(f"Database error in handle_meditation_progress: {e}")
            return "An error occurred. Please try again later."
        finally:
            conn.close()

    def _run_meditation_timer(self, sender, meditation_type):
        conn = sqlite3.connect('wellness.db')
        cursor = conn.cursor()

        try:
            meditation = self.meditations.get(meditation_type)
            if not meditation:
                logger.error(f"Meditation type '{meditation_type}' not found.")
                return

            intervals = meditation['intervals']

            while True:
                cursor.execute("SELECT start_time, paused FROM active_meditations WHERE user_phone = ?", (sender,))
                row = cursor.fetchone()
                if row is None:
                    break  # Meditation session ended

                start_time, paused = row

                if paused == 1:
                    time.sleep(60)  # Check every minute if paused
                    continue

                for i, interval in enumerate(intervals):
                    if i == 0:
                        continue

                    wait_time = interval * 60
                    time.sleep(wait_time)

                    cursor.execute("SELECT paused FROM active_meditations WHERE user_phone = ?", (sender,))
                    row = cursor.fetchone()
                    if row is None or row[0] == 1:
                        break  # Meditation ended or paused

                    message = meditation['script'].get(str(i))
                    if message:
                        self._send_twilio_message(sender, message)
                    else:
                        logger.error(f"Missing script for meditation '{meditation_type}', interval {i}")
                    conn.commit()

                break  # Exit loop after all intervals

        except sqlite3.Error as e:
            logger.error(f"Database error in _run_meditation_timer: {e}")
        finally:
            conn.close()

    def daily_affirmation(self, args, sender):
        return random.choice(self.affirmations)

    def help_command(self, args, sender):
        return """Mental Wellness Buddy Commands:
/start - Begin your wellness journey
/mood [1-10] [notes] - Log your current mood
/breathe - Start a breathing exercise
/meditate - Begin a meditation session
/affirmation - Get a daily affirmation
/vent - Share your thoughts and feelings
/analyze - View your mood patterns
/help - See all available commands"""

    def vent_session(self, args, sender):
        return self.vent_instructions['intro']

    def mood_analysis(self, args, sender):
        conn = sqlite3.connect('wellness.db')
        c = conn.cursor()
        c.execute('''SELECT AVG(intensity), COUNT(*) 
                    FROM mood_logs 
                    WHERE user_phone = ? 
                    AND timestamp >= date('now', '-7 days')''',
                  (sender,))
        avg_mood, log_count = c.fetchone()
        conn.close()

        if not avg_mood:
            return "No mood data available yet. Start logging with /mood!"

        return (f"Your 7-day mood analysis:\n"
                f"Average mood: {avg_mood:.1f}/10\n"
                f"Logs this week: {log_count}\n\n"
                "Keep tracking your moods to see patterns and growth! 📊")

    def is_admin(self, phone_number):
        return phone_number in self.admin_numbers

    def check_limit_command(self, args, sender):
        if not self.is_admin(sender):
            return "Access denied. This command is for admins only."
        # Add your Twilio message limit check logic here.
        return "Twilio message limit check results."

    def check_usage_command(self, args, sender):
        if not self.is_admin(sender):
            return "Access denied. This command is for admins only."

        result = self.check_twilio_daily_limit()
        return result["message"]


    def check_twilio_daily_limit(self):
        try:
            usage_records = self.client.usage.records.daily.list(limit=10)
            message_usage = [record for record in usage_records if record.category == 'sms']

            if not message_usage:
                return {"status": "success", "message": "No SMS usage recorded today."}

            usage_summary = []
            for record in message_usage:
                usage_summary.append(f"{record.description}: {record.usage} {record.usage_unit}")

            summary = "\n".join(usage_summary)
            return {"status": "success", "message": f"Today's usage:\n{summary}"}

        except Exception as e:
            logger.error(f"Error fetching usage data: {str(e)}")
            return {"status": "error", "message": "Failed to retrieve Twilio usage data."}

    def get_command_and_args(self, message):
        parts = message.strip().split(' ', 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''
        return command, args