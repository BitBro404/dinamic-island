#!/usr/bin/env bash
# Prueba de humo en X11 sin compositor (Docker: Xvfb + Openbox). Deja capturas e informe en tests/capturas/x11/.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-tests/capturas/x11}"
mkdir -p "$OUT"
docker build -q -t isla-x11 -f tests/docker/x11.Dockerfile . >/dev/null
docker run --rm -v "$PWD:/src:ro" -v "$(realpath "$OUT"):/out" isla-x11
echo "Tracebacks: $(cat "$OUT/tracebacks.txt")"
cat "$OUT/window.txt"
echo "Capturas en $OUT"
