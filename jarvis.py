#!/usr/bin/env python3
import os
import re
import json
import subprocess
import threading
import time
import logging
from datetime import datetime
from pathlib import Path

from evaluator import evaluate_output as local_evaluate
try:
    from feedback import evaluate_output as api_evaluate
except ImportError:
    api_evaluate = None

import computer
import password_vault as pv

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def setup_logging(log_file: str):
    os.makedirs(os.path.dirname(BASE_DIR / log_file), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(BASE_DIR / log_file),
            logging.StreamHandler()
        ]
    )


def evaluate_output(task: str, output: str, directory: str, api_key: str = "") -> dict:
    if api_key and api_evaluate:
        return api_evaluate(task, output, api_key)
    return local_evaluate(task, output, directory)


def read_tasks(tasks_file: str) -> list[dict]:
    path = BASE_DIR / tasks_file
    if not path.exists():
        return []
    tasks = []
    with open(path) as f:
        for line in f:
            match = re.match(r"- \[ \] (.+)", line)
            if match:
                full = match.group(1)
                parts = full.split(" | Verzeichnis: ")
                tasks.append({
                    "text": parts[0].strip(),
                    "directory": parts[1].strip() if len(parts) > 1 else str(Path.home()),
                    "raw": line
                })
    return tasks


def mark_task_done(tasks_file: str, raw_line: str, status: str = "x"):
    path = BASE_DIR / tasks_file
    content = path.read_text()
    content = content.replace(f"- [ ] {raw_line.strip()[6:]}", f"- [{status}] {raw_line.strip()[6:]}")
    path.write_text(content)


def run_claude_code(task: str, directory: str, timeout: int) -> str:
    os.makedirs(directory, exist_ok=True)
    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", task],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT: Claude Code hat zu lange gebraucht."
    except FileNotFoundError:
        return "FEHLER: Claude Code CLI nicht gefunden. Bitte 'claude' installieren."


# ─── Shared State ─────────────────────────────────────────────────────────────

state = {
    "running": False,
    "current_task": None,
    "current_mode": "pause",
    "log": [],
    "stats": {"done": 0, "retried": 0, "failed": 0},
    "vscode_dialogs_confirmed": 0,
    "password_alerts": [],
    "last_browser_url": "",
    "last_clipboard_capture": None,
}
state_lock = threading.Lock()


def log_event(msg: str, level: str = "info"):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "level": level}
    with state_lock:
        state["log"].insert(0, entry)
        if len(state["log"]) > 300:
            state["log"].pop()
    getattr(logging, level, logging.info)(msg)


# ─── Thread 1: Haupt-Task-Loop ────────────────────────────────────────────────

def run_task_loop():
    config = load_config()
    setup_logging(config["log_file"])
    log_event("Jarvis gestartet.")

    while True:
        with state_lock:
            if not state["running"]:
                time.sleep(2)
                continue

        config = load_config()
        tasks = read_tasks(config["tasks_file"])

        if not tasks:
            time.sleep(10)
            continue

        task = tasks[0]
        with state_lock:
            state["current_task"] = task["text"]

        log_event(f"Aufgabe: {task['text']}")

        feedback_result = {}
        success = False

        for attempt in range(1, config["max_retries"] + 1):
            prompt = task["text"] if attempt == 1 else feedback_result.get("verbesserungs_prompt", task["text"])
            log_event(f"Versuch {attempt}/{config['max_retries']}")

            output = run_claude_code(prompt, task["directory"], config["claude_code_timeout"])
            log_event(f"Output: {len(output)} Zeichen")

            feedback_result = evaluate_output(
                task["text"], output, task["directory"], config.get("anthropic_api_key", "")
            )
            log_event(
                f"Bewertung [{feedback_result.get('confidence', '?')}%]: "
                f"{feedback_result['status']} — {feedback_result['grund']}"
            )

            if feedback_result["status"] == "gut":
                success = True
                break
            else:
                with state_lock:
                    state["stats"]["retried"] += 1

        if success:
            mark_task_done(config["tasks_file"], task["raw"], status="x")
            with state_lock:
                state["stats"]["done"] += 1
                state["current_task"] = None
            log_event(f"Erledigt: {task['text']}")
        else:
            mark_task_done(config["tasks_file"], task["raw"], status="!")
            with state_lock:
                state["stats"]["failed"] += 1
                state["current_task"] = None
            log_event(f"Fehlgeschlagen: {task['text']}", "warning")

        time.sleep(2)


# ─── Thread 2: VS Code Dialog Auto-Confirm ────────────────────────────────────

def run_vscode_dialog_watcher():
    time.sleep(5)
    while True:
        try:
            config = load_config()
            if config.get("auto_confirm_vscode", True):
                confirmed = computer.confirm_vscode_dialogs()
                if confirmed > 0:
                    with state_lock:
                        state["vscode_dialogs_confirmed"] += confirmed
                    log_event(f"VS Code Dialog automatisch bestätigt ({confirmed}x)", "info")
        except Exception as e:
            pass
        time.sleep(3)


# ─── Thread 3: VS Code Fenster-Wächter ────────────────────────────────────────

def run_vscode_window_watcher():
    time.sleep(8)
    while True:
        try:
            config = load_config()
            if config.get("single_vscode_window", True) and computer.is_vscode_running():
                count = computer.get_vscode_window_count()
                if count > 1:
                    computer.close_extra_vscode_windows()
                    log_event(f"VS Code: {count} Fenster → auf 1 reduziert")
        except Exception:
            pass
        time.sleep(8)


# ─── Thread 4: Passwort Clipboard-Monitor ─────────────────────────────────────

def run_password_monitor():
    time.sleep(6)
    last_browser = {"url": "", "title": "", "login_page": False}

    while True:
        try:
            config = load_config()
            if not config.get("password_manager_enabled", True):
                time.sleep(5)
                continue

            vault = pv.get_vault(config.get("password_master_key", ""))

            # Clipboard-Überwachung
            if config.get("password_clipboard_capture", True):
                new_pw = pv.check_clipboard_for_password()
                if new_pw:
                    browser = pv.get_browser_state()
                    site = pv.extract_domain(browser["url"]) if browser["url"] else "unbekannt"
                    alert = {
                        "type": "clipboard_password",
                        "site": site,
                        "password_preview": new_pw[:3] + "•" * (len(new_pw) - 3),
                        "password": new_pw,
                        "time": datetime.now().strftime("%H:%M:%S")
                    }
                    with state_lock:
                        state["last_clipboard_capture"] = alert
                    log_event(f"Passwort im Clipboard erkannt — Site: {site}", "info")

            # Browser-Monitoring: Login-Fehler erkennen
            browser = pv.get_browser_state()
            if browser["url"] and browser["url"] != last_browser["url"]:
                url_changed = True
                domain = pv.extract_domain(browser["url"])

                # Prüfe ob Login fehlgeschlagen
                if last_browser["url"] and last_browser["login_page"]:
                    if pv.detect_login_error(browser["title"], browser["url"]):
                        # Passwörter für diese Domain als falsch markieren
                        entries = vault.get_for_site(last_browser.get("domain", ""))
                        for e in entries:
                            if e["status"] != "wrong":
                                vault.mark_wrong(e["id"])
                                alert = {
                                    "type": "wrong_password",
                                    "site": e["site"],
                                    "username": e["username"],
                                    "time": datetime.now().strftime("%H:%M:%S")
                                }
                                with state_lock:
                                    state["password_alerts"].insert(0, alert)
                                    if len(state["password_alerts"]) > 50:
                                        state["password_alerts"].pop()
                                log_event(f"Falsches Passwort erkannt: {e['site']} / {e['username']}", "warning")

                    elif pv.detect_login_success(browser["title"], browser["url"]):
                        entries = vault.get_for_site(last_browser.get("domain", ""))
                        for e in entries:
                            if e["status"] == "wrong":
                                vault.mark_ok(e["id"])
                                log_event(f"Passwort als korrekt markiert: {e['site']}", "info")

                is_login = any(kw in browser["url"].lower() for kw in [
                    "login", "signin", "sign-in", "auth", "account", "log-in",
                    "anmeld", "einlogg", "password", "passwort"
                ])

                last_browser = {
                    "url": browser["url"],
                    "title": browser["title"],
                    "domain": pv.extract_domain(browser["url"]),
                    "login_page": is_login
                }

        except Exception:
            pass

        time.sleep(4)


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    threads = [
        threading.Thread(target=run_task_loop, daemon=True, name="task-loop"),
        threading.Thread(target=run_vscode_dialog_watcher, daemon=True, name="vscode-confirm"),
        threading.Thread(target=run_vscode_window_watcher, daemon=True, name="vscode-windows"),
        threading.Thread(target=run_password_monitor, daemon=True, name="password-monitor"),
    ]

    for t in threads:
        t.start()

    # Flask im Hintergrund-Thread — Menüleiste braucht den Main-Thread
    from dashboard import create_app
    flask_app = create_app(state, state_lock)
    config = load_config()

    flask_thread = threading.Thread(
        target=lambda: flask_app.run(
            host="0.0.0.0", port=config["dashboard_port"],
            debug=False, use_reloader=False
        ),
        daemon=True,
        name="flask"
    )
    flask_thread.start()

    # Menüleiste im Main-Thread (macOS Anforderung)
    try:
        from menubar import run_menubar
        run_menubar()
    except Exception as e:
        # Fallback: ohne Menüleiste weiterlaufen
        logging.warning(f"Menüleiste nicht verfügbar: {e}")
        flask_thread.join()
