import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
import streamlit as st
from config import DATA_ODCIECIA, dzis_pl, parse_date
from database import db_query

GRANICA_STAREJ_UCHWALY = date(2025, 1, 1)

def waliduj_daty_czlonka(ur, wst):
    dzis = dzis_pl()
    if ur > dzis:
        return False, "Data urodzenia nie może być z przyszłości!"
    if wst > dzis:
        return False, "Data przystąpienia nie może być z przyszłości!"
    if wst < ur:
        return False, "Data przystąpienia nie może być wcześniejsza niż data urodzenia!"
    
    wiek_wstapienia = wst.year - ur.year - ((wst.month, wst.day) < (ur.month, ur.day))
    if wiek_wstapienia < 13:
        return False, f"Członek w momencie przystąpienia musi mieć ukończone co najmniej 13 lat (obliczono: {wiek_wstapienia} lat)!"
    return True, ""

def pobierz_parametr(data_urodzenia_val, reczny_parametr, punkt_odniesienia):
    """
    Zwraca kod progu i stawkę bazową na dany dzień w odniesieniu do obowiązujących przepisów.
    """
    punkt = parse_date(punkt_odniesienia)
    urodziny = parse_date(data_urodzenia_val)

    if reczny_parametr in ["B", "M", "S"]:
        stawki_gr = {"B": 600, "M": 900, "S": 1500}
        return reczny_parametr, stawki_gr[reczny_parametr]

    wiek = punkt.year - urodziny.year - ((punkt.month, punkt.day) < (urodziny.month, urodziny.day))

    # Okres Starej Uchwały nr 1/2023 (do 31.12.2024)
    if punkt < GRANICA_STAREJ_UCHWALY:
        if wiek < 16:
            return "STARA_<16", 0
        elif wiek < 21:
            return "STARA_16-20", 500
        else:
            return "STARA_21+", 1000

    # Okres Nowej Uchwały (od 01.01.2025)
    if wiek < 20:
        return "B", 600
    elif wiek < 30:
        return "M", 900
    else:
        return "S", 1500

def pobierz_stawke_za_miesiac(data_wstapienia_val, data_urodzenia_val, reczny_parametr, kursor_msc):
    """
    Precyzyjne wyliczenie składki za konkretny miesiąc kalendarzowy:
    - Przed 2025: Stara Uchwała nr 1/2023 (tylko dla członków przyjętych < 2025-01-01)
    - Od 2025: Nowe progi wiekowe (B: 6 zł do 20 lat, M: 9 zł do 30 lat, S: 15 zł od 30 lat)
    """
    wstapienie = parse_date(data_wstapienia_val)
    urodziny = parse_date(data_urodzenia_val)

    # 1. EPOKA STAREJ UCHWAŁY (przed 01.01.2025 r.)
    if kursor_msc < GRANICA_STAREJ_UCHWALY and wstapienie < GRANICA_STAREJ_UCHWALY:
        # § 5 ust. 3 Uchwały 1/2023: Pierwsza składka za miesiąc po miesiącu przyjęcia
        pierwszy_msc_platny = date(wstapienie.year, wstapienie.month, 1) + relativedelta(months=1)
        if kursor_msc < pierwszy_msc_platny:
            return "ZWOLNIONY_WSTAPIENIE", 0

        # Wiek liczony na 1. dzień miesiąca (§ 5 ust. 4 pkt 1: zmiana od kolejnego miesiąca)
        wiek_stary = kursor_msc.year - urodziny.year - ((kursor_msc.month, kursor_msc.day) < (urodziny.month, urodziny.day))
        if wiek_stary < 16:
            return "STARA_<16", 0
        elif wiek_stary < 21:
            return "STARA_16-20", 500   # 5.00 PLN
        else:
            return "STARA_21+", 1000    # 10.00 PLN

    # 2. EPOKA NOWEJ UCHWAŁY (od 01.01.2025 r. wzwyż)
    else:
        if reczny_parametr in ["B", "M", "S"]:
            stawki_gr = {"B": 600, "M": 900, "S": 1500}
            return reczny_parametr, stawki_gr[reczny_parametr]

        _, last_day = calendar.monthrange(kursor_msc.year, kursor_msc.month)
        ostatni_dzien_msc = date(kursor_msc.year, kursor_msc.month, last_day)
        wiek = ostatni_dzien_msc.year - urodziny.year - ((ostatni_dzien_msc.month, ostatni_dzien_msc.day) < (urodziny.month, urodziny.day))

        if wiek < 20:
            return "B", 600
        elif wiek < 30:
            return "M", 900
        else:
            return "S", 1500

def oblicz_naliczenia_gr(data_wstapienia_val, data_urodzenia_val, reczny_parametr, punkt_odniesienia, data_odciecia_override=None):
    """
    Główna funkcja wyliczania należności statutowych.
    Obsługuje zarówno stary stan prawny (< 2025 r.), jak i nowy.
    """
    wstapienie = parse_date(data_wstapienia_val)
    punkt = parse_date(punkt_odniesienia)
    odciecie = parse_date(data_odciecia_override) if data_odciecia_override else DATA_ODCIECIA
    poczatek = max(wstapienie, odciecie)

    suma_gr = 0
    licznik = 0
    kursor = date(poczatek.year, poczatek.month, 1)
    
    while kursor <= punkt:
        _, last_day = calendar.monthrange(kursor.year, kursor.month)
        ostatni_dzien_msc = date(kursor.year, kursor.month, last_day)
        
        if ostatni_dzien_msc <= punkt:
            kod, stawka_gr = pobierz_stawke_za_miesiac(wstapienie, data_urodzenia_val, reczny_parametr, kursor)
            if kod != "ZWOLNIONY_WSTAPIENIE":
                suma_gr += stawka_gr
                licznik += 1
            
        kursor += relativedelta(months=1)

    return suma_gr, licznik

def oblicz_symulacje_kalkulatora(
    data_wstapienia_val, 
    data_urodzenia_val, 
    reczny_parametr, 
    punkt_odniesienia_val, 
    data_startu_naliczania_val,
    uwzglednij_biezacy_miesiac=False,
    skladka_funkcyjna_gr=0,
    miesiace_funkcyjne=0
):
    """
    Silnik symulacyjny kalkulatora:
    - miesiąc po miesiącu sprawdza wiek i właściwą uchwałę,
    - rejestruje historię progów (np. 15 msc w Stara Uchwała 5 zł, 9 msc w B 6 zł, 12 msc w M 9 zł),
    - dolicza opcjonalną składkę funkcyjną ze Starej Uchwały.
    """
    wstapienie = parse_date(data_wstapienia_val)
    punkt = parse_date(punkt_odniesienia_val)
    start_nal = parse_date(data_startu_naliczania_val)
    poczatek = max(wstapienie, start_nal)

    suma_podstawowa_gr = 0
    licznik_miesiecy = 0
    historia_progow = {}

    kursor = date(poczatek.year, poczatek.month, 1)
    while kursor <= punkt:
        _, last_day = calendar.monthrange(kursor.year, kursor.month)
        ostatni_dzien_msc = date(kursor.year, kursor.month, last_day)
        
        czy_naliczyc = (ostatni_dzien_msc <= punkt) or (
            uwzglednij_biezacy_miesiac and (kursor.year == punkt.year and kursor.month == punkt.month)
        )
        
        if czy_naliczyc:
            kod_progu, stawka_gr = pobierz_stawke_za_miesiac(wstapienie, data_urodzenia_val, reczny_parametr, kursor)
            if kod_progu != "ZWOLNIONY_WSTAPIENIE":
                suma_podstawowa_gr += stawka_gr
                licznik_miesiecy += 1
                historia_progow[kod_progu] = historia_progow.get(kod_progu, 0) + 1
            
        kursor += relativedelta(months=1)

    suma_funkcyjna_gr = int(miesiace_funkcyjne) * int(skladka_funkcyjna_gr)
    suma_calkowita_gr = suma_podstawowa_gr + suma_funkcyjna_gr

    return suma_calkowita_gr, suma_podstawowa_gr, suma_funkcyjna_gr, licznik_miesiecy, historia_progow

@st.cache_data(ttl=60, show_spinner=False)
def _przelicz_finanse_wielu_kol_cached(kolo_ids_tuple, punkt_odniesienia):
    if not kolo_ids_tuple:
        return {}

    aktywne_id_df = db_query("SELECT id FROM aktywne_kola WHERE id = ANY(%s)", (list(kolo_ids_tuple),))
    kolo_ids = aktywne_id_df["id"].tolist() if not aktywne_id_df.empty else []

    wyniki = {kid: ([], 0, 0, 0, 0, 0, 0) for kid in kolo_ids_tuple}
    if not kolo_ids:
        return wyniki

    wplaty_kola_df = db_query("""
        SELECT kolo_id, SUM(kwota_gr) as suma_wplat_kola_gr 
        FROM wplaty 
        WHERE kolo_id = ANY(%s) AND data_wplaty <= %s 
        GROUP BY kolo_id
    """, (kolo_ids, punkt_odniesienia))
    mapa_wplat_kola = dict(zip(wplaty_kola_df["kolo_id"], wplaty_kola_df["suma_wplat_kola_gr"])) if not wplaty_kola_df.empty else {}

    wydatki_kola_df = db_query("""
        SELECT kolo_id, SUM(kwota_gr) as suma_wydatkow_gr 
        FROM wydatki 
        WHERE kolo_id = ANY(%s) AND data_wydatku <= %s 
        GROUP BY kolo_id
    """, (kolo_ids, punkt_odniesienia))
    mapa_wydatkow_kola = dict(zip(wydatki_kola_df["kolo_id"], wydatki_kola_df["suma_wydatkow_gr"])) if not wydatki_kola_df.empty else {}

    korekty_kasy_df = db_query("""
        SELECT kolo_id, SUM(delta_gr) as suma_korekt_kasy_gr 
        FROM korekty_kasy 
        WHERE kolo_id = ANY(%s) AND data_korekty <= %s 
        GROUP BY kolo_id
    """, (kolo_ids, punkt_odniesienia))
    mapa_korekt_kasy = dict(zip(korekty_kasy_df["kolo_id"], korekty_kasy_df["suma_korekt_kasy_gr"])) if not korekty_kasy_df.empty else {}

    czlonkowie_df = db_query("""
        SELECT id, kolo_id, imie_nazwisko, data_urodzenia, data_przystapienia, saldo_startowe_gr, reczny_parametr 
        FROM czlonkowie 
        WHERE kolo_id = ANY(%s)
    """, (kolo_ids,))

    if czlonkowie_df.empty:
        for kid in kolo_ids:
            w_kasa = int(mapa_wplat_kola.get(kid, 0))
            wyd_kasa = int(mapa_wydatkow_kola.get(kid, 0))
            kor_kasa = int(mapa_korekt_kasy.get(kid, 0))
            f_kasa = w_kasa - wyd_kasa + kor_kasa
            wyniki[kid] = ([], w_kasa, f_kasa, wyd_kasa, kor_kasa, 0, 0)
        return wyniki

    czlonek_ids = czlonkowie_df["id"].tolist()

    wplaty_czlonkow_df = db_query("""
        SELECT czlonek_id, SUM(kwota_gr) as suma_wplat_gr 
        FROM wplaty 
        WHERE czlonek_id = ANY(%s) AND data_wplaty <= %s 
        GROUP BY czlonek_id
    """, (czlonek_ids, punkt_odniesienia))
    mapa_wplat_czl = dict(zip(wplaty_czlonkow_df["czlonek_id"], wplaty_czlonkow_df["suma_wplat_gr"])) if not wplaty_czlonkow_df.empty else {}

    reczne_df = db_query("""
        SELECT czlonek_id, SUM(kwota_gr) as suma_recznych_gr, COUNT(id) as liczba_recznych 
        FROM naliczenia_reczne 
        WHERE czlonek_id = ANY(%s) AND data_naliczenia <= %s 
        GROUP BY czlonek_id
    """, (czlonek_ids, punkt_odniesienia))
    mapa_reczne = {r["czlonek_id"]: (int(r["suma_recznych_gr"]), int(r["liczba_recznych"])) for _, r in reczne_df.iterrows()} if not reczne_df.empty else {}

    korekty_df = db_query("""
        SELECT czlonek_id, SUM(delta_gr) as suma_delt_gr 
        FROM korekty 
        WHERE czlonek_id = ANY(%s) AND data_korekty <= %s 
        GROUP BY czlonek_id
    """, (czlonek_ids, punkt_odniesienia))
    mapa_korekt_czl = dict(zip(korekty_df["czlonek_id"], korekty_df["suma_delt_gr"])) if not korekty_df.empty else {}

    for kid in kolo_ids:
        w_kasa = int(mapa_wplat_kola.get(kid, 0))
        wyd_kasa = int(mapa_wydatkow_kola.get(kid, 0))
        kor_kasa = int(mapa_korekt_kasy.get(kid, 0))
        f_kasa = w_kasa - wyd_kasa + kor_kasa

        czlonkowie_tego_kola = czlonkowie_df[czlonkowie_df["kolo_id"] == kid]
        if czlonkowie_tego_kola.empty:
            wyniki[kid] = ([], w_kasa, f_kasa, wyd_kasa, kor_kasa, 0, 0)
            continue

        dane_kolo = []
        tot_z_gr = 0
        tot_s_gr = 0

        for _, row in czlonkowie_tego_kola.iterrows():
            cid = row["id"]
            wpl_gr = int(mapa_wplat_czl.get(cid, 0))
            rec_gr, rec_cnt = mapa_reczne.get(cid, (0, 0))
            kor_gr = int(mapa_korekt_czl.get(cid, 0))
            s_start_gr = int(row["saldo_startowe_gr"])

            nal_auto_gr, msc = oblicz_naliczenia_gr(row["data_przystapienia"], row["data_urodzenia"], row["reczny_parametr"], punkt_odniesienia)
            param_kod, stawka_biezaca_gr = pobierz_parametr(row["data_urodzenia"], row["reczny_parametr"], punkt_odniesienia)

            nal_tot_gr = nal_auto_gr + rec_gr
            sal_akt_gr = s_start_gr + wpl_gr + kor_gr - nal_tot_gr

            s_i_gr = max(0, s_start_gr) + wpl_gr
            z_i_gr = max(0, s_i_gr - sal_akt_gr)
            tot_z_gr += z_i_gr
            tot_s_gr += s_i_gr

            kdi_val = round(z_i_gr / s_i_gr, 2) if s_i_gr > 0 else None
            kdi_str = f"{kdi_val:.2f}" if kdi_val is not None else "Brak danych"

            if sal_akt_gr >= 0:
                moze_glosowac = True
                glosowanie_str = "TAK"
            else:
                miesiace_zadluzenia = abs(sal_akt_gr) / max(stawka_biezaca_gr, 1)
                moze_glosowac = (miesiace_zadluzenia <= 6.0)
                glosowanie_str = "TAK" if moze_glosowac else "NIE"

            dane_kolo.append({
                "id": cid,
                "imie_nazwisko": row["imie_nazwisko"],
                "data_ur": row["data_urodzenia"],
                "data_wst": row["data_przystapienia"],
                "parametr": param_kod,
                "reczny_parametr": row["reczny_parametr"],
                "saldo_start_gr": s_start_gr,
                "naliczone_gr": nal_tot_gr,
                "naliczone_auto_gr": nal_auto_gr,
                "reczne_gr": rec_gr,
                "liczba_recznych": rec_cnt,
                "msc": msc,
                "wplaty_gr": wpl_gr,
                "korekty_gr": kor_gr,
                "saldo_akt_gr": sal_akt_gr,
                "saldo_akt_pln": sal_akt_gr / 100.0,
                "kdi_val": kdi_val,
                "kdi_str": kdi_str,
                "moze_glosowac": moze_glosowac,
                "glosowanie_str": glosowanie_str
            })

        wyniki[kid] = (dane_kolo, w_kasa, f_kasa, wyd_kasa, kor_kasa, tot_z_gr, tot_s_gr)

    return wyniki

def przelicz_finanse_wielu_kol(kolo_ids_input, punkt_odniesienia):
    if not kolo_ids_input:
        return {}
    k_tuple = tuple(sorted(list(kolo_ids_input)))
    return _przelicz_finanse_wielu_kol_cached(k_tuple, punkt_odniesienia)

def przelicz_finanse_dla_kola(kolo_id, punkt_odniesienia):
    res = przelicz_finanse_wielu_kol([kolo_id], punkt_odniesienia)
    return res.get(kolo_id, ([], 0, 0, 0, 0, 0, 0))

def filtruj_interwal(records, interwal_kod):
    if not records:
        return []
    if interwal_kod == "D1":
        return records
    wybrane = []
    n = len(records)
    for idx, r in enumerate(records):
        d = r["date"]
        if idx == 0 or idx == n - 1:
            wybrane.append(r)
            continue
        if interwal_kod == "T1" and d.weekday() == 6:
            wybrane.append(r)
        elif interwal_kod == "M1":
            _, last_d = calendar.monthrange(d.year, d.month)
            if d.day == last_d:
                wybrane.append(r)
        elif interwal_kod == "Q1":
            _, last_d = calendar.monthrange(d.year, d.month)
            if d.month in [3, 6, 9, 12] and d.day == last_d:
                wybrane.append(r)
        elif interwal_kod == "Q2":
            _, last_d = calendar.monthrange(d.year, d.month)
            if d.month in [6, 12] and d.day == last_d:
                wybrane.append(r)
        elif interwal_kod == "Y1" and d.month == 12 and d.day == 31:
            wybrane.append(r)
    unikalne = []
    widziane = set()
    for r in wybrane:
        if r["date"] not in widziane:
            widziane.add(r["date"])
            unikalne.append(r)
    return unikalne