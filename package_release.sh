#!/bin/bash
# package_release.sh — Tworzy paczke ZIP do wydania
# Uzycie: ./package_release.sh [wersja]
# Przyklad: ./package_release.sh 1.0.0

set -e

VERSION="${1:-1.0.0}"
OUTPUT="udzialy-bot-v${VERSION}.zip"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

echo "========================================"
echo "  Pakowanie udzialy-bot v${VERSION}"
echo "========================================"
echo ""

cd "$PROJECT_DIR"

# Remove old release if exists
rm -f "$OUTPUT"

# Create ZIP excluding dev/build artifacts
zip -r "$OUTPUT" . \
    -x ".git/*" \
    -x ".git" \
    -x "__pycache__/*" \
    -x "*/__pycache__/*" \
    -x "*/*/__pycache__/*" \
    -x ".venv/*" \
    -x ".venv" \
    -x "*.pyc" \
    -x ".pytest_cache/*" \
    -x ".pytest_cache" \
    -x ".mypy_cache/*" \
    -x ".mypy_cache" \
    -x "tor/data/*" \
    -x "tor/tor.exe" \
    -x "tor/tor-bundle.tar.gz" \
    -x "tor/*.dll" \
    -x "tor/notices.log" \
    -x "bot.log" \
    -x "*.log" \
    -x ".env" \
    -x "udzialy-bot-v*.zip"

echo ""
echo "========================================"
echo "  Gotowe: $OUTPUT"
echo "  Rozmiar: $(du -h "$OUTPUT" | cut -f1)"
echo "========================================"
echo ""
echo "Zawartosc:"
unzip -l "$OUTPUT" | tail -1
echo ""
echo "Aby sprawdzic zawartosc: unzip -l $OUTPUT"
