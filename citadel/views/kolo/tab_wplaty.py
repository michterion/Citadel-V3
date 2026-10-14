import uuid
from datetime import date, timedelta
import pandas as pd
import streamlit as st
import psycopg
from psycopg import errors

from config import dzis_pl, teraz_utc, parse_date
from database import db_query, db_execute, db_scalar
from rbac import moze

def render_tab_wplaty(dane_przeliczone, wybrane_kolo_id, rola_uzytkownika, curr_user_id):
    st.markdown("<div style='max-width: 650px;'>", unsafe_allow_html=True)
    if not dane_przeliczone:
        st.warning("Najpierw wprowadź członków do bazy tego koła.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    opcje_w = {d["id"]: f"{d['imie_nazwisko']} (Saldo: {d['saldo_akt_pln']:.2f} zł)" for d in dane_przeliczone}
    
    if moze(rola_uzytkownika, "bezposrednie_ksiegowanie"):
        tryb_operacji = st.radio(
            "Czynność:",
            ["➕ Nowa wpłata (Księgowanie)", "📥 Zgłoś do kolejki (Test)", "✏️ Popraw / Usuń wpłatę"],
            horizontal=True
        )

        if tryb_operacji in ("➕ Nowa wpłata (Księgowanie)", "📥 Zgłoś do kolejki (Test)"):
            if "wplata_token" not in st.session_state:
                st.session_state["wplata_token"] = str(uuid.uuid4())
            with st.form("form_wplata_nowa_admin"):
                wybrany = st.selectbox("Członek", options=list(opcje_w.keys()), format_func=lambda x: opcje_w[x])
                kwota_pln = st.number_input("Kwota wpłaty (PLN)", min_value=0.01, value=9.0, step=1.0)
                data_w = st.date_input("Data wpływu", value=dzis_pl(), min_value=date(2015, 1, 1), max_value=dzis_pl())
                notatka = st.text_input("Tytuł / Notatka", value="Składka członkowska")
                
                osw_test = "MAM_POTWIERDZENIE"
                if tryb_operacji == "📥 Zgłoś do kolejki (Test)":
                    osw_test = st.selectbox("Oświadczenie testowe:", ["MAM_POTWIERDZENIE", "BRAK_POTWIERDZENIA"])

                wymus_duplikat = st.checkbox("Potwierdzam celowe dodanie kolejnej identycznej wpłaty (w ciągu 60s)")
                btn_txt = "Zaksięguj wpłatę bezpośrednio" if "Księgowanie" in tryb_operacji else "Wyślij do kolejki weryfikacji"
                
                if st.form_submit_button(btn_txt):
                    kwota_gr = int(round(kwota_pln * 100))
                    teraz = teraz_utc()
                    czl_kolo_id = db_scalar("SELECT kolo_id FROM czlonkowie WHERE id = %s", (wybrany,)) or wybrane_kolo_id

                    if tryb_operacji == "➕ Nowa wpłata (Księgowanie)":
                        granica_czasu = teraz - timedelta(seconds=60)
                        liczba_ostatnich = db_scalar("""
                            SELECT COUNT(*) FROM wplaty 
                            WHERE czlonek_id = %s AND kwota_gr = %s AND data_wpisu >= %s
                        """, (wybrany, kwota_gr, granica_czasu))
                        
                        if liczba_ostatnich and liczba_ostatnich > 0 and not wymus_duplikat:
                            st.error("⚠️ Identyczna wpłata w ciągu ostatnich 60s. Zaznacz checkbox, aby potwierdzić.")
                        else:
                            try:
                                db_execute("""
                                    INSERT INTO wplaty (kolo_id, czlonek_id, kwota_gr, data_wplaty, notatka, data_wpisu, idempotency_key)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (czl_kolo_id, wybrany, kwota_gr, data_w, notatka, teraz, st.session_state["wplata_token"]))
                                st.session_state["wplata_token"] = str(uuid.uuid4())
                                st.cache_data.clear()
                                st.success("Wpłata zarejestrowana bezpośrednio w księdze.")
                                st.rerun()
                            except (psycopg.IntegrityError, errors.UniqueViolation):
                                st.warning("Ta transakcja została już przetworzona w tle.")
                    else:
                        db_execute("""
                            INSERT INTO wplaty_oczekujace (kolo_id, czlonek_id, zglosil_uzytkownik_id, kwota_gr, data_wplaty, notatka, oswiadczenie, status, idempotency_key)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'OCZEKUJE', %s)
                        """, (czl_kolo_id, wybrany, curr_user_id, kwota_gr, data_w, notatka, osw_test, str(uuid.uuid4())))
                        st.cache_data.clear()
                        st.success("✅ Wpłata trafiła do kolejki weryfikacji.")
                        st.rerun()
        else:
            wplaty_lista = db_query("""
                SELECT w.id, w.czlonek_id, w.kwota_gr, w.data_wplaty, w.notatka, c.imie_nazwisko 
                FROM wplaty w LEFT JOIN czlonkowie c ON w.czlonek_id = c.id 
                WHERE w.kolo_id = %s ORDER BY w.id DESC
            """, (wybrane_kolo_id,))
            if wplaty_lista.empty:
                st.info("Brak wpłat do modyfikacji w tym kole.")
            else:
                opcje_edycji = {
                    row["id"]: f"ID #{row['id']} | {row['data_wplaty']} | {row['imie_nazwisko'] or 'Były członek'} | {row['kwota_gr']/100:.2f} zł ({row['notatka']})"
                    for _, row in wplaty_lista.iterrows()
                }
                wybrane_id = st.selectbox("Wybierz wpłatę:", options=list(opcje_edycji.keys()), format_func=lambda x: opcje_edycji[x])
                wpis = wplaty_lista[wplaty_lista["id"] == wybrane_id].iloc[0]
                with st.form("form_wplata_edycja"):
                    mapa_czl = {d["id"]: d["imie_nazwisko"] for d in dane_przeliczone}
                    domyslny_idx = list(mapa_czl.keys()).index(int(wpis["czlonek_id"])) if pd.notna(wpis["czlonek_id"]) and int(wpis["czlonek_id"]) in mapa_czl else 0
                    nowy_c_id = st.selectbox("Osoba", options=list(mapa_czl.keys()), index=domyslny_idx, format_func=lambda x: mapa_czl[x])
                    nowa_kwota_pln = st.number_input("Kwota (PLN)", min_value=0.01, value=float(wpis["kwota_gr"] / 100.0), step=1.0)
                    nowa_data_w = st.date_input("Data wpłaty", value=parse_date(wpis["data_wplaty"]), min_value=date(2015, 1, 1), max_value=dzis_pl())
                    nowa_notatka = st.text_input("Notatka", value=str(wpis["notatka"]))
                    usun_checkbox = st.checkbox("🔥 Całkowicie usuń tę wpłatę z rejestru")
                    if st.form_submit_button("Zastosuj operację"):
                        if usun_checkbox:
                            db_execute("DELETE FROM wplaty WHERE id = %s", (wybrane_id,))
                            st.cache_data.clear()
                            st.success("Wpłata usunięta.")
                        else:
                            db_execute("""
                                UPDATE wplaty 
                                SET czlonek_id = %s, kwota_gr = %s, data_wplaty = %s, notatka = %s 
                                WHERE id = %s
                            """, (nowy_c_id, int(round(nowa_kwota_pln * 100)), nowa_data_w, nowa_notatka, wybrane_id))
                            st.cache_data.clear()
                            st.success("Wpłata zaktualizowana.")
                        st.rerun()

    else:
        st.markdown("#### 📥 Zadeklaruj Wpłatę Członka")
        st.info("ℹ️ Jako Skarbnik Koła/Regionu deklarujesz wpłatę. Zostanie zaksięgowana w kasie po zatwierdzeniu przez Skarbnika Krajowego lub Administratora.")
        
        if "deklaracja_token" not in st.session_state:
            st.session_state["deklaracja_token"] = str(uuid.uuid4())

        with st.form("form_deklaracja_wplaty", clear_on_submit=False):
            wybrany_czl = st.selectbox("Wybierz członka", options=list(opcje_w.keys()), format_func=lambda x: opcje_w[x])
            deklarowana_kwota_pln = st.number_input("Kwota deklarowanej wpłaty (PLN)", min_value=0.01, value=9.0, step=1.0)
            deklarowana_data = st.date_input("Data wpływu na konto", value=dzis_pl(), min_value=date(2015, 1, 1), max_value=dzis_pl())
            deklarowana_notatka = st.text_input("Tytuł przelewu / Notatka", value="Składka członkowska")
            
            st.markdown("**Wymagane oświadczenie weryfikacyjne:**")
            oswiadczenie_wybor = st.radio(
                "Status potwierdzenia przelewu:",
                [
                    "📄 Dysponuję potwierdzeniem przelewu i jestem świadomy że mogę zostać o nie poproszony przez Skarbnika Krajowego lub Administratora",
                    "⚠️ Nie dysponuję potwierdzeniem Skarbnik krajowy lub administrator musi potwierdzić dane"
                ]
            )
            
            if st.form_submit_button("Wyślij wpłatę do zaakceptowania"):
                kod_oswiadczenia = "MAM_POTWIERDZENIE" if "Dysponuję" in oswiadczenie_wybor else "BRAK_POTWIERDZENIA"
                kwota_gr_deklarowana = int(round(deklarowana_kwota_pln * 100))
                czl_kolo_id = db_scalar("SELECT kolo_id FROM czlonkowie WHERE id = %s", (wybrany_czl,)) or wybrane_kolo_id
                
                try:
                    db_execute("""
                        INSERT INTO wplaty_oczekujace (
                            kolo_id, czlonek_id, zglosil_uzytkownik_id, kwota_gr, 
                            data_wplaty, notatka, oswiadczenie, status, idempotency_key
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'OCZEKUJE', %s)
                    """, (czl_kolo_id, wybrany_czl, curr_user_id, kwota_gr_deklarowana, 
                          deklarowana_data, deklarowana_notatka, kod_oswiadczenia, st.session_state["deklaracja_token"]))
                    
                    st.session_state["deklaracja_token"] = str(uuid.uuid4())
                    st.cache_data.clear()
                    st.success("✅ Wpłata została zgłoszona do kolejki akceptacji!")
                    st.rerun()
                except (psycopg.IntegrityError, errors.UniqueViolation):
                    st.warning("Ta wpłata została już wysłana.")

        st.markdown("---")
        st.markdown("#### ⏳ Ostatnie wpłaty zgłoszone w tym kole")
        ostatnie_deklaracje_df = db_query("""
            SELECT wo.id as "ID", wo.data_wplaty as "Data Przelewu", c.imie_nazwisko as "Członek", 
                   (wo.kwota_gr / 100.0) as "Kwota (PLN)", wo.status as "Status", wo.oswiadczenie as "Oświadczenie"
            FROM wplaty_oczekujace wo
            JOIN czlonkowie c ON wo.czlonek_id = c.id
            WHERE wo.kolo_id = %s
            ORDER BY wo.id DESC LIMIT 15
        """, (wybrane_kolo_id,))
        if not ostatnie_deklaracje_df.empty:
            st.dataframe(ostatnie_deklaracje_df, width="stretch", hide_index=True)
        else:
            st.caption("Brak zgłoszonych oczekujących wpłat.")
    st.markdown("</div>", unsafe_allow_html=True)
