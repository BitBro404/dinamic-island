# Plan: isla dinámica universal (cualquier escritorio y distro Linux)

Estado: **TERMINADO** (fases U0–U8 ejecutadas con TDD el 2026-11-21; queda la validación del usuario en VM).
Plan anterior archivado en `.ai/plans/2026-11-21-seguridad-refactor.md`.

## Objetivo y resultado esperado
Que la isla funcione en KDE Plasma, GNOME, Cinnamon, MATE, XFCE, LXDE, LXQt, Budgie, sway, Hyprland, Wayfire,
river, labwc y cualquier otro escritorio, en Wayland o X11, y en las familias de distros Debian/Ubuntu,
Fedora, Arch y openSUSE.
- **Lo básico funciona en todas partes:** píldora, panel, reloj, música (MPRIS), batería, avisos, Wi-Fi,
  Bluetooth, temporizador, pomodoro, clima, GitHub y el resto de páginas que no dependen del escritorio.
- **Lo que depende del escritorio** (bloqueo, apagar pantalla, inactividad, portapapeles, capturas, grabación,
  modo oscuro, luz nocturna, No molestar, ajustes) usa el mejor método disponible en cada escritorio.
- **Si no hay ningún método,** la función se oculta o muestra «No disponible en este escritorio».
- **`isla-dinamica --doctor`** dice qué escritorio detectó, qué método usa cada función y qué paquete falta.

## Alcance
- Repositorio: solo `dinamic island` (un repo).
- Incluido: paquete `isla_dinamica/platform/`, ventana X11, servicios con varios métodos, `install.sh --deps`,
  autoarranque por escritorio, extensión provisional de GNOME Shell, README y documentación.
- Excluido: escritorios que no sean Linux (BSD, macOS), Flatpak o Snap, y traducciones.

## Contexto actual (medido el 2026-11-21)
Puntos atados a Budgie/labwc:

| Función | Hoy | Problema fuera de Budgie/wlroots |
|---|---|---|
| Ventana | GtkLayerShell (`window.py`, `ui/dock.py`) | GNOME, Cinnamon, Weston y toda sesión X11 no tienen layer-shell |
| Avisos | Dispatcher de Budgie por D-Bus (`services/notifications.py`) | En otros escritorios no llega ningún aviso |
| No molestar y centro de avisos | Budgie y Raven | No existen fuera de Budgie |
| Bloqueo (presencia) | BudgieScreenlock → `loginctl` | Bien en general; falta swaylock en sway y similares |
| Apagar pantalla | `wlopm` | Solo wlroots |
| Inactividad | `swayidle` (ext-idle-notify) | No funciona en GNOME ni en X11 |
| Portapapeles | `wl-paste --watch` / `wl-copy` | No funciona en GNOME (no tiene data-control) ni en X11 |
| Capturas | `grim` + `slurp` | Solo wlroots |
| Grabación | `wf-recorder` | Solo wlroots |
| Modo oscuro y luz nocturna | gsettings de GNOME | Sin efecto en KDE, XFCE, LXQt, Cinnamon (claves propias) |
| Cerrar sesión y mantener despierto | `org.gnome.SessionManager` | No existe en KDE, XFCE, LXQt ni sway |
| Ajustes | `budgie-control-center` | Solo Budgie |
| Volumen y sonidos | `wpctl`, `pw-play` | Solo PipeWire (no PulseAudio puro) |
| Autoarranque | `.desktop` con `/home/luis` fijo | Ruta de un usuario; sway y Hyprland no leen `~/.config/autostart` |

Ya son universales: MPRIS, UPower, logind, BlueZ, NetworkManager (`nmcli`), rfkill, GVolumeMonitor (USB),
power-profiles-daemon (también `tuned-ppd` de Fedora), `parec`/`pactl` (PipeWire-Pulse o PulseAudio) y `gh`/`git`.

En esta máquina hay Budgie Wayland con XWayland, `labwc`, `swayidle`, `wlopm`, `grim`, `slurp`, `wf-recorder`,
`ffmpeg`, `xdotool`, `xset` y Docker. No hay GNOME, KDE, Cinnamon, sway ni Xvfb.

## Decisiones confirmadas (2026-11-21)
- D1. **Soporte para todos.** Si un escritorio necesita una pieza nativa propia (extensión), se crea como
  versión provisional.
- D2. **Funciones sin método:** se ocultan o se marcan «No disponible», y se añade el comando `--doctor`.
- D3. **Dependencias:** `install.sh --deps` detecta apt/dnf/pacman/zypper, muestra el comando y lo ejecuta con
  sudo solo si el usuario confirma.
- D4. **Pruebas:** pruebas unitarias de detección y de cada método; la ventana X11 se prueba aquí (XWayland) y
  en Docker con Xvfb y Openbox. GNOME, KDE y el resto los prueba el usuario en una VM u otro equipo, con una
  lista de comprobación por escritorio.

## Decisiones propuestas (se aprueban con el plan)
- P1. **Si no hay layer-shell, X11.** Si la sesión es Wayland y el compositor no tiene layer-shell (GNOME,
  Cinnamon Wayland, Weston, otros), la isla se relanza sola con `GDK_BACKEND=x11` y corre en XWayland como
  ventana X11. En una sesión X11 es ventana X11 desde el principio.
- P2. **Ventana X11:** sin bordes, siempre encima, en todos los escritorios virtuales, fuera de la barra de
  tareas y de Alt+Tab (tipo `DOCK`), y colocada con `move()`.
  - Sin compositor (LXDE/Openbox puro), las esquinas redondeadas se recortan con una máscara de forma
    (`shape_combine_region`), así no se ve un rectángulo negro.
- P3. **Extensión de GNOME Shell (provisional):** `extras/gnome-shell/isla-dinamica@bitbro404.github.io/`
  (GNOME 45+).
  - Busca la ventana de la isla por `wm_class` y la deja encima de todo, en todos los espacios, sin
    Alt+Tab ni vista general, y sin animaciones.
  - Expone por D-Bus `GetIdletime` (el que Mutter ya tiene) y `Screenshot` y `Screencast`, para lo que GNOME
    solo permite a la Shell.
  - Con la extensión activa, la isla corre como Wayland nativo en GNOME; sin ella, en XWayland (P1).
- P4. **Cada función con varios métodos es una cadena:** el primer método disponible gana (inversión de
  dependencias: los servicios piden «bloquear», no «Budgie»). Cada método declara `available()` con
  `which`/bus inyectables para probarlo sin el escritorio real.
- P5. **La seguridad se mantiene:** bloqueo verificado antes de apagar la pantalla (S2), contraseñas por stdin
  (S1) y URLs seguras (S3). Los métodos nuevos pasan las mismas pruebas.

## Suposiciones y restricciones
- systemd-logind presente (todas las distros principales). Sin él, bloqueo y energía usan solo los métodos del
  escritorio.
- GTK3 + PyGObject: los paquetes existen en las cuatro familias de distros.
- **Eavesdropping de D-Bus:** los avisos genéricos se leen con `BecomeMonitor` en el bus de sesión (permitido
  al mismo usuario en dbus-daemon y dbus-broker). Si una distro lo prohíbe, `--doctor` lo dice.
- No se puede probar de verdad GNOME, KDE, Cinnamon, XFCE, LXQt ni sway en esta máquina (ver D4).

## Arquitectura objetivo
```
isla_dinamica/platform/            ← nuevo: lo único que sabe en qué escritorio estamos
  desktop.py    Desktop(family, session, layer_shell) y detect(env) — función pura
  chain.py      Backend (available/name) + first_available(chain) + Tools(which, bus) inyectables
  lock.py       Budgie → org.freedesktop.ScreenSaver → org.gnome/cinnamon/mate.ScreenSaver →
                loginctl lock-session → swaylock -f → xdg-screensaver lock
  screen.py     apagar/encender: wlopm → swaymsg/hyprctl → kscreen-doctor → Mutter (extensión) → xset dpms
  idle.py       swayidle (ext-idle) → org.freedesktop.ScreenSaver.GetSessionIdleTime (KDE) →
                Mutter IdleMonitor (GNOME) → XScreenSaver (X11, por ctypes sin dependencias)
  clipboard.py  wl-paste --watch (wlroots/KDE) → Gtk.Clipboard owner-change (X11/XWayland)
  capture.py    grim+slurp → spectacle → extensión GNOME/portal → maim/scrot → xdg-desktop-portal Screenshot
  record.py     wf-recorder → gpu-screen-recorder → ffmpeg x11grab (X11) → extensión GNOME (Screencast)
  dnd.py        Budgie → GNOME gsettings → KDE Notifications.Inhibit → Cinnamon/MATE gsettings →
                xfconf → makoctl / swaync-client / dunstctl
  appearance.py oscuro: gsettings GNOME/Budgie, Cinnamon, MATE, xfconf, plasma-apply-colorscheme;
                lectura universal por el portal org.freedesktop.appearance.
                Luz nocturna: GNOME, Cinnamon, KDE (org.kde.KWin.NightLight).
  session.py    cerrar sesión (GNOME/Cinnamon/MATE SessionManager, KDE ksmserver, xfce4-session-logout,
                lxqt-leave, swaymsg exit, hyprctl dispatch exit, labwc --exit) y mantener despierto
                (SessionManager → ScreenSaver.Inhibit → systemd-inhibit)
  apps.py       ajustes por escritorio (panel wifi/bluetooth/energía) y monitor del sistema
  audio.py      volumen wpctl → pactl; sonido pw-play → paplay → canberra-gtk-play
  doctor.py     informe de texto: escritorio, método elegido por función, qué instalar
ui/placement.py LayerShellPlacement | X11Placement (misma interfaz: place(x, y, edge), set_size)
services/*      usan platform.* (nunca nombres de escritorio)
extras/gnome-shell/…  extensión provisional (P3)
```
Regla nueva: fuera de `platform/` y `ui/placement.py` no aparece ningún nombre de escritorio, comando de
compositor ni servicio D-Bus de un escritorio. Se comprueba con una prueba que busca esos nombres.

## Criterios de aceptación
1. Todas las pruebas en verde (las 118 actuales y las nuevas).
2. `detect()` reconoce, a partir de variables de entorno reales, al menos: budgie, gnome, kde, cinnamon, mate,
   xfce, lxde, lxqt, sway, hyprland, wayfire, river, labwc, pantheon, deepin, unity y «other», en Wayland y X11.
3. Cada cadena de `platform/` tiene pruebas: elige el método correcto según lo instalado y nunca falla si no
   hay ninguno.
4. Aquí, en Budgie Wayland, todo sigue igual: capturas del arnés sin cambios.
5. La isla corre como ventana X11 en XWayland (`GDK_BACKEND=x11`) y en Docker con Xvfb y Openbox: se ve,
   queda encima, se puede arrastrar y acoplar, y abre el panel.
6. `isla-dinamica --doctor` funciona en ambos modos.
7. `install.sh --deps` genera el comando correcto para apt, dnf, pacman y zypper (con pruebas del generador).
8. Autoarranque sin rutas fijas de usuario; instrucciones para sway, Hyprland y river (`exec`).
9. Lista de comprobación por escritorio en `docs/ESCRITORIOS.md` para que el usuario valide en VMs.
10. Ningún nombre de escritorio fuera de `platform/` y `ui/placement.py` (prueba automática).

## Estrategia de pruebas
- Unitarias puras con `Tools` falsos (un `which` que dice qué está instalado y un bus que responde lo que la
  prueba quiere).
- Caracterización primero: lo que hoy pasa en Budgie (método elegido = el actual) se fija antes de mover nada.
- **Integración X11:** `GDK_BACKEND=x11 python3 isla.py` aquí, y una imagen Docker
  (`tests/docker/x11.Dockerfile`: Debian + python3-gi + gir1.2-gtk-3.0 + xvfb + openbox + xdotool).
  - El arnés captura la pantalla del Xvfb con `import -window root`.
  - Con `xdotool` se comprueba que la ventana está arriba, sin decoración y en la posición acoplada.
- Arnés actual en Budgie para comprobar que no cambia nada.

## Tareas

### Fase U0 — Detección y diagnóstico
- [x] **U0.1 `platform/desktop.py`**: `detect(env)` → `Desktop(family, session, compositor)`.
  - Prueba RED `test_platform_desktop.py`: tabla de entornos reales (XDG_CURRENT_DESKTOP «KDE»,
    «ubuntu:GNOME», «X-Cinnamon», «LXQt», «Budgie:GNOME», «sway», «Hyprland», DESKTOP_SESSION=«LXDE», solo
    SWAYSOCK…) → familia y sesión esperadas.
- [x] **U0.2 `platform/chain.py`**: `Tools(which, session_bus, system_bus)`, `Backend`, `first_available`.
  - Prueba: elige el primero disponible, salta los que lanzan excepción y devuelve `None` si no hay ninguno.
- [x] **U0.3 `platform/doctor.py`** + `main.py --doctor`.
  - Prueba: con `Tools` falsos, el informe lista cada función con su método o «falta: <paquete>».

### Fase U1 — Ventana en cualquier escritorio
- [x] **U1.1 `ui/placement.py`**: sacar de `ui/dock.py` y `window.py` todo lo de GtkLayerShell a
  `LayerShellPlacement` (sin cambiar el comportamiento). Las capturas del arnés no deben cambiar.
- [x] **U1.2 `X11Placement`**: cálculo puro `x11_geometry(edge, pos, w, h, monitor)` reutilizando `dock_xy`
  (prueba) y la ventana configurada como en P2.
- [x] **U1.3 Elección y relanzamiento** en `main.py`: Wayland con layer-shell → LayerShell; Wayland sin
  layer-shell y sin extensión → `os.execv` con `GDK_BACKEND=x11` (una sola vez, marcado con una variable);
  X11 → X11.
  - Prueba pura `choose_backend(desktop, layer_shell_ok, gnome_ext_ok, env)`.
- [x] **U1.4 Máscara de forma** sin compositor (`screen.is_composited()` falso).
- [x] **U1.5 Teclado en X11**: que el campo de contraseña Wi-Fi y la búsqueda del clima reciban el foco
  (`set_accept_focus` y `present` al abrir el panel; prueba manual con xdotool).
- [x] **U1.6 Docker X11**: Dockerfile y script `tests/x11_smoke.sh` que arranca Xvfb + Openbox + la isla,
  captura la pantalla y comprueba con xdotool.

### Fase U2 — Avisos y No molestar
- [x] **U2.1 Monitor genérico** de `org.freedesktop.Notifications.Notify` (BecomeMonitor en una conexión
  propia). Se mantiene el de Budgie como primer método. Prueba: los parámetros de un `Notify` se convierten
  en el mismo diccionario que hoy (función pura compartida).
- [x] **U2.2 `platform/dnd.py`**: leer, cambiar y escuchar «No molestar» por escritorio o daemon (lista de
  arquitectura). Prueba por método con bus o comandos falsos.
- [x] **U2.3 Centro de avisos**: Budgie Raven, `swaync-client -t`, GNOME (extensión o `Main.panel`); si no hay
  método, el botón se oculta.

### Fase U3 — Presencia: bloqueo, pantalla e inactividad
- [x] **U3.1 `platform/lock.py`** con verificación (S2): un método solo cuenta como éxito si acepta la orden.
  `Presence` y `Power.lock` lo usan. Prueba: ningún método → False → no se apaga la pantalla (la prueba S2
  sigue en verde).
- [x] **U3.2 `platform/screen.py`**: apagar y encender por escritorio. Prueba por método (argv esperado).
- [x] **U3.3 `platform/idle.py`**: `IdleWatch` con dos formas, proceso (swayidle) o sondeo (idle_ms cada
  2 s), con la misma interfaz `on_idle`/`on_active`. Prueba del sondeo con reloj e `idle_ms` falsos. XScreenSaver
  por ctypes (`libXss.so.1`), sin depender de xprintidle.

### Fase U4 — Portapapeles, capturas y grabación
- [x] **U4.1 Portapapeles**: método Gtk.Clipboard `owner-change` para X11/XWayland y `copy` con
  `Gtk.Clipboard.set_text` + `store`. Mismo filtro de secretos (S4). Prueba: `History` intacto; elección de
  método.
- [x] **U4.2 Capturas**: cadena de `platform/capture.py` con área y pantalla completa; el portal
  `org.freedesktop.portal.Screenshot` como último recurso universal. Prueba del argv por método.
- [x] **U4.3 Grabación**: cadena de `platform/record.py`; ffmpeg x11grab con área (`-video_size`/`-i :0+x,y`) y
  audio de `pulse`. Si no hay método, la página Grabar se oculta. Prueba del argv.

### Fase U5 — Ajustes rápidos y sesión
- [x] **U5.1 `platform/appearance.py`**: oscuro y luz nocturna por escritorio; lectura del oscuro por el
  portal. La casilla se oculta si no hay método.
- [x] **U5.2 `platform/session.py`**: cerrar sesión y mantener despierto (cadena; `systemd-inhibit` como último
  recurso, guardando el proceso).
- [x] **U5.3 `platform/apps.py`**: ajustes (wifi, bluetooth, energía, pantalla) y monitor del sistema por
  escritorio; `Page._settings` y la página Sistema lo usan. Prueba: tabla escritorio → argv.
- [x] **U5.4 `platform/audio.py`**: volumen con `pactl` si no hay `wpctl`; sonido con
  `pw-play` → `paplay` → `canberra-gtk-play`. Prueba de `parse` de la salida de pactl.

### Fase U6 — Instalación y arranque
- [x] **U6.1 `install.sh --deps`**: el generador de paquetes en `tools/deps.py` (puro y probado), con
  paquetes por familia y por escritorio. Ejemplos:
  - apt: `python3-gi gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 …`
  - dnf: `python3-gobject gtk3 gtk-layer-shell …`
  - pacman: `python-gobject gtk3 gtk-layer-shell …`
  - zypper: `python3-gobject-Gdk typelib-1_0-GtkLayerShell-0_1 …`

  Se pregunta antes de ejecutar con sudo.
- [x] **U6.2 Autoarranque**: `install.sh` escribe `~/.config/autostart/isla-dinamica.desktop` con la ruta
  real del usuario. En sway, Hyprland, river y labwc muestra la línea `exec` que hay que añadir (no
  edita la configuración del compositor sin permiso).
- [x] **U6.3 Lanzador** `~/.local/bin/isla-dinamica` con `--doctor`.

### Fase U7 — Extensión provisional de GNOME Shell
- [x] **U7.1** `extras/gnome-shell/isla-dinamica@bitbro404.github.io/` con `metadata.json` (shell-version 45–48)
  y `extension.js`.
  - Ventana de la isla: siempre encima, en todos los espacios, fuera de Alt+Tab y de la vista general.
  - D-Bus `io.github.bitbro404.IslaDinamica.Shell` con `GetIdletime`, `Screenshot(area)`, `Screencast(...)`,
    `SetPowerSave(bool)` y `ToggleNotificationCenter`.
- [x] **U7.2** `install.sh --gnome-extension` la copia y la activa con `gnome-extensions enable` (pregunta
  antes).
- [x] **U7.3** La isla detecta la extensión (nombre en el bus) y la usa en las cadenas de U2–U4.
  - Prueba unitaria del lado Python (bus falso).
  - El JavaScript queda **sin probar aquí** (no hay GNOME); se marca como provisional en `docs/ESCRITORIOS.md`.

### Fase U8 — Documentación y cierre
- [x] **U8.1** Prueba de la regla «sin nombres de escritorio fuera de `platform/`»
  (`tests/unit/test_architecture.py`, analiza el AST; `make check` la ejecuta). La extensión y la elección
  de backend se centralizaron en `platform/shell.py` y `platform/placement.py`.
- [x] **U8.2** README: requisitos por distro, tabla de escritorios con lo que funciona en cada uno, `--doctor` y
  `--deps`. `docs/DOCUMENTACION.md`: niveles de dependencias por escritorio.
- [x] **U8.3** `docs/ESCRITORIOS.md`: lista de comprobación por escritorio (qué probar y qué esperar).
- [x] **U8.4** Verificación final (2026-11-21):
  - `make check` → 218 pruebas unitarias OK (incluye la regla de arquitectura) + `compileall` OK;
  - arnés en Budgie → `pill`, `home` y `notifs` capturados en `/tmp/opencode/isla-final`, sin tracebacks;
  - XWayland (`GDK_BACKEND=x11 ISLA_RELAUNCHED=1`) → 7 s activo, solo el SIGINT del temporizador;
  - Docker X11 (`tests/x11_smoke.sh`) → 0 tracebacks, ventana DOCK arriba, sin barra, arrastrable y acoplable;
  - `--doctor` en modo layer-shell (Budgie/Wayland) y en modo X11 (LXDE/X11) → 15 funciones;
  - `./install.sh` → lanzador, autoarranque con ruta real y `isla-dinamica --doctor` funcionando.

## Riesgos y casos límite
- **GNOME sin extensión (XWayland):** Mutter puede poner la isla detrás de ventanas a pantalla completa y no
  da inactividad, captura ni grabación a apps normales.
  - Mitigación: extensión (U7); y si no está, el portal de capturas e inactividad por sondeo
    (`org.gnome.Mutter.IdleMonitor`, que sí es accesible).
- **Openbox sin compositor:** sin transparencia ni sombras → máscara de forma; la sombra se pierde.
- **Varios monitores en X11 con escalas distintas:** la posición se calcula por monitor con `Gdk.Monitor`; puede
  quedar desplazada en configuraciones raras. Se comprueba en Xvfb con dos pantallas virtuales.
- **Foco de teclado en X11** con ventanas tipo DOCK: algunos gestores no les dan foco. Plan B: tipo UTILITY con
  `skip_taskbar`.
- **Nombres de paquetes** distintos entre versiones de distro: `--deps` muestra el comando antes de ejecutarlo
  y no falla si un paquete no existe (sugiere `--doctor`).
- **La extensión de GNOME no se puede probar aquí:** queda marcada como provisional hasta que el usuario la
  pruebe en una VM con GNOME.
- **Tamaño:** muchos archivos nuevos pero aislados en `platform/`. Cada fase es un commit independiente.

## Pendientes/preguntas abiertas
- Ninguna bloqueante. P1–P5 se aprueban con el plan.

## Comandos de verificación
```bash
make check    # compileall + 218 pruebas unitarias (incluye test_architecture.py)
```
```bash
python3 -W error::ResourceWarning -m unittest discover -s tests/unit
```
```bash
GDK_BACKEND=x11 python3 isla.py
```
```bash
python3 isla.py --doctor
```
```bash
tests/x11_smoke.sh
```
```bash
./install.sh --deps
```

## Estado y siguiente paso
- Fases U0–U8 ejecutadas con TDD y verificadas: **218 pruebas unitarias en verde**, `compileall` OK,
  `--doctor` en modo layer-shell y X11, XWayland sin tracebacks, humo X11 en Docker, arnés en Budgie e
  `install.sh` con lanzador y autoarranque. Cambios **sin commitear** (no se hace commit sin autorización).
- Siguiente paso del usuario: validar en VM los escritorios que no hay aquí (D4) siguiendo
  `docs/ESCRITORIOS.md`, sobre todo la extensión provisional de GNOME (U7), KDE, Cinnamon, MATE, XFCE,
  LXQt y sway/Hyprland. Hasta entonces el trabajo queda a la espera de confirmación.

## Registro de decisiones
- 2026-11-21: plan de seguridad y refactor archivado; este plan es el de soporte multi-escritorio.
- 2026-11-21: D1–D4 confirmadas por el usuario (soporte para todos con piezas provisionales, ocultar + doctor,
  `--deps` con confirmación, pruebas unitarias + X11 aquí).
- 2026-11-21: U2 integrado: `services/notifications.py` delega en las cadenas de `platform/`; los métodos de
  `CENTER` son acciones (se ejecutan con el bus), no fábricas; `supported`/`has_center` ocultan el tile y el
  botón sin método. Los backends que no avisan se consultan cada 3 s.
- 2026-11-21: U3 integrado: `DEFAULT_ACTIONS` de `Presence` y `Power.lock` usan `platform/lock.py` y
  `platform/screen.py`; se mantiene la regla S2 (sin bloqueo verificado no se apaga la pantalla).
  `IdleWatch` se movió a `platform/idle.py` y se reexporta desde `services/presence.py` (swayidle en wlroots,
  sondeo con libXss/Mutter/KDE en el resto).
- 2026-11-21: U4 integrado con `History`/S4 intactos: portapapeles (`wl-paste` → Gtk.Clipboard → portal),
  capturas (grim/spectacle/extensión/maim/scrot/portal) y grabación (wf-recorder/ffmpeg/extensión/portal).
- 2026-11-21: U5 integrado: `appearance`, `session` (con `systemd-inhibit` y cierre de sesión por escritorio),
  `apps` y `audio` (wpctl→pactl, pw-play→paplay→canberra); `Modes` delega en `Appearance` y `Session`.
- 2026-11-21: U6/U7 integrados: `tools/` calcula paquetes, autoarranque y lanzador; `install.sh` pregunta
  antes de instalar dependencias o la extensión; `platform/shell.py` centraliza el puente D-Bus y
  `platform/placement.py` la elección de backend.
- 2026-11-21: U8 cerrado: regla de arquitectura por AST, documentación universal y verificación final en
  verde. La extensión de GNOME sigue marcada como provisional hasta la validación en VM.
