import calendar
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from calculations import filtruj_interwal, oblicz_naliczenia_gr, pobierz_stawke_za_miesiac
from celestia import pobierz_kolor_celestia
from components.charts import PLOTLY_CONFIG, czy_jasny_motyw, render_wykres_kdi, render_wykres_salda
from components.ui import render_bento_card
from config import DATA_ODCIECIA, parse_date, pobierz_kolor_kdi
from database import db_query


def render_tab_profile(dane_przeliczone, dzis):
    if not dane_przeliczone:
        st.info("Brak danych do analizy.")
        return

    is_light = czy_jasny_motyw()
    mapa_osob = {d["id"]: f"{d['imie_nazwisko']} (Saldo: {d['saldo_akt_pln']:.2f} zł, KDI: {d['kdi_str']}, Celestia: {d.get('celestia_rating', '—')})" for d in dane_przeliczone}
    wybrany_id = st.selectbox("Wybierz członka do analizy wskaźników", options=list(mapa_osob.keys()), format_func=lambda x: mapa_osob[x])
    osoba = next(item for item in dane_przeliczone if item["id"] == wybrany_id)

    kolor_kdi_osoby = pobierz_kolor_kdi(osoba["kdi_val"])
    kolor_glos = "#10b981" if osoba["moze_glosowac"] else "#f43f5e"
    kolor_celestia = pobierz_kolor_celestia(osoba.get("celestia_rating", "DDD"), is_light)

    st.markdown(f"""
        <div class="profile-banner-card">
            <div><span style="color: #94a3b8; font-size: 0.85rem;">CZŁONEK:</span> <strong style="font-size: 1rem;">{osoba['imie_nazwisko']}</strong></div>
            <div><span style="color: #94a3b8; font-size: 0.85rem;">CELESTIA:</span> <strong style="color: {kolor_celestia}; font-size: 1.15rem; text-shadow: 0 0 10px {kolor_celestia};">{osoba.get('celestia_rating', '—')} ({osoba.get('celestia_score', 0)} pkt)</strong></div>
            <div><span style="color: #94a3b8; font-size: 0.85rem;">AKTUALNY KDI:</span> <strong style="color: {kolor_kdi_osoby}; font-size: 1.15rem; text-shadow: 0 0 10px {kolor_kdi_osoby};">{osoba['kdi_str']}</strong></div>
            <div><span style="color: #94a3b8; font-size: 0.85rem;">SALDO:</span> <strong style="color: {'#22c55e' if osoba['saldo_akt_pln'] >= 0 else '#f43f5e'}; font-size: 1rem;">{osoba['saldo_akt_pln']:.2f} zł</strong></div>
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
        st.plotly_chart(render_wykres_salda(punkty_x, punkty_saldo), width="stretch", config=PLOTLY_CONFIG)
    with subtab_kdi:
        st.plotly_chart(render_wykres_kdi(punkty_x, punkty_kdi, kdi_val=osoba["kdi_val"]), width="stretch", config=PLOTLY_CONFIG)

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

    # SEKCJA CELESTIA — AUDYT DYSCYPLINY W DNIACH GŁOSOWAŃ
    st.markdown("---")
    st.markdown("### ⭐ Celestia — Audyt Wiarygodności i Dni Głosowań")

    score_osoby = osoba.get('celestia_score', 0)
    kolor_score = pobierz_kolor_celestia(score_osoby, is_light)
    st.markdown(
        f"Klasa wiarygodności: <strong style='color: {kolor_score}; font-size: 1.1rem; text-shadow: 0 0 10px {kolor_score};'>{osoba.get('celestia_nazwa', 'Brak')} ({osoba.get('celestia_rating', '—')})</strong> | "
        f"Score: <strong style='color: {kolor_score}; font-size: 1.1rem; text-shadow: 0 0 10px {kolor_score};'>{score_osoby} / 1000 pkt</strong> | "
        f"{osoba.get('celestia_opis', '—')}",
        unsafe_allow_html=True
    )

    filary = osoba.get("celestia_filary", {})
    cf1, cf2, cf3, cf4 = st.columns(4)
    with cf1:
        vdc_val = filary.get("vdc_score")
        vdc_text = f"{vdc_val} pkt" if vdc_val is not None else "Brak zebrań"
        sub_text = f"W oparciu o {filary.get('liczba_glosowan', 0)} głosowań" if vdc_val is not None else "Brak zarejestrowanych zebrań"
        if vdc_val is not None:
            kolor_vdc = pobierz_kolor_celestia(vdc_val, is_light)
            styl_vdc = f"color: {kolor_vdc}; text-shadow: 0 0 14px {kolor_vdc};"
        else:
            styl_vdc = "color: #94a3b8;"
        render_bento_card("Dyscyplina Głosowań (65%)", vdc_text, sub_text, styl_custom=styl_vdc)
    with cf2:
        kdi_score = filary.get('kdi_score', 0)
        kolor_kdi = pobierz_kolor_celestia(kdi_score, is_light)
        styl_kdi = f"color: {kolor_kdi}; text-shadow: 0 0 14px {kolor_kdi};"
        render_bento_card("Wskaźnik KDI (10%)", f"{kdi_score} pkt", f"KDI: {osoba['kdi_str']}", styl_custom=styl_kdi)
    with cf3:
        saldo_score = filary.get('saldo_score', 0)
        kolor_saldo = pobierz_kolor_celestia(saldo_score, is_light)
        styl_saldo = f"color: {kolor_saldo}; text-shadow: 0 0 14px {kolor_saldo};"
        render_bento_card("Bieżące Saldo (20%)", f"{saldo_score} pkt", f"Saldo: {osoba['saldo_akt_pln']:.2f} zł", styl_custom=styl_saldo)
    with cf4:
        rytm_score = filary.get('rytm_score', 0)
        kolor_rytm = pobierz_kolor_celestia(rytm_score, is_light)
        styl_rytm = f"color: {kolor_rytm}; text-shadow: 0 0 14px {kolor_rytm};"
        render_bento_card("Rytm Płatności (5%)", f"{rytm_score} pkt", f"Liczba wpłat: {len(hist_wplaty)}", styl_custom=styl_rytm)

    audyt_glosowan = osoba.get("celestia_audyt_glosowan", [])
    if audyt_glosowan:
        st.markdown("#### 🗳️ Historia Dyscypliny na Głosowaniach Koła")
        st.caption("Ocena salda oraz wpłat w skonfigurowanym oknie zbiórki przed każdym terminem zapadalności:")
        df_audyt = pd.DataFrame([
            {
                "Data Głosowania": a["data_glosowania"],
                "Wydarzenie / Zebranie": a["nazwa"],
                "Okno Zbiórki": a.get("okres_zbiorki", "—"),
                "Wymagalność do": a.get("data_wymagalnosci", a["data_glosowania"]),
                "Saldo na Termin": f"{a['saldo_pln']:.2f} zł",
                "Wpłata w Oknie": f"{a['wplata_w_oknie_pln']:.2f} zł",
                "Ocena (0-100)": f"{a['punkty']} pkt",
                "Status Zdarzenia": a["status"]
            }
            for a in audyt_glosowan
        ])

        def stylizuj_ocena_glosowania(val):
            try:
                pkt_num = int(str(val).replace(" pkt", "").strip())
                kolor = pobierz_kolor_celestia(pkt_num * 10, is_light)
                return f"color: {kolor}; font-weight: 800;"
            except Exception:
                return ""

        styler_audyt = df_audyt.style.map(stylizuj_ocena_glosowania, subset=["Ocena (0-100)"])
        st.dataframe(styler_audyt, width="stretch", hide_index=True)
    else:
        st.info("Brak zarejestrowanych terminów głosowań przypadających w trakcie członkostwa tej osoby.")

