# panels/cashflow.py 
# ------------------
# Panel A: Cash Flow
# layout function returns full panel including sidebar controls
# callbacks to be added after layout confirmed working

from pydantic._internal._dataclasses import as_dataclass_field
from dash import dcc, html
import plotly.graph_objects as go

# 1. Helper: empty placeholder figure ----
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

# 2. Helpers: reusable card components ----

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


# 3. Layout ----

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


