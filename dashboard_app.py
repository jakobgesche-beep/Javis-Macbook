"""
Flask Dashboard — wird aus app_main.py mit konfigurierten Pfaden gestartet.
"""

import json
import threading
from pathlib import Path
from flask import Flask, jsonify, render_template, request

import computer
import password_vault as pv


def create_app(state, state_lock, config_file, tasks_file, modes_dir):
    config_file = Path(config_file)
    tasks_file  = Path(tasks_file)
    modes_dir   = Path(modes_dir)

    # Templates und Static aus dem Bundle-Verzeichnis
    bundle_dir = modes_dir.parent
    app = Flask(__name__,
                template_folder=str(bundle_dir / "templates"),
                static_folder=str(bundle_dir / "static"))

    def load_cfg():
        with open(config_file) as f:
            return json.load(f)

    def save_cfg(cfg):
        with open(config_file, "w") as f:
            json.dump(cfg, f, indent=2)

    def get_modes():
        modes = {}
        for p in modes_dir.glob("*.json"):
            with open(p) as f:
                modes[p.stem] = json.load(f)
        return modes

    @app.route("/")
    def index():
        return render_template("dashboard.html")

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

    @app.route("/api/modes")
    def api_modes():
        return jsonify(get_modes())

    @app.route("/api/mode", methods=["POST"])
    def api_mode():
        import threading as _t
        data = request.get_json()
        mode = data.get("mode", "")
        if not (modes_dir / f"{mode}.json").exists():
            return jsonify({"ok": False})
        # State sofort aktualisieren, Aktionen im Hintergrund ausführen
        with state_lock:
            state["current_mode"] = mode
        cfg = load_cfg(); cfg["current_mode"] = mode; save_cfg(cfg)
        _t.Thread(target=computer.apply_mode, args=(mode, str(modes_dir)), daemon=True).start()
        return jsonify({"ok": True})

    @app.route("/api/projects")
    def api_projects():
        cfg = load_cfg()
        root = Path(cfg.get("project_root", str(Path.home())))
        try:
            dirs = sorted([
                {"name": p.name, "path": str(p)}
                for p in root.iterdir()
                if p.is_dir() and not p.name.startswith(".")
            ], key=lambda x: x["name"].lower())
        except Exception:
            dirs = []
        return jsonify({"projects": dirs, "root": str(root)})

    @app.route("/api/tasks")
    def api_tasks():
        return jsonify({"content": tasks_file.read_text() if tasks_file.exists() else ""})

    @app.route("/api/tasks", methods=["POST"])
    def api_save_tasks():
        tasks_file.write_text(request.get_json().get("content", ""))
        return jsonify({"ok": True})

    @app.route("/api/config")
    def api_config():
        cfg = load_cfg()
        cfg.pop("anthropic_api_key", None)
        cfg.pop("password_master_key", None)
        return jsonify(cfg)

    @app.route("/api/config", methods=["POST"])
    def api_save_config():
        data = request.get_json()
        cfg = load_cfg()
        for key in ["max_retries","claude_code_timeout","auto_start","auto_confirm_vscode",
                    "single_vscode_window","enforce_claude_vscode","password_manager_enabled",
                    "password_clipboard_capture","jarvis_project_path","project_root"]:
            if key in data:
                cfg[key] = data[key]
        if data.get("anthropic_api_key"): cfg["anthropic_api_key"] = data["anthropic_api_key"]
        if data.get("password_master_key"): cfg["password_master_key"] = data["password_master_key"]
        save_cfg(cfg)
        return jsonify({"ok": True})

    @app.route("/api/vscode/open-jarvis", methods=["POST"])
    def api_open_jarvis():
        cfg = load_cfg()
        computer.open_jarvis_in_vscode(cfg.get("jarvis_project_path", str(Path.home())),
                                       cfg.get("single_vscode_window", True))
        return jsonify({"ok": True})

    # Passwort-Vault Endpoints
    def vault():
        return pv.get_vault(load_cfg().get("password_master_key", ""))

    @app.route("/api/passwords")
    def api_passwords():
        v = vault()
        return jsonify({"entries": v.get_all(), "count": v.count()})

    @app.route("/api/passwords", methods=["POST"])
    def api_add_password():
        d = request.get_json()
        if not d.get("site") or not d.get("password"):
            return jsonify({"ok": False}), 400
        e = vault().add(d["site"], d.get("username",""), d["password"], "manual")
        return jsonify({"ok": True, "id": e["id"]})

    @app.route("/api/passwords/<eid>", methods=["DELETE"])
    def api_del_pw(eid):
        return jsonify({"ok": vault().delete(eid)})

    @app.route("/api/passwords/<eid>/reveal")
    def api_reveal_pw(eid):
        pw = vault().get_password(eid)
        return jsonify({"ok": pw is not None, "password": pw or ""})

    @app.route("/api/passwords/<eid>/status", methods=["POST"])
    def api_pw_status(eid):
        s = request.get_json().get("status","")
        if s == "wrong": vault().mark_wrong(eid)
        elif s == "ok":  vault().mark_ok(eid)
        return jsonify({"ok": True})

    @app.route("/api/passwords/save-clipboard", methods=["POST"])
    def api_save_clipboard():
        d = request.get_json()
        with state_lock:
            capture = state.get("last_clipboard_capture")
        if not capture:
            return jsonify({"ok": False})
        vault().add(d.get("site", capture.get("site","unbekannt")),
                    d.get("username",""), capture["password"], "clipboard")
        with state_lock:
            state["last_clipboard_capture"] = None
        return jsonify({"ok": True})

    @app.route("/api/passwords/alerts/clear", methods=["POST"])
    def api_clear_alerts():
        with state_lock:
            state["password_alerts"] = []
        return jsonify({"ok": True})

    @app.route("/webhook/jarvis", methods=["POST"])
    def webhook_jarvis():
        cfg = load_cfg()
        computer.open_jarvis_in_vscode(cfg.get("jarvis_project_path",""),
                                       cfg.get("single_vscode_window", True))
        return jsonify({"ok": True})

    @app.route("/webhook/modus", methods=["POST"])
    def webhook_modus():
        data = request.get_json(force=True)
        mode = data.get("modus","")
        ok = computer.apply_mode(mode, str(modes_dir))
        if ok:
            with state_lock:
                state["current_mode"] = mode
        return jsonify({"ok": ok})

    return app
