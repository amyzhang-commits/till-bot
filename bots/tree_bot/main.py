import requests
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple

class TreeTillProcessor:
    def __init__(self, model_name="gemma3n:latest", base_url="http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.categories = [
            "Food & Dining",
            "Transportation", 
            "Personal Care",
            "Health & Fitness",
            "Shopping & Retail",
            "Entertainment",
            "Bills & Utilities",
            "Professional & Work",
            "Education & Learning",
            "Travel",
            "Home & Garden",
            "Income - Freelance",
            "Income - Salary", 
            "Income - Other",
            "Other"
        ]
    
    def init_tree_database(self):
        """Initialize the Tree Till database for processed transactions"""
        conn = sqlite3.connect('tree_till.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mycelium_id INTEGER,
            timestamp DATETIME,
            amount REAL NOT NULL,
            description TEXT,
            category TEXT,
            currency TEXT DEFAULT 'USD',
            is_income BOOLEAN DEFAULT FALSE,
            raw_message TEXT,
            user_id INTEGER,
            username TEXT,
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        print("🌳 Tree Till database initialized!")
    
    def categorize_transaction(self, description: str, amount: float, is_income: bool) -> Optional[str]:
        """
        Use Gemma to categorize a transaction (expense or income)
        Returns the category name or None if error
        """
        
        transaction_type = "income" if is_income else "expense"
        
        prompt = f"""You are a helpful financial categorization assistant. 

Your job is to categorize transactions into one of these categories:
{', '.join(self.categories)}

Given this {transaction_type}:
- Description: "{description}"
- Amount: ${amount:.2f}
- Type: {transaction_type}

Return ONLY the category name, nothing else. Choose the most appropriate category from the list above.

Examples for expenses:
- "coffee" → Food & Dining
- "uber ride" → Transportation  
- "moisturizer" → Personal Care
- "gym membership" → Health & Fitness
- "netflix subscription" → Entertainment

Examples for income:
- "freelance project" → Income - Freelance
- "client payment" → Income - Freelance
- "salary" → Income - Salary
- "bonus" → Income - Salary
- "gift money" → Income - Other

Category:"""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temp for consistent categorization
                        "num_predict": 30    # Allow for longer category names
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                category = result["response"].strip()
                
                # Validate the category is in our list
                if category in self.categories:
                    return category
                else:
                    # Try to find a close match
                    category_lower = category.lower()
                    for valid_cat in self.categories:
                        if category_lower in valid_cat.lower() or valid_cat.lower() in category_lower:
                            return valid_cat
                    
                    # Fallback based on transaction type
                    fallback = "Income - Other" if is_income else "Other"
                    print(f"⚠️  Gemma returned unknown category '{category}', using '{fallback}'")
                    return fallback
            else:
                print(f"❌ Ollama API error: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error to Ollama: {e}")
            return None
        except Exception as e:
            print(f"❌ Categorization error: {e}")
            return None
    
    def get_pending_mycelium_messages(self) -> List[Tuple]:
        """Get all unprocessed messages from mycelium database"""
        try:
            # Path to mycelium database in the other bot directory
            mycelium_db_path = '../mycelium_bot/mycelium_messages.db'
            conn = sqlite3.connect(mycelium_db_path)
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
            
            return results
        except Exception as e:
            print(f"❌ Error reading mycelium messages: {e}")
            return []
    
    def save_processed_transaction(self, mycelium_id: int, user_id: int, username: str,
                                 timestamp: str, amount: float, description: str, 
                                 category: str, currency: str, is_income: bool, 
                                 raw_message: str) -> bool:
        """Save processed transaction to tree_till.db"""
        try:
            conn = sqlite3.connect('tree_till.db')
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO transactions (mycelium_id, user_id, username, timestamp, 
                                    amount, description, category, currency, 
                                    is_income, raw_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (mycelium_id, user_id, username, timestamp, amount, description,
                  category, currency, is_income, raw_message))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Error saving transaction: {e}")
            return False
    
    def mark_mycelium_processed(self, mycelium_id: int) -> bool:
        """Mark a mycelium message as processed"""
        try:
            # Path to mycelium database in the other bot directory
            mycelium_db_path = '../mycelium_bot/mycelium_messages.db'
            conn = sqlite3.connect(mycelium_db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'UPDATE pending_messages SET processed = TRUE WHERE id = ?', 
                (mycelium_id,)
            )
            
            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            return updated
        except Exception as e:
            print(f"❌ Error marking processed: {e}")
            return False
    
    def process_pending_messages(self):
        """Main processing function - the Tree Till awakening!"""
        print("🌳 TREE TILL AWAKENING! 🌳")
        print("🍄 Syncing with mycelium network...")
        
        # Get pending messages
        pending = self.get_pending_mycelium_messages()
        
        if not pending:
            print("✅ No new messages from mycelium network!")
            print("🌱 The forest is peaceful... all transactions processed!")
            return
        
        print(f"🧠 Found {len(pending)} transactions to process with Gemma3n")
        print("=" * 60)
        
        success_count = 0
        
        for msg_data in pending:
            (mycelium_id, user_id, username, raw_message, msg_type, 
             amount, currency, description, is_income, timestamp) = msg_data
            
            print(f"\n🍄 Processing: {raw_message}")
            print(f"   Parsed: {currency} {amount:.2f} - {description}")
            
            # Categorize with Gemma3n
            category = self.categorize_transaction(description, amount, is_income)
            
            if category:
                # Save to tree database
                if self.save_processed_transaction(
                    mycelium_id, user_id, username, timestamp, amount, 
                    description, category, currency, is_income, raw_message
                ):
                    # Mark as processed in mycelium
                    if self.mark_mycelium_processed(mycelium_id):
                        emoji = "💰" if is_income else "💸"
                        print(f"   ✅ {emoji} Categorized as: {category}")
                        success_count += 1
                    else:
                        print(f"   ⚠️  Saved but failed to mark as processed")
                else:
                    print(f"   ❌ Failed to save transaction")
            else:
                print(f"   ❌ Failed to categorize")
        
        print("\n" + "=" * 60)
        print(f"🎉 Tree Till processed {success_count}/{len(pending)} transactions!")
        print("🌳 The forest grows wiser with each transaction! 🌱")
    
    def show_tree_stats(self):
        """Show statistics from the tree database"""
        try:
            conn = sqlite3.connect('tree_till.db')
            cursor = conn.cursor()
            
            # Total counts
            cursor.execute('SELECT COUNT(*), SUM(amount) FROM transactions WHERE is_income = FALSE')
            expense_count, expense_total = cursor.fetchone()
            expense_total = expense_total or 0
            
            cursor.execute('SELECT COUNT(*), SUM(amount) FROM transactions WHERE is_income = TRUE')
            income_count, income_total = cursor.fetchone()
            income_total = income_total or 0
            
            print("\n🌳 TREE TILL WISDOM 🌳")
            print("=" * 40)
            print(f"💸 Total Expenses: {expense_count} transactions, ${expense_total:.2f}")
            print(f"💰 Total Income: {income_count} transactions, ${income_total:.2f}")
            print(f"📊 Net Position: ${income_total - expense_total:+.2f}")
            
            # Category breakdown
            cursor.execute('''
            SELECT category, COUNT(*), SUM(amount), is_income
            FROM transactions 
            GROUP BY category, is_income
            ORDER BY is_income DESC, SUM(amount) DESC
            ''')
            
            categories = cursor.fetchall()
            
            if categories:
                print(f"\n📊 CATEGORY BREAKDOWN:")
                print("-" * 40)
                for category, count, total, is_income in categories:
                    emoji = "💰" if is_income else "💸"
                    print(f"{emoji} {category}: ${total:.2f} ({count} transactions)")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error showing stats: {e}")

def check_ollama_connection():
    """Test if Ollama is running and Gemma is available"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            gemma_models = [m["name"] for m in models if "gemma" in m["name"].lower()]
            print(f"✅ Ollama is running!")
            print(f"🧠 Available Gemma models: {gemma_models}")
            return True
        else:
            print("❌ Ollama not responding properly")
            return False
    except Exception as e:
        print(f"❌ Can't connect to Ollama: {e}")
        print("💡 Make sure Ollama is running: 'ollama serve'")
        return False

def main():
    print("🌳 TREE TILL - THE WISE FINANCIAL ADVISOR 🌳")
    print("=" * 50)
    
    # Check Ollama connection
    if not check_ollama_connection():
        exit(1)
    
    print()
    
    # Initialize processor
    processor = TreeTillProcessor()
    
    # Initialize database
    processor.init_tree_database()
    
    print()
    
    # Process pending messages
    processor.process_pending_messages()
    
    # Show current stats
    processor.show_tree_stats()
    
    print("\n🌱 Tree Till session complete! The forest is ready for your next conversation. 🌳")

if __name__ == "__main__":
    main()
