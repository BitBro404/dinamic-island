#!/usr/bin/env bash
# Instala la isla del proyecto en ~/.local/share/isla-dinamica y la reinicia.
set -euo pipefail
cd "$(dirname "$0")"
DEST="$HOME/.local/share/isla-dinamica"
BIN="$HOME/.local/bin/isla-dinamica"

python3 -m compileall -q isla_dinamica
mkdir -p "$DEST" "$(dirname "$BIN")"
rm -rf "$DEST/isla_dinamica.new"
cp -r isla_dinamica "$DEST/isla_dinamica.new"
find "$DEST/isla_dinamica.new" -name '__pycache__' -prune -exec rm -rf {} +
rm -rf "$DEST/isla_dinamica"
mv "$DEST/isla_dinamica.new" "$DEST/isla_dinamica"

cat > "$BIN" <<'LAUNCH'
#!/usr/bin/env python3
"""Isla dinámica (instalada con install.sh)."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.local/share/isla-dinamica"))
from isla_dinamica.main import main  # noqa: E402

main()
LAUNCH
chmod +x "$BIN"

# reiniciar la que esté corriendo
for pid in $(ps -eo pid,args | awk '$2 ~ /python3$/ && ($3 ~ /isla-dinamica$/ || $3 ~ /isla\.py$/) {print $1}'); do
    kill "$pid" 2>/dev/null || true
done
sleep 0.8
ISLA_NO_WELCOME=1 setsid "$BIN" >/dev/null 2>&1 < /dev/null &
echo "Isla instalada en $DEST y reiniciada."
