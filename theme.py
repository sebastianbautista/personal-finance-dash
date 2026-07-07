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

# Colorblind-accessible alternative palette (deuteranopia/protanopia-safe).
# Substitutes the red/green diverging pair with blue/orange (standard)
COLORS_COLORBLIND = dict(
    bg='#0b0c0e',
    surface='#13151a',
    surf2='#1b1e26',
    border='#2a2e3a',
    border2='#363b4a',
    text='#dde0e8',
    muted='#6b7080',
    accent='#5B9BD5',    # blue, replaces green (was #7EB8A4)
    accentB='#A89FD8',   # kept — purple isn't part of the red-green conflict
    warn='#C8A96E',      # kept — amber/gold generally distinguishable
    danger='#E8973E',    # orange, replaces red (was #C87070)
    gridline='#1e2230',
)

PALETTES = dict(
    default=COLORS,
    colorblind=COLORS_COLORBLIND,
)

def get_plotly_theme(palette='default'):
    """
    Returns a PLOTLY_THEME dict built from the specified palette
    palette: 'default' or 'colorblind', matching PALETTES keys
    """
    colors = PALETTES.get(palette, COLORS) # fallback to default
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono, monospace", size=11, color=colors['muted']),
        xaxis=dict(gridcolor=colors['gridline'], showgrid=True),
        yaxis=dict(gridcolor=colors['gridline'], showgrid=True),
        hoverlabel=dict(bgcolor=colors['surf2'], font=dict(color=colors['text'])),
    )

PLOTLY_THEME = get_plotly_theme('default')