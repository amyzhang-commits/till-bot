import requests
import json
import sqlite3
import os
import re
from datetime import datetime, date
from typing import Optional, List, Tuple, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AssetsManager:
    def __init__(self):
        self.init_assets_database()
    
    def init_assets_database(self):
        """Initialize the assets database with Education Fund support"""
        conn = sqlite3.connect(os.getenv('ASSETS_DB_PATH', 'assets.db'))
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS asset_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATE,
            
            -- Bank of America ecosystem
            boa_checking REAL,
            boa_credit_balance REAL,
            
            -- UFB Direct (high-yield savings)
            ufb_savings REAL,
            
            -- Vanguard investments
            vanguard_roth_ira REAL,
            vanguard_brokerage REAL,
            
            -- Health Equity HSA (special treatment)
            hsa_cash REAL,
            hsa_invested REAL,
            hsa_notes TEXT,  -- For IVF timeline notes
            
            -- Education Fund (NEW!)
            education_fund REAL DEFAULT 0,
            education_notes TEXT,  -- For learning goals, courses planned, etc.
            
            -- Other assets/debts
            other_assets REAL DEFAULT 0,
            other_debts REAL DEFAULT 0,
            
            -- Calculated totals
            total_liquid REAL,
            total_invested REAL,
            net_worth REAL,
            
            -- Metadata
            update_type TEXT,  -- 'quick' or 'full'
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Check if education_fund column exists and add it if it doesn't (for existing DBs)
        cursor.execute("PRAGMA table_info(asset_snapshots)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'education_fund' not in columns:
            cursor.execute('ALTER TABLE asset_snapshots ADD COLUMN education_fund REAL DEFAULT 0')
            print("✅ Added education_fund column")
        
        if 'education_notes' not in columns:
            cursor.execute('ALTER TABLE asset_snapshots ADD COLUMN education_notes TEXT')
            print("✅ Added education_notes column")
        
        conn.commit()
        conn.close()
        print("🌳 Assets database initialized!")
    
    def get_latest_snapshot(self) -> Optional[Dict]:
        """Get the most recent asset snapshot"""
        try:
            conn = sqlite3.connect(os.getenv('ASSETS_DB_PATH', 'assets.db'))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM asset_snapshots 
            ORDER BY snapshot_date DESC, created_at DESC 
            LIMIT 1
            ''')
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = [
                    'id', 'snapshot_date', 'boa_checking', 'boa_credit_balance',
                    'ufb_savings', 'vanguard_roth_ira', 'vanguard_brokerage',
                    'hsa_cash', 'hsa_invested', 'hsa_notes', 'education_fund', 
                    'education_notes', 'other_assets', 'other_debts', 
                    'total_liquid', 'total_invested', 'net_worth',
                    'update_type', 'notes', 'created_at'
                ]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"❌ Error getting latest snapshot: {e}")
            return None
    
    def parse_amount(self, input_str: str) -> Optional[float]:
        """Parse various amount formats: '$1,234.56', '1234.56', 'about 1200', etc."""
        if not input_str or input_str.lower().strip() in ['', 'skip', 'same', 'unchanged']:
            return None
        
        # Clean the input
        cleaned = input_str.lower().strip()
        cleaned = re.sub(r'[,$]', '', cleaned)  # Remove $ and commas
        cleaned = re.sub(r'about|around|roughly|approximately', '', cleaned).strip()
        
        # Extract number
        match = re.search(r'(\d+(?:\.\d{2})?)', cleaned)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None
    
    def start_assets_checkin(self):
        """Main assets check-in conversation"""
        print("\n🌳 TREE TILL ASSETS CHECK-IN 🌳")
        print("=" * 50)
        
        # Get previous snapshot
        previous = self.get_latest_snapshot()
        
        if previous:
           prev_date = previous['snapshot_date']
           prev_net_worth = previous.get('net_worth')
           if prev_net_worth is not None:
               print(f"💫 Last update: {prev_date} (Net Worth: ${prev_net_worth:,.2f})")
           else:
               print(f"💫 Last update: {prev_date} (Net Worth: not recorded)")
           print("🌱 Let's see how your financial forest has grown!")
        else:
            print("🌱 Welcome to your first financial forest survey!")
        
        print("\n🤔 What kind of update today?")
        print("   ⚡ Quick (5 min) - Just the basics")
        print("   📋 Full (15 min) - Complete review")
        
        while True:
            choice = input("\nChoice (quick/full): ").lower().strip()
            if choice in ['quick', 'q', 'full', 'f']:
                update_type = 'quick' if choice in ['quick', 'q'] else 'full'
                break
            print("Please choose 'quick' or 'full'")
        
        # Run the appropriate check-in
        if update_type == 'quick':
            self.quick_checkin(previous)
        else:
            self.full_checkin(previous)
    
    def quick_checkin(self, previous: Optional[Dict]):
        """Quick 5-minute check-in"""
        print("\n⚡ QUICK CHECK-IN ⚡")
        print("Just the accounts that probably changed...")
        
        new_data = {}
        
        # Use previous values as defaults
        if previous:
            new_data.update(previous)
        
        # Key liquid accounts that change frequently
        print(f"\n💰 LIQUID ACCOUNTS")
        new_data['boa_checking'] = self.ask_amount(
            "🏦 Bank of America Checking", 
            previous.get('boa_checking') if previous else None
        )
        
        new_data['ufb_savings'] = self.ask_amount(
            "💎 UFB Direct Savings", 
            previous.get('ufb_savings') if previous else None
        )
        
        new_data['boa_credit_balance'] = self.ask_amount(
            "💳 Credit Card Balance (what you owe)", 
            previous.get('boa_credit_balance') if previous else None,
            is_debt=True
        )
        
        # Education Fund (might change if adding money or spending on courses)
        print(f"\n📚 EDUCATION FUND")
        education_changed = input("   Any changes to your education fund? (y/n): ").lower()
        if education_changed.startswith('y'):
            new_data['education_fund'] = self.ask_amount(
                "   💡 Education Fund Balance", 
                previous.get('education_fund') if previous else None
            )
            new_data['education_notes'] = input("   📝 Education notes (courses planned, learning goals): ") or (previous.get('education_notes') if previous else '')
        elif previous:
            new_data['education_fund'] = previous.get('education_fund', 0)
            new_data['education_notes'] = previous.get('education_notes', '')
        else:
            new_data['education_fund'] = 0
            new_data['education_notes'] = ''
        
        # HSA (might change due to IVF planning)
        print(f"\n🏥 HSA (Health Equity)")
        hsa_changed = input("   Any changes to your HSA allocation? (y/n): ").lower()
        if hsa_changed.startswith('y'):
            new_data['hsa_cash'] = self.ask_amount("   💸 HSA Cash", previous.get('hsa_cash') if previous else None)
            new_data['hsa_invested'] = self.ask_amount("   📈 HSA Invested", previous.get('hsa_invested') if previous else None)
            new_data['hsa_notes'] = input("   📝 HSA notes (IVF timeline, etc.): ") or (previous.get('hsa_notes') if previous else '')
        elif previous:
            new_data['hsa_cash'] = previous.get('hsa_cash', 0)
            new_data['hsa_invested'] = previous.get('hsa_invested', 0)
            new_data['hsa_notes'] = previous.get('hsa_notes', '')
        else:
            new_data['hsa_cash'] = 0
            new_data['hsa_invested'] = 0
            new_data['hsa_notes'] = ''
        
        # Vanguard (less frequent changes)
        vanguard_changed = input(f"\n📊 Any major Vanguard changes? (y/n): ").lower()
        if vanguard_changed.startswith('y'):
            new_data['vanguard_roth_ira'] = self.ask_amount("   🛡️ Roth IRA", previous.get('vanguard_roth_ira') if previous else None)
            new_data['vanguard_brokerage'] = self.ask_amount("   📈 Brokerage", previous.get('vanguard_brokerage') if previous else None)
        elif previous:
            new_data['vanguard_roth_ira'] = previous.get('vanguard_roth_ira', 0)
            new_data['vanguard_brokerage'] = previous.get('vanguard_brokerage', 0)
        else:
            new_data['vanguard_roth_ira'] = 0
            new_data['vanguard_brokerage'] = 0
        
        # Fill in unchanged values
        for field in ['other_assets', 'other_debts']:
            if field not in new_data and previous:
                new_data[field] = previous.get(field, 0)
            elif field not in new_data:
                new_data[field] = 0
        
        new_data['update_type'] = 'quick'
        self.save_snapshot(new_data)
    
    def full_checkin(self, previous: Optional[Dict]):
        """Complete 15-minute review"""
        print("\n📋 FULL FINANCIAL FOREST SURVEY 📋")
        print("Let's check every tree in your financial forest...")
        
        new_data = {'update_type': 'full'}
        
        # Bank of America ecosystem
        print(f"\n🏦 BANK OF AMERICA")
        new_data['boa_checking'] = self.ask_amount(
            "   Checking Account", 
            previous.get('boa_checking') if previous else None
        )
        new_data['boa_credit_balance'] = self.ask_amount(
            "   Credit Card Balance (what you owe)", 
            previous.get('boa_credit_balance') if previous else None,
            is_debt=True
        )
        
        # UFB Direct
        print(f"\n💎 UFB DIRECT")
        new_data['ufb_savings'] = self.ask_amount(
            "   High-Yield Savings", 
            previous.get('ufb_savings') if previous else None
        )
        
        # Education Fund (NEW!)
        print(f"\n📚 EDUCATION FUND")
        new_data['education_fund'] = self.ask_amount(
            "   Education Fund Balance", 
            previous.get('education_fund') if previous else None
        ) or 0
        print("   📝 Learning Strategy & Goals:")
        new_data['education_notes'] = input("      (Courses planned, bootcamps, language learning, etc.): ") or ''
        
        # Vanguard investments
        print(f"\n📊 VANGUARD")
        new_data['vanguard_roth_ira'] = self.ask_amount(
            "   Roth IRA", 
            previous.get('vanguard_roth_ira') if previous else None
        )
        new_data['vanguard_brokerage'] = self.ask_amount(
            "   Brokerage Account", 
            previous.get('vanguard_brokerage') if previous else None
        )
        
        # HSA with special attention
        print(f"\n🏥 HEALTH EQUITY HSA")
        new_data['hsa_cash'] = self.ask_amount(
            "   Cash Position", 
            previous.get('hsa_cash') if previous else None
        )
        new_data['hsa_invested'] = self.ask_amount(
            "   Invested Portion", 
            previous.get('hsa_invested') if previous else None
        )
        print("   📝 IVF Planning Notes:")
        new_data['hsa_notes'] = input("      (Timeline, expected costs, strategy): ") or ''
        
        # Other assets/debts
        print(f"\n🏠 OTHER ASSETS & DEBTS")
        new_data['other_assets'] = self.ask_amount(
            "   Other Assets (car value, etc.)", 
            previous.get('other_assets', 0) if previous else None
        ) or 0
        new_data['other_debts'] = self.ask_amount(
            "   Other Debts (loans, etc.)", 
            previous.get('other_debts', 0) if previous else None,
            is_debt=True
        ) or 0
        
        self.save_snapshot(new_data)
    
    def ask_amount(self, prompt: str, previous_value: Optional[float], is_debt: bool = False) -> float:
        """Ask for an amount with smart prompting"""
        if previous_value is not None:
            prev_str = f"${previous_value:,.2f}"
            if is_debt and previous_value > 0:
                prev_str = f"${previous_value:,.2f} owed"
            prompt_text = f"   {prompt} (was {prev_str}): "
        else:
            prompt_text = f"   {prompt}: "
        
        while True:
            response = input(prompt_text).strip()
            
            if response.lower() in ['', 'same', 'unchanged'] and previous_value is not None:
                return previous_value
            
            amount = self.parse_amount(response)
            if amount is not None:
                return amount
            
            print("     🤔 I didn't catch that. Try: '$1,234.56', '1234', 'about 1200', or 'same'")
    
    def save_snapshot(self, data: Dict):
        """Save the asset snapshot and show results"""
        try:
            # Calculate totals - Education Fund counts as liquid asset since it's targeted savings
            liquid_total = (
                data.get('boa_checking', 0) + 
                data.get('ufb_savings', 0) + 
                data.get('hsa_cash', 0) +
                data.get('education_fund', 0)  # NEW: Education fund as liquid
            )
            
            invested_total = (
                data.get('vanguard_roth_ira', 0) + 
                data.get('vanguard_brokerage', 0) + 
                data.get('hsa_invested', 0) + 
                data.get('other_assets', 0)
            )
            
            total_debts = (
                data.get('boa_credit_balance', 0) + 
                data.get('other_debts', 0)
            )
            
            net_worth = liquid_total + invested_total - total_debts
            
            # Update data with calculations
            data.update({
                'snapshot_date': date.today().isoformat(),
                'total_liquid': liquid_total,
                'total_invested': invested_total,
                'net_worth': net_worth
            })
            
            # Remove id and created_at if they exist (from previous snapshot template)
            clean_data = {k: v for k, v in data.items() 
                         if k not in ['id', 'created_at']}
            
            # Save to database
            conn = sqlite3.connect(os.getenv('ASSETS_DB_PATH', 'assets.db'))
            cursor = conn.cursor()
            
            # Build dynamic insert query with clean data
            columns = list(clean_data.keys())
            placeholders = ', '.join(['?' for _ in columns])
            values = list(clean_data.values())
            
            query = f'''
            INSERT INTO asset_snapshots ({', '.join(columns)})
            VALUES ({placeholders})
            '''
            
            cursor.execute(query, values)
            conn.commit()
            conn.close()
            
            # Show beautiful results
            self.show_results(data)
            
        except Exception as e:
            print(f"❌ Error saving snapshot: {e}")
    
    def show_results(self, data: Dict):
        """Display the beautiful financial snapshot with Education Fund"""
        print(f"\n🌳 YOUR FINANCIAL FOREST SNAPSHOT 🌳")
        print("=" * 50)
        
        # Liquid assets
        print(f"💰 LIQUID ASSETS:")
        print(f"   🏦 Bank of America: ${data.get('boa_checking', 0):,.2f}")
        print(f"   💎 UFB Savings: ${data.get('ufb_savings', 0):,.2f}")
        print(f"   🏥 HSA Cash: ${data.get('hsa_cash', 0):,.2f}")
        print(f"   📚 Education Fund: ${data.get('education_fund', 0):,.2f}")
        print(f"   💧 Total Liquid: ${data.get('total_liquid', 0):,.2f}")
        
        # Investments
        print(f"\n📈 INVESTMENTS:")
        print(f"   🛡️ Roth IRA: ${data.get('vanguard_roth_ira', 0):,.2f}")
        print(f"   📊 Vanguard Brokerage: ${data.get('vanguard_brokerage', 0):,.2f}")
        print(f"   🏥 HSA Invested: ${data.get('hsa_invested', 0):,.2f}")
        if data.get('other_assets', 0) > 0:
            print(f"   🏠 Other Assets: ${data.get('other_assets', 0):,.2f}")
        print(f"   📈 Total Invested: ${data.get('total_invested', 0):,.2f}")
        
        # Debts
        total_debt = data.get('boa_credit_balance', 0) + data.get('other_debts', 0)
        if total_debt > 0:
            print(f"\n💳 DEBTS:")
            if data.get('boa_credit_balance', 0) > 0:
                print(f"   💳 Credit Card: ${data.get('boa_credit_balance', 0):,.2f}")
            if data.get('other_debts', 0) > 0:
                print(f"   🏠 Other Debts: ${data.get('other_debts', 0):,.2f}")
            print(f"   💸 Total Debt: ${total_debt:,.2f}")
        
        # Net worth with celebration
        net_worth = data.get('net_worth', 0)
        print(f"\n✨ NET WORTH: ${net_worth:,.2f} ✨")
        
        # Education notes if present
        if data.get('education_notes'):
            print(f"\n📚 Education Strategy:")
            print(f"   {data['education_notes']}")
        
        # HSA notes if present
        if data.get('hsa_notes'):
            print(f"\n🏥 HSA Strategy Notes:")
            print(f"   {data['hsa_notes']}")
        
        print(f"\n🌱 Financial snapshot saved! Your forest is looking strong! 🌳")
        
        # Education fund insights
        education_amount = data.get('education_fund', 0)
        if education_amount > 0:
            print(f"\n💡 Education Fund Insight: With ${education_amount:,.2f}, you're investing in your future!")
            if education_amount >= 1000:
                print(f"   That could cover several online courses or a bootcamp! 🚀")
            elif education_amount >= 500:
                print(f"   Perfect for language lessons or specialized courses! 🗣️")
            else:
                print(f"   Every dollar toward learning pays dividends! 📈")


class TreeTillProcessor:
    def __init__(self, model_name="gemma3n:latest", base_url="http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.mycelium_api_url = os.getenv('MYCELIUM_API_URL')  # Railway URL
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
        conn = sqlite3.connect(os.getenv('TREE_TILL_DB_PATH', 'tree_till.db'))
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
    
    def get_pending_mycelium_messages(self) -> List[Tuple]:
        """Get all unprocessed messages - Railway API first, local SQLite fallback"""
        
        # Try Railway API first
        if self.mycelium_api_url:
            try:
                print(f"🌐 Fetching from Railway API: {self.mycelium_api_url}")
                response = requests.get(
                    f"{self.mycelium_api_url}/api/pending-messages",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Got {len(data)} messages from Railway")
                    
                    # Convert JSON back to tuple format expected by the processor
                    results = []
                    for msg in data:
                        results.append((
                            msg['id'],
                            msg['user_id'], 
                            msg['username'],
                            msg['raw_message'],
                            msg['message_type'],
                            msg['amount'],
                            msg['currency'],
                            msg['description'],
                            msg['is_income'],
                            msg['timestamp']
                        ))
                    return results
                else:
                    print(f"⚠️ Railway API error {response.status_code}, falling back to local")
                    
            except Exception as e:
                print(f"⚠️ Railway API connection failed: {e}, falling back to local")
        
        # Fallback to local SQLite (development mode)
        print("🔧 Using local mycelium database")
        try:
            mycelium_db_path = os.getenv('MYCELIUM_DB_PATH', './bots/mycelium_bot/mycelium_messages.db')
            print(f"📍 Database path: {mycelium_db_path}")
            print(f"📍 Current directory: {os.getcwd()}")
            print(f"📍 Database exists: {os.path.exists(mycelium_db_path)}")	
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
            print(f"📁 Got {len(results)} messages from local database")
            return results
            
        except Exception as e:
            print(f"❌ Error reading local mycelium messages: {e}")
            return []
    
    def mark_mycelium_processed(self, message_ids: List[int]) -> bool:
        """Mark messages as processed - Railway API first, local SQLite fallback"""
        
        if not message_ids:
            return True
        
        # Try Railway API first
        if self.mycelium_api_url:
            try:
                response = requests.post(
                    f"{self.mycelium_api_url}/api/mark-processed",
                    json={'message_ids': message_ids},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    updated_count = result.get('updated_count', 0)
                    print(f"✅ Railway: Marked {updated_count} messages as processed")
                    return updated_count > 0
                else:
                    print(f"⚠️ Railway mark-processed error {response.status_code}, falling back to local")
                    
            except Exception as e:
                print(f"⚠️ Railway mark-processed failed: {e}, falling back to local")
        
        # Fallback to local SQLite
        try:
            mycelium_db_path = os.getenv('MYCELIUM_DB_PATH', './bots/mycelium_bot/mycelium_messages.db')
            conn = sqlite3.connect(mycelium_db_path)
            cursor = conn.cursor()
            
            # Mark multiple messages as processed
            placeholders = ','.join(['?' for _ in message_ids])
            cursor.execute(
                f'UPDATE pending_messages SET processed = TRUE WHERE id IN ({placeholders})',
                message_ids
            )
            
            updated = cursor.rowcount
            conn.commit()
            conn.close()
            
            print(f"📁 Local: Marked {updated} messages as processed")
            return updated > 0
            
        except Exception as e:
            print(f"❌ Error marking local messages as processed: {e}")
            return False
    
    def categorize_transaction(self, description: str, amount: float, is_income: bool) -> Optional[str]:
        """Use Gemma to categorize a transaction (expense or income)"""
        
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
- "iTalki lesson" → Education & Learning
- "programming book" → Education & Learning
- "bootcamp course" → Education & Learning

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
    
    def save_processed_transaction(self, mycelium_id: int, user_id: int, username: str,
                                 timestamp: str, amount: float, description: str, 
                                 category: str, currency: str, is_income: bool, 
                                 raw_message: str) -> bool:
        """Save processed transaction to tree_till.db"""
        try:
            conn = sqlite3.connect(os.getenv('TREE_TILL_DB_PATH', 'tree_till.db'))
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
    
    def process_pending_messages(self) -> bool:
        """Main processing function - the Tree Till awakening!"""
        print("🌳 TREE TILL AWAKENING! 🌳")
        print("🍄 Syncing with mycelium network...")
        
        # Detect mode
        mode = "🌐 Railway Cloud" if self.mycelium_api_url else "🔧 Local Development"
        print(f"Mode: {mode}")
        
        # Get pending messages
        pending = self.get_pending_mycelium_messages()
        
        if not pending:
            print("✅ No new messages from mycelium network!")
            print("🌱 The forest is peaceful... all transactions processed!")
            return False
        
        print(f"🧠 Found {len(pending)} transactions to process with Gemma3n")
        print("=" * 60)
        
        success_count = 0
        processed_ids = []
        
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
                    emoji = "💰" if is_income else "💸"
                    print(f"   ✅ {emoji} Categorized as: {category}")
                    success_count += 1
                    processed_ids.append(mycelium_id)
                else:
                    print(f"   ❌ Failed to save transaction")
            else:
                print(f"   ❌ Failed to categorize")
        
        # Mark all successfully processed messages in one batch
        if processed_ids:
            if self.mark_mycelium_processed(processed_ids):
                print(f"🔄 Successfully synced {len(processed_ids)} transactions with mycelium")
            else:
                print(f"⚠️ Transactions saved locally but sync with mycelium failed")
        
        print("\n" + "=" * 60)
        print(f"🎉 Tree Till processed {success_count}/{len(pending)} transactions!")
        print("🌳 The forest grows wiser with each transaction! 🌱")
        
        return success_count > 0
    
    def show_tree_stats(self):
        """Show statistics from the tree database"""
        try:
            conn = sqlite3.connect(os.getenv('TREE_TILL_DB_PATH', 'tree_till.db'))
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
    print("🌳 TREE TILL - THE COMPLETE FINANCIAL FOREST 🌳")
    print("=" * 55)
    
    # Check Ollama connection
    if not check_ollama_connection():
        exit(1)
    
    print()
    
    # Initialize processor
    processor = TreeTillProcessor()
    
    # Initialize database
    processor.init_tree_database()
    
    print()
    
    # STEP 1: Process pending messages
    processed_new_transactions = processor.process_pending_messages()
    
    # STEP 2: Show current stats
    processor.show_tree_stats()
    
    # STEP 3: Optional assets check-in
    print("\n" + "=" * 55)
    print("💰 ASSETS CHECK-IN")
    print("-" * 30)
    
    if processed_new_transactions:
        print("💡 Since you've got fresh transaction data, this might be a good time")
        print("   to update your asset balances too!")
    else:
        print("💫 No new transactions today, but you can still update your assets.")
    
    print("\n🤔 Would you like to do an assets check-in?")
    print("   💰 This tracks your bank accounts, investments, education fund, and net worth")
    print("   ⚡ Takes 5-15 minutes depending on detail level")
    
    while True:
        choice = input("\nAssets check-in? (y/n): ").lower().strip()
        if choice in ['y', 'yes', 'yep', 'sure', '1']:
            print("\n" + "=" * 55)
            try:
                assets_manager = AssetsManager()
                assets_manager.start_assets_checkin()
                break
            except Exception as e:
                print(f"❌ Error during assets check-in: {e}")
                break
        elif choice in ['n', 'no', 'nope', 'skip', '0']:
            print("\n✅ No problem! Your transaction data is all updated.")
            break
        else:
            print("Please enter 'y' for yes or 'n' for no")
    
    print("\n🌱 Tree Till session complete! Your financial forest is ready for conversations. 🌳")
    print("💬 Run 'python dapple_till.py' for personalized financial advice!")

if __name__ == "__main__":
    main()
