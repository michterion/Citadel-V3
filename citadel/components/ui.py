import streamlit as st
from rbac import pobierz_etykiete_roli

def render_bento_card(tytul: str, wartosc: str, podtytul: str, klasa_akcentu: str = "", styl_custom: str = ""):
    st.markdown(f"""
        <div class="bento-card">
            <div class="bento-card-header">{tytul}</div>
            <div class="bento-card-value {klasa_akcentu}" style="{styl_custom}">{wartosc}</div>
            <div class="bento-card-sub">{podtytul}</div>
        </div>
    """, unsafe_allow_html=True)

def render_user_pill(imie_nazwisko: str, rola: str):
    badge = pobierz_etykiete_roli(rola)
    st.markdown(f"<div style='font-size: 0.8rem; font-weight: 600; color: #94a3b8;'>{imie_nazwisko}</div>", unsafe_allow_html=True)
    st.markdown(f"<span class='user-pill'>{badge}</span>", unsafe_allow_html=True)