"""
Configuration file for Tree Till Bot
Contains categories, database settings, and other constants
"""

# Transaction Categories
# These are used by the AI model to categorize transactions
TRANSACTION_CATEGORIES = [
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

# Database Configuration
# Possible paths to look for the mycelium database (in order of preference)
MYCELIUM_DB_PATHS = [
    './bots/mycelium_bot/mycelium_messages.db',
    '../mycelium_bot/mycelium_messages.db',
    '../../bots/mycelium_bot/mycelium_messages.db'
]

# API Configuration
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL_NAME = "gemma3n:latest"

# Request Timeouts (in seconds)
API_TIMEOUT = 10
OLLAMA_TIMEOUT = 30

# Numeric fields in the assets database that need type conversion
ASSETS_NUMERIC_FIELDS = [
    'boa_checking', 'boa_credit_balance', 'ufb_savings', 
    'vanguard_roth_ira', 'vanguard_brokerage', 'hsa_cash', 
    'hsa_invested', 'education_fund', 'other_assets', 
    'other_debts', 'total_liquid', 'total_invested', 'net_worth'
]

# Column mapping for asset snapshots (for database operations)
ASSETS_COLUMNS = [
    'id', 'snapshot_date', 'boa_checking', 'boa_credit_balance',
    'ufb_savings', 'vanguard_roth_ira', 'vanguard_brokerage',
    'hsa_cash', 'hsa_invested', 'hsa_notes', 'education_fund', 
    'education_notes', 'other_assets', 'other_debts', 
    'total_liquid', 'total_invested', 'net_worth',
    'update_type', 'notes', 'created_at'
]