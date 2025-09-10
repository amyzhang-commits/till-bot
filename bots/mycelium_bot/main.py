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

# =============================================================================
# ERROR HANDLING & LOGGING
# =============================================================================

def log_error(context, error):
    """Centralized error logging"""
    print(f"❌ ERROR in {context}: {error}")

def log_warning(message):
    """Centralized warning logging"""
    print(f"⚠️ WARNING: {message}")

def log_info(message):
    """Centralized info logging"""
    print(f"ℹ️ INFO: {message}")

# =============================================================================
# SECURITY & USER MANAGEMENT
# =============================================================================

def get_allowed_users():
    """Parse allowed user IDs from environment variables"""
    user_ids_str = os.getenv('ALLOWED_USER_IDS', '')
    if not user_ids_str:
        log_warning("No ALLOWED_USER_IDS set in .env file!")
        return []
    try:
        return [int(uid.strip()) for uid in user_ids_str.split(',') if uid.strip()]
    except ValueError as e:
        log_error("parsing ALLOWED_USER_IDS", e)
        return []

ALLOWED_USERS = get_allowed_users()

def security_check(user_id, username):
    """Check if user is authorized to use the bot"""
    if user_id not in ALLOWED_USERS:
        log_warning(f"BLOCKED: User {user_id} (@{username}) tried to access bot")
        return False
    return True

# =============================================================================
# NATURAL LANGUAGE PROCESSING
# =============================================================================

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
    """Extract currency from text and return cleaned text"""
    try:
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
    except Exception as e:
        log_error("currency detection", e)
        return 'USD', text

def detect_income_vs_expense(text):
    """Determine if text describes income or expense and confidence level"""
    try:
        text_lower = text.lower()
        
        # Strong income indicators
        strong_income_keywords = [
            'earned', 'made money', 'income', 'freelance payment', 'client paid', 
            'received payment', 'salary', 'bonus', 'refund', 'cashback', 
            'sold something', 'gift money'
        ]
        
        # Strong expense indicators  
        strong_expense_keywords = [
            'spent', 'bought', 'purchased', 'paid for', 'cost me', 'bill',
            'subscription', 'fee', 'charge', 'rent', 'food', 'coffee',
            'book', 'course', 'lesson', 'uber', 'taxi', 'gas', 'groceries'
        ]
        
        # Weaker indicators
        income_keywords = ['earned', 'made', 'received', 'got paid']
        expense_keywords = ['paid', 'spend', 'buy', 'cost', 'on ', 'for ']
        
        # Check strong indicators first
        for keyword in strong_income_keywords:
            if keyword in text_lower:
                return True, 3  # Strong confidence income
                
        for keyword in strong_expense_keywords:
            if keyword in text_lower:
                return False, 3  # Strong confidence expense
        
        # Check patterns that are clearly expenses
        expense_patterns = [
            r'\d+(?:\.\d{2})?\s+(?:on|for)\s+\w+',  # "8.60 on book" or "8.60 for book"
            r'\w+\s+\d+(?:\.\d{2})?',  # "coffee 5.50"
            r'spent.*\d+',  # "spent 20"
            r'bought.*\d+',  # "bought something for 10"
        ]
        
        for pattern in expense_patterns:
            if re.search(pattern, text_lower):
                return False, 2  # Medium confidence expense
        
        # Fallback to basic keyword counting
        income_score = sum(1 for word in income_keywords if word in text_lower)
        expense_score = sum(1 for word in expense_keywords if word in text_lower)
        
        if income_score > expense_score:
            return True, 1
        elif expense_score > income_score:
            return False, 1
        else:
            return False, 0  # Default to expense with no confidence
            
    except Exception as e:
        log_error("income/expense detection", e)
        return False, 0

def parse_financial_text(message_text):
    """Parse financial message and extract amount, description, currency, income status"""
    try:
        original_text = message_text.strip()
        currency, text_without_currency = detect_currency(original_text)
        
        # Check for correction patterns FIRST (before income/expense detection)
        correction_patterns = [
            r'(?:actually|wait|i meant|should be|correction|make that|change to|fix that|sorry|oops)[,\s]*(\d+(?:\.\d{2})?)',
            r'^(\d+(?:\.\d{2})?)\s*(?:correction|fix|change)',
            r'correction[:\s]*(\d+(?:\.\d{2})?)'
        ]
        
        text_lower = text_without_currency.lower()
        
        # Check if this is a correction
        for pattern in correction_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    amount = float(match.group(1))
                    return amount, "CORRECTION", currency, None, 'correction'  # None for is_income = Tree Till decides
                except ValueError:
                    continue
        
        # If not a correction, proceed with normal parsing
        is_income, confidence = detect_income_vs_expense(original_text)
        text = text_without_currency.lower()

        patterns = [
            # Explicit action patterns (highest priority)
            (r'(?:earned|made|received)\s*(\d+(?:\.\d{2})?)\s*(?:from|for)?\s*(.*)', 'amount_first'),
            (r'(?:spent|paid|bought)\s*(\d+(?:\.\d{2})?)\s*(?:on|for)\s*(.*)', 'amount_first'),
            
            # Amount + preposition patterns  
            (r'^(\d+(?:\.\d{2})?)\s+(?:for|on)\s+(.*)', 'amount_first'),
            
            # Simple amount first patterns
            (r'^(\d+(?:\.\d{2})?)\s+(?:dollars?|euros?|pounds?|yen|yuan)?\s*(.*)', 'amount_first'),
            
            # Description first patterns
            (r'^(.*?)\s+(\d+(?:\.\d{2})?)$', 'desc_first')
        ]

        for pattern, order_type in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if order_type == 'amount_first':
                        amount = float(match.group(1))
                        description = match.group(2).strip() if len(match.groups()) > 1 else None
                    elif order_type == 'desc_first':
                        description = match.group(1).strip()
                        amount = float(match.group(2))
                    else:
                        continue

                    # Clean up description
                    if description:
                        description = re.sub(r'^(?:on|for|from)\s*', '', description).strip()
                        # Don't return empty descriptions
                        if not description:
                            description = None

                    return amount, description, currency, is_income, confidence
                except (ValueError, IndexError):
                    continue

        return None, None, currency, False, 0
        
    except Exception as e:
        log_error("financial text parsing", e)
        return None, None, 'USD', False, 0

# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def init_cloud_database():
    """Initialize the mycelium database with required tables"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        # Main messages table
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
        log_info("Mycelium database initialized!")
        
    except Exception as e:
        log_error("database initialization", e)
        raise

def store_message(user_id, username, raw_message, message_type, amount=None, currency='USD', description=None, is_income=False):
    """Store a message in the database"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pending_messages (user_id, username, raw_message, message_type, amount, currency, description, is_income)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, raw_message, message_type, amount, currency, description, is_income))
        conn.commit()
        conn.close()
        
    except Exception as e:
        log_error("storing message", e)
        raise

# =============================================================================
# TELEGRAM COMMUNICATION
# =============================================================================

def send_telegram_message(chat_id, text):
    """Send a message to Telegram chat"""
    try:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            log_error("Telegram communication", "No TELEGRAM_BOT_TOKEN in environment")
            return False
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})
        return response.status_code == 200
        
    except Exception as e:
        log_error("sending Telegram message", e)
        return False

# =============================================================================
# COMMAND HANDLING
# =============================================================================

def handle_start_command(user_id, username, chat_id):
    """Handle /start command"""
    try:
        store_message(user_id, username, "/start", "command")
        send_telegram_message(chat_id,
            "🍄 *Mycelium Till here!*\n\n"
            "Send expenses or income like:\n"
            "• `Coffee 5 dollars` or `Spent 8.60 on book`\n"
            "• `Earned 200 from client`\n"
            "• `Actually 12.50` (to correct last amount)\n\n"
            "*Commands:*\n"
            "• `/undo` - Mark last transaction for removal\n\n"
            "🌳 Tree Till will process everything when your laptop is online!"
        )
    except Exception as e:
        log_error("handling start command", e)

def handle_undo_command(user_id, username, chat_id):
    """Handle /undo command"""
    try:
        store_message(user_id, username, "/undo", "undo_request")
        send_telegram_message(chat_id, "🔄 Undo noted! Tree Till will handle it when processing.")
    except Exception as e:
        log_error("handling undo command", e)

def handle_whoami_command(user_id, username, chat_id):
    """Handle /whoami command"""
    try:
        send_telegram_message(chat_id, f"🆔 User ID: `{user_id}`\nUsername: @{username}")
    except Exception as e:
        log_error("handling whoami command", e)

# =============================================================================
# MESSAGE PROCESSING
# =============================================================================

def process_financial_message(user_id, username, chat_id, text):
    """Process a financial message (not a command)"""
    try:
        amount, description, currency, is_income, parse_type = parse_financial_text(text)

        # Handle corrections specially
        if parse_type == 'correction':
            store_message(user_id, username, text, "correction", amount, currency, description, None)
            send_telegram_message(chat_id,
                f"✏️ Correction noted! ${amount:.2f}\n"
                "🌳 Tree Till will update your last transaction!"
            )
        elif amount and description:
            msg_type = "income" if is_income else "expense"
            store_message(user_id, username, text, msg_type, amount, currency, description, is_income)

            action = "earned" if is_income else "spent"
            emoji = "💰" if is_income else "💸"

            # Show confidence level for debugging
            confidence_note = ""
            if parse_type == 0:
                confidence_note = " (guessing expense)"
            elif parse_type == 1:
                confidence_note = " (low confidence)"

            send_telegram_message(chat_id,
                f"✅ {emoji} {currency} {amount:.2f} {action} on {description}{confidence_note}\n"
                "🍄 Stored for Tree Till! 🌳"
            )
        elif amount and not description:
            # This might be a poorly formatted correction
            store_message(user_id, username, text, "unclear_amount", amount, currency, "NEEDS_CONTEXT", is_income)
            send_telegram_message(chat_id,
                f"🤔 Got ${amount:.2f} but unclear what for...\n"
                "💡 Try: `Actually 8.50 on coffee` or `Correction: 15.75`"
            )
        else:
            store_message(user_id, username, text, "unclear")
            send_telegram_message(chat_id,
                f"🍄 Noted: '{text}'\n"
                "🤖 Not sure if that's a transaction, but Tree Till will figure it out!"
            )
            
    except Exception as e:
        log_error("processing financial message", e)
        send_telegram_message(chat_id, "🍄 Something went wrong processing that message, but I've noted it!")

# =============================================================================
# FLASK ROUTES
# =============================================================================

@flask_app.route('/', methods=['GET'])
def home():
    return "🍄 Mycelium Till is running! Webhook mode enabled."

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint for receiving Telegram messages"""
    try:
        update_data = request.get_json()
        if not update_data:
            return "OK"
            
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
                "🍄 Sorry, this mycelium only responds to its gardener! 🌱\nThis is a personal financial bot."
            )
            return "OK"

        # Route to appropriate handler
        if text.startswith('/start'):
            handle_start_command(user_id, username, chat_id)
        elif text.startswith('/undo'):
            handle_undo_command(user_id, username, chat_id)
        elif text.startswith('/whoami'):
            handle_whoami_command(user_id, username, chat_id)
        elif not text.startswith('/'):
            # Regular financial message
            process_financial_message(user_id, username, chat_id, text)

        return "OK"

    except Exception as e:
        log_error("webhook processing", e)
        return "Error", 500

# =============================================================================
# TREE TILL API ENDPOINTS
# =============================================================================

@flask_app.route('/api/pending-messages', methods=['GET'])
def get_pending_messages():
    """API endpoint for Tree Till to fetch unprocessed messages"""
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

        messages = []
        for row in results:
            messages.append({
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'raw_message': row[3],
                'message_type': row[4],
                'amount': row[5],
                'currency': row[6],
                'description': row[7],
                'is_income': row[8],
                'timestamp': row[9]
            })
        return jsonify(messages)
        
    except Exception as e:
        log_error("fetching pending messages", e)
        return jsonify({'error': str(e)}), 500

@flask_app.route('/api/mark-processed', methods=['POST'])
def mark_processed():
    """API endpoint for Tree Till to mark messages as processed"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        message_ids = data.get('message_ids', [])
        if not message_ids:
            return jsonify({'error': 'No message IDs provided'}), 400

        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in message_ids])
        cursor.execute(f'UPDATE pending_messages SET processed = TRUE WHERE id IN ({placeholders})', message_ids)
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'updated_count': updated_count})
        
    except Exception as e:
        log_error("marking messages as processed", e)
        return jsonify({'error': str(e)}), 500

@flask_app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'mycelium-till'})

# =============================================================================
# APPLICATION INITIALIZATION
# =============================================================================

def main():
    """Initialize and start the Flask application"""
    try:
        log_info("Mycelium Till starting up!")
        init_cloud_database()
        
        # Show allowed users for debugging
        if ALLOWED_USERS:
            log_info(f"Authorized users: {ALLOWED_USERS}")
        else:
            log_warning("No authorized users configured!")
        
        port = int(os.environ.get('PORT', 8000))
        log_info(f"Starting server on port {port}")
        flask_app.run(host='0.0.0.0', port=port, debug=False)
        
    except Exception as e:
        log_error("application startup", e)
        raise

if __name__ == "__main__":
    main()
