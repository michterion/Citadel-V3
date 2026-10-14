import streamlit as st
import psycopg
from psycopg import errors

from config import formatuj_czas_pl
from database import (
    db_query, db_execute, db_scalar, pobierz_slownik_regionow,
    przenies_kolo_do_kosza, przywroc_kolo_z_kosza, usun_kolo_trwale,
    przenies_region_do_kosza, przywroc_region_z_kosza, usun_region_trwale
)
from rbac import moze

def render_tab_struktura(wybrany_kraj_id, wybrany_region_id, rola_uzytkownika):
    st.markdown("### 🏛️ Zarządzanie Architekturą Organizacji")
    st.caption("Pełne zarządzanie strukturą: tworzenie, edycja nazw i przypisań, archiwizacja (kosz) oraz trwałe usuwanie.")

    sub_reg, sub_kolo, sub_kosz = st.tabs(["🌍 Regiony", "🏢 Koła", "♻️ Kosz i Przywracanie"])

    # === ZAKŁADKA 1: REGIONY ===
    with sub_reg:
        col_r1, col_r2 = st.columns(2)
        
        with col_r1:
            st.markdown("#### ➕ Nowy Region")
            with st.form("form_nowy_region", clear_on_submit=True):
                nowy_reg_nazwa = st.text_input("Nazwa nowego regionu:")
                if st.form_submit_button("➕ Utwórz Region", use_container_width=True):
                    if not nowy_reg_nazwa.strip():
                        st.error("Nazwa regionu nie może być pusta.")
                    else:
                        try:
                            db_execute("INSERT INTO regiony (kraj_id, nazwa) VALUES (%s, %s)", (wybrany_kraj_id, nowy_reg_nazwa.strip()))
                            st.cache_data.clear()
                            st.success(f"Region '{nowy_reg_nazwa.strip()}' został utworzony.")
                            st.rerun()
                        except (psycopg.IntegrityError, errors.UniqueViolation):
                            st.error(f"Region o nazwie '{nowy_reg_nazwa.strip()}' już istnieje w tym kraju.")

        with col_r2:
            st.markdown("#### ✏️ Zmień Nazwę Regionu")
            aktywne_reg_df = db_query("SELECT id, nazwa FROM aktywne_regiony WHERE kraj_id = %s ORDER BY nazwa ASC", (wybrany_kraj_id,))
            if aktywne_reg_df.empty:
                st.caption("Brak aktywnych regionów do edycji.")
            else:
                mapa_reg_ed = dict(zip(aktywne_reg_df["id"], aktywne_reg_df["nazwa"]))
                domyslny_reg = wybrany_region_id if (wybrany_region_id and wybrany_region_id != -1 and wybrany_region_id in mapa_reg_ed) else list(mapa_reg_ed.keys())[0]
                sel_reg_ed_id = st.selectbox("Wybierz region do zmiany nazwy:", options=list(mapa_reg_ed.keys()), index=list(mapa_reg_ed.keys()).index(domyslny_reg), format_func=lambda x: mapa_reg_ed[x], key="sel_reg_ed")
                with st.form("form_edytuj_region"):
                    nowa_nazwa_reg = st.text_input("Nowa nazwa regionu:", value=mapa_reg_ed[sel_reg_ed_id])
                    if st.form_submit_button("💾 Zapisz nową nazwę", use_container_width=True):
                        if not nowa_nazwa_reg.strip():
                            st.error("Nazwa regionu nie może być pusta.")
                        else:
                            try:
                                db_execute("UPDATE regiony SET nazwa = %s WHERE id = %s", (nowa_nazwa_reg.strip(), sel_reg_ed_id))
                                st.cache_data.clear()
                                st.success("Nazwa regionu została zaktualizowana.")
                                st.rerun()
                            except (psycopg.IntegrityError, errors.UniqueViolation):
                                st.error("Region o takiej nazwie już istnieje.")

        st.markdown("---")
        st.markdown("#### 🗑️ Przenieś Region do Kosza")
        if aktywne_reg_df.empty:
            st.info("Brak aktywnych regionów.")
        else:
            c_del_r1, c_del_r2 = st.columns([1.2, 1])
            with c_del_r1:
                sel_reg_del_id = st.selectbox("Wybierz region do przeniesienia do kosza:", options=list(mapa_reg_ed.keys()), format_func=lambda x: mapa_reg_ed[x], key="sel_reg_del")
                liczba_kol_reg = db_scalar("SELECT COUNT(*) FROM aktywne_kola WHERE region_id = %s", (sel_reg_del_id,)) or 0
                st.warning(f"⚠️ **Uwaga:** Region '{mapa_reg_ed[sel_reg_del_id]}' posiada **{liczba_kol_reg}** aktywnych kół. Przeniesienie regionu do kosza spowoduje automatyczne ukrycie wszystkich jego kół.")
            with c_del_r2:
                st.markdown("<br>", unsafe_allow_html=True)
                potwierdz_del_r = st.checkbox(f"Potwierdzam przeniesienie do kosza regionu: {mapa_reg_ed[sel_reg_del_id]}", key="chk_del_reg")
                if st.button("🗑️ Przenieś region do kosza", use_container_width=True, key="btn_del_reg"):
                    if not potwierdz_del_r:
                        st.error("Zaznacz checkbox, aby potwierdzić operację.")
                    else:
                        przenies_region_do_kosza(sel_reg_del_id)
                        st.success(f"Region '{mapa_reg_ed[sel_reg_del_id]}' został przeniesiony do kosza.")
                        st.rerun()

    # === ZAKŁADKA 2: KOŁA ===
    with sub_kolo:
        aktywne_reg_df = db_query("SELECT id, nazwa FROM aktywne_regiony WHERE kraj_id = %s ORDER BY nazwa ASC", (wybrany_kraj_id,))
        mapa_reg_opcje = dict(zip(aktywne_reg_df["id"], aktywne_reg_df["nazwa"])) if not aktywne_reg_df.empty else {}
        lista_opcji_reg = [None] + list(mapa_reg_opcje.keys())

        def format_reg_choice(r_id):
            if r_id is None:
                return "⚠️ Bez przypisanego regionu"
            return mapa_reg_opcje.get(r_id, "Nieznany")

        col_k1, col_k2 = st.columns(2)
        with col_k1:
            st.markdown("#### ➕ Nowe Koło")
            with st.form("form_nowe_kolo", clear_on_submit=True):
                nowa_nazwa_k = st.text_input("Nazwa nowego koła:")
                domyslny_r_nowe = wybrany_region_id if (wybrany_region_id and wybrany_region_id != -1 and wybrany_region_id in mapa_reg_opcje) else None
                sel_reg_dla_nowego = st.selectbox(
                    "Przypisz do regionu:",
                    options=lista_opcji_reg,
                    index=lista_opcji_reg.index(domyslny_r_nowe) if domyslny_r_nowe in lista_opcji_reg else 0,
                    format_func=format_reg_choice
                )
                if st.form_submit_button("➕ Utwórz Koło", use_container_width=True):
                    if not nowa_nazwa_k.strip():
                        st.error("Nazwa koła jest wymagana.")
                    else:
                        try:
                            db_execute("""
                                INSERT INTO kola (nazwa, region_id, kraj_id) 
                                VALUES (%s, %s, %s)
                            """, (nowa_nazwa_k.strip(), sel_reg_dla_nowego, wybrany_kraj_id))
                            st.cache_data.clear()
                            st.success(f"Koło '{nowa_nazwa_k.strip()}' zostało utworzone.")
                            st.rerun()
                        except (psycopg.IntegrityError, errors.UniqueViolation):
                            st.error(f"Koło o nazwie '{nowa_nazwa_k.strip()}' już istnieje.")

        with col_k2:
            st.markdown("#### ✏️ Edytuj Koło (Nazwa i Region)")
            aktywne_kola_df = db_query("""
                SELECT k.id, k.nazwa, k.region_id, r.nazwa as region_nazwa
                FROM aktywne_kola k
                LEFT JOIN aktywne_regiony r ON k.region_id = r.id
                WHERE k.kraj_id = %s
                ORDER BY k.nazwa ASC
            """, (wybrany_kraj_id,))
            
            if aktywne_kola_df.empty:
                st.caption("Brak aktywnych kół w tym kraju.")
            else:
                mapa_kola_ed = {
                    r["id"]: f"{r['nazwa']} ({r['region_nazwa'] or 'Bez regionu'})"
                    for _, r in aktywne_kola_df.iterrows()
                }
                sel_kolo_ed_id = st.selectbox("Wybierz koło do edycji:", options=list(mapa_kola_ed.keys()), format_func=lambda x: mapa_kola_ed[x], key="sel_kolo_ed")
                wpis_kolo = aktywne_kola_df[aktywne_kola_df["id"] == sel_kolo_ed_id].iloc[0]

                with st.form("form_edytuj_kolo"):
                    edytowana_nazwa_k = st.text_input("Nazwa koła:", value=wpis_kolo["nazwa"])
                    akt_reg_kolo = wpis_kolo["region_id"] if pd.notna(wpis_kolo["region_id"]) and wpis_kolo["region_id"] in lista_opcji_reg else None
                    nowy_reg_kolo = st.selectbox(
                        "Region nadrzędny:",
                        options=lista_opcji_reg,
                        index=lista_opcji_reg.index(akt_reg_kolo),
                        format_func=format_reg_choice
                    )
                    if st.form_submit_button("💾 Zapisz zmiany w kole", use_container_width=True):
                        if not edytowana_nazwa_k.strip():
                            st.error("Nazwa koła nie może być pusta.")
                        else:
                            try:
                                db_execute("""
                                    UPDATE kola 
                                    SET nazwa = %s, region_id = %s 
                                    WHERE id = %s
                                """, (edytowana_nazwa_k.strip(), nowy_reg_kolo, sel_kolo_ed_id))
                                st.cache_data.clear()
                                st.success(f"Zaktualizowano koło '{edytowana_nazwa_k.strip()}'.")
                                st.rerun()
                            except (psycopg.IntegrityError, errors.UniqueViolation):
                                st.error("Koło o takiej nazwie już istnieje.")

        st.markdown("---")
        st.markdown("#### 🗑️ Przenieś Koło do Kosza")
        if aktywne_kola_df.empty:
            st.info("Brak kół do archiwizacji.")
        else:
            c_del_k1, c_del_k2 = st.columns([1.2, 1])
            with c_del_k1:
                sel_kolo_del_id = st.selectbox("Wybierz koło do przeniesienia do kosza:", options=list(mapa_kola_ed.keys()), format_func=lambda x: mapa_kola_ed[x], key="sel_kolo_del")
                wpis_kolo_del = aktywne_kola_df[aktywne_kola_df["id"] == sel_kolo_del_id].iloc[0]
                liczba_czl_kola = db_scalar("SELECT COUNT(*) FROM czlonkowie WHERE kolo_id = %s", (sel_kolo_del_id,)) or 0
                st.warning(f"⚠️ Koło '{wpis_kolo_del['nazwa']}' liczy **{liczba_czl_kola}** członków. Przeniesienie do kosza ukryje to koło z list wyboru i widoków publicznych.")
            with c_del_k2:
                st.markdown("<br>", unsafe_allow_html=True)
                potwierdz_del_k = st.checkbox(f"Potwierdzam przeniesienie do kosza: {wpis_kolo_del['nazwa']}", key="chk_del_kolo")
                if st.button("🗑️ Przenieś koło do kosza", use_container_width=True, key="btn_del_kolo"):
                    if not potwierdz_del_k:
                        st.error("Zaznacz checkbox, aby potwierdzić.")
                    else:
                        przenies_kolo_do_kosza(sel_kolo_del_id)
                        st.success(f"Koło '{wpis_kolo_del['nazwa']}' zostało przeniesione do kosza.")
                        st.rerun()

    # === ZAKŁADKA 3: KOSZ I PRZYWRACANIE ===
    with sub_kosz:
        st.markdown("#### ♻️ Elementy w Koszu (Archiwum)")
        st.caption("Elementy przeniesione do kosza są niewidoczne w systemie operacyjnym. Możesz je w każdej chwili przywrócić lub trwale usunąć.")

        tab_k_kola, tab_k_regiony = st.tabs(["🏢 Koła w Koszu", "🌍 Regiony w Koszu"])

        with tab_k_kola:
            kola_w_koszu_df = db_query("""
                SELECT k.id, k.nazwa, k.deleted_at, k.deleted_by_region_id,
                       r.nazwa as region_nazwa, r.is_deleted as region_w_koszu
                FROM kola k
                LEFT JOIN regiony r ON k.region_id = r.id
                WHERE k.is_deleted = TRUE AND k.kraj_id = %s
                ORDER BY k.deleted_at DESC NULLS LAST
            """, (wybrany_kraj_id,))

            if kola_w_koszu_df.empty:
                st.success("🎉 Kosz kół jest pusty.")
            else:
                for _, r_kolo in kola_w_koszu_df.iterrows():
                    kid = r_kolo["id"]
                    knazwa = r_kolo["nazwa"]
                    k_reg_nazwa = r_kolo["region_nazwa"] or "Bez regionu"
                    k_reg_del = bool(r_kolo["region_w_koszu"])
                    k_del_time = formatuj_czas_pl(r_kolo["deleted_at"])

                    st.markdown(f"**🏢 {knazwa}** | Region: **{k_reg_nazwa}** | Usunięto: `{k_del_time}`")
                    if k_reg_del:
                        st.warning(f"⚠️ Region nadrzędny ('{k_reg_nazwa}') znajduje się w koszu. Aby przywrócić to koło, musisz najpierw przywrócić jego region.")

                    c_act1, c_act2 = st.columns([1, 1.2])
                    with c_act1:
                        if st.button(f"🟢 Przywróć koło: {knazwa}", key=f"btn_res_k_{kid}"):
                            try:
                                przywroc_kolo_z_kosza(kid)
                                st.success(f"Koło '{knazwa}' zostało przywrócone.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))

                    with c_act2:
                        if moze(rola_uzytkownika, "zarzadza_koszem"):
                            with st.expander(f"🔥 Trwałe usunięcie ({knazwa})"):
                                st.error("⚠️ Ta operacja jest NIEODWRACALNA! Usunie wszystkie wpłaty, wydatki i historię członków tego koła.")
                                chk_perm_k = st.checkbox(f"Trwale usuń dane koła {knazwa}", key=f"chk_perm_k_{kid}")
                                if st.button(f"🔥 Usuń trwale z bazy #{kid}", key=f"btn_perm_k_{kid}"):
                                    if not chk_perm_k:
                                        st.error("Musisz zaznaczyć checkbox potwierdzający.")
                                    else:
                                        try:
                                            usun_kolo_trwale(kid)
                                            st.success(f"Koło '{knazwa}' zostało trwale usunięte z bazy.")
                                            st.rerun()
                                        except ValueError as e:
                                            st.error(str(e))
                    st.divider()

        with tab_k_regiony:
            regiony_w_koszu_df = db_query("""
                SELECT id, nazwa, deleted_at 
                FROM regiony 
                WHERE is_deleted = TRUE AND kraj_id = %s 
                ORDER BY deleted_at DESC NULLS LAST
            """, (wybrany_kraj_id,))

            if regiony_w_koszu_df.empty:
                st.success("🎉 Kosz regionów jest pusty.")
            else:
                for _, r_reg in regiony_w_koszu_df.iterrows():
                    rid = r_reg["id"]
                    rnazwa = r_reg["nazwa"]
                    rdel_time = formatuj_czas_pl(r_reg["deleted_at"])
                    powiazane_kola_cnt = db_scalar("SELECT COUNT(*) FROM kola WHERE region_id = %s", (rid,)) or 0

                    st.markdown(f"**🌍 {rnazwa}** | Podległe koła w archiwum: **{powiazane_kola_cnt}** | Usunięto: `{rdel_time}`")

                    c_act_r1, c_act_r2 = st.columns([1, 1.2])
                    with c_act_r1:
                        if st.button(f"🟢 Przywróć region: {rnazwa}", key=f"btn_res_r_{rid}"):
                            try:
                                przywroc_region_z_kosza(rid)
                                st.success(f"Region '{rnazwa}' oraz jego koła zostały pomyślnie przywrócone.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))

                    with c_act_r2:
                        if moze(rola_uzytkownika, "zarzadza_koszem"):
                            with st.expander(f"🔥 Trwałe usunięcie ({rnazwa})"):
                                st.error(f"⚠️ Trwałe usunięcie regionu skasuje również {powiazane_kola_cnt} powiązanych kół i ich całą historię finansową!")
                                chk_perm_r = st.checkbox(f"Trwale usuń region {rnazwa}", key=f"chk_perm_r_{rid}")
                                if st.button(f"🔥 Usuń trwale z bazy #{rid}", key=f"btn_perm_r_{rid}"):
                                    if not chk_perm_r:
                                        st.error("Musisz zaznaczyć checkbox potwierdzający.")
                                    else:
                                        try:
                                            usun_region_trwale(rid)
                                            st.success(f"Region '{rnazwa}' został trwale usunięty z bazy.")
                                            st.rerun()
                                        except ValueError as e:
                                            st.error(str(e))
                    st.divider()
