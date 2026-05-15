"""
Einstiegspunkt für die gebündelte Jarvis.app.
Setzt alle Pfade auf, startet Threads und die Menüleiste.
"""

import sys
import os
import json
import threading
import time
import logging
import subprocess
import re
from datetime import datetime
from pathlib import Path


# ─── Pfade (Bundle vs. Entwicklung) ──────────────────────────────────────────

IS_BUNDLE = getattr(sys, "frozen", False)

if IS_BUNDLE:
    BUNDLE_DIR = Path(sys._MEIPASS)
    USER_DIR   = Path.home() / "Library" / "Application Support" / "Jarvis"
else:
    BUNDLE_DIR = Path(__file__).parent
    USER_DIR   = Path(__file__).parent

# User-Verzeichnisse anlegen
for d in ["tasks", "logs", "data"]:
    (USER_DIR / d).mkdir(parents=True, exist_ok=True)

CONFIG_FILE   = USER_DIR   / "config.json"
TASKS_FILE    = USER_DIR   / "tasks" / "todo.md"
MODES_DIR     = BUNDLE_DIR / "modes"
TEMPLATES_DIR = BUNDLE_DIR / "templates"
STATIC_DIR    = BUNDLE_DIR / "static"


# ─── Default-Config anlegen falls nicht vorhanden ────────────────────────────

DEFAULT_CONFIG = {
    "anthropic_api_key": "",
    "max_retries": 3,
    "claude_code_timeout": 300,
    "dashboard_port": 8080,
    "tasks_file": str(TASKS_FILE),
    "log_file": str(USER_DIR / "logs" / "jarvis.log"),
    "current_mode": "pause",
    "auto_start": False,
    "jarvis_project_path": str(Path.home() / "Downloads" / "macbook-jarvis"),
    "auto_confirm_vscode": True,
    "single_vscode_window": True,
    "enforce_claude_vscode": True,
    "password_manager_enabled": True,
    "password_clipboard_capture": True,
    "password_master_key": "",
}

if not CONFIG_FILE.exists():
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2))

if not TASKS_FILE.exists():
    TASKS_FILE.write_text(
        "# Jarvis Task Queue\n\n"
        "<!-- Format: - [ ] Aufgabe | Verzeichnis: /pfad/zum/projekt -->\n"
    )


# ─── Pfade in Module injizieren ───────────────────────────────────────────────

os.environ["JARVIS_CONFIG"]    = str(CONFIG_FILE)
os.environ["JARVIS_USER_DIR"]  = str(USER_DIR)
os.environ["JARVIS_BUNDLE_DIR"] = str(BUNDLE_DIR)
os.environ["JARVIS_MODES_DIR"] = str(MODES_DIR)


# ─── Module laden (nach Pfad-Setup) ──────────────────────────────────────────

sys.path.insert(0, str(BUNDLE_DIR))

from evaluator import evaluate_output as local_evaluate
import computer
import password_vault as pv

try:
    from feedback import evaluate_output as api_evaluate
except ImportError:
    api_evaluate = None


# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def setup_logging(log_file: str):
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


# ─── Shared State ─────────────────────────────────────────────────────────────

state = {
    "running": False,
    "current_task": None,
    "current_mode": "pause",
    "log": [],
    "stats": {"done": 0, "retried": 0, "failed": 0},
    "vscode_dialogs_confirmed": 0,
    "password_alerts": [],
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


# ─── Claude Code Runner ───────────────────────────────────────────────────────

def run_claude_code(task: str, directory: str, timeout: int) -> str:
    os.makedirs(directory, exist_ok=True)
    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", task],
            cwd=directory, capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT: Claude Code hat zu lange gebraucht."
    except FileNotFoundError:
        return "FEHLER: Claude Code CLI nicht gefunden. Bitte 'npm install -g @anthropic-ai/claude-code' ausführen."


def evaluate(task, output, directory, api_key=""):
    if api_key and api_evaluate:
        return api_evaluate(task, output, api_key)
    return local_evaluate(task, output, directory)


def read_tasks() -> list[dict]:
    if not TASKS_FILE.exists():
        return []
    tasks = []
    with open(TASKS_FILE) as f:
        for line in f:
            m = re.match(r"- \[ \] (.+)", line)
            if m:
                full = m.group(1)
                parts = full.split(" | Verzeichnis: ")
                tasks.append({
                    "text": parts[0].strip(),
                    "directory": parts[1].strip() if len(parts) > 1 else str(Path.home()),
                    "raw": line,
                })
    return tasks


def mark_done(raw_line: str, status: str = "x"):
    content = TASKS_FILE.read_text()
    content = content.replace(
        f"- [ ] {raw_line.strip()[6:]}",
        f"- [{status}] {raw_line.strip()[6:]}"
    )
    TASKS_FILE.write_text(content)


# ─── Thread 1: Task-Loop ──────────────────────────────────────────────────────

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
        tasks = read_tasks()

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
            feedback_result = evaluate(task["text"], output, task["directory"], config.get("anthropic_api_key", ""))
            log_event(f"Bewertung [{feedback_result.get('confidence','?')}%]: {feedback_result['status']} — {feedback_result['grund']}")
            if feedback_result["status"] == "gut":
                success = True
                break
            else:
                with state_lock:
                    state["stats"]["retried"] += 1

        if success:
            mark_done(task["raw"], "x")
            with state_lock:
                state["stats"]["done"] += 1
                state["current_task"] = None
            log_event(f"Erledigt: {task['text']}")
        else:
            mark_done(task["raw"], "!")
            with state_lock:
                state["stats"]["failed"] += 1
                state["current_task"] = None
            log_event(f"Fehlgeschlagen: {task['text']}", "warning")

        time.sleep(2)


# ─── Thread 2: VS Code Dialog Confirm ─────────────────────────────────────────

def run_vscode_watcher():
    time.sleep(5)
    while True:
        try:
            config = load_config()
            if config.get("auto_confirm_vscode", True):
                n = computer.confirm_vscode_dialogs()
                if n > 0:
                    with state_lock:
                        state["vscode_dialogs_confirmed"] += n
                    log_event(f"VS Code Dialog bestätigt ({n}x)")
        except Exception:
            pass
        time.sleep(3)


# ─── Thread 3: VS Code Einzelfenster ─────────────────────────────────────────

def run_window_watcher():
    time.sleep(8)
    while True:
        try:
            config = load_config()
            if config.get("single_vscode_window", True) and computer.is_vscode_running():
                if computer.get_vscode_window_count() > 1:
                    computer.close_extra_vscode_windows()
                    log_event("VS Code: auf 1 Fenster reduziert")
        except Exception:
            pass
        time.sleep(8)


# ─── Thread 4: Passwort Monitor ───────────────────────────────────────────────

def run_password_monitor():
    time.sleep(6)
    last = {"url": "", "login_page": False, "domain": ""}
    while True:
        try:
            config = load_config()
            if not config.get("password_manager_enabled", True):
                time.sleep(5)
                continue

            vault = pv.get_vault(config.get("password_master_key", ""))

            if config.get("password_clipboard_capture", True):
                pw = pv.check_clipboard_for_password()
                if pw:
                    browser = pv.get_browser_state()
                    site = pv.extract_domain(browser["url"]) if browser["url"] else "unbekannt"
                    with state_lock:
                        state["last_clipboard_capture"] = {
                            "type": "clipboard_password",
                            "site": site,
                            "password_preview": pw[:3] + "•" * (len(pw) - 3),
                            "password": pw,
                            "time": datetime.now().strftime("%H:%M:%S"),
                        }

            browser = pv.get_browser_state()
            if browser["url"] and browser["url"] != last["url"]:
                if last["url"] and last["login_page"]:
                    entries = vault.get_for_site(last["domain"])
                    if pv.detect_login_error(browser["title"], browser["url"]):
                        for e in entries:
                            if e["status"] != "wrong":
                                vault.mark_wrong(e["id"])
                                with state_lock:
                                    state["password_alerts"].insert(0, {
                                        "type": "wrong_password",
                                        "site": e["site"],
                                        "username": e["username"],
                                        "time": datetime.now().strftime("%H:%M:%S"),
                                    })
                                log_event(f"Falsches Passwort: {e['site']}", "warning")
                    elif pv.detect_login_success(browser["title"], browser["url"]):
                        for e in entries:
                            if e["status"] == "wrong":
                                vault.mark_ok(e["id"])

                is_login = any(k in browser["url"].lower() for k in ["login", "signin", "auth", "anmeld", "password"])
                last = {"url": browser["url"], "title": browser["title"],
                        "domain": pv.extract_domain(browser["url"]), "login_page": is_login}
        except Exception:
            pass
        time.sleep(4)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    threads = [
        threading.Thread(target=run_task_loop,       daemon=True, name="tasks"),
        threading.Thread(target=run_vscode_watcher,  daemon=True, name="vscode"),
        threading.Thread(target=run_window_watcher,  daemon=True, name="windows"),
        threading.Thread(target=run_password_monitor,daemon=True, name="passwords"),
    ]
    for t in threads:
        t.start()

    # Flask im Hintergrund
    from dashboard_app import create_app
    flask_app = create_app(state, state_lock, CONFIG_FILE, TASKS_FILE, MODES_DIR)
    config = load_config()
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host="127.0.0.1", port=config["dashboard_port"],
                                     debug=False, use_reloader=False),
        daemon=True, name="flask"
    )
    flask_thread.start()

    # Menüleiste im Main-Thread (macOS-Anforderung)
    from menubar import JarvisMenuBar
    JarvisMenuBar(state, state_lock).run()


if __name__ == "__main__":
    main()
