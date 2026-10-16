from datetime import date

import streamlit as st
from calculations import formatuj_wartosc_kdi, oblicz_symulacje_kalkulatora, pobierz_parametr
from components.ui import render_bento_card
from config import DATA_ODCIECIA, dzis_pl, pobierz_kolor_kdi


def render_tab_kalkulator(dzis):
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

    stawka_bezp_gr = max(stawka_biezaca_gr, 1)
    min_wpl_sim_gr = max(0, z_i_gr - 6 * stawka_bezp_gr)
    if min_wpl_sim_gr > 0:
        kdi_prog_sim_val = round(z_i_gr / min_wpl_sim_gr, 2)
        kdi_prog_sim_str = f"≤ {kdi_prog_sim_val:.2f}"
    else:
        kdi_prog_sim_val = None
        kdi_prog_sim_str = "pełna karencja"
    wartosc_sim_kdi_html = formatuj_wartosc_kdi(kdi_str, kdi_prog_sim_val, kdi_prog_sim_str)

    if saldo_koncowe_gr >= 0:
        moze_glosowac = True
        miesiace_dlugu = 0.0
        doplata_do_glosu_pln = 0.0
    else:
        miesiace_dlugu = abs(saldo_koncowe_gr) / stawka_bezp_gr
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
            render_bento_card("Wskaźnik KDI", wartosc_sim_kdi_html, "Cel statutowy: ≤ 1.20", styl_custom=f"color: {kolor_kdi}; text-shadow: 0 0 16px {kolor_kdi};")

        cb3, cb4 = st.columns(2)
        with cb3:
            kolor_glosu = "#22c55e" if moze_glosowac else "#f43f5e"
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

