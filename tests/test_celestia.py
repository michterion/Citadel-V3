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

    # 1. Wpłata 2 dni po zebraniu (2026-10-12) - mieści się w poślizgu (<= 3 dni) -> 90 pkt
    wplaty_2dni = pd.DataFrame([{"data_wplaty": date(2026, 10, 12), "kwota_gr": 600}])
    res_2dni = oblicz_rating_celestia_dla_czlonka(1, dane_czl, terminy_df, wplaty_2dni, pd.DataFrame(), pd.DataFrame(), date(2026, 10, 15))
    assert res_2dni["audyt_glosowan"][0]["punkty"] == 90

    # 2. Wpłata 4 dni po zebraniu (2026-10-14) - poślizg wygasł (max 3 dni) -> 80 pkt (brak uznania poślizgu)
    wplaty_4dni = pd.DataFrame([{"data_wplaty": date(2026, 10, 14), "kwota_gr": 600}])
    res_4dni = oblicz_rating_celestia_dla_czlonka(1, dane_czl, terminy_df, wplaty_4dni, pd.DataFrame(), pd.DataFrame(), date(2026, 10, 15))
    assert res_4dni["audyt_glosowan"][0]["punkty"] == 80


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


