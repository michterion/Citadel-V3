# 🏰 Citadel V3 — System Zarządzania Strukturami i Ratingiem Wiarygodności

**Citadel V3** to kompleksowa platforma webowa dedykowana zarządzaniu finansami, strukturą organizacyjną, składkami członkowskimi oraz zaawansowaną oceną wiarygodności płatniczej w wielopoziomowych organizacjach (Kraj → Regiony → Koła → Członkowie).

Aplikacja integruje mechanizmy księgowości składek ze statutowym prawem głosu oraz autorskim silnikiem ratingowym **Celestia**.

---

## 🌟 Główne Moduły i Funkcjonalności

### 1. 🛡️ Silnik Ratingowy Celestia (Dyscyplina i Wiarygodność Płatnicza)
* **Indywidualny scoring (0–100 pkt) i skala AAA–DDD**:
  * `AAA`, `AA`, `A` — Klasa Prime (Wzorowa wiarygodność, brak opóźnień).
  * `BBB`, `BB`, `B` — Klasa Inwestycyjna (Dobra dyscyplina, drobne poślizgi bez utraty prawa głosu).
  * `CCC`, `CC`, `C` — Klasa Podwyższonego Ryzyka (Nieterminowość, narastające zaległości).
  * `DDD`, `DD`, `D` — Klasa Niewypłacalna / Dłużnicy z utratą praw członkowskich.
* **Punkty Zapadalności (Terminy Głosowań i Zebrań)**:
  * W praktyce organizacyjnej składki stają się wymagalne w perspektywie zebrań i głosowań.
  * **Elastyczne okno zbiórki**: Każde koło konfiguruje własną długość zbiórki (`dni_zbiorki_przed`: np. 5–7 dni w małych kołach, 14–30 dni w dużych) oraz dopuszczalny poślizg (`dni_wymagalnosci_po`).
  * **Wykładnicze zanikanie w czasie (*time-decay*)**: Ostatnie głosowania ważą najwięcej w ratingu (`exp(-0.0018 * dni)`).
* **Wagi Filarów i Odporność na Nadużycia**:
  * Główną wagę stanowią **Wpłaty w Oknie przed Głosowaniami (65%)**, uzupełniane przez **Bieżące Saldo (20%)**, **KDI (10%)** oraz **Rytm Płatności (5%)**.
  * Drobna, symboliczna wpłata po terminie nie zawyża ratingu dłużnika — okno poślizgu (3 dni) podnosi ocenę tylko wtedy, gdy wpłacona kwota faktycznie likwiduje powstałe zadłużenie.
  * **Ścisłe rozróżnienie prawa głosu**: Spłata poślizgowa daje 60 pkt tylko osobie, która na zebraniu zachowała prawo głosu (dług 2–6 msc). Osoba bez prawa głosu (dług > 6 msc) za spłatę ratunkową po fakcie otrzymuje jedynie 20 pkt, co zapobiega nagradzaniu bierności przed samym głosowaniem.
* **Indeks Wiarygodności Koła (Mediana)**:
  * Rating całego koła jest obliczany jako **mediana statystyczna** scoringów członków (`statistics.median`), co zapobiega zniekształceniu obrazu koła przez pojedynczego skrajnego dłużnika.

### 2. 💰 Finanse i Księgowość Składek
* **Jednostka groszowa (`BIGINT`)**: Wszystkie operacje finansowe w bazie danych oraz algorytmach są przeprowadzane w groszach całkowitych (`gr`), co całkowicie eliminuje błędy zaokrągleń zmiennoprzecinkowych IEEE 754.
* **KDI (Wskaźnik Dyscypliny Indywidualnej)**: Stosunek wpłaconych środków do wymaganych statutowo naliczeń.
* **Statutowe Prawo Głosu**: Automatyczna ewaluacja czy saldo członka pozwala na udział w głosowaniach (dopuszczalne zadłużenie do 2 miesięcy składek).
* **Obsługa wpłat i korekt**:
  * Formularz wpłat pojedynczych i szybkich księgowań.
  * Wpłaty zbiorcze (import z plików lub wklejanie danych).
  * Panel akceptacji wpłat oczekujących z kluczem idempotencji (`idempotency_key`), uniemożliwiającym podwójne zaksięgowanie tego samego przelewu.
  * Korekty salda i audytowane korekty kasy podręcznej.

### 3. 👥 Wielopoziomowa Struktura Organizacyjna
* **Widok Krajowy**: Globalny bilans finansowy, zestawienie wszystkich regionów, porównawczy wykres słupkowy KDI regionów.
* **Widok Regionalny**: Finanse regionu, lista kół, wskaźniki ściągalności składek i wykresy KDI kół w regionie.
* **Widok Koła**:
  * Bento-card z podsumowaniem kasy koła, liczby członków i uprawnionych do głosowania.
  * Zakładki: *Członkowie, Profile i Audyt, Celestia, Wpłaty, Zbiorcza, Akceptacje, Kasa Koła, Korekty, Ręczne naliczenia, Struktura, Kalkulator*.

### 4. 🔒 Bezpieczeństwo i RBAC
* **Role systemowe**:
  * `ADMIN` — Pełne zarządzanie strukturą, kontami, koszem i zaawansowanym audytem.
  * `SKARBNIK_KRAJOWY` — Nadzór nad wszystkimi regionami, akceptacja wpłat, ręczne naliczenia, korekty.
  * `SKARBNIK_REGIONU` — Wgląd analityczny w obrębie przypisanego regionu.
  * `SKARBNIK_KOLA` — Zarządzanie członkami i terminami głosowań własnego koła.
* **Centralna macierz uprawnień**: Realizowana przez funkcję `moze(rola, akcja)` w [`citadel/rbac.py`](file:///c:/Users/Micha%C5%82/Desktop/Citadel%20V3/citadel/rbac.py).
* **Haszowanie**: Standard PBKDF2-HMAC-SHA256 z 200 000 iteracji i unikalną 16-bajtową solą dla każdego użytkownika.

### 5. 🎨 Trzy Spójne Motywy Wizualne
Aplikacja posiada dopracowany system stylów CSS wstrzykiwany dynamicznie:
* 💜 **Fiolet (Domyślny)**: Głęboki fiolet z neonowymi akcentami (`#6b21a8`, `#9333ea`, `#c084fc`).
* 🖤 **Ciemny Mono (Dark Mono)**: Minimalistyczny, ciemny motyw grafitowy z wysokim kontrastem.
* 🤍 **Jasny Mono (Light Mono)**: Elegancki, czysty motyw jasny ze śnieżnobiałym tłem i ciemnymi kartami.
* Wykresy **Plotly** automatycznie adaptują kolory tła, czcionek i osi do aktywnego motywu (`czy_jasny_motyw()`).

---

## ⚡ Instalacja i Uruchomienie z `uv`

Projekt korzysta z nowoczesnego menedżera pakietów **[uv](https://astral.sh/uv)** (Astral).

### 1. Klonowanie i instalacja narzędzi
Upewnij się, że masz zainstalowany Python `>=3.11` oraz `uv`:
```powershell
# Instalacja uv w Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Alternatywnie przez pip:
pip install uv
```

### 2. Synchronizacja środowiska wirtualnego
W katalogu głównym projektu (`Citadel V3`):
```bash
uv sync
```
Polecenie to w kilka sekund utworzy folder `.venv` i zainstaluje zablokowane wersje z pliku `uv.lock`.

### 3. Konfiguracja połączenia z bazą PostgreSQL
W pliku `citadel/.streamlit/secrets.toml` wprowadź parametry bazy:
```toml
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "citadel_db"
DB_USER = "twoj_uzytkownik"
DB_PASSWORD = "twoje_bezpieczne_haslo"
DB_SSLMODE = "prefer"
```
*Uwaga: plik `.streamlit/secrets.toml` jest zabezpieczony w `.gitignore` przed przypadkowym wypchnięciem do repozytorium.*

### 4. Uruchomienie aplikacji
Z katalogu głównego projektu:
```powershell
uv run streamlit run citadel/app.py
```
lub przechodząc do folderu `citadel`:
```powershell
cd citadel
uv run streamlit run app.py
```
Możesz także po prostu kliknąć dwukrotnie plik **`citadel/Citadel_launch.bat`**.

---

## 📁 Struktura Katalogów

```
Citadel V3/
├── .gitignore                      # Reguły ignorowania dla gita (.venv, secrets, backups)
├── AGENTS.md                       # Pamięć projektu i wytyczne dla asystentów AI (Antigravity)
├── README.md                       # Niniejsza dokumentacja
├── pyproject.toml                  # Konfiguracja projektu PEP 621 oraz narzędzi uv, ruff, pytest
├── uv.lock                         # Deterministyczny zrzut wersji zależności
└── citadel/                        # Źródła aplikacji
    ├── app.py                      # Główny punkt wejścia aplikacji Streamlit
    ├── config.py                   # Motywy CSS, kolory KDI, strefa Europe/Warsaw, pomocniki
    ├── database.py                 # Pula połączeń PostgreSQL (psycopg3), schemat bazy, migracje
    ├── calculations.py             # Silnik naliczeń składek, KDI, prawa głosu i agregacji
    ├── celestia.py                 # Silnik ratingowy Celestia, wagi, audyt głosowań
    ├── rbac.py                     # Role, uprawnienia i bezpieczne haszowanie haseł
    ├── Citadel_launch.bat          # Skrypt uruchamiający Windows (uv run / python)
    ├── .streamlit/
    │   └── config.toml             # Konfiguracja serwera Streamlit
    ├── components/
    │   ├── charts.py               # Konfiguracja i generatory wykresów Plotly
    │   └── ui.py                   # Karty Bento, pigułki statusu, powiadomienia
    └── views/
        ├── view_kraj.py            # Dashboard widoku krajowego
        ├── view_region.py          # Dashboard widoku regionalnego
        ├── view_kolo.py            # Kontroler widoku koła
        └── kolo/                   # Poszczególne zakładki panelu koła (Celestia, Wpłaty, Kasa...)
```

---

## 🛠️ Narzędzia Jakości Kodu

```bash
# Formatowanie i analiza statyczna kodu (Ruff)
uv run ruff check citadel

# Automatyczna naprawa bezpiecznych reguł
uv run ruff check citadel --fix

# Uruchomienie testów
uv run pytest
```

# Automatyczna naprawa bezpiecznych reguł
uv run ruff check citadel --fix

# Uruchomienie testów
uv run pytest
```

