import pandas as pd
import streamlit as st
from config import pobierz_kolor_kdi, pobierz_kolor_uprawnionych
from database import pobierz_aktywne_kola_kraju
from calculations import przelicz_finanse_wielu_kol
from components.ui import render_bento_card
from components.charts import render_wykres_slupkowy_kdi, PLOTLY_CONFIG

def render_view_kraj(wybrany_kraj_id, mapa_krajow, mapa_regionow, dzis):
    nazwa_kraju = mapa_krajow.get(wybrany_kraj_id, "Polska")
    st.markdown(f"## 🇵🇱 Statystyki Ogólnokrajowe: {nazwa_kraju}")
    st.caption("Zagregowany bilans wszystkich aktywnych regionów i kół podległych jednostce centralnej | Czas biznesowy: **Warszawa**")

    wszystkie_aktywne_kola_kraju = pobierz_aktywne_kola_kraju(wybrany_kraj_id)

    kola_bez_regionu = wszystkie_aktywne_kola_kraju[wszystkie_aktywne_kola_kraju["region_id"].isna()]
    if not kola_bez_regionu.empty:
        nazwy_brak = ", ".join(kola_bez_regionu["nazwa"].tolist())
        st.warning(f"⚠️ **Wykryto {len(kola_bez_regionu)} koła bez przypisanego regionu:** {nazwy_brak}. Zostały ujęte w wierszu 'Bez regionu' poniżej.")

    if wszystkie_aktywne_kola_kraju.empty:
        st.info("Brak aktywnych kół w tym kraju.")
        return

    lista_kol_kraj = wszystkie_aktywne_kola_kraju["id"].tolist()
    finanse_hurt_kraj = przelicz_finanse_wielu_kol(lista_kol_kraj, dzis)

    kraj_kasa_gr = 0
    kraj_wplaty_gr = 0
    kraj_wydatki_gr = 0
    kraj_total_z_gr = 0
    kraj_total_s_gr = 0
    kraj_czlonkowie_count = 0
    kraj_uprawnieni_count = 0

    statystyki_per_region = {}
    for reg_id, reg_nazwa in mapa_regionow.items():
        statystyki_per_region[reg_id] = {
            "Region": reg_nazwa, "Liczba Kół": 0, "Członkowie": 0, "Kasa": 0, 
            "Wpłaty": 0, "Wydatki": 0, "total_z": 0, "total_s": 0, "uprawnieni": 0
        }

    bez_regionu_stat = {
        "Region": "⚠️ Bez regionu (nieprzypisane)", "Liczba Kół": 0, "Członkowie": 0, "Kasa": 0,
        "Wpłaty": 0, "Wydatki": 0, "total_z": 0, "total_s": 0, "uprawnieni": 0
    }

    for row in wszystkie_aktywne_kola_kraju.itertuples(index=False):
        k_id = row.id
        r_id = row.region_id
        dane, wplaty_kasa, kasa, wydatki, _, z_gr, s_gr = finanse_hurt_kraj.get(k_id, ([], 0, 0, 0, 0, 0, 0))
        
        kraj_kasa_gr += kasa
        kraj_wplaty_gr += wplaty_kasa
        kraj_wydatki_gr += wydatki
        kraj_total_z_gr += z_gr
        kraj_total_s_gr += s_gr
        
        czl_cnt = len(dane)
        upr_cnt = sum(1 for d in dane if d["moze_glosowac"])
        kraj_czlonkowie_count += czl_cnt
        kraj_uprawnieni_count += upr_cnt

        target_bucket = statystyki_per_region[r_id] if pd.notna(r_id) and r_id in statystyki_per_region else bez_regionu_stat
        target_bucket["Liczba Kół"] += 1
        target_bucket["Członkowie"] += czl_cnt
        target_bucket["Kasa"] += kasa
        target_bucket["Wpłaty"] += wplaty_kasa
        target_bucket["Wydatki"] += wydatki
        target_bucket["total_z"] += z_gr
        target_bucket["total_s"] += s_gr
        target_bucket["uprawnieni"] += upr_cnt

    kraj_kdi_val = round(kraj_total_z_gr / kraj_total_s_gr, 2) if kraj_total_s_gr > 0 else None
    kraj_kdi_str = f"{kraj_kdi_val:.2f}" if kraj_kdi_val is not None else "Brak danych"
    kolor_kraj_kdi = pobierz_kolor_kdi(kraj_kdi_val)

    kraj_pct_upr = (kraj_uprawnieni_count / kraj_czlonkowie_count * 100.0) if kraj_czlonkowie_count > 0 else 0.0
    kolor_kraj_upr = pobierz_kolor_uprawnionych(kraj_pct_upr if kraj_czlonkowie_count > 0 else None)
    kraj_kasa_color = "accent-green" if kraj_kasa_gr >= 0 else "accent-rose"

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        render_bento_card("Kasa Całego Kraju", f"{(kraj_kasa_gr / 100.0):,.2f} PLN", "Wpłaty - Wydatki + Korekty", kraj_kasa_color)
    with kc2:
        render_bento_card("Suma Składek (Kraj)", f"{(kraj_wplaty_gr / 100.0):,.2f} PLN", f"Wydatki: {(kraj_wydatki_gr / 100.0):,.2f} PLN", "accent-cyan")
    with kc3:
        render_bento_card("Zagregowany KDI Kraju", kraj_kdi_str, "Rekomendowane: ≤ 1.20", styl_custom=f"color: {kolor_kraj_kdi}; text-shadow: 0 0 16px {kolor_kraj_kdi}55;")
    with kc4:
        render_bento_card("Uprawnieni do Głosu (Kraj)", f"{kraj_uprawnieni_count} / {kraj_czlonkowie_count}", f"{kraj_pct_upr:.1f}% (karencja ≤ 6 msc)", styl_custom=f"color: {kolor_kraj_upr}; text-shadow: 0 0 16px {kolor_kraj_upr}55;")

    st.markdown("### 🗺️ Zestawienie Regionów w Polsce")
    tabela_zbiorcza_reg = []
    dane_wykres_reg = []
    for r_id, s in statystyki_per_region.items():
        r_kdi = round(s["total_z"] / s["total_s"], 2) if s["total_s"] > 0 else None
        r_pct = (s["uprawnieni"] / s["Członkowie"] * 100.0) if s["Członkowie"] > 0 else 0.0
        tabela_zbiorcza_reg.append({
            "Region": s["Region"],
            "Liczba Kół": s["Liczba Kół"],
            "Członkowie": s["Członkowie"],
            "Kasa Regionu": f"{(s['Kasa'] / 100.0):,.2f} zł",
            "Wpłaty": f"{(s['Wpłaty'] / 100.0):,.2f} zł",
            "Wydatki": f"{(s['Wydatki'] / 100.0):,.2f} zł",
            "KDI Regionu": f"{r_kdi:.2f}" if r_kdi is not None else "Brak danych",
            "Uprawnieni": f"{s['uprawnieni']}/{s['Członkowie']} ({r_pct:.1f}%)"
        })
        if r_kdi is not None:
            dane_wykres_reg.append({"nazwa": s["Region"], "kdi": r_kdi})
    
    if bez_regionu_stat["Liczba Kół"] > 0:
        br_kdi = round(bez_regionu_stat["total_z"] / bez_regionu_stat["total_s"], 2) if bez_regionu_stat["total_s"] > 0 else None
        br_pct = (bez_regionu_stat["uprawnieni"] / bez_regionu_stat["Członkowie"] * 100.0) if bez_regionu_stat["Członkowie"] > 0 else 0.0
        tabela_zbiorcza_reg.append({
            "Region": bez_regionu_stat["Region"],
            "Liczba Kół": bez_regionu_stat["Liczba Kół"],
            "Członkowie": bez_regionu_stat["Członkowie"],
            "Kasa Regionu": f"{(bez_regionu_stat['Kasa'] / 100.0):,.2f} zł",
            "Wpłaty": f"{(bez_regionu_stat['Wpłaty'] / 100.0):,.2f} zł",
            "Wydatki": f"{(bez_regionu_stat['Wydatki'] / 100.0):,.2f} zł",
            "KDI Regionu": f"{br_kdi:.2f}" if br_kdi is not None else "Brak danych",
            "Uprawnieni": f"{bez_regionu_stat['uprawnieni']}/{bez_regionu_stat['Członkowie']} ({br_pct:.1f}%)"
        })
        if br_kdi is not None:
            dane_wykres_reg.append({"nazwa": bez_regionu_stat["Region"], "kdi": br_kdi})

    tab_tabela, tab_wykres = st.tabs(["📋 Tabela Regionów", "📊 Porównanie KDI Regionów"])
    with tab_tabela:
        st.dataframe(pd.DataFrame(tabela_zbiorcza_reg), width="stretch", hide_index=True)
    with tab_wykres:
        fig_reg = render_wykres_slupkowy_kdi(dane_wykres_reg, tytul_x="Wskaźnik KDI Regionu")
        if fig_reg:
            st.plotly_chart(fig_reg, width="stretch", config=PLOTLY_CONFIG)
        else:
            st.caption("Brak danych KDI do wygenerowania wykresu regionów.")