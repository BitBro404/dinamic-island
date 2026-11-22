#!/bin/sh
# Dentro del contenedor: Xvfb + Openbox (sin compositor) + la isla en X11. Deja capturas e informe en /out.
set -u
export DISPLAY=:99 XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=LXDE ISLA_NO_WELCOME=1 NO_AT_BRIDGE=1
Xvfb :99 -screen 0 1280x720x24 >/dev/null 2>&1 &
sleep 1
openbox >/dev/null 2>&1 &
sleep 1
xsetroot -solid "#3a78d8"     # después de Openbox (al arrancar pinta el fondo de negro)
cd /src
python3 -m isla_dinamica --doctor > /out/doctor.txt 2>&1
dbus-run-session -- python3 -m isla_dinamica > /out/isla.log 2>&1 &
sleep 7
import -window root /out/pill.png
W=$(xdotool search --name "Isla dinámica" | head -1)
{
  echo "ventana: $W"
  xdotool getwindowgeometry "$W"
  xprop -id "$W" _NET_WM_WINDOW_TYPE _NET_WM_STATE
  xprop -root _NET_ACTIVE_WINDOW
} > /out/window.txt 2>&1
# pasar el ratón por encima: se abre el panel
eval "$(xdotool getwindowgeometry --shell "$W")"
xdotool mousemove $((X + WIDTH / 2)) $((Y + HEIGHT / 2))
sleep 3
import -window root /out/open.png
xdotool getwindowgeometry "$W" >> /out/window.txt 2>&1
# arrastrar la isla al borde izquierdo
xdotool mousemove $((X + WIDTH / 2)) $((Y + 10)) mousedown 1 sleep 0.3 mousemove 300 300 sleep 0.3 \
        mousemove 20 360 sleep 0.5 mouseup 1
sleep 3
import -window root /out/left.png
echo "--- tras arrastrar a la izquierda" >> /out/window.txt
xdotool getwindowgeometry "$W" >> /out/window.txt 2>&1
pkill -f isla_dinamica
sleep 1
grep -c Traceback /out/isla.log > /out/tracebacks.txt || true
