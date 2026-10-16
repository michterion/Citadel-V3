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
   * **AAA** (90–100 pkt) — Wzorowa wiarygodność (Prime)
   * **AA** (80–89 pkt) — Bardzo wysoka dyscyplina
   * **A** (70–79 pkt) — Wysoka dyscyplina
   * **BBB** (60–69 pkt) — Dobra wiarygodność inwestycyjna
   * **BB** (50–59 pkt) — Zadowalająca dyscyplina
   * **B** (40–49 pkt) — Dopuszczalna dyscyplina (drobne opóźnienia)
   * **CCC** (30–39 pkt) — Podwyższone ryzyko
   * **CC** (20–29 pkt) — Wysokie ryzyko zadłużenia
   * **C** (10–19 pkt) — Krytyczne zadłużenie
   * **DDD** (5–9 pkt) — Niewypłacalność głęboka
   * **DD** (1–4 pkt) — Trwały brak kontaktu / zadłużenie
   * **D** (0 pkt) — Skrajna niewypłacalność
2. **Głosowania i Terminy Wymagalności (`terminy_glosowan`)**:
   * W praktyce składki są wymagane na głosowania/zebrania koła.
   * Każde koło definiuje własne parametry:
     * `data_zbiorki_od` oraz `data_wymagalnosci_do`
     * `dni_zbiorki_przed` (1–90 dni, np. 5–7 dni w małych kołach, 14–30 dni w dużych)
     * `dni_wymagalnosci_po` (dopuszczalny poślizg 0–30 dni)
   * **Waga czasowa (*time-decay*)**: `waga_czasu = exp(-0.0018 * dni_od_glosowania)` faworyzuje najświeższe zachowania płatnicze.
3. **Rating Koła = MEDIANA, a nie Średnia**:
   * Główny wskaźnik wiarygodności koła jest wyliczany jako **mediana statystyczna** (`statistics.median`) ze scoringów członków.
   * Średnia arytmetyczna jest podawana jedynie pomocniczo w nawiasie.
   * Mediana chroni koło przed zafałszowaniem wskaźnika przez pojedyncze osoby nieaktywne/dłużników.

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

