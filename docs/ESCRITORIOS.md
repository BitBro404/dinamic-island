# Comprobación por escritorio

La isla es la misma en todas partes: solo cambia el método que usa cada función. Esta guía sirve para
validarla en un escritorio nuevo y para entender qué significa lo que dice `--doctor`.

**Estado de la validación (2026-11-21):** comprobado en esta máquina con **Budgie/Wayland (labwc)** y en
**X11 con Xvfb + Openbox** (Docker). El resto de escritorios y la extensión de GNOME están implementados
pero **pendientes de prueba en VM**; la extensión se marca como **provisional** porque su JavaScript no se
pudo ejecutar aquí.

---

## 1. Antes de empezar

```bash
echo "$XDG_SESSION_TYPE"        # wayland o x11
echo "$XDG_CURRENT_DESKTOP"     # GNOME, KDE, XFCE…
isla-dinamica --doctor          # escritorio, backend de ventana y método de cada función
ISLA_DEBUG=1 python3 isla.py    # arranque con trazas (terminal aparte)
```

`--doctor` debe mostrar 15 funciones: Avisos, No molestar, Centro de avisos, Bloqueo, Apagar pantalla,
Inactividad, Portapapeles, Captura de pantalla, Grabación, Modo oscuro, Luz nocturna, Cerrar sesión,
Mantener despierto, Volumen y Sonidos. `no disponible` es válido: significa que la casilla o el botón se
ocultan, no que la isla esté rota.

### Lista común (todos los escritorios)

| # | Acción | Resultado esperado |
|---|---|---|
| 1 | Arrancar `isla-dinamica` | Píldora arriba al centro, sin barra de tareas, legible sobre fondo claro y oscuro |
| 2 | Pasar el ratón y hacer clic | Se abre el panel; las páginas cambian sin parpadeos |
| 3 | Arrastrar la píldora y soltarla | Se acopla al borde más cercano y recuerda la posición al reiniciar |
| 4 | Enviar una notificación (`notify-send 'Hola'`) | Aparece la tarjeta; el historial guarda hasta 60 y el punto rojo indica no leídas |
| 5 | Activar «No molestar» | Dejan de salir tarjetas (salvo urgentes); el botón del centro abre el panel del escritorio si existe |
| 6 | Copiar texto y abrir Inicio → Copias | El texto aparece en el historial; los secretos marcados por gestores de contraseñas no se guardan |
| 7 | Inicio → Recorte y Pantalla | Se guarda un PNG en `~/Imágenes/Capturas/` |
| 8 | Más → Grabar, grabar 3 s y parar | Se guarda un vídeo en `~/Vídeos/`; la píldora muestra «Grabando» en rojo |
| 9 | Casillas Oscuro y Luz nocturna | Cambian el tema/color del escritorio; si no hay método, la casilla no está |
| 10 | Inicio → Energía → Salir / Despierto | Cierra sesión o impide el apagado; al desactivar «Despierto» se libera el inhibidor |
| 11 | Botón de ajustes de una página | Abre el panel nativo de wifi/Bluetooth/energía/pantalla; si no hay app, no aparece |
| 12 | Rueda sobre la píldora y sonido de alarma | Sube/baja el volumen con `wpctl` o `pactl`; suena con `pw-play`, `paplay` o `canberra` |
| 13 | Activar Presencia, ausentarse | Bloquea **antes** de apagar la pantalla; si el bloqueo falla, la pantalla sigue encendida |

---

## 2. Qué esperar según el escritorio

Los nombres de la columna son los que imprime `--doctor` (no necesariamente los paquetes instalados).

### Wayland de wlroots: sway, Hyprland, Wayfire, river, labwc, niri

| Función | Método esperado |
|---|---|
| Ventana | `layer-shell` (nativo, capa overlay) |
| Bloqueo / pantalla | `swaylock` o `hyprlock`; `wlopm` o `swaymsg`/`hyprctl`; `swayidle`/`hypridle` para inactividad |
| Portapapeles / captura / grabación | `wl-paste --watch`, `grim + slurp`, `wf-recorder` |
| DND / centro | mako, SwayNC o dunst; centro de SwayNC si está |
| Ajustes / oscuro / sesión | Los del escritorio; `loginctl` y `systemd-inhibit` como respaldo |

En labwc, river y niri el autoarranque estándar no siempre se lee: el instalador imprime la línea `exec`
que hay que añadir a la configuración del compositor. No la escribe por ti.

### GNOME Wayland

| Situación | Ventana | Funciones |
|---|---|---|
| **Con la extensión provisional** | `GNOME Shell (extensión)` | La extensión aporta centro de avisos, inactividad, captura, grabación y colocación de la ventana. El resto usa gsettings, `wpctl` y SessionManager |
| **Sin la extensión** | Se relanza con XWayland (backend `X11`) | Avisos por el bus, DND de GNOME, `GNOME IdleMonitor`, portal para captura/grabación. Sin layer-shell, una ventana maximizada puede tapar la isla |

Instalación: `./install.sh --gnome-extension` (pregunta antes) y cerrar/reabrir la sesión. Si GNOME
cambia su API interna, `--doctor` seguiría mostrando el nombre de la extensión pero el método podría fallar:
desactívala y usa la ventana X11. **Esta es la pieza provisional que falta validar en VM.**

### KDE Plasma

| Función | Método esperado |
|---|---|
| Ventana | `layer-shell` en Wayland; `X11` en sesiones X11 |
| Avisos / DND | Bus de notificaciones y `KDE Plasma` (gsettings propios) |
| Pantalla / inactividad | `kscreen-doctor` o `xset`; `KDE ScreenSaver` o `XScreenSaver` |
| Captura / grabación | `spectacle`, o portal; `ffmpeg (X11)`/portal para grabar |
| Ajustes / sesión | `systemsettings` (`kcm_*`) y `KDE ksmserver` |
| Oscuro | `KDE ColorScheme` (si hay `kwriteconfig6`/`qdbus6`), si no portal de solo lectura |

### Cinnamon, MATE, XFCE, LXDE, LXQt, Budgie (sesión clásica o X11)

| Función | Método esperado |
|---|---|
| Ventana | `X11` (o `layer-shell` si el escritorio corre sobre wlroots) |
| Avisos / DND | Monitor genérico del bus; DND de Cinnamon, MATE, XFCE (`xfconf-query`), Budgie o dunst |
| Bloqueo / pantalla / inactividad | ScreenSaver del escritorio o `loginctl`; `xset`; `XScreenSaver` por `libXss` |
| Captura / grabación | `maim`/`scrot` o portal; `ffmpeg (X11)` |
| Ajustes / sesión | `cinnamon-settings`, `mate-control-center`, `xfce4-settings-manager`, `lxappearance`, `lxqt-config`; `xfce4-session-logout`, `MATE SessionManager` o `loginctl` |
| Oscuro | gsettings de Cinnamon/Budgie o portal; luz nocturna con `gammastep`/`redshift` si está |

Budgie sobre labwc (la máquina de desarrollo) usa `layer-shell`, `wlopm`, `swayidle`, `grim + slurp` y
`wf-recorder`. Si Raven no está en el bus, `--doctor` marca «Centro de avisos: no disponible» y el botón
se oculta: es el comportamiento previsto.

### Cualquier otro escritorio

Si no se reconoce el nombre, la isla usa las cadenas universales: monitor D-Bus, `loginctl`, `xset`,
XScreenSaver, `wpctl`/`pactl`, `Gtk.Clipboard`, `maim`/`scrot`/portal y `ffmpeg`/portal. Puede faltar
alguna función (se oculta), pero la píldora, el panel y las páginas que no dependen del escritorio
siguen funcionando.

---

## 3. Si algo no funciona

1. `isla-dinamica --doctor`: ¿qué escritorio y backend detectó? ¿Qué método aparece para la función?
2. Si dice `no disponible`, instala la herramienta que indica (o la de la tabla de tu escritorio) y
   reinicia la isla.
3. Si el método aparece pero no funciona, prueba esa herramienta por separado en la terminal; puede
   faltar permiso, un socket (`$WAYLAND_DISPLAY`, `$XDG_RUNTIME_DIR`) o el portal.
4. `ISLA_DEBUG=1 python3 isla.py` muestra trazas sin el lanzador instalado.
5. Adjunta la salida de `--doctor`, `echo $XDG_SESSION_TYPE`, `echo $XDG_CURRENT_DESKTOP` y la versión
   de tu distro al abrir un issue.

### Comprobación automatizada disponible

```bash
make check                          # compila + pruebas unitarias (incluye la regla de arquitectura)
bash tests/x11_smoke.sh             # Docker con Xvfb + Openbox: ventana DOCK, arriba, sin barra, arrastrable
python3 tests/harness.py pill home notifs --out /tmp/isla-check   # capturas con datos falsos
```

El arnés detiene y reinicia la isla instalada. Las capturas de referencia de X11 están en
`tests/capturas/x11/`.
