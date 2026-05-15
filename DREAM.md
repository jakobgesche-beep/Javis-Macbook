# MacBook Jarvis — Die Vision

## Was ist das?

Ein persönlicher AI-Supervisor der im Hintergrund läuft und Claude Code autonom steuert.
Jarvis übernimmt die Steuerung: Er liest Aufgaben, startet Claude Code, bewertet das Ergebnis
und entscheidet selbst ob nachgebessert wird oder die nächste Aufgabe dran ist.

Du sagst nur noch: "Hey MacBook, Programmiermodus" — und der Rechner richtet sich selbst ein.

---

## Das große Bild

### AI Feedback Loop
Claude Code arbeitet autonom an einer Aufgabe. Jarvis schickt das Ergebnis an die Anthropic API
und lässt es bewerten. Ist es gut → nächste Aufgabe. Ist es schlecht → Jarvis generiert einen
Nachbesserungs-Prompt und startet Claude Code nochmal. Ohne dass du eingreifen musst.

### Computer-Kontrolle
Jarvis hat vollen Zugriff auf den Mac:
- Tabs speichern und schließen (Chrome)
- Apps öffnen und schließen
- Dateisystem lesen und schreiben
- Terminal-Befehle ausführen

Alles per AppleScript + Shell.

### Kalender & Todos
Jarvis liest deinen Apple Calendar und deine Reminders.
Er weiß was heute ansteht und kann Claude Code-Aufgaben daraus priorisieren.

### Sprachsteuerung
Alexa Routine oder Siri Shortcut → Webhook → Jarvis wechselt den Modus.
Kein Tippen, keine Maus. Nur ein Satz.

### Modi-System
Vordefinierte Arbeitsmodi die automatisch den Workspace vorbereiten:

| Modus | Was passiert |
|---|---|
| Programmiermodus | Alle Tabs schließen, VS Code + Claude Code + Terminal öffnen |
| Recherche-Modus | Browser mit gespeicherten Quellen öffnen, Notion öffnen |
| Musik-Modus | Alle Apps minimieren, Spotify öffnen |
| Pause-Modus | Alles speichern, Claude Code stoppen |

---

## Warum das geil ist

- Kein Klicken auf Permission-Popups (--dangerously-skip-permissions)
- Kein manuelles Aufgaben-Copy-Paste in Claude Code
- Kein Workspace-Setup beim Moduswechsel
- Der Mac arbeitet für dich, nicht umgekehrt

---

## Endausbau

- Web-Dashboard: Siehst live was Jarvis gerade macht
- Tages-Log: "Heute hat Jarvis 7 Aufgaben erledigt, 2 nachgebessert"
- Open Source auf GitHub
- Mehr Modi nach Bedarf
