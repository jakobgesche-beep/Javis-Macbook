"""
Jarvis Menüleisten-App.
Kleines Icon oben rechts im Mac — schneller Zugriff auf alles.
"""

import rumps
import requests
import subprocess
import threading
import webbrowser
from pathlib import Path

API = "http://localhost:8080"
BASE_DIR = Path(__file__).parent

MODES = {
    "programmieren": "💻 Programmieren",
    "recherche":     "🔍 Recherche",
    "musik":         "🎵 Musik",
    "pause":         "⏸ Pause",
}


def api(path, method="GET", json=None):
    try:
        fn = requests.post if method == "POST" else requests.get
        r = fn(f"{API}{path}", json=json, timeout=2)
        return r.json()
    except Exception:
        return {}


class JarvisApp(rumps.App):

    def __init__(self):
        super().__init__("🤖", quit_button=None)
        self._build_menu()
        self._running = False
        self._current_mode = "pause"
        self._task = None
        self._start_polling()

    def _build_menu(self):
        self.menu = [
            rumps.MenuItem("Jarvis — Gestoppt", callback=None),
            None,  # Separator
            rumps.MenuItem("▶  Starten",  callback=self.start),
            rumps.MenuItem("⏹  Stoppen",  callback=self.stop),
            None,
            rumps.MenuItem("Modi", callback=None),
        ]

        # Modi als Untermenü
        mode_menu = rumps.MenuItem("Modi")
        for key, label in MODES.items():
            item = rumps.MenuItem(label, callback=lambda sender, k=key: self.set_mode(sender, k))
            mode_menu.add(item)
        self.menu["Modi"] = mode_menu

        self.menu.add(None)
        self.menu.add(rumps.MenuItem("🌐  Dashboard öffnen", callback=self.open_dashboard))
        self.menu.add(rumps.MenuItem("📂  VS Code öffnen",  callback=self.open_vscode))
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("🔐  Passwörter",      callback=self.open_passwords))
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("⚙  Einstellungen",   callback=self.open_settings))
        self.menu.add(rumps.MenuItem("✕  Beenden",          callback=self.quit_app))

    def _start_polling(self):
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _poll_loop(self):
        while True:
            try:
                d = api("/api/status")
                if d:
                    running  = d.get("running", False)
                    task     = d.get("current_task")
                    mode     = d.get("current_mode", "pause")
                    stats    = d.get("stats", {})
                    pw_alerts = len(d.get("password_alerts", []))

                    self._running = running
                    self._current_mode = mode
                    self._task = task

                    # Icon je nach Status
                    if running and task:
                        self.title = "⚡"
                    elif running:
                        self.title = "🤖"
                    else:
                        self.title = "💤"

                    # Status-Zeile im Menü
                    status_line = self.menu["Jarvis — Gestoppt"]
                    if not status_line:
                        # Fallback: erstes Item
                        status_line = list(self.menu.values())[0]

                    label = MODES.get(mode, mode)
                    if running and task:
                        status_text = f"⚡ {task[:40]}"
                    elif running:
                        status_text = f"🟢 Läuft · {label} · ✓{stats.get('done',0)}"
                    else:
                        status_text = f"💤 Gestoppt · {label}"

                    if pw_alerts > 0:
                        status_text += f" · 🔑 {pw_alerts} Passwort-Alert"

                    # Menü-Titel updaten (thread-sicher über Timer-Trick)
                    self._update_status_label(status_text, running)

            except Exception:
                self.title = "🤖"

            import time
            time.sleep(3)

    @rumps.timer(3)
    def _refresh_title(self, _):
        pass  # Polling läuft im Thread, kein Extra-Timer nötig

    def _update_status_label(self, text, running):
        try:
            for key in list(self.menu.keys()):
                if "Jarvis" in key or "Gestoppt" in key or "Läuft" in key or "Gestoppt" in str(key):
                    item = self.menu[key]
                    if hasattr(item, 'title'):
                        item.title = text
                    break
        except Exception:
            pass

    # ── Aktionen ──────────────────────────────────────────────────────────────

    def start(self, _):
        api("/api/start", "POST")
        rumps.notification("Jarvis", "Gestartet", "Task-Loop läuft.")

    def stop(self, _):
        api("/api/stop", "POST")
        rumps.notification("Jarvis", "Gestoppt", "Task-Loop angehalten.")

    def set_mode(self, _, mode_key):
        result = api("/api/mode", "POST", {"mode": mode_key})
        if result.get("ok"):
            label = MODES.get(mode_key, mode_key)
            rumps.notification("Jarvis", f"Modus: {label}", "")

    def open_dashboard(self, _):
        webbrowser.open("http://localhost:8080")

    def open_passwords(self, _):
        webbrowser.open("http://localhost:8080/#passwords")

    def open_settings(self, _):
        webbrowser.open("http://localhost:8080/#settings")

    def open_vscode(self, _):
        api("/api/vscode/open-jarvis", "POST")

    def quit_app(self, _):
        rumps.quit_application()


def run_menubar():
    app = JarvisApp()
    app.run()


if __name__ == "__main__":
    run_menubar()
