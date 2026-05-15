import subprocess
import json
import os
import time


def run_applescript(script: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


# ─── Browser ──────────────────────────────────────────────────────────────────

def save_tabs(filepath: str = "logs/saved_tabs.txt"):
    script = """
    tell application "Google Chrome"
        set tab_urls to {}
        repeat with w in windows
            repeat with t in tabs of w
                set end of tab_urls to URL of t
            end repeat
        end repeat
        return tab_urls
    end tell
    """
    urls = run_applescript(script)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write(urls.replace(", ", "\n"))


def close_tabs():
    script = """
    tell application "Google Chrome"
        repeat with w in windows
            close w
        end repeat
    end tell
    """
    run_applescript(script)


def open_url(url: str):
    script = f"""
    tell application "Google Chrome"
        activate
        open location "{url}"
    end tell
    """
    run_applescript(script)


# ─── Apps ─────────────────────────────────────────────────────────────────────

def open_app(app_name: str):
    run_applescript(f'tell application "{app_name}" to activate')


def minimize_all():
    run_applescript("""
    tell application "System Events"
        set visible of every process to false
    end tell
    """)


# ─── VS Code ──────────────────────────────────────────────────────────────────

def get_vscode_window_count() -> int:
    script = """
    tell application "System Events"
        if exists process "Code" then
            return count of windows of process "Code"
        end if
        return 0
    end tell
    """
    try:
        return int(run_applescript(script) or "0")
    except Exception:
        return 0


def close_extra_vscode_windows():
    """Schließt alle VS Code Fenster außer dem vordersten."""
    script = """
    tell application "System Events"
        tell process "Code"
            set wins to windows
            if (count of wins) > 1 then
                repeat with i from 2 to count of wins
                    try
                        click button 1 of item i of wins
                    end try
                end repeat
            end if
        end tell
    end tell
    """
    run_applescript(script)


def open_project_in_vscode(project_path: str, close_others: bool = True):
    """Öffnet ein Projekt in VS Code, schließt optional andere Fenster."""
    if close_others:
        close_extra_vscode_windows()
        time.sleep(0.5)

    subprocess.Popen(["code", project_path])
    time.sleep(2)

    if close_others:
        close_extra_vscode_windows()


def open_jarvis_in_vscode(project_path: str, close_others: bool = True):
    """Öffnet Jarvis-Projekt in VS Code und öffnet Claude-Panel."""
    open_project_in_vscode(project_path, close_others)
    time.sleep(1.5)

    # VS Code Befehl: Claude-Panel öffnen (Cmd+Shift+P → claude)
    script = """
    tell application "Visual Studio Code"
        activate
    end tell
    tell application "System Events"
        tell process "Code"
            keystroke "p" using {command down, shift down}
        end tell
    end tell
    delay 0.8
    tell application "System Events"
        tell process "Code"
            keystroke "Claude: Focus on Claude Chat View"
            key code 36
        end tell
    end tell
    """
    run_applescript(script)


# ─── VS Code Dialog Auto-Confirm ──────────────────────────────────────────────

ALLOW_BUTTON_LABELS = [
    "Allow", "Yes", "Proceed", "Continue", "OK", "Accept",
    "Approve", "Confirm", "Grant", "Enable",
    "Erlauben", "Ja", "Weiter", "Fortfahren", "Bestätigen",
]

DENY_BUTTON_LABELS = [
    "Don't Allow", "No", "Cancel", "Deny", "Block", "Reject",
    "Nicht erlauben", "Nein", "Abbrechen", "Ablehnen",
]


def confirm_vscode_dialogs() -> int:
    """
    Sucht in VS Code nach Permission-Dialogen und klickt automatisch auf Allow/Yes.
    Gibt Anzahl der bestätigten Dialoge zurück.
    """
    confirmed = 0

    # Methode 1: Native macOS Dialoge die VS Code öffnet
    for label in ALLOW_BUTTON_LABELS:
        script = f"""
        tell application "System Events"
            try
                tell process "Code"
                    set allWindows to every window
                    repeat with w in allWindows
                        try
                            if exists button "{label}" of w then
                                click button "{label}" of w
                                return "clicked"
                            end if
                        end try
                        try
                            if exists sheet 1 of w then
                                if exists button "{label}" of sheet 1 of w then
                                    click button "{label}" of sheet 1 of w
                                    return "clicked"
                                end if
                            end if
                        end try
                    end repeat
                end tell
            end try
            return "none"
        end tell
        """
        result = run_applescript(script)
        if result == "clicked":
            confirmed += 1
            break

    # Methode 2: System-Dialog der on top liegt (z.B. Accessibility-Anfragen)
    script = """
    tell application "System Events"
        try
            set frontApp to name of first application process whose frontmost is true
            if frontApp is not "Code" then
                set dialogProcesses to every process whose name is "SecurityAgent" or name is "UserNotificationCenter"
                repeat with p in dialogProcesses
                    repeat with w in windows of p
                        try
                            if exists button "Allow" of w then
                                click button "Allow" of w
                                return "clicked_system"
                            end if
                            if exists button "OK" of w then
                                click button "OK" of w
                                return "clicked_ok"
                            end if
                        end try
                    end repeat
                end repeat
            end if
        end try
        return "none"
    end tell
    """
    result = run_applescript(script)
    if "clicked" in result:
        confirmed += 1

    # Methode 3: Claude Code notification im Notification Center
    script = """
    tell application "System Events"
        try
            tell process "NotificationCenter"
                set allGroups to every group of UI element 1 of scroll area 1 of window "Notification Center"
                repeat with g in allGroups
                    try
                        if exists button "Allow" of g then
                            click button "Allow" of g
                            return "clicked_nc"
                        end if
                    end try
                end repeat
            end tell
        end try
        return "none"
    end tell
    """
    result = run_applescript(script)
    if "clicked" in result:
        confirmed += 1

    return confirmed


def is_vscode_running() -> bool:
    script = """
    tell application "System Events"
        return exists process "Code"
    end tell
    """
    return run_applescript(script).lower() == "true"


def is_claude_visible_in_vscode() -> bool:
    """Prüft ob das Claude-Panel in VS Code sichtbar ist."""
    script = """
    tell application "System Events"
        try
            tell process "Code"
                set winTitle to name of front window
                return winTitle
            end tell
        end try
        return ""
    end tell
    """
    title = run_applescript(script)
    return bool(title)


# ─── Modi ─────────────────────────────────────────────────────────────────────

def apply_mode(mode_name: str, modes_dir: str = "modes") -> bool:
    path = os.path.join(modes_dir, f"{mode_name}.json")
    if not os.path.exists(path):
        return False

    with open(path) as f:
        mode = json.load(f)

    for action in mode.get("actions", []):
        t = action["type"]
        if t == "save_tabs":
            save_tabs()
        elif t == "close_tabs":
            close_tabs()
        elif t == "open_app":
            open_app(action["app"])
        elif t == "minimize_all":
            minimize_all()
        elif t == "open_url":
            open_url(action["url"])
        elif t == "open_vscode":
            open_project_in_vscode(action.get("path", ""), action.get("close_others", True))

    return True
