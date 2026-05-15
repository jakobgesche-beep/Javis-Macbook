import threading
import time
import requests
import rumps
import native_window
from updater import CURRENT_VERSION

API = "http://127.0.0.1:8080"

MODES = {
    "programmieren": ("💻", "Programmieren"),
    "recherche":     ("🔍", "Recherche"),
    "musik":         ("🎵", "Musik"),
    "pause":         ("⏸",  "Pause"),
}


def api_call(path, method="GET", json=None):
    try:
        fn = requests.post if method == "POST" else requests.get
        return fn(f"{API}{path}", json=json, timeout=2).json()
    except Exception:
        return {}


class JarvisMenuBar(rumps.App):

    def __init__(self, state: dict, state_lock: threading.Lock):
        super().__init__("🤖", quit_button=None)
        self._state     = state
        self._lock      = state_lock
        self._update_info = None

        self._build_menu()
        threading.Thread(target=self._poll,          daemon=True).start()
        threading.Thread(target=self._bg_update_check, daemon=True).start()

        # Öffne Fenster sobald Flask antwortet (jede Sekunde prüfen)
        self._flask_timer = rumps.Timer(self._wait_for_flask, 1)
        self._flask_timer.start()

    # ── Fenster ──────────────────────────────────────────────────────────────

    def _wait_for_flask(self, timer):
        try:
            requests.get(f"{API}/api/status", timeout=0.5)
            native_window.open_window()
            timer.stop()
        except Exception:
            pass

    # ── Menü ─────────────────────────────────────────────────────────────────

    def _build_menu(self):
        self._status_item = rumps.MenuItem("Jarvis — Gestoppt")
        self._status_item.set_callback(None)

        self._update_item = rumps.MenuItem(f"Jarvis v{CURRENT_VERSION}  ✓ Aktuell")
        self._update_item.set_callback(None)

        mode_menu = rumps.MenuItem("⚡  Modus wechseln")
        for key, (icon, label) in MODES.items():
            mode_menu.add(rumps.MenuItem(
                f"{icon}  {label}",
                callback=lambda _, k=key: api_call("/api/mode", "POST", {"mode": k})
                         or rumps.notification("Jarvis", f"Modus: {MODES[k][1]}", "")
            ))

        self.menu = [
            self._status_item,
            None,
            rumps.MenuItem("▶  Starten",  callback=self._start),
            rumps.MenuItem("⏹  Stoppen",  callback=self._stop),
            None,
            mode_menu,
            None,
            rumps.MenuItem("🖥  Dashboard öffnen", callback=lambda _: native_window.open_window()),
            rumps.MenuItem("📂  VS Code öffnen",   callback=lambda _: api_call("/api/vscode/open-jarvis", "POST")),
            None,
            self._update_item,
            None,
            rumps.MenuItem("✕  Beenden", callback=lambda _: rumps.quit_application()),
        ]

    # ── Status-Polling (Background-Thread) ───────────────────────────────────

    def _poll(self):
        while True:
            try:
                with self._lock:
                    running   = self._state["running"]
                    task      = self._state["current_task"]
                    stats     = self._state["stats"]
                    pw_alerts = len(self._state.get("password_alerts", []))

                if running and task:
                    self.title = "⚡"
                    label = f"⚡ {task[:45]}"
                elif running:
                    self.title = "🤖"
                    label = f"🟢 Läuft — ✓{stats['done']} erledigt"
                else:
                    self.title = "💤"
                    label = "💤 Gestoppt"

                if pw_alerts:
                    label += f"  · 🔑 {pw_alerts}"
                self._status_item.title = label

            except Exception:
                pass
            time.sleep(3)

    # ── Update-Check (Background-Thread) ─────────────────────────────────────

    def _bg_update_check(self):
        time.sleep(20)
        while True:
            from updater import check_for_update
            info = check_for_update()
            if info:
                self._update_info = info
                self._update_item.title = f"🔄 Update v{info['version']} installieren"
                self._update_item.set_callback(self._do_update)
                rumps.notification(
                    "Jarvis Update verfügbar",
                    f"Version {info['version']} ist bereit.",
                    "Menüleiste → Update installieren",
                )
                break
            time.sleep(3600)

    def _do_update(self, _):
        if not self._update_info:
            return
        self._update_item.title = "⏳ Update wird installiert…"
        self._update_item.set_callback(None)
        info = self._update_info

        def run():
            from updater import install_update
            install_update(info, progress_cb=lambda msg: setattr(self._update_item, "title", f"⏳ {msg}"))

        threading.Thread(target=run, daemon=True).start()

    # ── Controls ─────────────────────────────────────────────────────────────

    def _start(self, _):
        api_call("/api/start", "POST")
        rumps.notification("Jarvis", "Gestartet", "Task-Loop läuft.")

    def _stop(self, _):
        api_call("/api/stop", "POST")
        rumps.notification("Jarvis", "Gestoppt", "")

    def run(self):
        super().run()
