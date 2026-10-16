import pandas as pd
import streamlit as st
from calculations import formatuj_wartosc_kdi, oblicz_dynamiczny_prog_kdi, przelicz_finanse_wielu_kol
from components.charts import PLOTLY_CONFIG, render_wykres_slupkowy_kdi
from components.ui import render_bento_card
from config import pobierz_kolor_kdi, pobierz_kolor_uprawnionych
from database import db_query


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
    wszyscy_czlonkowie_reg = []
    for k_row in kola_w_tym_regionie.itertuples(index=False):
        k_id = k_row.id
        k_nazwa = k_row.nazwa
        dane, wplaty_kasa, kasa, wydatki, _, z_gr, s_gr = finanse_hurt_reg.get(k_id, ([], 0, 0, 0, 0, 0, 0))
        if dane:
            wszyscy_czlonkowie_reg.extend(dane)

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
        k_prog_val, k_prog_str = oblicz_dynamiczny_prog_kdi(dane)
        k_pct_upr = (upr_count / czl_count * 100.0) if czl_count > 0 else 0.0

        tabela_kol.append({
            "ID": k_id,
            "Koło": k_nazwa,
            "Liczba Członków": czl_count,
            "Kasa Koła": f"{(kasa / 100.0):,.2f} zł",
            "Wpłacone Składki": f"{(wplaty_kasa / 100.0):,.2f} zł",
            "Wydatki": f"{(wydatki / 100.0):,.2f} zł",
            "KDI Koła": f"{k_kdi_val:.2f}" if k_kdi_val is not None else "Brak danych",
            "Próg KDI (głos)": k_prog_str,
            "Uprawnieni": f"{upr_count}/{czl_count} ({k_pct_upr:.1f}%)"
        })
        if k_kdi_val is not None:
            dane_wykres_kol.append({"nazwa": k_nazwa, "kdi": k_kdi_val})

    reg_kdi_val = round(reg_total_z_gr / reg_total_s_gr, 2) if reg_total_s_gr > 0 else None
    reg_kdi_str = f"{reg_kdi_val:.2f}" if reg_kdi_val is not None else "Brak danych"
    kolor_reg_kdi = pobierz_kolor_kdi(reg_kdi_val)
    reg_kdi_prog_val, reg_kdi_prog_str = oblicz_dynamiczny_prog_kdi(wszyscy_czlonkowie_reg)
    wartosc_reg_kdi_html = formatuj_wartosc_kdi(reg_kdi_str, reg_kdi_prog_val, reg_kdi_prog_str)

    reg_pct_upr = (reg_uprawnieni_count / reg_lacznie_czlonkow * 100.0) if reg_lacznie_czlonkow > 0 else 0.0
    kolor_reg_upr = pobierz_kolor_uprawnionych(reg_pct_upr if reg_lacznie_czlonkow > 0 else None)
    kasa_color = "accent-green" if reg_kasa_gr >= 0 else "accent-rose"

    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1:
        render_bento_card("Kasa Całego Regionu", f"{(reg_kasa_gr / 100.0):,.2f} PLN", "Zagregowane środki płynne", kasa_color)
    with rc2:
        render_bento_card("Suma Składek Regionu", f"{(reg_wplaty_gr / 100.0):,.2f} PLN", f"Wydatki: {(reg_wydatki_gr / 100.0):,.2f} PLN", "accent-cyan")
    with rc3:
        render_bento_card("Zagregowany KDI Regionu", wartosc_reg_kdi_html, "Rekomendowane: ≤ 1.20", styl_custom=f"color: {kolor_reg_kdi}; text-shadow: 0 0 16px {kolor_reg_kdi};")
    with rc4:
        render_bento_card("Uprawnieni do Głosu (Region)", f"{reg_uprawnieni_count} / {reg_lacznie_czlonkow}", f"{reg_pct_upr:.1f}% (karencja ≤ 6 msc)", styl_custom=f"color: {kolor_reg_upr}; text-shadow: 0 0 16px {kolor_reg_upr};")

    st.markdown(f"### 🏛️ Koła podległe pod {nazwa_wybranego_regionu}")
    tab_tabela, tab_wykres = st.tabs(["📋 Tabela Kół", "📊 Porównanie KDI Kół"])
    with tab_tabela:
        df_kol = pd.DataFrame(tabela_kol)
        if not df_kol.empty:
            def stylizuj_kdi_kolo(wartosc):
                kolor = pobierz_kolor_kdi(wartosc)
                if wartosc == "Brak danych":
                    return f"color: {kolor}; font-style: italic;"
                return f"color: {kolor}; font-weight: 700;"

            def stylizuj_prog(wartosc):
                if wartosc == "pełna karencja":
                    return "color: #4ade80; font-weight: 700;"
                if isinstance(wartosc, str) and wartosc.startswith("≤ "):
                    val_str = wartosc.replace("≤ ", "")
                    kolor = pobierz_kolor_kdi(val_str)
                    return f"color: {kolor}; font-weight: 700;"
                return "color: #94a3b8;"

            styler_kol = (
                df_kol.style
                .map(stylizuj_kdi_kolo, subset=["KDI Koła"])
                .map(stylizuj_prog, subset=["Próg KDI (głos)"])
            )
            st.dataframe(styler_kol, width="stretch", hide_index=True)
        else:
            st.dataframe(df_kol, width="stretch", hide_index=True)
    with tab_wykres:
        fig_kol = render_wykres_slupkowy_kdi(dane_wykres_kol, tytul_x="Wskaźnik KDI Koła")
        if fig_kol:
            st.plotly_chart(fig_kol, width="stretch", config=PLOTLY_CONFIG)
        else:
            st.caption("Brak danych KDI do wygenerowania wykresu kół.")
