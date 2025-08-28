import os
import re
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

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
async def security_check(update: Update) -> bool:
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    if user_id not in ALLOWED_USERS:
        print(f"🚫 BLOCKED: User {user_id} (@{username}) tried to access bot")
        await update.message.reply_text(
            "🍄 Sorry, this mycelium only responds to its gardener! 🌱\n\n"
            "This is a personal financial bot. Add your user ID to ALLOWED_USER_IDS in .env"
        )
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

# SECURE COMMAND HANDLERS
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update):
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    store_message(user_id, username, "/start", "command")
    
    await update.message.reply_text(
        "🍄 Mycelium Till here! I'm your always-ready expense tracker 🌱\n\n"
        "**Just text me expenses:**\n"
        "• 'Coffee 5 dollars' or '$4.75 coffee'\n"
        "• 'Earned 500 euros from client work'\n"
        "• '20 yuan lunch' or 'Spent 15 on groceries'\n\n"
        "**Commands:**\n"
        "• /stats - Session totals\n"
        "• /status - Pending messages\n"
        "• /undo - Undo last entry\n\n"
        "Tree Till will process everything when your laptop syncs! 🌳"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update):
        return
        
    user_id = update.effective_user.id
    
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT currency, is_income, SUM(amount), COUNT(*)
        FROM pending_messages 
        WHERE user_id = ? AND processed = FALSE AND amount IS NOT NULL
        GROUP BY currency, is_income
        ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            await update.message.reply_text("🍄 No transactions this session!")
            return
        
        stats_text = "🍄 **Session Stats:**\n\n"
        
        # Group by currency
        currencies = {}
        for currency, is_income, total, count in results:
            if currency not in currencies:
                currencies[currency] = {'income': 0, 'expenses': 0}
            if is_income:
                currencies[currency]['income'] = total
            else:
                currencies[currency]['expenses'] = total
        
        for currency, data in currencies.items():
            income = data['income']
            expenses = data['expenses']
            net = income - expenses
            
            stats_text += f"**{currency}:**\n"
            if income > 0:
                stats_text += f"💰 Income: +{income:.2f}\n"
            if expenses > 0:
                stats_text += f"💸 Expenses: -{expenses:.2f}\n"
            stats_text += f"📊 Net: {net:+.2f}\n\n"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"🍄 Error getting stats: {str(e)}")

async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update):
        return
        
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    store_message(user_id, username, "/undo", "undo_request")
    
    await update.message.reply_text(
        "📝 Undo noted! Tree Till will remove your last transaction when it syncs 🌳"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update):
        return
        
    message_text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    # Check for correction
    correction_amount, correction_desc, correction_currency, correction_income = detect_correction(message_text)
    
    if correction_amount:
        store_message(user_id, username, message_text, "correction", 
                     correction_amount, correction_currency, correction_desc, correction_income)
        
        action = "earned" if correction_income else "spent"
        await update.message.reply_text(
            f"✏️ Correction noted! {correction_currency} {correction_amount:.2f} {action}\n"
            f"🌳 Tree Till will fix this when it syncs!"
        )
        return
    
    # Try to parse as transaction
    amount, description, currency, is_income = parse_transaction(message_text)
    
    if amount and description:
        msg_type = "income" if is_income else "expense"
        store_message(user_id, username, message_text, msg_type, 
                     amount, currency, description, is_income)
        
        action = "earned" if is_income else "spent"
        emoji = "💰" if is_income else "💸"
        
        await update.message.reply_text(
            f"📝 {emoji} {currency} {amount:.2f} {action} on {description}\n"
            f"🍄 Stored for Tree Till! 🌳"
        )
    else:
        # Store as unclear
        store_message(user_id, username, message_text, "unclear")
        await update.message.reply_text(
            f"📝 Noted: '{message_text}'\n"
            f"🤔 Not sure if that's a transaction, but Tree Till will figure it out!\n"
            f"💡 Try: 'Coffee 5 dollars' or 'Earned 200 from freelance'"
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update):
        return
        
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM pending_messages WHERE processed = FALSE')
        pending_count = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT message_type, COUNT(*) 
        FROM pending_messages 
        WHERE processed = FALSE 
        GROUP BY message_type
        ''')
        
        breakdown = cursor.fetchall()
        conn.close()
        
        status_text = f"🍄 **{pending_count} messages** waiting for Tree Till\n\n"
        
        if breakdown:
            emojis = {"expense": "💸", "income": "💰", "correction": "✏️", "unclear": "🤔"}
            for msg_type, count in breakdown:
                emoji = emojis.get(msg_type, "📄")
                status_text += f"{emoji} {count} {msg_type}\n"
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"🍄 Error: {str(e)}")

async def whoami_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    first_name = update.effective_user.first_name or "Unknown"
    
    await update.message.reply_text(
        f"🔍 **Your Info:**\n"
        f"👤 {first_name}\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📝 Username: @{username}\n\n"
        f"💡 Add your User ID to ALLOWED_USER_IDS in .env",
        parse_mode='Markdown'
    )

def main():
    print("🍄 Mycelium Till starting up!")
    
    if not ALLOWED_USERS:
        print("🚨 WARNING: No allowed users! Add ALLOWED_USER_IDS to .env")
    else:
        print(f"🔐 Authorized for {len(ALLOWED_USERS)} users")
    
    init_cloud_database()
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found!")
        return
    
    try:
        app = Application.builder().token(token).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("undo", undo_command))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(CommandHandler("whoami", whoami_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("🍄 Mycelium Till is SECURE and ready!")
        app.run_polling()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
