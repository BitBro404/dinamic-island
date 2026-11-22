# Handoff

## Solicitud y objetivo
Hacer la isla dinámica universal: KDE, GNOME, Cinnamon, MATE, XFCE, LXDE, LXQt, Budgie, sway, Hyprland,
Wayfire, river, labwc, niri y cualquier otro escritorio Linux, en Wayland o X11 y en las familias
Debian/Ubuntu, Fedora, Arch y openSUSE. El usuario pidió continuar el plan el 2026-11-21 y aprobó
«ejecuta todo» (U4–U8).

## Repositorios dentro del alcance
- Único repo: `/home/luis/dinamic island` (rama `main`). No hay repos anidados.
- Todos los cambios siguen **sin commitear**; no se hace commit, push, merge ni reset sin autorización.
- Hay cambios preexistentes del usuario que se han conservado (`core.py`, `main.py`, `ui/*`, `window.py`,
  `tests/harness.py`, `isla_dinamica/__init__.py`, entre otros).

## Estado actual
- **U0–U8 terminados** siguiendo TDD (RED → GREEN → REFACTOR), con 218 pruebas unitarias en verde.
- Plan maestro actualizado: `plan.md` (raíz). Plan anterior archivado en
  `.ai/plans/2026-11-21-seguridad-refactor.md`.
- Falta únicamente la **validación del usuario en VM** de los escritorios que no existen en esta máquina.
  Los resúmenes/memoria finales NO se han escrito: dependen de esa confirmación.

## Decisiones confirmadas
- D1–D4 y P1–P5 del plan (soporte universal con piezas provisionales; ocultar/marcar «No disponible» +
  `--doctor`; `install.sh --deps` con confirmación; pruebas unitarias + X11 aquí y el resto en VM;
  XWayland sin layer-shell; ventana X11 DOCK con máscara; extensión GNOME provisional; cadenas con
  `available()` vía `Tools` inyectables; mantener S1–S4).
- U2/U3: `services/notifications.py`, `Presence` y `Power` delegan en `platform/`; se conservan S2 (sin
  bloqueo verificado no se apaga la pantalla) y S4 (filtro de secretos del portapapeles).
- U4: portapapeles, capturas y grabación con cadenas por método; el portal es el último recurso.
- U5: `appearance`, `session`, `apps` y `audio`; `systemd-inhibit` guarda el proceso y se termina al
  desactivar; `Modes` delega en `Appearance`/`Session`.
- U6/U7: `tools/` genera paquetes, autoarranque y lanzador; `install.sh` pregunta antes de usar `sudo` o
  instalar la extensión; `platform/shell.py` centraliza el bus de la extensión.
- U8: los nombres de escritorio solo viven en `platform/` (regla comprobada por AST en
  `tests/unit/test_architecture.py`).

## Archivos principales
- Nuevos: `isla_dinamica/platform/{desktop,chain,doctor,features,notify,dnd,lock,screen,idle,clipboard,capture,record,appearance,session,apps,audio,shell,placement}.py`,
  `isla_dinamica/ui/placement.py`, `tools/`, `extras/gnome-shell/`, `Makefile`,
  `docs/ESCRITORIOS.md`, `tests/unit/test_*.py` (detección, cadenas, arquitectura, herramientas),
  `tests/{x11_smoke.sh,docker/*}`.
- Modificados: `install.sh`, `plan.md`, este handoff, `README.md`, `docs/DOCUMENTACION.md`, `main.py`,
  `core.py`, `services/*`, `pages/*`, `ui/*`, `util/proc.py`, `window.py`, `tests/harness.py`.
- La extensión de GNOME (`isla-dinamica@bitbro404.github.io`) es **provisional**: JS validado solo con
  `node --check`; no se pudo ejecutar en GNOME.

## Pruebas ejecutadas y resultados (2026-11-21)
- `make check` → `compileall` OK + **218 pruebas unitarias OK** (incluye `test_architecture.py`).
- `python3 -m isla_dinamica --doctor` (Budgie/Wayland, backend layer-shell) → 15 funciones: Budgie
  Dispatcher/DND, centro no disponible, Budgie Screenlock, wlopm, swayidle, wl-paste, grim+slurp,
  wf-recorder, GNOME color-scheme/night light/SessionManager, wpctl y pw-play.
- `--doctor` forzado a X11/LXDE → backend X11, Gtk.Clipboard, XScreenSaver y ffmpeg (X11).
- XWayland (`GDK_BACKEND=x11 ISLA_RELAUNCHED=1 python3 isla.py`, 7 s) → solo `Got SIGINT, exiting.`,
  sin tracebacks.
- `bash tests/x11_smoke.sh` (Docker: Xvfb + Openbox) → 0 tracebacks; ventana DOCK, arriba, sin barra de
  tareas, arrastrable y acoplable; capturas en `tests/capturas/x11/`.
- `python3 tests/harness.py pill home notifs --out /tmp/opencode/isla-final` → tres PNG, sin errores;
  la isla instalada se reinició al terminar.
- `./install.sh` → lanzador en `~/.local/bin/isla-dinamica`, autoarranque con la ruta real del usuario y
  `isla-dinamica --doctor` funcionando desde la copia instalada.
- `python3 -m json.tool .../metadata.json` y `node --check .../extension.js` → OK.

## Fallos conocidos / bloqueos
- No hay GNOME, KDE, Cinnamon, XFCE, LXQt ni sway en esta máquina: D4 exige validación del usuario en VM.
- En Budgie/Wayland el nombre `org.budgie_desktop.Raven` no está en el bus: `--doctor` marca «Centro de
  avisos: no disponible» y el botón se oculta (comportamiento previsto por D2).
- El JavaScript de la extensión no se pudo probar aquí; está marcado como provisional en
  `docs/ESCRITORIOS.md`.

## Próximo paso exacto (usuario)
Seguir `docs/ESCRITORIOS.md` en una VM por escritorio: ejecutar `isla-dinamica --doctor`, comprobar la
píldora/panel/arrastre, avisos, DND, portapapeles, captura, grabación, oscuro, sesión y audio, y comparar
con la tabla de resultados esperados. Prioridad: GNOME con extensión, KDE, XFCE y un compositor wlroots
distinto de labwc. Después de esa validación se pueden escribir los resúmenes/memoria y decidir commits.

## Qué no se debe repetir
- No commits, pushes ni resets sin permiso explícito.
- No escribir adaptadores de escritorio fuera de `platform/` (lo detecta `test_architecture.py`).
- No ejecutar `install.sh --deps` ni `--gnome-extension` sin la confirmación interactiva del usuario.
- Antes de usar el arnés o `install.sh`, revisar `git status`: hay cambios preexistentes del usuario.
- El inventario de dependencias y el contexto medido de Budgie/labwc están en `plan.md` → «Contexto actual».
