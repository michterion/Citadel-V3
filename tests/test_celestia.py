from celestia import (
    POZIOMY_CELESTIA,
    pobierz_definicje_ratingu,
    pobierz_kolor_celestia,
)


def test_celestia_poziomy_count():
    # 12 poziomów: AAA, AA, A, BBB, BB, B, CCC, CC, C, D, DD, DDD
    assert len(POZIOMY_CELESTIA) == 12
    kody = [p["kod"] for p in POZIOMY_CELESTIA]
    assert kody == ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D", "DD", "DDD"]

def test_pobierz_definicje_ratingu_prog():
    assert pobierz_definicje_ratingu(1000)["kod"] == "AAA"
    assert pobierz_definicje_ratingu(950)["kod"] == "AAA"
    assert pobierz_definicje_ratingu(949)["kod"] == "AA"
    assert pobierz_definicje_ratingu(880)["kod"] == "AA"
    assert pobierz_definicje_ratingu(879)["kod"] == "A"
    assert pobierz_definicje_ratingu(800)["kod"] == "A"
    assert pobierz_definicje_ratingu(799)["kod"] == "BBB"
    assert pobierz_definicje_ratingu(700)["kod"] == "BBB"
    assert pobierz_definicje_ratingu(699)["kod"] == "BB"
    assert pobierz_definicje_ratingu(600)["kod"] == "BB"
    assert pobierz_definicje_ratingu(599)["kod"] == "B"
    assert pobierz_definicje_ratingu(500)["kod"] == "B"
    assert pobierz_definicje_ratingu(499)["kod"] == "CCC"
    assert pobierz_definicje_ratingu(380)["kod"] == "CCC"
    assert pobierz_definicje_ratingu(379)["kod"] == "CC"
    assert pobierz_definicje_ratingu(260)["kod"] == "CC"
    assert pobierz_definicje_ratingu(259)["kod"] == "C"
    assert pobierz_definicje_ratingu(150)["kod"] == "C"
    assert pobierz_definicje_ratingu(149)["kod"] == "D"
    assert pobierz_definicje_ratingu(90)["kod"] == "D"
    assert pobierz_definicje_ratingu(89)["kod"] == "DD"
    assert pobierz_definicje_ratingu(40)["kod"] == "DD"
    assert pobierz_definicje_ratingu(39)["kod"] == "DDD"
    assert pobierz_definicje_ratingu(0)["kod"] == "DDD"

def test_pobierz_kolor_celestia():
    # 1000 pkt to szmaragd KDI (#16823c)
    kolor_top = pobierz_kolor_celestia(1000, is_light=False)
    assert kolor_top == "#16823c"

    # 0 pkt to głęboki fiolet KDI (#a855f7)
    kolor_bottom = pobierz_kolor_celestia(0, is_light=False)
    assert kolor_bottom == "#a855f7"

    # Obsługa stringów z jednostką "pkt"
    kolor_string_pkt = pobierz_kolor_celestia("1000 pkt", is_light=False)
    assert kolor_string_pkt == "#16823c"

    # Kody ratingowe z POZIOMY_CELESTIA
    kolor_aaa = pobierz_kolor_celestia("AAA", is_light=False)
    assert kolor_aaa == "#23994d"
    kolor_ddd_light = pobierz_kolor_celestia("DDD", is_light=True)
    assert kolor_ddd_light == "#6a2ad0"


def test_poslizg_max_3_dni():
    from datetime import date

    import pandas as pd
    from celestia import oblicz_rating_celestia_dla_czlonka

    dane_czl = {
        "data_wst": date(2026, 1, 1),
        "data_ur": date(2000, 1, 1),
        "reczny_parametr": "M",
        "saldo_start_gr": -600,  # 1 msc długu
        "saldo_akt_gr": -600,
        "naliczone_gr": 0,
        "kdi_val": None,
    }

    # Zebranie 2026-10-10, skonfigurowany poślizg: 3 dni
    terminy_df = pd.DataFrame([{
        "id": 1,
        "data_glosowania": date(2026, 10, 10),
        "dni_zbiorki_przed": 14,
        "dni_wymagalnosci_po": 3,
        "waga": 1.0,
        "nazwa": "Zebranie"
    }])

    # 1. Wpłata 2 dni po zebraniu (2026-10-12) - mieści się w poślizgu (<= 3 dni) -> 50.0 pkt (500 pkt, poniżej 600 pkt z dnia zebrania)
    wplaty_2dni = pd.DataFrame([{"data_wplaty": date(2026, 10, 12), "kwota_gr": 600}])
    res_2dni = oblicz_rating_celestia_dla_czlonka(1, dane_czl, terminy_df, wplaty_2dni, pd.DataFrame(), pd.DataFrame(), date(2026, 10, 15))
    assert res_2dni["audyt_glosowan"][0]["punkty"] == 50.0

    # 2. Wpłata 4 dni po zebraniu (2026-10-14) - poślizg wygasł (max 3 dni) -> 40.0 pkt (brak uznania poślizgu)
    wplaty_4dni = pd.DataFrame([{"data_wplaty": date(2026, 10, 14), "kwota_gr": 600}])
    res_4dni = oblicz_rating_celestia_dla_czlonka(1, dane_czl, terminy_df, wplaty_4dni, pd.DataFrame(), pd.DataFrame(), date(2026, 10, 15))
    assert res_4dni["audyt_glosowan"][0]["punkty"] == 40.0


def test_celestia_data_wstapienia_przyszlosc_zabezpieczenie():
    from datetime import date

    import pandas as pd
    from celestia import oblicz_rating_celestia_dla_czlonka

    # Przypadek błędu w dacie wstąpienia (np. 2026-10-28 zamiast 2024-10-28)
    dzis = date(2026, 10, 14)
    dane_czl = {
        "data_wst": date(2026, 10, 28),
        "data_ur": date(2004, 6, 27),
        "reczny_parametr": None,
        "saldo_start_gr": -3500,
        "saldo_akt_gr": -2500,
        "naliczone_gr": 0,
        "kdi_val": None,
    }

    # Nadchodzące zebranie za 3 dni (2026-10-17)
    terminy_df = pd.DataFrame([{
        "id": 1,
        "data_glosowania": date(2026, 10, 17),
        "dni_zbiorki_przed": 14,
        "dni_wymagalnosci_po": 3,
        "waga": 1.0,
        "nazwa": "Zebranie regionu"
    }])

    res = oblicz_rating_celestia_dla_czlonka(66, dane_czl, terminy_df, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), dzis)
    # Głosowanie nie powinno zostać odrzucone jako "przed stażem"
    assert res["filary"]["liczba_glosowan"] == 1
    assert res["filary"]["vdc_score"] is not None
    assert res["rating"] in ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D", "DD", "DDD"]


def test_rytm_platnosci_kwartalny_1000_pkt():
    from datetime import date

    import pandas as pd
    from celestia import oblicz_rating_celestia_dla_czlonka

    dzis = date(2026, 10, 1)
    # Staż 360 dni, 4 wpłaty (co ~90 dni) - wzorcowy rytm kwartalny
    dane_czl = {
        "data_wst": date(2025, 10, 5),
        "data_ur": date(1995, 1, 1),
        "reczny_parametr": "M",
        "saldo_start_gr": 0,
        "saldo_akt_gr": 0,
        "naliczone_gr": 3600,
        "kdi_val": 1.0,
    }
    wplaty_df = pd.DataFrame([
        {"data_wplaty": date(2026, 1, 5), "kwota_gr": 900},
        {"data_wplaty": date(2026, 4, 5), "kwota_gr": 900},
        {"data_wplaty": date(2026, 7, 5), "kwota_gr": 900},
        {"data_wplaty": date(2026, 9, 20), "kwota_gr": 900},  # świeża wpłata w bieżącym kwartale
    ])

    res = oblicz_rating_celestia_dla_czlonka(1, dane_czl, pd.DataFrame(), wplaty_df, pd.DataFrame(), pd.DataFrame(), dzis)
    # Płacenie kwartalne (średnio ~90 dni na wpłatę) powinno dawać pełne 1000 pkt
    assert res["filary"]["kadencja_dni"] <= 105
    assert res["filary"]["rytm_score"] == 1000


def test_termin_kwartalny_nie_jest_glosowaniem_i_wplywa_na_rytm():
    from datetime import date

    import pandas as pd
    from celestia import oblicz_rating_celestia_dla_czlonka

    dzis = date(2026, 10, 1)
    dane_czl = {
        "data_wst": date(2025, 1, 1),
        "data_ur": date(1990, 1, 1),
        "reczny_parametr": "M",
        "saldo_start_gr": 0,
        "saldo_akt_gr": 0,
        "naliczone_gr": 6000,
        "kdi_val": 1.0,
    }

    # Zarejestrowana TYLKO zbiórka kwartalna (nie ma żadnych zebrań / głosowań)
    terminy_df = pd.DataFrame([{
        "id": 10,
        "data_glosowania": date(2026, 6, 30),
        "dni_zbiorki_przed": 14,
        "dni_wymagalnosci_po": 3,
        "waga": 1.0,
        "nazwa": "Zbiórka Q2 2026",
        "typ_terminu": "KWARTALNY"
    }])

    # Wpłata w oknie zbiórki kwartalnej (2026-06-25)
    wplaty_df = pd.DataFrame([
        {"data_wplaty": date(2026, 6, 25), "kwota_gr": 6000}
    ])

    res = oblicz_rating_celestia_dla_czlonka(1, dane_czl, terminy_df, wplaty_df, pd.DataFrame(), pd.DataFrame(), dzis)

    # 1. Termin kwartalny NIE MOŻE zaliczać się jako dzień głosowania (VDC)
    assert res["filary"]["liczba_glosowan"] == 0
    assert res["filary"]["vdc_score"] is None
    assert len(res["audyt_glosowan"]) == 0

    # 2. Termin kwartalny został zaliczony do zbiórek kwartalnych i filaru Rytmu
    assert res["filary"]["liczba_kwartalnych"] == 1
    assert len(res["audyt_kwartalny"]) == 1
    assert res["audyt_kwartalny"][0]["nazwa"] == "Zbiórka Q2 2026"
    assert res["audyt_kwartalny"][0]["punkty"] == 100
    assert res["filary"]["kwartalne_score"] == 1000
    assert res["filary"]["rytm_score"] >= 750


def test_dynamiczna_terminowosc_okna_zbiorki():
    from datetime import date

    import pandas as pd
    from celestia import oblicz_rating_celestia_dla_czlonka

    dzis = date(2026, 10, 20)
    dane_czl = {
        "data_wst": date(2025, 1, 1),
        "data_ur": date(1995, 1, 1),
        "reczny_parametr": "M",
        "saldo_start_gr": -600,
        "saldo_akt_gr": 0,
        "naliczone_gr": 0,
        "kdi_val": 1.0,
    }

    # Zebranie 2026-10-14, okno zbiórki 14 dni (od 2026-09-30 do 2026-10-14)
    terminy_df = pd.DataFrame([{
        "id": 1,
        "data_glosowania": date(2026, 10, 14),
        "dni_zbiorki_przed": 14,
        "dni_wymagalnosci_po": 0,
        "waga": 1.0,
        "nazwa": "Zebranie testowe"
    }])

    # 1. Wpłata w I połowie okna (np. dzień 5 z 14: 2026-10-05) -> 100.0 pkt (1000 pkt)
    wpl_wczesna = pd.DataFrame([{"data_wplaty": date(2026, 10, 5), "kwota_gr": 600}])
    res_wczesna = oblicz_rating_celestia_dla_czlonka(1, dane_czl, terminy_df, wpl_wczesna, pd.DataFrame(), pd.DataFrame(), dzis)
    assert res_wczesna["audyt_glosowan"][0]["punkty"] == 100.0

    # 2. Wpłata w dniu głosowania (ostatni dzień okna: 2026-10-14) -> dokładnie 60.0 pkt (600 pkt)
    wpl_ostatni_dzien = pd.DataFrame([{"data_wplaty": date(2026, 10, 14), "kwota_gr": 600}])
    res_ostatni_dzien = oblicz_rating_celestia_dla_czlonka(1, dane_czl, terminy_df, wpl_ostatni_dzien, pd.DataFrame(), pd.DataFrame(), dzis)
    assert res_ostatni_dzien["audyt_glosowan"][0]["punkty"] == 60.0

    # 3. Wpłata na 75% czasu okna (dzień 10.5 z 14, np. 2026-10-11, progress = 11/14 ~ 0.786) -> ~77.1 pkt
    wpl_srodek = pd.DataFrame([{"data_wplaty": date(2026, 10, 11), "kwota_gr": 600}])
    res_srodek = oblicz_rating_celestia_dla_czlonka(1, dane_czl, terminy_df, wpl_srodek, pd.DataFrame(), pd.DataFrame(), dzis)
    assert 70.0 <= res_srodek["audyt_glosowan"][0]["punkty"] <= 85.0


def test_zasada_zelazna_brak_aaa_bez_nadplaty():
    from datetime import date

    import pandas as pd
    from celestia import oblicz_rating_celestia_dla_czlonka

    dzis = date(2026, 10, 1)

    # Członek A: Idealne wyniki, ale saldo = 0 (brak nadpłaty)
    czlonek_bez_nadplaty = {
        "data_wst": date(2025, 1, 1),
        "data_ur": date(1995, 1, 1),
        "reczny_parametr": "M",
        "saldo_start_gr": 0,
        "saldo_akt_gr": 0,  # SALDO RÓWNE ZERO
        "naliczone_gr": 3600,
        "kdi_val": 0.50,
    }

    # Członek B: Identyczne wyniki, ale posiada nadpłatę (+50.00 zł)
    czlonek_z_nadplata = {
        "data_wst": date(2025, 1, 1),
        "data_ur": date(1995, 1, 1),
        "reczny_parametr": "M",
        "saldo_start_gr": 5000,
        "saldo_akt_gr": 5000,  # Nスキル NADPŁATA +50 zł
        "naliczone_gr": 3600,
        "kdi_val": 0.50,
    }

    wplaty_df = pd.DataFrame([
        {"data_wplaty": date(2026, 1, 5), "kwota_gr": 900},
        {"data_wplaty": date(2026, 4, 5), "kwota_gr": 900},
        {"data_wplaty": date(2026, 7, 5), "kwota_gr": 900},
        {"data_wplaty": date(2026, 9, 20), "kwota_gr": 900},
    ])

    res_bez = oblicz_rating_celestia_dla_czlonka(1, czlonek_bez_nadplaty, pd.DataFrame(), wplaty_df, pd.DataFrame(), pd.DataFrame(), dzis)
    res_z = oblicz_rating_celestia_dla_czlonka(2, czlonek_z_nadplata, pd.DataFrame(), wplaty_df, pd.DataFrame(), pd.DataFrame(), dzis)

    # Członek bez nadpłaty ma twardy sufit na poziomie 949 pkt i NIE MOŻE mieć AAA
    assert res_bez["score"] <= 949
    assert res_bez["rating"] == "AA"

    # Członek z nadpłatą otrzymuje poziom AAA (>= 950 pkt)
    assert res_z["score"] >= 950
    assert res_z["rating"] == "AAA"


def test_wygaszanie_salda_dla_dluznikow_baza_250():
    from datetime import date

    import pandas as pd
    from celestia import oblicz_rating_celestia_dla_czlonka

    dzis = date(2026, 10, 1)

    # 1. Członek z długiem 6 miesięcy (stawka 600 gr/msc, dług -3600 gr) -> dokładnie 250 pkt
    dane_6msc = {
        "data_wst": date(2024, 1, 1),
        "data_ur": date(2008, 1, 1),
        "reczny_parametr": "B",
        "saldo_start_gr": -3600,
        "saldo_akt_gr": -3600,
        "naliczone_gr": 3600,
        "kdi_val": 2.0,
    }
    res_6msc = oblicz_rating_celestia_dla_czlonka(1, dane_6msc, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), dzis)
    assert res_6msc["filary"]["saldo_score"] == 250

    # 2. Członek z długiem 18 miesięcy (dług -10800 gr): 250 - (18-6) * (250/30) = 250 - 100 = 150 pkt
    dane_18msc = {
        "data_wst": date(2024, 1, 1),
        "data_ur": date(2008, 1, 1),
        "reczny_parametr": "B",
        "saldo_start_gr": -10800,
        "saldo_akt_gr": -10800,
        "naliczone_gr": 10800,
        "kdi_val": 3.0,
    }
    res_18msc = oblicz_rating_celestia_dla_czlonka(2, dane_18msc, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), dzis)
    assert res_18msc["filary"]["saldo_score"] == 150

    # 3. Członek z długiem 24 miesiące (dług -14400 gr): 250 - (24-6) * (250/30) = 250 - 150 = 100 pkt
    dane_24msc = {
        "data_wst": date(2024, 1, 1),
        "data_ur": date(2008, 1, 1),
        "reczny_parametr": "B",
        "saldo_start_gr": -14400,
        "saldo_akt_gr": -14400,
        "naliczone_gr": 14400,
        "kdi_val": 4.0,
    }
    res_24msc = oblicz_rating_celestia_dla_czlonka(3, dane_24msc, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), dzis)
    assert res_24msc["filary"]["saldo_score"] == 100


def test_brak_wplat_kadencja_score_50():
    from datetime import date

    import pandas as pd
    from celestia import oblicz_rating_celestia_dla_czlonka

    dzis = date(2026, 10, 1)

    # Nowy członek bez wpłat w historii i zerowych naliczeniach nie może dostać 1000 pkt za rytm
    nowy_czlonek = {
        "data_wst": date(2026, 9, 25),
        "data_ur": date(2005, 1, 1),
        "reczny_parametr": "M",
        "saldo_start_gr": 0,
        "saldo_akt_gr": 0,
        "naliczone_gr": 0,
        "kdi_val": None,
    }

    res = oblicz_rating_celestia_dla_czlonka(1, nowy_czlonek, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), dzis)
    # Brak wpłat w historii daje minimalny scoring kadencji 50 pkt (brak wyrobionego rytmu wpłat)
    assert res["filary"]["rytm_score"] == 50
    assert res["filary"]["kadencja_dni"] is None





