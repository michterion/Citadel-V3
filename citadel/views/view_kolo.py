import pandas as pd
import streamlit as st

from config import pobierz_kolor_kdi, pobierz_kolor_uprawnionych
from database import db_query, db_scalar
from rbac import moze, pobierz_etykiete_roli
from calculations import przelicz_finanse_dla_kola
from components.ui import render_bento_card

from views.kolo.tab_zbiorcza import render_tab_zbiorcza
from views.kolo.tab_profile import render_tab_profile
from views.kolo.tab_wplaty import render_tab_wplaty
from views.kolo.tab_reczne import render_tab_reczne
from views.kolo.tab_kasa import render_tab_kasa
from views.kolo.tab_korekty import render_tab_korekty
from views.kolo.tab_czlonkowie import render_tab_czlonkowie
from views.kolo.tab_kalkulator import render_tab_kalkulator
from views.kolo.tab_akceptacje import render_tab_akceptacje
from views.kolo.tab_struktura import render_tab_struktura
from views.kolo.tab_audyt import render_tab_audyt
from views.kolo.tab_centauri import render_tab_centauri

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
        render_bento_card(f"KDI Koła ({nazwa_aktywnego_kola})", kdi_global_str, "Rekomendowane: ≤ 1.20", styl_custom=f"color: {kolor_kdi_global}; text-shadow: 0 0 16px {kolor_kdi_global};")
    with c4:
        uprawnieni_count = sum(1 for d in dane_przeliczone if d["moze_glosowac"])
        lacznie_czlonkow = len(dane_przeliczone)
        pct_uprawnieni = (uprawnieni_count / lacznie_czlonkow * 100.0) if lacznie_czlonkow > 0 else 0.0
        kolor_uprawnieni = pobierz_kolor_uprawnionych(pct_uprawnieni if lacznie_czlonkow > 0 else None)
        render_bento_card("Uprawnieni do Głosowania", f"{uprawnieni_count} / {lacznie_czlonkow}", f"{pct_uprawnieni:.1f}% (karencja ≤ 6 msc)", styl_custom=f"color: {kolor_uprawnieni}; text-shadow: 0 0 16px {kolor_uprawnieni};")

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
        render_tab_zbiorcza(dane_przeliczone, nazwa_aktywnego_kola)

    # 2. PROFIL I WYKRESY
    with tab_map["📈 Profile & Wykresy"]:
        render_tab_profile(dane_przeliczone, dzis)

    # 3. ZARZĄDZANIE WPŁATAMI
    with tab_map["💰 Wpłaty Członków"]:
        render_tab_wplaty(dane_przeliczone, wybrane_kolo_id, rola_uzytkownika, curr_user_id)

    # 4. RĘCZNE NALICZENIA
    if "📝 Ręczne Naliczenia" in tab_map:
        with tab_map["📝 Ręczne Naliczenia"]:
            render_tab_reczne(dane_przeliczone, wybrane_kolo_id)

    # 5. KASA KOŁA & WYDATKI
    with tab_map["💳 Kasa Koła & Wydatki"]:
        render_tab_kasa(
            wybrane_kolo_id, nazwa_aktywnego_kola,
            suma_wplat_kola_gr, faktyczna_kasa_kola_gr,
            suma_wydatkow_gr, suma_korekt_kasy_gr
        )

    # 6. KOREKTA SALDA OSOBY
    if "🛠️ Korekta Salda Osoby" in tab_map:
        with tab_map["🛠️ Korekta Salda Osoby"]:
            render_tab_korekty(dane_przeliczone, wybrane_kolo_id)

    # 7. ZARZĄDZANIE CZŁONKAMI
    with tab_map["👤 Zarządzaj Członkami"]:
        render_tab_czlonkowie(dane_przeliczone, wybrane_kolo_id, rola_uzytkownika)

    # 8. PODRĘCZNY KALKULATOR SKŁADEK I MANDATÓW
    with tab_map["🧮 Kalkulator"]:
        render_tab_kalkulator(dzis)

    # 9. WPŁATY DO ZAAKCEPTOWANIA
    klucz_akcept = next((k for k in zakladki_nazwy if "Wpłaty do zaakceptowania" in k), None)
    if klucz_akcept and klucz_akcept in tab_map:
        with tab_map[klucz_akcept]:
            render_tab_akceptacje(curr_user_id)

    # 10. ZARZĄDZANIE STRUKTURĄ
    if "🏛️ Zarządzaj Strukturą" in tab_map:
        with tab_map["🏛️ Zarządzaj Strukturą"]:
            render_tab_struktura(wybrany_kraj_id, wybrany_region_id, rola_uzytkownika)

    # 11. LOGI AUDYTOWE
    if "📜 Logi Audytowe" in tab_map:
        with tab_map["📜 Logi Audytowe"]:
            render_tab_audyt(wybrane_kolo_id)

    # 12. PANEL CENTAURI
    if "🏛️ Panel Centauri" in tab_map:
        with tab_map["🏛️ Panel Centauri"]:
            render_tab_centauri(curr_user_id, wybrany_kraj_id)