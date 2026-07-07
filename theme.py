# theme.py
# --------
# Single source for dashboard's color palette and Plotly theme
# Imported by app.py (to build the CSS :root block) and by both
# panels/cashflow.py and panels/budget.py (for chart colors)
# Lives in its own module, separate from app.py and panels,
# to avoid circular imports

COLORS = dict(
    bg='#0b0c0e',
    surface='#13151a',
    surf2='#1b1e26',
    border='#2a2e3a',
    border2='#363b4a',
    text='#dde0e8',
    muted='#6b7080',
    accent='#7EB8A4',
    accentB='#A89FD8',
    warn='#C8A96E',
    danger='#C87070',
    gridline='#1e2230',  # not in original CSS :root, but used repeatedly in Plotly gridcolor
)

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Mono, monospace", size=11, color=COLORS['muted']),
    xaxis=dict(gridcolor=COLORS['gridline'], showgrid=True),
    yaxis=dict(gridcolor=COLORS['gridline'], showgrid=True),
    hoverlabel=dict(bgcolor=COLORS['surf2'], font=dict(color=COLORS['text'])),
)