# app.py
# ------
# Entry point for personal finance dashboard
# App instantiation, global CSS, top-level layout, tab routing
# Chart logic lives in panels/

import dash
from dash import dcc, html, Input, Output

# import theme and panel layout functions that return html.Div trees
from theme import COLORS
from panels.cashflow import cashflow_layout
from panels.budget import budget_layout

# 1. App instantiation ----
# suppress_callback_exceptions=True because panel layouts are
# injected dynamically via tab routing 
# dash would complain about callbacks referencing components
# that aren't in the initial layout
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server # exposed for possible deployment later on

# 2. CSS and global styles ----
# generating this dynamically from theme.COLORS
# replace the :root block with an f-string and inject into existing CSS

# double {{}} (literals) to escape f-string {} placeholder
CSS_ROOT = f""":root{{
    --bg:      {COLORS['bg']};
    --surface: {COLORS['surface']};
    --surf2:   {COLORS['surf2']};
    --border:  {COLORS['border']};
    --border2: {COLORS['border2']};
    --text:    {COLORS['text']};
    --muted:   {COLORS['muted']};
    --accent:  {COLORS['accent']};
    --accentB: {COLORS['accentB']};
    --warn:    {COLORS['warn']};
    --danger:  {COLORS['danger']};
}}"""

CSS = CSS_ROOT +  """
* { box-sizing: border-box; margin: 0; padding: 0; } 

body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
}

/* ---------- layout ---------- */
.panel-grid {
    display: grid;
    grid-template-columns: 220px 1fr;
    min-height: 100vh;
}

.sidebar {
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 24px 16px;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
}

.main-content {
    padding: 24px;
    overflow-y: auto;
}

/* ---------- tabs ---------- */
.tab-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 24px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
}

.tab-btn {
    background: none;
    border: none;
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    padding: 6px 14px;
    cursor: pointer;
    border-radius: 4px 4px 0 0;
    transition: color 0.15s;
}

.tab-btn:hover  { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom: 2px solid var(--accent); }

/* ---------- cards ---------- */
.chart-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
    margin-bottom: 16px;
}

.card-title {
    font-family: 'Libre Baskerville', serif;
    font-style: italic;
    font-size: 13px;
    color: var(--muted);
    margin-bottom: 12px;
}

/* ---------- KPI grid ---------- */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}

.kpi-card {
    background: var(--surf2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px;
}

.kpi-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.kpi-value {
    font-family: 'DM Mono', monospace;
    font-size: 22px;
    color: var(--text);
    margin-top: 4px;
}

/* ---------- sidebar elements ---------- */
.sidebar-title {
    font-family: 'Libre Baskerville', serif;
    font-style: italic;
    font-size: 15px;
    color: var(--accent);
    margin-bottom: 20px;
}

.sidebar-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
    margin-top: 16px;
}
"""

app.index_string = f"""<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>Personal Finance</title>
        {{%favicon%}}
        {{%css%}}
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300;1,400;1,500&family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
        <style>{CSS}</style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>"""

# 3. Top-level layout ----
# dcc.Location tracks URL
# dcc.Store holds loaded data in-browser so we don't reload on callback
# tab bar is plain HTML buttons connected to callback below

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='store-data'), # for data caching later
    dcc.Store(id='store-palette', data='default'),  # holds 'default' or 'colorblind'

    html.Div([
        # sidebar
        html.Div([
            html.Div('Personal Finance Dashboard', className='sidebar-title'),
            html.Div('panel', className='sidebar-label'),
            html.Div([
                html.Button('Cash Flow', id='tab-cashflow', className='tab-btn active', n_clicks=0),
                html.Button('Budget', id='tab-budget', className='tab-btn',        n_clicks=0)
            ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '4px'}),

            html.Div('Color Palette', className='sidebar-label'),
            dcc.RadioItems(
                id='palette-toggle',
                options=[
                    dict(label='Default',    value='default'),
                    dict(label='Colorblind', value='colorblind'),
                ],
                value='default',
                style=dict(fontSize='11px', color='var(--muted)'),
                inputStyle=dict(marginRight='4px', marginLeft='8px'),
                labelStyle=dict(color='var(--text)'),
            ),
        ], className='sidebar'),

        # main content
        html.Div([
            html.Div(id='panel-content') # swapped by tab callback
        ], className='main-content'),

    ], className='panel-grid'),
], style={'minHeight': '100vh', 'background': 'var(--bg)'})

# 4. Tab routing callback ----
# watches both tab buttons and renders most recently clicked

@app.callback(
    Output('panel-content', 'children'),
    Output('tab-cashflow', 'className'),
    Output('tab-budget', 'className'),
    Input('tab-cashflow', 'n_clicks'),
    Input('tab-budget', 'n_clicks'),
)
def render_panel(n_cashflow, n_budget):
    # dash.ctx.triggered_id points to which input fired callback
    # on first load, nothing is clicked so triggered_id is None
    # this defaults to cashflow panel
    triggered = dash.ctx.triggered_id

    if triggered == 'tab-budget':
        return budget_layout(), 'tab-btn', 'tab-btn active'
    else:
        return cashflow_layout(), 'tab-btn active', 'tab-btn'


@app.callback(
    Output('store-palette', 'data'),
    Input('palette-toggle', 'value')
)
def update_palette_store(selected_palette):
    return selected_palette


# 5. Run ----
if __name__ == '__main__':
    app.run(debug=True)
