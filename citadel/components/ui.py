import streamlit as st
from rbac import pobierz_etykiete_roli

import re

def _czysc_styl(styl: str) -> str:
    if not styl:
        return ""
    # Usuwamy !important oraz -webkit-text-fill-color, które powodują usunięcie stylu przez DOMPurify
    s = styl.replace("!important", "").replace("-webkit-text-fill-color", "")
    # Zamieniamy 8-znakowe hex (#RRGGBBAA) na standardowe 6-znakowe (#RRGGBB) akceptowane przez DOMPurify
    s = re.sub(r'#([0-9a-fA-F]{6})[0-9a-fA-F]{2}', r'#\1', s)
    czesci = [c.strip() for c in s.split(";") if c.strip() and ":" in c]
    return "; ".join(czesci)

def render_bento_card(tytul: str, wartosc: str, podtytul: str, klasa_akcentu: str = "", styl_custom: str = ""):
    clean_style = _czysc_styl(styl_custom)
    attr_style = f' style="{clean_style}"' if clean_style else ""
    
    if clean_style:
        wartosc_html = f'<span{attr_style}>{wartosc}</span>'
    else:
        wartosc_html = str(wartosc)

    st.markdown(f"""
        <div class="bento-card">
            <div class="bento-card-header">{tytul}</div>
            <div class="bento-card-value {klasa_akcentu}"{attr_style}>{wartosc_html}</div>
            <div class="bento-card-sub">{podtytul}</div>
        </div>
    """, unsafe_allow_html=True)

def render_user_pill(imie_nazwisko: str, rola: str):
    badge = pobierz_etykiete_roli(rola)
    st.markdown(f"<div style='font-size: 0.8rem; font-weight: 600; color: #94a3b8;'>{imie_nazwisko}</div>", unsafe_allow_html=True)
    st.markdown(f"<span class='user-pill'>{badge}</span>", unsafe_allow_html=True)