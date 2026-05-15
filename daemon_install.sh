#!/bin/bash
# Jarvis Daemon — Install / Uninstall / Status

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"
PLIST_SRC="$PROJECT_DIR/com.jarvis.daemon.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.jarvis.daemon.plist"
LAUNCH_LABEL="com.jarvis.daemon"

cmd="${1:-install}"

case "$cmd" in

  install)
    echo "🤖 Jarvis Daemon — Installation"
    echo "================================"

    if [ ! -f "$VENV_PYTHON" ]; then
      echo "❌ venv nicht gefunden. Bitte erst: bash install.sh"
      exit 1
    fi

    mkdir -p "$HOME/Library/LaunchAgents"
    mkdir -p "$PROJECT_DIR/logs"

    # Plist mit echten Pfaden befüllen
    sed \
      -e "s|VENV_PYTHON_PLACEHOLDER|$VENV_PYTHON|g" \
      -e "s|PROJECT_PATH_PLACEHOLDER|$PROJECT_DIR|g" \
      "$PLIST_SRC" > "$PLIST_DEST"

    # Laden
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    launchctl load "$PLIST_DEST"

    echo "✅ Daemon installiert und gestartet!"
    echo "   Dashboard: http://localhost:8080"
    echo "   Logs:      $PROJECT_DIR/logs/daemon.log"
    echo ""
    echo "   Jarvis startet jetzt automatisch bei jedem Login."
    ;;

  uninstall)
    echo "🛑 Jarvis Daemon — Deinstallation"
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm -f "$PLIST_DEST"
    echo "✅ Daemon entfernt. Jarvis startet nicht mehr automatisch."
    ;;

  status)
    echo "📊 Jarvis Daemon Status"
    launchctl list | grep jarvis || echo "❌ Daemon nicht aktiv"
    echo ""
    if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
      echo "✅ Dashboard erreichbar: http://localhost:8080"
    else
      echo "❌ Dashboard nicht erreichbar"
    fi
    ;;

  restart)
    bash "$0" uninstall
    sleep 1
    bash "$0" install
    ;;

  logs)
    tail -f "$PROJECT_DIR/logs/daemon.log"
    ;;

  *)
    echo "Verwendung: bash daemon_install.sh [install|uninstall|status|restart|logs]"
    ;;
esac
