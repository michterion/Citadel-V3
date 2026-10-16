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

