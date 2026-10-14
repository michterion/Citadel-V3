import calendar
from datetime import date, timedelta
import pandas as pd
import streamlit as st

from config import DATA_ODCIECIA, parse_date, pobierz_kolor_kdi
from database import db_query
from calculations import oblicz_naliczenia_gr, filtruj_interwal, pobierz_stawke_za_miesiac
from components.charts import render_wykres_salda, render_wykres_kdi

def render_tab_profile(dane_przeliczone, dzis):
    if not dane_przeliczone:
        st.info("Brak danych do analizy.")
        return

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

