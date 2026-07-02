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
from panels.cashflow import PLOTLY_THEME, _chart_card, _kpi_card, _empty_fig

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

    # restrict to the same window used to compute budget ----
    # comparing months from before budget start is apples-to-oranges
    # here we only evaluate status within the same 12-mo window the budget 
    # itself was built from
    monthly = monthly[
        (monthly['month'] >= twelve_months_ago) &
        (monthly['month'] < current_month)
    ]

    # join budget back onto restricted monthly series ----
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


def _category_over_persistence(analysis_df, min_transactions=10, min_over_observations=3):
    """
    Per-category 'overbudget' persistence rate: given a category was overbudget this month,
    what fraction of the time was it also overbudget the following month?

    Category-level counterpart to the pooled _roll_rate_matrix
    Shows which specific categories are prone to persistent overspending vs. which self-correct (cure)

    Parameters
    ----------
    analysis_df : pd.DataFrame 
    min_transactions : int - same sparsity cutoff used elsewhere
    min_over_transactions : int - categories with fewer than this many 'over' months are excluded

    Returns
    -------
    pd.DataFrame - columns: category, over_persistence, n_over_observations
    sorted by over_persistence desc
    """
    status_df = _budget_status(analysis_df, min_transactions)
    status_df = status_df.sort_values(['category', 'month'])

    status_df['next_status'] = status_df.groupby('category')['status'].shift(-1)
    status_df['next_month'] = status_df.groupby('category')['month'].shift(-1)

    gap_series = status_df['next_month'] - status_df['month']
    status_df['month_gap'] = gap_series.map(lambda x: x.n, na_action='ignore')
    status_df = status_df[status_df['month_gap'] == 1]

    # keep only rows where this month was 'over' ----
    # specifically measuring transitions from over, not from under
    over_rows = status_df[status_df['status'] == 'over']

    # per category: what fraction of 'over' months were followed by another 'over'? ----
    persistence = (
        over_rows
        .groupby('category')['next_status']
        .apply(lambda s: (s == 'over').mean())
        .rename('over_persistence')
    )

    n_observations = over_rows.groupby('category').size().rename('n_over_observations')

    # joins on index (both are based on over_rows.groupby('category'))
    # need to_frame() because Series don't have a .join method
    # had pd.concat(..., axis=1) earlier but this is more explicit wrt index
    result = persistence.to_frame().join(n_observations).reset_index()

    # filter out categories with too few 'over' obs to be reliable ----
    result = result[result['n_over_observations'] >= min_over_observations]

    result = result.sort_values('over_persistence', ascending=False)

    return result 


def _spending_runway(analysis_df, cash_balance, bucket=None, trailing_months=12):
    """
    Estimate how many months a given cash balance would sustain spending
    using the trailing n-month average as the monthly burn rate

    Parameters
    ----------
    analysis_df : pd.DataFrame
    cash_balance : float or None - user-provided balance; default None
    bucket : str or None - 'wants' for discretionary-only runway, 'needs' for
                            essential only, None for total spending (all buckets)
    trailing_months : int - window for computing average monthly spending, defaults to 12
                            for consistency with budget baseline
    
    Returns
    -------
    float or None - estimated months of runway; None if cash_balance not provided or
        if monthly spending is 0
    """

    if cash_balance is None or cash_balance <= 0:
        return None

    expenses = analysis_df[analysis_df['type'] == 'Expense'].copy()

    if bucket is not None:
        expenses = expenses[expenses['bucket'] == bucket.title()]

    current_month = pd.Timestamp.now().to_period('M')
    cutoff = current_month - trailing_months
    
    expenses['month'] = expenses['date'].dt.to_period('M')
    expenses = expenses[(expenses['month'] >= cutoff) & (expenses['month'] < current_month)]

    monthly_spending = expenses.groupby('month')['amount'].sum().abs()

    if len(monthly_spending) == 0:
        return None
    
    avg_monthly_spending = monthly_spending.mean()

    if avg_monthly_spending == 0:
        return None

    return cash_balance / avg_monthly_spending


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
            ),
            html.Div('Current Cash Balance', className='sidebar-label'),
            dcc.Input(
                id='bg-cash-balance',
                type='number',
                placeholder='Enter amount ($)',
                value=None,
                style=dict(
                    width='100%',
                    fontSize='12px',
                    padding='6px',
                    background='var(--surf2)',
                    color='var(--text)',
                    border='1px solid var(--border)',
                    borderRadius='4px'
                ),
            ),
        ], className='sidebar'),

        # main content
        html.Div([
            # KPI row - separate nested div, own className
            html.Div([
                _kpi_card('bg-runway-total', 'Total Runway (months)'),
                _kpi_card('bg-runway-discretionary', 'Discretionary Runway (months)'),
            ], className='kpi-grid'),

            # chart cards - separate divs, each with chart-card styling
            _chart_card('bg-transition-matrix', 'Budget Roll-Rate Transition Matrix'),
            _chart_card('bg-persistence-chart', 'Category Over-Budget Persistence (trailing 12mo)'),
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


@callback(
    Output('bg-persistence-chart', 'figure'),
    Input('bg-category-filter', 'value'), # ignored for now
)
def update_persistence_chart(category_filter):
    """
    Per-category over-budget persistence rate, restricted to the same 
    12-month window used to compute each category's budget
    Bar opacity reflects observation count since some have very few 'over' months
    """
    from data import load_data

    _, analysis_df = load_data()
    result = _category_over_persistence(analysis_df)

    # opacity scales from 0.4 (few obs) to 1.0 (more)
    # so thin-sample categories are visually de-emphasized without hiding
    max_obs = result['n_over_observations'].max()
    opacities = 0.4 + 0.6 * (result['n_over_observations'] / max_obs)

    # horizontal bar plot, so value on x and category on y
    fig = go.Figure(
        go.Bar(
            x=result['over_persistence'],
            y=result['category'],
            orientation='h',
            marker=dict(color='#A89FD8', opacity=opacities),
            text=[f'{p:.0%} (n={n})' for p, n in
                  zip(result['over_persistence'], result['n_over_observations'])],
            textposition='outside',
            hovertemplate=(
                '%{y}<br>'
                'Over-persistence: %{x:.0%}<br>'
                'Based on %{customdata} months over budget'
                '<extra></extra>'
            ),
            customdata=result['n_over_observations']
        )
    )

    fig.update_layout(
        **PLOTLY_THEME,
        height=400,
        margin=dict(t=40, b=40, l=140, r=100)
    )

    fig.update_yaxes(autorange='reversed')
    fig.update_xaxes(tickformat='.0%', gridcolor='#1e2230', range=[0, 1.15])

    return fig


@callback(
    Output('bg-runway-total', 'children'),
    Output('bg-runway-discretionary', 'children'),
    Input('bg-cash-balance', 'value')
)
def update_runway(cash_balance):
    """
    Updates both runway KPI cards from a single cash_balance input
    Total runway uses all expenses; discretionary uses wants only
    """
    from data import load_data

    _, analysis_df = load_data()

    total_runway = _spending_runway(analysis_df, cash_balance, bucket=None)
    discretionary_runway = _spending_runway(analysis_df, cash_balance, bucket='Wants')

    total_text = f'{total_runway:.1f}' if total_runway is not None else '-'
    discretionary_text = f'{discretionary_runway:.1f}' if discretionary_runway is not None else '-'

    return total_text, discretionary_text

