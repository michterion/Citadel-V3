from datetime import date
import streamlit as st

from config import dzis_pl, teraz_utc
from database import db_query, db_execute
from calculations import przelicz_finanse_dla_kola
from components.ui import render_bento_card

def render_tab_kasa(wybrane_kolo_id, nazwa_aktywnego_kola, suma_wplat_kola_gr, faktyczna_kasa_kola_gr, suma_wydatkow_gr, suma_korekt_kasy_gr):
    st.markdown(f"### 💳 Kasa i Płynność: {nazwa_aktywnego_kola}")
    
    kasa_kolor_netto = "accent-green" if faktyczna_kasa_kola_gr >= 0 else "accent-rose"
    col_k1, col_k2, col_k3 = st.columns(3)
    with col_k1:
        render_bento_card(
            "Suma Wpłaconych Pieniędzy",
            f"{(suma_wplat_kola_gr / 100.0):,.2f} PLN",
            "Wszystkie wpłaty na rachunek tego koła",
            "accent-cyan"
        )
    with col_k2:
        render_bento_card(
            "Suma Wydatków Koła",
            f"{(suma_wydatkow_gr / 100.0):,.2f} PLN",
            "Zarejestrowane koszty operacyjne",
            "accent-rose"
        )
    with col_k3:
        render_bento_card(
            "Pozostałe Środki (Kasa Netto)",
            f"{(faktyczna_kasa_kola_gr / 100.0):,.2f} PLN",
            f"Wpłaty - Wydatki + Korekty ({(suma_korekt_kasy_gr / 100.0):+,.2f} PLN)",
            kasa_kolor_netto
        )

    st.markdown("---")

    col_wyd, col_kor_kasa = st.columns(2)
    with col_wyd:
        st.markdown("#### 📤 Zarejestruj Wydatek")
        with st.form("form_dodaj_wydatek", clear_on_submit=True):
            kwota_wyd_pln = st.number_input("Kwota wydatku (PLN)", min_value=0.01, value=50.0, step=1.0)
            data_wyd = st.date_input("Data poniesienia kosztu", value=dzis_pl(), min_value=date(2015, 1, 1), max_value=dzis_pl())
            kat_wyd = st.selectbox("Kategoria", ["Integracja", "Materiały biurowe / Druki", "Wydarzenia / Prelekcje", "Sprzęt", "Inne"])
            opis_wyd = st.text_input("Opis wydatku / Nr faktury", value="")
            if st.form_submit_button("Zaksięguj wydatek"):
                db_execute("""
                    INSERT INTO wydatki (kolo_id, kwota_gr, data_wydatku, kategoria, opis, data_wpisu)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (wybrane_kolo_id, int(round(kwota_wyd_pln * 100)), data_wyd, kat_wyd, opis_wyd, teraz_utc()))
                st.cache_data.clear()
                st.success("Wydatek zaksięgowany.")
                st.rerun()

    with col_kor_kasa:
        st.markdown("#### 🛠️ Wyrównaj Stan Kasy z Wyciągiem")
        st.caption("Ustawia kwotę gotówki w kasie (wyrównanie ze stanem wyciągu bankowego na wskazaną datę).")
        with st.form("form_korekta_kasy", clear_on_submit=True):
            docelowy_stan_pln = st.number_input("Docelowy stan kasy (PLN)", value=float(faktyczna_kasa_kola_gr / 100.0), step=10.0)
            data_kor_kasa = st.date_input("Data wyciągu bankowego", value=dzis_pl(), min_value=date(2015, 1, 1), max_value=dzis_pl())
            powod_kasa = st.text_input("Powód korekty", value="Wyrównanie ze stanem wyciągu bankowego")
            if st.form_submit_button("Zastosuj korektę kasy"):
                docelowy_gr = int(round(docelowy_stan_pln * 100))
                _, _, kasa_wtedy_gr, _, _, _, _ = przelicz_finanse_dla_kola(wybrane_kolo_id, data_kor_kasa)
                delta_kasy_gr = docelowy_gr - kasa_wtedy_gr
                db_execute("""
                    INSERT INTO korekty_kasy (kolo_id, delta_gr, docelowy_stan_gr, data_korekty, powod, data_wpisu)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (wybrane_kolo_id, delta_kasy_gr, docelowy_gr, data_kor_kasa, powod_kasa, teraz_utc()))
                st.cache_data.clear()
                st.success(f"Stan kasy zaktualizowany na dzień {data_kor_kasa}.")
                st.rerun()

    st.markdown("---")
    col_hist_w, col_hist_k = st.columns(2)
    with col_hist_w:
        st.markdown("#### 📋 Ostatnie Wydatki Koła")
        wydatki_df = db_query("""
            SELECT id as "ID", data_wydatku as "Data", (kwota_gr / 100.0) as "Kwota (PLN)", kategoria as "Kategoria", opis as "Opis / Faktura"
            FROM wydatki WHERE kolo_id = %s ORDER BY id DESC
        """, (wybrane_kolo_id,))
        if not wydatki_df.empty:
            st.dataframe(wydatki_df, width="stretch", hide_index=True)
        else:
            st.caption("Brak zarejestrowanych wydatków.")

    with col_hist_k:
        st.markdown("#### ⚖️ Historia Ręcznych Korekt Kasy")
        korekty_kasy_df = db_query("""
            SELECT id as "ID", data_korekty as "Data", (delta_gr / 100.0) as "Delta (PLN)", (docelowy_stan_gr / 100.0) as "Nowy Stan (PLN)", powod as "Powód"
            FROM korekty_kasy WHERE kolo_id = %s ORDER BY id DESC
        """, (wybrane_kolo_id,))
        if not korekty_kasy_df.empty:
            st.dataframe(korekty_kasy_df, width="stretch", hide_index=True)
        else:
            st.caption("Brak ręcznych korekt stanu kasy.")
