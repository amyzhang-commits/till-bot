import sqlite3
import pandas as pd
from datetime import datetime

def view_mycelium_schema():
    """Show the database schema"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(pending_messages)")
        columns = cursor.fetchall()
        
        print("🍄 MYCELIUM DATABASE SCHEMA 🍄")
        print("=" * 50)
        for col in columns:
            null_info = "NOT NULL" if col[3] else "NULL OK"
            default = f" (default: {col[4]})" if col[4] else ""
            print(f"{col[1]:15} | {col[2]:12} | {null_info}{default}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error reading schema: {e}")

def view_all_messages():
    """View all pending messages in a nice format"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        
        # Get all messages
        query = '''
        SELECT id, user_id, username, raw_message, message_type, 
               amount, currency, description, is_income,
               datetime(timestamp, 'localtime') as local_time,
               processed
        FROM pending_messages 
        ORDER BY timestamp DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        print("\n🍄 MYCELIUM TILL MESSAGES 🍄")
        print("=" * 80)
        print(f"Total messages: {len(df)}")
        
        if len(df) > 0:
            # Summary stats
            transactions = df[df['amount'].notna()]
            if len(transactions) > 0:
                total_amount = transactions['amount'].sum()
                income_total = transactions[transactions['is_income'] == True]['amount'].sum() or 0
                expense_total = transactions[transactions['is_income'] == False]['amount'].sum() or 0
                
                print(f"💰 Total income: {income_total:.2f}")
                print(f"💸 Total expenses: {expense_total:.2f}")
                print(f"📊 Net: {income_total - expense_total:+.2f}")
                
                # Currency breakdown
                currency_summary = transactions.groupby(['currency', 'is_income']).agg({
                    'amount': 'sum',
                    'id': 'count'
                }).round(2)
                
                if not currency_summary.empty:
                    print(f"\n💱 CURRENCY BREAKDOWN:")
                    print("-" * 40)
                    for (currency, is_income), row in currency_summary.iterrows():
                        type_str = "Income" if is_income else "Expenses"
                        emoji = "💰" if is_income else "💸"
                        print(f"{emoji} {currency} {type_str}: {row['amount']:.2f} ({row['id']} entries)")
            
            print(f"\n📝 ALL MESSAGES:")
            print("-" * 80)
            for _, row in df.iterrows():
                # Status indicators
                status = "✅ Processed" if row['processed'] else "⏳ Pending"
                income_indicator = ""
                
                if pd.notna(row['amount']):
                    emoji = "💰" if row['is_income'] else "💸"
                    amount_str = f"{row['currency']} {row['amount']:.2f}"
                    income_indicator = f" | {emoji} {amount_str}"
                
                print(f"#{row['id']:2d} | {row['message_type']:10} | {status}{income_indicator}")
                print(f"     Raw: '{row['raw_message']}'")
                if pd.notna(row['description']):
                    print(f"     Parsed: {row['description']}")
                print(f"     User: {row['username']} | Time: {row['local_time']}")
                print()
        else:
            print("No messages yet - the mycelium network is waiting to grow! 🌱")
            
    except Exception as e:
        print(f"Error reading messages: {e}")

def view_pending_only():
    """Show only unprocessed messages waiting for Tree Till"""
    try:
        conn = sqlite3.connect('mycelium_messages.db')
        
        query = '''
        SELECT COUNT(*) as pending_count,
               SUM(CASE WHEN amount IS NOT NULL THEN 1 ELSE 0 END) as transaction_count
        FROM pending_messages 
        WHERE processed = FALSE
        '''
        
        cursor = conn.cursor()
        cursor.execute(query)
        pending_count, transaction_count = cursor.fetchone()
        
        print(f"\n🌳 WAITING FOR TREE TILL 🌳")
        print("=" * 40)
        print(f"📝 {pending_count} total messages pending")
        print(f"💰 {transaction_count} transactions ready for processing")
        
        if pending_count > 0:
            # Show breakdown by type
            cursor.execute('''
            SELECT message_type, COUNT(*) 
            FROM pending_messages 
            WHERE processed = FALSE 
            GROUP BY message_type
            ORDER BY COUNT(*) DESC
            ''')
            
            breakdown = cursor.fetchall()
            print(f"\nMessage Types:")
            type_emojis = {
                "expense": "💸", "income": "💰", "correction": "✏️", 
                "undo_request": "↩️", "unclear": "🤔", "command": "⚡"
            }
            
            for msg_type, count in breakdown:
                emoji = type_emojis.get(msg_type, "📄")
                print(f"  {emoji} {count:2d} {msg_type.replace('_', ' ')}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error reading pending messages: {e}")

def main():
    print("🍄 MYCELIUM NETWORK EXPLORER 🍄")
    print("Looking into the underground database...")
    print()
    
    # Show schema
    view_mycelium_schema()
    
    # Show all messages
    view_all_messages()
    
    # Show pending summary
    view_pending_only()
    
    print("\n🌱 The mycelium network grows silently, waiting for Tree Till to awaken! 🌳")

if __name__ == "__main__":
    main()
