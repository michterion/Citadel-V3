import streamlit as st
import pandas as pd
from config import DARK_THEME_CSS, dzis_pl, teraz_utc
from database import (
    init_db_once, db_query, db_execute, db_scalar,
    pobierz_slownik_krajow, pobierz_slownik_regionow, pobierz_liczbe_kol_bez_regionu
)
from rbac import weryfikuj_haslo, hashuj_haslo, generuj_sol, moze
from components.ui import render_user_pill
from views.view_kraj import render_view_kraj
from views.view_region import render_view_region
from views.view_kolo import render_view_kolo

pd.set_option('future.no_silent_downcasting', True)
st.set_page_config(page_title="Citadel for NG", layout="wide", initial_sidebar_state="collapsed")
st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

# Inicjalizacja schematu bazy danych i triggerów
init_db_once()

if "auth_user" not in st.session_state:
    st.session_state["auth_user"] = None

# BRAMKA LOGOWANIA
if st.session_state["auth_user"] is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, c_l2, _ = st.columns([1, 1.2, 1])
    with c_l2:
        st.markdown("""
            <div class="bento-card" style="text-align: center; border: 1px solid #4338ca;">
                <h2 style="font-weight: 800; margin-bottom: 4px;">CITADEL FOR NG</h2>
                <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 24px;">System Ewidencji Składek i Finansów</div>
            </div>
        """, unsafe_allow_html=True)
        with st.form("form_login"):
            log_login = st.text_input("Login")
            log_haslo = st.text_input("Hasło", type="password")
            if st.form_submit_button("Zaloguj do systemu", use_container_width=True):
                u_df = db_query("SELECT * FROM uzytkownicy WHERE login = %s", (log_login.strip(),))
                if u_df.empty:
                    st.error("Nieprawidłowy login lub hasło.")
                else:
                    u_row = u_df.iloc[0]
                    if not u_row["is_active"]:
                        st.error("Konto zostało zablokowane przez Administratora.")
                    elif weryfikuj_haslo(log_haslo, u_row["salt"], u_row["haslo_hash"]):
                        teraz = teraz_utc()
                        db_execute("""
                            UPDATE uzytkownicy 
                            SET ostatnie_logowanie = %s, ostatnia_aktywnosc = %s 
                            WHERE id = %s
                        """, (teraz, teraz, u_row["id"]))
                        st.session_state["auth_user"] = u_row.to_dict()
                        st.rerun()
                    else:
                        st.error("Nieprawidłowy login lub hasło.")
    st.stop()

# CIĄGŁA WERYFIKACJA SESJI I WERSJI SESJI
curr_user_id = st.session_state["auth_user"]["id"]
weryfikacja_df = db_query("""
    SELECT id, login, imie_nazwisko, rola, kraj_id, region_id, kolo_id, 
           is_active, wymus_zmiane_hasla, sesja_wersja 
    FROM uzytkownicy 
    WHERE id = %s
""", (curr_user_id,))

if (weryfikacja_df.empty or 
    not weryfikacja_df.iloc[0]["is_active"] or 
    weryfikacja_df.iloc[0]["sesja_wersja"] != st.session_state["auth_user"].get("sesja_wersja", 1)):
    st.session_state["auth_user"] = None
    st.warning("⚠️ Twoja sesja wygasła lub konto zostało zablokowane / zmodyfikowane. Zaloguj się ponownie.")
    st.rerun()

zalogowany_uzytkownik = weryfikacja_df.iloc[0].to_dict()
st.session_state["auth_user"] = zalogowany_uzytkownik

# Śledzenie aktywności (heartbeat online)
db_execute("UPDATE uzytkownicy SET ostatnia_aktywnosc = %s WHERE id = %s", (teraz_utc(), curr_user_id))

# WYMUSZENIE ZMIANY HASŁA STARTOWEGO
if zalogowany_uzytkownik["wymus_zmiane_hasla"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_zm, _ = st.columns([1, 1.2, 1])
    with col_zm:
        st.warning("⚠️ Twoje konto wymaga zmiany hasła przed uzyskaniem dostępu do panelu.")
        with st.form("form_wymus_haslo"):
            n_haslo1 = st.text_input("Nowe hasło (min. 8 znaków)", type="password")
            n_haslo2 = st.text_input("Powtórz hasło", type="password")
            if st.form_submit_button("Zapisz nowe hasło i przejdź do systemu"):
                if len(n_haslo1) < 8:
                    st.error("Hasło musi mieć co najmniej 8 znaków.")
                elif n_haslo1 != n_haslo2:
                    st.error("Wprowadzone hasła nie są identyczne.")
                else:
                    n_salt = generuj_sol()
                    n_hash = hashuj_haslo(n_haslo1, n_salt)
                    db_execute("""
                        UPDATE uzytkownicy 
                        SET haslo_hash = %s, salt = %s, wymus_zmiane_hasla = FALSE, sesja_wersja = sesja_wersja + 1 
                        WHERE id = %s
                    """, (n_hash, n_salt, curr_user_id))
                    st.session_state["auth_user"]["sesja_wersja"] += 1
                    st.session_state["auth_user"]["wymus_zmiane_hasla"] = False
                    st.success("Hasło zostało zaktualizowane!")
                    st.rerun()
    st.stop()

# GŁÓWNA NAWIGACJA HIERARCHICZNA
kraje_df = pobierz_slownik_krajow()
mapa_krajow = dict(zip(kraje_df["id"], kraje_df["nazwa"]))
rola_uzytkownika = zalogowany_uzytkownik["rola"]

col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([1.8, 0.8, 1.2, 1.4, 0.9])
with col_h1:
    st.markdown("<h1 style='font-size: 1.6rem; font-weight: 700; margin: 0;'>Citadel for NG</h1>", unsafe_allow_html=True)

with col_h2:
    if moze(rola_uzytkownika, "widzi_kraj"):
        wybrany_kraj_id = st.selectbox("Kraj", options=list(mapa_krajow.keys()), format_func=lambda x: mapa_krajow[x])
    else:
        wybrany_kraj_id = zalogowany_uzytkownik["kraj_id"] or list(mapa_krajow.keys())[0]
        st.selectbox("Kraj", options=[wybrany_kraj_id], format_func=lambda x: mapa_krajow.get(x, "Polska"), disabled=True)

regiony_df = pobierz_slownik_regionow(wybrany_kraj_id)
mapa_regionow = dict(zip(regiony_df["id"], regiony_df["nazwa"])) if not regiony_df.empty else {}
liczba_kol_bez_regionu = pobierz_liczbe_kol_bez_regionu(wybrany_kraj_id)

opcje_regionow = list(mapa_regionow.keys())
if liczba_kol_bez_regionu > 0 and moze(rola_uzytkownika, "widzi_kraj"):
    opcje_regionow.append(-1)

def formatuj_nazwe_regionu(reg_id):
    if reg_id == -1:
        return f"⚠️ Bez regionu ({liczba_kol_bez_regionu})"
    return mapa_regionow.get(reg_id, "Nieznany region")

with col_h3:
    if moze(rola_uzytkownika, "widzi_kraj"):
        if opcje_regionow:
            wybrany_region_id = st.selectbox("Aktywny Region:", options=opcje_regionow, format_func=formatuj_nazwe_regionu)
            nazwa_wybranego_regionu = "Nieprzypisane do regionu" if wybrany_region_id == -1 else mapa_regionow[wybrany_region_id]
        else:
            wybrany_region_id = None
            nazwa_wybranego_regionu = "Brak aktywnych regionów"
            st.selectbox("Aktywny Region:", options=[0], format_func=lambda x: "Brak regionów w bazie")
    elif rola_uzytkownika == "SKARBNIK_REGIONU":
        wybrany_region_id = zalogowany_uzytkownik["region_id"]
        nazwa_wybranego_regionu = mapa_regionow.get(wybrany_region_id, "Twój Region")
        st.selectbox("Aktywny Region:", options=[wybrany_region_id] if wybrany_region_id else [0], format_func=lambda x: nazwa_wybranego_regionu, disabled=True)
    else:
        kolo_reg_id = db_scalar("SELECT region_id FROM kola WHERE id = %s", (zalogowany_uzytkownik["kolo_id"],))
        wybrany_region_id = kolo_reg_id
        nazwa_wybranego_regionu = mapa_regionow.get(wybrany_region_id, "Region Koła")
        st.selectbox("Region:", options=[wybrany_region_id or 0], format_func=lambda x: nazwa_wybranego_regionu, disabled=True)

with col_h4:
    if moze(rola_uzytkownika, "widzi_kraj"):
        tryb_widoku = st.radio("Poziom analityczny:", ["🏢 Koło", "📊 Statystyki Regionu", "🇵🇱 Statystyki Kraju"], horizontal=True)
    elif moze(rola_uzytkownika, "widzi_region"):
        tryb_widoku = st.radio("Poziom analityczny:", ["🏢 Koło", "📊 Statystyki Regionu"], horizontal=True)
    else:
        tryb_widoku = "🏢 Koło"
        st.caption("🔒 Dostęp do własnego Koła")

with col_h5:
    render_user_pill(zalogowany_uzytkownik["imie_nazwisko"], rola_uzytkownika)
    if st.button("Wyloguj", key="btn_logout", use_container_width=True):
        db_execute("UPDATE uzytkownicy SET ostatnia_aktywnosc = NULL WHERE id = %s", (curr_user_id,))
        st.session_state["auth_user"] = None
        st.rerun()

# Powiadomienie o oczekujących wpłatach
if moze(rola_uzytkownika, "akceptuje_wplaty"):
    cnt_oczek = db_scalar("SELECT COUNT(*) FROM wplaty_oczekujace WHERE status = 'OCZEKUJE';") or 0
    if cnt_oczek > 0:
        st.warning(f"🔔 **Kolejka Weryfikacji:** Wpłaty czekające na Twoją akceptację: **{cnt_oczek}**. Przejdź do widoku **🏢 Koło $\\rightarrow$ 📥 Wpłaty do zaakceptowania**.")

nazwa_kraju = mapa_krajow.get(wybrany_kraj_id, "Polska")
dzis = dzis_pl()

# ROUTING WIDOKÓW
if tryb_widoku == "🇵🇱 Statystyki Kraju":
    render_view_kraj(wybrany_kraj_id, mapa_krajow, mapa_regionow, dzis)
elif tryb_widoku == "📊 Statystyki Regionu":
    render_view_region(wybrany_kraj_id, wybrany_region_id, nazwa_wybranego_regionu, nazwa_kraju, dzis)
else:
    render_view_kolo(zalogowany_uzytkownik, wybrany_kraj_id, wybrany_region_id, nazwa_wybranego_regionu, dzis)