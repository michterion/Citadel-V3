from datetime import date
import streamlit as st

from config import dzis_pl, teraz_utc
from database import db_query, db_execute

def render_tab_reczne(dane_przeliczone, wybrane_kolo_id):
    st.markdown("<div style='max-width: 650px;'>", unsafe_allow_html=True)
    tryb_nal = st.radio("Czynność:", ["➕ Nowe naliczenie", "📋 Przeglądaj / Usuń naliczenie"], horizontal=True)
    if not dane_przeliczone:
        st.warning("Najpierw wprowadź członków do bazy tego koła.")
    else:
        if tryb_nal == "➕ Nowe naliczenie":
            opcje_nal = {d["id"]: f"{d['imie_nazwisko']} (Saldo: {d['saldo_akt_pln']:.2f} zł)" for d in dane_przeliczone}
            with st.form("form_nowe_naliczenie", clear_on_submit=True):
                wybrany_nal = st.selectbox("Członek", options=list(opcje_nal.keys()), format_func=lambda x: opcje_nal[x])
                kwota_nal_pln = st.number_input("Kwota naliczenia (PLN)", min_value=0.01, value=9.0, step=1.0)
                data_nal = st.date_input("Data naliczenia", value=dzis_pl(), min_value=date(2015, 1, 1), max_value=dzis_pl())
                tytul_nal = st.text_input("Tytuł obciążenia", value="Składka statutowa")
                if st.form_submit_button("Zaksięguj naliczenie"):
                    if tytul_nal.strip():
                        db_execute("""
                            INSERT INTO naliczenia_reczne (czlonek_id, kwota_gr, data_naliczenia, tytul, data_wpisu)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (wybrany_nal, int(round(kwota_nal_pln * 100)), data_nal, tytul_nal.strip(), teraz_utc()))
                        st.cache_data.clear()
                        st.success("Zaksięgowano ręczne obciążenie.")
                        st.rerun()
        else:
            lista_recznych = db_query("""
                SELECT nr.id, nr.czlonek_id, nr.kwota_gr, nr.data_naliczenia, nr.tytul, c.imie_nazwisko 
                FROM naliczenia_reczne nr JOIN czlonkowie c ON nr.czlonek_id = c.id 
                WHERE c.kolo_id = %s ORDER BY nr.id DESC
            """, (wybrane_kolo_id,))
            if lista_recznych.empty:
                st.info("Brak ręcznych naliczeń.")
            else:
                opcje_usun_nal = {
                    row["id"]: f"ID #{row['id']} | {row['data_naliczenia']} | {row['imie_nazwisko']} | {row['kwota_gr']/100:.2f} zł ({row['tytul']})"
                    for _, row in lista_recznych.iterrows()
                }
                wybrane_nal_id = st.selectbox("Wpis do usunięcia:", options=list(opcje_usun_nal.keys()), format_func=lambda x: opcje_usun_nal[x])
                if st.button("🔥 Usuń to naliczenie z konta"):
                    db_execute("DELETE FROM naliczenia_reczne WHERE id = %s", (wybrane_nal_id,))
                    st.cache_data.clear()
                    st.success("Naliczenie usunięte.")
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
