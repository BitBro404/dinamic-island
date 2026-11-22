#!/usr/bin/env bash
# U7.2: copia la extensión provisional y la activa, siempre con confirmación.
set -euo pipefail
cd "$(dirname "$0")/.."

UUID='isla-dinamica@bitbro404.github.io'
SRC="extras/gnome-shell/$UUID"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"

if ! command -v gnome-extensions >/dev/null 2>&1; then
    echo "No se encontró gnome-extensions: esto solo tiene sentido en GNOME Shell." >&2
    exit 1
fi
if [[ ! -d "$SRC" ]]; then
    echo "Falta la extensión en $SRC" >&2
    exit 1
fi
if [[ ! -t 0 ]]; then
    echo "La instalación de la extensión necesita una terminal interactiva." >&2
    exit 1
fi

echo "Se instalará la extensión provisional $UUID en:"
echo "  $DEST"
read -r -p "¿Continuar? [s/N] " answer
if [[ ! "$answer" =~ ^[sS]([iI])?$ ]]; then
    echo "No se ha instalado nada."
    exit 0
fi

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST.new"
cp -r "$SRC" "$DEST.new"
rm -rf "$DEST"
mv "$DEST.new" "$DEST"

if gnome-extensions list --user 2>/dev/null | grep -qx "$UUID"; then
    gnome-extensions enable "$UUID"
    echo "Extensión instalada y activada."
else
    echo "Extensión copiada. Actívala con: gnome-extensions enable $UUID"
fi
