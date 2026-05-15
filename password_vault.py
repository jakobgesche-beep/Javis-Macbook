"""
Verschlüsselter Passwort-Vault für Jarvis.
Speichert Passwörter mit Website, erkennt falsche Logins über Browser-Monitoring.
"""

import json
import os
import re
import subprocess
import hashlib
import base64
import secrets
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
VAULT_FILE = BASE_DIR / "data" / "vault.enc"
VAULT_META = BASE_DIR / "data" / "vault_meta.json"

# Login-Fehler-Muster die im Browser-Titel / URL auftauchen
LOGIN_ERROR_PATTERNS = [
    r"(wrong|incorrect|invalid|failed|error).{0,20}(password|credentials|login)",
    r"(password|credentials|login).{0,20}(wrong|incorrect|invalid|failed|error)",
    r"authentication.{0,20}fail(ed)?",
    r"login.{0,20}fail(ed)?",
    r"sign.?in.{0,20}fail(ed)?",
    r"ungültig(es)?.{0,20}(passwort|kennwort)",
    r"falsches?.{0,20}(passwort|kennwort)",
    r"passwort.{0,20}(falsch|ungültig|fehlgeschlagen)",
    r"access.{0,20}denied",
    r"zugang.{0,20}verweigert",
    r"too many.{0,10}attempt",
    r"account.{0,20}lock(ed)?",
    r"konto.{0,20}gesperrt",
    r"401", r"403",
    r"nicht autorisiert",
    r"unauthorized",
]

LOGIN_SUCCESS_PATTERNS = [
    r"(welcome|willkommen).{0,30}",
    r"dashboard", r"home", r"feed", r"timeline",
    r"signed.{0,5}in", r"logged.{0,5}in",
    r"erfolgreich.{0,20}(angemeldet|eingeloggt)",
]

PASSWORD_LIKE = re.compile(
    r'^(?=.*[A-Za-z])(?=.*\d|.*[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~])[A-Za-z\d!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]{8,64}$'
)


# ─── Verschlüsselung ──────────────────────────────────────────────────────────

def _get_machine_id() -> str:
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "Hardware UUID" in line:
                return line.split(":")[1].strip()
    except Exception:
        pass
    return "jarvis-default-machine-id"


def _derive_key(master_password: str = "") -> bytes:
    machine_id = _get_machine_id()
    base = (machine_id + master_password + "jarvis-vault-v1").encode()
    key = hashlib.pbkdf2_hmac("sha256", base, b"jarvis-salt-2024", 200_000)
    return base64.urlsafe_b64encode(key[:32])


def _xor_cipher(data: bytes, key: bytes) -> bytes:
    key_stream = (key * ((len(data) // len(key)) + 1))[:len(data)]
    return bytes(a ^ b for a, b in zip(data, key_stream))


def _encrypt(plaintext: str, master_password: str = "") -> str:
    key = _derive_key(master_password)
    salt = secrets.token_bytes(16)
    data = plaintext.encode("utf-8")
    encrypted = _xor_cipher(data, key + salt)
    return base64.b64encode(salt + encrypted).decode()


def _decrypt(ciphertext: str, master_password: str = "") -> str:
    key = _derive_key(master_password)
    raw = base64.b64decode(ciphertext.encode())
    salt = raw[:16]
    encrypted = raw[16:]
    decrypted = _xor_cipher(encrypted, key + salt)
    return decrypted.decode("utf-8")


# ─── Vault ────────────────────────────────────────────────────────────────────

class PasswordVault:

    def __init__(self, master_password: str = ""):
        self.master_password = master_password
        os.makedirs(BASE_DIR / "data", exist_ok=True)
        self._entries: list[dict] = []
        self._load()

    def _load(self):
        if not VAULT_FILE.exists():
            self._entries = []
            return
        try:
            raw = VAULT_FILE.read_text()
            decrypted = _decrypt(raw, self.master_password)
            self._entries = json.loads(decrypted)
        except Exception:
            self._entries = []

    def _save(self):
        data = json.dumps(self._entries, ensure_ascii=False, indent=2)
        encrypted = _encrypt(data, self.master_password)
        VAULT_FILE.write_text(encrypted)

    def add(self, site: str, username: str, password: str, source: str = "manual") -> dict:
        entry = {
            "id": secrets.token_hex(8),
            "site": site.strip(),
            "username": username.strip(),
            "password": password,
            "source": source,
            "status": "unknown",
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "wrong_attempts": 0,
            "notes": ""
        }
        # Duplikat prüfen
        for e in self._entries:
            if e["site"] == entry["site"] and e["username"] == entry["username"]:
                e["password"] = password
                e["last_used"] = datetime.now().isoformat()
                self._save()
                return e
        self._entries.append(entry)
        self._save()
        return entry

    def get_all(self) -> list[dict]:
        result = []
        for e in self._entries:
            safe = dict(e)
            safe["password_masked"] = "•" * min(len(e["password"]), 12)
            result.append(safe)
        return result

    def get_for_site(self, site: str) -> list[dict]:
        site_lower = site.lower()
        return [e for e in self._entries if site_lower in e["site"].lower()]

    def get_password(self, entry_id: str) -> str | None:
        for e in self._entries:
            if e["id"] == entry_id:
                return e["password"]
        return None

    def mark_wrong(self, entry_id: str):
        for e in self._entries:
            if e["id"] == entry_id:
                e["status"] = "wrong"
                e["wrong_attempts"] = e.get("wrong_attempts", 0) + 1
                self._save()
                return True
        return False

    def mark_ok(self, entry_id: str):
        for e in self._entries:
            if e["id"] == entry_id:
                e["status"] = "ok"
                e["last_used"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def delete(self, entry_id: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        if len(self._entries) < before:
            self._save()
            return True
        return False

    def update_notes(self, entry_id: str, notes: str):
        for e in self._entries:
            if e["id"] == entry_id:
                e["notes"] = notes
                self._save()
                return True
        return False

    def count(self) -> dict:
        return {
            "total": len(self._entries),
            "ok": sum(1 for e in self._entries if e["status"] == "ok"),
            "wrong": sum(1 for e in self._entries if e["status"] == "wrong"),
            "unknown": sum(1 for e in self._entries if e["status"] == "unknown"),
        }


# ─── Clipboard-Monitor ────────────────────────────────────────────────────────

_last_clipboard = ""


def get_clipboard() -> str:
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
        return result.stdout.strip()
    except Exception:
        return ""


def clipboard_looks_like_password(text: str) -> bool:
    if len(text) < 8 or len(text) > 128:
        return False
    if "\n" in text or "\t" in text:
        return False
    return bool(PASSWORD_LIKE.match(text))


def check_clipboard_for_password() -> str | None:
    global _last_clipboard
    current = get_clipboard()
    if current != _last_clipboard:
        _last_clipboard = current
        if clipboard_looks_like_password(current):
            return current
    return None


# ─── Browser-Monitor ─────────────────────────────────────────────────────────

def get_browser_state() -> dict:
    script = """
    try
        tell application "Google Chrome"
            set t to title of active tab of front window
            set u to URL of active tab of front window
            return t & "|||" & u
        end tell
    on error
        return "|||"
    end try
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=3
        )
        parts = result.stdout.strip().split("|||")
        return {
            "title": parts[0].strip() if parts else "",
            "url": parts[1].strip() if len(parts) > 1 else ""
        }
    except Exception:
        return {"title": "", "url": ""}


def extract_domain(url: str) -> str:
    match = re.search(r"https?://(?:www\.)?([^/\?]+)", url)
    return match.group(1) if match else url


def detect_login_error(title: str, url: str) -> bool:
    text = (title + " " + url).lower()
    for pattern in LOGIN_ERROR_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def detect_login_success(title: str, url: str) -> bool:
    text = (title + " " + url).lower()
    for pattern in LOGIN_SUCCESS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ─── Singleton ────────────────────────────────────────────────────────────────

_vault: PasswordVault | None = None


def get_vault(master_password: str = "") -> PasswordVault:
    global _vault
    if _vault is None:
        _vault = PasswordVault(master_password)
    return _vault
