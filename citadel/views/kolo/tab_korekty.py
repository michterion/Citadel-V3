from datetime import date
import streamlit as st

from config import dzis_pl, teraz_utc
from database import db_execute
from calculations import przelicz_finanse_dla_kola

def render_tab_korekty(dane_przeliczone, wybrane_kolo_id):
    st.markdown("<div style='max-width: 550px;'>", unsafe_allow_html=True)
    if not dane_przeliczone:
        st.warning("Brak członków w kole.")
    else:
        opcje_k = {d["id"]: f"{d['imie_nazwisko']} | Obecne saldo: {d['saldo_akt_pln']:.2f} zł" for d in dane_przeliczone}
        with st.form("form_korekta_czlonek", clear_on_submit=True):
            wybrany_k = st.selectbox("Wybierz członka:", options=list(opcje_k.keys()), format_func=lambda x: opcje_k[x])
            nowe_saldo_pln = st.number_input("Docelowe nowe saldo (PLN)", value=0.0, step=1.0)
            data_kor = st.date_input("Data korekty", value=dzis_pl(), min_value=date(2015, 1, 1), max_value=dzis_pl())
            powod = st.text_input("Powód korekty", value="Wyrównanie ze stanem papierowym")
            if st.form_submit_button("Zastosuj korektę członka"):
                nowe_saldo_gr = int(round(nowe_saldo_pln * 100))
                dane_wtedy, _, _, _, _, _, _ = przelicz_finanse_dla_kola(wybrane_kolo_id, data_kor)
                osoba_wtedy = next((x for x in dane_wtedy if x["id"] == wybrany_k), None)
                saldo_wtedy_gr = osoba_wtedy["saldo_akt_gr"] if osoba_wtedy else 0
                delta_gr = nowe_saldo_gr - saldo_wtedy_gr
                db_execute("""
                    INSERT INTO korekty (czlonek_id, delta_gr, docelowe_saldo_gr, data_korekty, powod, data_wpisu)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (wybrany_k, delta_gr, nowe_saldo_gr, data_kor, powod, teraz_utc()))
                st.cache_data.clear()
                st.success(f"Zaktualizowano saldo o deltę: {delta_gr/100:+.2f} zł.")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

