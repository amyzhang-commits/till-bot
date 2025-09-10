import requests
import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from contextlib import contextmanager

# Import our shared configuration and helpers
try:
    from .config import (
        DEFAULT_OLLAMA_BASE_URL, DEFAULT_MODEL_NAME, OLLAMA_TIMEOUT,
        ASSETS_COLUMNS, ASSETS_NUMERIC_FIELDS
    )
    from .main import ValidationHelpers
except ImportError:
    # Fallback for direct execution
    from config import (
        DEFAULT_OLLAMA_BASE_URL, DEFAULT_MODEL_NAME, OLLAMA_TIMEOUT,
        ASSETS_COLUMNS, ASSETS_NUMERIC_FIELDS
    )
    from main import ValidationHelpers


# =======================
# DATABASE CONTEXT MANAGER
# =======================

@contextmanager
def get_db_connection(db_path):
    """
    Context manager for database connections.
    Ensures connections are properly closed even if errors occur.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

class DappleTillConversation:
    """
    Dapple Till - The wise financial garden spirit that provides poetic financial advice.
    Now enhanced with proper multi-currency handling and optimized database operations.
    """
    
    def __init__(self, model_name=DEFAULT_MODEL_NAME, base_url=DEFAULT_OLLAMA_BASE_URL):
        self.model_name = model_name
        self.base_url = base_url
        
        # Get the directory where this script is located
        self.script_dir = Path(__file__).parent.absolute()
        
        # Define database paths relative to script location
        self.assets_db_path = self.script_dir / 'assets.db'
        self.tree_db_path = self.script_dir / 'tree_till.db'
        
        # Check if databases exist and only show paths if there's a problem
        missing_dbs = []
        if not self.assets_db_path.exists():
            missing_dbs.append(f"assets.db (expected at {self.assets_db_path})")
        if not self.tree_db_path.exists():
            missing_dbs.append(f"tree_till.db (expected at {self.tree_db_path})")
        
        if missing_dbs:
            print(f"⚠️  Warning: Missing databases:")
            for db in missing_dbs:
                print(f"   📁 {db}")
        else:
            print(f"🌿 Database connections ready!")
    
    def get_latest_assets(self) -> Optional[Dict]:
        """Get the most recent asset snapshot with proper column mapping and validation"""
        try:
            with get_db_connection(str(self.assets_db_path)) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT * FROM asset_snapshots 
                ORDER BY snapshot_date DESC, created_at DESC 
                LIMIT 1
                ''')
                
                row = cursor.fetchone()
                
                if row:
                    # Use the centralized column mapping from config
                    data = dict(zip(ASSETS_COLUMNS, row))
                    
                    # Use the helper method to convert numeric fields safely
                    data = ValidationHelpers.convert_numeric_fields(data, ASSETS_NUMERIC_FIELDS)
                    
                    return data
                return None
        except Exception as e:
            print(f"❌ Error getting assets: {e}")
            return None
    
    def get_recent_transactions(self, days: int = 30) -> List[Dict]:
        """Get recent transactions from tree_till.db with proper database handling"""
        try:
            with get_db_connection(str(self.tree_db_path)) as conn:
                cursor = conn.cursor()
                
                # Get transactions from last N days
                cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                
                cursor.execute('''
                SELECT amount, description, category, currency, is_income, 
                       timestamp, raw_message
                FROM transactions 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                ''', (cutoff_date,))
                
                rows = cursor.fetchall()
                
                transactions = []
                for row in rows:
                    transactions.append({
                        'amount': row[0],
                        'description': row[1], 
                        'category': row[2],
                        'currency': row[3],
                        'is_income': row[4],
                        'timestamp': row[5],
                        'raw_message': row[6]
                    })
                
                return transactions
        except Exception as e:
            print(f"❌ Error getting transactions: {e}")
            return []

    def build_context_prompt(self, user_question: str) -> str:
        """Build the context-rich prompt for Dapple Till"""
        
        # Get current financial data
        assets = self.get_latest_assets()
        recent_transactions = self.get_recent_transactions(30)
        
        # Calculate debt values BEFORE the f-string with safe conversion
        try:
            credit_balance = float(assets.get('boa_credit_balance', 0) or 0) if assets else 0
        except (ValueError, TypeError):
            credit_balance = 0

        try:
            other_debts = float(assets.get('other_debts', 0) or 0) if assets else 0
        except (ValueError, TypeError):
            other_debts = 0
            
        total_debt = credit_balance + other_debts
        
        prompt = f"""You are Dapple Till, a witty financial garden spirit. 
You always respond in poetic form – haiku, limerick, or rhyming verse. 
Your poems should sound clever, encouraging, and a bit tongue-in-cheek. 
They must include at least one concrete number or metric from the "Financial Context."
Calculate relationships between numbers - percentages, ratios, comparisons - to make the data meaningful.
Never invent numbers. Always use the ones given.
Keep the poem light but not dismissive – humorous wisdom with a grounding in truth.

After your poem, end with "Consider these questions:" followed by exactly three practical questions related to their message that would help them reflect further or research their situation. End the final question with a small leaf emoji 🌱

CURRENT FINANCIAL SNAPSHOT:"""

        if assets:
            prompt += f"""
📊 NET WORTH: ${assets['net_worth']:,.2f}
💧 LIQUID ASSETS: ${assets['total_liquid']:,.2f}
   - Bank of America: ${assets.get('boa_checking', 0):,.2f}
   - UFB Savings: ${assets.get('ufb_savings', 0):,.2f}
   - HSA Cash: ${assets.get('hsa_cash', 0):,.2f}

📈 INVESTMENTS: ${assets['total_invested']:,.2f}
   - Roth IRA: ${assets.get('vanguard_roth_ira', 0):,.2f}
   - Brokerage: ${assets.get('vanguard_brokerage', 0):,.2f}
   - HSA Invested: ${assets.get('hsa_invested', 0):,.2f}

💳 DEBTS: ${total_debt:,.2f}

🏥 HSA TOTAL: ${(assets.get('hsa_cash', 0) + assets.get('hsa_invested', 0)):,.2f}"""

            if assets.get('hsa_notes'):
                prompt += f"\n   HSA Notes: {assets['hsa_notes']}"

            # Calculate emergency fund months (estimate $3k monthly expenses)
            emergency_months = assets['total_liquid'] / 3000
            prompt += f"\n🛡️ EMERGENCY FUND: ~{emergency_months:.1f} months of coverage"

        # Add recent spending context with proper multi-currency handling
        if recent_transactions:
            # Group transactions by currency to avoid meaningless mixed-currency sums
            currency_summary = {}
            for transaction in recent_transactions:
                currency = transaction['currency']
                if currency not in currency_summary:
                    currency_summary[currency] = {'expenses': 0, 'income': 0, 'count': 0}
                
                if transaction['is_income']:
                    currency_summary[currency]['income'] += transaction['amount']
                else:
                    currency_summary[currency]['expenses'] += transaction['amount']
                currency_summary[currency]['count'] += 1
            
            prompt += f"""

RECENT SPENDING (Last 30 days) - BY CURRENCY:"""
            
            for currency, totals in currency_summary.items():
                net_position = totals['income'] - totals['expenses']
                prompt += f"""
💵 {currency}:
  💸 Expenses: {totals['expenses']:,.2f}
  💰 Income: {totals['income']:,.2f}
  🎯 Net: {net_position:+,.2f} ({totals['count']} transactions)"""
            
            prompt += f"""

Recent transactions:"""
            
            # Show last 10 transactions for context, grouped by currency
            for transaction in recent_transactions[:10]:
                emoji = "💰" if transaction['is_income'] else "💸"
                prompt += f"\n{emoji} {transaction['currency']} {transaction['amount']:.2f} - {transaction['category']} - {transaction['description']}"

        prompt += f"""

CONVERSATION GUIDELINES:
- Ask clarifying questions when you need more specific information
- Point out what information might be missing for better advice
- Help them think through scenarios and trade-offs
- Use their actual numbers to illustrate points
- Flag potential risks or blind spots
- Stay objective - don't automatically praise or worry
- Keep responses focused and practical
- If they're asking about big decisions, break it down into components

USER QUESTION: "{user_question}"

Respond as Dapple Till with warmth, wisdom, and specific insights based on their financial data:"""

        return prompt
    
    def chat(self, user_question: str) -> str:
        """Have a conversation with Dapple Till"""
        
        prompt = self.build_context_prompt(user_question)
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.9,  # Higher creativity for more varied responses
                        "num_predict": 500,  # Allow longer, more elaborate poems
                        "top_p": 0.9        # Add nucleus sampling for more variety
                    }
                },
                timeout=OLLAMA_TIMEOUT  # Use centralized timeout constant
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["response"].strip()
            else:
                return f"❌ Sorry, I'm having trouble connecting to my financial wisdom right now. (Error: {response.status_code})"
                
        except requests.exceptions.RequestException as e:
            return f"❌ I can't access my financial knowledge base right now. Error: {e}"
        except Exception as e:
            return f"❌ Something went wrong with my thinking process: {e}"

def main():
    print("🌿 DAPPLE TILL 🌿")
    print("="*60)
    print("💫 Hello! I'm Dapple Till, your wise financial advisor.")
    print("🔍 I know your complete financial picture and spending patterns.")
    print("🌱 Ask me anything about your finances - spending, saving, planning!")
    print("\n💡 Try things like:")
    print("   • 'I spent $200 on dining this week, is that okay?'")
    print("   • 'How's my emergency fund looking?'")
    print("   • 'Should I be worried about my spending this month?'")
    print("   • 'How am I doing with my HSA strategy?'")
    print("   • 'What's my biggest expense category lately?'")
    print("\n✨ Type 'quit' to exit\n")
    
    # Initialize Dapple Till
    dapple_till = DappleTillConversation()
    
    # Check if we have financial data
    assets = dapple_till.get_latest_assets()
    recent_transactions = dapple_till.get_recent_transactions()
    
    if not assets:
        print("🌱 I notice you haven't done an assets check-in yet!")
        print("💡 Run 'python main.py' first so I know your complete financial picture.")
        return
    
    if not recent_transactions:
        print("🍄 I don't see any processed transactions yet!")
        print("💡 Make sure you've run 'python main.py' to process your spending data.")
        print("🌿 I can still chat about your assets though!\n")
    
    # Start conversation loop
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("\n🌿 Thanks for chatting! Keep growing that financial forest! 🌱✨")
            break
        
        if not user_input:
            continue
        
        print("\n🌿 Dapple Till is thinking...\n")
        
        # Get Dapple Till's response
        response = dapple_till.chat(user_input)
        print(f"🌿 Dapple Till: {response}\n")

if __name__ == "__main__":
    main()
