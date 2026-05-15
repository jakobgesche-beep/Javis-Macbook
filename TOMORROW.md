# Morgen — Zwischen-Todo

## 1. Daemon installieren
```bash
bash daemon_install.sh install
bash daemon_install.sh status
```
→ Jarvis soll ab jetzt automatisch beim Login starten.

## 2. GitHub Repo anlegen & pushen
- Repo auf github.com erstellen (Name: `macbook-jarvis`)
- `git init && git add . && git commit -m "initial: Jarvis v1"`
- `git remote add origin https://github.com/...`
- `git push -u origin main`

## 3. Cloudflare Tunnel einrichten
```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:8080
```
→ URL ins Dashboard unter Einstellungen eintragen  
→ Damit funktioniert der Siri Shortcut auch außer Haus

## 4. Siri Shortcut bauen
- Kurzbefehle-App öffnen
- Neuer Shortcut: "Wenn ich 'Jarvis' sage → HTTP POST an `<tunnel-url>/webhook/jarvis`"
- Testen: "Hey Siri, Jarvis"

## 5. End-to-End testen
- [ ] Eine echte Aufgabe in `tasks/todo.md` eintragen
- [ ] Im Dashboard auf ▶ Starten klicken
- [ ] Schauen ob Claude Code die Aufgabe erledigt
- [ ] Bewertung im Log prüfen (Confidence-Wert)

## 6. Accessibility-Permission für Dialog-Confirm
Einstellungen → Datenschutz → Bedienungshilfen → Terminal/Code erlauben  
→ Danach funktioniert VS Code Auto-Confirm zuverlässig

## 7. Passwort-Vault testen
- Ein echtes Passwort manuell eintragen
- Clipboard-Erkennung testen: Passwort kopieren → Banner erscheint?
- Browser: auf eine Login-Seite gehen → funktioniert Fehler-Erkennung?
