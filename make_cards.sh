#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: make_cards.sh <session-folder>"
    echo ""
    echo "  Generates a print-ready PDF of ASK picture cards from a folder of images."
    echo "  The filename (without extension) is used as the card label."
    echo ""
    echo "  Arguments:"
    echo "    <session-folder>   Path to a session folder, e.g. sessions/2026-03-familie"
    echo ""
    echo "  Output:"
    echo "    output/<session-name>.pdf"
    echo ""
    echo "  Supported image formats: jpg, jpeg, png, webp, avif"
    echo ""
    echo "  Examples:"
    echo "    make_cards.sh sessions/2026-03-familie"
    echo "    make_cards.sh sessions/2026-04-skole"
}

if [[ $# -eq 0 || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

python3 "$SCRIPT_DIR/make_cards.py" "$1"
