import sqlite3
import requests
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import json
from dataclasses import dataclass
from calendar import month_name

@dataclass
class SummaryPeriod:
    start_date: date
    end_date: date
    period_type: str  # 'weekly', 'monthly', 'quarterly', 'yearly', 'custom'
    period_name: str  # 'Week of Sep 2', 'January 2025', 'Q1 2025', etc.

class FinancialSummaryGenerator:
    def __init__(self, model_name="gemma3n:latest", base_url="http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.init_summaries_database()
    
    def init_summaries_database(self):
        """Initialize the financial summaries database"""
        conn = sqlite3.connect('financial_summaries.db')
        cursor = conn.cursor()
        
        # Main summaries table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_type TEXT NOT NULL,
            period_name TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            total_income REAL DEFAULT 0,
            total_expenses REAL DEFAULT 0,
            net_position REAL DEFAULT 0,
            transaction_count INTEGER DEFAULT 0,
            top_category TEXT,
            top_category_amount REAL DEFAULT 0,
            summary_data TEXT,  -- JSON with detailed breakdowns
            ai_insights TEXT,   -- Gemma3n generated insights
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(period_type, start_date, end_date)
        )
        ''')
        
        # Category summaries table (for tax records)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_id INTEGER,
            category TEXT NOT NULL,
            total_amount REAL NOT NULL,
            transaction_count INTEGER NOT NULL,
            is_income BOOLEAN DEFAULT FALSE,
            avg_transaction REAL,
            largest_transaction REAL,
            smallest_transaction REAL,
            FOREIGN KEY (summary_id) REFERENCES financial_summaries (id)
        )
        ''')
        
        # Weekly patterns table for trend analysis
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS weekly_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start DATE NOT NULL,
            category TEXT NOT NULL,
            total_amount REAL NOT NULL,
            transaction_count INTEGER NOT NULL,
            is_income BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(week_start, category, is_income)
        )
        ''')
        
        conn.commit()
        conn.close()
        print("Financial summaries database initialized!")
    
    def get_week_boundaries(self, weeks_ago=0):
        """Get start/end dates for a week (0=current, 1=last week, etc.)"""
        today = date.today()
        days_since_monday = today.weekday()  # Monday=0, Sunday=6
        
        # Find this week's Monday
        current_monday = today - timedelta(days=days_since_monday)
        target_monday = current_monday - timedelta(weeks=weeks_ago)
        target_sunday = target_monday + timedelta(days=6)
        
        return target_monday, target_sunday

    def create_weekly_summary(self, weeks_ago=0) -> Optional[int]:
        """Create a summary for a specific week (0=current, 1=last week, etc.)"""
        start_date, end_date = self.get_week_boundaries(weeks_ago)
        
        # Create nice period name
        if weeks_ago == 0:
            period_name = f"This Week ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"
        elif weeks_ago == 1:
            period_name = f"Last Week ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"
        else:
            period_name = f"Week of {start_date.strftime('%b %d, %Y')}"
        
        period = SummaryPeriod(
            start_date=start_date,
            end_date=end_date,
            period_type='weekly',
            period_name=period_name
        )
        
        print(f"Generating summary for {period.period_name}...")
        
        # Get the data
        data = self.get_period_data(period)
        
        if not data.get('transactions'):
            print(f"No transactions found for {period.period_name}")
            return None
        
        print(f"Found ${data['total_income']:.2f} income, ${data['total_expenses']:.2f} expenses")
        print(f"Generating AI insights...")
        
        # Generate AI insights with weekly context
        ai_insights = self.generate_weekly_ai_insights(period, data)
        
        # Update weekly patterns table for trend tracking
        self.update_weekly_patterns(start_date, data)
        
        # Save everything
        summary_id = self.save_summary(period, data, ai_insights)
        
        if summary_id:
            print(f"Weekly summary saved! ID: {summary_id}")
            return summary_id
        else:
            print("Failed to save summary")
            return None

    def update_weekly_patterns(self, week_start: date, data: Dict):
        """Update the weekly patterns table for trend analysis"""
        try:
            conn = sqlite3.connect('financial_summaries.db')
            cursor = conn.cursor()
            
            # Clear existing patterns for this week
            cursor.execute('DELETE FROM weekly_patterns WHERE week_start = ?', (week_start.isoformat(),))
            
            # Insert new patterns
            for category, cat_data in data.get('category_data', {}).items():
                cursor.execute('''
                INSERT INTO weekly_patterns (week_start, category, total_amount, transaction_count, is_income)
                VALUES (?, ?, ?, ?, ?)
                ''', (
                    week_start.isoformat(),
                    category,
                    cat_data['total'],
                    cat_data['count'],
                    cat_data['is_income']
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error updating weekly patterns: {e}")

    def generate_weekly_ai_insights(self, period: SummaryPeriod, data: Dict) -> str:
        """Generate AI insights with weekly comparison context"""
        
        # Get previous weeks for comparison
        prev_week_data = None
        if period.start_date > date(2025, 9, 1):  # Only compare if not the very first week
            prev_start = period.start_date - timedelta(weeks=1)
            try:
                conn = sqlite3.connect('financial_summaries.db')
                cursor = conn.cursor()
                cursor.execute('''
                SELECT total_income, total_expenses, net_position
                FROM financial_summaries 
                WHERE period_type = 'weekly' AND start_date = ?
                ''', (prev_start.isoformat(),))
                prev_result = cursor.fetchone()
                conn.close()
                
                if prev_result:
                    prev_week_data = {
                        'income': prev_result[0],
                        'expenses': prev_result[1],
                        'net': prev_result[2]
                    }
            except Exception:
                pass  # No previous week data available
        
        # Build context for AI
        insights_prompt = f"""You are Till, a wise financial advisor. Generate insights about this weekly financial summary.

CURRENT WEEK ({period.period_name}):
- Total Income: ${data['total_income']:.2f}
- Total Expenses: ${data['total_expenses']:.2f}
- Net Position: ${data['net_position']:+.2f}
- Transaction Count: {data['transaction_count']}"""

        # Add comparison context if available
        if prev_week_data:
            expense_change = data['total_expenses'] - prev_week_data['expenses']
            income_change = data['total_income'] - prev_week_data['income']
            insights_prompt += f"""

COMPARED TO LAST WEEK:
- Expense Change: ${expense_change:+.2f}
- Income Change: ${income_change:+.2f}
- Spending trend: {'Higher' if expense_change > 0 else 'Lower' if expense_change < 0 else 'Similar'}"""

        insights_prompt += f"""

CATEGORY BREAKDOWN:"""

        for category, cat_data in data.get('category_data', {}).items():
            emoji = "💰" if cat_data['is_income'] else "💸"
            insights_prompt += f"\n{emoji} {category}: ${cat_data['total']:.2f} ({cat_data['count']} transactions)"

        insights_prompt += f"""

Provide practical weekly insights in 2-3 paragraphs covering:
1. How this week compares to patterns (if comparison data available)
2. Notable spending observations - what stands out this week?
3. One actionable insight for the upcoming week

Be encouraging and focus on patterns rather than judgment. This is for personal reflection on weekly spending habits."""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": insights_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 400
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["response"].strip()
            else:
                return f"AI insights unavailable (API error: {response.status_code})"
                
        except Exception as e:
            return f"AI insights unavailable (error: {e})"

    def get_period_data(self, period: SummaryPeriod) -> Dict:
        """Get all financial data for a specific period"""
        try:
            conn = sqlite3.connect('tree_till.db')
            cursor = conn.cursor()
            
            # Get all transactions in period
            cursor.execute('''
            SELECT id, amount, description, category, currency, is_income, 
                   timestamp, raw_message, user_id
            FROM transactions 
            WHERE date(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp DESC
            ''', (period.start_date.isoformat(), period.end_date.isoformat()))
            
            transactions = cursor.fetchall()
            conn.close()
            
            # Process the data
            total_income = sum(t[1] for t in transactions if t[5])  # is_income
            total_expenses = sum(t[1] for t in transactions if not t[5])
            
            # Category breakdowns
            category_data = {}
            for t in transactions:
                category = t[3]
                amount = t[1]
                is_income = t[5]
                
                if category not in category_data:
                    category_data[category] = {
                        'total': 0, 'count': 0, 'transactions': [],
                        'is_income': is_income, 'amounts': []
                    }
                
                category_data[category]['total'] += amount
                category_data[category]['count'] += 1
                category_data[category]['amounts'].append(amount)
                category_data[category]['transactions'].append({
                    'id': t[0], 'amount': amount, 'description': t[2],
                    'date': t[6], 'raw_message': t[7]
                })
            
            # Calculate category stats
            for cat_data in category_data.values():
                amounts = cat_data['amounts']
                cat_data['avg'] = sum(amounts) / len(amounts)
                cat_data['max'] = max(amounts)
                cat_data['min'] = min(amounts)
            
            # Find top category (excluding income categories)
            expense_categories = {k: v for k, v in category_data.items() 
                                if not v['is_income']}
            top_category = max(expense_categories.items(), 
                             key=lambda x: x[1]['total']) if expense_categories else None
            
            return {
                'transactions': transactions,
                'total_income': total_income,
                'total_expenses': total_expenses,
                'net_position': total_income - total_expenses,
                'transaction_count': len(transactions),
                'category_data': category_data,
                'top_category': top_category[0] if top_category else None,
                'top_category_amount': top_category[1]['total'] if top_category else 0
            }
            
        except Exception as e:
            print(f"Error getting period data: {e}")
            return {}

    def generate_ai_insights(self, period: SummaryPeriod, data: Dict) -> str:
        """Generate AI insights about the financial period"""
        
        # Build context for AI
        insights_prompt = f"""You are Till, a wise financial advisor. Generate practical insights about this {period.period_type} financial summary for {period.period_name}.

FINANCIAL DATA:
- Total Income: ${data['total_income']:.2f}
- Total Expenses: ${data['total_expenses']:.2f}
- Net Position: ${data['net_position']:+.2f}
- Transaction Count: {data['transaction_count']}

CATEGORY BREAKDOWN:"""

        for category, cat_data in data.get('category_data', {}).items():
            emoji = "💰" if cat_data['is_income'] else "💸"
            insights_prompt += f"\n{emoji} {category}: ${cat_data['total']:.2f} ({cat_data['count']} transactions)"
            insights_prompt += f" - Avg: ${cat_data['avg']:.2f}, Range: ${cat_data['min']:.2f}-${cat_data['max']:.2f}"

        insights_prompt += f"""

Provide practical insights in 3-4 paragraphs covering:
1. Overall financial health for this period
2. Spending pattern observations (what's normal vs unusual)
3. Category-specific insights (biggest categories, trends)
4. Actionable recommendations for next period

Be encouraging but honest. Focus on concrete observations from the data. Keep it conversational but professional - this is for personal financial records."""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": insights_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 500
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["response"].strip()
            else:
                return f"AI insights unavailable (API error: {response.status_code})"
                
        except Exception as e:
            return f"AI insights unavailable (error: {e})"
    
    def save_summary(self, period: SummaryPeriod, data: Dict, ai_insights: str) -> int:
        """Save the complete summary to database"""
        try:
            conn = sqlite3.connect('financial_summaries.db')
            cursor = conn.cursor()
            
            # Prepare summary data as JSON
            summary_data = {
                'period': {
                    'type': period.period_type,
                    'name': period.period_name,
                    'start': period.start_date.isoformat(),
                    'end': period.end_date.isoformat()
                },
                'totals': {
                    'income': data['total_income'],
                    'expenses': data['total_expenses'],
                    'net': data['net_position'],
                    'transaction_count': data['transaction_count']
                },
                'categories': {}
            }
            
            # Add category details
            for category, cat_data in data.get('category_data', {}).items():
                summary_data['categories'][category] = {
                    'total': cat_data['total'],
                    'count': cat_data['count'],
                    'average': cat_data['avg'],
                    'max': cat_data['max'],
                    'min': cat_data['min'],
                    'is_income': cat_data['is_income']
                }
            
            # Insert main summary
            cursor.execute('''
            INSERT OR REPLACE INTO financial_summaries 
            (period_type, period_name, start_date, end_date, total_income, 
             total_expenses, net_position, transaction_count, top_category, 
             top_category_amount, summary_data, ai_insights)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                period.period_type, period.period_name,
                period.start_date.isoformat(), period.end_date.isoformat(),
                data['total_income'], data['total_expenses'], data['net_position'],
                data['transaction_count'], data.get('top_category'),
                data.get('top_category_amount', 0),
                json.dumps(summary_data), ai_insights
            ))
            
            summary_id = cursor.lastrowid
            
            # Insert category summaries
            cursor.execute('DELETE FROM category_summaries WHERE summary_id = ?', (summary_id,))
            
            for category, cat_data in data.get('category_data', {}).items():
                cursor.execute('''
                INSERT INTO category_summaries 
                (summary_id, category, total_amount, transaction_count, is_income,
                 avg_transaction, largest_transaction, smallest_transaction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    summary_id, category, cat_data['total'], cat_data['count'],
                    cat_data['is_income'], cat_data['avg'], cat_data['max'], cat_data['min']
                ))
            
            conn.commit()
            conn.close()
            
            return summary_id
            
        except Exception as e:
            print(f"Error saving summary: {e}")
            return 0

    def create_monthly_summary(self, year: int, month: int) -> Optional[int]:
        """Create a summary for a specific month"""
        # Calculate period dates
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        period = SummaryPeriod(
            start_date=start_date,
            end_date=end_date,
            period_type='monthly',
            period_name=f"{month_name[month]} {year}"
        )
        
        print(f"Generating summary for {period.period_name}...")
        
        # Get the data
        data = self.get_period_data(period)
        
        if not data.get('transactions'):
            print(f"No transactions found for {period.period_name}")
            return None
        
        print(f"Found ${data['total_income']:.2f} income, ${data['total_expenses']:.2f} expenses")
        print(f"Generating AI insights...")
        
        # Generate AI insights
        ai_insights = self.generate_ai_insights(period, data)
        
        # Save everything
        summary_id = self.save_summary(period, data, ai_insights)
        
        if summary_id:
            print(f"Summary saved! ID: {summary_id}")
            return summary_id
        else:
            print("Failed to save summary")
            return None
    
    def create_quarterly_summary(self, year: int, quarter: int) -> Optional[int]:
        """Create a summary for a specific quarter (1-4)"""
        if quarter == 1:
            start_month, end_month = 1, 3
        elif quarter == 2:
            start_month, end_month = 4, 6
        elif quarter == 3:
            start_month, end_month = 7, 9
        else:  # quarter == 4
            start_month, end_month = 10, 12
        
        start_date = date(year, start_month, 1)
        end_date = date(year, end_month + 1, 1) - timedelta(days=1) if end_month < 12 else date(year, 12, 31)
        
        period = SummaryPeriod(
            start_date=start_date,
            end_date=end_date,
            period_type='quarterly',
            period_name=f"Q{quarter} {year}"
        )
        
        print(f"Generating quarterly summary for {period.period_name}...")
        
        data = self.get_period_data(period)
        if not data.get('transactions'):
            print(f"No transactions found for {period.period_name}")
            return None
        
        ai_insights = self.generate_ai_insights(period, data)
        summary_id = self.save_summary(period, data, ai_insights)
        
        if summary_id:
            print(f"Quarterly summary saved! ID: {summary_id}")
        
        return summary_id

    def compare_weeks(self, weeks_to_compare=4):
        """Show comparison of recent weeks"""
        print(f"\nWEEKLY TRENDS (Last {weeks_to_compare} weeks)")
        print("=" * 50)
        
        try:
            conn = sqlite3.connect('financial_summaries.db')
            cursor = conn.cursor()
            
            # Get recent weekly summaries
            cursor.execute('''
            SELECT period_name, total_expenses, total_income, net_position, start_date
            FROM financial_summaries 
            WHERE period_type = 'weekly'
            ORDER BY start_date DESC
            LIMIT ?
            ''', (weeks_to_compare,))
            
            weeks = cursor.fetchall()
            conn.close()
            
            if not weeks:
                print("No weekly summaries available yet")
                return
            
            # Show each week
            for week in reversed(weeks):  # Show chronologically
                period_name, expenses, income, net, start_date = week
                net_emoji = "📈" if net >= 0 else "📉"
                print(f"{net_emoji} {period_name}")
                print(f"    💸 Spent: ${expenses:.2f} | 💰 Earned: ${income:.2f} | Net: ${net:+.2f}")
            
            # Show spending trend
            if len(weeks) >= 2:
                recent_avg = sum(w[1] for w in weeks[:2]) / 2  # Last 2 weeks average
                older_avg = sum(w[1] for w in weeks[2:]) / len(weeks[2:]) if len(weeks) > 2 else recent_avg
                
                if recent_avg > older_avg * 1.1:
                    print(f"\n📊 Trend: Spending increasing (recent avg: ${recent_avg:.2f})")
                elif recent_avg < older_avg * 0.9:
                    print(f"\n📊 Trend: Spending decreasing (recent avg: ${recent_avg:.2f})")
                else:
                    print(f"\n📊 Trend: Spending stable (recent avg: ${recent_avg:.2f})")
            
        except Exception as e:
            print(f"Error comparing weeks: {e}")
    
    def export_tax_records(self, year: int) -> str:
        """Export tax-relevant records for a year"""
        try:
            conn = sqlite3.connect('tree_till.db')
            cursor = conn.cursor()
            
            # Get all transactions for the year
            cursor.execute('''
            SELECT amount, description, category, timestamp, raw_message
            FROM transactions 
            WHERE strftime('%Y', timestamp) = ?
            ORDER BY timestamp
            ''', (str(year),))
            
            transactions = cursor.fetchall()
            conn.close()
            
            if not transactions:
                return f"No transactions found for {year}"
            
            # Categorize for tax purposes
            business_categories = [
                "Professional & Work", "Education & Learning", "Transportation"
            ]
            
            tax_report = f"TAX RECORDS FOR {year}\n"
            tax_report += "=" * 50 + "\n\n"
            
            # Business expenses
            business_total = 0
            tax_report += "POTENTIAL BUSINESS DEDUCTIONS:\n"
            tax_report += "-" * 30 + "\n"
            
            for t in transactions:
                amount, desc, category, timestamp, raw = t
                if category in business_categories:
                    tax_report += f"{timestamp[:10]} | {category} | ${amount:.2f} | {desc}\n"
                    business_total += amount
            
            tax_report += f"\nTotal Potential Business Deductions: ${business_total:.2f}\n\n"
            
            # Category summary
            tax_report += "CATEGORY TOTALS:\n"
            tax_report += "-" * 20 + "\n"
            
            categories = {}
            for t in transactions:
                category = t[2]
                amount = t[0]
                categories[category] = categories.get(category, 0) + amount
            
            for category, total in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                tax_report += f"{category}: ${total:.2f}\n"
            
            # Save to file
            filename = f"tax_records_{year}.txt"
            with open(filename, 'w') as f:
                f.write(tax_report)
            
            return f"Tax records exported to {filename}"
            
        except Exception as e:
            return f"Error exporting tax records: {e}"
    
    def view_summary(self, summary_id: int):
        """Display a saved summary"""
        try:
            conn = sqlite3.connect('financial_summaries.db')
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT period_name, total_income, total_expenses, net_position,
                   transaction_count, ai_insights, created_at
            FROM financial_summaries WHERE id = ?
            ''', (summary_id,))
            
            summary = cursor.fetchone()
            if not summary:
                print(f"Summary {summary_id} not found")
                return
            
            # Get category breakdown
            cursor.execute('''
            SELECT category, total_amount, transaction_count, is_income,
                   avg_transaction, largest_transaction
            FROM category_summaries WHERE summary_id = ?
            ORDER BY total_amount DESC
            ''', (summary_id,))
            
            categories = cursor.fetchall()
            conn.close()
            
            # Display the summary
            print(f"\nFINANCIAL SUMMARY: {summary[0]}")
            print("=" * 50)
            print(f"💰 Total Income: ${summary[1]:,.2f}")
            print(f"💸 Total Expenses: ${summary[2]:,.2f}")
            print(f"📊 Net Position: ${summary[3]:+,.2f}")
            print(f"📝 Transactions: {summary[4]}")
            print(f"📅 Generated: {summary[6][:16]}")
            
            print(f"\n💡 AI INSIGHTS:")
            print("-" * 20)
            print(summary[5])
            
            print(f"\nCATEGORY BREAKDOWN:")
            print("-" * 30)
            for cat in categories:
                category, total, count, is_income, avg, largest = cat
                emoji = "💰" if is_income else "💸"
                print(f"{emoji} {category}: ${total:,.2f} ({count} transactions)")
                print(f"    Average: ${avg:.2f} | Largest: ${largest:.2f}")
            
        except Exception as e:
            print(f"Error viewing summary: {e}")

def main():
    print("FINANCIAL SUMMARY GENERATOR")
    print("=" * 50)
    
    generator = FinancialSummaryGenerator()
    
    print("\nAvailable commands:")
    print("1. Generate weekly summary")
    print("2. Generate monthly summary")
    print("3. Generate quarterly summary") 
    print("4. Compare recent weeks")
    print("5. Export tax records")
    print("6. View saved summary")
    print("7. List all summaries")
    
    while True:
        choice = input("\nChoose an option (1-7, or 'quit'): ").strip()
        
        if choice.lower() in ['quit', 'exit', 'q']:
            break
        
        elif choice == '1':
            weeks_ago = input("Which week? (0=this week, 1=last week, 2=two weeks ago): ").strip()
            try:
                weeks_ago = int(weeks_ago) if weeks_ago else 0
                generator.create_weekly_summary(weeks_ago)
            except ValueError:
                print("Please enter a number")
        
        elif choice == '2':
            year = int(input("Enter year (e.g., 2025): "))
            month = int(input("Enter month (1-12): "))
            generator.create_monthly_summary(year, month)
        
        elif choice == '3':
            year = int(input("Enter year (e.g., 2025): "))
            quarter = int(input("Enter quarter (1-4): "))
            generator.create_quarterly_summary(year, quarter)
        
        elif choice == '4':
            weeks = input("How many weeks to compare? (default 4): ").strip()
            try:
                weeks = int(weeks) if weeks else 4
                generator.compare_weeks(weeks)
            except ValueError:
                generator.compare_weeks(4)
        
        elif choice == '5':
            year = int(input("Enter year for tax records: "))
            result = generator.export_tax_records(year)
            print(result)
        
        elif choice == '6':
            summary_id = int(input("Enter summary ID: "))
            generator.view_summary(summary_id)
        
        elif choice == '7':
            # List summaries
            try:
                conn = sqlite3.connect('financial_summaries.db')
                cursor = conn.cursor()
                cursor.execute('''
                SELECT id, period_type, period_name, net_position, created_at
                FROM financial_summaries ORDER BY created_at DESC
                ''')
                summaries = cursor.fetchall()
                conn.close()
                
                if summaries:
                    print("\nSAVED SUMMARIES:")
                    for s in summaries:
                        print(f"ID {s[0]}: {s[1].title()} - {s[2]} | Net: ${s[3]:+.2f} | {s[4][:16]}")
                else:
                    print("No summaries found")
            except Exception as e:
                print(f"Error listing summaries: {e}")

if __name__ == "__main__":
    main()
