import pandas as pd
import streamlit as st
from celestia import pobierz_kolor_celestia
from components.charts import czy_jasny_motyw
from config import pobierz_kolor_kdi


def render_tab_zbiorcza(dane_przeliczone, nazwa_aktywnego_kola):
    if not dane_przeliczone:
        st.info(f"Baza dla koła '{nazwa_aktywnego_kola}' jest pusta. Dodaj pierwszego członka.")
        return

    is_light = czy_jasny_motyw()

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
            "Próg KDI (głos)": d.get("kdi_prog_str", "—"),
            "Celestia": d.get("celestia_rating", "—"),
            "Możliwość głosowania": d["glosowanie_str"]
        }
        for d in dane_przeliczone
    ])

    def stylizuj_kdi_komorke(wartosc):
        kolor = pobierz_kolor_kdi(wartosc)
        if wartosc == "Brak danych":
            return f"color: {kolor}; font-style: italic;"
        return f"color: {kolor}; font-weight: 700;"

    def stylizuj_kdi_prog(wartosc):
        if wartosc == "pełna karencja":
            return "color: #4ade80; font-weight: 700;"
        if isinstance(wartosc, str) and wartosc.startswith("≤ "):
            val_str = wartosc.replace("≤ ", "")
            kolor = pobierz_kolor_kdi(val_str)
            return f"color: {kolor}; font-weight: 700;"
        return "color: #94a3b8;"

    def stylizuj_celestia_komorke(wartosc):
        kolor = pobierz_kolor_celestia(wartosc, is_light)
        return f"color: {kolor}; font-weight: 800;"

    def stylizuj_glosowanie(wartosc):
        if wartosc == "TAK":
            return "color: #22c55e; font-weight: 800;"
        elif wartosc == "NIE":
            return "color: #f43f5e; font-weight: 800;"
        return ""

    styler = (
        df_wyswietl.style
        .map(stylizuj_kdi_komorke, subset=["Wskaźnik KDI"])
        .map(stylizuj_kdi_prog, subset=["Próg KDI (głos)"])
        .map(stylizuj_celestia_komorke, subset=["Celestia"])
        .map(stylizuj_glosowanie, subset=["Możliwość głosowania"])
    )
    st.dataframe(styler, width="stretch", hide_index=True)

