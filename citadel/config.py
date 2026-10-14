import calendar
from datetime import date, datetime, timezone
from dateutil import tz
import pandas as pd

WARSAW_TZ = tz.gettz("Europe/Warsaw")
DATA_ODCIECIA = date(2026, 10, 1)

def teraz_utc():
    return datetime.now(timezone.utc)

def dzis_pl():
    return datetime.now(WARSAW_TZ).date()

def formatuj_czas_pl(val):
    if val is None:
        return "b/d"
    try:
        if pd.isna(val):
            return "b/d"
    except (ValueError, TypeError):
        pass

    if isinstance(val, str):
        val_clean = val.strip().lower()
        if not val_clean or val_clean in ("none", "nat", "nan", "b/d", "null"):
            return "b/d"
        try:
            val = pd.to_datetime(val)
        except Exception:
            return str(val)

    if isinstance(val, (datetime, pd.Timestamp)):
        if pd.isna(val):
            return "b/d"
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.astimezone(WARSAW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    return str(val)

def parse_date(d):
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return pd.to_datetime(d).date()

def gr_na_pln(gr: int) -> float:
    return gr / 100.0

def pln_na_gr(pln: float) -> int:
    return int(round(pln * 100))

def format_pln(gr: int) -> str:
    return f"{(gr / 100.0):,.2f} zł"

KDI_STOPS = [
    (0.1, (22, 130, 60)),
    (0.5, (74, 222, 128)),
    (1.0, (255, 255, 255)),
    (1.2, (250, 204, 21)),
    (2.0, (249, 115, 22)),
    (3.0, (239, 68, 68)),
    (5.0, (236, 72, 153)),
    (10.0, (59, 130, 246)),
    (20.0, (168, 85, 247)),
]

def pobierz_kolor_kdi(wartosc):
    if wartosc is None:
        return "#64748b"
    try:
        val = float(wartosc)
    except (ValueError, TypeError):
        return "#64748b"

    if val <= KDI_STOPS[0][0]:
        r, g, b = KDI_STOPS[0][1]
        return f"#{r:02x}{g:02x}{b:02x}"
    if val >= KDI_STOPS[-1][0]:
        r, g, b = KDI_STOPS[-1][1]
        return f"#{r:02x}{g:02x}{b:02x}"

    for i in range(len(KDI_STOPS) - 1):
        v1, c1 = KDI_STOPS[i]
        v2, c2 = KDI_STOPS[i + 1]
        if v1 <= val <= v2:
            t = (val - v1) / (v2 - v1)
            r = int(c1[0] + t * (c2[0] - c1[0]))
            g = int(c1[1] + t * (c2[1] - c1[1]))
            b = int(c1[2] + t * (c2[2] - c1[2]))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#ffffff"

UPRAWNIENI_STOPS = [
    (100.0, (22, 130, 60)),
    (90.0,  (74, 222, 128)),
    (80.0,  (255, 255, 255)),
    (70.0,  (250, 204, 21)),
    (55.0,  (249, 115, 22)),
    (40.0,  (239, 68, 68)),
    (25.0,  (236, 72, 153)),
    (10.0,  (59, 130, 246)),
    (0.0,   (168, 85, 247)),
]

def pobierz_kolor_uprawnionych(procent):
    if procent is None:
        return "#64748b"
    try:
        val = float(procent)
    except (ValueError, TypeError):
        return "#64748b"

    if val >= UPRAWNIENI_STOPS[0][0]:
        r, g, b = UPRAWNIENI_STOPS[0][1]
        return f"#{r:02x}{g:02x}{b:02x}"
    if val <= UPRAWNIENI_STOPS[-1][0]:
        r, g, b = UPRAWNIENI_STOPS[-1][1]
        return f"#{r:02x}{g:02x}{b:02x}"

    for i in range(len(UPRAWNIENI_STOPS) - 1):
        v1, c1 = UPRAWNIENI_STOPS[i]
        v2, c2 = UPRAWNIENI_STOPS[i + 1]
        if v2 <= val <= v1:
            t = (v1 - val) / (v1 - v2)
            r = int(c1[0] + t * (c2[0] - c1[0]))
            g = int(c1[1] + t * (c2[1] - c1[1]))
            b = int(c1[2] + t * (c2[2] - c1[2]))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#ffffff"

DARK_THEME_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0b0914; color: #f1f5f9; }
    
    .bento-card {
        background: #151226;
        border: 1px solid #262040;
        border-radius: 18px;
        padding: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        margin-bottom: 20px;
    }
    .bento-card-header {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94a3b8;
        margin-bottom: 6px;
    }
    .bento-card-value { font-size: 1.8rem; font-weight: 700; color: #ffffff; }
    .bento-card-sub { font-size: 0.8rem; margin-top: 5px; color: #64748b; }
    
    .accent-purple { color: #a855f7; }
    .accent-cyan { color: #06b6d4; }
    .accent-green { color: #10b981; }
    .accent-rose { color: #f43f5e; }

    .user-pill {
        display: inline-flex;
        align-items: center;
        background: #191430;
        border: 1px solid #332658;
        border-radius: 12px;
        padding: 6px 14px;
        font-size: 0.88rem;
        color: #e2e8f0;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #120e20;
        padding: 6px;
        border-radius: 14px;
        border: 1px solid #231c38;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 10px;
        color: #94a3b8;
        border: none;
        padding: 0 16px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%) !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.35);
    }
    div[data-baseweb="tab-highlight"] {
        display: none !important;
    }
    div[data-baseweb="tab-border"] {
        background-color: transparent !important;
    }
    div[data-testid="stForm"] {
        background-color: #141028 !important;
        border: 1px solid #4338ca !important;
        border-radius: 16px !important;
        box-shadow: 0 0 22px rgba(99, 102, 241, 0.28) !important;
    }
    .stTextInput > div > div, .stNumberInput > div > div, .stSelectbox > div > div, .stDateInput > div > div {
        background-color: #161226 !important;
        border: 1px solid #2b2347 !important;
        border-radius: 10px !important;
        color: #ffffff !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stTextInput > div > div:hover, .stNumberInput > div > div:hover, .stSelectbox > div > div:hover, .stDateInput > div > div:hover {
        border-color: #4f46e5 !important;
    }
    .stTextInput > div > div:focus-within, .stNumberInput > div > div:focus-within, .stSelectbox > div > div:focus-within, .stDateInput > div > div:focus-within {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 14px rgba(139, 92, 246, 0.5) !important;
    }
    .stButton > button, div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 9px 22px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4) !important;
    }
    div[data-testid="stRadio"] label, div[data-testid="stRadio"] label p {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
    }
    .login-header-card {
        text-align: center;
        border: 1px solid #6366f1 !important;
        box-shadow: 0 0 25px rgba(99, 102, 241, 0.35) !important;
    }
    .profile-banner-card {
        background: #161228 !important;
        border: 1px solid #282046 !important;
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 18px;
        display: flex;
        gap: 24px;
        align-items: center;
        flex-wrap: wrap;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #282046 !important;
        border-radius: 12px !important;
    }
</style>
"""

MONO_THEME_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #141416; color: #f4f4f5; }
    
    .bento-card {
        background: #1c1c20;
        border: 1px solid #2e2e34;
        border-radius: 18px;
        padding: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.45);
        margin-bottom: 20px;
    }
    .bento-card-header {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #a1a1aa;
        margin-bottom: 6px;
    }
    .bento-card-value { font-size: 1.8rem; font-weight: 700; color: #ffffff; }
    .bento-card-sub { font-size: 0.8rem; margin-top: 5px; color: #71717a; }
    
    /* Dynamiczne kolory akcentów pozostają w 100% żywe i nasycone */
    .accent-purple { color: #c084fc; }
    .accent-cyan { color: #38bdf8; }
    .accent-green { color: #22c55e; }
    .accent-rose { color: #f43f5e; }

    .user-pill {
        display: inline-flex;
        align-items: center;
        background: #202025;
        border: 1px solid #33333a;
        border-radius: 12px;
        padding: 6px 14px;
        font-size: 0.88rem;
        color: #e4e4e7;
    }

    .profile-banner-card {
        background: #1c1c20 !important;
        border: 1px solid #2e2e34 !important;
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 18px;
        display: flex;
        gap: 24px;
        align-items: center;
        flex-wrap: wrap;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #18181b;
        padding: 6px;
        border-radius: 14px;
        border: 1px solid #2b2b30;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 10px;
        color: #a1a1aa;
        border: none;
        padding: 0 16px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #35353c 0%, #242429 100%) !important;
        color: #ffffff !important;
        border: 1px solid #4a4a54 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
    }
    div[data-baseweb="tab-highlight"] {
        display: none !important;
    }
    div[data-baseweb="tab-border"] {
        background-color: transparent !important;
    }

    div[data-testid="stForm"] {
        background-color: #1a1a1e !important;
        border: 1px solid #33333a !important;
        border-radius: 16px !important;
        box-shadow: 0 0 20px rgba(255, 255, 255, 0.04) !important;
    }
    .stTextInput > div > div, .stNumberInput > div > div, .stSelectbox > div > div, .stDateInput > div > div {
        background-color: #17171a !important;
        border: 1px solid #2f2f36 !important;
        border-radius: 10px !important;
        color: #ffffff !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stTextInput > div > div:hover, .stNumberInput > div > div:hover, .stSelectbox > div > div:hover, .stDateInput > div > div:hover {
        border-color: #52525b !important;
    }
    .stTextInput > div > div:focus-within, .stNumberInput > div > div:focus-within, .stSelectbox > div > div:focus-within, .stDateInput > div > div:focus-within {
        border-color: #a1a1aa !important;
        box-shadow: 0 0 14px rgba(255, 255, 255, 0.15) !important;
    }
    .stButton > button, div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #323238 0%, #202024 100%) !important;
        color: #ffffff !important;
        border: 1px solid #3f3f46 !important;
        border-radius: 10px !important;
        padding: 9px 22px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
        background: linear-gradient(135deg, #3f3f46 0%, #27272c 100%) !important;
        border-color: #5f5f68 !important;
        box-shadow: 0 0 16px rgba(255, 255, 255, 0.1) !important;
    }
    div[data-testid="stRadio"] label, div[data-testid="stRadio"] label p {
        color: #f4f4f5 !important;
        font-weight: 600 !important;
    }
    /* Usunięcie fioletowych akcentów z radio buttonów w trybie mono */
    div[data-testid="stRadio"] [data-testid="stRadioOption"] [class*="e1dm8mpf4"],
    div[data-testid="stRadio"] [data-testid="stRadioOption"] > label > div:first-child,
    div[data-testid="stRadio"] [data-testid="stRadioGroup"] [aria-checked="true"] > div {
        border-color: #71717a !important;
        background-color: #3f3f46 !important;
    }
    div[data-testid="stRadio"] [data-testid="stRadioOption"] [class*="e1dm8mpf5"] {
        background-color: #ffffff !important;
    }
    div[data-testid="stRadio"] [data-testid="stRadioOption"]:hover [class*="e1dm8mpf4"] {
        border-color: #a1a1aa !important;
    }

    /* Tabele stDataFrame - dynamiczna desaturacja fioletowego canvasu do neutralnej szarości */
    div[data-testid="stDataFrame"] canvas[data-testid="data-grid-canvas"],
    div[data-testid="stDataFrame"] canvas {
        filter: saturate(0) brightness(1.15) !important;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #2e2e34 !important;
        border-radius: 12px !important;
        --gdg-bg-header: #1c1c20 !important;
        --gdg-bg-header-hovered: #26262b !important;
        --gdg-bg-header-has-focus: #26262b !important;
        --gdg-bg-cell: #141416 !important;
        --gdg-bg-cell-medium: #18181b !important;
        --gdg-border-color: #2e2e34 !important;
        --gdg-horizontal-border-color: #27272c !important;
        --gdg-accent-color: #71717a !important;
        --gdg-accent-light: rgba(255, 255, 255, 0.08) !important;
        --gdg-text-header: #d4d4d8 !important;
        --gdg-text-dark: #f4f4f5 !important;
        --gdg-text-medium: #a1a1aa !important;
    }

    .login-header-card {
        text-align: center;
        border: 1px solid #33333a !important;
        box-shadow: 0 0 25px rgba(255, 255, 255, 0.08) !important;
    }
</style>
"""

def pobierz_motyw_css(tryb_mono: bool = False) -> str:
    return MONO_THEME_CSS if tryb_mono else DARK_THEME_CSS