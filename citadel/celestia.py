import math
from datetime import date, timedelta
import pandas as pd
from config import parse_date, DATA_ODCIECIA
from calculations import pobierz_stawke_za_miesiac, oblicz_naliczenia_gr

# =========================================================================
# DEFINICJA SKALI RATINGOWEJ CELESTIA (AAA -> DDD)
# =========================================================================

POZIOMY_CELESTIA = [
    {
        "kod": "AAA",
        "nazwa": "Prime Apex",
        "min_score": 950,
        "max_score": 1000,
        "kolor_dark": "#10b981",      # Szmaragdowy neon
        "kolor_light": "#059669",
        "opis": "Wzorcowa dyscyplina finansowa. Stała nadpłata lub regularne wpłaty z wyprzedzeniem przed każdym terminem głosowania. Zero zaległości."
    },
    {
        "kod": "AA",
        "nazwa": "High Grade",
        "min_score": 880,
        "max_score": 949,
        "kolor_dark": "#22c55e",      # Żywa zieleń
        "kolor_light": "#16a34a",
        "opis": "Bardzo wysoka wiarygodność. Składki uregulowane przed terminami głosowań. Sporadyczne, minimalne poślizgi bieżące."
    },
    {
        "kod": "A",
        "nazwa": "Upper Medium",
        "min_score": 800,
        "max_score": 879,
        "kolor_dark": "#34d399",      # Miętowy
        "kolor_light": "#0d9488",
        "opis": "Solidny płatnik. Regularnie posiada uprawnienia do głosu na zebraniach. Zazwyczaj reguluje zaległość w okienku przed samym głosowaniem."
    },
    {
        "kod": "BBB",
        "nazwa": "Good Standing",
        "min_score": 700,
        "max_score": 799,
        "kolor_dark": "#38bdf8",      # Błękit
        "kolor_light": "#0284c7",
        "opis": "Dobra wiarygodność. Spłaca zaległości przed głosowaniami, rzadziej w samym dniu zebrania. Wskaźniki w normie statutowej."
    },
    {
        "kod": "BB",
        "nazwa": "Moderate",
        "min_score": 600,
        "max_score": 699,
        "kolor_dark": "#fbbf24",      # Złoty / Amber
        "kolor_light": "#d97706",
        "opis": "Umiarkowana regularność. W niektórych głosowaniach korzysta z marginesu karencji (zadłużenie do 6 msc). Spłaty zrywami."
    },
    {
        "kod": "B",
        "nazwa": "Vulnerable",
        "min_score": 500,
        "max_score": 599,
        "kolor_dark": "#f59e0b",      # Pomarańczowy
        "kolor_light": "#b45309",
        "opis": "Wrażliwa dyscyplina. Częste balansowanie na granicy utraty prawa głosu. Wpłaty dopiero po wezwaniach lub z poślizgiem."
    },
    {
        "kod": "CCC",
        "nazwa": "Substantial Risk",
        "min_score": 380,
        "max_score": 499,
        "kolor_dark": "#f87171",      # Jasny czerwony
        "kolor_light": "#dc2626",
        "opis": "Podwyższone ryzyko. Wejścia w dni głosowań z zadłużeniem przekraczającym karencję (utrata prawa głosu). Długie okresy bierności."
    },
    {
        "kod": "CC",
        "nazwa": "Extremely Speculative",
        "min_score": 260,
        "max_score": 379,
        "kolor_dark": "#ef4444",      # Czerwień
        "kolor_light": "#b91c1c",
        "opis": "Krytyczna niespłacalność. Chroniczne ignorowanie terminów zebrań i głosowań. Rzadkie i cząstkowe spłaty."
    },
    {
        "kod": "C",
        "nazwa": "Near Default",
        "min_score": 150,
        "max_score": 259,
        "kolor_dark": "#e11d48",      # Karmin
        "kolor_light": "#9f1239",
        "opis": "Trwałe zadłużenie. Brak jakichkolwiek wpłat przed zebraniami od ponad roku. Członek bierny finansowo."
    },
    {
        "kod": "DDD",
        "nazwa": "Default",
        "min_score": 0,
        "max_score": 149,
        "kolor_dark": "#991b1b",      # Głęboki ciemny karmin
        "kolor_light": "#4c0519",
        "opis": "Całkowity default. Brak wpłat w całej historii członkostwa lub wielokrotne, wieloletnie przekroczenie okresów karencji."
    }
]

def pobierz_definicje_ratingu(score: int) -> dict:
    """Zwraca metadane ratingu dla danej liczby punktów (0-1000)."""
    s = max(0, min(1000, int(score)))
    for p in POZIOMY_CELESTIA:
        if p["min_score"] <= s <= p["max_score"]:
            return p
    return POZIOMY_CELESTIA[-1]

def pobierz_kolor_celestia(rating_kod_lub_score, is_light: bool = False) -> str:
    """Zwraca kolor heksadecymalny dla zadanego ratingu lub wyniku punktowego."""
    if isinstance(rating_kod_lub_score, (int, float)):
        def_r = pobierz_definicje_ratingu(int(rating_kod_lub_score))
        return def_r["kolor_light"] if is_light else def_r["kolor_dark"]
    
    kod = str(rating_kod_lub_score).strip().upper()
    for p in POZIOMY_CELESTIA:
        if p["kod"] == kod:
            return p["kolor_light"] if is_light else p["kolor_dark"]
    return "#64748b"

# =========================================================================
# SILNIK OBLICZENIOWY RATINGU CELESTIA
# =========================================================================

def oblicz_rating_celestia_dla_czlonka(
    czlonek_id: int,
    dane_czlonka: dict,
    terminy_glosowan_df,
    wplaty_czlonka_df,
    reczne_czlonka_df,
    korekty_czlonka_df,
    dzis: date
) -> dict:
    """
    Oblicza indywidualny rating Celestia dla danego członka koła.
    
    Główny filar (VDC): dyscyplina spłaty w okienku zapadalności wokół terminów głosowań koła.
    Pozostałe filary: KDI, bieżący stan salda, rytm wpłat.
    """
    data_wst = parse_date(dane_czlonka["data_wst"])
    data_ur = parse_date(dane_czlonka["data_ur"])
    reczny_param = dane_czlonka.get("reczny_parametr")
    saldo_start_gr = int(dane_czlonka.get("saldo_start_gr", 0))
    saldo_akt_gr = int(dane_czlonka.get("saldo_akt_gr", 0))
    kdi_val = dane_czlonka.get("kdi_val")
    stawka_biezaca_gr = 1500  # domyślny fallback
    try:
        from calculations import pobierz_parametr
        _, stawka_biezaca_gr = pobierz_parametr(data_ur, reczny_param, dzis)
    except Exception:
        pass

    # Mapy wpłat, korekt i naliczeń wg daty
    wplaty_map = {}
    if wplaty_czlonka_df is not None and not wplaty_czlonka_df.empty:
        for _, r in wplaty_czlonka_df.iterrows():
            d = parse_date(r["data_wplaty"])
            wplaty_map[d] = wplaty_map.get(d, 0) + int(r["kwota_gr"])

    reczne_map = {}
    if reczne_czlonka_df is not None and not reczne_czlonka_df.empty:
        for _, r in reczne_czlonka_df.iterrows():
            d = parse_date(r["data_naliczenia"])
            reczne_map[d] = reczne_map.get(d, 0) + int(r["kwota_gr"])

    korekty_map = {}
    if korekty_czlonka_df is not None and not korekty_czlonka_df.empty:
        for _, r in korekty_czlonka_df.iterrows():
            d = parse_date(r["data_korekty"])
            korekty_map[d] = korekty_map.get(d, 0) + int(r["delta_gr"])

    # ---------------------------------------------------------------------
    # FILAR 1: Voting Due Compliance (VDC) - Waga: 55%
    # ---------------------------------------------------------------------
    audyt_glosowan = []
    vdc_score = None
    
    glosowania_w_stazu = []
    if terminy_glosowan_df is not None and not terminy_glosowan_df.empty:
        for _, row_g in terminy_glosowan_df.iterrows():
            d_glos = parse_date(row_g["data_glosowania"])
            if d_glos >= data_wst and d_glos <= dzis:
                # Dynamiczny termin otwarcia zbiórki
                if pd.notna(row_g.get("data_zbiorki_od")):
                    d_od = parse_date(row_g["data_zbiorki_od"])
                else:
                    dni_przed = int(row_g.get("dni_zbiorki_przed") or 14)
                    d_od = d_glos - timedelta(days=dni_przed)

                # Dynamiczny ostateczny termin wymagalności
                if pd.notna(row_g.get("data_wymagalnosci_do")):
                    d_do = parse_date(row_g["data_wymagalnosci_do"])
                else:
                    dni_po = int(row_g.get("dni_wymagalnosci_po") or 0)
                    d_do = d_glos + timedelta(days=dni_po)

                glosowania_w_stazu.append({
                    "id": row_g.get("id"),
                    "data": d_glos,
                    "data_zbiorki_od": d_od,
                    "data_wymagalnosci_do": d_do,
                    "nazwa": row_g.get("nazwa", "Głosowanie Koła"),
                    "waga": float(row_g.get("waga", 1.0))
                })

    if glosowania_w_stazu:
        # Sortowanie chronologiczne
        glosowania_w_stazu = sorted(glosowania_w_stazu, key=lambda x: x["data"])
        suma_wazona_punktow = 0.0
        suma_wag = 0.0

        for g in glosowania_w_stazu:
            d_glos = g["data"]
            waga_g = g["waga"]
            okno_start = g["data_zbiorki_od"]
            termin_wymagalnosci = g["data_wymagalnosci_do"]

            # Wyznaczenie salda członka na moment terminu wymagalności
            sum_wpl_do_wym = sum(kw for d, kw in wplaty_map.items() if d <= termin_wymagalnosci)
            sum_rec_do_wym = sum(kw for d, kw in reczne_map.items() if d <= termin_wymagalnosci)
            sum_kor_do_wym = sum(kw for d, kw in korekty_map.items() if d <= termin_wymagalnosci)
            nal_auto_do_wym, _ = oblicz_naliczenia_gr(data_wst, data_ur, reczny_param, termin_wymagalnosci)
            
            saldo_na_wym_gr = saldo_start_gr + sum_wpl_do_wym + sum_kor_do_wym - (nal_auto_do_wym + sum_rec_do_wym)

            # Wpłaty w skonfigurowanym oknie zbiórki: [okno_start, termin_wymagalnosci]
            wplaty_w_oknie_gr = sum(kw for d, kw in wplaty_map.items() if okno_start <= d <= termin_wymagalnosci)

            # Wpłaty w okienku poślizgu: (termin_wymagalnosci, termin_wymagalnosci + 3 dni]
            okno_poslizgu = termin_wymagalnosci + timedelta(days=3)
            wplaty_poslizg_gr = sum(kw for d, kw in wplaty_map.items() if termin_wymagalnosci < d <= okno_poslizgu)

            # Stawka statutowa w miesiącu wymagalności
            _, stawka_g_gr = pobierz_stawke_za_miesiac(data_wst, data_ur, reczny_param, termin_wymagalnosci)
            stawka_g_gr = max(stawka_g_gr, 600)

            dni_okna = max(1, (termin_wymagalnosci - okno_start).days)

            # Ocena zdarzenia głosowania (0 - 100 pkt)
            if saldo_na_wym_gr >= 0:
                pkt_zdarzenia = 100
                if wplaty_w_oknie_gr > 0:
                    status_zdarzenia = f"🟢 Spłacono w oknie zbiórki ({dni_okna} dni) — Czyste konto"
                else:
                    status_zdarzenia = "🟢 Stała nadpłata / Czyste konto"
            else:
                miesiace_dlugu = abs(saldo_na_wym_gr) / stawka_g_gr
                if wplaty_poslizg_gr > 0:
                    pkt_zdarzenia = 60
                    status_zdarzenia = "🟡 Spłata z lekkim poślizgiem (do 3 dni po terminie)"
                elif miesiace_dlugu <= 2.0:
                    pkt_zdarzenia = 80
                    status_zdarzenia = f"🟢 Drobne zadłużenie ({miesiace_dlugu:.1f} msc) — zachowane prawo głosu"
                elif miesiace_dlugu <= 6.0:
                    pkt_zdarzenia = 35
                    status_zdarzenia = f"🟠 Na krawędzi karencji ({miesiace_dlugu:.1f} msc) — zachowane prawo głosu"
                else:
                    pkt_zdarzenia = 0
                    status_zdarzenia = f"🔴 Utrata prawa głosu (> 6 msc długu: {miesiace_dlugu:.1f} msc)"

            # Współczynnik zanikania w czasie (time-decay): ostatnie głosowania ważą najwięcej
            dni_od_glos = max(0, (dzis - d_glos).days)
            waga_czasu = math.exp(-0.0018 * dni_od_glos)
            efektywna_waga = waga_g * waga_czasu

            suma_wazona_punktow += pkt_zdarzenia * efektywna_waga
            suma_wag += efektywna_waga

            audyt_glosowan.append({
                "data_glosowania": d_glos.strftime("%Y-%m-%d"),
                "nazwa": g["nazwa"],
                "data_od": okno_start.strftime("%Y-%m-%d"),
                "data_do": termin_wymagalnosci.strftime("%Y-%m-%d"),
                "okres_zbiorki": f"{okno_start.strftime('%Y-%m-%d')} → {termin_wymagalnosci.strftime('%Y-%m-%d')} ({dni_okna} dni)",
                "data_wymagalnosci": termin_wymagalnosci.strftime("%Y-%m-%d"),
                "saldo_pln": saldo_na_wym_gr / 100.0,
                "wplata_w_oknie_pln": wplaty_w_oknie_gr / 100.0,
                "punkty": pkt_zdarzenia,
                "status": status_zdarzenia
            })

        if suma_wag > 0:
            vdc_score = int(round((suma_wazona_punktow / suma_wag) * 10))

    # ---------------------------------------------------------------------
    # FILAR 2: Wskaźnik Pokrycia Zadłużenia KDI - Waga: 20%
    # ---------------------------------------------------------------------
    if kdi_val is None:
        naliczone_gr = int(dane_czlonka.get("naliczone_gr", 0))
        kdi_score = 1000 if naliczone_gr == 0 else 50
    else:
        if kdi_val <= 0.50:
            kdi_score = 1000
        elif kdi_val <= 1.00:
            kdi_score = int(round(1000 - (kdi_val - 0.50) * 400))  # 1.00 -> 800
        elif kdi_val <= 1.20:
            kdi_score = int(round(800 - (kdi_val - 1.00) * 1000))  # 1.20 -> 600
        elif kdi_val <= 2.00:
            kdi_score = max(100, int(round(600 - (kdi_val - 1.20) * 500)))
        else:
            kdi_score = 50

    # ---------------------------------------------------------------------
    # FILAR 3: Bieżące Saldo i Karencja - Waga: 15%
    # ---------------------------------------------------------------------
    if saldo_akt_gr >= 0:
        saldo_score = 1000
    else:
        m_dlug = abs(saldo_akt_gr) / max(stawka_biezaca_gr, 1)
        if m_dlug <= 1.0:
            saldo_score = 850
        elif m_dlug <= 3.0:
            saldo_score = 600
        elif m_dlug <= 6.0:
            saldo_score = 300
        else:
            saldo_score = max(0, int(round(150 - (m_dlug - 6.0) * 25)))

    # ---------------------------------------------------------------------
    # FILAR 4: Rytm i Regularność Wpłat - Waga: 10%
    # ---------------------------------------------------------------------
    liczba_wplat = len(wplaty_map)
    staz_dni = max(1, (dzis - data_wst).days)
    
    if liczba_wplat == 0:
        rytm_score = 50 if dane_czlonka.get("naliczone_gr", 0) > 0 else 800
    else:
        srednio_dni_na_wplate = staz_dni / liczba_wplat
        if srednio_dni_na_wplate <= 45:
            rytm_score = 1000  # comiesięcznie lub częściej
        elif srednio_dni_na_wplate <= 100:
            rytm_score = 850   # kwartalnie
        elif srednio_dni_na_wplate <= 200:
            rytm_score = 650   # półrocznie
        elif srednio_dni_na_wplate <= 380:
            rytm_score = 450   # rocznie
        else:
            rytm_score = 250

        # Bonus jeśli była wpłata w ciągu ostatnich 90 dni
        ostatnia_wplata = max(wplaty_map.keys())
        if (dzis - ostatnia_wplata).days <= 90:
            rytm_score = min(1000, rytm_score + 100)

    # ---------------------------------------------------------------------
    # SYNTEZA CAŁKOWITEGO SCORE (0 - 1000)
    # ---------------------------------------------------------------------
    if vdc_score is not None:
        # Koło ma zarejestrowane głosowania w okresie stażu członka
        calkowity_score = int(round(
            0.55 * vdc_score + 
            0.20 * kdi_score + 
            0.15 * saldo_score + 
            0.10 * rytm_score
        ))
    else:
        # Fallback gdy koło nie zdefiniowało jeszcze terminów głosowań
        calkowity_score = int(round(
            0.45 * kdi_score + 
            0.35 * saldo_score + 
            0.20 * rytm_score
        ))

    calkowity_score = max(0, min(1000, calkowity_score))
    def_rating = pobierz_definicje_ratingu(calkowity_score)

    return {
        "czlonek_id": czlonek_id,
        "score": calkowity_score,
        "rating": def_rating["kod"],
        "nazwa_poziomu": def_rating["nazwa"],
        "kolor_dark": def_rating["kolor_dark"],
        "kolor_light": def_rating["kolor_light"],
        "opis_poziomu": def_rating["opis"],
        "filary": {
            "vdc_score": vdc_score,
            "kdi_score": kdi_score,
            "saldo_score": saldo_score,
            "rytm_score": rytm_score,
            "liczba_glosowan": len(glosowania_w_stazu)
        },
        "audyt_glosowan": list(reversed(audyt_glosowan))  # najnowsze u góry
    }

def przelicz_celestia_dla_calego_kola(kolo_id: int, dane_przeliczone: list, dzis: date) -> list:
    """
    Optymalnie wylicza i dołącza rating Celestia do każdego członka w dane_przeliczone.
    """
    if not dane_przeliczone:
        return []

    from database import db_query, pobierz_terminy_glosowan_kola

    czlonek_ids = [d["id"] for d in dane_przeliczone]
    terminy_df = pobierz_terminy_glosowan_kola(kolo_id)

    # Pobranie historii wpłat, korekt i naliczeń dla koła w jednym zapytaniu per tabela
    wplaty_df = db_query("""
        SELECT czlonek_id, kwota_gr, data_wplaty 
        FROM wplaty 
        WHERE czlonek_id = ANY(%s) AND data_wplaty <= %s 
        ORDER BY data_wplaty ASC
    """, (czlonek_ids, dzis))

    reczne_df = db_query("""
        SELECT czlonek_id, kwota_gr, data_naliczenia 
        FROM naliczenia_reczne 
        WHERE czlonek_id = ANY(%s) AND data_naliczenia <= %s 
        ORDER BY data_naliczenia ASC
    """, (czlonek_ids, dzis))

    korekty_df = db_query("""
        SELECT czlonek_id, delta_gr, data_korekty 
        FROM korekty 
        WHERE czlonek_id = ANY(%s) AND data_korekty <= %s 
        ORDER BY data_korekty ASC
    """, (czlonek_ids, dzis))

    # Grupowanie per czlonek_id
    wplaty_by_czl = {}
    if not wplaty_df.empty:
        for cid, group in wplaty_df.groupby("czlonek_id"):
            wplaty_by_czl[cid] = group

    reczne_by_czl = {}
    if not reczne_df.empty:
        for cid, group in reczne_df.groupby("czlonek_id"):
            reczne_by_czl[cid] = group

    korekty_by_czl = {}
    if not korekty_df.empty:
        for cid, group in korekty_df.groupby("czlonek_id"):
            korekty_by_czl[cid] = group

    wyniki_rozszerzone = []
    for d in dane_przeliczone:
        cid = d["id"]
        res_celestia = oblicz_rating_celestia_dla_czlonka(
            czlonek_id=cid,
            dane_czlonka=d,
            terminy_glosowan_df=terminy_df,
            wplaty_czlonka_df=wplaty_by_czl.get(cid),
            reczne_czlonka_df=reczne_by_czl.get(cid),
            korekty_czlonka_df=korekty_by_czl.get(cid),
            dzis=dzis
        )
        
        # Wzbogacenie słownika członka o metryki Celestia
        d_kopia = dict(d)
        d_kopia["celestia_score"] = res_celestia["score"]
        d_kopia["celestia_rating"] = res_celestia["rating"]
        d_kopia["celestia_kolor_dark"] = res_celestia["kolor_dark"]
        d_kopia["celestia_kolor_light"] = res_celestia["kolor_light"]
        d_kopia["celestia_nazwa"] = res_celestia["nazwa_poziomu"]
        d_kopia["celestia_opis"] = res_celestia["opis_poziomu"]
        d_kopia["celestia_filary"] = res_celestia["filary"]
        d_kopia["celestia_audyt_glosowan"] = res_celestia["audyt_glosowan"]
        wyniki_rozszerzone.append(d_kopia)

    return wyniki_rozszerzone

