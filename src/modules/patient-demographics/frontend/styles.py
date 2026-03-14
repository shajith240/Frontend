"""Global CSS theme — deep navy clinical dashboard with glassmorphism cards.

Injects a single <style> block into Streamlit that overrides the default
light theme. Called once from app.py on every page load.
"""

import streamlit as st


# Design tokens
NAVY = "#0A0F1E"
NAVY_LIGHT = "#111827"
NAVY_CARD = "#1E293B"
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#3B82F6"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"
TEXT = "#F8FAFC"
TEXT_MUTED = "#94A3B8"
BORDER = "#334155"
GRID = "#1E293B"

# Plotly layout defaults — importable by any page that builds charts
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family="Inter, sans-serif"),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
    yaxis=dict(gridcolor=GRID, zerolinecolor=GRID),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT)),
    hoverlabel=dict(bgcolor=NAVY_CARD, font_color=TEXT, bordercolor=BORDER),
)

PLOTLY_CONFIG = {"displaylogo": False, "displayModeBar": False}

# Color sequence for charts
CHART_COLORS = [PRIMARY, SUCCESS, WARNING, DANGER, "#8B5CF6", "#EC4899", "#06B6D4", "#F97316"]


def inject_css() -> None:
    """Inject the complete dark-theme CSS into the current Streamlit page.

    Must be called at the top of the main render, after st.set_page_config().
    """
    st.markdown(
        f"""
<style>
/* ── Import Inter font ─────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Root variables ────────────────────────────────────────── */
:root {{
    --navy: {NAVY};
    --navy-light: {NAVY_LIGHT};
    --navy-card: {NAVY_CARD};
    --primary: {PRIMARY};
    --primary-hover: {PRIMARY_HOVER};
    --success: {SUCCESS};
    --warning: {WARNING};
    --danger: {DANGER};
    --text: {TEXT};
    --text-muted: {TEXT_MUTED};
    --border: {BORDER};
}}

/* ── Global base ───────────────────────────────────────────── */
.stApp {{
    background: linear-gradient(135deg, {NAVY} 0%, {NAVY_LIGHT} 100%) !important;
    color: {TEXT} !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}

/* ── Scrollbar ─────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {NAVY}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {TEXT_MUTED}; }}

/* ── Sidebar ───────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {NAVY} 0%, {NAVY_LIGHT} 100%) !important;
    border-right: 1px solid {BORDER} !important;
}}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] label {{
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

/* ── Headers ───────────────────────────────────────────────── */
h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
    color: {TEXT} !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}}

/* ── Text ──────────────────────────────────────────────────── */
p, span, li, label, .stMarkdown, .stText {{
    color: {TEXT} !important;
}}
.stCaption, [data-testid="stCaptionContainer"] {{
    color: {TEXT_MUTED} !important;
}}

/* ── Metric cards ──────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: rgba(30, 41, 59, 0.6) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(51, 65, 85, 0.5) !important;
    border-radius: 12px !important;
    padding: 20px 16px !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}}
[data-testid="stMetric"]:hover {{
    transform: translateY(-2px);
    border-color: {PRIMARY} !important;
    box-shadow: 0 8px 25px rgba(37, 99, 235, 0.15) !important;
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

/* ── Glassmorphism containers ──────────────────────────────── */
[data-testid="stExpander"],
[data-testid="stForm"],
div[data-testid="stVerticalBlockBorderWrapper"] > div:has(> [data-testid="stVerticalBlock"]) {{
    border-color: {BORDER} !important;
}}
[data-testid="stExpander"] {{
    background: rgba(30, 41, 59, 0.4) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
}}
[data-testid="stExpander"] summary {{
    color: {TEXT} !important;
}}

/* bordered containers */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[style*="border"]) {{
    background: rgba(30, 41, 59, 0.4) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[style*="border"]):hover {{
    border-color: rgba(37, 99, 235, 0.4) !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
}}

/* ── Buttons ───────────────────────────────────────────────── */
.stButton > button {{
    background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_HOVER} 100%) !important;
    color: {TEXT} !important;
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
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35) !important;
}}
.stButton > button:active {{
    transform: translateY(0) !important;
}}
/* secondary / non-primary buttons */
.stButton > button[kind="secondary"] {{
    background: rgba(30, 41, 59, 0.6) !important;
    border: 1px solid {BORDER} !important;
}}

/* ── Form ──────────────────────────────────────────────────── */
[data-testid="stForm"] {{
    background: rgba(30, 41, 59, 0.4) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    padding: 24px !important;
}}

/* ── Inputs ────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {{
    background: rgba(15, 23, 42, 0.8) !important;
    color: {TEXT} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s ease !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {PRIMARY} !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2) !important;
}}

/* Selectbox / dropdown */
.stSelectbox > div > div,
.stMultiSelect > div > div {{
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    color: {TEXT} !important;
}}

/* ── Tabs ──────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    background: rgba(15, 23, 42, 0.6) !important;
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
    background: {PRIMARY} !important;
    color: {TEXT} !important;
    font-weight: 600 !important;
}}

/* ── Dataframes ────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden !important;
}}
[data-testid="stDataFrame"] > div {{
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
}}

/* ── Alert / Info / Success / Warning / Error boxes ────────── */
[data-testid="stAlert"] {{
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    backdrop-filter: blur(4px) !important;
}}

/* ── Dividers ──────────────────────────────────────────────── */
hr {{
    border-color: {BORDER} !important;
    opacity: 0.5;
}}

/* ── Code blocks ───────────────────────────────────────────── */
pre, code, .stCode {{
    background: rgba(15, 23, 42, 0.9) !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
}}

/* ── Spinner ───────────────────────────────────────────────── */
[data-testid="stSpinner"] > div {{
    border-top-color: {PRIMARY} !important;
}}

/* ── Radio buttons in sidebar ──────────────────────────────── */
.stRadio > div {{
    gap: 2px !important;
}}
.stRadio > div > label {{
    padding: 8px 12px !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
}}
.stRadio > div > label:hover {{
    background: rgba(37, 99, 235, 0.1) !important;
}}
.stRadio > div > label[data-checked="true"] {{
    background: rgba(37, 99, 235, 0.2) !important;
}}

/* ── Progress bar ──────────────────────────────────────────── */
.stProgress > div > div > div {{
    background: linear-gradient(90deg, {PRIMARY} 0%, {SUCCESS} 100%) !important;
    border-radius: 4px !important;
}}

/* ── JSON viewer ───────────────────────────────────────────── */
[data-testid="stJson"] {{
    background: rgba(15, 23, 42, 0.9) !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}

/* ── Smooth transitions for page content ───────────────────── */
.main .block-container {{
    animation: fadeIn 0.3s ease-in-out;
    padding-top: 2rem !important;
    max-width: 1400px !important;
}}
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

/* ── Pulse animation for alert dots ────────────────────────── */
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.5; }}
}}
.pulse-dot {{
    animation: pulse 2s ease-in-out infinite;
}}

/* ── Skeleton loading shimmer ──────────────────────────────── */
@keyframes shimmer {{
    0% {{ background-position: -200% 0; }}
    100% {{ background-position: 200% 0; }}
}}
.skeleton {{
    background: linear-gradient(
        90deg,
        rgba(30, 41, 59, 0.4) 25%,
        rgba(51, 65, 85, 0.4) 50%,
        rgba(30, 41, 59, 0.4) 75%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
    border-radius: 8px;
}}

/* ── Tooltip dark theme ────────────────────────────────────── */
[data-testid="stTooltipContent"] {{
    background: {NAVY_CARD} !important;
    color: {TEXT} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )
