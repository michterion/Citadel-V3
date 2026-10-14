import pandas as pd
import streamlit as st
import psycopg
from psycopg import errors

from config import teraz_utc, formatuj_czas_pl
from database import db_query, db_execute, db_scalar, pobierz_slownik_regionow
from rbac import pobierz_etykiete_roli, generuj_sol, hashuj_haslo

def render_tab_centauri(curr_user_id, wybrany_kraj_id):
    st.markdown("### 🏛️ Panel Centauri — Zarządzanie Kontami i Uprawnieniami")
    st.caption("Centrum kontroli dostępu, zarządzanie sesjami w czasie rzeczywistym i nadzór nad kontami.")

    sub_cent1, sub_cent2 = st.tabs(["👥 Rejestr Użytkowników & Akcje", "➕ Nowe Konto"])

    with sub_cent1:
        uzytkownicy_df = db_query("""
            SELECT u.id, u.login, u.imie_nazwisko, u.rola, u.is_active, 
                   u.ostatnie_logowanie, u.ostatnia_aktywnosc, u.sesja_wersja,
                   r.nazwa as region_nazwa, k.nazwa as kolo_nazwa
            FROM uzytkownicy u
            LEFT JOIN regiony r ON u.region_id = r.id
            LEFT JOIN kola k ON u.kolo_id = k.id
            ORDER BY u.id ASC
        """)

        teraz_baza = teraz_utc()
        tabela_prezentacyjna = []

        for _, u_r in uzytkownicy_df.iterrows():
            ost_akt = u_r["ostatnia_aktywnosc"]
            if pd.notna(ost_akt):
                if ost_akt.tzinfo is None:
                    ost_akt = ost_akt.replace(tzinfo=teraz_baza.tzinfo)
                sekundy_od_akcji = (teraz_baza - ost_akt).total_seconds()
                jest_online = 0 <= sekundy_od_akcji <= 300
            else:
                jest_online = False

            stan_sesji = "🟢 Online" if jest_online else "⚪ Offline"
            status_konta = "🟢 AKTYWNY" if u_r["is_active"] else "🔴 ZABLOKOWANY"

            if u_r["rola"] == "SKARBNIK_KOLA":
                przypisanie_str = f"Koło: {u_r['kolo_nazwa'] or 'Brak'}"
            elif u_r["rola"] == "SKARBNIK_REGIONU":
                przypisanie_str = f"Region: {u_r['region_nazwa'] or 'Brak'}"
            else:
                przypisanie_str = "Centrala (Kraj)"

            tabela_prezentacyjna.append({
                "ID": u_r["id"],
                "Login": u_r["login"],
                "Imię i Nazwisko": u_r["imie_nazwisko"],
                "Rola": pobierz_etykiete_roli(u_r["rola"]),
                "Jednostka": przypisanie_str,
                "Status Konta": status_konta,
                "Sesja": stan_sesji,
                "Ostatnie logowanie": formatuj_czas_pl(u_r["ostatnie_logowanie"]),
                "Ostatnia aktywność": formatuj_czas_pl(u_r["ostatnia_aktywnosc"])
            })

        st.dataframe(pd.DataFrame(tabela_prezentacyjna), width="stretch", hide_index=True)

        st.markdown("---")
        col_akc1, col_akc2, col_akc3, col_akc4 = st.columns(4)

        # AKCJA 1: BLOKADA DOSTĘPU
        with col_akc1:
            st.markdown("#### 🔒 Blokada Dostępu")
            opcje_blokady = {
                u["id"]: f"{u['login']} ({'Aktywny' if u['is_active'] else 'ZABLOKOWANY'})"
                for _, u in uzytkownicy_df.iterrows() if u["id"] != curr_user_id
            }
            if opcje_blokady:
                sel_blokada = st.selectbox("Wybierz konto:", options=list(opcje_blokady.keys()), format_func=lambda x: opcje_blokady[x], key="sel_blokada")
                target_u = uzytkownicy_df[uzytkownicy_df["id"] == sel_blokada].iloc[0]
                
                btn_label = "🔴 Zablokuj dostęp" if target_u["is_active"] else "🟢 Odblokuj dostęp"
                if st.button(btn_label, key="btn_toggle_blokada", use_container_width=True):
                    nowy_stan = not target_u["is_active"]
                    db_execute("""
                        UPDATE uzytkownicy 
                        SET is_active = %s, sesja_wersja = sesja_wersja + 1, ostatnia_aktywnosc = NULL 
                        WHERE id = %s
                    """, (nowy_stan, sel_blokada))
                    st.success(f"Zaktualizowano status konta: {target_u['login']}.")
                    st.rerun()
            else:
                st.caption("Brak innych kont.")

        # AKCJA 2: ZMIANA ROLI
        with col_akc2:
            st.markdown("#### 🔄 Zmiana Roli")
            opcje_roli = {
                u["id"]: f"{u['login']} ({u['imie_nazwisko']})" 
                for _, u in uzytkownicy_df.iterrows() if u["id"] != curr_user_id
            }
            if opcje_roli:
                sel_przepnij = st.selectbox("Wybierz konto:", options=list(opcje_roli.keys()), format_func=lambda x: opcje_roli[x], key="sel_przepnij")
                nowa_rola = st.selectbox("Nowa rola:", ["SKARBNIK_KOLA", "SKARBNIK_REGIONU", "SKARBNIK_KRAJOWY", "ADMIN"], key="sel_nowa_rola")
                if st.button("Zastosuj nową rolę", use_container_width=True):
                    db_execute("""
                        UPDATE uzytkownicy 
                        SET rola = %s, sesja_wersja = sesja_wersja + 1 
                        WHERE id = %s
                    """, (nowa_rola, sel_przepnij))
                    st.success("Uprawnienia zostały zaktualizowane.")
                    st.rerun()
            else:
                st.caption("Brak innych kont.")

        # AKCJA 3: RESET HASŁA
        with col_akc3:
            st.markdown("#### 🔑 Reset Hasła")
            opcje_reset = {u["id"]: u["login"] for _, u in uzytkownicy_df.iterrows()}
            sel_reset = st.selectbox("Konto do resetu:", options=list(opcje_reset.keys()), format_func=lambda x: opcje_reset[x], key="sel_reset")
            haslo_val = st.text_input("Nowe hasło:", value="Citadel2026!", key="txt_pass_reset")
            if st.button("Ustaw i wymuś zmianę", use_container_width=True):
                if len(haslo_val) < 6:
                    st.error("Min. 6 znaków!")
                else:
                    r_sol = generuj_sol()
                    r_hash = hashuj_haslo(haslo_val, r_sol)
                    db_execute("""
                        UPDATE uzytkownicy 
                        SET haslo_hash = %s, salt = %s, wymus_zmiane_hasla = TRUE, sesja_wersja = sesja_wersja + 1, ostatnia_aktywnosc = NULL 
                        WHERE id = %s
                    """, (r_hash, r_sol, sel_reset))
                    st.success("Hasło zaktualizowane. Aktywna sesja wygasła.")
                    st.rerun()

        # AKCJA 4: USUWANIE UŻYTKOWNIKA
        with col_akc4:
            st.markdown("#### 🗑️ Usuń Konto")
            opcje_usun = {
                u["id"]: f"{u['login']} ({u['imie_nazwisko']})"
                for _, u in uzytkownicy_df.iterrows() if u["id"] != curr_user_id
            }
            if opcje_usun:
                sel_usun_id = st.selectbox("Konto do usunięcia:", options=list(opcje_usun.keys()), format_func=lambda x: opcje_usun[x], key="sel_usun_user")
                u_do_skasowania = uzytkownicy_df[uzytkownicy_df["id"] == sel_usun_id].iloc[0]
                
                with st.expander("⚠️ Potwierdzenie"):
                    potw_usun = st.checkbox(f"Usuń {u_do_skasowania['login']}", key=f"chk_del_u_{sel_usun_id}")
                    if st.button("🔥 Skasuj trwale", key=f"btn_del_u_{sel_usun_id}", use_container_width=True):
                        if potw_usun:
                            db_execute("DELETE FROM uzytkownicy WHERE id = %s", (sel_usun_id,))
                            st.success(f"Konto {u_do_skasowania['login']} zostało usunięte.")
                            st.rerun()
                        else:
                            st.warning("Potwierdź checkboxem.")
            else:
                st.caption("Brak innych użytkowników.")

    with sub_cent2:
        st.markdown("<div style='max-width: 600px;'>", unsafe_allow_html=True)
        st.markdown("#### 👤 Tworzenie Nowego Konta")
        nowy_login = st.text_input("Login (np. skarbnik_lodz)")
        nowe_imie_nazw = st.text_input("Imię i Nazwisko użytkownika")
        nowe_haslo_start = st.text_input("Hasło startowe", value="Citadel2026!")
        wybrana_rola = st.selectbox("Rola w organizacji:", ["SKARBNIK_KOLA", "SKARBNIK_REGIONU", "SKARBNIK_KRAJOWY", "ADMIN"])

        assigned_kolo = None
        assigned_reg = None

        if wybrana_rola == "SKARBNIK_KOLA":
            wszystkie_kola = db_query("SELECT id, nazwa FROM aktywne_kola ORDER BY nazwa ASC")
            if not wszystkie_kola.empty:
                mapa_all_k = dict(zip(wszystkie_kola["id"], wszystkie_kola["nazwa"]))
                assigned_kolo = st.selectbox("Przypisz Koło:", options=list(mapa_all_k.keys()), format_func=lambda x: mapa_all_k[x])
        elif wybrana_rola == "SKARBNIK_REGIONU":
            wszystkie_reg = pobierz_slownik_regionow(wybrany_kraj_id)
            if not wszystkie_reg.empty:
                mapa_all_r = dict(zip(wszystkie_reg["id"], wszystkie_reg["nazwa"]))
                assigned_reg = st.selectbox("Przypisz Region:", options=list(mapa_all_r.keys()), format_func=lambda x: mapa_all_r[x])

        if st.button("➕ Utwórz konto w Citadel", use_container_width=True):
            if not nowy_login.strip() or not nowe_imie_nazw.strip():
                st.error("Wypełnij wymagane pola.")
            else:
                try:
                    s_sol = generuj_sol()
                    s_hash = hashuj_haslo(nowe_haslo_start, s_sol)
                    r_id = assigned_reg
                    k_id = assigned_kolo
                    if wybrana_rola == "SKARBNIK_KOLA" and assigned_kolo:
                        r_id = db_scalar("SELECT region_id FROM kola WHERE id = %s", (assigned_kolo,))

                    db_execute("""
                        INSERT INTO uzytkownicy (login, haslo_hash, salt, imie_nazwisko, rola, kraj_id, region_id, kolo_id, is_active, wymus_zmiane_hasla, sesja_wersja)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, TRUE, 1)
                    """, (nowy_login.strip(), s_hash, s_sol, nowe_imie_nazw.strip(), wybrana_rola, wybrany_kraj_id, r_id, k_id))
                    st.success(f"Utworzono konto: {nowy_login.strip()}!")
                    st.rerun()
                except (psycopg.IntegrityError, errors.UniqueViolation):
                    st.error("Użytkownik o takim loginie już istnieje.")
        st.markdown("</div>", unsafe_allow_html=True)
