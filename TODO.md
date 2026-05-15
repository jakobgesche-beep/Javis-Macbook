# MacBook Jarvis — Todo

## Phase 1 — Fundament
- [ ] Python-Daemon-Grundstruktur aufsetzen (jarvis.py)
- [ ] launchd plist erstellen damit Jarvis im Hintergrund startet
- [ ] todo.md Format definieren (Aufgaben als Markdown-Checklist)
- [ ] Claude Code per subprocess starten können
- [ ] --dangerously-skip-permissions Flag einbauen
- [ ] Einfacher Loop: Aufgabe lesen → Claude Code starten → auf Ende warten
- [ ] Output von Claude Code abfangen und speichern

## Phase 2 — AI Feedback Loop
- [ ] Anthropic API einbinden (pip: anthropic)
- [ ] Bewertungs-Prompt bauen: "Bewerte diese Arbeit: {output}"
- [ ] API-Response parsen: gut / nachbessern
- [ ] Bei "nachbessern": neuen Prompt generieren und Claude Code nochmal starten
- [ ] Maximale Retry-Anzahl definieren (z.B. 3x) um Endlosschleifen zu verhindern
- [ ] Aufgabe nach Erfolg in todo.md als erledigt markieren

## Phase 3 — Computer-Kontrolle
- [ ] AppleScript: Chrome Tabs speichern (URLs in Datei schreiben)
- [ ] AppleScript: Chrome Tabs schließen
- [ ] AppleScript: Apps öffnen (VS Code, Terminal, Spotify usw.)
- [ ] AppleScript: Apps schließen / minimieren
- [ ] Apple Kalender lesen (ical-Parser oder pyobjc)
- [ ] Apple Reminders lesen
- [ ] Modi als JSON-Config-Dateien definieren
- [ ] Modus-Wechsel-Funktion implementieren (Config laden + ausführen)

## Phase 4 — Sprachsteuerung
- [ ] Flask/FastAPI Webhook-Server aufsetzen (läuft lokal)
- [ ] Endpunkt: POST /modus mit Body {"modus": "programmieren"}
- [ ] Siri Shortcut erstellen: HTTP Request → lokaler Webhook
- [ ] Alexa Routine → IFTTT/Make → Webhook (optional, wenn Alexa vorhanden)
- [ ] Modi per Sprachbefehl auslösen

## Phase 5 — Polish
- [ ] Web-Dashboard (einfaches HTML/Flask) das live Status zeigt
- [ ] Tages-Log: was wurde erledigt, was wurde nachgebessert
- [ ] Konfigurationsdatei für persönliche Einstellungen (config.json)
- [ ] Fehlerbehandlung und Logging verbessern
- [ ] README schreiben
- [ ] Auf GitHub veröffentlichen
