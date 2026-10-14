import os
import streamlit as st
from config import formatuj_czas_pl
from database import db_query, generuj_zrzut_bazy_sql

def render_tab_audyt(wybrane_kolo_id):
    subtab_audyt_db, subtab_audyt_wplaty, subtab_backup = st.tabs([
        "🛡️ Dziennik Audytu Zdarzeń (Trigger PG)", 
        "💰 Rejestr Wpłat",
        "💾 Kopia Zapasowa (.sql)"
    ])
    with subtab_audyt_db:
        st.markdown("#### 🛡️ Rejestr Zmian Systemowych (PostgreSQL Audit Trigger)")
        tabela_filtr = st.selectbox("Filtruj tabelę:", ["Wszystkie", "czlonkowie", "wplaty", "wplaty_oczekujace", "naliczenia_reczne", "korekty", "wydatki", "korekty_kasy", "kola", "regiony", "uzytkownicy"])
        if tabela_filtr == "Wszystkie":
            logi_db = db_query("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100")
        else:
            logi_db = db_query("SELECT * FROM audit_log WHERE tabela = %s ORDER BY id DESC LIMIT 100", (tabela_filtr,))
        
        if logi_db.empty:
            st.info("Brak zarejestrowanych wpisów w dzienniku audytu.")
        else:
            logi_db["Czas (PL)"] = logi_db["zmieniono_o"].apply(formatuj_czas_pl)
            st.dataframe(logi_db[["id", "Czas (PL)", "tabela", "operacja", "rekord_id", "stare_dane", "nowe_dane"]], width="stretch", hide_index=True)

    with subtab_audyt_wplaty:
        logi_w = db_query("""
            SELECT w.id as "ID", w.data_wpisu, w.data_wplaty as "Data Wpływu", 
                   COALESCE(c.imie_nazwisko, 'Były członek') as "Członek", 
                   (w.kwota_gr / 100.0) as "Kwota (PLN)", w.notatka as "Uwagi"
            FROM wplaty w 
            LEFT JOIN czlonkowie c ON w.czlonek_id = c.id 
            WHERE w.kolo_id = %s ORDER BY w.id DESC
        """, (wybrane_kolo_id,))
        if not logi_w.empty:
            logi_w["Zarejestrowano (PL)"] = logi_w["data_wpisu"].apply(formatuj_czas_pl)
            st.dataframe(logi_w[["ID", "Zarejestrowano (PL)", "Data Wpływu", "Członek", "Kwota (PLN)", "Uwagi"]], width="stretch", hide_index=True)
        else:
            st.info("Brak wpłat w historii tego koła.")

    with subtab_backup:
        st.markdown("#### 💾 Pełna Kopia Zapasowa Bazy Danych (.sql)")
        if st.button("🚀 Wygeneruj zrzut bazy (.sql)", key="btn_generate_sql_backup"):
            with st.spinner("Generowanie zrzutu..."):
                f_path, f_name, f_size_kb, silnik = generuj_zrzut_bazy_sql()
                st.session_state["backup_filepath"] = f_path
                st.session_state["backup_filename"] = f_name
                st.success(f"✅ Zrzut gotowy! Rozmiar: {f_size_kb:.1f} KB")

        if "backup_filepath" in st.session_state and os.path.exists(st.session_state["backup_filepath"]):
            with open(st.session_state["backup_filepath"], "rb") as f_dl:
                st.download_button("📥 Pobierz plik bazy (.sql)", data=f_dl.read(), file_name=st.session_state["backup_filename"], mime="application/sql")
