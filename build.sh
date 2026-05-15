#!/bin/bash
set -e

cd "$(dirname "$0")"
VERSION="1.0.0"
APP_NAME="Jarvis"
DMG_NAME="MacBook-Jarvis-${VERSION}.dmg"
BUILD_DIR="dist"
DMG_DIR="/tmp/jarvis-dmg"

echo "🤖 MacBook Jarvis — Build v${VERSION}"
echo "======================================"

# venv aktivieren
source venv/bin/activate

echo "📦 Installiere Build-Dependencies..."
pip install pyinstaller rumps requests -q

echo "🔨 Baue .app mit PyInstaller..."
pyinstaller Jarvis.spec --noconfirm --clean

echo "✅ .app gebaut: dist/Jarvis.app"

# DMG erstellen
echo "💿 Erstelle DMG..."
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR"

cp -r "${BUILD_DIR}/${APP_NAME}.app" "$DMG_DIR/"

# Symlink zu Applications
ln -sf /Applications "$DMG_DIR/Applications"

# DMG bauen
hdiutil create \
  -volname "MacBook Jarvis" \
  -srcfolder "$DMG_DIR" \
  -ov \
  -format UDZO \
  -fs HFS+ \
  "${BUILD_DIR}/${DMG_NAME}"

rm -rf "$DMG_DIR"

echo ""
echo "✅ Fertig!"
echo "   App:  ${BUILD_DIR}/${APP_NAME}.app"
echo "   DMG:  ${BUILD_DIR}/${DMG_NAME}"
echo ""
echo "Nächste Schritte:"
echo "  1. DMG testen: open ${BUILD_DIR}/${DMG_NAME}"
echo "  2. DMG als GitHub Release hochladen"
echo "  3. Download-URL in website/index.html eintragen"
echo "  4. Website zu Cloudflare Pages pushen"
