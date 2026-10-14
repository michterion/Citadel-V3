import streamlit as st
from database import db_execute

def render_tab_struktura(wybrany_kraj_id, wybrany_region_id):
    st.markdown("### 🏛️ Zarządzanie Architekturą Organizacji")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown(f"#### 🌍 Regiony")
        with st.form("form_nowy_region", clear_on_submit=True):
            nowy_reg_nazwa = st.text_input("Nazwa nowego regionu")
            if st.form_submit_button("➕ Utwórz Region"):
                if nowy_reg_nazwa.strip():
                    db_execute("INSERT INTO regiony (kraj_id, nazwa) VALUES (%s, %s)", (wybrany_kraj_id, nowy_reg_nazwa.strip()))
                    st.cache_data.clear()
                    st.success("Region utworzony.")
                    st.rerun()
    with col_s2:
        st.markdown(f"#### 🏢 Koła")
        with st.form("form_nowe_kolo", clear_on_submit=True):
            nowa_nazwa_k = st.text_input("Nazwa nowego koła")
            if st.form_submit_button("➕ Utwórz Koło"):
                if nowa_nazwa_k.strip():
                    db_execute("INSERT INTO kola (nazwa, region_id, kraj_id) VALUES (%s, %s, %s)", (nowa_nazwa_k.strip(), wybrany_region_id if wybrany_region_id != -1 else None, wybrany_kraj_id))
                    st.cache_data.clear()
                    st.success("Koło utworzone.")
                    st.rerun()
