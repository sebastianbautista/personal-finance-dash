# panels/cashflow.py 
# ------------------
# Panel A: Cash Flow
# layout function returns full panel including sidebar controls
# callbacks to be added after layout confirmed working

import numpy as np
import pandas as pd
import calendar
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
    hoverlabel=dict(bgcolor='#1b1e26', font=dict(color='#dde0e8')),  # consistent tooltip styling across all charts
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

        # sidebar controls ----
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
                value=24, # default to 24 months so STL plot isn't empty on load
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

        # main content ----
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

            # heatmap gets a custom card because it needs an extra control -
            # toggle between raw $ values and normalized (z-score) view
            html.Div([
                html.Div('Category Heatmap', className='card-title'),
                dcc.RadioItems(
                    id='cf-heatmap-scale',
                    options=[
                        dict(label='Raw ($)',    value='raw'),
                        dict(label='Normalized', value='normalized')
                    ],
                    value='normalized', # default to normalized, more readable,
                    inline=True,
                    style=dict(fontSize='11px', marginBottom='8px', color='var(--muted)'),
                    inputStyle=dict(marginRight='4px', marginLeft='8px'),
                ),
                dcc.Graph(
                    id='cf-heatmap',
                    figure=_empty_fig(),
                    config=dict(displayModeBar=False),
                ),
            ], className='chart-card'),

            _chart_card('cf-vs-avg',    'This Month vs 3-Month Average'),

        ], className='main-content')
    ], className='panel-grid')


# 4. Data aggregation helpers (_waterfall/_stl/_heatmap/_vs_avg_data()) ----

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


def _stl_data(analysis_df, trailing_months):
    """
    Aggregate monthly spending and apply STL decomposition

    STL splits time series into trend/seasonal/residual

    Parameters
    ----------
    analysis_df : pd.DataFrame
    trailing_months : int - 0 = all data

    Returns
    -------
    pd.DataFrame with columns: month, spending, trend, seasonal, residual
    """
    from statsmodels.tsa.seasonal import STL

    expenses = analysis_df[analysis_df['type'] == 'Expense'].copy()

    monthly = (
        expenses
        .groupby(expenses['date'].dt.to_period('M'))['amount']
        .sum()
        .abs()
        .reset_index()
    )
    monthly.columns = ['month', 'spending']
    monthly['month'] = monthly['month'].dt.to_timestamp()

    # exclude partial first month (Nov 2023) ----
    monthly = monthly[monthly['month'] >= '2023-12-01'].copy()

    # apply trailing months filter ----
    if trailing_months != 0:
        now = pd.Timestamp.now()
        cutoff = now - pd.DateOffset(months=trailing_months)
        monthly = monthly[monthly['month'] >= cutoff].copy()

    # STL needs at least 2 full seasonal cycles (here years) to decompose ----
    # if filtered series is too short, return None
    if len(monthly) < 24:
        return None

    # run STL ----
    stl = STL(monthly['spending'], period=12, seasonal=13, robust=True)
    result = stl.fit()

    monthly['trend']    = result.trend
    monthly['seasonal'] = result.seasonal
    monthly['residual'] = result.resid

    return monthly


def _heatmap_data(analysis_df, trailing_months, min_transactions=10):
    """
    Average spending by category x month-of-year for categories with enough volume

    Returns both a raw $ pivot and row-normalized (z-score) pivot

    Parameters
    ----------
    analysis_df : pd.DataFrame
    trailing_months : int - 0 = all data
    min_transactions: int - categories with fewer transactions are excluded

    Returns
    -------
    tuple of (pivot_raw, pivot_normalized), both pd.DataFrame pivots
    categories as rows, months 1-12 as cols
    """
    expenses = analysis_df[analysis_df['type'] == 'Expense'].copy()

    # apply trailing months filter ----
    if trailing_months != 0:
        now = pd.Timestamp.now()
        cutoff = now - pd.DateOffset(months=trailing_months)
        expenses = expenses[expenses['date'] >= cutoff].copy()

    expenses_all = expenses.copy()
        
    # drop sparse categories ----
    counts = expenses['category'].value_counts()
    valid_categories = counts[counts >= min_transactions].index
    expenses = expenses[expenses['category'].isin(valid_categories)]

    # grab month number ----
    expenses['month_num'] = expenses['date'].dt.month

    # pivot: mean absolute spending by category x month ----
    pivot = (
        expenses
        .groupby(['category', 'month_num'])['amount']
        .mean()
        .abs()
        .unstack(fill_value=0) # convert innermost multiindex (month) to columns
    )

    # ensure all months are present ----
    pivot = pivot.reindex(columns=range(1, 13), fill_value=0)

    # sort categories by total spending, desc ----
    # done before normalizing so row order is unchanged between views
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]

    # add Total row here ---
    total_by_month = (
        expenses_all
        .groupby(expenses_all['date'].dt.month)['amount']
        .sum()
        .abs()
        .reindex(range(1, 13), fill_value=0)
    )
    total_by_month.name = 'Total'

    # transpose and prepend (concat) Total as first row
    pivot = pd.concat([total_by_month.to_frame().T, pivot])

    # row-normalize (z-score) ----
    row_mean = pivot.mean(axis=1) # avg monthly spend for each category
    row_std = pivot.std(axis=1, ddof=0) # monthly std
    row_std = row_std.replace(0, 1) # avoid divide by zero

    # (value - mean) / std = z-score
    # axis=0 makes sure indices (categories) match up
    pivot_normalized = pivot.sub(row_mean, axis=0).div(row_std, axis=0)

    return pivot, pivot_normalized


def _vs_avg_data(analysis_df):
    """
    Compare current month's (prorated) spending by category against each
    category's trailing 3-month average, ranked by deviation

    Proration: scale current spending by (days_in_month / days_elapsed) to estimate
    a full-month pace, making the comparison meaningful at any point in the month

    Note: 3-month timespan is hard-coded, so no trailing_months parameter 

    Parameters
    ----------
    analysis_df : pd.DataFrame

    Returns
    -------
    pd.DataFrame with columns: category, current_prorated, trailing_avg, deviation
    sorted by deviation descending
    """

    expenses = analysis_df[analysis_df['type'] == 'Expense'].copy()

    now = pd.Timestamp.now()
    current_month_start = now.replace(day=1)

    # curent month spending by category ----
    current = expenses[expenses['date'] >= current_month_start]
    current_by_cat = current.groupby('category')['amount'].sum().abs()

    # prorate to estimate full-month pace ----
    days_in_month = calendar.monthrange(now.year, now.month)[1] # [1] = number of dadys
    days_elapsed = now.day
    proration_factor = days_in_month / days_elapsed

    current_prorated = current_by_cat * proration_factor

    # trailing 3-month average ----
    three_month_cutoff = current_month_start - pd.DateOffset(months=3)
    trailing = expenses[
        (expenses['date'] >= three_month_cutoff) &
        (expenses['date'] < current_month_start)
    ]
    trailing_avg_by_cat = trailing.groupby('category')['amount'].sum().abs() / 3

    # combine ----
    comparison = pd.DataFrame({
        'current_prorated': current_prorated,
        'trailing_avg': trailing_avg_by_cat,
    }).fillna(0)

    comparison['deviation'] = comparison['current_prorated'] - comparison['trailing_avg']

    comparison = comparison.round(2)
    comparison = comparison.reset_index().rename(columns={'index': 'category'})
    comparison = comparison.sort_values('deviation', ascending=False)

    return comparison


# 5. Callbacks: update all four figures ----

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
            connector    = dict(line=dict(color='#2a2e3a', width=1)), # border color
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


# again, figure depends on value of trailing months
@callback(
    Output('cf-stl', 'figure'),
    Input('cf-trailing-months', 'value')
)
def update_stl(trailing_months):
    """
    STL decomposition of monthly spending
    Shows trend, seasonal, and residual components as subplots

    make_subplots() is like par(mfrow=c(3,1)) in R or fig, axes = plt.subplots(3,1) in matplotlib
    """
    from data import load_data
    from plotly.subplots import make_subplots

    _, analysis_df = load_data()
    monthly = _stl_data(analysis_df, trailing_months)

    # handle cases when not enough data
    if monthly is None:
        fig = go.Figure()
        fig.update_layout(
            **PLOTLY_THEME,
            height=400,
            title=dict(text='Not enough data for STL (need 24+ months)',
                    font=dict(color='#6b7080'))
        )
        return fig

    # build subplot figure ----
    # 3 rows, 1 column, trend -> seasonal -> residual
    # shared_xaxes=True links date axes so zooming zooms all three
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=['Trend', 'Seasonal', 'Residual']
    )

    # trend: line chart ----
    # go.Scatter with mode='lines' is line chart
    # equiv to geom_line()
    fig.add_trace(
        go.Scatter(
            x=monthly['month'],
            y=monthly['trend'],
            mode='lines',
            line=dict(color='#7EB8A4', width=2),
            name='Trend',
            hovertemplate='%{x|%b %Y}: $%{y:,.0f}<extra></extra>' # last bit suppresses default trace name in hover box
        ),
        row=1, col=1
    )

    # seasonal: bar chart ----
    # positive seasonal = month above trend
    # negative seasonal = month below trend
    fig.add_trace(
        go.Bar(
            x=monthly['month'],
            y=monthly['seasonal'],
            marker=dict(
                color=monthly['seasonal'],
                # maps values to colors
                colorscale=[[0, '#C87070'], [0.5, '#2a2e3a'], [1, '#7EB8A4']],
                cmid=0, # center colorscale at 0
            ),
            name='Seasonal',
            hovertemplate='%{x|%b %Y}: $%{y:,.0f}<extra></extra>'
        ),
        row=2, col=1
    )

    # residual: bar chart ----
    # large residuals = one-off events
    fig.add_trace(
        go.Bar(
            x=monthly['month'],
            y=monthly['residual'],
            marker=dict(
                color=monthly['residual'],
                colorscale=[[0, '#C87070'], [0.5, '#2a2e3a'], [1, '#7EB8A4']],
                cmid=0
            ),
            name='Residual',
            hovertemplate='%{x|%b %Y}: $%{y:,.0f}<extra></extra>'
        ),
        row=3, col=1,
    )

    # apply theme ----
    fig.update_layout(
        **PLOTLY_THEME,
        height=600,
        showlegend=False,
        margin=dict(t=40, b=40, l=40, r=40)
    )

    fig.update_yaxes(tickprefix='$', tickformat=',.0f', gridcolor='#1e2230')
    fig.update_xaxes(gridcolor='#1e2230', showgrid=False)

    return fig


# heatmap depends on an additional 'cf-heatmap-scale' component-id
# to change view between raw/normalized
@callback(
    Output('cf-heatmap', 'figure'),
    Input('cf-trailing-months', 'value'),
    Input('cf-heatmap-scale', 'value')
)
def update_heatmap(trailing_months, scale_mode):
    """
    Heatmap of average spendding by category x month-of-year
    Shows recurring seasonal patterns 
    Toggles between raw $ values and row-normalized z-scores

    go.Heatmap takes a 2D `z` matrix plus `x` and `y` axis labels
    Equivalent to geom_tile() in ggplot with fill = value
    """
    from data import load_data

    _, analysis_df = load_data()
    pivot_raw, pivot_normalized = _heatmap_data(analysis_df, trailing_months)

    # month number to abbreviated name ----
    month_names = list(calendar.month_abbr)[1:]

    if scale_mode == 'normalized':
        z_values = pivot_normalized.values
        # diverging colorscale - green (negative z, low spending) to red (+, high)
        # plotly colorscales are always defined on normalized [0, 1] domain
        colorscale = [[0, '#7EB8A4'], [0.5, '#1b1e26'], [1, '#C87070']]
        zmid = 0 # anchors diverging colorscale at 0
        colorbar_title = 'σ' # sigma for std

        # customdata lets us use raw data from outside the chart
        # carries 3 values per cell: raw $, row min, row max
        # category min/max, reshaped to 1 column and however many rows works (n categories)
        # in order to broadcast across all columns
        row_min = pivot_raw.min(axis=1).values.reshape(-1, 1) # 26 x 1
        row_max = pivot_raw.max(axis=1).values.reshape(-1, 1)
        row_min_grid = np.tile(row_min, (1, 12)) # repeat the row min across all 12 months = 26 x 12
        row_max_grid = np.tile(row_max, (1, 12))
        # np.dstack stacks 2D arrays along new third dimension, 
        # so each cell in the heatmap gets a small array [raw, row_min, row_max]
        # instead of a single raw value
        customdata = np.dstack([pivot_raw.values, row_min_grid, row_max_grid])


        # hover shows raw $ even here since std isn't as interpretable
        # %{customdata[0]} = raw $, [1] = row min, [2] = row max
        hovertemplate = (
            '%{y} - %{x}<br>'
            '$%{customdata[0]:,.0f} (%{z:.1f}σ)<br>'
            'range: $%{customdata[1]:,.0f}-$%{customdata[2]:,.0f}'
            '<extra></extra>'
        )
    else:
        z_values = pivot_raw.values
        # single-direction colorscale since spending is >= 0
        colorscale = [[0, '#1b1e26'], [1, '#7EB8A4']]
        zmid = None # not used for single-direction
        colorbar_title = '$'
        customdata = None
        hovertemplate = '%{y} - %{x}: $%{z:,.0f}<extra></extra>'

    heatmap_kwargs = dict(
        z=z_values,
        x=month_names,
        y=pivot_raw.index,
        colorscale=colorscale,
        colorbar=dict(
            title=dict(text=colorbar_title, side='right'),
            tickfont=dict(color='#9aa0b0', size=10)
        ),
        hovertemplate=hovertemplate,
    )

    # zmid is only valid when set - passing zmid=None overrides Plotly
    # so we conditionally add it
    if zmid is not None:
        heatmap_kwargs['zmid'] = zmid

    if customdata is not None:
        heatmap_kwargs['customdata'] = customdata

    fig = go.Figure(go.Heatmap(**heatmap_kwargs))

    fig.update_layout(
        **PLOTLY_THEME,
        height=600,
        margin=dict(t=40, b=40, l=120, r=40) # l=120 gives category labels room
    )

    fig.update_yaxes(autorange='reversed') # highest spend category at top
    fig.update_xaxes(side='top') # months along the top

    # add separator line under Total row ----
    # heatmap yaxis is categorical and plotly places categories at integer positions
    # since Total is always row 0, we draw a horizontal line at y=0.5 (between 0 and 1)
    fig.add_shape(
        type='line',
        x0=0, x1=1, xref='paper', # 'paper' spans full width regardless of x-axis units
        y0=0.5, y1=0.5, yref='y',
        line=dict(color='#363b4a', width=2),
    )

    return fig


@callback(
    Output('cf-vs-avg', 'figure'),
    Input('cf-trailing-months', 'value') # included for consistency but ignored
)
def update_vs_avg(trailing_months):
    """
    Bar chart: current month's prorated spending vs trailing 3-month average,
    by category, ranked by deviation. Shows any categories running hot or cold
    relative to recent habits

    Note: this always compares to a fixed 3-month trailing window regardless of trailing_months
    """
    from data import load_data

    _, analysis_df = load_data()
    comparison = _vs_avg_data(analysis_df)

    # color bars by direction: red = higher than usual, green = lower
    colors = ['#C87070' if d > 0 else '#7EB8A4' for d in comparison['deviation']] 

    fig = go.Figure(
        go.Bar(
            x=comparison['deviation'],
            y=comparison['category'],
            orientation='h', # easier to read category names horizontally
            marker=dict(color=colors),
            text=[f'${d:+,.0f}' for d in comparison['deviation']], # + sign shows direction explicitly
            textposition='outside',
            hovertemplate=(
                '%{y}<br>'
                'This month (prorated): $%{customdata[0]:,.0f}<br>'
                '3-month avg: $%{customdata[1]:,.0f}<br>'
                'Deviation: %${x:+,.0f}'
                '<extra></extra>'
            ),
            customdata=comparison[['current_prorated', 'trailing_avg']].values
        )
    )

    fig.update_layout(
        **PLOTLY_THEME,
        height=600,
        margin=dict(t=40, b=40, l=140, r=60) # l=140 for category label room
    )

    fig.update_yaxes(autorange='reversed') # largest positive deviation at top
    fig.update_xaxes(tickprefix='$', tickformat=',.0f', gridcolor='#1e2230')

    return fig

 