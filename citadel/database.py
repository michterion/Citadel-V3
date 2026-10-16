import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from config import WARSAW_TZ, teraz_utc
from psycopg_pool import ConnectionPool
from rbac import generuj_sol, hashuj_haslo


def get_db_conninfo():
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
        elif "postgres" in st.secrets:
            cfg = st.secrets["postgres"]
            ssl = f" sslmode={cfg.get('sslmode', 'require')}" if "sslmode" in cfg or "neon.tech" in str(cfg.get('host', '')) else ""
            return f"host={cfg['host']} port={cfg.get('port', 5432)} dbname={cfg['dbname']} user={cfg['user']} password='{cfg['password']}'" + ssl
    except Exception:
        pass
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    return None

@st.cache_resource
def get_db_pool():
    conninfo = get_db_conninfo()
    if not conninfo:
        try:
            st.error("⚠️ Brak konfiguracji bazy danych w secrets.toml lub zmiennej DATABASE_URL.")
            st.stop()
        except Exception:
            return None
    try:
        return ConnectionPool(conninfo=conninfo, min_size=1, max_size=5, open=True)
    except Exception:
        return None

pool = get_db_pool()

def db_query(sql: str, params=None) -> pd.DataFrame:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if cur.description:
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return pd.DataFrame(rows, columns=cols)
            return pd.DataFrame()

def db_execute(sql: str, params=None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()

def db_scalar(sql: str, params=None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return row[0] if row else None

DDL_SCHEMA_EXPORT = """-- === DEFINICJE STRUKTURY DANYCH (DDL) ===
CREATE TABLE IF NOT EXISTS kraje (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nazwa TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS regiony (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kraj_id BIGINT REFERENCES kraje(id) ON DELETE SET NULL,
    nazwa TEXT NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS kola (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kraj_id BIGINT REFERENCES kraje(id) ON DELETE RESTRICT DEFAULT 1,
    nazwa TEXT NOT NULL,
    region_id BIGINT REFERENCES regiony(id) ON DELETE SET NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    deleted_by_region_id BIGINT REFERENCES regiony(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS uzytkownicy (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    haslo_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    imie_nazwisko TEXT NOT NULL,
    rola TEXT NOT NULL CHECK (rola IN ('ADMIN', 'SKARBNIK_KRAJOWY', 'SKARBNIK_REGIONU', 'SKARBNIK_KOLA')),
    kraj_id BIGINT REFERENCES kraje(id) ON DELETE SET NULL,
    region_id BIGINT REFERENCES regiony(id) ON DELETE SET NULL,
    kolo_id BIGINT REFERENCES kola(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    wymus_zmiane_hasla BOOLEAN NOT NULL DEFAULT FALSE,
    sesja_wersja INT NOT NULL DEFAULT 1,
    ostatnie_logowanie TIMESTAMPTZ,
    ostatnia_aktywnosc TIMESTAMPTZ,
    utworzono_o TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS czlonkowie (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kolo_id BIGINT NOT NULL DEFAULT 1 REFERENCES kola(id) ON DELETE RESTRICT,
    imie_nazwisko TEXT NOT NULL,
    data_urodzenia DATE NOT NULL,
    data_przystapienia DATE NOT NULL,
    saldo_startowe_gr BIGINT DEFAULT 0,
    reczny_parametr TEXT DEFAULT 'AUTO'
);
CREATE TABLE IF NOT EXISTS wplaty (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE RESTRICT,
    czlonek_id BIGINT REFERENCES czlonkowie(id) ON DELETE SET NULL,
    kwota_gr BIGINT NOT NULL,
    data_wplaty DATE NOT NULL,
    notatka TEXT,
    data_wpisu TIMESTAMPTZ NOT NULL,
    idempotency_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS wplaty_oczekujace (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE RESTRICT,
    czlonek_id BIGINT REFERENCES czlonkowie(id) ON DELETE SET NULL,
    zglosil_uzytkownik_id BIGINT REFERENCES uzytkownicy(id) ON DELETE SET NULL,
    kwota_gr BIGINT NOT NULL CHECK (kwota_gr > 0),
    data_wplaty DATE NOT NULL CHECK (data_wplaty >= '2015-01-01'),
    notatka TEXT,
    oswiadczenie TEXT NOT NULL CHECK (oswiadczenie IN ('MAM_POTWIERDZENIE', 'BRAK_POTWIERDZENIA')),
    status TEXT NOT NULL DEFAULT 'OCZEKUJE' CHECK (status IN ('OCZEKUJE', 'ZAAKCEPTOWANA', 'ODRZUCONA')),
    idempotency_key TEXT UNIQUE,
    data_zgloszenia TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rozpatrzyl_uzytkownik_id BIGINT REFERENCES uzytkownicy(id) ON DELETE SET NULL,
    data_rozpatrzenia TIMESTAMPTZ,
    powod_odrzucenia TEXT
);
CREATE TABLE IF NOT EXISTS naliczenia_reczne (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    czlonek_id BIGINT NOT NULL REFERENCES czlonkowie(id) ON DELETE CASCADE,
    kwota_gr BIGINT NOT NULL,
    data_naliczenia DATE NOT NULL,
    tytul TEXT NOT NULL,
    data_wpisu TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS korekty (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    czlonek_id BIGINT NOT NULL REFERENCES czlonkowie(id) ON DELETE CASCADE,
    delta_gr BIGINT NOT NULL,
    docelowe_saldo_gr BIGINT NOT NULL,
    data_korekty DATE NOT NULL,
    powod TEXT,
    data_wpisu TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS wydatki (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE RESTRICT,
    kwota_gr BIGINT NOT NULL,
    data_wydatku DATE NOT NULL,
    kategoria TEXT,
    opis TEXT,
    data_wpisu TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS korekty_kasy (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE RESTRICT,
    delta_gr BIGINT NOT NULL,
    docelowy_stan_gr BIGINT NOT NULL,
    data_korekty DATE NOT NULL,
    powod TEXT,
    data_wpisu TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tabela VARCHAR(50) NOT NULL,
    operacja VARCHAR(10) NOT NULL,
    rekord_id BIGINT,
    stare_dane JSONB,
    nowe_dane JSONB,
    zmieniono_o TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS terminy_glosowan (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE CASCADE,
    data_glosowania DATE NOT NULL,
    data_zbiorki_od DATE,
    data_wymagalnosci_do DATE,
    dni_zbiorki_przed INT NOT NULL DEFAULT 14,
    dni_wymagalnosci_po INT NOT NULL DEFAULT 0,
    nazwa TEXT NOT NULL,
    opis TEXT,
    waga NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    typ_terminu TEXT NOT NULL DEFAULT 'GLOSOWANIE',
    utworzono_o TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    utworzono_przez BIGINT REFERENCES uzytkownicy(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_wplaty_czlonek_data ON wplaty(czlonek_id, data_wplaty);
CREATE INDEX IF NOT EXISTS idx_wplaty_kolo_data ON wplaty(kolo_id, data_wplaty);
CREATE INDEX IF NOT EXISTS idx_czlonkowie_kolo ON czlonkowie(kolo_id);
CREATE INDEX IF NOT EXISTS idx_naliczenia_reczne_czlonek ON naliczenia_reczne(czlonek_id, data_naliczenia);
CREATE INDEX IF NOT EXISTS idx_korekty_czlonek ON korekty(czlonek_id, data_korekty);
CREATE INDEX IF NOT EXISTS idx_wydatki_kolo_data ON wydatki(kolo_id, data_wydatku);
CREATE INDEX IF NOT EXISTS idx_korekty_kasy_kolo ON korekty_kasy(kolo_id, data_korekty);
CREATE INDEX IF NOT EXISTS idx_kola_region ON kola(region_id);
CREATE INDEX IF NOT EXISTS idx_kola_kraj ON kola(kraj_id);
CREATE INDEX IF NOT EXISTS idx_regiony_kraj ON regiony(kraj_id);
CREATE INDEX IF NOT EXISTS idx_wplaty_oczekujace_kolo ON wplaty_oczekujace(kolo_id);
CREATE INDEX IF NOT EXISTS idx_terminy_glosowan_kolo_data ON terminy_glosowan(kolo_id, data_glosowania);
"""

@st.cache_resource(show_spinner=False)
def init_db_once():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kraje (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    nazwa TEXT NOT NULL UNIQUE
                );
            """)
            cur.execute("INSERT INTO kraje (nazwa) VALUES ('Polska') ON CONFLICT (nazwa) DO NOTHING;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS regiony (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    kraj_id BIGINT REFERENCES kraje(id) ON DELETE SET NULL,
                    nazwa TEXT NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    deleted_at TIMESTAMPTZ
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kola (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    kraj_id BIGINT REFERENCES kraje(id) ON DELETE RESTRICT DEFAULT 1,
                    nazwa TEXT NOT NULL,
                    region_id BIGINT REFERENCES regiony(id) ON DELETE SET NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    deleted_at TIMESTAMPTZ,
                    deleted_by_region_id BIGINT REFERENCES regiony(id) ON DELETE SET NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS uzytkownicy (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    login TEXT NOT NULL UNIQUE,
                    haslo_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    imie_nazwisko TEXT NOT NULL,
                    rola TEXT NOT NULL CHECK (rola IN ('ADMIN', 'SKARBNIK_KRAJOWY', 'SKARBNIK_REGIONU', 'SKARBNIK_KOLA')),
                    kraj_id BIGINT REFERENCES kraje(id) ON DELETE SET NULL,
                    region_id BIGINT REFERENCES regiony(id) ON DELETE SET NULL,
                    kolo_id BIGINT REFERENCES kola(id) ON DELETE SET NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    wymus_zmiane_hasla BOOLEAN NOT NULL DEFAULT FALSE,
                    sesja_wersja INT NOT NULL DEFAULT 1,
                    ostatnie_logowanie TIMESTAMPTZ,
                    ostatnia_aktywnosc TIMESTAMPTZ,
                    utworzono_o TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_uzytkownicy_login ON uzytkownicy(login);
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_aktywne_kola_nazwa 
                ON kola (nazwa) WHERE (is_deleted = FALSE);
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_aktywne_regiony_nazwa 
                ON regiony (kraj_id, nazwa) WHERE (is_deleted = FALSE);
            """)
            cur.execute("""
                CREATE OR REPLACE VIEW aktywne_regiony AS
                SELECT * FROM regiony WHERE is_deleted = FALSE;
            """)
            cur.execute("""
                CREATE OR REPLACE VIEW aktywne_kola AS
                SELECT * FROM kola WHERE is_deleted = FALSE;
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS czlonkowie (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    kolo_id BIGINT NOT NULL DEFAULT 1 REFERENCES kola(id) ON DELETE RESTRICT,
                    imie_nazwisko TEXT NOT NULL,
                    data_urodzenia DATE NOT NULL,
                    data_przystapienia DATE NOT NULL,
                    saldo_startowe_gr BIGINT DEFAULT 0,
                    reczny_parametr TEXT DEFAULT 'AUTO'
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wplaty (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE RESTRICT,
                    czlonek_id BIGINT REFERENCES czlonkowie(id) ON DELETE SET NULL,
                    kwota_gr BIGINT NOT NULL,
                    data_wplaty DATE NOT NULL,
                    notatka TEXT,
                    data_wpisu TIMESTAMPTZ NOT NULL,
                    idempotency_key TEXT UNIQUE
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wplaty_oczekujace (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE RESTRICT,
                    czlonek_id BIGINT REFERENCES czlonkowie(id) ON DELETE SET NULL,
                    zglosil_uzytkownik_id BIGINT REFERENCES uzytkownicy(id) ON DELETE SET NULL,
                    kwota_gr BIGINT NOT NULL CHECK (kwota_gr > 0),
                    data_wplaty DATE NOT NULL CHECK (data_wplaty >= '2015-01-01'),
                    notatka TEXT,
                    oswiadczenie TEXT NOT NULL CHECK (oswiadczenie IN ('MAM_POTWIERDZENIE', 'BRAK_POTWIERDZENIA')),
                    status TEXT NOT NULL DEFAULT 'OCZEKUJE' CHECK (status IN ('OCZEKUJE', 'ZAAKCEPTOWANA', 'ODRZUCONA')),
                    idempotency_key TEXT UNIQUE,
                    data_zgloszenia TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    rozpatrzyl_uzytkownik_id BIGINT REFERENCES uzytkownicy(id) ON DELETE SET NULL,
                    data_rozpatrzenia TIMESTAMPTZ,
                    powod_odrzucenia TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_wplaty_oczekujace_status ON wplaty_oczekujace(status);
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS naliczenia_reczne (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    czlonek_id BIGINT NOT NULL REFERENCES czlonkowie(id) ON DELETE CASCADE,
                    kwota_gr BIGINT NOT NULL,
                    data_naliczenia DATE NOT NULL,
                    tytul TEXT NOT NULL,
                    data_wpisu TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS korekty (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    czlonek_id BIGINT NOT NULL REFERENCES czlonkowie(id) ON DELETE CASCADE,
                    delta_gr BIGINT NOT NULL,
                    docelowe_saldo_gr BIGINT NOT NULL,
                    data_korekty DATE NOT NULL,
                    powod TEXT,
                    data_wpisu TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wydatki (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE RESTRICT,
                    kwota_gr BIGINT NOT NULL,
                    data_wydatku DATE NOT NULL,
                    kategoria TEXT,
                    opis TEXT,
                    data_wpisu TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS korekty_kasy (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE RESTRICT,
                    delta_gr BIGINT NOT NULL,
                    docelowy_stan_gr BIGINT NOT NULL,
                    data_korekty DATE NOT NULL,
                    powod TEXT,
                    data_wpisu TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    tabela VARCHAR(50) NOT NULL,
                    operacja VARCHAR(10) NOT NULL,
                    rekord_id BIGINT,
                    stare_dane JSONB,
                    nowe_dane JSONB,
                    zmieniono_o TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS terminy_glosowan (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    kolo_id BIGINT NOT NULL REFERENCES kola(id) ON DELETE CASCADE,
                    data_glosowania DATE NOT NULL,
                    data_zbiorki_od DATE,
                    data_wymagalnosci_do DATE,
                    dni_zbiorki_przed INT NOT NULL DEFAULT 14,
                    dni_wymagalnosci_po INT NOT NULL DEFAULT 0,
                    nazwa TEXT NOT NULL,
                    opis TEXT,
                    waga NUMERIC(3,2) NOT NULL DEFAULT 1.0,
                    typ_terminu TEXT NOT NULL DEFAULT 'GLOSOWANIE',
                    utworzono_o TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    utworzono_przez BIGINT REFERENCES uzytkownicy(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_log_tabela_czas ON audit_log(tabela, zmieniono_o DESC);
            """)

            # Bezpieczne migracje kolumn dla kompatybilności wstecznej
            cur.execute("ALTER TABLE uzytkownicy ADD COLUMN IF NOT EXISTS sesja_wersja INT NOT NULL DEFAULT 1;")
            cur.execute("ALTER TABLE uzytkownicy ADD COLUMN IF NOT EXISTS ostatnia_aktywnosc TIMESTAMPTZ;")
            cur.execute("ALTER TABLE wplaty_oczekujace ADD COLUMN IF NOT EXISTS idempotency_key TEXT UNIQUE;")
            cur.execute("ALTER TABLE terminy_glosowan ADD COLUMN IF NOT EXISTS data_zbiorki_od DATE;")
            cur.execute("ALTER TABLE terminy_glosowan ADD COLUMN IF NOT EXISTS data_wymagalnosci_do DATE;")
            cur.execute("ALTER TABLE terminy_glosowan ADD COLUMN IF NOT EXISTS dni_zbiorki_przed INT NOT NULL DEFAULT 14;")
            cur.execute("ALTER TABLE terminy_glosowan ADD COLUMN IF NOT EXISTS dni_wymagalnosci_po INT NOT NULL DEFAULT 0;")
            cur.execute("ALTER TABLE terminy_glosowan ADD COLUMN IF NOT EXISTS typ_terminu TEXT NOT NULL DEFAULT 'GLOSOWANIE';")

            # Indeksy wydajnościowe na kluczach obcych i filtrach
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_wplaty_czlonek_data ON wplaty(czlonek_id, data_wplaty);
                CREATE INDEX IF NOT EXISTS idx_wplaty_kolo_data ON wplaty(kolo_id, data_wplaty);
                CREATE INDEX IF NOT EXISTS idx_czlonkowie_kolo ON czlonkowie(kolo_id);
                CREATE INDEX IF NOT EXISTS idx_naliczenia_reczne_czlonek ON naliczenia_reczne(czlonek_id, data_naliczenia);
                CREATE INDEX IF NOT EXISTS idx_korekty_czlonek ON korekty(czlonek_id, data_korekty);
                CREATE INDEX IF NOT EXISTS idx_wydatki_kolo_data ON wydatki(kolo_id, data_wydatku);
                CREATE INDEX IF NOT EXISTS idx_korekty_kasy_kolo ON korekty_kasy(kolo_id, data_korekty);
                CREATE INDEX IF NOT EXISTS idx_kola_region ON kola(region_id);
                CREATE INDEX IF NOT EXISTS idx_kola_kraj ON kola(kraj_id);
                CREATE INDEX IF NOT EXISTS idx_regiony_kraj ON regiony(kraj_id);
                CREATE INDEX IF NOT EXISTS idx_wplaty_oczekujace_kolo ON wplaty_oczekujace(kolo_id);
                CREATE INDEX IF NOT EXISTS idx_terminy_glosowan_kolo_data ON terminy_glosowan(kolo_id, data_glosowania);
            """)

            # PRZYWRÓCENIE TRIGGERA AUDYTU
            cur.execute("""
                CREATE OR REPLACE FUNCTION audit_trigger_func()
                RETURNS TRIGGER AS $$
                DECLARE
                    v_stare_dane JSONB := NULL;
                    v_nowe_dane JSONB := NULL;
                    v_rekord_id BIGINT := NULL;
                BEGIN
                    IF (TG_OP = 'DELETE') THEN
                        v_stare_dane := to_jsonb(OLD);
                        v_rekord_id := OLD.id;
                    ELSIF (TG_OP = 'UPDATE') THEN
                        -- Ignoruj update'y wyłącznie aktywności / logowania (ochrona audit_log przed puchnięciem)
                        IF TG_TABLE_NAME = 'uzytkownicy' THEN
                            IF (OLD.login = NEW.login AND 
                                OLD.haslo_hash = NEW.haslo_hash AND 
                                OLD.salt = NEW.salt AND 
                                OLD.imie_nazwisko = NEW.imie_nazwisko AND 
                                OLD.rola = NEW.rola AND 
                                OLD.kraj_id IS NOT DISTINCT FROM NEW.kraj_id AND 
                                OLD.region_id IS NOT DISTINCT FROM NEW.region_id AND 
                                OLD.kolo_id IS NOT DISTINCT FROM NEW.kolo_id AND 
                                OLD.is_active = NEW.is_active AND 
                                OLD.wymus_zmiane_hasla = NEW.wymus_zmiane_hasla AND 
                                OLD.sesja_wersja = NEW.sesja_wersja) THEN
                                RETURN NEW;
                            END IF;
                        END IF;

                        v_stare_dane := to_jsonb(OLD);
                        v_nowe_dane := to_jsonb(NEW);
                        v_rekord_id := NEW.id;
                    ELSIF (TG_OP = 'INSERT') THEN
                        v_nowe_dane := to_jsonb(NEW);
                        v_rekord_id := NEW.id;
                    END IF;

                    -- Ochrona poufności: wycinamy hashe haseł i sól
                    IF TG_TABLE_NAME = 'uzytkownicy' THEN
                        IF v_stare_dane IS NOT NULL THEN
                            v_stare_dane := v_stare_dane - 'haslo_hash' - 'salt';
                        END IF;
                        IF v_nowe_dane IS NOT NULL THEN
                            v_nowe_dane := v_nowe_dane - 'haslo_hash' - 'salt';
                        END IF;
                    END IF;

                    INSERT INTO audit_log (tabela, operacja, rekord_id, stare_dane, nowe_dane, zmieniono_o)
                    VALUES (TG_TABLE_NAME, TG_OP, v_rekord_id, v_stare_dane, v_nowe_dane, CURRENT_TIMESTAMP);

                    RETURN COALESCE(NEW, OLD);
                END;
                $$ LANGUAGE plpgsql;
            """)

            cur.execute("""
                DO $$
                DECLARE
                    t TEXT;
                    tabele TEXT[] := ARRAY[
                        'kraje', 'regiony', 'kola', 'uzytkownicy', 'czlonkowie', 
                        'wplaty', 'wplaty_oczekujace', 'naliczenia_reczne', 
                        'korekty', 'wydatki', 'korekty_kasy', 'terminy_glosowan'
                    ];
                BEGIN
                    FOREACH t IN ARRAY tabele LOOP
                        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON %I;', t, t);
                        EXECUTE format('CREATE TRIGGER trg_audit_%I
                                        AFTER INSERT OR UPDATE OR DELETE ON %I
                                        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();', t, t);
                    END LOOP;
                END $$;
            """)

            cur.execute("SELECT COUNT(*) FROM uzytkownicy WHERE rola = 'ADMIN';")
            if cur.fetchone()[0] == 0:
                s_salt = generuj_sol()
                s_pass_hash = hashuj_haslo("Centauri2026!", s_salt)
                cur.execute("""
                    INSERT INTO uzytkownicy (login, haslo_hash, salt, imie_nazwisko, rola, is_active, wymus_zmiane_hasla, sesja_wersja)
                    VALUES ('admin', %s, %s, 'Super Administrator', 'ADMIN', TRUE, TRUE, 1);
                """, (s_pass_hash, s_salt))
        conn.commit()
    return True

@st.cache_data(ttl=60, show_spinner=False)
def pobierz_slownik_krajow():
    return db_query("SELECT id, nazwa FROM kraje ORDER BY id ASC")

@st.cache_data(ttl=60, show_spinner=False)
def pobierz_slownik_regionow(kraj_id):
    return db_query("SELECT id, nazwa FROM aktywne_regiony WHERE kraj_id = %s ORDER BY nazwa ASC", (kraj_id,))

@st.cache_data(ttl=60, show_spinner=False)
def pobierz_liczbe_kol_bez_regionu(kraj_id):
    return db_scalar("SELECT COUNT(*) FROM aktywne_kola WHERE region_id IS NULL AND kraj_id = %s", (kraj_id,)) or 0

@st.cache_data(ttl=60, show_spinner=False)
def pobierz_aktywne_kola_kraju(kraj_id):
    return db_query("""
        SELECT k.id, k.nazwa, k.region_id, r.nazwa as region_nazwa
        FROM aktywne_kola k
        LEFT JOIN aktywne_regiony r ON k.region_id = r.id
        WHERE k.kraj_id = %s
        ORDER BY k.nazwa ASC
    """, (kraj_id,))

def usun_czlonka_bezpiecznie(czlonek_id: int):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT imie_nazwisko FROM czlonkowie WHERE id = %s", (czlonek_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Członek o ID #{czlonek_id} nie istnieje lub został już usunięty.")
            nazwa_czlonka = row[0]

            cur.execute("""
                UPDATE wplaty 
                SET czlonek_id = NULL,
                    notatka = COALESCE(notatka, '') || ' [Wpłata usuniętego członka: ' || %s || ']'
                WHERE czlonek_id = %s
            """, (nazwa_czlonka, czlonek_id))

            cur.execute("DELETE FROM naliczenia_reczne WHERE czlonek_id = %s", (czlonek_id,))
            cur.execute("DELETE FROM korekty WHERE czlonek_id = %s", (czlonek_id,))
            cur.execute("DELETE FROM czlonkowie WHERE id = %s", (czlonek_id,))
        conn.commit()
    st.cache_data.clear()

def przenies_kolo_do_kosza(kolo_id: int):
    teraz = teraz_utc()
    db_execute("""
        UPDATE kola 
        SET is_deleted = TRUE, deleted_at = %s, deleted_by_region_id = NULL 
        WHERE id = %s
    """, (teraz, kolo_id))
    st.cache_data.clear()

def przywroc_kolo_z_kosza(kolo_id: int):
    region_info = db_query("""
        SELECT r.nazwa, r.is_deleted 
        FROM kola k 
        JOIN regiony r ON k.region_id = r.id 
        WHERE k.id = %s
    """, (kolo_id,))

    if not region_info.empty and region_info.iloc[0]["is_deleted"]:
        nazwa_r = region_info.iloc[0]["nazwa"]
        raise ValueError(f"Nie można przywrócić koła: jego region nadrzędny ('{nazwa_r}') znajduje się w koszu!")

    db_execute("""
        UPDATE kola 
        SET is_deleted = FALSE, deleted_at = NULL, deleted_by_region_id = NULL 
        WHERE id = %s
    """, (kolo_id,))
    st.cache_data.clear()

def przenies_region_do_kosza(region_id: int):
    teraz = teraz_utc()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE regiony SET is_deleted = TRUE, deleted_at = %s WHERE id = %s", (teraz, region_id))
            cur.execute("""
                UPDATE kola 
                SET is_deleted = TRUE, deleted_at = %s, deleted_by_region_id = %s 
                WHERE region_id = %s AND is_deleted = FALSE
            """, (teraz, region_id, region_id))
        conn.commit()
    st.cache_data.clear()

def przywroc_region_z_kosza(region_id: int):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE kola 
                SET is_deleted = FALSE, deleted_at = NULL, deleted_by_region_id = NULL 
                WHERE region_id = %s AND is_deleted = TRUE AND deleted_by_region_id = %s
            """, (region_id, region_id))
            cur.execute("UPDATE regiony SET is_deleted = FALSE, deleted_at = NULL WHERE id = %s", (region_id,))
        conn.commit()
    st.cache_data.clear()

def _usun_kolo_trwale_w_transakcji(cur, kolo_id: int):
    cur.execute("DELETE FROM wplaty WHERE kolo_id = %s OR czlonek_id IN (SELECT id FROM czlonkowie WHERE kolo_id = %s)", (kolo_id, kolo_id))
    cur.execute("DELETE FROM wplaty_oczekujace WHERE kolo_id = %s", (kolo_id,))
    cur.execute("DELETE FROM naliczenia_reczne WHERE czlonek_id IN (SELECT id FROM czlonkowie WHERE kolo_id = %s)", (kolo_id,))
    cur.execute("DELETE FROM korekty WHERE czlonek_id IN (SELECT id FROM czlonkowie WHERE kolo_id = %s)", (kolo_id,))
    cur.execute("DELETE FROM czlonkowie WHERE kolo_id = %s", (kolo_id,))
    cur.execute("DELETE FROM wydatki WHERE kolo_id = %s", (kolo_id,))
    cur.execute("DELETE FROM korekty_kasy WHERE kolo_id = %s", (kolo_id,))
    cur.execute("DELETE FROM kola WHERE id = %s", (kolo_id,))

def usun_kolo_trwale(kolo_id: int):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_deleted FROM kola WHERE id = %s", (kolo_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                raise ValueError("Nie można trwale usunąć aktywnego koła! Przenieś je najpierw do kosza.")
            _usun_kolo_trwale_w_transakcji(cur, kolo_id)
        conn.commit()
    st.cache_data.clear()

def usun_region_trwale(region_id: int):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_deleted FROM regiony WHERE id = %s", (region_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                raise ValueError("Nie można trwale usunąć aktywnego regionu! Przenieś go najpierw do kosza.")

            cur.execute("SELECT id FROM kola WHERE region_id = %s", (region_id,))
            kolo_ids = [r[0] for r in cur.fetchall()]
            for k_id in kolo_ids:
                _usun_kolo_trwale_w_transakcji(cur, k_id)

            cur.execute("DELETE FROM regiony WHERE id = %s", (region_id,))
        conn.commit()
    st.cache_data.clear()

def format_val_sql(v):
    if v is None:
        return "NULL"
    elif isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False).replace("'", "''")
        return f"'{s}'"
    else:
        s = str(v).replace("'", "''")
        return f"'{s}'"

def generuj_zrzut_bazy_sql():
    os.makedirs("backups", exist_ok=True)
    timestamp_str = datetime.now(WARSAW_TZ).strftime("%Y%m%d_%H%M%S")
    filename = f"citadel_backup_{timestamp_str}.sql"
    filepath = os.path.join("backups", filename)

    tabele_parent_to_child = [
        "kraje", "regiony", "kola", "uzytkownicy", "czlonkowie",
        "wplaty", "wplaty_oczekujace", "naliczenia_reczne", "korekty", "wydatki", "korekty_kasy", "terminy_glosowan", "audit_log"
    ]
    tabele_child_to_parent = tabele_parent_to_child[::-1]

    with open(filepath, "w", encoding="utf-8") as f_out:
        f_out.write("-- =========================================================================\n")
        f_out.write("-- CITADEL NG — PEŁNY ZRZUT BAZY DANYCH (POSTGRESQL)\n")
        f_out.write(f"-- Data wygenerowania: {datetime.now(WARSAW_TZ).strftime('%Y-%m-%d %H:%M:%S')} (Warszawa)\n")
        f_out.write("-- Silnik: Citadel Native Python Engine\n")
        f_out.write("-- =========================================================================\n\n")
        f_out.write("SET statement_timeout = 0;\n")
        f_out.write("SET client_encoding = 'UTF8';\n")
        f_out.write("SET standard_conforming_strings = on;\n")
        f_out.write("SET check_function_bodies = false;\n")
        f_out.write("SET client_min_messages = warning;\n")
        f_out.write("SET row_security = off;\n")
        f_out.write("SET session_replication_role = replica;\n\n")
        f_out.write("BEGIN;\n\n")
        f_out.write(DDL_SCHEMA_EXPORT)
        f_out.write("\n-- === CZYSZCZENIE DANYCH PRZED IMPORTEM ===\n")

        truncate_list = ", ".join([f'"{t}"' for t in tabele_child_to_parent])
        f_out.write(f"TRUNCATE TABLE {truncate_list} CASCADE;\n\n")

        with pool.connection() as conn:
            with conn.cursor() as cur:
                for tab in tabele_parent_to_child:
                    cur.execute("""
                        SELECT column_name, identity_generation
                        FROM information_schema.columns 
                        WHERE table_name = %s 
                        ORDER BY ordinal_position
                    """, (tab,))
                    cols_info = cur.fetchall()
                    if not cols_info:
                        continue

                    col_names = [c[0] for c in cols_info]
                    has_always_identity = any(c[1] == 'ALWAYS' for c in cols_info)
                    overriding_clause = " OVERRIDING SYSTEM VALUE" if has_always_identity else ""
                    col_names_escaped = ", ".join([f'"{c}"' for c in col_names])

                    cur.execute(f'SELECT {col_names_escaped} FROM "{tab}" ORDER BY id ASC')
                    rows = cur.fetchall()

                    f_out.write(f"\n-- Tabela: {tab} ({len(rows)} rekordów)\n")
                    for r in rows:
                        vals = [format_val_sql(v) for v in r]
                        f_out.write(f'INSERT INTO "{tab}" ({col_names_escaped}){overriding_clause} VALUES ({", ".join(vals)});\n')

                    if rows:
                        f_out.write(f'SELECT setval(pg_get_serial_sequence(\'"{tab}"\', \'id\'), COALESCE(max(id), 1)) FROM "{tab}";\n')

        f_out.write("\nCOMMIT;\n\n")
        f_out.write("SET session_replication_role = DEFAULT;\n")

    file_size_kb = os.path.getsize(filepath) / 1024.0
    return filepath, filename, file_size_kb, "Citadel Python Engine (FK-safe + RBAC)"

def pobierz_terminy_glosowan_kola(kolo_id: int):
    """Pobiera wszystkie zarejestrowane terminy głosowań / wymagalności dla danego koła."""
    return db_query("""
        SELECT tg.id, tg.kolo_id, tg.data_glosowania, tg.data_zbiorki_od, tg.data_wymagalnosci_do,
               tg.dni_zbiorki_przed, tg.dni_wymagalnosci_po, tg.nazwa, tg.opis, tg.waga, tg.typ_terminu,
               tg.utworzono_o, tg.utworzono_przez, u.imie_nazwisko as dodal_imie
        FROM terminy_glosowan tg
        LEFT JOIN uzytkownicy u ON tg.utworzono_przez = u.id
        WHERE tg.kolo_id = %s
        ORDER BY tg.data_glosowania DESC, tg.id DESC
    """, (kolo_id,))

def dodaj_termin_glosowania(
    kolo_id: int,
    data_glosowania,
    nazwa: str,
    data_zbiorki_od = None,
    data_wymagalnosci_do = None,
    dni_zbiorki_przed: int = 14,
    dni_wymagalnosci_po: int = 0,
    opis: str = None,
    waga: float = 1.0,
    typ_terminu: str = "GLOSOWANIE",
    user_id: int = None
):
    """Rejestruje nowy termin głosowania lub zbiórki kwartalnej dla koła."""
    db_execute("""
        INSERT INTO terminy_glosowan (
            kolo_id, data_glosowania, data_zbiorki_od, data_wymagalnosci_do,
            dni_zbiorki_przed, dni_wymagalnosci_po, nazwa, opis, waga, typ_terminu, utworzono_przez
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        kolo_id, data_glosowania, data_zbiorki_od, data_wymagalnosci_do,
        int(dni_zbiorki_przed), int(dni_wymagalnosci_po), nazwa.strip(),
        opis.strip() if opis else None, float(waga), typ_terminu, user_id
    ))

def usun_termin_glosowania(termin_id: int, kolo_id: int):
    """Usuwa termin głosowania dla danego koła."""
    db_execute("""
        DELETE FROM terminy_glosowan
        WHERE id = %s AND kolo_id = %s
    """, (termin_id, kolo_id))