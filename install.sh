#!/usr/bin/env bash
# Instala la isla del proyecto en ~/.local/share/isla-dinamica y la reinicia.
#   install.sh             instala o actualiza
#   install.sh --deps      calcula los paquetes según distro/escritorio y pide confirmación
#   install.sh --help      ayuda
set -euo pipefail
cd "$(dirname "$0")"

CLI=(python3 tools/install_cli.py)
DEST="$HOME/.local/share/isla-dinamica"
BIN="$HOME/.local/bin/isla-dinamica"
AUTOSTART="$HOME/.config/autostart/isla-dinamica.desktop"
RESTART=1

usage() {
    cat <<'USO'
Uso: ./install.sh [opción]

  (sin opciones)     Instala o actualiza la isla y la reinicia
  --deps             Muestra los paquetes que faltan y, si confirmas, los instala
  --gnome-extension  Instala la extensión provisional de GNOME (pregunta antes)
  --no-restart       Instala sin reiniciar la isla que esté corriendo
  --help             Muestra esta ayuda

El lanzador acepta `isla-dinamica --doctor` para ver qué método usa cada función.
USO
}

case "${1:-}" in
    --help|-h)
        usage
        exit 0
        ;;
    --deps)
        "${CLI[@]}" deps-plan
        if [[ ! -t 0 ]]; then
            echo "La instalación de paquetes necesita una terminal interactiva." >&2
            exit 1
        fi
        read -r -p "¿Instalar estos paquetes? [s/N] " answer
        if [[ ! "$answer" =~ ^[sS]([iI])?$ ]]; then
            echo "No se ha instalado nada."
            exit 0
        fi
        mapfile -t CMD < <("${CLI[@]}" deps-command)
        "${CMD[@]}"
        echo "Dependencias instaladas."
        exit 0
        ;;
    --gnome-extension)
        bash tools/install_gnome_extension.sh
        exit 0
        ;;
    --no-restart)
        RESTART=0
        ;;
    "")
        ;;
    *)
        echo "Opción desconocida: $1" >&2
        usage >&2
        exit 1
        ;;
esac

python3 -m compileall -q isla_dinamica
mkdir -p "$DEST" "$(dirname "$BIN")" "$(dirname "$AUTOSTART")"
rm -rf "$DEST/isla_dinamica.new"
cp -r isla_dinamica "$DEST/isla_dinamica.new"
find "$DEST/isla_dinamica.new" -name '__pycache__' -prune -exec rm -rf {} +
rm -rf "$DEST/isla_dinamica"
mv "$DEST/isla_dinamica.new" "$DEST/isla_dinamica"

"${CLI[@]}" launcher "$DEST" > "$BIN"
chmod +x "$BIN"
"${CLI[@]}" autostart > "$AUTOSTART"

if hint="$("${CLI[@]}" hint)"; [[ -n "$hint" ]]; then
    echo "Este compositor no tiene autoarranque estándar. Añade a su configuración:"
    echo "    $hint"
fi

if [[ "$RESTART" == 1 ]]; then
    # reiniciar la que esté corriendo
    for pid in $(ps -eo pid,args | awk '$2 ~ /python3$/ && ($3 ~ /isla-dinamica$/ || $3 ~ /isla\.py$/) {print $1}'); do
        kill "$pid" 2>/dev/null || true
    done
    sleep 0.8
    ISLA_NO_WELCOME=1 setsid "$BIN" >/dev/null 2>&1 < /dev/null &
fi
echo "Isla instalada en $DEST y lanzador en $BIN."
