"""Global CSS theme — dual light/dark clinical dashboard.

Uses Streamlit's native CSS variables so the stylesheet automatically
adapts when the user switches between Light and Dark in Settings.
Called once from app.py on every page load.
"""

import streamlit as st


# Static design tokens for Python-side usage (Plotly, inline styles).
# These are defaults for light mode; use get_theme_colors() for runtime values.
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#3B82F6"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"

# Fallback values — only used where CSS variables cannot reach (Plotly, etc.)
TEXT = "#1E293B"
TEXT_MUTED = "#64748B"
BORDER = "#E2E8F0"

# Chart colors — these accent colors work on both light and dark
CHART_COLORS = [PRIMARY, SUCCESS, WARNING, DANGER, "#8B5CF6", "#EC4899", "#06B6D4", "#F97316"]


def _is_dark_theme() -> bool:
    """Detect whether the active Streamlit theme is dark.

    Checks multiple Streamlit theme options for reliability:
    1. theme.base — explicitly "dark" or "light"
    2. theme.backgroundColor — luminance analysis
    3. theme.textColor — if text is light, background is likely dark

    Returns:
        True if background color is dark, False otherwise.
    """
    # 1. Check explicit base theme setting
    try:
        base = st.get_option("theme.base")
        if base == "dark":
            return True
        if base == "light":
            return False
    except Exception:
        pass

    # 2. Check background color luminance
    try:
        bg = st.get_option("theme.backgroundColor")
        if bg and bg.startswith("#") and len(bg) >= 7:
            r = int(bg[1:3], 16)
            g = int(bg[3:5], 16)
            b = int(bg[5:7], 16)
            return (r * 299 + g * 587 + b * 114) / 1000 < 128
    except Exception:
        pass

    # 3. Check text color — light text implies dark background
    try:
        tc = st.get_option("theme.textColor")
        if tc and tc.startswith("#") and len(tc) >= 7:
            r = int(tc[1:3], 16)
            g = int(tc[3:5], 16)
            b = int(tc[5:7], 16)
            return (r * 299 + g * 587 + b * 114) / 1000 > 128
    except Exception:
        pass

    return False


def get_theme_colors() -> dict[str, str]:
    """Return color tokens adapted to the current theme.

    Returns:
        Dict with keys: text, text_muted, background, card_bg, sidebar_bg, border.
    """
    if _is_dark_theme():
        return {
            "text": "#E2E8F0",
            "text_muted": "#94A3B8",
            "background": "#0E1117",
            "card_bg": "#1A1D23",
            "sidebar_bg": "#161B22",
            "border": "#2D3748",
        }
    return {
        "text": "#1E293B",
        "text_muted": "#64748B",
        "background": "#FFFFFF",
        "card_bg": "#FFFFFF",
        "sidebar_bg": "#F8FAFC",
        "border": "#E2E8F0",
    }


def get_plotly_layout() -> dict:
    """Return Plotly layout defaults that respect the active theme.

    Returns:
        Dict suitable for fig.update_layout(**get_plotly_layout()).
    """
    colors = get_theme_colors()
    grid = colors["border"]
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["text"], family="Inter, sans-serif"),
        margin=dict(l=40, r=20, t=40, b=40),
        xaxis=dict(gridcolor=grid, zerolinecolor=grid),
        yaxis=dict(gridcolor=grid, zerolinecolor=grid),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=colors["text"])),
        hoverlabel=dict(
            bgcolor=colors["card_bg"],
            font_color=colors["text"],
            bordercolor=colors["border"],
        ),
    )


PLOTLY_CONFIG = {"displaylogo": False, "displayModeBar": False}


def inject_css() -> None:
    """Inject theme-adaptive CSS into the current Streamlit page.

    Uses Streamlit's own CSS custom properties so all colors
    automatically flip when the user switches themes in Settings.
    Must be called at the top of the main render, after st.set_page_config().
    """
    css_content = """
/* -- Import Inter font --------------------------------------------------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* -- Convenience aliases for Streamlit's theme variables ------------------ */
:root {
    --bg: var(--background-color);
    --bg2: var(--secondary-background-color);
    --fg: var(--text-color);
    --accent: var(--primary-color);
}

/* =========================================================================
   GLOBAL BASE
   ========================================================================= */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stAppViewBlockContainer"],
.main, .main .block-container,
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="block-container"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

[data-testid="stHeader"] {
    background-color: var(--bg) !important;
}

/* -- Scrollbar ----------------------------------------------------------- */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg2); }
::-webkit-scrollbar-thumb { background: var(--bg2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { opacity: 0.8; }

/* =========================================================================
   SIDEBAR
   ========================================================================= */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128, 128, 128, 0.3) !important;
}
section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
    font-size: 1.1rem !important;
    font-weight: 700 !important;
}

/* =========================================================================
   TYPOGRAPHY
   ========================================================================= */
h1, h2, h3, h4, h5, h6,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}

/* =========================================================================
   METRIC CARDS — equal size, theme-adaptive borders
   ========================================================================= */
[data-testid="stMetric"] {
    background-color: var(--bg) !important;
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 12px !important;
    padding: 16px 12px !important;
    height: 120px !important; /* Fixed height for all metric cards */
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    border-color: var(--accent) !important;
    box-shadow: 0 4px 12px color-mix(in srgb, var(--accent) 15%, transparent) !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.75rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    opacity: 0.7;
}
[data-testid="stMetricDelta"] {
    font-weight: 600 !important;
}

/* Force metric column containers to equal height */
[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    flex: 1 1 0 !important;
    min-width: 0 !important;
}

/* =========================================================================
   CONTAINERS, FORMS, EXPANDERS
   ========================================================================= */
[data-testid="stExpander"] {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 12px !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[style*="border"]) {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[style*="border"]):hover {
    border-color: color-mix(in srgb, var(--accent) 30%, transparent) !important;
    box-shadow: 0 2px 8px color-mix(in srgb, var(--fg) 5%, transparent) !important;
}

[data-testid="stForm"] {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 12px !important;
    padding: 24px !important;
}

/* =========================================================================
   BUTTONS
   ========================================================================= */
.stButton > button {
    background: linear-gradient(135deg, var(--accent) 0%, color-mix(in srgb, var(--accent) 80%, white) 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    letter-spacing: 0.01em;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px color-mix(in srgb, var(--accent) 25%, transparent) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}
.stButton > button[kind="secondary"] {
    background: var(--bg) !important;
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    color: var(--fg) !important;
}
.stDownloadButton > button {
    background: var(--bg) !important;
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    color: var(--fg) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}
.stDownloadButton > button:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}

/* =========================================================================
   INPUTS
   ========================================================================= */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stDateInput > div > div > input,
.stTimeInput > div > div > input {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s ease !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: none !important; /* Removed inner shadow */
}

/* =========================================================================
   SELECTBOX / DROPDOWN
   ========================================================================= */
.stSelectbox > div > div,
.stMultiSelect > div > div,
[data-baseweb="select"] > div {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 8px !important;
}
/* Dropdown menu items — hover uses subtle tint, not blue highlight */
ul[role="listbox"] > li:hover,
li[role="option"]:hover {
    background-color: var(--bg2) !important;
}
ul[role="listbox"] > li[aria-selected="true"],
li[role="option"][aria-selected="true"] {
    background-color: color-mix(in srgb, var(--accent) 12%, var(--bg)) !important;
}

/* =========================================================================
   TABS
   ========================================================================= */
.stTabs [data-baseweb="tab-list"] {
    gap: 24px;
    background-color: transparent !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 0 !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    padding-top: 8px !important;
    padding-bottom: 8px !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    transition: color 0.2s ease, opacity 0.2s ease !important;
    opacity: 0.65;
}
.stTabs [aria-selected="true"] {
    background: transparent !important;
    color: var(--fg) !important;
    font-weight: 600 !important;
    opacity: 1;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: var(--accent) !important;
    height: 3px !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
}
.stTabs [data-baseweb="tab-border"] {
    background-color: rgba(128, 128, 128, 0.2) !important;
}

/* =========================================================================
   DATAFRAMES / TABLES
   ========================================================================= */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden !important;
}
[data-testid="stDataFrame"] > div {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 12px !important;
}

/* =========================================================================
   ALERTS
   ========================================================================= */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
}

/* =========================================================================
   RADIO BUTTONS (sidebar navigation)
   ========================================================================= */
.stRadio > div {
    gap: 2px !important;
}
.stRadio > div > label {
    padding: 8px 12px !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
}
.stRadio > div > label:hover {
    background: color-mix(in srgb, var(--fg) 8%, transparent) !important;
}
/* Selected radio — uses foreground/background flip for contrast */
.stRadio > div > label[data-checked="true"],
.stRadio > div > label:has(input:checked) {
    background: var(--fg) !important;
}
.stRadio > div > label[data-checked="true"] span,
.stRadio > div > label[data-checked="true"] p,
.stRadio > div > label:has(input:checked) span,
.stRadio > div > label:has(input:checked) p {
    color: var(--bg) !important;
}

/* =========================================================================
   DIVIDERS
   ========================================================================= */
hr {
    border-color: rgba(128, 128, 128, 0.3) !important;
    opacity: 0.5;
}

/* =========================================================================
   CODE BLOCKS
   ========================================================================= */
[data-testid="stCode"] {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 8px !important;
}
[data-testid="stCode"] pre,
[data-testid="stCode"] code {
    border: none !important;
}

/* =========================================================================
   JSON VIEWER
   ========================================================================= */
[data-testid="stJson"],
[data-testid="stJson"] > div {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 8px !important;
}

/* =========================================================================
   PROGRESS BAR
   ========================================================================= */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--accent) 0%, #10B981 100%) !important;
    border-radius: 4px !important;
}

/* =========================================================================
   TOOLTIP
   ========================================================================= */
[data-testid="stTooltipContent"] {
    border: 1px solid rgba(128, 128, 128, 0.3) !important;
    border-radius: 8px !important;
}

/* =========================================================================
   LAYOUT
   ========================================================================= */
.main .block-container {
    animation: fadeIn 0.3s ease-in-out;
    padding-top: 2rem !important;
    max-width: 1400px !important;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
"""

    st.markdown(
        f"<style>\n{css_content}\n</style>",
        unsafe_allow_html=True,
    )
