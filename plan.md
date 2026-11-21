# Plan: refactor SOLID + comentarios + plan de seguridad

> Estado: **APROBADO** (2026-11-21, orden: seguridad → refactor). Fase S hecha; refactor pendiente.
> El plan anterior (sensor de presencia, ya terminado) se archivó en `.ai/plans/2026-11-21-sensor-presencia.md`.

## Objetivo y resultado esperado
1. **Refactor:** dejar el código más fácil de leer y mantener **sin cambiar lo que hace la isla**. Para eso:
   - separar responsabilidades (SOLID);
   - quitar redundancia y el código muerto;
   - cambiar las importaciones `*` por importaciones explícitas;
   - comentar los módulos y las piezas clave en español.
2. **Seguridad:** identificar los riesgos y corregirlos uno a uno con TDD (sección «Riesgos de seguridad»).

Resultado: la misma isla (comprobada con las 54 pruebas actuales y capturas antes/después), con una
estructura en capas fácil de recorrer y los riesgos de seguridad cerrados o documentados.

## Alcance
- Repositorios incluidos: `/home/luis/dinamic island` (un único repo; rama `main`, limpia y al día con `origin`).
- Repositorios excluidos: ninguno más.
- Fuera de alcance: funciones nuevas, cambios visuales, migrar a GTK4 y cambiar de librería de pruebas.

## Contexto actual (medido el 2026-11-21)
- Unas 7 500 líneas en `isla_dinamica/` y 54 pruebas unitarias en verde.
- Comando de pruebas: `python3 -W error::ResourceWarning -m unittest discover -s tests/unit`.
- Arnés de capturas: `tests/harness.py` con datos falsos en `tests/fixtures/`.
- Puntos calientes:

| Archivo | Líneas | Problema |
|---|---|---|
| `window.py` | 1165 | «Clase Dios»: `IslandWindow(*PAGE_CLASSES, Gtk.Window)` hereda de **todas** las páginas (viola SRP e ISP). Mezcla dibujo Cairo, animación, hover, arrastre y acople, burbujas y la cadena de prioridad de la píldora: `refresh()` es un `if/elif` de 15 ramas (viola OCP: cada función nueva obliga a editarla) |
| `core.py` | 534 | Crea todos los servicios **y** traduce más de 20 eventos (`_on_battery`, `_on_deploy`, `_on_github`…) a avisos de la UI (SRP). Captura de pantalla y grabación también viven aquí |
| `common.py` | 426 | Mezcla CSS (70 líneas), constantes de layout, fabricación de widgets, formato de fechas, procesos, configuración y HTTP |
| `widgets.py` | 540 | Los títulos de sección engañan («servicios», «la isla» encima de widgets que no lo son) |
| `isla_v1.py` | 875 | **Código muerto**: versión previa a la modularización; nada lo importa (sigue en el historial de git) |

- Redundancias detectadas:
  - el bucle «reproducir el primer sonido que exista» está copiado en `core.py:411` y `core.py:484`, además de `common.play_sound`;
  - el patrón «sondear cada N s con `_schedule`/`_tick`» se repite en varios servicios (16 temporizadores);
  - el patrón «refrescar al abrir la página si los datos tienen más de N s» se repite en varias páginas;
  - hay 79 `from ..x import *` que ocultan de dónde sale cada nombre.
- Bloqueos del hilo de la UI: `media.py:83` llama a `subprocess.run(wpctl get-volume)` en el hilo principal
  (los de `audio.py` y `privacy.py` sí corren en hilos).

## Decisiones confirmadas
- Comentarios y docstrings en **español**, como el resto del proyecto.
- Pruebas con `unittest` de la biblioteca estándar (sin pytest).
- No hay commit ni push sin autorización explícita. El hook de evanflow bloquea `git push`, así que el push lo hace el usuario.

## Decisiones propuestas (se aprueban con el plan)
- D1. Borrar `isla_v1.py`; queda en el historial de git (`3872417`).
- D2. Refactor **por fases pequeñas**. Cada fase deja todo en verde y se puede validar y hacer commit por separado.
- D3. Las correcciones de seguridad van **después** del refactor (fase S), cada una con su prueba RED. Si
  prefieres, S1 y S2 pueden ir primero porque son las de mayor impacto.
- D4. No se cambia el aspecto visual. Las capturas antes/después del arnés deben coincidir.

## Suposiciones y restricciones
- Sin pruebas de UI automáticas: lo visual se verifica con el arnés y una revisión manual de las capturas.
- Mover código entre módulos sin cambiar la lógica se cubre con: las pruebas existentes, nuevas pruebas de
  caracterización donde la lógica sea pura (prioridad de la píldora, burbujas) y `compileall`.
- El arnés reinicia la isla instalada. No se ejecuta `./install.sh` hasta el final, con aprobación.

## Arquitectura objetivo (SOLID, en una imagen)

```
isla_dinamica/
  main.py                 arranque: crea App y Core
  config.py               Config + DEFAULTS + validadores           (antes en common.py)
  core.py                 Core: crea servicios y guarda el estado; ya no formatea avisos
  events.py               EventRouter: traduce los eventos de los servicios en avisos de la píldora (SRP)
  util/
    fmt.py                hm, ago, ago_long, fmt_secs, fecha, today_count, iso_ts  (funciones puras)
    proc.py               run, tied, open_uri, launch_desktop, play_sound
    net.py                fetch_json
  ui/
    style.py              CSS, ACCENTS y constantes de tamaño
    gtk.py                label, icon, button, clear, set_accent, set_class
    widgets/              Art, Spectrum, Equalizer, WeatherIcon, PrivacyDots, Spark, TempBar, Tile
    pill.py               PillChain: lista ordenada de «proveedores de píldora» (OCP)
    bubbles.py            cálculo de las burbujas (lógica pura y testeable)
    dock.py               arrastre y acople a los bordes
    window.py             IslandWindow: compone lo anterior, sin heredar de las páginas
  pages/                  una clase por página que recibe (core, window): composición en vez de herencia
  services/               sin cambios de API; base común Poller para los que sondean (DRY)
```

Cómo se ve cada principio SOLID:
- **S** (una responsabilidad por clase): `EventRouter` formatea los avisos, `PillChain` decide qué muestra la
  píldora, `Dock` mueve la ventana y `Config` guarda las preferencias.
- **O** (abierto a extensión): cada función nueva añade un proveedor a `PILL_PROVIDERS` o una página a
  `PAGES`, sin editar `refresh()`.
- **L** (sustitución): todos los proveedores de píldora cumplen el mismo contrato `match(ctx)` → `render(win, ctx)`,
  y todas las páginas el contrato `build()` / `fill()` / `opened()`.
- **I** (interfaces pequeñas): una página solo ve el `core` y unos pocos métodos de la ventana (`go`,
  `collapse_then`, `row`, `fold`…) a través de un objeto `PageHost`, no toda la ventana.
- **D** (depender de abstracciones): los servicios reciben callbacks y relojes inyectados, como ya hace
  `Presence`. `Poller` recibe la función de consulta.

## Archivos o módulos a inspeccionar/modificar
`isla_dinamica/{common,core,window,widgets,main}.py`, `isla_dinamica/pages/*.py`, `isla_dinamica/services/*.py`,
`tests/harness.py`, `tests/unit/*`, `install.sh` (solo si cambia la ruta del paquete), `README.md` y
`docs/DOCUMENTACION.md` (sección Estructura).

## Criterios de aceptación
1. Las 54 pruebas actuales y las nuevas en verde: `python3 -W error::ResourceWarning -m unittest discover -s tests/unit`.
2. `python3 -m compileall -q isla_dinamica` sin errores.
3. Capturas del arnés antes/después iguales en: `pill`, `home`, `github`, `ms`, `presence`, `more`, `weather`, `system`.
4. Ningún `from … import *` dentro de `isla_dinamica/`.
5. Ningún archivo de `isla_dinamica/` pasa de unas 400 líneas.
6. Cada módulo tiene un docstring que explica su responsabilidad, y cada clase pública el suyo.
7. `isla_v1.py` eliminado; sin bloques duplicados de sonido ni de sondeo.
8. Cada riesgo de seguridad de la tabla queda corregido con su prueba, o documentado como aceptado.

## Estrategia de pruebas
- **Pruebas de caracterización primero:** antes de mover lógica, fijar con pruebas su comportamiento actual
  (prioridad de la píldora, burbujas, formatos de hora, parseo de `nmcli`).
- **Capturas «antes»:** se guardan en `tests/capturas/antes/` (ignorado por git) y se comparan al final de
  cada fase.
- **Seguridad:** cada corrección tiene una prueba RED que demuestra el fallo actual (por ejemplo, «la
  contraseña aparece en argv» o «se abre una URL file://»).

## Tareas

### Fase 0 — Red de seguridad
- [x] **R0.1 Capturas de referencia**
  - Archivos: ninguno de código.
  - Paso: `python3 tests/harness.py pill home github ms presence more weather system --setup tests/fixtures/sections_demo.py --out tests/capturas/antes`.
  - Verificación: 8 PNG guardados.
- [x] **R0.2 Caracterizar la prioridad de la píldora**
  - Archivos: `tests/unit/test_pill_priority.py`.
  - Prueba: contexto falso (llamada + música + pomodoro…) → la píldora elige «call»; sin llamada → «media»; etc. Cubre las 15 ramas.
  - Requisito: extraer antes la decisión pura de `refresh()` a una función `pick_pill(ctx)` **sin cambiar el
    orden**. Es el primer cambio GREEN.
- [x] **R0.3 Caracterizar las burbujas**: `_activities()` → función pura `activities(ctx)` con su prueba.

### Fase 1 — Limpieza sin riesgo
- [x] **R1.1** Borrar `isla_v1.py` (D1). Verificación: `grep -r isla_v1` vacío y pruebas en verde.
- [x] **R1.2** Un solo `play_sound(*rutas)` en `util/proc.py`, usado desde `core.py`. Prueba: ignora las rutas que no existen y llama una vez con la primera que existe (Popen inyectado).
- [x] **R1.3** Corregir los títulos de sección de `widgets.py` y añadir docstrings donde falten.

### Fase 2 — Partir `common.py` (S)
- [x] **R2.1** Crear `config.py`, `util/fmt.py`, `util/proc.py`, `util/net.py`, `ui/style.py` y `ui/gtk.py`, moviendo el código tal cual.
  - Durante la transición, `common.py` reexporta estos nombres para no romper nada. Se borra en R2.3.
  - Pruebas: las actuales (`test_config_presence`, `test_sections`…) importan desde los módulos nuevos.
- [x] **R2.2** Importaciones explícitas en `services/` (sustituir `from ..common import *`).
- [x] **R2.3** Importaciones explícitas en `pages/`, `core.py`, `window.py` y `main.py`; borrar `common.py`.
  - Verificación: `grep -rn "import \*" isla_dinamica` vacío.

### Fase 3 — `Poller` común para los servicios que sondean (DRY + D)
- [x] **R3.1** `services/poller.py`: `Poller(interval_fn, fetch, enabled)` con `schedule(secs)`, `refresh()` y `stop()`, usando un reloj y un `timeout_add` inyectables.
  - Prueba RED: con un `timeout_add` falso, el siguiente intervalo es corto si hay algo en curso y largo si no, y no hay dos consultas a la vez.
- [x] **R3.2** Pasar `deploys.py`, `github.py`, `weather.py`, `fx.py` y `gitwatch.py` a `Poller`. Sus pruebas y las capturas deben seguir iguales.
- [ ] ~~**R3.3**~~ (descartado: solo dos usos, ver «Resultado del refactor») Un helper `refresh_if_stale(service, max_age)` para las páginas (`_open_github`, `_open_ms`…).

### Fase 4 — `core.py`: separar el formateo de avisos (S)
- [x] **R4.1** `events.py` con `EventRouter(show_event, open_…)`: pasar ahí los `_on_*` de `core.py` (batería, despliegues, GitHub, red, sysmon, servidores, descargas, USB, Bluetooth, pomodoro, recordatorios).
  - Prueba RED: `EventRouter` con un `show_event` falso, de modo que `deploy("start", d)` genera la píldora naranja «Desplegando x · env» y `deploy` con FAILURE genera una tarjeta roja con acción. Una prueba por cada tipo de evento.
- [x] **R4.2** Pasar la captura de pantalla y la grabación a `services/capture.py`.
- [x] **R4.3** Quitar `subprocess.run(wpctl)` del hilo de la UI en `media.py:83` y usar `run()` asíncrono.

### Fase 5 — `window.py`: composición en vez de herencia (S, O, I)
- [x] **R5.1** `ui/pill.py`: `PILL_PROVIDERS = [AlertProvider, CardHoldProvider, …]`, cada uno con `match(ctx)` y `render(win, ctx)`. `refresh()` recorre la lista.
  - Prueba: la de R0.2 sigue en verde, ahora contra `PILL_PROVIDERS`.
- [x] **R5.2** `ui/bubbles.py` (cálculo y dibujo de las burbujas) y `ui/dock.py` (arrastre, acople, `_nearest_edge`, `_target_xy`).
  - Prueba: `nearest_edge` y `target_xy` son puros, así que se prueban con varias geometrías de monitor.
- [x] **R5.3** `PageHost`: interfaz pequeña que la ventana expone a las páginas (`core`, `go`, `collapse_then`, `row`, `fold`, `empty`, `page`, `scroller`, `switch`, `copy`).
  - Las páginas pasan de mixins a clases `Page(host)`, y `IslandWindow` deja de heredar de `PAGE_CLASSES`.
  - Se migra página a página (primero GitHub y Teams, que ya usan `fold`). Cada página migrada debe dar la misma captura.
- [x] **R5.4** Mover los widgets a `ui/widgets/` (un archivo por widget o por familia).

### Fase 6 — Documentación del código
- [x] **R6.1** Docstring de módulo y de clase en todo `isla_dinamica/`, y comentarios en las partes no obvias (prioridades, tiempos, hilos, `GLib.idle_add`).
- [x] **R6.2** Actualizar la «Estructura» de `README.md`, la de `docs/DOCUMENTACION.md` y `.ai/PROJECT_MEMORY.md` con la arquitectura nueva y un diagrama de dependencias entre capas.

### Fase S — Seguridad (cada fila es una tarea TDD)

| # | Riesgo | Dónde | Impacto | Corrección propuesta | Prueba RED |
|---|---|---|---|---|---|
| **S1** | La **contraseña del Wi‑Fi** se pasa en la línea de comandos de `nmcli` y cualquier usuario o proceso local puede leerla en `/proc/<pid>/cmdline` o con `ps` mientras dura la conexión | `services/network.py:149` | **Alto** | Pasarla por un archivo temporal `passwd-file` con permisos 0600 en `$XDG_RUNTIME_DIR` (`nmcli --ask … passwd-file`), borrarlo siempre en `finally` y no dejarla nunca en argv | Con un `run` falso, `connect(net, password="x")` → `"x"` no aparece en argv y el archivo se crea con modo 0600 y se borra después |
| **S2** | La presencia **apaga la pantalla aunque el bloqueo haya fallado**: si el D-Bus de Budgie y `loginctl` fallan, la sesión queda abierta con la pantalla negra y el estado dice «Bloqueado» | `services/presence.py:226-239`, `_tick` | **Alto** (la función promete seguridad) | `lock()` devuelve si bloqueó (comprobando `LockedHint` de logind o el código de salida de `loginctl`). Si no bloqueó, no apaga la pantalla y muestra el estado de error «No se pudo bloquear» | Acción `lock` falsa que devuelve False → no se llama `screen_off`, el estado es `error` y se avisa |
| **S3** | **URLs sin validar** de terceros: `logUrl`/`environmentUrl` de los despliegues (los escribe la plataforma) y las URLs de GitHub se abren con `open_uri`, que acepta `file://`, `ssh://` o esquemas de apps instaladas | `services/deploys.py:93`, `pages/github.py`, `core.open_github` | Medio | `safe_open_url(url)`: solo `https://` (y `http://` para `localhost`). Si no cumple, se ignora y se registra con `dbg` | `file:///etc/passwd`, `javascript:` y `x-scheme://` no se abren; `https://github.com/...` sí |
| **S4** | **Historial del portapapeles** con secretos: guarda los últimos 40 textos copiados (tokens, contraseñas copiadas desde la terminal) y los muestra en claro. Solo filtra el aviso de KDE | `services/clipboard.py` | Medio | Ocultar (`••••`) y no guardar en el historial lo que parezca un secreto (claves `ghp_`, `sk-`, `AKIA`, JWT, cadenas de alta entropía de más de 20 caracteres sin espacios); caducar las entradas a los 30 min y vaciar al bloquear la sesión | `looks_secret("ghp_abc…")` es True y `"hola mundo"` es False; un secreto copiado no entra en `items` |
| **S5** | **La isla sobre la pantalla de bloqueo**: si el bloqueo de Budgie no usa `ext-session-lock`, la isla (capa *overlay*) podría verse e incluso usarse sobre él: avisos, portapapeles, Wi‑Fi, apagar… | `window.py`, `core.py` | Alto **si se confirma** | 1) Comprobación manual (bloquear y mirar). 2) Si se ve: escuchar `LockedHint` / `Lock` de logind y ocultar la isla mientras dure el bloqueo | `Core` con una señal de bloqueo falsa → `set_hidden(True)`, y al desbloquear `set_hidden(False)` |
| **S6** | **Abrir descargas directamente**: el clic en una descarga la abre con la app predeterminada; un archivo malicioso (`.desktop`, script o documento con macros) queda a un clic | `pages/downloads.py:63` | Bajo-medio | Para tipos ejecutables o desconocidos (`application/x-executable`, `x-shellscript`, `x-desktop`, `x-ms-dos-executable`…) mostrarlo en la carpeta en vez de abrirlo | `should_open_directly("x.sh")` es False y `"foto.png"` es True |
| **S7** | Una **notificación puede lanzar cualquier app instalada**: el hint `desktop-entry` lo pone quien envía el aviso, y al hacer clic la isla lanza esa entrada | `core.open_notif` → `launch_desktop` | Bajo | Lanzar solo si el `desktop-entry` coincide con la app que envió el aviso (`app_name`); si no, abrir el centro de notificaciones | Aviso de la app «X» con `desktop-entry` «terminal» → no se lanza |
| **S8** | **Registro de datos privados** con `ISLA_DEBUG`: imprime el título de cada notificación (mensajes de Teams o del correo) | `core.py:218` | Bajo | Registrar solo la app y el tipo, no el contenido | Con `dbg` capturado, el resumen no aparece en la salida |
| **S9** | **Permisos de `config.json`**: se crea con la umask (normalmente 0644) y lo puede leer cualquier usuario local (carpetas, ciudad, horario) | `Config.save` | Bajo | Crear el archivo temporal con 0600 antes de escribir | Tras `save()`, el modo es 0600 |

Riesgos revisados que **no** necesitan cambios (para no repetir el análisis):
- No hay `shell=True`, `eval`, `exec`, `pickle` ni `yaml.load`.
- Los `sh -c` del portapapeles y de la captura pasan la ruta como `$1`, nunca interpolada en el texto del script.
- Ninguna etiqueta usa *markup* de Pango con texto externo: `strip_markup` + `Gtk.Label` en texto plano.
- `fetch_json` usa HTTPS con un tiempo de espera de 10 s, y el nombre de la ciudad se codifica con `urllib.parse.quote`.
- `servers.stop` solo puede matar procesos propios: sin root, `ss` no da el PID de procesos ajenos y `kill` fallaría.
- La consulta de `gh` interpola `login`, que viene del propio `gh api user`, no de terceros.
- El modelo YuNet en `~/.local/share` solo lo puede cambiar el propio usuario.

## Riesgos y casos límite del refactor
- **Romper el aspecto sin que fallen las pruebas:** se mitiga con capturas antes/después en cada fase.
- **Atributos que las páginas leen de la ventana** (`self.hover`, `self.page`…): R5.3 los hace explícitos en
  `PageHost`. Si sale alguno no previsto, se añade a la interfaz y se anota aquí.
- **Señales de GTK conectadas a métodos de las páginas mixin:** al pasar a composición, cuidar las lambdas que
  capturan `self`.
- **Tamaño del cambio:** cada fase se puede hacer en un commit; si algo se tuerce se revierte solo esa fase.

## Pendientes/preguntas abiertas
- P1. ¿Aprobar D1 a D4 tal como están?
- P2. ✅ Decidido: toda la fase S primero y después el refactor.
- P3. S5 necesita una prueba manual tuya: bloquear la sesión (Super+L) y decir si la isla se ve encima.

## Comandos de verificación
```bash
python3 -W error::ResourceWarning -m unittest discover -s tests/unit
```
```bash
python3 -m compileall -q isla_dinamica
```
```bash
grep -rn "import \*" isla_dinamica
```
```bash
python3 tests/harness.py pill home github ms presence more weather system --setup tests/fixtures/sections_demo.py --out tests/capturas/despues
```
```bash
wc -l isla_dinamica/**/*.py | sort -rn | head
```

## Estado y siguiente paso
- Fase S terminada y validada por el usuario.
- Refactor R0–R6 terminado: 118 pruebas en verde, `compileall` OK, sin `import *`, isla instalada con `./install.sh`.
- Siguiente paso: validación del usuario → resumen en `.ai/summaries/` → commit (lo hace el usuario: firma GPG).

### Resultado del refactor (y en qué se apartó del plan)
- R0: capturas en `tests/capturas/antes/`; `ui/pill.py` (`PillState`, `PILL_ORDER`, `pick_pill`) y
  `ui/bubbles.py` (`activities`, `bubble_rects`) puros con `test_pill_priority.py` y `test_bubbles.py`.
- R1: `isla_v1.py` borrado; `util/proc.play_sound` único (prueba `test_play_sound.py`, de caracterización: la
  función ya existía, no se vio en rojo).
- R2: `common.py` y `widgets.py` borrados en un solo paso (sin la fase de reexportación): `config.py`,
  `util/{fmt,proc,safety,net,links}.py`, `ui/{style,gtk}.py`, `ui/widgets/{art,audio,weather_icon,charts,tile}.py`.
  Los imports explícitos se generaron con `symtable` (nombres libres → módulo que los define).
  `gi.require_version` vive en `isla_dinamica/__init__.py`. `services/__init__.py` ya no reexporta nada.
- R3: `Poller` con `every/soon/retry/stop` (en vez de `schedule/refresh`), con `timeout_add` inyectado
  (`test_poller.py`). Usado por deploys, github, weather, fx y gitwatch. **R3.3 (`refresh_if_stale`) no se hizo**:
  solo había dos usos y no compensaba la abstracción.
- R4: `events.py` (`EventRouter`, `test_events.py`); captura/grabación en `isla_dinamica/capture.py` (no en
  `services/`, porque usa GTK y el núcleo); volumen asíncrono con `parse_volume` (`test_volume_parse.py`).
- R5: en lugar de clases «Provider», la píldora usa `PILL_ORDER` + un método `_pill_<clave>` por estado
  (abierto/cerrado: añadir un estado = una clave y un método). La ventana se compone de mixins
  (`ui/pill_view.py`, `ui/bubbles.py`, `ui/paint.py`, `ui/dock.py`) y las páginas son objetos `Page(host)`
  (`pages/base.py`) con ganchos `live/on_collapse/typing/waiting`. Geometría del acople pura (`test_dock.py`).
- R6: docstring en todos los módulos y clases; «Estructura» del README reescrita con el sentido de las
  dependencias; `docs/DOCUMENTACION.md` no tenía sección de estructura: se añadió «Para desarrolladores» que
  remite al README; `.ai/PROJECT_MEMORY.md` actualizado.
- Capturas después (todas las páginas, con y sin fixtures): sin errores; las diferencias con «antes» son de
  datos en vivo (hora, batería, audio real, secciones plegadas en tu config).
- Archivo más largo: `services/presence.py` (426 líneas, no se tocó su estructura); el resto ≤ 365.

### Resultado de la fase S
- [x] S1 `services/network.py`: `wifi_connect_command` → `nmcli --ask` con la contraseña por stdin. Prueba: `test_sec_wifi.py`.
- [x] S2 `services/presence.py`: `_budgie_lock` devuelve si bloqueó; si falla, NO apaga la pantalla y el estado es `lock_failed`. Prueba: `test_presence_service.test_failed_lock_never_turns_screen_off`.
- [x] S3 `common.is_safe_web_url` / `open_web` + `deploys.deploy_url`; usados en despliegues, PR y servidores. Prueba: `test_sec_urls.py`.
- [x] S4 `services/clipboard.py`: `looks_secret` + `History` (no guarda secretos, caduca a los 30 min, límite 40). Prueba: `test_sec_clipboard.py`.
- [x] S5 `services/lockguard.py`: `LockGuard` + `watch_session_lock` (logind Lock/Unlock/LockedHint de la sesión «Display») → oculta la isla y vacía el portapapeles. Prueba: `test_sec_lockguard.py` (se escribió junto con la implementación; no se vio en rojo).
- [x] S6 `common.safe_to_open`: las descargas ejecutables o desconocidas se muestran en la carpeta (página y tarjeta). Prueba: `test_sec_low.py`.
- [x] S7 `common.desktop_matches_app`: un aviso solo lanza la app que lo envió.
- [x] S8 `common.notif_debug_line`: el registro de depuración no incluye el contenido de los avisos.
- [x] S9 `Config.save`: `config.json` con permisos 0600.
- Riesgo residual S1: no se pudo probar `nmcli --ask` con una red real desde aquí.
- Riesgo residual S5: si el bloqueador de Budgie no avisa a logind (Lock/LockedHint), la isla no se oculta con su bloqueo; queda la comprobación manual.

## Registro de decisiones
- 2026-11-21: se archiva el plan de presencia en `.ai/plans/`; este `plan.md` es el del refactor y la seguridad.
