import os
import re
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests

# Load environment variables
load_dotenv()

# Flask app for API endpoints
flask_app = Flask(__name__)

# Get allowed users from environment
def get_allowed_users():
    user_ids_str = os.getenv('ALLOWED_USER_IDS', '')
    if not user_ids_str:
        print("⚠️  WARNING: No ALLOWED_USER_IDS set in .env file!")
        return []
    
    try:
        user_ids = [int(uid.strip()) for uid in user_ids_str.split(',') if uid.strip()]
        print(f"🔐 Loaded {len(user_ids)} allowed users from .env")
        return user_ids
    except ValueError as e:
        print(f"❌ Error parsing ALLOWED_USER_IDS: {e}")
        return []

ALLOWED_USERS = get_allowed_users()

# Security check function
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
    original_text = text
    text_lower = text.lower().strip()
    
    # Check for currency words
    words = text_lower.split()
    for word in words:
        clean_word = re.sub(r'[^\w]', '', word)
        if clean_word in CURRENCY_WORDS:
            currency = CURRENCY_WORDS[clean_word]
            cleaned_text = re.sub(r'\b' + re.escape(word) + r'\b', '', text_lower, flags=re.IGNORECASE).strip()
            return currency, cleaned_text
    
    # Check for $ symbol
    if '$' in original_text:
        return 'USD', original_text.replace('$', '').strip()
    
    return 'USD', original_text

def detect_income_vs_expense(text):
    text_lower = text.lower()
    
    income_keywords = ['earn', 'earned', 'made', 'income', 'freelance', 'payment', 'received']
    expense_keywords = ['spent', 'spend', 'bought', 'buy', 'paid', 'cost']
    
    income_score = sum(1 for word in income_keywords if word in text_lower)
    expense_score = sum(1 for word in expense_keywords if word in text_lower)
    
    if income_score == 0 and expense_score == 0:
        # Default to expense if no clear signals
        return False, 0  
    
    return income_score > expense_score, max(income_score, expense_score)

def parse_transaction(message_text):
    original_text = message_text.strip()
    currency, text_without_currency = detect_currency(original_text)
    is_income, confidence = detect_income_vs_expense(original_text)
    text = text_without_currency.lower()
    
    # Simple, robust patterns
    patterns = [
        # "earned 500 from client" / "spent 20 on groceries"
        (r'(?:earned?|made|received|spent|paid)\s*(\d+(?:\.\d{2})?)\s*(?:from|on|for)?\s*(.*)', 'amount_first'),
        # "5.50 for coffee" / "20 dollars coffee"
        (r'^(\d+(?:\.\d{2})?)\s+(?:for\s+|dollars?\s+|euros?\s+)?(.*)', 'amount_first'),
        # "coffee 5.50" - description first
        (r'^(.*?)\s+(\d+(?:\.\d{2})?)$', 'desc_first'),
    ]
    
    for pattern, order_type in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                if order_type == 'amount_first':
                    amount = float(match.group(1))
                    description = match.group(2).strip()
                else:
                    description = match.group(1).strip()
                    amount = float(match.group(2))
                
                # Clean description
                description = re.sub(r'^\b(?:on|for|from)\b\s*', '', description).strip()
                
                if description and amount > 0:
                    return amount, description, currency, is_income
                    
            except (ValueError, IndexError):
                continue
    
    return None, None, None, None

def detect_correction(message_text):
    currency, text_without_currency = detect_currency(message_text)
    text = text_without_currency.strip().lower()
    
    correction_patterns = [
        r'(?:actually|wait|i meant|should be|correction)\s*(\d+(?:\.\d{2})?)',
        r'(?:make that|change to|fix that)\s*(\d+(?:\.\d{2})?)',
        r'(?:sorry|oops)[,\s]*(\d+(?:\.\d{2})?)',
    ]
    
    for pattern in correction_patterns:
        match = re.search(pattern, text)
        if match:
            amount = float(match.group(1))
            remaining = re.sub(pattern, '', text).strip()
            description = remaining if remaining else None
            is_income, _ = detect_income_vs_expense(message_text)
            return amount, description, currency, is_income
    
    return None, None, None, None

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
    
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id

def send_telegram_message(chat_id, text):
    """Send a message via Telegram Bot API"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        })
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

# FLASK ROUTES
@flask_app.route('/', methods=['GET'])
def home():
    """Root endpoint"""
    return "🍄 Mycelium Till is running! Webhook mode enabled."

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates"""
    try:
        update_data = request.get_json()
        
        # Extract message info
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
        
        # Security check
        if not security_check(user_id, username):
            send_telegram_message(chat_id, 
                "🍄 Sorry, this mycelium only responds to its gardener! 🌱\n\n"
                "This is a personal financial bot."
            )
            return "OK"
        
        # Handle commands
        if text.startswith('/start'):
            store_message(user_id, username, text, "command")
            send_telegram_message(chat_id,
                "🍄 Mycelium Till here! I'm your always-ready expense tracker 🌱\n\n"
                "**Just text me expenses:**\n"
                "• 'Coffee 5 dollars' or '$4.75 coffee'\n"
                "• 'Earned 500 euros from client work'\n"
                "• '20 yuan lunch' or 'Spent 15 on groceries'\n\n"
                "Tree Till will process everything when your laptop syncs! 🌳"
            )
            return "OK"
        
        elif text.startswith('/undo'):
            store_message(user_id, username, text, "undo_request")
            send_telegram_message(chat_id,
                "📝 Undo noted! Tree Till will remove your last transaction when it syncs 🌳"
            )
            return "OK"
        
        elif text.startswith('/whoami'):
            send_telegram_message(chat_id,
                f"🔍 **Your Info:**\n"
                f"🆔 User ID: `{user_id}`\n"
                f"📝 Username: @{username}\n\n"
                f"💡 Add your User ID to ALLOWED_USER_IDS in .env"
            )
            return "OK"
        
        # Handle regular messages
        if not text.startswith('/'):
            # Check for correction
            correction_amount, correction_desc, correction_currency, correction_income = detect_correction(text)
            
            if correction_amount:
                store_message(user_id, username, text, "correction", 
                             correction_amount, correction_currency, correction_desc, correction_income)
                
                action = "earned" if correction_income else "spent"
                send_telegram_message(chat_id,
                    f"✏️ Correction noted! {correction_currency} {correction_amount:.2f} {action}\n"
                    f"🌳 Tree Till will fix this when it syncs!"
                )
                return "OK"
            
            # Try to parse as transaction
            amount, description, currency, is_income = parse_transaction(text)
            
            if amount and description:
                msg_type = "income" if is_income else "expense"
                store_message(user_id, username, text, msg_type, 
                             amount, currency, description, is_income)
                
                action = "earned" if is_income else "spent"
                emoji = "💰" if is_income else "💸"
                
                send_telegram_message(chat_id,
                    f"📝 {emoji} {currency} {amount:.2f} {action} on {description}\n"
                    f"🍄 Stored for Tree Till! 🌳"
                )
            else:
                # Store as unclear
                store_message(user_id, username, text, "unclear")
                send_telegram_message(chat_id,
                    f"📝 Noted: '{text}'\n"
                    f"🤔 Not sure if that's a transaction, but Tree Till will figure it out!\n"
                    f"💡 Try: 'Coffee 5 dollars' or 'Earned 200 from freelance'"
                )
        
        return "OK"
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

# API ENDPOINTS FOR TREE TILL
@flask_app.route('/api/pending-messages', methods=['GET'])
def get_pending_messages():
    """API endpoint for Tree Till to fetch pending messages"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, user_id, username, raw_message, message_type, 
               amount, currency, description, is_income, timestamp
        FROM pending_messages 
        WHERE processed = FALSE AND amount IS NOT NULL
        ORDER BY timestamp ASC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert to JSON-serializable format
        messages = []
        for row in results:
            messages.append({
                'id': row[0], 'user_id': row[1], 'username': row[2],
                'raw_message': row[3], 'message_type': row[4],
                'amount': row[5], 'currency': row[6], 'description': row[7],
                'is_income': row[8], 'timestamp': row[9]
            })
        
        return jsonify(messages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@flask_app.route('/api/mark-processed', methods=['POST'])
def mark_processed():
    """API endpoint for Tree Till to mark messages as processed"""
    try:
        message_ids = request.json.get('message_ids', [])
        
        if not message_ids:
            return jsonify({'error': 'No message IDs provided'}), 400
        
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        # Mark messages as processed
        placeholders = ','.join(['?' for _ in message_ids])
        cursor.execute(f'UPDATE pending_messages SET processed = TRUE WHERE id IN ({placeholders})', message_ids)
        
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'updated': updated_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@flask_app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({'status': 'healthy', 'service': 'mycelium-till'})

def main():
    print("🍄 Mycelium Till starting up!")
    print(f"🔧 Environment: {os.getenv('RAILWAY_ENVIRONMENT_NAME', 'local')}")
    print(f"🔑 Token exists: {bool(os.getenv('TELEGRAM_BOT_TOKEN'))}")
    print(f"🛡️ Allowed users: {len(ALLOWED_USERS)}")
    print("📊 Initializing database...")
    
    init_cloud_database()
    
    # Set webhook URL if on Railway
    if os.getenv('RAILWAY_ENVIRONMENT_NAME'):
        try:
            token = os.getenv('TELEGRAM_BOT_TOKEN')
            webhook_url = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/webhook"
            
            # Set webhook via Telegram API
            response = requests.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={'url': webhook_url}
            )
            
            if response.status_code == 200:
                print(f"🍄 Webhook set successfully: {webhook_url}")
            else:
                print(f"⚠️  Webhook setup failed: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Webhook setup error: {e}")
    
    print("🍄 Mycelium Till ready!")

if __name__ == "__main__":
    try:
        print("🍄 Mycelium Till starting up!")
        main()
        port = int(os.environ.get('PORT', 8000))
        flask_app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        raise
