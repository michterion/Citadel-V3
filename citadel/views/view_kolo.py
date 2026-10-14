import os
import uuid
import calendar
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import psycopg
from psycopg import errors

from config import (
    DATA_ODCIECIA, dzis_pl, teraz_utc, formatuj_czas_pl, parse_date,
    pobierz_kolor_kdi, pobierz_kolor_uprawnionych
)
from database import (
    db_query, db_execute, db_scalar, pool,
    usun_czlonka_bezpiecznie, przenies_kolo_do_kosza, przywroc_kolo_z_kosza,
    przenies_region_do_kosza, przywroc_region_z_kosza, usun_kolo_trwale,
    usun_region_trwale, generuj_zrzut_bazy_sql, pobierz_slownik_regionow
)
from rbac import moze, pobierz_etykiete_roli, generuj_sol, hashuj_haslo
from calculations import (
    przelicz_finanse_dla_kola, pobierz_parametr, oblicz_naliczenia_gr,
    oblicz_symulacje_kalkulatora, waliduj_daty_czlonka, filtruj_interwal,
    pobierz_stawke_za_miesiac
)
from components.ui import render_bento_card
from components.charts import render_wykres_salda, render_wykres_kdi

def render_view_kolo(zalogowany_uzytkownik, wybrany_kraj_id, wybrany_region_id, nazwa_wybranego_regionu, dzis):
    rola_uzytkownika = zalogowany_uzytkownik["rola"]
    curr_user_id = zalogowany_uzytkownik["id"]
    badge_rola = pobierz_etykiete_roli(rola_uzytkownika)

    if rola_uzytkownika == "SKARBNIK_KOLA":
        kola_df = db_query("SELECT id, nazwa, region_id FROM aktywne_kola WHERE id = %s", (zalogowany_uzytkownik["kolo_id"],))
    elif rola_uzytkownika == "SKARBNIK_REGIONU":
        kola_df = db_query("""
            SELECT k.id, k.nazwa, k.region_id, r.nazwa as region_nazwa
            FROM aktywne_kola k
            LEFT JOIN aktywne_regiony r ON k.region_id = r.id
            WHERE k.region_id = %s
            ORDER BY k.nazwa ASC
        """, (zalogowany_uzytkownik["region_id"],))
    else:
        if wybrany_region_id == -1:
            kola_df = db_query("""
                SELECT id, nazwa, region_id, NULL as region_nazwa
                FROM aktywne_kola
                WHERE region_id IS NULL AND kraj_id = %s
                ORDER BY nazwa ASC
            """, (wybrany_kraj_id,))
        elif wybrany_region_id is not None:
            kola_df = db_query("""
                SELECT k.id, k.nazwa, k.region_id, r.nazwa as region_nazwa
                FROM aktywne_kola k
                JOIN aktywne_regiony r ON k.region_id = r.id
                WHERE k.region_id = %s
                ORDER BY k.nazwa ASC
            """, (wybrany_region_id,))
        else:
            kola_df = pd.DataFrame()

    if kola_df.empty:
        st.warning("Brak dostępnych aktywnych kół w tym widoku.")
        return

    mapa_kol = dict(zip(kola_df["id"], kola_df["nazwa"]))
    c_sel, _ = st.columns([2, 2])
    with c_sel:
        if rola_uzytkownika == "SKARBNIK_KOLA":
            wybrane_kolo_id = zalogowany_uzytkownik["kolo_id"]
            st.selectbox("Koło:", options=[wybrane_kolo_id], format_func=lambda x: mapa_kol.get(x, "Twoje Koło"), disabled=True)
        else:
            wybrane_kolo_id = st.selectbox(
                f"Wybierz Koło z regionu: {nazwa_wybranego_regionu}",
                options=list(mapa_kol.keys()),
                format_func=lambda x: mapa_kol[x]
            )

    nazwa_aktywnego_kola = mapa_kol[wybrane_kolo_id]
    st.caption(f"Aktywna jednostka: **{nazwa_aktywnego_kola}** | Rola: **{badge_rola}** | Czas: **Europe/Warsaw**")

    dane_przeliczone, suma_wplat_kola_gr, faktyczna_kasa_kola_gr, suma_wydatkow_gr, suma_korekt_kasy_gr, total_z_gr, total_s_gr = przelicz_finanse_dla_kola(wybrane_kolo_id, dzis)

    kdi_global_val = round(total_z_gr / total_s_gr, 2) if total_s_gr > 0 else None
    kdi_global_str = f"{kdi_global_val:.2f}" if kdi_global_val is not None else "Brak danych"
    kolor_kdi_global = pobierz_kolor_kdi(kdi_global_val)

    # Bento Cards KPI Koła (Główny pasek koła)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kasa_color = "accent-green" if faktyczna_kasa_kola_gr >= 0 else "accent-rose"
        render_bento_card("Faktyczna Kasa Koła", f"{(faktyczna_kasa_kola_gr / 100.0):,.2f} PLN", "Wpłaty - Wydatki + Korekty", kasa_color)
    with c2:
        render_bento_card("Suma Wpłaconych Składek", f"{(suma_wplat_kola_gr / 100.0):,.2f} PLN", "Wpłacone do kasy tego koła", "accent-cyan")
    with c3:
        render_bento_card(f"KDI Koła ({nazwa_aktywnego_kola})", kdi_global_str, "Rekomendowane: ≤ 1.20", styl_custom=f"color: {kolor_kdi_global}; text-shadow: 0 0 16px {kolor_kdi_global}55;")
    with c4:
        uprawnieni_count = sum(1 for d in dane_przeliczone if d["moze_glosowac"])
        lacznie_czlonkow = len(dane_przeliczone)
        pct_uprawnieni = (uprawnieni_count / lacznie_czlonkow * 100.0) if lacznie_czlonkow > 0 else 0.0
        kolor_uprawnieni = pobierz_kolor_uprawnionych(pct_uprawnieni if lacznie_czlonkow > 0 else None)
        render_bento_card("Uprawnieni do Głosowania", f"{uprawnieni_count} / {lacznie_czlonkow}", f"{pct_uprawnieni:.1f}% (karencja ≤ 6 msc)", styl_custom=f"color: {kolor_uprawnieni}; text-shadow: 0 0 16px {kolor_uprawnieni}55;")

    # Dynamiczne zakładki sterowane przez moze()
    zakladki_nazwy = ["📊 Tabela Zbiorcza", "📈 Profile & Wykresy", "💰 Wpłaty Członków"]
    if moze(rola_uzytkownika, "reczne_naliczenia"):
        zakladki_nazwy.append("📝 Ręczne Naliczenia")
    zakladki_nazwy.append("💳 Kasa Koła & Wydatki")
    if moze(rola_uzytkownika, "korekty_salda"):
        zakladki_nazwy.append("🛠️ Korekta Salda Osoby")
    zakladki_nazwy.append("👤 Zarządzaj Członkami")
    zakladki_nazwy.append("🧮 Kalkulator")

    if moze(rola_uzytkownika, "akceptuje_wplaty"):
        cnt_pending = db_scalar("SELECT COUNT(*) FROM wplaty_oczekujace WHERE status = 'OCZEKUJE';") or 0
        tag_pending = f" ({cnt_pending})" if cnt_pending > 0 else ""
        zakladki_nazwy.append(f"📥 Wpłaty do zaakceptowania{tag_pending}")

    if moze(rola_uzytkownika, "zarzadza_struktura"):
        zakladki_nazwy.append("🏛️ Zarządzaj Strukturą")
    if moze(rola_uzytkownika, "widzi_audyt"):
        zakladki_nazwy.append("📜 Logi Audytowe")
    if moze(rola_uzytkownika, "zarzadza_kontami"):
        zakladki_nazwy.append("🏛️ Panel Centauri")

    st_tabs = st.tabs(zakladki_nazwy)
    tab_map = dict(zip(zakladki_nazwy, st_tabs))

    # 1. TABELA ZBIORCZA
    with tab_map["📊 Tabela Zbiorcza"]:
        if not dane_przeliczone:
            st.info(f"Baza dla koła '{nazwa_aktywnego_kola}' jest pusta. Dodaj pierwszego członka.")
        else:
            df_wyswietl = pd.DataFrame([
                {
                    "ID": d["id"],
                    "Członek": d["imie_nazwisko"],
                    "Próg": f"Parametr {d['parametr']}",
                    "Saldo Start": f"{(d['saldo_start_gr'] / 100.0):.2f} zł",
                    "Korekty": f"{(d['korekty_gr'] / 100.0):.2f} zł",
                    "Naliczone": f"{(d['naliczone_gr'] / 100.0):.2f} zł ({d['msc']} msc" + (f" + {d['liczba_recznych']} ręczne)" if d['liczba_recznych'] > 0 else ")"),
                    "Wpłacone": f"{(d['wplaty_gr'] / 100.0):.2f} zł",
                    "Saldo Aktualne": f"{d['saldo_akt_pln']:.2f} zł",
                    "Wskaźnik KDI": d["kdi_str"],
                    "Możliwość głosowania": d["glosowanie_str"]
                }
                for d in dane_przeliczone
            ])

            def stylizuj_kdi_komorke(wartosc):
                kolor = pobierz_kolor_kdi(wartosc)
                if wartosc == "Brak danych":
                    return f"color: {kolor}; font-style: italic;"
                return f"color: {kolor}; font-weight: 700; text-shadow: 0 0 8px {kolor}40;"

            def stylizuj_glosowanie(wartosc):
                if wartosc == "TAK":
                    return "color: #10b981; font-weight: 800;"
                elif wartosc == "NIE":
                    return "color: #f43f5e; font-weight: 800;"
                return ""

            styler = df_wyswietl.style.map(stylizuj_kdi_komorke, subset=["Wskaźnik KDI"]).map(stylizuj_glosowanie, subset=["Możliwość głosowania"])
            st.dataframe(styler, width="stretch", hide_index=True)

    # 2. PROFIL I WYKRESY
    with tab_map["📈 Profile & Wykresy"]:
        if not dane_przeliczone:
            st.info("Brak danych do analizy.")
        else:
            mapa_osob = {d["id"]: f"{d['imie_nazwisko']} (Saldo: {d['saldo_akt_pln']:.2f} zł, KDI: {d['kdi_str']})" for d in dane_przeliczone}
            wybrany_id = st.selectbox("Wybierz członka do analizy wskaźników", options=list(mapa_osob.keys()), format_func=lambda x: mapa_osob[x])
            osoba = next(item for item in dane_przeliczone if item["id"] == wybrany_id)
            
            kolor_kdi_osoby = pobierz_kolor_kdi(osoba["kdi_val"])
            kolor_glos = "#10b981" if osoba["moze_glosowac"] else "#f43f5e"
            
            st.markdown(f"""
                <div style="background: #161228; border: 1px solid #282046; border-radius: 12px; padding: 12px 18px; margin-bottom: 18px; display: flex; gap: 24px; align-items: center; flex-wrap: wrap;">
                    <div><span style="color: #94a3b8; font-size: 0.85rem;">CZŁONEK:</span> <strong style="color: #ffffff; font-size: 1rem;">{osoba['imie_nazwisko']}</strong></div>
                    <div><span style="color: #94a3b8; font-size: 0.85rem;">AKTUALNY KDI:</span> <strong style="color: {kolor_kdi_osoby}; font-size: 1.15rem; text-shadow: 0 0 10px {kolor_kdi_osoby}66;">{osoba['kdi_str']}</strong></div>
                    <div><span style="color: #94a3b8; font-size: 0.85rem;">SALDO:</span> <strong style="color: {'#10b981' if osoba['saldo_akt_pln'] >= 0 else '#f43f5e'}; font-size: 1rem;">{osoba['saldo_akt_pln']:.2f} zł</strong></div>
                    <div><span style="color: #94a3b8; font-size: 0.85rem;">GŁOSOWANIE:</span> <strong style="color: {kolor_glos}; font-size: 1.05rem; font-weight: 800;">{osoba['glosowanie_str']}</strong></div>
                </div>
            """, unsafe_allow_html=True)

            hist_wplaty = db_query("SELECT id, kwota_gr, data_wplaty, notatka FROM wplaty WHERE czlonek_id = %s ORDER BY data_wplaty ASC", (wybrany_id,))
            hist_naliczenia_reczne = db_query("SELECT id, kwota_gr, data_naliczenia, tytul FROM naliczenia_reczne WHERE czlonek_id = %s ORDER BY data_naliczenia ASC", (wybrany_id,))
            hist_korekty = db_query("SELECT id, delta_gr, docelowe_saldo_gr, data_korekty, powod FROM korekty WHERE czlonek_id = %s ORDER BY data_korekty ASC", (wybrany_id,))

            data_wst_parsed = parse_date(osoba["data_wst"])
            data_ur_parsed = parse_date(osoba["data_ur"])
            reczny_param = osoba["reczny_parametr"]

            wplaty_map = {}
            for _, r in hist_wplaty.iterrows():
                d = parse_date(r["data_wplaty"])
                wplaty_map[d] = wplaty_map.get(d, 0) + int(r["kwota_gr"])

            reczne_nal_map = {}
            for _, r in hist_naliczenia_reczne.iterrows():
                d = parse_date(r["data_naliczenia"])
                reczne_nal_map[d] = reczne_nal_map.get(d, 0) + int(r["kwota_gr"])

            korekty_map = {}
            for _, r in hist_korekty.iterrows():
                d = parse_date(r["data_korekty"])
                korekty_map[d] = korekty_map.get(d, 0) + int(r["delta_gr"])

            start_date = max(data_wst_parsed, DATA_ODCIECIA)
            if start_date > dzis:
                start_date = dzis

            # Inicjalizacja sum skumulowanych przed start_date (dla zachowania spójności)
            running_wplaty_gr = sum(kw for d, kw in wplaty_map.items() if d < start_date)
            running_reczne_nal_gr = sum(kw for d, kw in reczne_nal_map.items() if d < start_date)
            running_kor_netto_gr = sum(kw for d, kw in korekty_map.items() if d < start_date)

            # Bazowe naliczenie automatyczne na start_date
            running_nal_auto_gr, _ = oblicz_naliczenia_gr(data_wst_parsed, data_ur_parsed, reczny_param, start_date)

            daily_records = []
            cur_date = start_date

            while cur_date <= dzis:
                if cur_date in wplaty_map:
                    running_wplaty_gr += wplaty_map[cur_date]
                if cur_date in reczne_nal_map:
                    running_reczne_nal_gr += reczne_nal_map[cur_date]
                if cur_date in korekty_map:
                    running_kor_netto_gr += korekty_map[cur_date]

                # Naliczenie statutowe wzrasta w ostatnim dniu miesiąca (inkrementalnie O(1) zamiast pętli wstecznej)
                if cur_date > start_date:
                    _, last_day = calendar.monthrange(cur_date.year, cur_date.month)
                    if cur_date.day == last_day:
                        kod_st, stawka_gr = pobierz_stawke_za_miesiac(
                            data_wst_parsed, data_ur_parsed, reczny_param, date(cur_date.year, cur_date.month, 1)
                        )
                        if kod_st != "ZWOLNIONY_WSTAPIENIE":
                            running_nal_auto_gr += stawka_gr

                nal_total_pt = running_nal_auto_gr + running_reczne_nal_gr
                saldo_pt_gr = osoba["saldo_start_gr"] + running_wplaty_gr + running_kor_netto_gr - nal_total_pt
                saldo_pt = saldo_pt_gr / 100.0

                s_pt = max(0, osoba["saldo_start_gr"]) + running_wplaty_gr
                z_pt = max(0, s_pt - saldo_pt_gr)
                kdi_pt = round(z_pt / s_pt, 2) if s_pt > 0 else None

                daily_records.append({
                    "date": cur_date,
                    "date_str": cur_date.strftime("%Y-%m-%d"),
                    "saldo": saldo_pt,
                    "kdi": kdi_pt
                })
                cur_date += timedelta(days=1)

            wybrany_interwal = st.radio("Interwał wykresu", ["D1", "T1", "M1", "Q1", "Q2", "Y1", "Cały okres"], horizontal=True)
            rekordy_do_wykresu = filtruj_interwal(daily_records, wybrany_interwal)
            punkty_x = [r["date_str"] for r in rekordy_do_wykresu]
            punkty_saldo = [r["saldo"] for r in rekordy_do_wykresu]
            punkty_kdi = [r["kdi"] for r in rekordy_do_wykresu]
                
            subtab_saldo, subtab_kdi = st.tabs(["📉 Oś Czasu Salda (PLN)", "🎯 Dynamika Wskaźnika KDI"])
            with subtab_saldo:
                st.plotly_chart(render_wykres_salda(punkty_x, punkty_saldo), width="stretch")
            with subtab_kdi:
                st.plotly_chart(render_wykres_kdi(punkty_x, punkty_kdi), width="stretch")

            col_w, col_r, col_k = st.columns(3)
            with col_w:
                st.markdown("**Historia Wpłat**")
                if not hist_wplaty.empty:
                    hw = hist_wplaty.copy()
                    hw["Kwota"] = (hw["kwota_gr"] / 100.0).map("{:.2f} zł".format)
                    st.dataframe(hw[["id", "data_wplaty", "Kwota", "notatka"]], width="stretch", hide_index=True)
                else:
                    st.caption("Brak wpłat.")
            with col_r:
                st.markdown("**Ręczne Naliczenia**")
                if not hist_naliczenia_reczne.empty:
                    hr = hist_naliczenia_reczne.copy()
                    hr["Kwota"] = (hr["kwota_gr"] / 100.0).map("{:.2f} zł".format)
                    st.dataframe(hr[["data_naliczenia", "Kwota", "tytul"]], width="stretch", hide_index=True)
                else:
                    st.caption("Brak ręcznych naliczeń.")
            with col_k:
                st.markdown("**Historia Korekt Salda**")
                if not hist_korekty.empty:
                    hk = hist_korekty.copy()
                    hk["Delta"] = (hk["delta_gr"] / 100.0).map("{:+.2f} zł".format)
                    hk["Docelowe"] = (hk["docelowe_saldo_gr"] / 100.0).map("{:.2f} zł".format)
                    st.dataframe(hk[["data_korekty", "Delta", "Docelowe", "powod"]], width="stretch", hide_index=True)
                else:
                    st.caption("Brak korekt.")

    # 3. ZARZĄDZANIE WPŁATAMI
    with tab_map["💰 Wpłaty Członków"]:
        st.markdown("<div style='max-width: 650px;'>", unsafe_allow_html=True)
        if not dane_przeliczone:
            st.warning("Najpierw wprowadź członków do bazy tego koła.")
        else:
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

    # 4. RĘCZNE NALICZENIA
    if "📝 Ręczne Naliczenia" in tab_map:
        with tab_map["📝 Ręczne Naliczenia"]:
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

    # 5. KASA KOŁA & WYDATKI
    with tab_map["💳 Kasa Koła & Wydatki"]:
        st.markdown(f"### 💳 Kasa i Płynność: {nazwa_aktywnego_kola}")
        
        # PRZYWRÓCONE KARTY BILANSU KASY KOŁA
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

    # 6. KOREKTA SALDA OSOBY
    if "🛠️ Korekta Salda Osoby" in tab_map:
        with tab_map["🛠️ Korekta Salda Osoby"]:
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

    # 7. ZARZĄDZANIE CZŁONKAMI
    with tab_map["👤 Zarządzaj Członkami"]:
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

    # 8. PODRĘCZNY KALKULATOR SKŁADEK I MANDATÓW
    with tab_map["🧮 Kalkulator"]:
        st.markdown("### 🧮 Podręczny Kalkulator Składek i Mandatów")
        st.caption("Symulator obsługujący dynamiczne zmiany progów wiekowych, Starą Uchwałę nr 1/2023 (do 31.12.2024), Nową Uchwałę (od 01.01.2025) oraz składki funkcyjne.")

        col_in, col_out = st.columns([1.1, 1.4], gap="large")

        with col_in:
            st.markdown("#### 📥 Parametry Członka")
            tryb_naliczania = st.radio(
                "Sposób ustalania stawki miesięcznej:",
                ["🎂 Automatycznie z daty urodzenia (Wiek)", "🏷️ Ręczny wybór progu (B / M / S)"],
                horizontal=True
            )

            c_k1, c_k2 = st.columns(2)
            if tryb_naliczania == "🎂 Automatycznie z daty urodzenia (Wiek)":
                with c_k1:
                    calc_data_ur = st.date_input("Data urodzenia", value=date(2005, 10, 10), min_value=date(1940, 1, 1), max_value=dzis_pl(), key="calc_ur")
                with c_k2:
                    calc_param_kod = "AUTO"
                    st.text_input("Wybrany próg", value="AUTO (wg wieku)", disabled=True)
            else:
                with c_k1:
                    calc_data_ur = date(2000, 1, 1)
                    st.text_input("Data urodzenia", value="Pominięto (tryb ręczny)", disabled=True)
                with c_k2:
                    wybrana_stawka = st.selectbox("Próg składek:", ["M (9.00 zł / msc)", "B (6.00 zł / msc)", "S (15.00 zł / msc)"], key="calc_param_sel")
                    calc_param_kod = wybrana_stawka[0]

            c_k3, c_k4 = st.columns(2)
            with c_k3:
                calc_data_wst = st.date_input("Data przystąpienia", value=date(2023, 9, 12), min_value=date(2015, 1, 1), max_value=dzis_pl(), key="calc_wst")
            with c_k4:
                calc_punkt_odniesienia = st.date_input("Kalkulacja na dzień:", value=dzis_pl(), min_value=date(2015, 1, 1), key="calc_punkt")

            opcja_startu = st.selectbox(
                "Naliczaj składki od:",
                [
                    "Od daty przystąpienia członka",
                    "Od początku 2025 r. (01.01.2025 - Nowa Uchwała)",
                    "Od początku 2026 r. (01.01.2026)",
                    "Od systemowej daty odcięcia (01.10.2026)",
                    "Własna data początkowa"
                ]
            )

            if opcja_startu == "Od daty przystąpienia członka":
                data_poczatku_naliczania = calc_data_wst
            elif opcja_startu == "Od początku 2025 r. (01.01.2025 - Nowa Uchwała)":
                data_poczatku_naliczania = max(calc_data_wst, date(2025, 1, 1))
            elif opcja_startu == "Od początku 2026 r. (01.01.2026)":
                data_poczatku_naliczania = max(calc_data_wst, date(2026, 1, 1))
            elif opcja_startu == "Od systemowej daty odcięcia (01.10.2026)":
                data_poczatku_naliczania = max(calc_data_wst, DATA_ODCIECIA)
            else:
                data_poczatku_naliczania = st.date_input("Własna data początkowa naliczania:", value=date(2025, 1, 1), min_value=date(2015, 1, 1))

            uwzglednij_biezacy = st.checkbox("Uwzględnij bieżący (niepełny) miesiąc w naliczeniu", value=False)

            st.markdown("---")
            st.markdown("#### 🏛️ Składka Funkcyjna (Uchwała nr 1/2023)")
            col_fn1, col_fn2 = st.columns(2)
            with col_fn1:
                opcja_funkcji = st.selectbox(
                    "Pełniona funkcja w organizacji:",
                    [
                        "Brak funkcji (0 zł)",
                        "Członek Zarządu Krajowego (+20 zł / msc)",
                        "Przewodniczący Regionu / Koła / Rada Krajowa / KKRD (+10 zł / msc)",
                        "Inna kwota funkcyjna (własna)"
                    ]
                )
                if opcja_funkcji == "Członek Zarządu Krajowego (+20 zł / msc)":
                    stawka_fn_pln = 20.0
                elif opcja_funkcji == "Przewodniczący Regionu / Koła / Rada Krajowa / KKRD (+10 zł / msc)":
                    stawka_fn_pln = 10.0
                elif opcja_funkcji == "Inna kwota funkcyjna (własna)":
                    stawka_fn_pln = st.number_input("Miesięczna stawka funkcyjna (PLN):", min_value=0.0, value=10.0, step=5.0)
                else:
                    stawka_fn_pln = 0.0

            with col_fn2:
                if stawka_fn_pln > 0:
                    miesiace_fn = st.number_input("Liczba miesięcy pełnienia funkcji:", min_value=0, max_value=120, value=0, step=1)
                else:
                    miesiace_fn = 0
                    st.text_input("Liczba miesięcy pełnienia funkcji:", value="0 (brak)", disabled=True)

            st.markdown("---")
            st.markdown("#### 💰 Wartości Finansowe")
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                calc_saldo_start_pln = st.number_input("Saldo początkowe (PLN)", min_value=-10000.0, max_value=10000.0, value=0.0, step=10.0, key="calc_s_start")
            with c_f2:
                calc_wplaty_pln = st.number_input("Suma dotychczasowych wpłat (PLN)", min_value=0.0, max_value=50000.0, value=0.0, step=10.0, key="calc_wpl")

        suma_calkowita_gr, suma_podstawowa_gr, suma_funkcyjna_gr, licznik_miesiecy, historia_progow = oblicz_symulacje_kalkulatora(
            calc_data_wst, calc_data_ur, calc_param_kod, calc_punkt_odniesienia, data_poczatku_naliczania,
            uwzglednij_biezacy, int(round(stawka_fn_pln * 100)), miesiace_fn
        )

        prog_biezacy, stawka_biezaca_gr = pobierz_parametr(calc_data_ur, calc_param_kod, calc_punkt_odniesienia)
        stawka_biezaca_pln = stawka_biezaca_gr / 100.0

        saldo_start_gr = int(round(calc_saldo_start_pln * 100))
        wplaty_gr = int(round(calc_wplaty_pln * 100))
        saldo_koncowe_gr = saldo_start_gr + wplaty_gr - suma_calkowita_gr
        saldo_koncowe_pln = saldo_koncowe_gr / 100.0

        s_i_gr = max(0, saldo_start_gr) + wplaty_gr
        z_i_gr = max(0, s_i_gr - saldo_koncowe_gr)
        kdi_calc = round(z_i_gr / s_i_gr, 2) if s_i_gr > 0 else None
        kdi_str = f"{kdi_calc:.2f}" if kdi_calc is not None else "Brak danych"
        kolor_kdi = pobierz_kolor_kdi(kdi_calc)

        if saldo_koncowe_gr >= 0:
            moze_glosowac = True
            miesiace_dlugu = 0.0
            doplata_do_glosu_pln = 0.0
        else:
            miesiace_dlugu = abs(saldo_koncowe_gr) / max(stawka_biezaca_gr, 1)
            moze_glosowac = (miesiace_dlugu <= 6.0)
            limit_karencji_gr = 6 * stawka_biezaca_gr
            doplata_do_glosu_gr = max(0, abs(saldo_koncowe_gr) - limit_karencji_gr)
            doplata_do_glosu_pln = doplata_do_glosu_gr / 100.0

        doplata_do_zera_pln = max(0.0, -saldo_koncowe_pln)

        etykiety_stawek = {
            "STARA_<16": "0 zł (Stara Uchwała: < 16 lat)",
            "STARA_16-20": "5 zł (Stara Uchwała: 16–20 lat)",
            "STARA_21+": "10 zł (Stara Uchwała: 21+ lat)",
            "B": "6 zł (Nowa Uchwała: < 20 lat)",
            "M": "9 zł (Nowa Uchwała: 20–29 lat)",
            "S": "15 zł (Nowa Uchwała: 30+ lat)"
        }

        with col_out:
            st.markdown("#### 📊 Wynik Symulacji")

            cb1, cb2 = st.columns(2)
            with cb1:
                kolor_salda = "accent-green" if saldo_koncowe_pln >= 0 else "accent-rose"
                render_bento_card("Saldo Końcowe", f"{saldo_koncowe_pln:,.2f} PLN", f"Start: {calc_saldo_start_pln:.2f} zł | Wpłaty: {calc_wplaty_pln:.2f} zł", kolor_salda)
            with cb2:
                render_bento_card("Wskaźnik KDI", kdi_str, "Cel statutowy: ≤ 1.20", styl_custom=f"color: {kolor_kdi}; text-shadow: 0 0 16px {kolor_kdi}55;")

            cb3, cb4 = st.columns(2)
            with cb3:
                kolor_glosu = "#10b981" if moze_glosowac else "#f43f5e"
                napis_glosu = "TAK (UPRAWNIONY)" if moze_glosowac else "NIE (ZAWIESZONY)"
                render_bento_card("Prawo Głosu (Karencja ≤ 6 msc)", napis_glosu, f"Zadłużenie: {miesiace_dlugu:.1f} msc (limit: 6.0 msc)", styl_custom=f"color: {kolor_glosu}; font-size: 1.45rem;")
            with cb4:
                sub_txt = f"{licznik_miesiecy} msc | Próg bieżący: {prog_biezacy}"
                if suma_funkcyjna_gr > 0:
                    sub_txt += f" (+{(suma_funkcyjna_gr / 100):.2f} zł funkcyjne)"
                render_bento_card("Naliczone Składki", f"{(suma_calkowita_gr / 100.0):,.2f} PLN", sub_txt, "accent-cyan")

            if historia_progow or suma_funkcyjna_gr > 0:
                detale = []
                for p, cnt in sorted(historia_progow.items()):
                    detale.append(f"• **{cnt} msc** × {etykiety_stawek.get(p, p)}")
                if suma_funkcyjna_gr > 0:
                    detale.append(f"• **{miesiace_fn} msc** × {stawka_fn_pln:.2f} zł (Składka funkcyjna) = **{(suma_funkcyjna_gr / 100):.2f} zł**")
                st.info("📋 **Rozbicie naliczeń w okresie symulacji:**\n\n" + "\n".join(detale))

            st.markdown("##### 📋 Rekomendacja dla wpłacającego:")
            if saldo_koncowe_pln >= 0:
                st.success(f"✅ **Konto w pełni uregulowane.** Nadpłata wynosi **{saldo_koncowe_pln:.2f} zł**. Członek ma pewne prawo głosu na zebraniach.")
            elif moze_glosowac:
                st.warning(f"⚠️ **Zadłużenie w granicach karencji ({miesiace_dlugu:.1f} msc długu).** Członek zachowuje prawo głosu. Do pełnego wyzerowania konta brakuje: **{doplata_do_zera_pln:.2f} zł**.")
            else:
                st.error(f"""
                    ❌ **Utrata prawa głosu!** Zadłużenie przekracza limit 6 miesięcy (wynosi **{miesiace_dlugu:.1f} msc**).
                    * Aby **przywrócić prawo głosu**, członek musi wpłacić minimum: **{doplata_do_glosu_pln:.2f} zł**
                    * Aby **całkowicie wyzerować zadłużenie**, należy wpłacić: **{doplata_do_zera_pln:.2f} zł**
                """)

            with st.expander("🔍 Symulacja natychmiastowej dopłaty (Co jeśli wpłaci X zł?)"):
                sym_doplata = st.slider("Symulowana kwota przelewu (PLN):", min_value=0.0, max_value=float(max(100.0, doplata_do_zera_pln + 50.0)), value=float(doplata_do_glosu_pln), step=5.0)
                sym_nowe_saldo = saldo_koncowe_pln + sym_doplata
                sym_nowe_msc_dlugu = abs(sym_nowe_saldo) / stawka_biezaca_pln if sym_nowe_saldo < 0 else 0.0
                sym_glos = (sym_nowe_saldo >= 0) or (sym_nowe_msc_dlugu <= 6.0)
                
                st.write(f"• Nowe saldo po dopłacie: **{sym_nowe_saldo:+.2f} zł**")
                st.write(f"• Nowe zadłużenie: **{sym_nowe_msc_dlugu:.1f} miesięcy**")
                st.write(f"• Status głosu: **{'✅ UPRAWNIONY' if sym_glos else '❌ NADAL BEZ PRAWA GŁOSU'}**")

    # 9. WPŁATY DO ZAAKCEPTOWANIA
    klucz_akcept = next((k for k in zakladki_nazwy if "Wpłaty do zaakceptowania" in k), None)
    if klucz_akcept and klucz_akcept in tab_map:
        with tab_map[klucz_akcept]:
            st.markdown("### 📥 Kolejka Weryfikacji Wpłat")
            st.caption("Wpłaty zadeklarowane przez Skarbników Kół i Regionów.")
            oczekujace_df = db_query("""
                SELECT wo.id, wo.kolo_id, k.nazwa as kolo_nazwa, wo.czlonek_id, c.imie_nazwisko as czlonek_nazwa,
                       wo.kwota_gr, wo.data_wplaty, wo.notatka, wo.oswiadczenie, wo.data_zgloszenia,
                       u.imie_nazwisko as zglosil_nazwa
                FROM wplaty_oczekujace wo
                JOIN kola k ON wo.kolo_id = k.id
                LEFT JOIN czlonkowie c ON wo.czlonek_id = c.id
                LEFT JOIN uzytkownicy u ON wo.zglosil_uzytkownik_id = u.id
                WHERE wo.status = 'OCZEKUJE'
                ORDER BY wo.data_zgloszenia ASC
            """)

            if oczekujace_df.empty:
                st.success("🎉 Brak oczekujących wpłat. Wszystkie transakcje są rozpatrzone!")
            else:
                for _, r_oczek in oczekujace_df.iterrows():
                    o_id = r_oczek["id"]
                    o_kolo = r_oczek["kolo_nazwa"]
                    o_czl = r_oczek["czlonek_nazwa"] or "Brak przypisania"
                    o_kwota = r_oczek["kwota_gr"] / 100.0
                    
                    st.markdown(f"**{o_czl}** ({o_kolo}) — **{o_kwota:.2f} zł** | Przelew: **{r_oczek['data_wplaty']}** | Zgłosił: {r_oczek['zglosil_nazwa']}")
                    c_ak1, c_ak2 = st.columns([1, 1])
                    with c_ak1:
                        if st.button(f"✅ Akceptuj wpłatę #{o_id}", key=f"btn_akcept_{o_id}"):
                            teraz_akcept = teraz_utc()
                            idempotent_key = f"zaakceptowana_oczekujaca_{o_id}"
                            with pool.connection() as conn:
                                with conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO wplaty (kolo_id, czlonek_id, kwota_gr, data_wplaty, notatka, data_wpisu, idempotency_key)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (r_oczek["kolo_id"], r_oczek["czlonek_id"], r_oczek["kwota_gr"], r_oczek["data_wplaty"], r_oczek["notatka"], teraz_akcept, idempotent_key))
                                    
                                    cur.execute("""
                                        UPDATE wplaty_oczekujace 
                                        SET status = 'ZAAKCEPTOWANA', rozpatrzyl_uzytkownik_id = %s, data_rozpatrzenia = %s 
                                        WHERE id = %s
                                    """, (curr_user_id, teraz_akcept, o_id))
                                conn.commit()
                            st.cache_data.clear()
                            st.success(f"Zaksięgowano wpłatę.")
                            st.rerun()
                    with c_ak2:
                        with st.expander("❌ Odrzuć wpłatę"):
                            powod_odrzut = st.text_input("Powód odrzucenia:", value="Brak wpływu na wyciągu", key=f"txt_odrzuc_{o_id}")
                            if st.button("Potwierdź odrzucenie", key=f"btn_odrzuc_{o_id}"):
                                db_execute("""
                                    UPDATE wplaty_oczekujace 
                                    SET status = 'ODRZUCONA', rozpatrzyl_uzytkownik_id = %s, data_rozpatrzenia = %s, powod_odrzucenia = %s 
                                    WHERE id = %s
                                """, (curr_user_id, teraz_utc(), powod_odrzut, o_id))
                                st.warning("Wpłata odrzucona.")
                                st.rerun()
                    st.divider()

    # 10. ZARZĄDZANIE STRUKTURĄ
    if "🏛️ Zarządzaj Strukturą" in tab_map:
        with tab_map["🏛️ Zarządzaj Strukturą"]:
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

    # 11. LOGI AUDYTOWE
    if "📜 Logi Audytowe" in tab_map:
        with tab_map["📜 Logi Audytowe"]:
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

    # 12. PANEL CENTAURI
    if "🏛️ Panel Centauri" in tab_map:
        with tab_map["🏛️ Panel Centauri"]:
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