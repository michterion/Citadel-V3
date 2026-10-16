import math
from datetime import date, timedelta

import pandas as pd
from calculations import oblicz_naliczenia_gr, pobierz_parametr, pobierz_stawke_za_miesiac
from config import parse_date


def _num(v, d):
    """Bezpieczne pobieranie wartości liczbowej z pandas / SQL (odporne na None i NaN)."""
    return d if v is None or pd.isna(v) else v

# =========================================================================
# DEFINICJA SKALI RATINGOWEJ CELESTIA (AAA -> DDD)
# =========================================================================
# DEFINICJA SKALI RATINGOWEJ CELESTIA (AAA -> DDD) W OPARCIU O SKALĘ KDI
# =========================================================================

# Progi interpolacji barw oparte na kanonicznej skali KDI (Emerald -> Light Green -> White -> Yellow -> Orange -> Red -> Pink -> Blue -> Purple)
KDI_CELESTIA_STOPS_DARK = [
    (1000.0, (22, 130, 60)),   # Szmaragd
    (900.0,  (74, 222, 128)),  # Jasna zieleń
    (800.0,  (255, 255, 255)), # Biel
    (700.0,  (250, 204, 21)),  # Żółty
    (550.0,  (249, 115, 22)),  # Pomarańczowy
    (400.0,  (239, 68, 68)),   # Czerwony
    (250.0,  (236, 72, 153)),  # Różowy
    (100.0,  (59, 130, 246)),  # Niebieski
    (0.0,    (168, 85, 247)),  # Fioletowy
]

KDI_CELESTIA_STOPS_LIGHT = [
    (1000.0, (21, 128, 61)),   # Głęboki szmaragd
    (900.0,  (22, 163, 74)),   # Zieleń
    (800.0,  (30, 41, 59)),    # Ciemny grafit (kontrast na jasnym tle)
    (700.0,  (202, 138, 4)),   # Ciemne złoto
    (550.0,  (194, 65, 12)),   # Ciemny pomarańcz
    (400.0,  (185, 28, 28)),   # Ciemna czerwień
    (250.0,  (190, 24, 93)),   # Ciemny róż
    (100.0,  (29, 78, 216)),   # Ciemny błękit
    (0.0,    (126, 34, 206)),  # Ciemny fiolet
]


def interpoluj_kolor_skali_kdi(val: float, is_light: bool = False) -> str:
    """Liniowa interpolacja koloru w kanonicznej skali KDI (od 0 do 1000 pkt)."""
    stops = KDI_CELESTIA_STOPS_LIGHT if is_light else KDI_CELESTIA_STOPS_DARK
    val = max(0.0, min(1000.0, float(val)))
    if val >= stops[0][0]:
        r, g, b = stops[0][1]
        return f"#{r:02x}{g:02x}{b:02x}"
    if val <= stops[-1][0]:
        r, g, b = stops[-1][1]
        return f"#{r:02x}{g:02x}{b:02x}"

    for i in range(len(stops) - 1):
        v1, c1 = stops[i]
        v2, c2 = stops[i + 1]
        if v2 <= val <= v1:
            t = (val - v2) / (v1 - v2)
            r = int(c2[0] + t * (c1[0] - c2[0]))
            g = int(c2[1] + t * (c1[1] - c2[1]))
            b = int(c2[2] + t * (c1[2] - c2[2]))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#000000" if is_light else "#ffffff"


POZIOMY_CELESTIA = [
    {
        "kod": "AAA",
        "nazwa": "Prime Apex",
        "min_score": 950,
        "max_score": 1000,
        "kolor_dark": "#23994d",      # Głęboki szmaragd KDI
        "kolor_light": "#158840",
        "opis": "Wzorcowa dyscyplina finansowa. Stała nadpłata lub regularne wpłaty z wyprzedzeniem przed każdym terminem głosowania. Zero zaległości."
    },
    {
        "kod": "AA",
        "nazwa": "High Grade",
        "min_score": 880,
        "max_score": 949,
        "kolor_dark": "#42d075",      # Żywa zieleń KDI
        "kolor_light": "#159d48",
        "opis": "Bardzo wysoka wiarygodność. Składki uregulowane przed terminami głosowań. Sporadyczne, minimalne poślizgi bieżące."
    },
    {
        "kod": "A",
        "nazwa": "Upper Medium",
        "min_score": 800,
        "max_score": 879,
        "kolor_dark": "#b6f1cc",      # Miętowa biel / srebrzysty KDI
        "kolor_light": "#1a5941",
        "opis": "Solidny płatnik. Regularnie posiada uprawnienia do głosu na zebraniach. Zazwyczaj reguluje zaległość w okienku przed samym głosowaniem."
    },
    {
        "kod": "BBB",
        "nazwa": "Good Standing",
        "min_score": 700,
        "max_score": 799,
        "kolor_dark": "#fce58a",      # Pastelowy żółty KDI
        "kolor_light": "#74591f",
        "opis": "Dobra wiarygodność. Spłaca zaległości przed głosowaniami, rzadziej w samym dniu zebrania. Wskaźniki w normie statutowej."
    },
    {
        "kod": "BB",
        "nazwa": "Moderate",
        "min_score": 600,
        "max_score": 699,
        "kolor_dark": "#f9ae15",      # Złocisty bursztyn KDI
        "kolor_light": "#c77106",
        "opis": "Umiarkowana regularność. W niektórych głosowaniach korzysta z marginesu karencji (zadłużenie do 6 msc). Spłaty zrywami."
    },
    {
        "kod": "B",
        "nazwa": "Vulnerable",
        "min_score": 500,
        "max_score": 599,
        "kolor_dark": "#f97316",      # Pomarańczowy KDI
        "kolor_light": "#c2410c",
        "opis": "Wrażliwa dyscyplina. Częste balansowanie na granicy utraty prawa głosu. Wpłaty dopiero po wezwaniach lub z poślizgiem."
    },
    {
        "kod": "CCC",
        "nazwa": "Substantial Risk",
        "min_score": 380,
        "max_score": 499,
        "kolor_dark": "#f15037",      # Koralowy czerwony KDI
        "kolor_light": "#bb2517",
        "opis": "Podwyższone ryzyko. Wejścia w dni głosowań z zadłużeniem przekraczającym karencję (utrata prawa głosu). Długie okresy bierności."
    },
    {
        "kod": "CC",
        "nazwa": "Extremely Speculative",
        "min_score": 260,
        "max_score": 379,
        "kolor_dark": "#ed4671",      # Ciemny róż KDI
        "kolor_light": "#bb193e",
        "opis": "Krytyczna niespłacalność. Chroniczne ignorowanie terminów zebrań i głosowań. Rzadkie i cząstkowe spłaty."
    },
    {
        "kod": "C",
        "nazwa": "Near Default",
        "min_score": 150,
        "max_score": 259,
        "kolor_dark": "#b15bb8",      # Purpurowy róż / Magenta KDI
        "kolor_light": "#882a86",
        "opis": "Zadłużenie roczne (ok. 8–12 msc długu, ~60–100 zł). Świeża lub utrwalona utrata praw głosu na zebraniach."
    },
    {
        "kod": "D",
        "nazwa": "Insolvency Grade 1",
        "min_score": 90,
        "max_score": 149,
        "kolor_dark": "#527ae9",      # Niebieski KDI
        "kolor_light": "#3246c7",
        "opis": "Głęboka niewypłacalność (ok. 12–18 msc długu, ~100–160 zł). Brak wpłat na zebrania od ponad roku."
    },
    {
        "kod": "DD",
        "nazwa": "Insolvency Grade 2",
        "min_score": 40,
        "max_score": 89,
        "kolor_dark": "#6172f6",      # Błękitno-fioletowy / Indygo KDI
        "kolor_light": "#3e3ed4",
        "opis": "Wieloletnia niewypłacalność (ok. 18–26 msc długu, ~160–250 zł). Utrwalony, dwuletni brak wpłat i kontaktu."
    },
    {
        "kod": "DDD",
        "nazwa": "Terminal Default",
        "min_score": 0,
        "max_score": 39,
        "kolor_dark": "#925ef6",      # Głęboki fiolet KDI
        "kolor_light": "#6a2ad0",
        "opis": "Całkowity default (> 28–36 msc długu, > 350–450 zł). Członek całkowicie nieaktywny, zero wpłat w historii."
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
    """Zwraca kolor heksadecymalny w skali KDI dla zadanego ratingu lub wyniku punktowego (0-1000)."""
    if rating_kod_lub_score is None:
        return "#64748b"

    if isinstance(rating_kod_lub_score, (int, float)):
        return interpoluj_kolor_skali_kdi(rating_kod_lub_score, is_light)

    tekst = str(rating_kod_lub_score).strip()
    tekst_czysty = tekst.replace(" pkt", "").replace("pkt", "").strip()
    try:
        val = float(tekst_czysty)
        return interpoluj_kolor_skali_kdi(val, is_light)
    except ValueError:
        pass

    kod = tekst.upper()
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
    # Zabezpieczenie przed błędną datą wstąpienia z przyszłości:
    # Aktywny członek koła ewaluowany na dzień dzis ma efektywny staż co najmniej od dnia dzisiejszego.
    efektywna_data_wst = min(data_wst, dzis)
    data_ur = parse_date(dane_czlonka["data_ur"])
    reczny_param = dane_czlonka.get("reczny_parametr")
    saldo_start_gr = int(dane_czlonka.get("saldo_start_gr", 0))
    saldo_akt_gr = int(dane_czlonka.get("saldo_akt_gr", 0))
    kdi_val = dane_czlonka.get("kdi_val")
    _, stawka_biezaca_gr = pobierz_parametr(data_ur, reczny_param, dzis)
    stawka_biezaca_gr = max(stawka_biezaca_gr, 600)

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
    # FILAR 1: Voting Due Compliance (VDC) - Waga: 65%
    # ---------------------------------------------------------------------
    audyt_glosowan = []
    vdc_score = None

    glosowania_w_stazu = []
    terminy_kwartalne_w_stazu = []
    if terminy_glosowan_df is not None and not terminy_glosowan_df.empty:
        for _, row_g in terminy_glosowan_df.iterrows():
            typ_terminu = str(row_g.get("typ_terminu") or "GLOSOWANIE").upper().strip()
            d_termin = parse_date(row_g["data_glosowania"])

            # Dynamiczny termin otwarcia zbiórki
            if pd.notna(row_g.get("data_zbiorki_od")):
                d_od = parse_date(row_g["data_zbiorki_od"])
            else:
                dni_przed = int(_num(row_g.get("dni_zbiorki_przed"), 14))
                d_od = d_termin - timedelta(days=dni_przed)

            # Dynamiczny termin poślizgu (maksymalnie 3 dni po zebraniu / terminie)
            dni_po = min(3, max(0, int(_num(row_g.get("dni_wymagalnosci_po"), 0))))
            d_do = d_termin + timedelta(days=dni_po)

            # Uwzględniamy terminy:
            # 1. Członek wstąpił przed lub w dniu terminu (d_termin >= efektywna_data_wst)
            # 2. Termin już się odbył LUB okno zbiórki jest już otwarte (d_od <= dzis) LUB termin odbędzie się w ciągu 30 dni
            if d_termin >= efektywna_data_wst and (d_termin <= dzis or d_od <= dzis or d_termin <= dzis + timedelta(days=30)):
                obiekt_t = {
                    "id": row_g.get("id"),
                    "data": d_termin,
                    "data_zbiorki_od": d_od,
                    "data_wymagalnosci_do": d_do,
                    "dni_wymagalnosci_po": dni_po,
                    "nazwa": row_g.get("nazwa", "Głosowanie Koła" if typ_terminu == "GLOSOWANIE" else "Zbiórka Kwartalna"),
                    "waga": float(_num(row_g.get("waga"), 1.0)),
                    "typ_terminu": typ_terminu
                }
                if typ_terminu == "KWARTALNY":
                    terminy_kwartalne_w_stazu.append(obiekt_t)
                else:
                    glosowania_w_stazu.append(obiekt_t)

    if glosowania_w_stazu:
        # Sortowanie chronologiczne
        glosowania_w_stazu = sorted(glosowania_w_stazu, key=lambda x: x["data"])
        suma_wazona_punktow = 0.0
        suma_wag = 0.0

        for g in glosowania_w_stazu:
            d_glos = g["data"]
            waga_g = g["waga"]
            okno_start = g["data_zbiorki_od"]
            dni_poslizgu = min(3, max(0, int(g.get("dni_wymagalnosci_po", 0))))

            # 1. Termin wymagalności składek na zebranie to DZIEŃ ZEBRANIA / GŁOSOWANIA (d_glos)
            sum_wpl_do_glos = sum(kw for d, kw in wplaty_map.items() if d <= d_glos)
            sum_rec_do_glos = sum(kw for d, kw in reczne_map.items() if d <= d_glos)
            sum_kor_do_glos = sum(kw for d, kw in korekty_map.items() if d <= d_glos)
            nal_auto_do_glos, _ = oblicz_naliczenia_gr(efektywna_data_wst, data_ur, reczny_param, d_glos)

            saldo_na_glos_gr = saldo_start_gr + sum_wpl_do_glos + sum_kor_do_glos - (nal_auto_do_glos + sum_rec_do_glos)

            # 2. Wpłaty w skonfigurowanym oknie zbiórki przed zebraniem: [okno_start, d_glos]
            wplaty_w_oknie_gr = sum(kw for d, kw in wplaty_map.items() if okno_start <= d <= d_glos)

            # 3. Wpłaty w okienku poślizgu: wyłącznie po dniu zebrania, MAKSYMALNIE DO 3 DNI po głosowaniu!
            if dni_poslizgu > 0:
                okno_poslizgu = d_glos + timedelta(days=dni_poslizgu)
                wplaty_poslizg_gr = sum(kw for d, kw in wplaty_map.items() if d_glos < d <= okno_poslizgu)
            else:
                wplaty_poslizg_gr = 0

            # Stawka statutowa w miesiącu zebrania
            _, stawka_g_gr = pobierz_stawke_za_miesiac(efektywna_data_wst, data_ur, reczny_param, d_glos)
            stawka_g_gr = max(stawka_g_gr, 600)

            dni_okna = max(1, (d_glos - okno_start).days)

            # Ocena zdarzenia głosowania (0 - 100 pkt)
            saldo_po_poslizgu_gr = saldo_na_glos_gr + wplaty_poslizg_gr
            pokryto_po_poslizgu = (wplaty_poslizg_gr > 0 and saldo_po_poslizgu_gr >= 0)

            if saldo_na_glos_gr >= 0:
                # Weryfikacja czy członek miał stałą nadpłatę, czy musiał dokonać wpłaty w oknie
                saldo_przed_oknem_gr = saldo_na_glos_gr - wplaty_w_oknie_gr
                if saldo_przed_oknem_gr >= 0:
                    pkt_zdarzenia = 100.0
                    status_zdarzenia = "🟢 Stała nadpłata / Pokrycie przed zbiórką — wzorowa terminowość (1000 pkt)"
                else:
                    # Członek pokrył zadłużenie wpłatą w oknie zbiórki [okno_start, d_glos]
                    wplaty_w_oknie = [(d, kw) for d, kw in wplaty_map.items() if okno_start <= d <= d_glos]
                    wplaty_posortowane = sorted(wplaty_w_oknie, key=lambda x: x[0])
                    data_efekt = wplaty_posortowane[-1][0] if wplaty_posortowane else d_glos

                    dni_od_startu = max(0, (data_efekt - okno_start).days)
                    progress = min(1.0, max(0.0, dni_od_startu / dni_okna))

                    # Dynamiczna skala terminowości w oknie zbiórki:
                    # Pierwsze 50% czasu nie obniża wyniku (1000 pkt / 100.0).
                    # W drugiej połowie skala liniowo spada do 600 pkt (60.0) w dniu głosowania.
                    if progress <= 0.50:
                        pkt_zdarzenia = 100.0
                        dni_przed = (d_glos - data_efekt).days
                        status_zdarzenia = f"🟢 Wpłata w I połowie okna zbiórki ({dni_przed} dni przed zebraniem) — 1000 pkt"
                    else:
                        pkt_zdarzenia = round(100.0 - ((progress - 0.50) / 0.50) * 40.0, 1)
                        dni_przed = (d_glos - data_efekt).days
                        pkt_tys = int(round(pkt_zdarzenia * 10))
                        if dni_przed == 0:
                            status_zdarzenia = f"🟡 Wpłata w dniu głosowania (ostatni dzień zbiórki) — {pkt_tys} pkt"
                        else:
                            status_zdarzenia = f"🟢 Wpłata w II połowie okna zbiórki ({dni_przed} dni przed zebraniem) — {pkt_tys} pkt"
            else:
                miesiace_dlugu = abs(saldo_na_glos_gr) / stawka_g_gr

                # 1. Skrajny default (> 28 msc długu, ~400+ zł)
                if miesiace_dlugu > 28.0:
                    if pokryto_po_poslizgu:
                        pkt_zdarzenia = 5.0
                        status_zdarzenia = f"🟡 Spłata ratunkowa skrajnego długu po terminie ({miesiace_dlugu:.1f} msc) — brak prawa głosu w dniu zebrania"
                    else:
                        pkt_zdarzenia = 0.0
                        if dzis <= d_glos:
                            status_zdarzenia = f"🔴 Brak prawa głosu na zebraniu — skrajny default (> 28 msc: {miesiace_dlugu:.1f} msc)"
                        else:
                            status_zdarzenia = f"🔴 Utrata prawa głosu — skrajny default (> 28 msc: {miesiace_dlugu:.1f} msc)"

                # 2. Głęboka niewypłacalność (18 - 28 msc długu, ~250-350 zł)
                elif miesiace_dlugu > 18.0:
                    if pokryto_po_poslizgu:
                        pkt_zdarzenia = 10.0
                        status_zdarzenia = f"🟡 Spłata ratunkowa wieloletniego długu po terminie ({miesiace_dlugu:.1f} msc) — brak prawa głosu w dniu zebrania"
                    else:
                        pkt_zdarzenia = 3.0
                        if dzis <= d_glos:
                            status_zdarzenia = f"🔴 Brak prawa głosu na zebraniu — wieloletnie zadłużenie ({miesiace_dlugu:.1f} msc)"
                        else:
                            status_zdarzenia = f"🔴 Utrata prawa głosu — wieloletnie zadłużenie ({miesiace_dlugu:.1f} msc)"

                # 3. Dług ponadroczny (12 - 18 msc długu, ~180-250 zł)
                elif miesiace_dlugu > 12.0:
                    if pokryto_po_poslizgu:
                        pkt_zdarzenia = 18.0
                        status_zdarzenia = f"🟡 Spłata ratunkowa długu ponadrocznego po terminie ({miesiace_dlugu:.1f} msc) — brak prawa głosu w dniu zebrania"
                    else:
                        pkt_zdarzenia = 6.0
                        if dzis <= d_glos:
                            status_zdarzenia = f"🔴 Brak prawa głosu na zebraniu — zadłużenie ponadroczne ({miesiace_dlugu:.1f} msc)"
                        else:
                            status_zdarzenia = f"🔴 Utrata prawa głosu — zadłużenie ponadroczne ({miesiace_dlugu:.1f} msc)"

                # 4. Utrwalone zadłużenie (8 - 12 msc długu — do 1 roku)
                elif miesiace_dlugu > 8.0:
                    if pokryto_po_poslizgu:
                        pkt_zdarzenia = 25.0
                        status_zdarzenia = f"🟡 Spłata ratunkowa utrwalonego długu po terminie ({miesiace_dlugu:.1f} msc) — brak prawa głosu w dniu zebrania"
                    else:
                        pkt_zdarzenia = 12.0
                        if dzis <= d_glos:
                            status_zdarzenia = f"🔴 Brak prawa głosu na zebraniu — utrwalone zadłużenie ({miesiace_dlugu:.1f} msc)"
                        else:
                            status_zdarzenia = f"🔴 Utrata prawa głosu — utrwalone zadłużenie ({miesiace_dlugu:.1f} msc)"

                # 5. Świeże przekroczenie karencji (6 - 8 msc długu — utrata prawa głosu od niedawna)
                elif miesiace_dlugu > 6.0:
                    if pokryto_po_poslizgu:
                        pkt_zdarzenia = 30.0
                        status_zdarzenia = f"🟡 Spłata ratunkowa po terminie ({miesiace_dlugu:.1f} msc) — brak prawa głosu w dniu zebrania"
                    else:
                        pkt_zdarzenia = 18.0
                        if dzis <= d_glos:
                            status_zdarzenia = f"🔴 Brak prawa głosu na zebraniu — świeże przekroczenie karencji ({miesiace_dlugu:.1f} msc)"
                        else:
                            status_zdarzenia = f"🔴 Utrata prawa głosu — świeże przekroczenie karencji ({miesiace_dlugu:.1f} msc)"

                # 6. Na krawędzi karencji (2 - 6 msc długu — zachowane prawo głosu na zebraniu)
                elif miesiace_dlugu > 2.0:
                    if pokryto_po_poslizgu:
                        pkt_zdarzenia = 45.0
                        status_zdarzenia = f"🟡 Pełna spłata zaległości w poślizgu (+{dni_poslizgu} dni) — zachowane prawo głosu (450 pkt)"
                    else:
                        pkt_zdarzenia = 28.0
                        status_zdarzenia = f"🟠 Na krawędzi karencji ({miesiace_dlugu:.1f} msc) — zachowane prawo głosu (280 pkt)"

                # 7. Drobne zadłużenie (<= 2 msc długu — pełne prawo głosu)
                else:
                    if pokryto_po_poslizgu:
                        pkt_zdarzenia = 50.0
                        status_zdarzenia = f"🟢 Drobne zadłużenie spłacone w poślizgu ({dni_poslizgu} dni) — 500 pkt"
                    else:
                        pkt_zdarzenia = 40.0
                        status_zdarzenia = f"🟢 Drobne zadłużenie ({miesiace_dlugu:.1f} msc) — zachowane prawo głosu (400 pkt)"

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
                "data_do": d_glos.strftime("%Y-%m-%d"),
                "okres_zbiorki": f"{okno_start.strftime('%Y-%m-%d')} → {d_glos.strftime('%Y-%m-%d')} ({dni_okna} dni)",
                "data_wymagalnosci": d_glos.strftime("%Y-%m-%d"),
                "saldo_pln": saldo_na_glos_gr / 100.0,
                "wplata_w_oknie_pln": wplaty_w_oknie_gr / 100.0,
                "punkty": pkt_zdarzenia,
                "status": status_zdarzenia
            })

        if suma_wag > 0:
            vdc_score = int(round((suma_wazona_punktow / suma_wag) * 10))

    # ---------------------------------------------------------------------
    # FILAR 2: Wskaźnik Pokrycia Zadłużenia KDI - Waga: 10%
    # ---------------------------------------------------------------------
    if kdi_val is None:
        naliczone_gr = int(dane_czlonka.get("naliczone_gr", 0))
        kdi_score = 1000 if (naliczone_gr == 0 and saldo_akt_gr >= 0) else 50
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
    # FILAR 3: Bieżące Saldo i Karencja - Waga: 20%
    # ---------------------------------------------------------------------
    # ---------------------------------------------------------------------
    # FILAR 3: Bieżące Saldo i Karencja - Waga: 20%
    # ---------------------------------------------------------------------
    if saldo_akt_gr > 0:
        saldo_score = 1000  # Faktyczna nadpłata (składki opłacone w przód)
    elif saldo_akt_gr == 0:
        saldo_score = 900   # Czyste konto (brak długu, ale brak nadpłaty)
    else:
        m_dlug = abs(saldo_akt_gr) / max(stawka_biezaca_gr, 1)
        if m_dlug <= 1.0:
            saldo_score = 800
        elif m_dlug <= 3.0:
            saldo_score = 550
        elif m_dlug <= 6.0:
            saldo_score = 250
        else:
            # Liniowe wygaszanie od 6 do 36 miesięcy (twarde zero dopiero po 36 msc długu)
            saldo_score = max(0, int(round(250 - (m_dlug - 6.0) * (250 / 30.0))))

    # ---------------------------------------------------------------------
    # FILAR 4: Rytm i Regularność Wpłat - Waga: 5% (Model Zbiórek Kwartalnych)
    # ---------------------------------------------------------------------
    liczba_wplat = len(wplaty_map)
    staz_dni = max(1, (dzis - efektywna_data_wst).days)
    audyt_kwartalny = []

    # 1. Bazowa kadencja wpłat: model oparty na zbieraniu kwartalnym
    # W kole zbieramy składki kwartalnie, więc płacenie kwartalne (średnio ≤ 105 dni) daje pełne 1000 pkt.
    if liczba_wplat == 0:
        # Brak wpłat w historii: brak wypracowanego rytmu płatniczego (nie przyznajemy 1000 pkt za brak danych/brak wpłat)
        kadencja_score = 50
        srednio_dni_na_wplate = None
    else:
        srednio_dni_na_wplate = staz_dni / liczba_wplat
        if srednio_dni_na_wplate <= 105:
            kadencja_score = 1000  # kwartalnie lub częściej (wzorzec statutowy)
        elif srednio_dni_na_wplate <= 200:
            kadencja_score = 800   # półrocznie
        elif srednio_dni_na_wplate <= 380:
            kadencja_score = 600   # rocznie
        else:
            kadencja_score = 350   # rzadziej niż rocznie

        # Bonus za świeżą wpłatę w bieżącym okresie kwartalnym (ostatnie 105 dni)
        ostatnia_wplata = max(wplaty_map.keys())
        if (dzis - ostatnia_wplata).days <= 105:
            kadencja_score = min(1000, kadencja_score + 100)

    # 2. Dedykowana ocena wyznaczonych zbiórek kwartalnych (jeśli koło je zarejestrowało)
    if terminy_kwartalne_w_stazu:
        terminy_kwartalne_w_stazu = sorted(terminy_kwartalne_w_stazu, key=lambda x: x["data"])
        suma_wazona_kw = 0.0
        suma_wag_kw = 0.0

        for q in terminy_kwartalne_w_stazu:
            d_q = q["data"]
            waga_q = q["waga"]
            okno_start = q["data_zbiorki_od"]
            dni_poslizgu = min(3, max(0, int(q.get("dni_wymagalnosci_po", 0))))

            sum_wpl_do_q = sum(kw for d, kw in wplaty_map.items() if d <= d_q)
            sum_rec_do_q = sum(kw for d, kw in reczne_map.items() if d <= d_q)
            sum_kor_do_q = sum(kw for d, kw in korekty_map.items() if d <= d_q)
            nal_auto_do_q, _ = oblicz_naliczenia_gr(efektywna_data_wst, data_ur, reczny_param, d_q)
            saldo_na_q_gr = saldo_start_gr + sum_wpl_do_q + sum_kor_do_q - (nal_auto_do_q + sum_rec_do_q)

            wplaty_w_oknie_gr = sum(kw for d, kw in wplaty_map.items() if okno_start <= d <= d_q)
            if dni_poslizgu > 0:
                okno_poslizgu = d_q + timedelta(days=dni_poslizgu)
                wplaty_poslizg_gr = sum(kw for d, kw in wplaty_map.items() if d_q < d <= okno_poslizgu)
            else:
                wplaty_poslizg_gr = 0

            saldo_po_poslizgu_gr = saldo_na_q_gr + wplaty_poslizg_gr
            _, stawka_q_gr = pobierz_stawke_za_miesiac(efektywna_data_wst, data_ur, reczny_param, d_q)
            stawka_q_gr = max(stawka_q_gr, 600)

            dni_okna_q = max(1, (d_q - okno_start).days)
            if saldo_na_q_gr >= 0:
                saldo_przed_oknem_q = saldo_na_q_gr - wplaty_w_oknie_gr
                if saldo_przed_oknem_q >= 0:
                    pkt_q = 100.0
                    status_q = "Stała nadpłata przed zbiórką (brak długu) — 1000 pkt"
                else:
                    wplaty_w_oknie_q = [(d, kw) for d, kw in wplaty_map.items() if okno_start <= d <= d_q]
                    wplaty_posortowane_q = sorted(wplaty_w_oknie_q, key=lambda x: x[0])
                    data_efekt_q = wplaty_posortowane_q[-1][0] if wplaty_posortowane_q else d_q

                    dni_od_start_q = max(0, (data_efekt_q - okno_start).days)
                    prog_q = min(1.0, max(0.0, dni_od_start_q / dni_okna_q))

                    if prog_q <= 0.50:
                        pkt_q = 100.0
                        dni_przed_q = (d_q - data_efekt_q).days
                        status_q = f"Wpłata w I połowie okna ({dni_przed_q} dni przed terminem) — 1000 pkt"
                    else:
                        pkt_q = round(100.0 - ((prog_q - 0.50) / 0.50) * 40.0, 1)
                        dni_przed_q = (d_q - data_efekt_q).days
                        pkt_q_tys = int(round(pkt_q * 10))
                        if dni_przed_q == 0:
                            status_q = f"Wpłata w dniu zbiórki (ostatni dzień) — {pkt_q_tys} pkt"
                        else:
                            status_q = f"Wpłata w II połowie okna ({dni_przed_q} dni przed terminem) — {pkt_q_tys} pkt"
            elif wplaty_poslizg_gr > 0 and saldo_po_poslizgu_gr >= 0:
                pkt_q = 50.0
                status_q = f"Opłacono w poślizgu (+{dni_poslizgu} dni) — 500 pkt"
            elif wplaty_w_oknie_gr > 0:
                pkt_q = 35.0
                status_q = "Częściowa wpłata w oknie zbiórki"
            else:
                m_dlugu_q = abs(saldo_na_q_gr) / max(stawka_q_gr, 1)
                if m_dlugu_q <= 1.0:
                    pkt_q = 25.0
                    status_q = "Niewielkie opóźnienie (≤ 1 msc długu)"
                elif m_dlugu_q <= 3.0:
                    pkt_q = 15.0
                    status_q = "Zaległość kwartalna (1–3 msc długu)"
                else:
                    pkt_q = 5.0
                    status_q = "Brak wpłaty na zbiórkę kwartalną (> 3 msc długu)"

            dni_od_q = max(0, (dzis - d_q).days) if d_q <= dzis else 0
            waga_czasu = math.exp(-0.0018 * dni_od_q)
            efektywna_waga = waga_q * waga_czasu

            suma_wazona_kw += pkt_q * efektywna_waga
            suma_wag_kw += efektywna_waga

            audyt_kwartalny.append({
                "id": q["id"],
                "data": str(d_q),
                "nazwa": q["nazwa"],
                "okres_zbiorki": f"{okno_start} → {d_q}",
                "data_wymagalnosci": str(d_q + timedelta(days=dni_poslizgu)) if dni_poslizgu > 0 else str(d_q),
                "saldo_pln": round(saldo_na_q_gr / 100.0, 2),
                "wplata_w_oknie_pln": round(wplaty_w_oknie_gr / 100.0, 2),
                "punkty": pkt_q,
                "status": status_q,
                "waga": waga_q
            })

        kwartalne_score = int(round((suma_wazona_kw / suma_wag_kw) * 10.0)) if suma_wag_kw > 0 else 1000
        # Połączenie: 60% dyscypliny w ogłoszonych zbiórkach kwartalnych + 40% ogólnej kadencji wpłat
        rytm_score = int(round(0.60 * kwartalne_score + 0.40 * kadencja_score))
    else:
        kwartalne_score = None
        rytm_score = kadencja_score

    rytm_score = max(0, min(1000, rytm_score))

    # ---------------------------------------------------------------------
    # SYNTEZA CAŁKOWITEGO SCORE (0 - 1000)
    # ---------------------------------------------------------------------
    if vdc_score is not None:
        # Koło ma zarejestrowane głosowania w okresie stażu członka
        calkowity_score = int(round(
            0.65 * vdc_score +
            0.20 * saldo_score +
            0.10 * kdi_score +
            0.05 * rytm_score
        ))
    else:
        # Fallback gdy koło nie zdefiniowało jeszcze terminów głosowań
        calkowity_score = int(round(
            0.55 * saldo_score +
            0.30 * kdi_score +
            0.15 * rytm_score
        ))

    calkowity_score = max(0, min(1000, calkowity_score))

    # ---------------------------------------------------------------------
    # ZASADA ŻELAZNA: Bez nadpłaty nie powinno się mieć nigdy AAA
    # ---------------------------------------------------------------------
    # Poziom AAA (950–1000 pkt) jest zarezerwowany WYŁĄCZNIE dla członków z faktyczną nadpłatą (saldo_akt_gr > 0).
    # Osoby rozliczone na zero (saldo_akt_gr == 0) lub z zadłużeniem mają twardy sufit na poziomie 949 pkt (klasa AA).
    if saldo_akt_gr <= 0 and calkowity_score >= 950:
        calkowity_score = 949

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
            "liczba_glosowan": len(glosowania_w_stazu),
            "liczba_kwartalnych": len(terminy_kwartalne_w_stazu),
            "kwartalne_score": kwartalne_score,
            "kadencja_dni": round(srednio_dni_na_wplate, 1) if srednio_dni_na_wplate is not None else None
        },
        "audyt_glosowan": list(reversed(audyt_glosowan)),  # najnowsze u góry
        "audyt_kwartalny": list(reversed(audyt_kwartalny))
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
        d_kopia["celestia_audyt_kwartalny"] = res_celestia.get("audyt_kwartalny", [])
        wyniki_rozszerzone.append(d_kopia)

    return wyniki_rozszerzone

