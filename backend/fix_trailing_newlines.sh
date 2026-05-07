#!/usr/bin/env bash
# Run from inside your backend/ directory:
#   bash fix_trailing_newlines.sh

echo "Adding trailing newlines to all Python files that are missing them..."

find . -name "*.py" \
  -not -path "./venv/*" \
  -not -path "./.venv/*" \
  -not -path "*/__pycache__/*" | while read -r f; do
    # Check if last byte is NOT a newline
    last=$(tail -c 1 "$f" | xxd -p 2>/dev/null || printf "")
    if [ "$last" != "0a" ]; then
        printf '\n' >> "$f"
        echo "  fixed: $f"
    fi
done

echo "Done."