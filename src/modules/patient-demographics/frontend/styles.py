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
    from pathlib import Path
    
    css_file_path = Path(__file__).parent / "styles.css"
    with open(css_file_path, "r") as f:
        css_content = f.read()

    st.markdown(
        f"<style>\n{css_content}\n</style>",
        unsafe_allow_html=True,
    )
