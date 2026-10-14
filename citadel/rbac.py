import hashlib
import secrets

UPRAWNIENIA = {
    "widzi_kraj": {"ADMIN", "SKARBNIK_KRAJOWY"},
    "widzi_region": {"ADMIN", "SKARBNIK_KRAJOWY", "SKARBNIK_REGIONU"},
    "akceptuje_wplaty": {"ADMIN", "SKARBNIK_KRAJOWY"},
    "bezposrednie_ksiegowanie": {"ADMIN", "SKARBNIK_KRAJOWY"},
    "reczne_naliczenia": {"ADMIN", "SKARBNIK_KRAJOWY"},
    "korekty_salda": {"ADMIN", "SKARBNIK_KRAJOWY"},
    "usuwa_czlonka": {"ADMIN", "SKARBNIK_KRAJOWY"},
    "zarzadza_struktura": {"ADMIN", "SKARBNIK_KRAJOWY"},
    "zarzadza_koszem": {"ADMIN"},
    "zarzadza_kontami": {"ADMIN"},
    "widzi_audyt": {"ADMIN"},
}

def moze(rola: str, akcja: str) -> bool:
    """Jedno miejsce prawdy dla weryfikacji uprawnień użytkownika."""
    dozwolone = UPRAWNIENIA.get(akcja, set())
    return rola in dozwolone

def pobierz_etykiete_roli(rola: str) -> str:
    return {
        "ADMIN": "👑 Admin",
        "SKARBNIK_KRAJOWY": "🇵🇱 Krajowy",
        "SKARBNIK_REGIONU": "📊 Region",
        "SKARBNIK_KOLA": "🏢 Koło"
    }.get(rola, rola)

def generuj_sol() -> str:
    return secrets.token_hex(16)

def hashuj_haslo(haslo: str, sol: str) -> str:
    h = hashlib.pbkdf2_hmac("sha256", haslo.encode("utf-8"), sol.encode("utf-8"), 200_000)
    return h.hex()

def weryfikuj_haslo(haslo: str, sol: str, oczekiwany_hash: str) -> bool:
    obliczony = hashuj_haslo(haslo, sol)
    return secrets.compare_digest(obliczony, oczekiwany_hash)