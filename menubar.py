import threading
import time
import requests
import rumps
import native_window

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
        self._state = state
        self._lock  = state_lock
        self._build_menu()
        threading.Thread(target=self._poll, daemon=True).start()

        # Fenster automatisch öffnen sobald Flask bereit ist (rumps.Timer = Main-Thread)
        self._open_timer = rumps.Timer(self._auto_open, 2.5)
        self._open_timer.start()

    def _auto_open(self, timer):
        native_window.open_window()
        timer.stop()

    def _build_menu(self):
        self._status_item = rumps.MenuItem("Jarvis — Gestoppt")
        self._status_item.set_callback(None)

        self._start_item = rumps.MenuItem("▶  Starten",  callback=self._start)
        self._stop_item  = rumps.MenuItem("⏹  Stoppen",  callback=self._stop)

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
            self._start_item,
            self._stop_item,
            None,
            mode_menu,
            None,
            rumps.MenuItem("🖥  Dashboard öffnen",  callback=lambda _: native_window.open_window()),
            rumps.MenuItem("📂  VS Code öffnen",    callback=lambda _: api_call("/api/vscode/open-jarvis", "POST")),
            None,
            rumps.MenuItem("✕  Beenden",            callback=lambda _: rumps.quit_application()),
        ]

    def _poll(self):
        while True:
            try:
                with self._lock:
                    running  = self._state["running"]
                    task     = self._state["current_task"]
                    stats    = self._state["stats"]
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

    def _start(self, _):
        api_call("/api/start", "POST")
        rumps.notification("Jarvis", "Gestartet", "Task-Loop läuft.")

    def _stop(self, _):
        api_call("/api/stop", "POST")
        rumps.notification("Jarvis", "Gestoppt", "")

    def run(self):
        super().run()
