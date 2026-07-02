# panels/budget.py 
# ----------------
# Panel B: Budget and Risk Tracking
# Roll-rate analysis (over/under budget transitions) and discretionary runway
# layout function returns full panel; callbacks added after layout confirmed working

import numpy as np
import pandas as pd
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go

# reuse same theme as panel A
from panels.cashflow import PLOTLY_THEME, _chart_card, _empty_fig

# 1. Data aggregation helpers ----

def _monthly_category_spending(analysis_df):
    """
    Build a category x month matrix of actual monthly spending
    Foundation for both the budget comparison and roll-rate matrix

    Parameters
    ----------
    analysis_df : pd.DataFrame

    Returns
    -------
    pd.DataFrame - long format, columns: category, month, spending
        (month is a pd.Period, not timestamp, for clean chronological sorting)
    """

    expenses = analysis_df[analysis_df['type'] == 'Expense'].copy()
    expenses['month'] = expenses['date'].dt.to_period('M')

    monthly = (
        expenses
        .groupby(['category', 'month'])['amount']
        .sum()
        .abs()
        .reset_index()
    )
    monthly.columns = ['category', 'month', 'spending']

    return monthly


def _budget_status(analysis_df, min_transactions=10):
    
    """
    For each category, compute a budget as the trailing 3-month average of spending
    then flag every month as 'over' or 'under' that budget

    Mirrors credit risk 'performance status' - each period gets a binary state similar to transition matrix

    Parameters
    ----------
    analysis_df : pd.DataFrame
    min_transactions : int - same sparsity cutoff as panel A

    Returns
    -------
    pd.DataFrame - columns: category, month, spending, budget, status (over/under)
    """
    monthly = _monthly_category_spending(analysis_df)

    # drop sparse categories ----
    # count using underlying data, not from monthly aggregate
    expenses = analysis_df[analysis_df['type'] == 'Expense']
    counts = expenses['category'].value_counts()
    valid_categories = counts[counts >= min_transactions].index
    monthly = monthly[monthly['category'].isin(valid_categories)].copy()

    # compute budget per category ----
    # budget = trailing 12-month average spending
    # living situation changed July 2025, so 12-month trailing window captures "current lifestyle"
    # without needing hard-coded cutoff
    now = pd.Timestamp.now()
    current_month = now.to_period('M')
    twelve_months_ago = current_month - 12

    # exclude current (partial) month when establishing baseline
    complete_months = monthly[
        (monthly['month'] < current_month) &
        (monthly['month'] >= twelve_months_ago)
    ]

    budgets = complete_months.groupby('category')['spending'].mean().rename('budget')

    # join budget back onto full monthly series ----
    monthly = monthly.merge(budgets, on='category', how='left')

    # drop rows if budget wasn't computed
    monthly = monthly.dropna(subset=['budget'])

    # flag over/under
    monthly['status'] = np.where(monthly['spending'] > monthly['budget'], 'over', 'under')

    return monthly


def _roll_rate_matrix(analysis_df, min_transactions=10):
    """
    Build a roll-rate transition matrix: given a category's status this month,
    what is the probability of each status next month?

    Same idea as credit risk roll-rate analysis: given a loan is 30 DPD, 
    what's the probability it's current, 30 DPD, or 60 DPD next month
    Here, the two states are 'over' and 'under' budget instead of dq

    Parameters
    ----------
    analysis_df : pd.DataFrame 
    min_transactions : int - same sparsity cutoff used elsewhere

    Returns
    -------
    pd.DataFrame - 2x2 matrix, rows = current status, columns = next status,
    values = transition probability (rows sum to 1.0)
    """
    status_df = _budget_status(analysis_df, min_transactions)

    # build (category, this_month_status, next_month_status) triples ----
    # sort by category then month so shift() correctly grabs next row
    # within each category, not across category boundaries
    status_df = status_df.sort_values(['category', 'month'])

    # shift(-1) grabs next row's value: groupby ensures it doesn't
    # leak across category boundaries
    status_df['next_status'] = status_df.groupby('category')['status'].shift(-1)
    status_df['next_month'] = status_df.groupby('category')['month'].shift(-1)

    # keep only genuine consecutive-month pairs ----
    # if there's a gap (no transactions in category in some month)
    # the 'next' row may be 2+ mo later, which isn't valid MoM -
    # filter those out
    gap_series = status_df['next_month'] - status_df['month'] # returns periods (dateoffset)
    status_df['month_gap'] = gap_series.map(lambda x: x.n, na_action='ignore') # converts to int, ignores NaT
    valid_transactions = status_df[status_df['month_gap'] == 1]

    # build transition matrix ----
    # crosstab counts occurrences of each (status, next_status) pair
    counts = pd.crosstab(valid_transactions['status'], valid_transactions['next_status'])

    # normalize each row to sum to 1.0 (counts to probabilities)
    matrix = counts.div(counts.sum(axis=1), axis=0)

    return matrix


# 2. Layout ----

def budget_layout():
    return html.Div([

        # sidebar controls
        html.Div([
            html.Div('', className='sidebar-title'),
            html.Div('Category', className='sidebar-label'),
            dcc.Dropdown(
                id='bg-category-filter',
                options=[], # populated by callback once data loads
                multi=True,
                placeholder='All categories',
                style=(dict(fontSize='12px'))
            )
        ], className='sidebar'),

        # main content
        html.Div([
            _chart_card('bg-transition-matrix', 'Budget Roll-Rate Transition Matrix'),
        ], className='main-content'),

    ], className='panel-grid')


# 3. Callbacks ----

@callback(
    Output('bg-transition-matrix', 'figure'),
    Input('bg-category-filter', 'value') # placeholder
)
def update_transition_matrix(category_filter):
    """
    Heatmap visualization of the over/under budget transition matrix
    Rows = this month's status, columns = next month's status
    cell value = transition probability
    """
    from data import load_data

    _, analysis_df = load_data()
    matrix = _roll_rate_matrix(analysis_df)

    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=matrix.columns,
            y=matrix.index,
            colorscale=[[0, '#1b1e26'], [1, '#A89FD8']],
            zmin=0, zmax=1, # fixed scale for probabilities
            text=matrix.values,
            texttemplate='%{text:.1%}', # show percentage on each cell
            textfont=dict(size=16, color='#dde0e8'),
            colorbar=dict(
                title=dict(text='Probability', side='right'),
                tickformat='.0%',
                tickfont=dict(color='#9aa0b0', size=10),
            ),
            hovertemplate='%{y} -> %{x}: %{z:.1%}<extra></extra>'
        )
    )

    fig.update_layout(
        **PLOTLY_THEME,
        height=400,
        margin=dict(t=40, b=40, l=100, r=40)
    )

    fig.update_yaxes(title='This Month', autorange='reversed')
    fig.update_xaxes(title='Next Month', side='top')

    return fig

    