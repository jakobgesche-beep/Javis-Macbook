# MacBook Jarvis

Ein persönlicher AI-Supervisor-Daemon für macOS, der Claude Code autonom steuert.

## Was macht Jarvis?

Jarvis läuft im Hintergrund und übernimmt den kompletten Workflow:

1. Aufgaben aus `tasks/todo.md` lesen
2. Claude Code per subprocess starten
3. Output über die Anthropic API bewerten lassen
4. Bei schlechtem Ergebnis: Nachbesserungs-Prompt generieren und nochmal starten (max. 3 Retries)
5. Bei Erfolg: Aufgabe als erledigt markieren, nächste Aufgabe

Du sagst nur noch "Hey MacBook, Programmiermodus" — der Rest passiert automatisch.

## Features

- **AI Feedback Loop** — Claude Code arbeitet, Jarvis bewertet und korrigiert ohne manuellen Eingriff
- **Computer-Kontrolle** — Chrome-Tabs, Apps, Dateisystem und Terminal per AppleScript
- **Modi-System** — vordefinierte Arbeitsmodi richten den Workspace automatisch ein
- **Sprachsteuerung** — Siri Shortcut oder Alexa Routine → lokaler Webhook → Modus wechselt

## Modi

| Modus | Was passiert |
|---|---|
| Programmiermodus | Alle Tabs schließen, VS Code + Claude Code + Terminal öffnen |
| Recherche-Modus | Browser mit Quellen öffnen, Notion öffnen |
| Musik-Modus | Alle Apps minimieren, Spotify öffnen |
| Pause-Modus | Alles speichern, Claude Code stoppen |

## Projektstruktur

```
jarvis.py          # Haupt-Daemon
feedback.py        # Anthropic API Feedback Loop
computer.py        # AppleScript-Steuerung
webhook.py         # Flask Webhook-Server für Sprachsteuerung
modes/             # JSON-Configs für die einzelnen Modi
tasks/todo.md      # Aufgabenliste für Jarvis
config.json        # Persönliche Einstellungen
```

## Setup

```bash
cp config.example.json config.json
# config.json anpassen (API-Key, Pfade)

bash install.sh
```

## Status

In aktiver Entwicklung — siehe [TODO.md](TODO.md) für den aktuellen Stand der 5 Phasen.
