import requests
import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

class TreeTillConversation:
    def __init__(self, model_name="gemma3n:latest", base_url="http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
    
    def get_latest_assets(self) -> Optional[Dict]:
        """Get the most recent asset snapshot"""
        try:
            conn = sqlite3.connect('assets.db')
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
                    'hsa_cash', 'hsa_invested', 'hsa_notes', 'other_assets',
                    'other_debts', 'total_liquid', 'total_invested', 'net_worth',
                    'update_type', 'notes', 'created_at'
                ]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"❌ Error getting assets: {e}")
            return None
    
    def get_recent_expenses(self, days: int = 30) -> List[Dict]:
        """Get recent expenses from tree_till.db"""
        try:
            conn = sqlite3.connect('tree_till.db')
            cursor = conn.cursor()
            
            # Get expenses from last N days
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute('''
            SELECT amount, description, category, currency, is_income, 
                   timestamp, raw_message
            FROM transactions 
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            ''', (cutoff_date,))
            
            rows = cursor.fetchall()
            conn.close()
            
            expenses = []
            for row in rows:
                expenses.append({
                    'amount': row[0],
                    'description': row[1], 
                    'category': row[2],
                    'currency': row[3],
                    'is_income': row[4],
                    'timestamp': row[5],
                    'raw_message': row[6]
                })
            
            return expenses
        except Exception as e:
            print(f"❌ Error getting expenses: {e}")
            return []
    
    def build_context_prompt(self, user_question: str) -> str:
        """Build the context-rich prompt for Tree Till"""
        
        # Get current financial data
        assets = self.get_latest_assets()
        recent_expenses = self.get_recent_expenses(30)
        
        # Build the comprehensive prompt
        prompt = f"""You are Tree Till, a pragmatic financial advisor AI. You have access to the user's complete financial picture and recent spending patterns. Your personality is:

- Practical, thoughtful, and focused on helping them think through decisions
- Asks clarifying questions rather than just cheerleading
- Points out potential blind spots or missing information
- Helps them work through scenarios and trade-offs
- Warm but no-nonsense - like a friend who's good at planning trips
- Uses specific numbers and percentages when relevant
- Flags when you need more information to give good advice
- Doesn't automatically praise their financial position - stays objective

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

💳 DEBTS: ${(assets.get('boa_credit_balance', 0) + assets.get('other_debts', 0)):,.2f}

🏥 HSA TOTAL: ${(assets.get('hsa_cash', 0) + assets.get('hsa_invested', 0)):,.2f}"""

            if assets.get('hsa_notes'):
                prompt += f"\n   HSA Notes: {assets['hsa_notes']}"

            # Calculate emergency fund months (estimate $3k monthly expenses)
            emergency_months = assets['total_liquid'] / 3000
            prompt += f"\n🛡️ EMERGENCY FUND: ~{emergency_months:.1f} months of coverage"

        # Add recent spending context
        if recent_expenses:
            total_expenses = sum(e['amount'] for e in recent_expenses if not e['is_income'])
            total_income = sum(e['amount'] for e in recent_expenses if e['is_income'])
            
            prompt += f"""

RECENT SPENDING (Last 30 days):
💸 Total Expenses: ${total_expenses:,.2f}
💰 Total Income: ${total_income:,.2f}
📊 Net: ${total_income - total_expenses:+,.2f}

Recent transactions:"""
            
            # Show last 10 transactions for context
            for expense in recent_expenses[:10]:
                emoji = "💰" if expense['is_income'] else "💸"
                prompt += f"\n{emoji} {expense['currency']} {expense['amount']:.2f} - {expense['category']} - {expense['description']}"

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

Respond as Tree Till with warmth, wisdom, and specific insights based on their financial data:"""

        return prompt
    
    def chat(self, user_question: str) -> str:
        """Have a conversation with Tree Till"""
        
        prompt = self.build_context_prompt(user_question)
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,  # More creative for conversation
                        "num_predict": 400   # Longer responses for conversation
                    }
                },
                timeout=60
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
    print("🌳 TREE TILL - YOUR FINANCIAL CONVERSATION PARTNER 🌳")
    print("=" * 60)
    print("💫 Hello! I'm Tree Till, your wise financial advisor.")
    print("🧠 I know your complete financial picture and spending patterns.")
    print("🌱 Ask me anything about your finances - spending, saving, planning!")
    print("\n💡 Try things like:")
    print("   • 'I spent $200 on dining this week, is that okay?'")
    print("   • 'How's my emergency fund looking?'")
    print("   • 'Should I be worried about my spending this month?'")
    print("   • 'How am I doing with my HSA strategy?'")
    print("   • 'What's my biggest expense category lately?'")
    print("\n✨ Type 'quit' to exit\n")
    
    # Initialize Tree Till
    tree_till = TreeTillConversation()
    
    # Check if we have financial data
    assets = tree_till.get_latest_assets()
    recent_expenses = tree_till.get_recent_expenses()
    
    if not assets:
        print("🌱 I notice you haven't done an assets check-in yet!")
        print("💡 Run 'python assets_checkin.py' first so I know your complete financial picture.")
        return
    
    if not recent_expenses:
        print("🍄 I don't see any processed expenses yet!")
        print("💡 Make sure you've run 'python process_mycelium.py' to process your spending data.")
        print("🌳 I can still chat about your assets though!\n")
    
    # Start conversation loop
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("\n🌳 Thanks for chatting! Keep growing that financial forest! 🌱✨")
            break
        
        if not user_input:
            continue
        
        print("\n🌳 Tree Till is thinking...\n")
        
        # Get Tree Till's response
        response = tree_till.chat(user_input)
        print(f"🌳 Tree Till: {response}\n")

if __name__ == "__main__":
    main()
