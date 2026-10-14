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
    .stButton > button,
    .stButton > button *,
    .stButton > button p,
    .stButton > button span,
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stFormSubmitButton"] > button *,
    div[data-testid="stFormSubmitButton"] > button p,
    div[data-testid="stFormSubmitButton"] > button span,
    div[data-testid="stDownloadButton"] > button,
    div[data-testid="stDownloadButton"] > button * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    .stButton > button, div[data-testid="stFormSubmitButton"] > button, div[data-testid="stDownloadButton"] > button {
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
    .stButton > button,
    .stButton > button *,
    .stButton > button p,
    .stButton > button span,
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stFormSubmitButton"] > button *,
    div[data-testid="stFormSubmitButton"] > button p,
    div[data-testid="stFormSubmitButton"] > button span,
    div[data-testid="stDownloadButton"] > button,
    div[data-testid="stDownloadButton"] > button * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    .stButton > button, div[data-testid="stFormSubmitButton"] > button, div[data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #323238 0%, #202024 100%) !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: 1px solid #3f3f46 !important;
        border-radius: 10px !important;
        padding: 9px 22px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover, div[data-testid="stDownloadButton"] > button:hover {
        background: linear-gradient(135deg, #3f3f46 0%, #27272c 100%) !important;
        border-color: #5f5f68 !important;
        box-shadow: 0 0 16px rgba(255, 255, 255, 0.1) !important;
    }
    .stButton > button:hover *, div[data-testid="stFormSubmitButton"] > button:hover *, div[data-testid="stDownloadButton"] > button:hover * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
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

    /* Tabele stDataFrame - zachowanie żywych kolorów wskaźników KDI oraz statusu TAK/NIE */
    div[data-testid="stDataFrame"] {
        border: 1px solid #2e2e34 !important;
        border-radius: 12px !important;
    }

    .login-header-card {
        text-align: center;
        border: 1px solid #33333a !important;
        box-shadow: 0 0 25px rgba(255, 255, 255, 0.08) !important;
    }
</style>
"""

LIGHT_MONO_THEME_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    :root, .stApp {
        background-color: #f8fafc !important;
        color: #0f172a !important;
        --text-color: #0f172a !important;
        --background-color: #f8fafc !important;
        --secondary-background-color: #f1f5f9 !important;
        --primary-color: #0f172a !important;
    }
    
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }

    /* Ogólna typografia bazowa dla jasnego motywu */
    .stApp, .stApp p, .stApp span, .stApp label, .stApp li, .stApp small {
        color: #0f172a;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }

    /* Wszystkie etykiety pól (input, selectbox, date, radio itp.) */
    label,
    label p,
    label span,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    div[data-testid="stWidgetLabel"] p,
    div[data-testid="stWidgetLabel"] span {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        font-weight: 600 !important;
    }

    /* Karty Bento */
    .bento-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        padding: 20px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }
    .bento-card-header {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        margin-bottom: 6px;
    }
    .bento-card-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0f172a;
    }
    .bento-card-sub {
        font-size: 0.8rem;
        margin-top: 5px;
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
    }
    
    /* Dynamiczne kolory akcentów w jasnym trybie - żywe, eleganckie i czytelne */
    .accent-purple { color: #9333ea !important; -webkit-text-fill-color: #9333ea !important; }
    .accent-cyan { color: #0284c7 !important; -webkit-text-fill-color: #0284c7 !important; }
    .accent-green { color: #16a34a !important; -webkit-text-fill-color: #16a34a !important; }
    .accent-rose { color: #e11d48 !important; -webkit-text-fill-color: #e11d48 !important; }

    .user-pill {
        display: inline-flex;
        align-items: center;
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        padding: 6px 14px;
        font-size: 0.88rem;
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }

    .profile-banner-card {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 18px;
        display: flex;
        gap: 24px;
        align-items: center;
        flex-wrap: wrap;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
    }
    .profile-banner-card span {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
    }

    /* Zakładki - zarówno poziomu 1 jak i podrzędne poziomu 2 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 14px;
        border: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 10px;
        border: none;
        padding: 0 16px;
        font-weight: 500;
        background-color: transparent !important;
    }
    .stTabs [data-baseweb="tab"],
    .stTabs [data-baseweb="tab"] *,
    .stTabs [data-baseweb="tab"] p,
    .stTabs [data-baseweb="tab"] div,
    .stTabs [data-baseweb="tab"] span {
        color: #334155 !important;
        -webkit-text-fill-color: #334155 !important;
    }
    .stTabs [data-baseweb="tab"]:hover,
    .stTabs [data-baseweb="tab"]:hover * {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"],
    .stTabs [data-baseweb="tab"][aria-selected="true"] *,
    .stTabs [data-baseweb="tab"][aria-selected="true"] p,
    .stTabs [data-baseweb="tab"][aria-selected="true"] span {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        font-weight: 700 !important;
    }
    div[data-baseweb="tab-highlight"] {
        display: none !important;
    }
    div[data-baseweb="tab-border"] {
        background-color: transparent !important;
    }

    /* Formularze i pola edycyjne */
    div[data-testid="stForm"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04) !important;
    }
    .stTextInput > div > div, .stNumberInput > div > div, .stSelectbox > div > div, .stDateInput > div > div {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 10px !important;
        color: #0f172a !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stTextInput > div > div:hover, .stNumberInput > div > div:hover, .stSelectbox > div > div:hover, .stDateInput > div > div:hover {
        border-color: #94a3b8 !important;
    }
    .stTextInput > div > div:focus-within, .stNumberInput > div > div:focus-within, .stSelectbox > div > div:focus-within, .stDateInput > div > div:focus-within {
        border-color: #0f172a !important;
        box-shadow: 0 0 12px rgba(15, 23, 42, 0.12) !important;
    }

    /* Wartości wpisywane i wybrane wewnątrz pól tekstowych / selectboxów */
    input, textarea, select {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        background-color: #ffffff !important;
    }
    input::placeholder, textarea::placeholder {
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
    }
    div[data-baseweb="select"],
    div[data-baseweb="select"] *,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    div[data-baseweb="select"] svg {
        fill: #0f172a !important;
    }

    /* Pola zablokowane (disabled) */
    input:disabled,
    textarea:disabled,
    div[aria-disabled="true"],
    div[aria-disabled="true"] * {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        background-color: #f8fafc !important;
    }

    /* Menu rozwijane (Popovers i listy opcji) */
    div[data-baseweb="popover"],
    div[data-baseweb="menu"],
    ul[role="listbox"],
    li[role="option"] {
        background-color: #ffffff !important;
    }
    div[data-baseweb="popover"] *,
    div[data-baseweb="menu"] *,
    ul[role="listbox"] *,
    li[role="option"] * {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    li[role="option"]:hover,
    li[role="option"]:hover * {
        background-color: #f1f5f9 !important;
    }
    li[role="option"][aria-selected="true"],
    li[role="option"][aria-selected="true"] * {
        background-color: #e2e8f0 !important;
        font-weight: 600 !important;
    }

    /* Przyciski - jednoznaczne białe litery na ciemnym tle, odporne na kaskadę */
    .stButton > button,
    .stButton > button *,
    .stButton > button p,
    .stButton > button span,
    .stButton > button div,
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stFormSubmitButton"] > button *,
    div[data-testid="stFormSubmitButton"] > button p,
    div[data-testid="stFormSubmitButton"] > button span,
    div[data-testid="stFormSubmitButton"] > button div,
    div[data-testid="stDownloadButton"] > button,
    div[data-testid="stDownloadButton"] > button *,
    div[data-testid="stDownloadButton"] > button p,
    div[data-testid="stDownloadButton"] > button span,
    div[data-testid="stDownloadButton"] > button div {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    .stButton > button, div[data-testid="stFormSubmitButton"] > button, div[data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: 1px solid #0f172a !important;
        border-radius: 10px !important;
        padding: 9px 22px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.15) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover, div[data-testid="stDownloadButton"] > button:hover {
        background: linear-gradient(135deg, #334155 0%, #1e293b 100%) !important;
        border-color: #334155 !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.22) !important;
    }
    .stButton > button:hover *, div[data-testid="stFormSubmitButton"] > button:hover *, div[data-testid="stDownloadButton"] > button:hover * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    .stButton > button:disabled,
    .stButton > button:disabled *,
    div[data-testid="stFormSubmitButton"] > button:disabled,
    div[data-testid="stFormSubmitButton"] > button:disabled *,
    div[data-testid="stDownloadButton"] > button:disabled,
    div[data-testid="stDownloadButton"] > button:disabled * {
        background: #e2e8f0 !important;
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
        border-color: #cbd5e1 !important;
        cursor: not-allowed !important;
        box-shadow: none !important;
    }

    /* Radio buttony i Checkboxy */
    div[data-testid="stRadio"] label,
    div[data-testid="stRadio"] label p,
    div[data-testid="stRadio"] label span,
    div[data-testid="stCheckbox"] label,
    div[data-testid="stCheckbox"] label p,
    div[data-testid="stCheckbox"] label span {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        font-weight: 600 !important;
    }
    div[data-testid="stRadio"] [data-testid="stRadioOption"] [class*="e1dm8mpf4"],
    div[data-testid="stRadio"] [data-testid="stRadioOption"] > label > div:first-child,
    div[data-testid="stRadio"] [data-testid="stRadioGroup"] [aria-checked="true"] > div {
        border-color: #0f172a !important;
        background-color: #0f172a !important;
    }
    div[data-testid="stRadio"] [data-testid="stRadioOption"] [class*="e1dm8mpf5"] {
        background-color: #ffffff !important;
    }
    div[data-testid="stRadio"] [data-testid="stRadioOption"]:hover [class*="e1dm8mpf4"] {
        border-color: #475569 !important;
    }

    /* Komunikaty alertów st.warning, st.info, st.error, st.success */
    div[data-testid="stAlert"] {
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
    }
    div[data-testid="stAlert"],
    div[data-testid="stAlert"] *,
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] div {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }

    /* Teksty w kontenerach Markdown i Caption (z wykluczeniem przycisków i wskaźników) */
    div[data-testid="stMarkdownContainer"]:not(button *):not(.bento-card-value),
    div[data-testid="stMarkdownContainer"]:not(button *):not(.bento-card-value) > p,
    div[data-testid="stMarkdownContainer"]:not(button *):not(.bento-card-value) > span,
    div[data-testid="stMarkdownContainer"]:not(button *):not(.bento-card-value) > li {
        color: #0f172a;
    }
    div[data-testid="stCaptionContainer"],
    div[data-testid="stCaptionContainer"] p,
    div[data-testid="stCaptionContainer"] span {
        color: #475569 !important;
        -webkit-text-fill-color: #475569 !important;
    }

    /* Tabele stDataFrame w jasnym trybie - zachowanie pełnych kolorów wskaźników KDI oraz TAK/NIE */
    div[data-testid="stDataFrame"] canvas[data-testid="data-grid-canvas"],
    div[data-testid="stDataFrame"] canvas {
        filter: invert(0.92) hue-rotate(180deg) contrast(1.05) !important;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #cbd5e1 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
    }

    .login-header-card {
        text-align: center;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 4px 25px rgba(0, 0, 0, 0.06) !important;
    }
    .login-header-card h2 {
        color: #0f172a !important;
    }
    hr {
        border-color: #e2e8f0 !important;
    }

    /* Gwarancja czytelności tekstu przycisków w jasnym motywie */
    .stButton button,
    .stButton button *,
    div[data-testid="stFormSubmitButton"] button,
    div[data-testid="stFormSubmitButton"] button *,
    div[data-testid="stDownloadButton"] button,
    div[data-testid="stDownloadButton"] button * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
</style>
"""

def pobierz_motyw_css(motyw="fiolet") -> str:
    if isinstance(motyw, bool):
        motyw = "dark_mono" if motyw else "fiolet"
    if motyw == "light_mono":
        return LIGHT_MONO_THEME_CSS
    elif motyw == "dark_mono":
        return MONO_THEME_CSS
    return DARK_THEME_CSS