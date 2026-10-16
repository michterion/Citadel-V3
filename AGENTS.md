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
5. **Dynamiczny Próg KDI a Benchmark 1.20**:
   * Statutowy benchmark `Rekomendowane: ≤ 1.20` odpowiada dokładnie 3-letniemu stażowi członka przy 6 miesiącach karencji statutowej ($36S / 30S = 1.20$). Pozostaje on trwałym benchmarkiem porównawczym w napisach i kodzie.
   * Rzeczywisty, dynamiczny próg KDI do zachowania praw głosu zależy od stażu i struktury wiekowej koła/regionu/kraju:
     $KDI_{\text{próg}} = \frac{\sum z_i}{\sum \max(0, z_i - 6 \times S_i)}$.
   * Dla osób o stażu $\le 6$ msc próg wynosi `pełna karencja` (brak konieczności jakichkolwiek wpłat do prawa głosu).
   * Wartość progu jest renderowana dynamicznie w kafelkach Bento obok bieżącego KDI mniejszą czcionką z poświatą tekstu (`text-shadow`) i kolorem ze skali KDI (`formatuj_wartosc_kdi`), zachowując niezmieniony benchmark w podtytule (`Rekomendowane: ≤ 1.20`).

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
2. **Dni Wymagalności (`terminy_glosowan`) — Dwie Kategorie Zdarzeń**:
   * Tabela `terminy_glosowan` obsługuje dwa odrębne typy zdarzeń (`typ_terminu`):
     1. **`GLOSOWANIE`** (Domyślny) — Walne Zebranie, Wybory Władz, Głosowania uchwał:
        * Kluczowy punkt zapadalności dla **Filaru 1 (VDC — 65%)** i wyznaczania praw głosu.
        * Wymaga niezalegania ze składkami na dzień zebrania (z max 3-dniowym poślizgiem).
     2. **`KWARTALNY`** — Oficjalny Dzień Wymagalności Kwartalnej / Zbiórka Kwartalna:
        * **BEZWZGLĘDNIE NIE zalicza się jako dzień głosowania** (nie wchodzi do VDC, nie zlicza się w `liczba_glosowan`, nie blokuje praw głosu na zebraniach).
        * Wpływa bezpośrednio na **Filar 4: Rytm i Regularność Wpłat**.
   * Każde wydarzenie definiuje:
     * `data_zbiorki_od` oraz `data_wymagalnosci_do`
     * `dni_zbiorki_przed` (1–90 dni)
     * `dni_wymagalnosci_po` (dopuszczalny poślizg 0–3 dni, maksymalnie 3 dni)
   * **Uwzględnianie terminów w oknie zbiórki i nadchodzących**:
     * Terminy są włączane do ratingu Celestia nie tylko wstecz, ale również gdy okno zbiórki jest już otwarte (`d_od <= dzis`) lub gdy termin przypada w horyzoncie 30 dni (`d_termin <= dzis + 30 dni`).
   * **Waga czasowa (*time-decay*)**: `waga_czasu = exp(-0.0018 * dni_od_terminu)` faworyzuje najświeższe zachowania płatnicze.
3. **Wagi Filarów Scoringowych i Nowy Rytm Kwartalny**:
   * **Głosowania i Zapadalność (VDC)**: **65%** — kluczowy wyznacznik wiarygodności (tylko zdarzenia `GLOSOWANIE`).
   * **Bieżące Saldo i Karencja**: **20%** — stały bezpiecznik stanu konta:
     * `saldo_akt_gr > 0` (nadpłata): **1000 pkt**.
     * `saldo_akt_gr == 0` (stan zerowy, brak zaległości): **900 pkt**.
     * Liniowe wygaszanie punktów salda od 6 do 36 miesięcy zaległości (twarde zero dopiero po 36 msc długu).
   * **Wskaźnik Pokrycia KDI**: **10%** — bilans wpłat do naliczeń.
   * **Rytm i Regularność Wpłat**: **5%** — **zorientowany na model kwartalny**:
     * Wpłaty co kwartał (średnio do 105 dni na wpłatę) dają wzorcowe **1000 pkt** (zamiast sztucznie zaniżanych 850 pkt).
     * Jeśli koło zarejestrowało zbiórki kwartalne (`KWARTALNY`), filar łączy realizację wyznaczonych zbiórek kwartalnych (60%) z ogólną kadencją wpłat (40%).
     * Jeśli koło nie ogłaszało jeszcze zbiórek kwartalnych, ocena bazuje w 100% na ogólnej kadencji kwartalnej.
4. **Dynamiczna Terminowość w Oknie Zbiórki i Żelazna Reguła AAA**:
   * **Dynamiczna skala punktowa w oknie zbiórki**:
     * Stała nadpłata przed zbiórką (`saldo_na_glos_gr - wplaty_w_oknie_gr >= 0`): **1000 pkt**.
     * Wpłata w pierwszych 50% czasu trwania zbiórki ($progress \le 0.50$): **1000 pkt** (brak jakiejkolwiek kary).
     * Wpłata w drugiej połowie okna zbiórki ($0.50 < progress \le 1.0$): płynny, liniowy spadek od **1000 pkt** do **600 pkt** w ostatnim dniu zbiórki / dniu głosowania (`pkt = 100.0 - ((progress - 0.50) / 0.50) * 40.0`).
     * Poślizg (1–3 dni po terminie, tylko przy pełnym pokryciu długu): **500–550 pkt** (musi dawać mniej niż wpłata w dniu terminu, by wyeliminować opłacalność spóźnienia).
   * **Żelazna Reguła AAA (Brak AAA bez nadpłaty)**:
     * Poziom **AAA (950–1000 pkt)** jest bezwzględnie zarezerwowany **wyłącznie dla członków z faktyczną nadpłatą** (`saldo_akt_gr > 0`).
     * Członek z saldem $\le 0$ (nawet przy idealnym rozliczeniu na zero i 1000 pkt w VDC) ma twardy sufit na poziomie **949 pkt (maksimum klasa AA)**.
   * **Progresywna skala VDC zależna od czasu trwania długu**:
     * `dług <= 2 msc`: **400 pkt** (brak wpłaty) / **500–550 pkt** (poślizg) — zachowane pełne prawo głosu.
     * `2–6 msc`: **400 pkt** (brak) / **650 pkt** (poślizg) — zachowane prawo głosu (karencja statutowa).
     * `6–8 msc`: **250 pkt** (brak) / **450 pkt** (poślizg) — świeże przekroczenie karencji o 1–2 msc (klasa CC/CCC).
     * `8–12 msc`: **150 pkt** (brak) / **300 pkt** (poślizg) — utrwalone zadłużenie do 1 roku (klasa C).
     * `12–18 msc`: **80 pkt** (brak) / **200 pkt** (poślizg) — zadłużenie ponadroczne, ~100–160 zł (klasa D).
     * `18–28 msc`: **30 pkt** (brak) / **100 pkt** (poślizg) — zadłużenie wieloletnie, ~160–250 zł (klasa DD).
     * `> 28 msc`: **0 pkt** (brak) / **50 pkt** (poślizg) — skrajny default, > 350–450 zł (klasa DDD).
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

