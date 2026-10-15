import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import date

from config import dzis_pl, formatuj_czas_pl
from database import (
    pobierz_terminy_glosowan_kola,
    dodaj_termin_glosowania,
    usun_termin_glosowania
)
from celestia import POZIOMY_CELESTIA, pobierz_kolor_celestia
from components.ui import render_bento_card
from components.charts import PLOTLY_CONFIG, czy_jasny_motyw

def render_tab_celestia(wybrane_kolo_id: int, dane_przeliczone: list, curr_user_id: int, dzis: date):
    st.markdown("### ⭐ Panel Celestia — Rating Wypłacalności i Dni Zapadalności")
    st.caption(
        "Celestia to zaawansowany rating dyscypliny składkowej członków. Głównym wyznacznikiem wiarygodności jest "
        "wywiązywanie się ze składek w okolicy faktycznych terminów zapadalności — którymi w życiu koła są dni zebrań i głosowań."
    )

    sub_cel1, sub_cel2 = st.tabs(["🏆 Tablica Wiarygodności & Ranking", "🗳️ Rejestr Dni Głosowań (Zapadalności)"])

    # =========================================================================
    # PODZAKŁADKA 1: TABLICA WIARYGODNOŚCI I RANKING
    # =========================================================================
    with sub_cel1:
        if not dane_przeliczone:
            st.info("Brak danych członków w tym kole.")
            return

        is_light = czy_jasny_motyw()

        # Obliczenie statystyk klas wiarygodności
        ranking_posortowany = sorted(dane_przeliczone, key=lambda x: x.get("celestia_score", 0), reverse=True)
        total_czlonkow = len(ranking_posortowany)
        
        liczba_prime = sum(1 for d in ranking_posortowany if d.get("celestia_rating") in ["AAA", "AA", "A"])
        liczba_medium = sum(1 for d in ranking_posortowany if d.get("celestia_rating") in ["BBB", "BB", "B"])
        liczba_risk = sum(1 for d in ranking_posortowany if d.get("celestia_rating") in ["CCC", "CC", "C", "DDD"])
        
        sredni_score = int(round(sum(d.get("celestia_score", 0) for d in ranking_posortowany) / max(total_czlonkow, 1)))
        
        # Wyznaczenie średniego ratingu koła
        from celestia import pobierz_definicje_ratingu
        def_sredni = pobierz_definicje_ratingu(sredni_score)
        kolor_sredni = def_sredni["kolor_light"] if is_light else def_sredni["kolor_dark"]

        # 4 Bento Cards podsumowujące koło
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        with col_c1:
            render_bento_card(
                "Indeks Wiarygodności Koła",
                f"{def_sredni['kod']} ({sredni_score} pkt)",
                f"Poziom: {def_sredni['nazwa']}",
                styl_custom=f"color: {kolor_sredni}; text-shadow: 0 0 14px {kolor_sredni};"
            )
        with col_c2:
            pct_prime = (liczba_prime / total_czlonkow * 100) if total_czlonkow > 0 else 0
            render_bento_card(
                "Klasa Prime (AAA — A)",
                f"{liczba_prime} / {total_czlonkow}",
                f"{pct_prime:.1f}% członków wzorowych",
                "accent-green"
            )
        with col_c3:
            pct_med = (liczba_medium / total_czlonkow * 100) if total_czlonkow > 0 else 0
            render_bento_card(
                "Klasa Średnia (BBB — B)",
                f"{liczba_medium} / {total_czlonkow}",
                f"{pct_med:.1f}% stabilnych / umiarkowanych",
                "accent-cyan"
            )
        with col_c4:
            pct_risk = (liczba_risk / total_czlonkow * 100) if total_czlonkow > 0 else 0
            render_bento_card(
                "Zagrożeni (CCC — DDD)",
                f"{liczba_risk} / {total_czlonkow}",
                f"{pct_risk:.1f}% ryzyko utraty praw głosu",
                "accent-rose"
            )

        st.markdown("#### 📊 Rozkład Poziomów Ratingowych w Kole")
        
        # Wykres słupkowy rozkładu ratingów
        kody_kolejnosc = [p["kod"] for p in POZIOMY_CELESTIA]
        liczniki_poziomow = {k: 0 for k in kody_kolejnosc}
        for d in ranking_posortowany:
            r_kod = d.get("celestia_rating", "DDD")
            if r_kod in liczniki_poziomow:
                liczniki_poziomow[r_kod] += 1

        kolory_slupkow = [pobierz_kolor_celestia(k, is_light) for k in kody_kolejnosc]

        fig_dist = go.Figure()
        fig_dist.add_trace(go.Bar(
            x=kody_kolejnosc,
            y=[liczniki_poziomow[k] for k in kody_kolejnosc],
            marker=dict(
                color=kolory_slupkow,
                line=dict(color='rgba(255, 255, 255, 0.2)' if not is_light else 'rgba(15, 23, 42, 0.2)', width=1)
            ),
            text=[str(liczniki_poziomow[k]) if liczniki_poziomow[k] > 0 else "" for k in kody_kolejnosc],
            textposition='auto',
            hovertemplate='<b>Poziom %{x}</b><br>Liczba członków: %{y}<extra></extra>'
        ))

        fig_dist.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter, sans-serif', color='#0f172a' if is_light else '#f1f5f9'),
            margin=dict(l=20, r=20, t=25, b=25),
            height=260,
            xaxis=dict(showgrid=False, color='#64748b' if is_light else '#94a3b8'),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0, 0, 0, 0.08)' if is_light else 'rgba(255, 255, 255, 0.06)',
                color='#64748b' if is_light else '#94a3b8'
            )
        )
        st.plotly_chart(fig_dist, use_container_width=True, config=PLOTLY_CONFIG)

        # Filtrowanie i tabela rankingu
        st.markdown("#### 📋 Szczegółowy Ranking Wiarygodności Członków")
        
        opcje_filtr = ["Wszyscy", "Tylko Prime (AAA — A)", "Tylko Średnia (BBB — B)", "Tylko Zagrożeni (CCC — DDD)"]
        wybrany_filtr = st.radio("Filtruj wg klasy ratingu:", opcje_filtr, horizontal=True, label_visibility="collapsed")

        if wybrany_filtr == "Tylko Prime (AAA — A)":
            przefiltrowani = [d for d in ranking_posortowany if d.get("celestia_rating") in ["AAA", "AA", "A"]]
        elif wybrany_filtr == "Tylko Średnia (BBB — B)":
            przefiltrowani = [d for d in ranking_posortowany if d.get("celestia_rating") in ["BBB", "BB", "B"]]
        elif wybrany_filtr == "Tylko Zagrożeni (CCC — DDD)":
            przefiltrowani = [d for d in ranking_posortowany if d.get("celestia_rating") in ["CCC", "CC", "C", "DDD"]]
        else:
            przefiltrowani = ranking_posortowany

        tabela_dane = []
        for idx, d in enumerate(przefiltrowani, start=1):
            filary = d.get("celestia_filary", {})
            vdc_val = filary.get("vdc_score")
            vdc_str = f"{vdc_val} pkt" if vdc_val is not None else "Brak głosowań"

            tabela_dane.append({
                "Pozycja": idx,
                "Członek": d["imie_nazwisko"],
                "Rating Celestia": d.get("celestia_rating", "DDD"),
                "Score (0-1000)": f"{d.get('celestia_score', 0)} pkt",
                "Dyscyplina Głosowań (VDC)": vdc_str,
                "KDI": d["kdi_str"],
                "Saldo Aktualne": f"{d['saldo_akt_pln']:.2f} zł",
                "Uprawnienie do głosu": d["glosowanie_str"]
            })

        df_rank = pd.DataFrame(tabela_dane)
        
        def stylizuj_celestia_ranking(wartosc):
            kolor = pobierz_kolor_celestia(wartosc, is_light)
            return f"color: {kolor}; font-weight: 800; font-size: 1.05rem;"

        def stylizuj_glos_ranking(wartosc):
            if wartosc == "TAK":
                return "color: #22c55e; font-weight: 800;"
            elif wartosc == "NIE":
                return "color: #f43f5e; font-weight: 800;"
            return ""

        styler_rank = df_rank.style.map(
            stylizuj_celestia_ranking, subset=["Rating Celestia"]
        ).map(
            stylizuj_glos_ranking, subset=["Uprawnienie do głosu"]
        )

        st.dataframe(styler_rank, width="stretch", hide_index=True)

    # =========================================================================
    # PODZAKŁADKA 2: REJESTR DNI GŁOSOWAŃ (WYMAGALNOŚCI)
    # =========================================================================
    with sub_cel2:
        st.markdown("#### 🗳️ Rejestr Dni Głosowań (Terminów Zapadalności Koła)")
        st.caption(
            "Wprowadź daty walnych zebrań, zjazdów lub głosowań uchwał w tym kole. Każdy wpis staje się oficjalnym "
            "punktem zapadalności dla algorytmu Celestia, badając czy składki zostały uregulowane w okienku przed zebraniem."
        )

        # Formularz dodawania nowego terminu głosowania
        with st.form("form_dodaj_glosowanie", clear_on_submit=True):
            col_g1, col_g2, col_g3 = st.columns([2, 3, 2])
            with col_g1:
                nowa_data = st.date_input("Data Głosowania / Zebrania:", value=dzis_pl())
            with col_g2:
                nowa_nazwa = st.text_input("Nazwa / Okazja:", placeholder="np. Walne Zebranie Członków, Wybory Zarządu Koła")
            with col_g3:
                nowa_waga_wybor = st.selectbox(
                    "Ranga wydarzenia:",
                    options=["Zwyczajne (waga 1.0)", "Kluczowe / Wybory Władz (waga 1.5)"]
                )
                waga_num = 1.5 if "1.5" in nowa_waga_wybor else 1.0

            nowy_opis = st.text_input("Opcjonalny opis / uwagi:", placeholder="np. Wymóg braku zadłużenia na dzień otwarcia obrad")

            btn_dodaj = st.form_submit_button("➕ Zarejestruj Termin Głosowania", use_container_width=True)
            if btn_dodaj:
                if not nowa_nazwa.strip():
                    st.error("Wprowadź nazwę wydarzenia!")
                else:
                    dodaj_termin_glosowania(
                        kolo_id=wybrane_kolo_id,
                        data_glosowania=nowa_data,
                        nazwa=nowa_nazwa,
                        opis=nowy_opis,
                        waga=waga_num,
                        user_id=curr_user_id
                    )
                    st.success(f"Pomyślnie zarejestrowano termin głosowania: '{nowa_nazwa}' ({nowa_data}).")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 📅 Zarejestrowane Terminy Głosowań w Kole")

        terminy_df = pobierz_terminy_glosowan_kola(wybrane_kolo_id)
        if terminy_df.empty:
            st.info(
                "Koło nie ma jeszcze zarejestrowanych terminów głosowań. "
                "Użyj powyższego formularza, aby dodać pierwsze zebranie i aktywować pełne wagi zapadalności w Celestii!"
            )
        else:
            # Prezentacja tabeli terminów z opcją usuwania
            tablica_terminow = []
            for _, r in terminy_df.iterrows():
                tablica_terminow.append({
                    "ID": r["id"],
                    "Data Głosowania": str(r["data_glosowania"]),
                    "Nazwa Wydarzenia": r["nazwa"],
                    "Ranga / Waga": f"{float(r['waga']):.1f}x",
                    "Opis": r["opis"] or "—",
                    "Zarejestrował": r["dodal_imie"] or "System",
                    "Data Wpisu": formatuj_czas_pl(r["utworzono_o"])
                })

            df_t = pd.DataFrame(tablica_terminow)
            st.dataframe(df_t[["Data Głosowania", "Nazwa Wydarzenia", "Ranga / Waga", "Opis", "Zarejestrował", "Data Wpisu"]], width="stretch", hide_index=True)

            # Sekcja usuwania wpisu
            st.markdown("##### 🗑️ Usuwanie terminu głosowania")
            c_del1, c_del2 = st.columns([3, 1])
            with c_del1:
                opcje_usun = {r["id"]: f"{r['data_glosowania']} — {r['nazwa']}" for _, r in terminy_df.iterrows()}
                wybrany_do_usun = st.selectbox(
                    "Wybierz termin do usunięcia:",
                    options=list(opcje_usun.keys()),
                    format_func=lambda x: opcje_usun[x],
                    label_visibility="collapsed"
                )
            with c_del2:
                if st.button("Usuń wybrany termin", type="secondary", use_container_width=True):
                    usun_termin_glosowania(wybrany_do_usun, wybrane_kolo_id)
                    st.success("Usunięto wybrany termin głosowania. Przeliczono ratingi.")
                    st.rerun()

