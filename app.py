# app.py
# ------
# Entry point for personal finance dashboard
# App instantiation, global CSS, top-level layout, tab routing
# Chart logic lives in panels/

import dash
from dash import dcc, html, Input, Output

# import panel layout functions that return html.Div trees
# (placeholder for now)
from panels.cashflow import cashflow_layout
from panels.networth import networth_layout

# 1. App instantiation ----
# suppress_callback_exceptions=True because panel layouts are
# injected dynamically via tab routing 
# dash would complain about callbacks referencing components
# that aren't in the initial layout
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server # exposed for possible deployment later on

# 2. CSS and global styles ----
# just pasting this from earlier template

CSS = """
:root {
    --bg:      #0b0c0e;
    --surface: #13151a;
    --surf2:   #1b1e26;
    --border:  #2a2e3a;
    --border2: #363b4a;
    --text:    #dde0e8;
    --muted:   #6b7080;
    --accent:  #7EB8A4;
    --accentB: #A89FD8;
    --warn:    #C8A96E;
    --danger:  #C87070;
}

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

    html.Div([
        # sidebar
        html.Div([
            html.Div('Personal Finance Dashboard', className='sidebar-title'),
            html.Div('panel', className='sidebar-label'),
            html.Div([
                html.Button('Cash Flow', id='tab-cashflow', className='tab-btn active', n_clicks=0),
                html.Button('Net Worth', id='tab-networth', className='tab-btn',        n_clicks=0)
            ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '4px'}),
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
    Output('tab-networth', 'className'),
    Input('tab-cashflow', 'n_clicks'),
    Input('tab-networth', 'n_clicks'),
)
def render_panel(n_cashflow, n_networth):
    # dash.ctx.triggered_id points to which input fired callback
    # on first load, nothing is clicked so triggered_id is None
    # this defaults to cashflow panel
    triggered = dash.ctx.triggered_id

    if triggered == 'tab-networth':
        return networth_layout(), 'tab-btn', 'tab-btn active'
    else:
        return cashflow_layout(), 'tab-btn active', 'tab-btn'


# 5. Run ----
if __name__ == '__main__':
    app.run(debug=True)
