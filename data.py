# data.py 
# -------
# data ingestion and transformation lives here
# the func load_data() returns two dataframes:
#   - df: full transaction history, all types, with in_transfer flag
#   - analysis_df: expenses and income only (no transfers)

import glob
import os
import pandas as pd

def _find_latest_origin_file(data_dir: str = 'data') -> str:
    """
    Use glob to find all transaction CSVs from Origin in data_dir
    Return the most recent one by filename
    Sorting should == chronological sort due to filename formatting
    """
    pattern = os.path.join(data_dir, '*transactions*.csv')
    files = glob.glob(pattern)

    if not files:
        raise FileNotFoundError(f"No transaction CSVs in '{data_dir}/'")

    return max(files) # max(string) works bc of date prefix


def load_data(data_dir: str = 'data') -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load and clean most recent Origin transaction CSV

    Returns two DataFrames
    ----------------------
    df: full transaction history with transfers and flag
    analysis_df: expenses and income only, main df for analysis
    """

    path = _find_latest_origin_file(data_dir)
    print(f'Loading {path}')

    # 1. Read file and clean names
    df = pd.read_csv(path)
    df.columns = df.columns.str.lower().str.replace(' ', '_')

    # 2. Parse dates
    df['date'] = pd.to_datetime(df['date'])

    # 3. Drop unused columns
    df = df.drop(columns=['statement_description', 'tags', 'notes'])

    # 4. Flag transfers
    df['is_transfer'] = df['type'] == 'Transfer'

    # 5. Category bucket mapping
    BUCKET_MAP = {
    # needs
    'Rent':                   'Needs',
    'Utilities':              'Needs',
    'Groceries':              'Needs',
    'Auto & transport':       'Needs',
    'Healthcare':             'Needs',
    'Personal care':          'Needs',
    'Household':              'Needs',
    'General merchandise':    'Needs',
    'Financial':              'Needs',
    'Taxes':                  'Needs',
    'Childcare & education':  'Needs',
    'Other':                  'Needs',
    # wants
    'Fast food':              'Wants',
    'Drinks & dining':        'Wants',
    'Alcohol':                'Wants',
    'Food delivery':          'Wants',
    'Snacks':                 'Wants',
    'Gaming':                 'Wants',
    'Entertainment':          'Wants',
    'Concerts':               'Wants',
    'Amusement':              'Wants',
    'Festivals':              'Wants',
    'Travel & vacation':      'Wants',
    'Shopping':               'Wants',
    'Hobbies':                'Wants',
    'Subscriptions':          'Wants',
    # Income
    'Paycheck':               'Income',
    'Parental':               'Income',
    'Reimbursement':          'Income',
    'Interest':               'Income',
    'Income':                 'Income',
    'Tax refund':             'Income',
    # Transfer (flagged but still mapped for completeness)
    'Credit card payment':    'Transfer',
    'Transfer':               'Transfer',
    }

    df['bucket'] = df['category'].map(BUCKET_MAP)

    # warn if categories unmapped
    unmapped = df[df['bucket'].isna()]['category'].unique()
    if len(unmapped) > 0:
        print(f'WARNING: unmapped categories: {unmapped}')

    # 6. Shorten account names
    # raw acct strings are verbose, so pull out last 4 acct id
    df['account_short'] = df['account'].str.extract(r'\(([^)]+)\)$')
    # venmo doesn't have a number and parses NaN, so manual fill 
    df['account_short'] = df['account_short'].fillna('9999')

    # 7. Create analysis subset
    # .copy() avoids SettingWithCopyWarning if mutating later
    analysis_df = df[~df['is_transfer']].copy()

    return df, analysis_df

