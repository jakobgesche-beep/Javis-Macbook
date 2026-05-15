#!/bin/bash
set -e

echo "🤖 MacBook Jarvis — Setup"
echo "========================="

# Python check
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 nicht gefunden. Bitte installieren: brew install python"
  exit 1
fi

# Claude Code check
if ! command -v claude &>/dev/null; then
  echo "❌ Claude Code nicht gefunden. Bitte installieren: npm install -g @anthropic-ai/claude-code"
  exit 1
fi

echo "✅ Python: $(python3 --version)"
echo "✅ Claude Code: $(claude --version 2>/dev/null || echo 'gefunden')"

# Venv
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "✅ Setup abgeschlossen!"
echo ""
echo "Nächste Schritte:"
echo "  1. API Key eintragen: öffne config.json und setze 'anthropic_api_key'"
echo "  2. Jarvis starten:    source venv/bin/activate && python3 jarvis.py"
echo "  3. Dashboard öffnen: http://localhost:8080"
echo ""
echo "Optional — Cloudflare Tunnel für Siri/Alexa:"
echo "  brew install cloudflared"
echo "  cloudflared tunnel --url http://localhost:8080"
