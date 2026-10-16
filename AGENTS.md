# Citadel V3 — Baza Wiedzy i Wytyczne dla Agenta (AGENTS.md)

Ten plik stanowi trwałą pamięć projektu dla asystentów AI (Antigravity). Zawiera zasady architektoniczne, reguły biznesowe, schematy bazy danych oraz konwencje programistyczne dla repozytorium **Citadel V3**.

---

## 🏛️ 1. Architektura i Kontekst Projektu
* **Domena**: System zarządzania finansami, strukturą organizacyjną (Kraj → Regiony → Koła → Członkowie) oraz dyscypliną składek i prawem głosu.
* **Silnik ratingowy Celestia**: Autorski algorytm scoringu wypłacalności i dyscypliny członków (skala AAA do DDD), gdzie kluczowym parametrem jest terminowość wpłat w oknie zbiórki przed zarejestrowanymi głosowaniami/zebraniami.
* **Technologie**:
  * Python 3.11+
  * **Streamlit** (architektura reaktywna, `st.session_state`, custom injected CSS)
  * **PostgreSQL** z biblioteką `psycopg` (v3) oraz `psycopg_pool.ConnectionPool`
  * **Astral uv** (`pyproject.toml` zgodny z PEP 621, flaga `package = false`, `uv.lock`)
  * **Plotly** dla wykresów analitycznych (z adaptacją do motywu)

---

## ⚡ 2. Środowisko i Zarządzanie Zależnościami (uv)
* W projekcie używamy wyłącznie **`uv`** do zarządzania wirtualnym środowiskiem i zależnościami:
  * Instalacja / synchronizacja: `uv sync`
  * Uruchamianie aplikacji: `uv run streamlit run citadel/app.py` (lub z poziomu `citadel/`: `uv run streamlit run app.py`)
  * Formatowanie i linting: `uv run ruff check citadel`
  * Uruchamianie testów: `uv run pytest`
* **Plik `pyproject.toml`** w katalogu głównym:
  * Skonfigurowany z `[tool.uv] package = false`, ponieważ Citadel to aplikacja webowa, a nie pakiet biblioteczny do publikacji na PyPI.
  * Zależności produkcyjne: `streamlit`, `pandas`, `plotly`, `psycopg[binary,pool]`, `python-dateutil`, `openpyxl`, `watchdog`.
  * Zależności deweloperskie: `pytest`, `ruff` w sekcji `[dependency-groups] dev`.
  * Skrypt `citadel/Citadel_launch.bat` automatycznie wykrywa obecność `uv` i uruchamia projekt przez `uv run`.

---

## 💰 3. Finanse, Kwoty i Spójność Danych (Kluczowe Zasady)
1. **Zasada Grosza (`BIGINT`)**:
   * Wszystkie operacje finansowe (składki, wpłaty, salda, korekty, kasa podręczna) w bazie danych oraz w pamięci algorytmów **muszą być liczone w groszach całkowitych (`int` / `BIGINT`)**.
   * Przeliczniki: `gr_na_pln(gr: int) -> float` oraz `pln_na_gr(pln: float) -> int` z modułu [`config.py`](file:///c:/Users/Micha%C5%82/Desktop/Citadel%20V3/citadel/config.py).
   * Nigdy nie przechowuj kwot pieniężnych w bazie jako typy zmiennoprzecinkowe `REAL` / `FLOAT`.
2. **Klucz Idempotencji (`idempotency_key`)**:
   * Tabela `wplaty_oczekujace` posiada unikalny klucz `idempotency_key TEXT UNIQUE` zapobiegający wielokrotnemu wprowadzeniu tej samej transakcji bankowej/wpłaty.
3. **Data Odcięcia**:
   * Stała `DATA_ODCIECIA = date(2026, 10, 1)` definiuje początek naliczania składek w bieżącym okresie rozliczeniowym.
4. **Strefa Czasowa**:
   * Zawsze używamy czasu warszawskiego (`WARSAW_TZ = tz.gettz("Europe/Warsaw")`, funkcje `dzis_pl()`, `teraz_utc()`, `formatuj_czas_pl()`).

---

## 🛡️ 4. Silnik Ratingowy Celestia — Szczegóły Implementacji
1. **Skala Ratingowa (12 stopni)**:
   * **AAA** (950–1000 pkt) — Wzorowa wiarygodność (Prime Apex)
   * **AA** (880–949 pkt) — Bardzo wysoka dyscyplina (High Grade)
   * **A** (800–879 pkt) — Wysoka dyscyplina (Upper Medium)
   * **BBB** (700–799 pkt) — Dobra wiarygodność inwestycyjna (Good Standing)
   * **BB** (600–699 pkt) — Zadowalająca dyscyplina (Moderate)
   * **B** (500–599 pkt) — Dopuszczalna dyscyplina (Vulnerable)
   * **CCC** (380–499 pkt) — Podwyższone ryzyko (Substantial Risk)
   * **CC** (260–379 pkt) — Wysokie ryzyko zadłużenia (Extremely Speculative)
   * **C** (150–259 pkt) — Krytyczne zadłużenie roczne (Near Default, ~60–100 zł)
   * **D** (90–149 pkt) — Wczesna niewypłacalność ponadroczna (Insolvency 1, ~100–160 zł)
   * **DD** (40–89 pkt) — Głęboka niewypłacalność dwuletnia (Insolvency 2, ~160–250 zł)
   * **DDD** (0–39 pkt) — Skrajny / terminalny default (> 28–36 msc, > 350–450 zł)
2. **Głosowania i Terminy Wymagalności (`terminy_glosowan`)**:
   * W praktyce składki są wymagane na głosowania/zebrania koła.
   * Każde koło definiuje własne parametry:
     * `data_zbiorki_od` oraz `data_wymagalnosci_do`
     * `dni_zbiorki_przed` (1–90 dni, np. 5–7 dni w małych kołach, 14–30 dni w dużych)
     * `dni_wymagalnosci_po` (dopuszczalny poślizg 0–30 dni)
   * **Uwzględnianie zebrań w oknie zbiórki i nadchodzących**:
     * Zebrania są włączane do ratingu Celestia nie tylko wstecz, ale również gdy okno zbiórki jest już otwarte (`d_od <= dzis`) lub gdy termin zebrania przypada w horyzoncie 30 dni (`d_glos <= dzis + 30 dni`).
     * Pozwala to skarbnikowi i członkom na bieżąco monitorować prawa głosu i wywiązywanie się ze składek przed samym zebraniem (do terminu zebrania w danym miesiącu nie nalicza się nowa składka).
   * **Waga czasowa (*time-decay*)**: `waga_czasu = exp(-0.0018 * dni_od_glosowania)` faworyzuje najświeższe zachowania płatnicze (dla bieżących i nadchodzących zebrań `dni_od_glos = 0`, waga = 1.0).
3. **Wagi Filarów Scoringowych**:
   * **Głosowania i Zapadalność (VDC)**: **65%** — kluczowy wyznacznik wiarygodności.
   * **Bieżące Saldo i Karencja**: **20%** — stały bezpiecznik stanu konta (twarde zero dopiero po 36 msc długu).
   * **Wskaźnik Pokrycia KDI**: **10%** — bilans wpłat do naliczeń.
   * **Rytm i Regularność Wpłat**: **5%** — ciągłość i rytmika transakcji.
4. **Zabezpieczenie przed Symboliczną Wpłatą i Progresywna Skala Zapadalności**:
   * Okienko poślizgu (do 3 dni po terminie) jest uznawane **wyłącznie wtedy, gdy wpłata faktycznie pokrywa całe zadłużenie** (`saldo_na_wym_gr + wplaty_poslizg_gr >= 0`).
   * **Progresywna skala VDC zależna od czasu trwania długu**:
     * `dług <= 2 msc`: **80 pkt** (brak) / **90 pkt** (poślizg) — pełne prawo głosu.
     * `2–6 msc`: **40 pkt** (brak) / **65 pkt** (poślizg) — zachowane prawo głosu (karencja statutowa).
     * `6–8 msc`: **25 pkt** (brak) / **45 pkt** (poślizg) — świeże przekroczenie karencji o 1–2 msc (klasa CC/CCC).
     * `8–12 msc`: **15 pkt** (brak) / **30 pkt** (poślizg) — utrwalone zadłużenie do 1 roku (klasa C).
     * `12–18 msc`: **8 pkt** (brak) / **20 pkt** (poślizg) — zadłużenie ponadroczne, ~100–160 zł (klasa D).
     * `18–28 msc`: **3 pkt** (brak) / **10 pkt** (poślizg) — zadłużenie wieloletnie, ~160–250 zł (klasa DD).
     * `> 28 msc`: **0 pkt** (brak) / **5 pkt** (poślizg) — skrajny default, > 350–450 zł (klasa DDD).
   * **Filar Salda — twarde zero dopiero przy 36 msc**: Liniowe wygaszanie punktów salda od 6 do 36 miesięcy zapobiega zrównywaniu członka z 1.5 roku długu z osobą z 3+ latami bierności.
   * Dzięki temu osoba z długiem ~150 zł ląduje w **D**, z ~200 zł w **DD**, a dopiero notoryczny dłużnik z 400+ zł długu w **DDD**.
5. **Rating Koła = MEDIANA, a nie Średnia**:
   * Główny wskaźnik wiarygodności koła jest wyliczany jako **mediana statystyczna** (`statistics.median`) ze scoringów członków.
   * Średnia arytmetyczna jest podawana jedynie pomocniczo w nawiasie.
   * Mediana chroni koło przed zafałszowaniem wskaźnika przez pojedyncze osoby nieaktywne/dłużników.
6. **Bezpieczne Parsowanie Kolumn SQL / Pandas**:
   * Zawsze stosuj helper `_num(v, d): return d if v is None or pd.isna(v) else v` przy odczytywaniu kolumn z tabeli `terminy_glosowan` (`dni_zbiorki_przed`, `dni_wymagalnosci_po`, `waga`), aby zapobiec `ValueError` przy wartościach `NaN`.
   * Importy parametrów stawek (`pobierz_parametr`) muszą znajdować się na górze modułów, bez cichego tłumienia błędów `except Exception: pass`.
7. **Spójność Barwna ze Skalą KDI**:
   * Zgodnie z zasadą spójności UI, Celestia nie korzysta z odrębnej palety barw, lecz bazuje na kanonicznej skali gradientu KDI / Uprawnieni:
     Szmaragd (`1000 pkt`) → Jasna Zieleń (`900 pkt`) → Biel/Srebro (`800 pkt`) → Żółty (`700 pkt`) → Pomarańczowy (`550 pkt`) → Czerwony (`400 pkt`) → Różowy (`250 pkt`) → Błękitny (`100 pkt`) → Fioletowy (`0 pkt`).
   * Funkcja `pobierz_kolor_celestia` płynnie interpoluje punkty 0–1000 wzdłuż krzywej KDI lub zwraca barwę przypisaną do kodu klasy wiarygodności, z zachowaniem wysokiego kontrastu dla jasnego motywu.

---

## 🔐 5. Kontrola Dostępu (RBAC)
* Moduł [`citadel/rbac.py`](file:///c:/Users/Micha%C5%82/Desktop/Citadel%20V3/citadel/rbac.py) jest pojedynczym źródłem prawdy dla autoryzacji:
  * Role: `ADMIN`, `SKARBNIK_KRAJOWY`, `SKARBNIK_REGIONU`, `SKARBNIK_KOLA`.
  * Weryfikacja: `moze(rola, "akcja")`.
* Bezpieczeństwo haseł:
  * `hashlib.pbkdf2_hmac("sha256", haslo, sol, 200_000)` z `secrets.token_hex(16)` i `secrets.compare_digest`.

---

## 🎨 6. Motywy i Spójność UI
* Trzy motywy w [`config.py`](file:///c:/Users/Micha%C5%82/Desktop/Citadel%20V3/citadel/config.py):
  1. `fiolet` (akcenty `#9333ea`, tło `#0a0612`)
  2. `dark_mono` (grafit/czerń `#0e1117`, obramowania `#262730`)
  3. `light_mono` (śnieżnobiałe tło `#ffffff`, karty `#f8fafc`, wysoki kontrast)
* **Zasada**: Wszelkie nowe komponenty, tabele i przyciski muszą korzystać z klas CSS motywu (`st.session_state["motyw"]`) lub zmiennych z `pobierz_motyw_css()`, bez hardkodowania kolorów tekstu czy tła na stałe.
* Wykresy Plotly korzystają z funkcji pomocniczej `czy_jasny_motyw()` do automatycznego doboru szablonu i barw etykiet.

