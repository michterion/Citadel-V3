from calculations import formatuj_wartosc_kdi, oblicz_dynamiczny_prog_kdi


def test_oblicz_dynamiczny_prog_kdi_brak_danych():
    val, text = oblicz_dynamiczny_prog_kdi([])
    assert val is None
    assert text == "Brak danych"


def test_oblicz_dynamiczny_prog_kdi_pelna_karencja():
    # Członkowie o stażu <= 6 miesięcy nie mają minimalnego wymogu wpłat do głosu
    dane = [
        {"z_i_gr": 3000, "stawka_biezaca_gr": 1000},  # 3 msc
        {"z_i_gr": 6000, "stawka_biezaca_gr": 1000},  # 6 msc (dokładnie granica)
    ]
    val, text = oblicz_dynamiczny_prog_kdi(dane)
    assert val is None
    assert text == "pełna karencja"


def test_oblicz_dynamiczny_prog_kdi_7_miesiecy():
    # 7 miesięcy: zapotrzebowanie 70 zł, wymóg wpłaty: 70 - 60 = 10 zł. KDI próg = 70 / 10 = 7.00
    dane = [{"z_i_gr": 7000, "stawka_biezaca_gr": 1000}]
    val, text = oblicz_dynamiczny_prog_kdi(dane)
    assert val == 7.00
    assert text == "≤ 7.00"


def test_oblicz_dynamiczny_prog_kdi_36_miesiecy_benchmark():
    # 36 miesięcy (3 lata): zapotrzebowanie 360 zł, wymóg wpłaty: 360 - 60 = 300 zł.
    # KDI próg = 360 / 300 = 1.20 (dokładne źródło benchmarku 1.20!)
    dane = [{"z_i_gr": 36000, "stawka_biezaca_gr": 1000}]
    val, text = oblicz_dynamiczny_prog_kdi(dane)
    assert val == 1.20
    assert text == "≤ 1.20"


def test_oblicz_dynamiczny_prog_kdi_5_lat():
    # 60 miesięcy (5 lat): zapotrzebowanie 600 zł, wymóg wpłaty: 600 - 60 = 540 zł.
    # KDI próg = 600 / 540 = 1.11
    dane = [{"z_i_gr": 60000, "stawka_biezaca_gr": 1000}]
    val, text = oblicz_dynamiczny_prog_kdi(dane)
    assert val == 1.11
    assert text == "≤ 1.11"


def test_oblicz_dynamiczny_prog_kdi_agregacja_kola():
    # Koło dwuosobowe:
    # Osoba A: 7 msc (z=7000, stawka=1000 -> min_wplata = 1000)
    # Osoba B: 60 msc (z=60000, stawka=1000 -> min_wplata = 54000)
    # Suma z = 67000, Suma min_wplat = 55000 -> KDI progu = 67000 / 55000 = 1.218... -> 1.22
    dane = [
        {"z_i_gr": 7000, "stawka_biezaca_gr": 1000},
        {"z_i_gr": 60000, "stawka_biezaca_gr": 1000},
    ]
    val, text = oblicz_dynamiczny_prog_kdi(dane)
    assert val == 1.22
    assert text == "≤ 1.22"


def test_formatuj_wartosc_kdi():
    # 1. Z wartością progową
    html_val = formatuj_wartosc_kdi("1.15", 1.25, "≤ 1.25")
    assert "1.15" in html_val
    assert "(próg: ≤ 1.25)" in html_val
    assert "font-size: 0.92rem" in html_val

    # 2. Z pełną karencją
    html_karencja = formatuj_wartosc_kdi("Brak danych", None, "pełna karencja")
    assert "Brak danych" in html_karencja
    assert "(próg: pełna karencja)" in html_karencja
    assert "#4ade80" in html_karencja

    # 3. Brak danych i brak karencji
    assert formatuj_wartosc_kdi("Brak danych", None, "") == "Brak danych"
