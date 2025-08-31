import os
import re
import sqlite3
from datetime import datetime, date, timedelta
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

# Income vs expense detection
def detect_income_vs_expense(text):
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

def parse_financial_text(message_text):
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

# Database functions
def init_cloud_database():
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
    
    # NEW: Running stats table for quick queries
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS running_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date DATE,
            total_spent REAL DEFAULT 0,
            total_earned REAL DEFAULT 0,
            transaction_count INTEGER DEFAULT 0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, date)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("🍄 Mycelium database initialized!")

def update_running_stats(user_id, amount, is_income):
    """Update daily running stats when a transaction is recorded"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        today = date.today().isoformat()
        
        # Get existing stats for today
        cursor.execute('''
            SELECT total_spent, total_earned, transaction_count 
            FROM running_stats WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        
        existing = cursor.fetchone()
        
        if existing:
            spent, earned, count = existing
            if is_income:
                earned += amount
            else:
                spent += amount
            count += 1
            
            cursor.execute('''
                UPDATE running_stats 
                SET total_spent = ?, total_earned = ?, transaction_count = ?, last_updated = CURRENT_TIMESTAMP
                WHERE user_id = ? AND date = ?
            ''', (spent, earned, count, user_id, today))
        else:
            spent = 0 if is_income else amount
            earned = amount if is_income else 0
            
            cursor.execute('''
                INSERT INTO running_stats (user_id, date, total_spent, total_earned, transaction_count)
                VALUES (?, ?, ?, ?, 1)
            ''', (user_id, today, spent, earned))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error updating stats: {e}")

def get_stats(user_id, days=1):
    """Get running stats for the last N days"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        cursor.execute('''
            SELECT date, total_spent, total_earned, transaction_count
            FROM running_stats 
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date DESC
        ''', (user_id, start_date.isoformat(), end_date.isoformat()))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
        
        # Sum up the period
        total_spent = sum(row[1] for row in results)
        total_earned = sum(row[2] for row in results)
        total_transactions = sum(row[3] for row in results)
        
        return {
            'days': days,
            'spent': total_spent,
            'earned': total_earned,
            'net': total_earned - total_spent,
            'transactions': total_transactions,
            'daily_breakdown': results
        }
        
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return None

def get_category_stats(user_id, days=7):
    """Get category breakdown from recent messages"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        # Get messages from last N days
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute('''
            SELECT description, amount, is_income, message_type
            FROM pending_messages 
            WHERE user_id = ? AND timestamp >= ? AND amount IS NOT NULL
            ORDER BY timestamp DESC
        ''', (user_id, cutoff_date))
        
        results = cursor.fetchall()
        conn.close()
        
        # Group by rough categories (simplified for quick stats)
        categories = {}
        for desc, amount, is_income, msg_type in results:
            if msg_type == "correction":
                continue  # Skip corrections for category stats
                
            # Simple category detection
            desc_lower = (desc or "other").lower()
            category = "Other"
            
            if any(word in desc_lower for word in ['coffee', 'tea', 'food', 'lunch', 'dinner', 'restaurant']):
                category = "🍕 Food"
            elif any(word in desc_lower for word in ['uber', 'taxi', 'gas', 'transport', 'metro']):
                category = "🚗 Transport"  
            elif any(word in desc_lower for word in ['book', 'course', 'lesson', 'education']):
                category = "📚 Learning"
            elif any(word in desc_lower for word in ['subscription', 'netflix', 'spotify']):
                category = "📱 Subscriptions"
            elif is_income:
                category = "💰 Income"
            else:
                category = "💸 Other"
            
            if category not in categories:
                categories[category] = {'total': 0, 'count': 0}
            
            categories[category]['total'] += amount
            categories[category]['count'] += 1
        
        return categories
        
    except Exception as e:
        print(f"❌ Error getting category stats: {e}")
        return {}

def store_message(user_id, username, raw_message, message_type, amount=None, currency='USD', description=None, is_income=False):
    conn = sqlite3.connect('mycelium_messages.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pending_messages (user_id, username, raw_message, message_type, amount, currency, description, is_income)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, raw_message, message_type, amount, currency, description, is_income))
    conn.commit()
    conn.close()
    
    # Update running stats if it's a financial transaction
    if amount is not None and message_type not in ["correction", "undo_request", "command"]:
        update_running_stats(user_id, amount, is_income)

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
    return "🍄 Mycelium Till is running! Webhook mode enabled."

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
                "🍄 *Mycelium Till here!*\n\n"
                "Send expenses or income like:\n"
                "• `Coffee 5 dollars` or `Spent 8.60 on book`\n"
                "• `Earned 200 from client`\n"
                "• `Actually 12.50` (to correct last amount)\n\n"
                "*Commands:*\n"
                "• `/undo` - Mark last transaction for removal\n\n"
                "🌳 Tree Till will process everything when your laptop is online!"
            )
            return "OK"
            
        elif text.startswith('/undo'):
            store_message(user_id, username, text, "undo_request")
            send_telegram_message(chat_id, "🔄 Undo noted! Tree Till will handle it when processing.")
            return "OK"
            
        elif text.startswith('/whoami'):
            send_telegram_message(chat_id, f"🆔 User ID: `{user_id}`\nUsername: @{username}")
            return "OK"
            

        # Handle regular messages
        if not text.startswith('/'):
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

        return "OK"

    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

# API endpoints for Tree Till
@flask_app.route('/api/pending-messages', methods=['GET'])
def get_pending_messages():
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
        return jsonify({'error': str(e)}), 500

@flask_app.route('/api/mark-processed', methods=['POST'])
def mark_processed():
    try:
        message_ids = request.json.get('message_ids', [])
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
        return jsonify({'error': str(e)}), 500

@flask_app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'mycelium-till'})

# Initialize DB and run app
def main():
    print("🍄 Mycelium Till starting up!")
    init_cloud_database()
    
    # Show allowed users for debugging
    if ALLOWED_USERS:
        print(f"✅ Authorized users: {ALLOWED_USERS}")
    else:
        print("⚠️ No authorized users configured!")
    
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 Starting server on port {port}")
    flask_app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()
