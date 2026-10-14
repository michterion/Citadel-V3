import pandas as pd
import streamlit as st
from config import pobierz_kolor_kdi, pobierz_kolor_uprawnionych
from database import db_query
from calculations import przelicz_finanse_wielu_kol
from components.ui import render_bento_card
from components.charts import render_wykres_slupkowy_kdi, PLOTLY_CONFIG

def render_view_region(wybrany_kraj_id, wybrany_region_id, nazwa_wybranego_regionu, nazwa_kraju, dzis):
    st.markdown(f"## 📊 Pulpit Analityczny: {nazwa_wybranego_regionu}")
    st.caption(f"Kraj: **{nazwa_kraju}** | Strefa biznesowa: **Warszawa**")

    if wybrany_region_id == -1:
        kola_w_tym_regionie = db_query("""
            SELECT id, nazwa FROM aktywne_kola 
            WHERE region_id IS NULL AND kraj_id = %s 
            ORDER BY nazwa ASC
        """, (wybrany_kraj_id,))
    else:
        kola_w_tym_regionie = db_query("""
            SELECT id, nazwa FROM aktywne_kola 
            WHERE region_id = %s 
            ORDER BY nazwa ASC
        """, (wybrany_region_id,))

    if kola_w_tym_regionie.empty:
        st.info(f"Region '{nazwa_wybranego_regionu}' nie posiada aktualnie przypisanych aktywnych kół.")
        return

    lista_kol_reg = kola_w_tym_regionie["id"].tolist()
    finanse_hurt_reg = przelicz_finanse_wielu_kol(lista_kol_reg, dzis)

    reg_kasa_gr = 0
    reg_wplaty_gr = 0
    reg_wydatki_gr = 0
    reg_total_z_gr = 0
    reg_total_s_gr = 0
    reg_lacznie_czlonkow = 0
    reg_uprawnieni_count = 0
    
    tabela_kol = []
    dane_wykres_kol = []
    for k_row in kola_w_tym_regionie.itertuples(index=False):
        k_id = k_row.id
        k_nazwa = k_row.nazwa
        dane, wplaty_kasa, kasa, wydatki, _, z_gr, s_gr = finanse_hurt_reg.get(k_id, ([], 0, 0, 0, 0, 0, 0))
        
        reg_kasa_gr += kasa
        reg_wplaty_gr += wplaty_kasa
        reg_wydatki_gr += wydatki
        reg_total_z_gr += z_gr
        reg_total_s_gr += s_gr
        
        czl_count = len(dane)
        upr_count = sum(1 for d in dane if d["moze_glosowac"])
        reg_lacznie_czlonkow += czl_count
        reg_uprawnieni_count += upr_count
        
        k_kdi_val = round(z_gr / s_gr, 2) if s_gr > 0 else None
        k_pct_upr = (upr_count / czl_count * 100.0) if czl_count > 0 else 0.0
        
        tabela_kol.append({
            "ID": k_id,
            "Koło": k_nazwa,
            "Liczba Członków": czl_count,
            "Kasa Koła": f"{(kasa / 100.0):,.2f} zł",
            "Wpłacone Składki": f"{(wplaty_kasa / 100.0):,.2f} zł",
            "Wydatki": f"{(wydatki / 100.0):,.2f} zł",
            "KDI Koła": f"{k_kdi_val:.2f}" if k_kdi_val is not None else "Brak danych",
            "Uprawnieni": f"{upr_count}/{czl_count} ({k_pct_upr:.1f}%)"
        })
        if k_kdi_val is not None:
            dane_wykres_kol.append({"nazwa": k_nazwa, "kdi": k_kdi_val})

    reg_kdi_val = round(reg_total_z_gr / reg_total_s_gr, 2) if reg_total_s_gr > 0 else None
    reg_kdi_str = f"{reg_kdi_val:.2f}" if reg_kdi_val is not None else "Brak danych"
    kolor_reg_kdi = pobierz_kolor_kdi(reg_kdi_val)
    
    reg_pct_upr = (reg_uprawnieni_count / reg_lacznie_czlonkow * 100.0) if reg_lacznie_czlonkow > 0 else 0.0
    kolor_reg_upr = pobierz_kolor_uprawnionych(reg_pct_upr if reg_lacznie_czlonkow > 0 else None)
    kasa_color = "accent-green" if reg_kasa_gr >= 0 else "accent-rose"

    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1:
        render_bento_card("Kasa Całego Regionu", f"{(reg_kasa_gr / 100.0):,.2f} PLN", "Zagregowane środki płynne", kasa_color)
    with rc2:
        render_bento_card("Suma Składek Regionu", f"{(reg_wplaty_gr / 100.0):,.2f} PLN", f"Wydatki: {(reg_wydatki_gr / 100.0):,.2f} PLN", "accent-cyan")
    with rc3:
        render_bento_card("Zagregowany KDI Regionu", reg_kdi_str, "Rekomendowane: ≤ 1.20", styl_custom=f"color: {kolor_reg_kdi}; text-shadow: 0 0 16px {kolor_reg_kdi}55;")
    with rc4:
        render_bento_card("Uprawnieni do Głosu (Region)", f"{reg_uprawnieni_count} / {reg_lacznie_czlonkow}", f"{reg_pct_upr:.1f}% (karencja ≤ 6 msc)", styl_custom=f"color: {kolor_reg_upr}; text-shadow: 0 0 16px {kolor_reg_upr}55;")

    st.markdown(f"### 🏛️ Koła podległe pod {nazwa_wybranego_regionu}")
    tab_tabela, tab_wykres = st.tabs(["📋 Tabela Kół", "📊 Porównanie KDI Kół"])
    with tab_tabela:
        st.dataframe(pd.DataFrame(tabela_kol), width="stretch", hide_index=True)
    with tab_wykres:
        fig_kol = render_wykres_slupkowy_kdi(dane_wykres_kol, tytul_x="Wskaźnik KDI Koła")
        if fig_kol:
            st.plotly_chart(fig_kol, width="stretch", config=PLOTLY_CONFIG)
        else:
            st.caption("Brak danych KDI do wygenerowania wykresu kół.")