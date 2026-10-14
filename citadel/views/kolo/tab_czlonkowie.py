from datetime import date
import streamlit as st

from config import dzis_pl, parse_date
from database import db_execute, usun_czlonka_bezpiecznie
from calculations import waliduj_daty_czlonka
from rbac import moze

def render_tab_czlonkowie(dane_przeliczone, wybrane_kolo_id, rola_uzytkownika):
    st.markdown("<div style='max-width: 650px;'>", unsafe_allow_html=True)
    opcje_operacji_czlonka = ["➕ Dodaj nowego członka", "✏️ Edytuj profil członka"]
    if moze(rola_uzytkownika, "usuwa_czlonka"):
        opcje_operacji_czlonka.append("🗑️ Usuń członka z koła")
    tryb_czlonka = st.radio("Operacja:", opcje_operacji_czlonka, horizontal=True)

    if tryb_czlonka == "➕ Dodaj nowego członka":
        with st.form("form_dodaj_czlonka", clear_on_submit=True):
            nazwa = st.text_input("Imię i Nazwisko")
            c_u1, c_u2 = st.columns(2)
            with c_u1:
                ur = st.date_input("Data urodzenia", value=date(2004, 1, 1), min_value=date(1940, 1, 1), max_value=dzis_pl())
            with c_u2:
                wst = st.date_input("Data przystąpienia", value=dzis_pl(), min_value=date(2015, 1, 1), max_value=dzis_pl())
            c_u3, c_u4 = st.columns(2)
            with c_u3:
                s_start_pln = st.number_input("Saldo początkowe (PLN)", min_value=-10000.0, max_value=10000.0, value=0.0, step=1.0)
            with c_u4:
                param = st.selectbox("Próg składek", ["AUTO", "B", "M", "S"])
            if st.form_submit_button("Zapisz profil"):
                poprawne, err_msg = waliduj_daty_czlonka(ur, wst)
                if not poprawne:
                    st.error(f"⚠️ {err_msg}")
                elif not nazwa.strip():
                    st.error("Imię i nazwisko jest wymagane.")
                else:
                    db_execute("""
                        INSERT INTO czlonkowie (kolo_id, imie_nazwisko, data_urodzenia, data_przystapienia, saldo_startowe_gr, reczny_parametr)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (wybrane_kolo_id, nazwa.strip(), ur, wst, int(round(s_start_pln * 100)), param))
                    st.cache_data.clear()
                    st.success(f"Dodano członka: {nazwa}")
                    st.rerun()

    elif tryb_czlonka == "✏️ Edytuj profil członka" and dane_przeliczone:
        mapa_edycji = {d["id"]: f"{d['imie_nazwisko']} (Saldo: {d['saldo_akt_pln']:.2f} zł)" for d in dane_przeliczone}
        czlonek_edit_id = st.selectbox("Wybierz członka:", options=list(mapa_edycji.keys()), format_func=lambda x: mapa_edycji[x])
        osoba_edytowana = next(d for d in dane_przeliczone if d["id"] == czlonek_edit_id)
        with st.form("form_edytuj_czlonka"):
            nowe_imie = st.text_input("Imię i Nazwisko", value=osoba_edytowana["imie_nazwisko"])
            data_ur_val = parse_date(osoba_edytowana["data_ur"])
            data_wst_val = parse_date(osoba_edytowana["data_wst"])
            nowa_data_ur = st.date_input("Data urodzenia", value=data_ur_val, min_value=date(1940, 1, 1), max_value=dzis_pl())
            nowa_data_wst = st.date_input("Data przystąpienia", value=data_wst_val, min_value=date(2015, 1, 1), max_value=dzis_pl())
            nowe_s_start_pln = st.number_input("Saldo początkowe (PLN)", value=float(osoba_edytowana["saldo_start_gr"] / 100.0), step=1.0)
            nowy_param = st.selectbox("Próg składek", ["AUTO", "B", "M", "S"], index=["AUTO", "B", "M", "S"].index(osoba_edytowana["reczny_parametr"] if osoba_edytowana["reczny_parametr"] in ["AUTO", "B", "M", "S"] else "AUTO"))
            
            czy_zmieniono_krytyczne = (nowa_data_wst != data_wst_val) or (int(round(nowe_s_start_pln * 100)) != osoba_edytowana["saldo_start_gr"])
            potwierdzenie_krytyczne = not czy_zmieniono_krytyczne
            if czy_zmieniono_krytyczne:
                st.error("⚠️ Zmiana parametrów krytycznych przeliczy wstecznie KDI i naliczenia!")
                potwierdzenie_krytyczne = st.checkbox("Potwierdzam wsteczną modyfikację parametrów")

            if st.form_submit_button("Zapisz zmiany w profilu"):
                poprawne, err_msg = waliduj_daty_czlonka(nowa_data_ur, nowa_data_wst)
                if not poprawne:
                    st.error(f"⚠️ {err_msg}")
                elif not nowe_imie.strip():
                    st.error("Imię i nazwisko nie może być puste.")
                elif czy_zmieniono_krytyczne and not potwierdzenie_krytyczne:
                    st.error("Zaznacz checkbox potwierdzający modyfikację parametrów krytycznych!")
                else:
                    db_execute("""
                        UPDATE czlonkowie
                        SET imie_nazwisko = %s, data_urodzenia = %s, data_przystapienia = %s, saldo_startowe_gr = %s, reczny_parametr = %s
                        WHERE id = %s
                    """, (nowe_imie.strip(), nowa_data_ur, nowa_data_wst, int(round(nowe_s_start_pln * 100)), nowy_param, czlonek_edit_id))
                    st.cache_data.clear()
                    st.success("Zaktualizowano dane członka.")
                    st.rerun()

    elif tryb_czlonka == "🗑️ Usuń członka z koła" and dane_przeliczone:
        mapa_usun = {d["id"]: f"{d['imie_nazwisko']} (Saldo: {d['saldo_akt_pln']:.2f} zł)" for d in dane_przeliczone}
        czlonek_del_id = st.selectbox("Wybierz członka do usunięcia:", options=list(mapa_usun.keys()), format_func=lambda x: mapa_usun[x])
        osoba_kasowana = next(d for d in dane_przeliczone if d["id"] == czlonek_del_id)
        with st.form("form_usun_czlonka"):
            st.error(f"⚠️ Usunięcie {osoba_kasowana['imie_nazwisko']} pozostawi jego wpłaty zarchiwizowane w kasie koła.")
            potwierdzenie_del = st.checkbox(f"Potwierdzam usunięcie profilu: {osoba_kasowana['imie_nazwisko']}")
            if st.form_submit_button("🔥 Usuń trwale profil"):
                if potwierdzenie_del:
                    usun_czlonka_bezpiecznie(czlonek_del_id)
                    st.success("Profil usunięty.")
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

