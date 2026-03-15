"""Global CSS theme — clean light clinical dashboard.

Injects a single <style> block into Streamlit that sets a consistent
light theme. Called once from app.py on every page load.
"""

import streamlit as st


# Design tokens — light theme
BACKGROUND = "#FFFFFF"
SIDEBAR_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#3B82F6"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"
TEXT = "#1E293B"
TEXT_MUTED = "#64748B"
BORDER = "#E2E8F0"
GRID = "#E2E8F0"

# Plotly layout defaults — importable by any page that builds charts
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family="Inter, sans-serif"),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
    yaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT)),
    hoverlabel=dict(bgcolor=CARD_BG, font_color=TEXT, bordercolor=BORDER),
)

PLOTLY_CONFIG = {"displaylogo": False, "displayModeBar": False}

# Color sequence for charts
CHART_COLORS = [PRIMARY, SUCCESS, WARNING, DANGER, "#8B5CF6", "#EC4899", "#06B6D4", "#F97316"]


def inject_css() -> None:
    """Inject the complete light-theme CSS into the current Streamlit page.

    Must be called at the top of the main render, after st.set_page_config().
    """
    st.markdown(
        f"""
<style>
/* -- Import Inter font --------------------------------------------------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* -- Root variables ------------------------------------------------------ */
:root {{
    --background: {BACKGROUND};
    --sidebar-bg: {SIDEBAR_BG};
    --card-bg: {CARD_BG};
    --primary: {PRIMARY};
    --primary-hover: {PRIMARY_HOVER};
    --success: {SUCCESS};
    --warning: {WARNING};
    --danger: {DANGER};
    --text: {TEXT};
    --text-muted: {TEXT_MUTED};
    --border: {BORDER};
}}

/* =========================================================================
   GLOBAL BASE — force light on every surface
   ========================================================================= */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppViewBlockContainer"],
.main, .main .block-container,
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="block-container"] {{
    background-color: {BACKGROUND} !important;
    color: {TEXT} !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}

/* Hide Streamlit branding */
[data-testid="stHeader"] {{
    background-color: {BACKGROUND} !important;
}}
footer, #MainMenu {{
    visibility: hidden !important;
}}

/* -- Scrollbar ----------------------------------------------------------- */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {SIDEBAR_BG}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {TEXT_MUTED}; }}

/* =========================================================================
   SIDEBAR
   ========================================================================= */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div > div,
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: {SIDEBAR_BG} !important;
    color: {TEXT} !important;
}}
section[data-testid="stSidebar"] {{
    border-right: 1px solid {BORDER} !important;
}}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown {{
    color: {TEXT} !important;
}}
section[data-testid="stSidebar"] [data-testid="stMetricValue"] {{
    color: {TEXT} !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
}}
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] {{
    color: {TEXT_MUTED} !important;
}}

/* =========================================================================
   TYPOGRAPHY
   ========================================================================= */
h1, h2, h3, h4, h5, h6,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {{
    color: {TEXT} !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}}

p, span, li, label, div,
.stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown li,
.stText, [data-testid="stText"] {{
    color: {TEXT} !important;
}}
.stCaption, [data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {{
    color: {TEXT_MUTED} !important;
}}

/* =========================================================================
   METRIC CARDS — equal size
   ========================================================================= */
[data-testid="stMetric"] {{
    background-color: {CARD_BG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    padding: 20px 16px !important;
    min-height: 110px !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}}
[data-testid="stMetric"]:hover {{
    transform: translateY(-2px);
    border-color: {PRIMARY} !important;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1) !important;
}}
[data-testid="stMetricValue"] {{
    color: {TEXT} !important;
    font-size: 2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em;
}}
[data-testid="stMetricLabel"] {{
    color: {TEXT_MUTED} !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}}
[data-testid="stMetricDelta"] {{
    font-weight: 600 !important;
}}

/* Force metric column containers to equal height */
[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
    flex: 1 1 0 !important;
    min-width: 0 !important;
}}

/* =========================================================================
   CONTAINERS, FORMS, EXPANDERS
   ========================================================================= */
[data-testid="stExpander"],
[data-testid="stForm"],
div[data-testid="stVerticalBlockBorderWrapper"] > div:has(> [data-testid="stVerticalBlock"]) {{
    border-color: {BORDER} !important;
}}
[data-testid="stExpander"] {{
    background-color: {CARD_BG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
}}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary p {{
    color: {TEXT} !important;
    background-color: transparent !important;
}}
[data-testid="stExpander"] details {{
    background-color: {CARD_BG} !important;
}}
[data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
    background-color: {CARD_BG} !important;
}}

/* bordered containers */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[style*="border"]) {{
    background-color: {CARD_BG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[style*="border"]):hover {{
    border-color: rgba(37, 99, 235, 0.3) !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
}}

[data-testid="stForm"] {{
    background-color: {CARD_BG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    padding: 24px !important;
}}

/* =========================================================================
   BUTTONS
   ========================================================================= */
.stButton > button {{
    background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_HOVER} 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    letter-spacing: 0.01em;
}}
.stButton > button:hover {{
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25) !important;
}}
.stButton > button:active {{
    transform: translateY(0) !important;
}}
.stButton > button[kind="secondary"] {{
    background: {CARD_BG} !important;
    border: 1px solid {BORDER} !important;
    color: {TEXT} !important;
}}
.stDownloadButton > button {{
    background: {CARD_BG} !important;
    border: 1px solid {BORDER} !important;
    color: {TEXT} !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}}
.stDownloadButton > button:hover {{
    border-color: {PRIMARY} !important;
    color: {PRIMARY} !important;
}}

/* =========================================================================
   INPUTS — text, number, date, textarea
   ========================================================================= */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stDateInput > div > div > input,
.stTimeInput > div > div > input,
input[type="text"],
input[type="number"],
textarea {{
    background-color: {BACKGROUND} !important;
    color: {TEXT} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s ease !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {PRIMARY} !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
}}

/* Input labels */
.stTextInput label, .stTextArea label, .stNumberInput label,
.stDateInput label, .stTimeInput label, .stSelectbox label,
.stMultiSelect label, .stRadio label, .stCheckbox label {{
    color: {TEXT} !important;
}}

/* =========================================================================
   SELECTBOX / DROPDOWN — full override for dark mode internals
   ========================================================================= */
.stSelectbox > div > div,
.stMultiSelect > div > div,
[data-baseweb="select"] > div,
[data-baseweb="select"] {{
    background-color: {BACKGROUND} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    color: {TEXT} !important;
}}
/* Selected value text */
[data-baseweb="select"] span,
[data-baseweb="select"] div[class*="ValueContainer"] span,
[data-baseweb="select"] [data-testid="stMarkdownContainer"] {{
    color: {TEXT} !important;
}}
/* Dropdown menu */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-baseweb="menu"] > div,
ul[role="listbox"],
ul[role="listbox"] > li {{
    background-color: {BACKGROUND} !important;
    color: {TEXT} !important;
    border-color: {BORDER} !important;
}}
/* Dropdown option hover — subtle gray, not blue */
ul[role="listbox"] > li:hover,
ul[role="listbox"] > li[aria-selected="true"],
[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] li[aria-selected="true"],
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {{
    background-color: {SIDEBAR_BG} !important;
    color: {TEXT} !important;
}}
/* Dropdown option text */
ul[role="listbox"] > li > div,
[data-baseweb="menu"] li span,
li[role="option"] span {{
    color: {TEXT} !important;
}}
/* Dropdown search input */
[data-baseweb="popover"] input {{
    background-color: {BACKGROUND} !important;
    color: {TEXT} !important;
    border-color: {BORDER} !important;
}}

/* =========================================================================
   TABS — selected tab uses teal accent, not blue highlight
   ========================================================================= */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    background-color: {SIDEBAR_BG} !important;
    border-radius: 10px !important;
    padding: 4px !important;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    color: {TEXT_MUTED} !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 8px 16px !important;
    transition: all 0.2s ease !important;
}}
.stTabs [aria-selected="true"] {{
    background: {TEXT} !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}}
/* Tab highlight bar — remove the blue underline */
.stTabs [data-baseweb="tab-highlight"] {{
    background-color: transparent !important;
}}
.stTabs [data-baseweb="tab-border"] {{
    background-color: transparent !important;
}}

/* =========================================================================
   DATAFRAMES / TABLES
   ========================================================================= */
[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden !important;
}}
[data-testid="stDataFrame"] > div {{
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
}}
/* Table header and cells */
[data-testid="stDataFrame"] th {{
    background-color: {SIDEBAR_BG} !important;
    color: {TEXT} !important;
}}
[data-testid="stDataFrame"] td {{
    background-color: {BACKGROUND} !important;
    color: {TEXT} !important;
}}

/* =========================================================================
   ALERT / INFO / SUCCESS / WARNING / ERROR boxes
   ========================================================================= */
[data-testid="stAlert"] {{
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
}}

/* =========================================================================
   RADIO BUTTONS — sidebar nav selection style (no blue)
   ========================================================================= */
.stRadio > div {{
    gap: 2px !important;
}}
.stRadio > div > label {{
    padding: 8px 12px !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
    color: {TEXT} !important;
    background: transparent !important;
}}
.stRadio > div > label:hover {{
    background: rgba(30, 41, 59, 0.06) !important;
}}
/* Selected radio — dark pill, white text */
.stRadio > div > label[data-checked="true"],
.stRadio > div > label:has(input:checked) {{
    background: {TEXT} !important;
    color: #FFFFFF !important;
}}
.stRadio > div > label[data-checked="true"] span,
.stRadio > div > label[data-checked="true"] p,
.stRadio > div > label:has(input:checked) span,
.stRadio > div > label:has(input:checked) p {{
    color: #FFFFFF !important;
}}

/* =========================================================================
   CHECKBOX
   ========================================================================= */
.stCheckbox label span {{
    color: {TEXT} !important;
}}

/* =========================================================================
   DIVIDERS
   ========================================================================= */
hr {{
    border-color: {BORDER} !important;
    opacity: 0.5;
}}

/* =========================================================================
   CODE BLOCKS
   ========================================================================= */
pre, code, .stCode,
[data-testid="stCode"],
[data-testid="stCode"] pre {{
    background-color: {SIDEBAR_BG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    color: {TEXT} !important;
}}

/* =========================================================================
   JSON VIEWER
   ========================================================================= */
[data-testid="stJson"],
[data-testid="stJson"] > div {{
    background-color: {SIDEBAR_BG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    color: {TEXT} !important;
}}

/* =========================================================================
   SPINNER
   ========================================================================= */
[data-testid="stSpinner"] > div {{
    border-top-color: {PRIMARY} !important;
}}

/* =========================================================================
   PROGRESS BAR
   ========================================================================= */
.stProgress > div > div > div {{
    background: linear-gradient(90deg, {PRIMARY} 0%, {SUCCESS} 100%) !important;
    border-radius: 4px !important;
}}

/* =========================================================================
   TOOLTIP
   ========================================================================= */
[data-testid="stTooltipContent"] {{
    background: {CARD_BG} !important;
    color: {TEXT} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}

/* =========================================================================
   STREAMLIT INTERNAL DARK-MODE OVERRIDES
   ========================================================================= */
/* Widget containers and wrappers */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span {{
    color: {TEXT} !important;
}}

/* Popover / date picker / modal backgrounds */
[data-baseweb="popover"] > div,
[data-baseweb="calendar"] {{
    background-color: {BACKGROUND} !important;
    color: {TEXT} !important;
}}
[data-baseweb="calendar"] div {{
    color: {TEXT} !important;
}}

/* Number input +/- buttons */
.stNumberInput button {{
    background-color: {SIDEBAR_BG} !important;
    border-color: {BORDER} !important;
    color: {TEXT} !important;
}}

/* Multiselect tags */
[data-baseweb="tag"] {{
    background-color: {SIDEBAR_BG} !important;
    color: {TEXT} !important;
}}

/* Ensure all icon SVGs in Streamlit widgets are visible */
.stSelectbox svg, .stMultiSelect svg,
.stDateInput svg, .stTimeInput svg,
.stNumberInput svg {{
    fill: {TEXT_MUTED} !important;
}}

/* Bottom padding for page content */
.main .block-container {{
    animation: fadeIn 0.3s ease-in-out;
    padding-top: 2rem !important;
    max-width: 1400px !important;
}}
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
