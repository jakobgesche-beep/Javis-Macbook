import json
import os
import threading
from pathlib import Path
from flask import Flask, jsonify, render_template, request

import computer
import password_vault as pv

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
MODES_DIR = BASE_DIR / "modes"


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_modes():
    modes = {}
    for p in MODES_DIR.glob("*.json"):
        with open(p) as f:
            data = json.load(f)
            modes[p.stem] = data
    return modes


def create_app(state: dict, state_lock: threading.Lock) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ── Dashboard ─────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("dashboard.html")

    # ── Status & Control ──────────────────────────────────────────────────────

    @app.route("/api/status")
    def api_status():
        with state_lock:
            return jsonify({
                "running": state["running"],
                "current_task": state["current_task"],
                "current_mode": state["current_mode"],
                "stats": state["stats"],
                "log": state["log"][:60],
                "vscode_dialogs_confirmed": state["vscode_dialogs_confirmed"],
                "password_alerts": state["password_alerts"][:10],
                "last_clipboard_capture": state["last_clipboard_capture"],
            })

    @app.route("/api/start", methods=["POST"])
    def api_start():
        with state_lock:
            state["running"] = True
        return jsonify({"ok": True})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        with state_lock:
            state["running"] = False
        return jsonify({"ok": True})

    # ── Modi ──────────────────────────────────────────────────────────────────

    @app.route("/api/modes")
    def api_modes():
        return jsonify(get_modes())

    @app.route("/api/mode", methods=["POST"])
    def api_set_mode():
        data = request.get_json()
        mode = data.get("mode", "")
        if not mode:
            return jsonify({"ok": False, "error": "Kein Modus"}), 400
        success = computer.apply_mode(mode, str(MODES_DIR))
        if success:
            with state_lock:
                state["current_mode"] = mode
            config = load_config()
            config["current_mode"] = mode
            save_config(config)
        return jsonify({"ok": success})

    # ── Tasks ─────────────────────────────────────────────────────────────────

    @app.route("/api/tasks")
    def api_tasks():
        config = load_config()
        path = BASE_DIR / config["tasks_file"]
        return jsonify({"content": path.read_text() if path.exists() else ""})

    @app.route("/api/tasks", methods=["POST"])
    def api_save_tasks():
        data = request.get_json()
        config = load_config()
        path = BASE_DIR / config["tasks_file"]
        path.write_text(data.get("content", ""))
        return jsonify({"ok": True})

    # ── Config ────────────────────────────────────────────────────────────────

    @app.route("/api/config")
    def api_config():
        config = load_config()
        config.pop("anthropic_api_key", None)
        config.pop("password_master_key", None)
        return jsonify(config)

    @app.route("/api/config", methods=["POST"])
    def api_save_config():
        data = request.get_json()
        config = load_config()
        editable = [
            "max_retries", "claude_code_timeout", "auto_start",
            "auto_confirm_vscode", "single_vscode_window", "enforce_claude_vscode",
            "password_manager_enabled", "password_clipboard_capture",
            "jarvis_project_path",
        ]
        for key in editable:
            if key in data:
                config[key] = data[key]
        if data.get("anthropic_api_key"):
            config["anthropic_api_key"] = data["anthropic_api_key"]
        if data.get("password_master_key"):
            config["password_master_key"] = data["password_master_key"]
        save_config(config)
        return jsonify({"ok": True})

    # ── VS Code Steuerung ─────────────────────────────────────────────────────

    @app.route("/api/vscode/open-jarvis", methods=["POST"])
    def api_open_jarvis():
        config = load_config()
        path = config.get("jarvis_project_path", str(BASE_DIR))
        close_others = config.get("single_vscode_window", True)
        computer.open_jarvis_in_vscode(path, close_others)
        return jsonify({"ok": True})

    @app.route("/api/vscode/confirm-dialogs", methods=["POST"])
    def api_confirm_dialogs():
        confirmed = computer.confirm_vscode_dialogs()
        with state_lock:
            state["vscode_dialogs_confirmed"] += confirmed
        return jsonify({"ok": True, "confirmed": confirmed})

    # ── Passwort Vault ────────────────────────────────────────────────────────

    def _vault():
        config = load_config()
        return pv.get_vault(config.get("password_master_key", ""))

    @app.route("/api/passwords")
    def api_passwords():
        entries = _vault().get_all()
        return jsonify({"entries": entries, "count": _vault().count()})

    @app.route("/api/passwords", methods=["POST"])
    def api_add_password():
        data = request.get_json()
        site = data.get("site", "").strip()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        if not site or not password:
            return jsonify({"ok": False, "error": "Site und Passwort erforderlich"}), 400
        entry = _vault().add(site, username, password, source="manual")
        return jsonify({"ok": True, "id": entry["id"]})

    @app.route("/api/passwords/<entry_id>", methods=["DELETE"])
    def api_delete_password(entry_id):
        ok = _vault().delete(entry_id)
        return jsonify({"ok": ok})

    @app.route("/api/passwords/<entry_id>/reveal", methods=["GET"])
    def api_reveal_password(entry_id):
        pw = _vault().get_password(entry_id)
        if pw is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "password": pw})

    @app.route("/api/passwords/<entry_id>/status", methods=["POST"])
    def api_password_status(entry_id):
        data = request.get_json()
        status = data.get("status", "")
        if status == "wrong":
            _vault().mark_wrong(entry_id)
        elif status == "ok":
            _vault().mark_ok(entry_id)
        return jsonify({"ok": True})

    @app.route("/api/passwords/save-clipboard", methods=["POST"])
    def api_save_clipboard_password():
        data = request.get_json()
        with state_lock:
            capture = state.get("last_clipboard_capture")
        if not capture:
            return jsonify({"ok": False, "error": "Kein Clipboard-Passwort gefunden"})
        entry = _vault().add(
            site=data.get("site", capture.get("site", "unbekannt")),
            username=data.get("username", ""),
            password=capture["password"],
            source="clipboard"
        )
        with state_lock:
            state["last_clipboard_capture"] = None
        return jsonify({"ok": True, "id": entry["id"]})

    @app.route("/api/passwords/alerts")
    def api_password_alerts():
        with state_lock:
            alerts = list(state["password_alerts"])
        return jsonify({"alerts": alerts})

    @app.route("/api/passwords/alerts/clear", methods=["POST"])
    def api_clear_alerts():
        with state_lock:
            state["password_alerts"] = []
        return jsonify({"ok": True})

    # ── Webhooks (Siri / Alexa) ───────────────────────────────────────────────

    @app.route("/webhook/modus", methods=["POST"])
    def webhook_modus():
        data = request.get_json(force=True)
        mode = data.get("modus", "")
        if not mode:
            return jsonify({"ok": False, "error": "Kein Modus"}), 400
        success = computer.apply_mode(mode, str(MODES_DIR))
        if success:
            with state_lock:
                state["current_mode"] = mode
        return jsonify({"ok": success})

    @app.route("/webhook/jarvis", methods=["POST"])
    def webhook_jarvis():
        """Siri/Alexa Trigger: 'Jarvis' → Projekt in VS Code öffnen."""
        config = load_config()
        path = config.get("jarvis_project_path", str(BASE_DIR))
        close_others = config.get("single_vscode_window", True)
        computer.open_jarvis_in_vscode(path, close_others)
        with state_lock:
            state["log"].insert(0, {
                "time": __import__("datetime").datetime.now().strftime("%H:%M:%S"),
                "msg": "Jarvis Sprachbefehl: VS Code geöffnet",
                "level": "info"
            })
        return jsonify({"ok": True})

    return app
