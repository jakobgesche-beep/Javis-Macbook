# MacBook Jarvis — Setup Checklist

Schritt-für-Schritt um das Projekt von null lauffähig zu kriegen.

---

## Voraussetzungen

- [ ] Python 3.11+ installiert (`python3 --version`)
- [ ] Claude Code CLI installiert (`claude --version`)
- [ ] Anthropic API Key vorhanden (console.anthropic.com)
- [ ] API Key als Umgebungsvariable gesetzt (`export ANTHROPIC_API_KEY=sk-...`)
- [ ] pip installiert (`pip3 --version`)

---

## Projekt aufsetzen

- [ ] Projektordner angelegt (`~/Downloads/macbook-jarvis/`)
- [ ] Virtuelle Python-Umgebung erstellt (`python3 -m venv venv`)
- [ ] Venv aktiviert (`source venv/bin/activate`)
- [ ] Abhängigkeiten installiert:
  - [ ] `pip install anthropic`
  - [ ] `pip install flask`
  - [ ] `pip install pyobjc` (für Kalender, optional)
- [ ] `requirements.txt` erstellt (`pip freeze > requirements.txt`)

---

## Dateien erstellen

- [ ] `jarvis.py` — Haupt-Daemon
- [ ] `feedback.py` — Anthropic API Feedback Loop
- [ ] `computer.py` — AppleScript-Steuerung
- [ ] `modes/` — Ordner für Modus-JSONs
  - [ ] `modes/programmieren.json`
  - [ ] `modes/recherche.json`
  - [ ] `modes/musik.json`
  - [ ] `modes/pause.json`
- [ ] `tasks/todo.md` — Aufgabenliste für Jarvis
- [ ] `webhook.py` — Flask Webhook-Server
- [ ] `config.json` — Persönliche Einstellungen

---

## Phase 1 testen

- [ ] `python3 jarvis.py` startet ohne Fehler
- [ ] Jarvis liest erste Aufgabe aus `tasks/todo.md`
- [ ] Claude Code wird korrekt per subprocess gestartet
- [ ] Claude Code Output wird in Datei gespeichert
- [ ] Aufgabe wird nach Abschluss als erledigt markiert

---

## Phase 2 testen

- [ ] Anthropic API antwortet auf Bewertungs-Prompt
- [ ] Bei "gut": nächste Aufgabe wird gestartet
- [ ] Bei "nachbessern": Claude Code startet nochmal mit neuem Prompt
- [ ] Nach 3 Retries wird Aufgabe als "fehlgeschlagen" markiert

---

## Phase 3 testen

- [ ] AppleScript öffnet Chrome-Tab erfolgreich
- [ ] AppleScript schließt Chrome-Tabs und speichert URLs
- [ ] VS Code wird per Script geöffnet
- [ ] Modus "Programmieren" läuft vollständig durch

---

## Phase 4 testen

- [ ] `python3 webhook.py` startet auf Port 5000
- [ ] `curl -X POST localhost:5000/modus -d '{"modus":"programmieren"}'` wechselt Modus
- [ ] Siri Shortcut sendet erfolgreichen Request an lokalen Server

---

## Hintergrund-Daemon

- [ ] launchd plist erstellt unter `~/Library/LaunchAgents/com.jarvis.daemon.plist`
- [ ] Daemon geladen: `launchctl load ~/Library/LaunchAgents/com.jarvis.daemon.plist`
- [ ] Daemon läuft nach Neustart automatisch
- [ ] Daemon stoppen: `launchctl unload ~/Library/LaunchAgents/com.jarvis.daemon.plist`

---

## Bereit zum Benutzen

- [ ] Jarvis läuft im Hintergrund
- [ ] Erste echte Aufgabe in `tasks/todo.md` eingetragen
- [ ] Sprachbefehl funktioniert
- [ ] Dashboard erreichbar unter `localhost:8080`
