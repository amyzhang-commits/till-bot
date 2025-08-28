import os
import re
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests

# Load environment variables
load_dotenv()

flask_app = Flask(__name__)

# Allowed users
def get_allowed_users():
    user_ids_str = os.getenv('ALLOWED_USER_IDS', '')
    if not user_ids_str:
        print("⚠️ WARNING: No ALLOWED_USER_IDS set in .env file!")
        return []
    try:
        return [int(uid.strip()) for uid in user_ids_str.split(',') if uid.strip()]
    except ValueError as e:
        print(f"❌ Error parsing ALLOWED_USER_IDS: {e}")
        return []

ALLOWED_USERS = get_allowed_users()

def security_check(user_id, username):
    if user_id not in ALLOWED_USERS:
        print(f"🚫 BLOCKED: User {user_id} (@{username}) tried to access bot")
        return False
    return True

# Currency detection
CURRENCY_WORDS = {
    'dollar': 'USD', 'dollars': 'USD', 'usd': 'USD',
    'euro': 'EUR', 'euros': 'EUR', 'eur': 'EUR', 
    'pound': 'GBP', 'pounds': 'GBP', 'gbp': 'GBP',
    'yen': 'JPY', 'yuan': 'CNY', 'jpy': 'JPY', 'cny': 'CNY',
    'real': 'BRL', 'reals': 'BRL', 'reais': 'BRL', 'brl': 'BRL',
    'rupee': 'INR', 'rupees': 'INR', 'inr': 'INR'
}

def detect_currency(text):
    text_lower = text.lower().strip()
    words = text_lower.split()
    for word in words:
        clean_word = re.sub(r'[^\w]', '', word)
        if clean_word in CURRENCY_WORDS:
            currency = CURRENCY_WORDS[clean_word]
            cleaned_text = re.sub(r'\b' + re.escape(word) + r'\b', '', text_lower, flags=re.IGNORECASE).strip()
            return currency, cleaned_text
    if '$' in text:
        return 'USD', text.replace('$', '').strip()
    return 'USD', text

# Unified parser for transactions & corrections
def detect_income_vs_expense(text):
    text_lower = text.lower()
    income_keywords = ['earn', 'earned', 'made', 'income', 'freelance', 'payment', 'received']
    expense_keywords = ['spent', 'spend', 'bought', 'buy', 'paid', 'cost']
    income_score = sum(1 for word in income_keywords if word in text_lower)
    expense_score = sum(1 for word in expense_keywords if word in text_lower)
    if max(income_score, expense_score) == 0:
        return False, 0  # default to expense
    return income_score > expense_score, max(income_score, expense_score)

def parse_financial_text(message_text):
    original_text = message_text.strip()
    currency, text_without_currency = detect_currency(original_text)
    is_income, _ = detect_income_vs_expense(original_text)
    text = text_without_currency.lower()

    patterns = [
        (r'(?:earned?|made|received|spent|paid)\s*(\d+(?:\.\d{2})?)\s*(?:from|on|for)?\s*(.*)', 'amount_first'),
        (r'^(\d+(?:\.\d{2})?)\s+(?:for\s+|dollars?\s+|euros?\s+)?(.*)', 'amount_first'),
        (r'^(.*?)\s+(\d+(?:\.\d{2})?)$', 'desc_first'),
        (r'(?:actually|wait|i meant|should be|correction|make that|change to|fix that|sorry|oops)[,\s]*(\d+(?:\.\d{2})?)', 'correction')
    ]

    for pattern, order_type in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                if order_type == 'amount_first':
                    amount = float(match.group(1))
                    description = match.group(2).strip()
                elif order_type == 'desc_first':
                    description = match.group(1).strip()
                    amount = float(match.group(2))
                elif order_type == 'correction':
                    amount = float(match.group(1))
                    remaining = re.sub(pattern, '', text).strip()
                    description = remaining if remaining else None
                else:
                    continue

                if description:
                    description = re.sub(r'^\b(?:on|for|from)\b\s*', '', description).strip()

                return amount, description, currency, is_income
            except (ValueError, IndexError):
                continue

    return None, None, currency, False  # default to expense

# Database functions
def init_cloud_database():
    conn = sqlite3.connect('mycelium_messages.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            amount REAL,
            description TEXT,
            raw_message TEXT,
            message_type TEXT,
            currency TEXT DEFAULT 'USD',
            is_income BOOLEAN DEFAULT FALSE,
            processed BOOLEAN DEFAULT FALSE
        )
    ''')
    conn.commit()
    conn.close()
    print("🍄 Mycelium database initialized!")

def store_message(user_id, username, raw_message, message_type, amount=None, currency='USD', description=None, is_income=False):
    conn = sqlite3.connect('mycelium_messages.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pending_messages (user_id, username, raw_message, message_type, amount, currency, description, is_income)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, raw_message, message_type, amount, currency, description, is_income))
    conn.commit()
    conn.close()

def send_telegram_message(chat_id, text):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

# FLASK ROUTES
@flask_app.route('/', methods=['GET'])
def home():
    """Root endpoint"""
    return "🍄 Mycelium Till is running! Webhook mode enabled."

# Webhook route
@flask_app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update_data = request.get_json()
        message = update_data.get('message', {})
        if not message:
            return "OK"

        user = message.get('from', {})
        user_id = user.get('id')
        username = user.get('username', 'Unknown')
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')

        if not user_id or not text:
            return "OK"

        if not security_check(user_id, username):
            send_telegram_message(chat_id,
                "🍄 Sorry, this mycelium only responds to its gardener! 🌱\nThis is a personal financial bot."
            )
            return "OK"

        # Handle commands
        if text.startswith('/start'):
            store_message(user_id, username, text, "command")
            send_telegram_message(chat_id,
                "🍄 Mycelium Till here! Send expenses or income, e.g., 'Coffee 5 dollars' or 'Earned 200'."
            )
            return "OK"
        elif text.startswith('/undo'):
            store_message(user_id, username, text, "undo_request")
            send_telegram_message(chat_id, "📝 Undo noted!")
            return "OK"
        elif text.startswith('/whoami'):
            send_telegram_message(chat_id, f"🆔 User ID: `{user_id}`\nUsername: @{username}")
            return "OK"

        # Regular messages
        if not text.startswith('/'):
    amount, description, currency, is_income = parse_financial_text(text)
    is_income_detected, confidence = detect_income_vs_expense(text)
    
    # Default to expense if confidence is 0
    if confidence == 0:
        is_income = False
    
    if amount and description:
        msg_type = "income" if is_income else "expense"
        store_message(user_id, username, text, msg_type, amount, currency, description, is_income)
        
        action = "earned" if is_income else "spent"
        emoji = "💰" if is_income else "💸"
        
        defaulting_msg = ""
        if confidence == 0:
            defaulting_msg = "\n(Defaulting to expense)"
        
        send_telegram_message(chat_id,
            f"📝 {emoji} {currency} {amount:.2f} {action} on {description}{defaulting_msg}\n"
            "🍄 Stored for Tree Till! 🌳"
        )
    elif amount and not description:
        store_message(user_id, username, text, "correction", amount, currency, description, is_income)
        action = "earned" if is_income else "spent"
        send_telegram_message(chat_id,
            f"✏️ Correction noted! {currency} {amount:.2f} {action}\n"
            "🍄 Stored for Tree Till! 🌳"
        )
    else:
        store_message(user_id, username, text, "unclear")
        send_telegram_message(chat_id,
            f"📝 Noted: '{text}' (unclear)"
        )


        return "OK"

    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

# Initialize DB and run app
def main():
    init_cloud_database()
    port = int(os.environ.get('PORT', 8000))
    flask_app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()

