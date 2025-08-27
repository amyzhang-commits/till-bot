import sqlite3
import json
from datetime import datetime, date
from typing import Dict, Optional, Tuple
import re

class AssetsManager:
    def __init__(self):
        self.init_assets_database()
    
    def init_assets_database(self):
        """Initialize the assets database"""
        conn = sqlite3.connect('assets.db')
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
        
        conn.commit()
        conn.close()
        print("🌳 Assets database initialized!")
    
    def get_latest_snapshot(self) -> Optional[Dict]:
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
            prev_net_worth = previous['net_worth']
            print(f"💫 Last update: {prev_date} (Net Worth: ${prev_net_worth:,.2f})")
            print("🌱 Let's see how your financial forest has grown!")
        else:
            print("🌱 Welcome to your first financial forest survey!")
        
        print("\n🤔 What kind of update today?")
        print("   ⚡ Quick (5 min) - Just the basics")
        print("   🔍 Full (15 min) - Complete review")
        
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
        
        # Vanguard (less frequent changes)
        vanguard_changed = input(f"\n📊 Any major Vanguard changes? (y/n): ").lower()
        if vanguard_changed.startswith('y'):
            new_data['vanguard_roth_ira'] = self.ask_amount("   🏛️ Roth IRA", previous.get('vanguard_roth_ira') if previous else None)
            new_data['vanguard_brokerage'] = self.ask_amount("   📈 Brokerage", previous.get('vanguard_brokerage') if previous else None)
        elif previous:
            new_data['vanguard_roth_ira'] = previous.get('vanguard_roth_ira', 0)
            new_data['vanguard_brokerage'] = previous.get('vanguard_brokerage', 0)
        
        # Fill in unchanged values
        for field in ['other_assets', 'other_debts']:
            if field not in new_data and previous:
                new_data[field] = previous.get(field, 0)
        
        new_data['update_type'] = 'quick'
        self.save_snapshot(new_data)
    
    def full_checkin(self, previous: Optional[Dict]):
        """Complete 15-minute review"""
        print("\n🔍 FULL FINANCIAL FOREST SURVEY 🔍")
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
            # Calculate totals
            liquid_total = (
                data.get('boa_checking', 0) + 
                data.get('ufb_savings', 0) + 
                data.get('hsa_cash', 0)
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
            
            # Save to database
            conn = sqlite3.connect('assets.db')
            cursor = conn.cursor()
            
            # Build dynamic insert query
            columns = list(data.keys())
            placeholders = ', '.join(['?' for _ in columns])
            values = list(data.values())
            
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
        """Display the beautiful financial snapshot"""
        print(f"\n🌳 YOUR FINANCIAL FOREST SNAPSHOT 🌳")
        print("=" * 50)
        
        # Liquid assets
        print(f"💰 LIQUID ASSETS:")
        print(f"   🏦 Bank of America: ${data.get('boa_checking', 0):,.2f}")
        print(f"   💎 UFB Savings: ${data.get('ufb_savings', 0):,.2f}")
        print(f"   🏥 HSA Cash: ${data.get('hsa_cash', 0):,.2f}")
        print(f"   💧 Total Liquid: ${data.get('total_liquid', 0):,.2f}")
        
        # Investments
        print(f"\n📈 INVESTMENTS:")
        print(f"   🏛️ Roth IRA: ${data.get('vanguard_roth_ira', 0):,.2f}")
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
        
        # HSA notes if present
        if data.get('hsa_notes'):
            print(f"\n🏥 HSA Strategy Notes:")
            print(f"   {data['hsa_notes']}")
        
        print(f"\n🌱 Financial snapshot saved! Your forest is looking strong! 🌳")

def main():
    print("🌳 TREE TILL ASSETS MANAGER 🌳")
    
    manager = AssetsManager()
    manager.start_assets_checkin()

if __name__ == "__main__":
    main()
