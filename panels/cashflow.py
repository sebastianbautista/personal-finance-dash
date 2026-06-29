# panels/cashflow.py 
# ------------------
# Panel A: Cash Flow
# layout function returns full panel including sidebar controls
# callbacks to be added after layout confirmed working

import pandas as pd
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go

# 1. Helper: empty placeholder figure (PLOTLY_THEME and _empty_fig()) ----
# returns a blank plotly fig with dark theme applied
# used for standin until callbacks finished
# defined here so placeholders look consistent

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Mono, monospace", size=11, color="#9aa0b0"),
    xaxis=dict(gridcolor="#1e2230", showgrid=True),
    yaxis=dict(gridcolor="#1e2230", showgrid=True),
)

def _empty_fig(title=""):
    """Blank themed figure used as a placeholder before callbacks are wired."""
    fig = go.Figure()
    fig.update_layout(
        **PLOTLY_THEME,
        title=dict(text=title, font=dict(size=12, color="#6b7080")),
        height=300,
    )
    return fig

# 2. Helpers: reusable card components (_kpi/_chart_card()) ----

def _kpi_card(card_id, label):
    """
    Returns a single KPI card div with a label and value placeholder
    The value span is given an id so callbacks can update it directly
    """
    return html.Div([
        html.Div(label, className='kpi-label'),
        html.Span('-', id=card_id, className='kpi-value'),
    ], className='kpi-card')


def _chart_card(chart_id, title):
    """ 
    Returns a chart card div containing a titled dcc.Graph placeholder
    The dcc.Graph id is what callbacks target to update the figure
    """
    return html.Div([
        html.Div(title, className='card-title'),
        dcc.Graph(
            id=chart_id,
            figure=_empty_fig(),
            config=dict(displayModeBar=False), # hide plotly toolbar
        ),
    ], className='chart-card')


# 3. Layout (cashflow_layout()) ----

def cashflow_layout():
    return html.Div([

        # sidebar controls
        html.Div([
            html.Div('', className='sidebar-title'),

            html.Div('Trailing Period', className='sidebar-label'),
            dcc.Dropdown(
                id='cf-trailing-months',
                options=[
                    dict(label='3 Months',  value=3),
                    dict(label='6 Months',  value=6),
                    dict(label='12 Months', value=12),
                    dict(label='24 Months', value=24),
                    dict(label='All',  value=0), # 0 = sentinel for 'all data'
                ],
                value=6, # default to 6 months
                clearable=False,
                style=dict(fontSize='12px'),
            ),

            html.Div('Category', className='sidebar-label'),
            dcc.Dropdown(
                id='cf-category-filter',
                options=[], # populated by callback after data loaded
                multi=True,
                placeholder='All categories',
                style=dict(fontSize='12px')
            ),
        ], className='sidebar'),

        # main content
        html.Div([

            # KPI row
            html.Div([
                _kpi_card('kpi-income',        'Income (MTD)'),
                _kpi_card('kpi-spending',      'Spending (MTD)'),
                _kpi_card('kpi-vs-avg',        'vs 3-Month Avg'),
                _kpi_card('kpi-biggest-mover', 'Biggest Mover'),
            ], className='kpi-grid'),

            # chart cards
            _chart_card('cf-waterfall', 'Waterfall - Income to Net'),
            _chart_card('cf-stl',       'Spending Seasonality (STL)'),
            _chart_card('cf-heatmap',   'Category Heatmap'),
            _chart_card('cf-vs-avg',    'This Month vs 3-Month Average'),

        ], className='main-content')
    ], className='panel-grid')


# 4. Data aggregation helpers (_waterfall_data()) ----

def _waterfall_data(analysis_df, trailing_months):
    """
    Aggregate income and spending by bucket for the waterfall chart

    Parameters
    ----------
    analysis_df: pd.DataFrame - dataframe excluding transfers from data.load_data()
    trailing_months: int - number of trailing months to include (0 = all data)

    Returns
    -------
    dict with keys: measure, x, y, text
        Ready to pass into go.Waterfall()
    """
    # filter to trailing n months ----

    now = pd.Timestamp.now()

    if trailing_months == 0:
        # 0 = all data = no filter
        filtered = analysis_df.copy()
    else:
        cutoff = now - pd.DateOffset(months=trailing_months)
        filtered = analysis_df[analysis_df['date'] >= cutoff].copy()

    # sum by bucket ----
    buckets = filtered.groupby('bucket')['amount'].sum()

    # build waterfall structure ----
    # plotly waterfall uses two bar types set via 'measure'
    #  'relative' - bar that steps up or down from previous bar
    #  'total' - bar that shows running total

    income = buckets.get('Income', 0) # pos
    needs  = buckets.get('Needs', 0)  # neg
    wants  = buckets.get('Wants', 0)  # neg

    net = income + needs + wants

    return dict(
        measure = ['relative', 'relative', 'relative', 'total'],
        x       = ['Income', 'Needs', 'Wants', 'Net'],
        y       = [income, needs, wants, net],
        text    = [f'${v:,.0f}' if v >= 0 else f'-${abs(v):,.0f}' for v in [income, needs, wants, net]]
    )


# 5. Callbacks ----

# change the cf-waterfall figure based on the value of cf-trailing-months
@callback(
    Output('cf-waterfall', 'figure'), # component_id, component_property
    Input('cf-trailing-months', 'value')
)
def update_waterfall(trailing_months):
    """
    Fires when the trailing months dropdown changes, rebuilding the waterfall fig each time
    
    Callbacks are functions decorated with @callback
    Inputs are component properties that trigger the function
    Outputs are component properties that get updated with return value (output = f(inputs))
    """
    from data import load_data # avoiding circular imports at module level

    _, analysis_df = load_data()

    # get aggregated waterfall data using helper
    wd = _waterfall_data(analysis_df, trailing_months)

    # build the figure ----
    # go.Figure() is the container (cf ggplot())
    # go.Waterfall() is the trace (cf geom_ layer)
    fig = go.Figure(
        go.Waterfall(
            measure = wd['measure'],
            x            = wd['x'],
            y            = wd['y'],
            text         = wd['text'],
            textposition = 'outside',
            increasing   = dict(marker=dict(color='#7EB8A4')), # green for pos
            decreasing   = dict(marker=dict(color='#C87070')), # red for neg
            totals       = dict(marker=dict(color='#A89FD8')), # purple for net
            connector    = dict(line=dict(color='#2a2e3a', width=1)) # border color
        )
    )

    fig.update_layout(
        **PLOTLY_THEME,
        height = 400,
        margin = dict(t=40, b=40, l=40, r=40),
    )

    fig.update_yaxes(tickprefix='$', tickformat=',.0f', gridcolor='#1e2230', showgrid=True)
    fig.update_xaxes(gridcolor='#1e2230', showgrid=False)

    return fig