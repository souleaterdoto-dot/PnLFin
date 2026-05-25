"""Shared Dash styling constants."""

from __future__ import annotations


BG_FROM = "#EAF0F7"
BG_TO = "#F3F6FB"
SURFACE = "#FFFFFF"
SURFACE_ELEV = "#F6F9FD"
HAIRLINE = "#14285014"
HAIRLINE_STRONG = "#14285024"
TEXT = "#0F1F3D"
TEXT_DIM = "#54637D"
MUTED = "#8A95A8"
ACCENT = "#1E4A8C"
ACCENT_BRIGHT = "#2E6FD4"
ACCENT_SOFT = "#2E6FD41A"
ACCENT_GLOW = "#2E6FD438"
POSITIVE = "#2E7D8F"
NEGATIVE = "#C25450"


COLORS = {
    "bg": BG_FROM,
    "bg_to": BG_TO,
    "surface": SURFACE,
    "surface_alt": SURFACE_ELEV,
    "border": HAIRLINE,
    "border_strong": HAIRLINE_STRONG,
    "text": TEXT,
    "text_dim": TEXT_DIM,
    "muted": MUTED,
    "primary": ACCENT_BRIGHT,
    "primary_dark": ACCENT,
    "success": POSITIVE,
    "danger": NEGATIVE,
    "accent_soft": ACCENT_SOFT,
    "accent_glow": ACCENT_GLOW,
    "ink": TEXT,
}


CHART_TEMPLATE = "plotly_white"


PAGE_STYLE = {
    "minHeight": "100vh",
    "background": f"linear-gradient(135deg, {BG_FROM} 0%, {BG_TO} 100%)",
    "fontFamily": "'Inter', 'Segoe UI', Arial, sans-serif",
    "fontVariantNumeric": "tabular-nums",
    "color": TEXT,
    "padding": "22px",
}


CARD_STYLE = {
    "background": SURFACE,
    "border": f"1px solid {HAIRLINE}",
    "borderRadius": "16px",
    "boxShadow": "0 8px 24px #0F1F3D14",
}


KPI_STYLE = {
    **CARD_STYLE,
    "padding": "16px 18px",
}


FILTER_STYLE = {
    **CARD_STYLE,
    "padding": "16px",
    "display": "grid",
    "gridTemplateColumns": "1.2fr repeat(5, minmax(150px, 1fr))",
    "gap": "12px",
    "alignItems": "end",
}


GRAPH_CARD_STYLE = {
    **CARD_STYLE,
    "padding": "14px",
    "minHeight": "560px",
}


REFERRAL_GRID_STYLE = {
    "display": "grid",
    "gridTemplateColumns": "repeat(2, minmax(460px, 1fr))",
    "gap": "20px",
    "alignItems": "stretch",
}


REFERRAL_CARD_STYLE = {
    **CARD_STYLE,
    "padding": "24px",
    "minHeight": "520px",
}


REFERRAL_FILTER_STYLE = {
    "marginTop": "14px",
    "marginBottom": "12px",
}


TAB_STYLE = {
    "background": "transparent",
    "border": "0",
    "borderBottom": f"1px solid {HAIRLINE}",
    "borderRadius": "0",
    "padding": "0",
    "boxShadow": "none",
    "marginBottom": "18px",
}


HERO_STYLE = {
    **CARD_STYLE,
    "padding": "18px 20px",
    "background": SURFACE,
    "marginBottom": "16px",
}


CUSTOM_CSS = f"""
* {{
  box-sizing: border-box;
}}

.analytics-card {{
  transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}}

.analytics-card:hover {{
  border-color: {ACCENT_GLOW};
  box-shadow: 0 8px 32px {ACCENT_GLOW};
}}

.analytics-tab {{
  transition: color 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}}

.analytics-chip,
.analytics-filter-summary {{
  transition: background 140ms ease, border-color 140ms ease, color 140ms ease;
}}

.analytics-chip:hover,
.analytics-filter-summary:hover {{
  background: {ACCENT_SOFT};
}}

.analytics-filter-details {{
  position: relative;
}}

.analytics-filter-details > summary {{
  list-style: none;
}}

.analytics-filter-details > summary::-webkit-details-marker {{
  display: none;
}}

.analytics-hidden-filters {{
  display: none;
  position: absolute;
  right: 0;
  top: 36px;
  width: 520px;
  z-index: 20;
  padding: 12px;
  border: 1px solid {HAIRLINE_STRONG};
  border-radius: 12px;
  background: {SURFACE};
  box-shadow: 0 8px 24px #0F1F3D14;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}}

.analytics-filter-details[open] .analytics-hidden-filters {{
  display: grid;
}}

.analytics-dropdown-shell label {{
  color: {TEXT_DIM};
}}

.analytics-dropdown-shell .Select-control,
.analytics-dropdown-shell .Select-menu-outer {{
  border-color: {HAIRLINE_STRONG};
}}

.analytics-dropdown-shell .Select-placeholder,
.analytics-dropdown-shell .Select-value-label {{
  color: {TEXT_DIM};
}}

.analytics-operation-radio {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}}

.analytics-operation-radio-label {{
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 13px 0 10px;
  border-radius: 999px;
  border: 1px solid {HAIRLINE};
  background: {SURFACE_ELEV};
  color: {TEXT_DIM};
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease, box-shadow 160ms ease;
}}

.analytics-operation-radio-label input,
.analytics-chart-mode-label input {{
  cursor: pointer;
  flex: 0 0 auto;
}}

.analytics-operation-radio-label:hover {{
  background: {ACCENT_SOFT};
  border-color: {ACCENT_GLOW};
  color: {ACCENT};
}}

.analytics-operation-radio-label:has(input:checked) {{
  background: {ACCENT_SOFT};
  border-color: {ACCENT_BRIGHT};
  color: {ACCENT};
  box-shadow: 0 0 8px {ACCENT_GLOW};
}}

.analytics-chart-mode {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  border: 1px solid {HAIRLINE};
  border-radius: 999px;
  background: {SURFACE_ELEV};
}}

.analytics-chart-mode-label {{
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px 0 8px;
  border-radius: 999px;
  color: {TEXT_DIM};
  font-size: 10px;
  font-weight: 500;
  cursor: pointer;
  transition: background 160ms ease, color 160ms ease, box-shadow 160ms ease;
}}

.analytics-chart-mode-label:hover {{
  color: {ACCENT};
  background: {ACCENT_SOFT};
}}

.analytics-chart-mode-label:has(input:checked) {{
  background: {SURFACE};
  color: {ACCENT};
  box-shadow: 0 0 8px {ACCENT_GLOW};
}}

.analytics-date-input {{
  color-scheme: light;
}}

.analytics-date-input::-webkit-calendar-picker-indicator {{
  cursor: pointer;
  opacity: 0.72;
  filter: hue-rotate(185deg) saturate(1.4);
}}

.analytics-date-input:hover {{
  border-color: {ACCENT_GLOW} !important;
  background: {SURFACE} !important;
}}

.analytics-date-input:focus {{
  border-color: {ACCENT_BRIGHT} !important;
  box-shadow: 0 0 0 3px {ACCENT_SOFT};
}}

.analytics-client-referrals {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 12px;
}}

.analytics-client-referral-label {{
  min-height: 68px;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 12px 13px;
  border-radius: 16px;
  border: 1px solid {HAIRLINE};
  background: linear-gradient(135deg, {SURFACE} 0%, {SURFACE_ELEV} 100%);
  color: {TEXT_DIM};
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
  box-shadow: 0 8px 22px #0F1F3D0D;
}}

.analytics-client-referral-label:hover {{
  background: linear-gradient(135deg, {SURFACE} 0%, #EEF5FF 100%);
  border-color: {ACCENT_GLOW};
  color: {ACCENT};
  transform: translateY(-1px);
  box-shadow: 0 12px 28px {ACCENT_GLOW};
}}

.analytics-client-referral-label:has(input:checked) {{
  background: linear-gradient(135deg, {SURFACE} 0%, #EAF2FF 100%);
  border-color: {ACCENT_BRIGHT};
  color: {ACCENT};
  box-shadow: 0 12px 30px {ACCENT_GLOW};
}}

.analytics-client-referral-label input {{
  accent-color: {ACCENT_BRIGHT};
  flex: 0 0 auto;
}}

.analytics-client-referral-card-inner {{
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 auto;
  overflow: hidden;
}}

.analytics-clients-grid {{
  display: grid;
  grid-template-columns: repeat(5, minmax(160px, 1fr));
  gap: 12px;
}}

.analytics-client-card {{
  cursor: pointer;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}}

.analytics-client-card:hover {{
  border-color: {ACCENT_GLOW};
  box-shadow: 0 12px 32px {ACCENT_GLOW};
  transform: translateY(-2px);
}}

.analytics-modal-backdrop {{
  position: fixed;
  inset: 0;
  z-index: 1200;
  align-items: center;
  justify-content: center;
  padding: 28px;
  background: #0F1F3D66;
  backdrop-filter: blur(8px);
}}

.analytics-modal-card {{
  position: relative;
  width: min(980px, 96vw);
  max-height: 88vh;
  overflow: auto;
  border-radius: 20px;
  border: 1px solid {HAIRLINE_STRONG};
  background: {SURFACE};
  box-shadow: 0 24px 80px #0F1F3D38;
  padding: 24px;
}}

.analytics-modal-close {{
  position: absolute;
  top: 14px;
  right: 14px;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: 1px solid {HAIRLINE_STRONG};
  background: {SURFACE_ELEV};
  color: {TEXT_DIM};
  font-size: 22px;
  line-height: 28px;
  cursor: pointer;
}}

.analytics-modal-close:hover {{
  color: {ACCENT};
  border-color: {ACCENT_GLOW};
  background: {ACCENT_SOFT};
}}

.analytics-roi-kpis {{
  display: grid;
  grid-template-columns: repeat(4, minmax(140px, 1fr));
  gap: 10px;
}}
"""
