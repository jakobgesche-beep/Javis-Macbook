"""
Auto-Updater: prüft GitHub Releases und installiert neue Version ohne manuellen Download.
"""

import os
import subprocess
import threading
import time
from pathlib import Path

GITHUB_API = "https://api.github.com/repos/jakobgesche-beep/Javis-Macbook/releases/latest"
CURRENT_VERSION = "1.0.2"
APP_BUNDLE = Path("/Applications/Jarvis.app")


def _parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("v").split("."))


def check_for_update() -> dict | None:
    try:
        import requests
        r = requests.get(GITHUB_API, timeout=10, headers={"Accept": "application/vnd.github+json"})
        data = r.json()
        latest = data.get("tag_name", "").lstrip("v")
        if not latest:
            return None
        if _parse_version(latest) > _parse_version(CURRENT_VERSION):
            for asset in data.get("assets", []):
                if asset["name"].endswith(".dmg"):
                    return {"version": latest, "url": asset["browser_download_url"], "name": asset["name"]}
    except Exception:
        pass
    return None


def install_update(update_info: dict, progress_cb=None) -> bool:
    """
    Lädt DMG, mountet es, kopiert .app nach /Applications und startet neu.
    Muss in einem Background-Thread laufen.
    """
    import requests
    import tempfile

    try:
        dmg_path = Path(tempfile.mktemp(suffix=".dmg"))

        if progress_cb:
            progress_cb("Lade Update herunter…")
        r = requests.get(update_info["url"], stream=True, timeout=180)
        r.raise_for_status()
        with open(dmg_path, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)

        if progress_cb:
            progress_cb("Installiere…")
        attach = subprocess.run(
            ["hdiutil", "attach", str(dmg_path), "-nobrowse", "-quiet"],
            capture_output=True, text=True, check=True,
        )

        mount_point = None
        for line in attach.stdout.splitlines():
            if "/Volumes/" in line:
                mount_point = line.split("\t")[-1].strip()
                break
        if not mount_point:
            return False

        app_src = Path(mount_point) / "Jarvis.app"
        subprocess.run(["cp", "-r", str(app_src), "/Applications/"], check=True)
        subprocess.run(["hdiutil", "detach", mount_point, "-quiet"])
        dmg_path.unlink(missing_ok=True)

        if progress_cb:
            progress_cb("Neustart…")

        # Neues App starten und nach 1s alten Prozess beenden
        subprocess.Popen(["open", str(APP_BUNDLE)])
        time.sleep(1.5)
        os.kill(os.getpid(), 15)

        return True

    except Exception as e:
        if progress_cb:
            progress_cb(f"Fehler: {e}")
        return False
