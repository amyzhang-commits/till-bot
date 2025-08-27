import sqlite3
import pandas as pd
from datetime import datetime

def view_assets_schema():
    """Show the assets database schema"""
    try:
        conn = sqlite3.connect('assets.db')
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(asset_snapshots)")
        columns = cursor.fetchall()
        
        print("🌳 ASSETS DATABASE SCHEMA 🌳")
        print("=" * 50)
        for col in columns:
            null_info = "NOT NULL" if col[3] else "NULL OK"
            default = f" (default: {col[4]})" if col[4] else ""
            print(f"{col[1]:20} | {col[2]:12} | {null_info}{default}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error reading schema: {e}")

def view_latest_snapshot():
    """View the most recent asset snapshot with beautiful formatting"""
    try:
        conn = sqlite3.connect('assets.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM asset_snapshots 
        ORDER BY snapshot_date DESC, created_at DESC 
        LIMIT 1
        ''')
        
        row = cursor.fetchone()
        
        if not row:
            print("📊 No asset snapshots found yet!")
            print("💡 Run assets_checkin.py to create your first financial forest survey!")
            return
        
        # Get column names
        cursor.execute("PRAGMA table_info(asset_snapshots)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Create dictionary
        data = dict(zip(columns, row))
        
        conn.close()
        
        print("🌳 YOUR LATEST FINANCIAL FOREST SNAPSHOT 🌳")
        print("=" * 60)
        print(f"📅 Snapshot Date: {data['snapshot_date']}")
        print(f"⚡ Update Type: {data['update_type'].title()}")
        print(f"🕐 Created: {data['created_at']}")
        
        print(f"\n💰 LIQUID ASSETS (Your Emergency Fund):")
        print(f"   🏦 Bank of America Checking: ${data.get('boa_checking', 0):>10,.2f}")
        print(f"   💎 UFB Direct Savings:       ${data.get('ufb_savings', 0):>10,.2f}")
        print(f"   🏥 HSA Cash Position:        ${data.get('hsa_cash', 0):>10,.2f}")
        print(f"   ──────────────────────────────────────────")
        print(f"   💧 Total Liquid Assets:      ${data.get('total_liquid', 0):>10,.2f}")
        
        print(f"\n📈 INVESTMENTS (Your Future Self):")
        print(f"   🏛️  Vanguard Roth IRA:       ${data.get('vanguard_roth_ira', 0):>10,.2f}")
        print(f"   📊 Vanguard Brokerage:       ${data.get('vanguard_brokerage', 0):>10,.2f}")
        print(f"   🏥 HSA Invested Portion:     ${data.get('hsa_invested', 0):>10,.2f}")
        if data.get('other_assets', 0) > 0:
            print(f"   🏠 Other Assets:             ${data.get('other_assets', 0):>10,.2f}")
        print(f"   ──────────────────────────────────────────")
        print(f"   📈 Total Invested:           ${data.get('total_invested', 0):>10,.2f}")
        
        # Show debts if any
        total_debt = (data.get('boa_credit_balance', 0) or 0) + (data.get('other_debts', 0) or 0)
        if total_debt > 0:
            print(f"\n💳 DEBTS (What You Owe):")
            if data.get('boa_credit_balance', 0):
                print(f"   💳 Credit Card Balance:      ${data.get('boa_credit_balance', 0):>10,.2f}")
            if data.get('other_debts', 0):
                print(f"   🏠 Other Debts:              ${data.get('other_debts', 0):>10,.2f}")
            print(f"   ──────────────────────────────────────────")
            print(f"   💸 Total Debt:               ${total_debt:>10,.2f}")
        
        # Net worth celebration
        net_worth = data.get('net_worth', 0)
        print(f"\n✨ NET WORTH: ${net_worth:>25,.2f} ✨")
        
        # HSA special section
        total_hsa = (data.get('hsa_cash', 0) or 0) + (data.get('hsa_invested', 0) or 0)
        if total_hsa > 0:
            hsa_cash_pct = (data.get('hsa_cash', 0) / total_hsa * 100) if total_hsa > 0 else 0
            print(f"\n🏥 HSA STRATEGY SPOTLIGHT:")
            print(f"   💰 Total HSA: ${total_hsa:,.2f}")
            print(f"   💸 Cash: ${data.get('hsa_cash', 0):,.2f} ({hsa_cash_pct:.1f}%)")
            print(f"   📈 Invested: ${data.get('hsa_invested', 0):,.2f} ({100-hsa_cash_pct:.1f}%)")
            if data.get('hsa_notes'):
                print(f"   📝 Notes: {data['hsa_notes']}")
        
        # Analysis insights
        print(f"\n🧠 TREE TILL INSIGHTS:")
        
        # Emergency fund analysis (assuming monthly expenses around $3000)
        estimated_monthly = 3000  # We could get this from expense data later
        emergency_months = data.get('total_liquid', 0) / estimated_monthly
        print(f"   🛡️  Emergency Fund: ~{emergency_months:.1f} months of expenses")
        
        # Investment allocation
        total_assets = data.get('total_liquid', 0) + data.get('total_invested', 0)
        if total_assets > 0:
            invested_pct = data.get('total_invested', 0) / total_assets * 100
            print(f"   📊 Investment Allocation: {invested_pct:.1f}% invested, {100-invested_pct:.1f}% liquid")
        
        # Notes if any
        if data.get('notes'):
            print(f"\n📝 NOTES:")
            print(f"   {data['notes']}")
        
    except Exception as e:
        print(f"Error reading assets: {e}")

def view_all_snapshots():
    """Show history of all asset snapshots"""
    try:
        conn = sqlite3.connect('assets.db')
        
        query = '''
        SELECT snapshot_date, net_worth, total_liquid, total_invested, update_type, notes
        FROM asset_snapshots 
        ORDER BY snapshot_date DESC, created_at DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(df) == 0:
            print("📊 No snapshots found!")
            return
        
        print(f"\n📈 FINANCIAL FOREST HISTORY 📈")
        print("=" * 60)
        print(f"Total snapshots: {len(df)}")
        
        for i, row in df.iterrows():
            print(f"\n📅 {row['snapshot_date']} ({row['update_type']})")
            print(f"   ✨ Net Worth: ${row['net_worth']:,.2f}")
            print(f"   💧 Liquid: ${row['total_liquid']:,.2f} | 📈 Invested: ${row['total_invested']:,.2f}")
            if pd.notna(row['notes']) and row['notes']:
                print(f"   📝 {row['notes']}")
        
        # Growth analysis if multiple snapshots
        if len(df) > 1:
            latest = df.iloc[0]
            previous = df.iloc[1]
            growth = latest['net_worth'] - previous['net_worth']
            growth_pct = (growth / previous['net_worth'] * 100) if previous['net_worth'] != 0 else 0
            
            print(f"\n📊 GROWTH ANALYSIS:")
            print(f"   📈 Net Worth Change: ${growth:+,.2f} ({growth_pct:+.1f}%)")
            print(f"   🗓️  Since: {previous['snapshot_date']}")
        
    except Exception as e:
        print(f"Error reading snapshot history: {e}")

def main():
    print("🌳 TREE TILL ASSETS VIEWER 🌳")
    print("Looking into your financial forest database...")
    print()
    
    # Show schema
    view_assets_schema()
    print()
    
    # Show latest snapshot
    view_latest_snapshot()
    
    # Show history
    view_all_snapshots()
    
    print(f"\n🌱 This is what Tree Till sees when making financial decisions for you! 🌳")

if __name__ == "__main__":
    main()
