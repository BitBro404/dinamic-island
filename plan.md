# Plan: GitHub en la isla — arreglar el cambio de cuenta; ramas, PR entre ramas y stash por repo

Plan anterior (burbuja Bluetooth, ya en `ce8f1ea`) archivado en `.ai/plans/2026-11-21-burbuja-bluetooth.md`.

## Objetivo y resultado esperado
1. **Cambio de cuenta**: tras poner bien la contraseña, la página «Cuentas de GitHub» debe dejar de decir
   «Esperando tu contraseña…», marcar la cuenta nueva como «En uso en la isla» y mostrar las PR, repos y
   avisos de esa cuenta. La cuenta elegida debe **mantenerse al reiniciar la isla**.
2. **Por repo** (página del repo dentro de GitHub), para los repos de la cuenta elegida:
   - **Cambiar de rama** (locales y remotas); **bloqueado si hay cambios sin commit**.
   - **Crear PR de una rama a otra**: eliges origen y destino y la isla **abre GitHub** en la página de
     comparar para que confirmes allí. Si la rama de origen no está subida o tiene commits sin subir,
     **solo avisa** y no abre nada.
   - **Ver los stash** (si hay): rama, mensaje y hace cuánto; **Aplicar (pop)** y **Borrar** (segundo clic).

## Alcance
- Repositorios incluidos: único repo `/home/luis/dinamic island` (rama `main`). No hay repos anidados.
- Repositorios excluidos: ninguno. Los repos de `~/Documentos/WM` solo se **leen y operan** desde la isla en
  ejecución (cambio de rama/stash los hará el usuario al usar la isla); las pruebas usan repos temporales.
- Fuera: crear la PR con la API (se confirma en GitHub), crear/borrar ramas, merge/rebase locales,
  `stash push` manual, resolver conflictos.

## Contexto actual
- Estado Git: `main...origin/main [adelante 2]` y **el trabajo de cuentas/PR/push-pull está en el índice
  sin commit** (el commit falló porque la firma GPG pidió la contraseña de la llave y caducó). Este plan
  trabaja encima de ese índice; no se hace commit sin autorización.
- `config.json` del usuario ya tiene `"github_account": "BitBro404"` (la contraseña sí fue aceptada).
- Diagnóstico del bug (reproducido con un `pkexec` falso que devuelve 0, harness + fixture):
  1. **Causa principal — recursión infinita**: `Core.github` (property, `core.py`) crea `GitHub(...)` y lo
     guarda en `self._github[login]` **después** del constructor; el constructor llama a `refresh()` →
     `on_change()` → `core.changed("github")` → la ventana se redibuja → `pages/home.py` lee `c.github` →
     como aún no está guardado, crea otro → … → `RecursionError`. La excepción corta
     `Accounts.switch.authed` antes de su `self.on_change()`, así que la página se queda en «Esperando…».
  2. **La cuenta no se recuerda**: `Config.__init__` solo copia claves conocidas y no carga
     `github_account`; al reiniciar vuelve la cuenta activa de `gh`.
  3. **Nombre repetido**: `GitHubPage._switch(login)` tapa `Page._switch(cb)` (fábrica de `Gtk.Switch`).
     Hoy no rompe nada, pero confunde; se renombra.
- La página del repo (`ghrepo`) solo se abre desde «Commits por sincronizar» (repos con ↑/↓). Repos al día no
  tienen entrada → no se podría cambiar de rama ni ver stash en ellos.
- `services/gitwatch.py` ya tiene `repo_status` (incluye `stash` como número), `_git_run(..., token=)`,
  `auth_env(token)`, `sync()` en hilo con `GLib.idle_add`, `syncing` por ruta.

## Decisiones confirmadas (usuario, 2026-11-22)
- D1 Cambiar de rama con cambios sin commit (staged, modificados, sin seguimiento o en conflicto) → **bloqueado**,
  con mensaje «Haz commit o descarta los cambios antes de cambiar de rama».
- D2 PR con la rama de origen sin subir o con commits sin subir → **solo avisar** («Sube la rama X primero»),
  sin abrir GitHub.
- D3 Stash: **ver, aplicar (pop) y borrar** (borrar con segundo clic).

## Suposiciones y restricciones (propuestas; corregir si no encajan)
- S1 Nueva sección **«TUS REPOS»** en la página GitHub con **todos** los repos de la cuenta (no solo los
  pendientes); cada fila abre la página del repo. «Commits por sincronizar» se mantiene.
- S2 Ramas listadas: locales + remotas de `origin` sin copia local (al elegir una remota, `git switch <rama>`
  crea la local con seguimiento). Se ocultan `HEAD` y la rama actual.
- S3 Destino por defecto de la PR: la rama por defecto del remoto (`origin/HEAD`), si no `main`/`master`/`devel`.
  Origen por defecto: la rama actual. Origen = destino → aviso.
- S4 URL: `https://github.com/<owner>/<repo>/compare/<destino>...<origen>?expand=1` con nombres codificados
  (`urllib.parse.quote(nombre, safe="/")`), abierta con `util.safety.open_web`.
- S5 «Aplicar» = `git stash pop stash@{n}`. Antes de aplicar o borrar se comprueba que `stash@{n}` sigue
  siendo el mismo (por su hash) para no tocar otro si la lista cambió. Si `pop` choca, git conserva el stash y
  la isla muestra el error.
- S6 Todas las operaciones git corren en hilo (como `sync`) y el resultado vuelve con `GLib.idle_add`.
- S7 Sin commit/push/merge/rebase/reset del repo de la isla sin autorización.

## Contratos/dependencias
- `repo_status(s)` añade: `branches` (no; se pide aparte, ver T4), `stashes: [{ref, sha, branch, msg, ts}]`.
- `GitWatch.op(s, kind, done, **kw)` generaliza `sync`: `pull`, `push`, `switch` (branch), `stash_pop`
  (ref, sha), `stash_drop` (ref, sha). `done(ok, mensaje)`.
- Funciones puras nuevas en `gitwatch.py`: `parse_branches(out, current)`, `parse_stashes(out)`,
  `compare_url(slug, base, head)`, `pr_blocker(status, head, remote_branches)` → texto de aviso o `None`.

## Archivos o módulos
- `isla_dinamica/core.py` (property `github`), `isla_dinamica/config.py` (cargar `github_account`),
  `isla_dinamica/services/ghaccounts.py` (`authed` robusto), `isla_dinamica/services/gitwatch.py`,
  `isla_dinamica/pages/github.py`, `tests/unit/test_github_accounts.py`, `tests/unit/test_git_branches.py`
  (nuevo), `tests/fixtures/github_pages_demo.py`, `README.md`.

## Criterios de aceptación
- A1 Con `pkexec` que devuelve 0: la página de cuentas pasa a «En uso en la isla» en la cuenta nueva, sin
  excepciones, y `core.github.login` es la cuenta nueva.
- A2 Con `pkexec` que devuelve ≠0: mensaje rojo «Contraseña cancelada o incorrecta…» y sigue la anterior.
- A3 Reiniciar la isla conserva la cuenta elegida.
- A4 En un repo limpio, elegir otra rama la cambia (local o remota); con cambios sin commit no cambia y avisa.
- A5 «Crear PR» con origen subido y al día abre `…/compare/<destino>...<origen>?expand=1`; si no, avisa sin abrir.
- A6 Los stash se listan con rama, mensaje y hace cuánto; Aplicar los recupera; Borrar pide segundo clic y
  lo borra; si la lista cambió entre medias, no toca nada y lo dice.
- A7 Todas las pruebas unitarias pasan (`make check`).

## Estrategia de pruebas
- Unitarias puras (parsers, URL, bloqueos).
- Integración con **repos git temporales** (`tempfile`, `git init`, remoto «bare» local): switch, bloqueo por
  cambios, stash pop/drop con verificación de hash, aviso de rama sin subir. Sin red.
- Regresión del bug: prueba que crea `Core.github` con un `on_change` que vuelve a leer la property → no recursión.
- Visual: harness con fixture (repo y stash reales de un repo temporal) para capturas de la página del repo.

## Tareas
- [x] T1 Sin recursión al crear el servicio de una cuenta
  - Archivos: `core.py`, `services/github.py`.
  - RED: prueba con un núcleo mínimo cuyo `changed` lee `core.github` otra vez → hoy `RecursionError`.
  - GREEN: `GitHub(..., start=False)`; la property guarda la instancia y después llama `refresh()`.
  - Refactor: `Accounts.switch.authed` con `try/finally` para que `switching=None` y `on_change()` siempre ocurran.
- [x] T2 Recordar la cuenta elegida
  - Archivos: `config.py`. RED: `Config` con `{"github_account": "X"}` en disco → hoy `None`. GREEN: cargar si es `str`.
- [x] T3 Renombrar `GitHubPage._switch` → `_switch_account` (sin cambio de comportamiento; pruebas existentes).
- [x] T4 Ramas: `list_branches(repo)` + `parse_branches` y operación `switch` bloqueada con cambios
  - RED: repo temporal con `main` y `feat` (local) y `origin/remota`; con archivo modificado → bloqueo.
  - GREEN: `git for-each-ref --format=… refs/heads refs/remotes/origin`; `git switch <rama>`.
- [x] T5 PR entre ramas: `compare_url` y `pr_blocker`
  - RED: rama sin subir → «Sube la rama…»; con ↑ → «…tiene N commits sin subir»; igual a destino → aviso;
    OK → `None`; URL con nombres con `/` y espacios codificados.
  - GREEN: funciones puras + `default_branch(repo)` (`git symbolic-ref refs/remotes/origin/HEAD`).
- [x] T6 Stash: `parse_stashes` en `repo_status` y operaciones `stash_pop`/`stash_drop` con hash
  - RED: repo temporal con 2 stash → lista; pop del 1.º; drop con hash distinto → error sin tocar.
  - GREEN: `git stash list --format=%gd%x1f%H%x1f%gs%x1f%ct`; `git rev-parse stash@{n}` antes de actuar.
- [x] T7 UI: sección «TUS REPOS»; en la página del repo: selector de rama + «Cambiar», selector origen/destino
  + «Crear PR en GitHub», sección «STASH · N» con Aplicar/Borrar; mensajes de estado.
  - Verificación: harness con fixture de repo temporal; capturas revisadas.
- [x] T8 README, `make check`, `./install.sh`, verificación real del cambio de cuenta (lo confirma el usuario
  con su contraseña).

## Riesgos y casos límite
- Repos en estado «detached HEAD» → mostrar «(sin rama)» y permitir cambiar a una rama.
- Ramas remotas con el mismo nombre que una local → solo se muestra la local.
- `git switch` a una remota cuyo nombre existe en varios remotos → solo se usa `origin`.
- Stash de otra rama: se puede aplicar igual (git lo permite); se muestra la rama de origen en el texto.
- Repos sin remoto de GitHub no aparecen en «TUS REPOS» (siguen en Proyectos).
- El arnés detiene y reinicia la isla instalada; si se cuelga, volver a lanzar `~/.local/bin/isla-dinamica`.

## Pendientes/preguntas abiertas
- Confirmar S1–S6 (o corregirlas) al aprobar el plan.
- Commit del trabajo previo (cuentas/PR/push-pull) sigue pendiente de la firma GPG del usuario.

## Comandos de verificación
```bash
python3 -W error::ResourceWarning -m unittest discover -s tests/unit
make check
python3 tests/harness.py github ghacct ghrepo --wait 6 --setup tests/fixtures/github_pages_demo.py
./install.sh
```

## Estado y siguiente paso
- 2026-11-22: plan aprobado y **T1–T8 hechos con TDD**. Falta la validación del usuario.
  - T1 RED `RecursionError` (tests/unit/test_github_core.py) → GREEN `GitHub(start=False)` + registro antes de
    `refresh()`; refactor `authed` con `finally` (RED `'BitBro404' != None`).
  - T2 RED `test_config_github` → GREEN `github_account` en `DEFAULTS` y carga validada.
  - T3 `_switch` → `_switch_account`.
  - T4 RED `AttributeError parse_branches/list_branches/run_op` → GREEN en `gitwatch.py`; `sync()` usa `op()`.
  - T5 RED `compare_url/default_branch/pr_check` → GREEN.
  - T6 RED `parse_stashes`, `KeyError 'stashes'` → GREEN (pop/drop verifican el hash).
  - T7 UI: «TUS REPOS», selector de rama + Cambiar, origen → destino + «Crear PR en GitHub», «STASH · N»;
    `waiting()` mantiene abierta la isla con un desplegable abierto. Capturas con `tests/fixtures/git_branches_demo.py`.
  - T8 `make check` → **320 pruebas OK**; README; `./install.sh`; cambio de cuenta verificado con `pkexec`
    falso (ida y vuelta, sin «Esperando…»). La isla instalada vieja borraba `github_account` al guardar;
    se restauró `BitBro404` antes de instalar.
- Siguiente: el usuario prueba el cambio de cuenta con su contraseña real, cambiar de rama, PR y stash.
- Sin commit (el trabajo previo también sigue en el índice por la firma GPG).

## Ampliación P1 (2026-11-22): proyectos por cuenta
- Pedido: «añade por cuenta la posibilidad de añadir proyectos… que recuerde los proyectos… y poderlos quitar».
- Decisiones tomadas (a validar): lista propia por cuenta en `config.json` → `account_folders` {login: [rutas]};
  se escanean las carpetas globales de «Proyectos (git)» + las de la cuenta elegida; «Tus repos» = proyectos de la
  cuenta (`s["mine"]`) + repos globales con acceso; subpágina «Proyectos» junto a «Cuentas»; quitar no borra nada.
- [x] RED `tests/unit/test_account_projects.py` (9 pruebas: `KeyError 'account_folders'`, `AttributeError
  add_account_folder/scan_folders`, `TypeError _scan`) → GREEN en `config.py` y `services/gitwatch.py`.
- [x] UI `pages/github.py` (`ghproj`), `core.py` pasa `account=` a `GitWatch`; fixture
  `tests/fixtures/account_projects_demo.py` (no guarda config); capturas revisadas; README.

## Ampliación P2 (2026-11-22): crear ramas, merge y conflictos
- Pedido: crear ramas desde una existente; merge; si hay conflicto, usar Claude/OpenCode para corregirlo o abrir VS Code.
- Decisiones (a validar): merge = rama elegida → rama actual (`git merge --no-edit`), segundo clic, bloqueado con
  cambios; crear rama `--no-track` (desde remota `origin/x`), «ir» cambia a ella (bloqueado con cambios);
  conflicto → panel con archivos, Claude (`claude "<instrucción>"`) y OpenCode (`opencode --prompt … <repo>`) en
  terminal (`platform/terminal.py`), VS Code con los archivos; «Terminar merge» = `git commit --no-edit` (puede
  pedir la llave GPG); «Cancelar merge» = `git merge --abort` con segundo clic. La instrucción prohíbe commit/push/abort.
- [x] RED `tests/unit/test_git_merge.py` (create/merge/abort/finish/merge_from, git con config temporal sin GPG) y
  `tests/unit/test_conflict_tools.py` (terminales, comillas, herramientas, instrucción) → GREEN en
  `services/gitwatch.py` y `platform/terminal.py` (nuevo). Refactor `_files_msg(files, suffix)`.
- [x] UI en `pages/github.py`; demo `DEMO_CONFLICT=1 tests/fixtures/git_branches_demo.py`; capturas revisadas.
- No se lanzó Claude/OpenCode/VS Code de verdad (solo se comprobaron los argv); lo valida el usuario.

## Ampliación P3 (2026-11-22): siempre centrada, crece hacia los dos lados
- Pedido: verse siempre centrada; al expandirse crecer hacia x y -x; por defecto arriba al centro.
- Causa: en layer-shell se anclaba arriba+izquierda con margen izquierdo; margen y tamaño llegaban en commits
  distintos y crecía hacia la derecha antes de recolocarse.
- [x] RED `tests/unit/test_dock.py` (anclas solo al borde si está centrada, centro fijo al crecer, ajuste al centro
  al soltar ±6 %, `dock` guardado se ignora al arrancar) → GREEN en `ui/dock.py` (`layer_layout`, `drop_position`,
  `SNAP`) y `config.py` (no carga `dock`). Prueba antigua de anclas pasada a posiciones fuera del centro.
- [x] Verificado en pantalla (HDMI-A-1, ráfaga de `grim` durante la animación compact → github): centro 958.5–959.5
  en todos los cuadros (pantalla 960), incluido el rebote. 352 pruebas OK, instalado.
- Las burbujas cuentan dentro del grupo centrado (píldora + burbujas), no se centra solo la píldora.

## Ampliación P4 (2026-11-22): detener, recordar y relanzar servidores
- Pedido: detener servidores que corren y relanzarlos; que recuerde los comandos.
- Decisiones (a validar): se recuerda al detener desde la isla, al reiniciar y si se cae; se sube por los padres
  de la misma carpeta que sean lanzadores (npm/pnpm/yarn/nodemon/`sh -c`…), nunca a un shell interactivo ni a otra
  carpeta; se guarda carpeta, argv, puerto y solo `PATH` (no el resto del entorno); máximo 8 en `servers_recent`;
  relanzar = `Popen` con `start_new_session`, log en `~/.cache/isla-dinamica/servers/`; detener = SIGTERM al
  lanzador (a su grupo si lo encabeza) y al servidor; ↻ reinicia cuando el puerto queda libre.
- [x] RED `tests/unit/test_servers_relaunch.py` (lanzador, recordar, config, lanzamiento real con http.server,
  flujo detener/caída/reiniciar/relanzar/olvidar) → GREEN en `services/servers.py`, `config.py`, `core.py`,
  `events.py` (avisos «Relanzando» y «No se pudo relanzar»), `pages/servers.py` (↻, ■, sección DETENIDOS ▶ ✕).
- [x] Demo `tests/fixtures/servers_relaunch_demo.py`; capturas: ↻ reinició demo-frontend (11:46 → 11:47),
  DETENIDOS muestra demo-api. 367 pruebas OK, instalado. No probado con un `npm run dev` real.

## Ampliación P5 (2026-11-22): servidores en Docker
- Pedido: «¿y para Docker?» → detener, reiniciar y volver a arrancar contenedores desde Servidores.
- Decisión (a validar): agrupar por proyecto de compose (label `com.docker.compose.project`), si no por
  contenedor; ↻ `docker restart`, ■ `docker stop` (todos los del grupo), ▶ `docker start` de los nombres
  recordados (`servers_recent` con clave `docker`). Puertos publicados salen de la lista de `ss`.
  Mientras hay un stop/restart en curso no cuenta como caída; si `docker ps` falla, Docker queda como estaba.
- [x] RED `tests/unit/test_servers_docker.py` (puertos, grupos, quitar de ss, config, stop/restart/caída/
  relanzar/fallo/ocultar en marcha) → GREEN en `services/servers.py`, `config.py`, `events.py`, `pages/servers.py`.
- [x] Demo real `tests/fixtures/docker_demo.py` (alpine `isla-demo-web` en :18080, `--init`): ■ → DETENIDOS,
  ▶ → vuelve a correr; opengym agrupado sin tocarlo; contenedor de prueba borrado. 377 pruebas OK, instalado.
- [x] Fallo reportado: «tengo Docker corriendo y no lo veo». Causa: en la primera pasada `_apply_docker` no
  llamaba a `on_change` (`_first`) y las siguientes no veían diferencia → la página nunca se repintaba (la demo
  lo ocultaba porque la fixture provocaba otros cambios). Prueba `FirstScanTest` (RED→GREEN); captura con el
  Docker real: «opengym · :8080 · Docker Compose · api, web». 378 pruebas OK, instalado.

## Ampliación P6 (2026-11-22): escaneo de puertos a mano
- [x] RED `ManualScanTest` (ss + docker ps, responde con cuántos; responde None si `ss` falla) → GREEN
  `Servers.scan(cb)` y ↻ en la cabecera de «Servidores locales» (se desactiva mientras escanea; «Escaneo hecho · N»).
  Captura con el Docker real: «Escaneo hecho · 1 servidor». 380 pruebas OK, instalado.

## Ampliación P7 (2026-11-22): puertos de Node y Python, un proyecto de Docker por entrada
- Fallo: el `yarn dev` (nodemon) de wmservice-backend en :3000 no salía: Node 24 se llama «MainThread» en `ss`
  (y Python puede ser «python3.12»). `runtime(comm, exe)` mira también `/proc/<pid>/exe`; VS Code y Chrome
  siguen fuera. Con datos reales: «:3000 · wmservice-backend · Node», lanzador recordado `yarn dev`, `node`
  se encuentra con el PATH de nvm del proceso.
- Fallo: opengym salía dos veces en DETENIDOS (compose para web y api por separado). `remember` une por
  nombre de proyecto; la configuración une duplicados viejos al cargar.
- [x] RED `RuntimeTest`, `OneEntryPerProjectTest` → GREEN. 384 pruebas OK, instalado, captura revisada.
  No se detuvo ni relanzó el servidor real del usuario.

## Ampliación P8 (2026-11-22): sección DEV, Más opciones, 2.º monitor y punto de novedades
- Pedido: ocultar en el segundo monitor las opciones tras un botón (confirmado: «segundo monitor»); en Inicio una
  sección DEV (GitHub, Servidores, Proyectos, Teams y correo); botón «Más opciones»; punto y alerta cuando el
  fetch detecta commits por bajar o una PR nueva.
- Decisiones: principal = `get_primary_monitor()` o, si no hay (labwc), el de arriba a la izquierda (eDP-1);
  «Opciones» se vuelve a ocultar al cerrar la isla. PR nueva = PR abierta de otros en tus repos que no estaba
  (no en la primera carga, no repetida si la bandeja ya la avisó); también enciende el punto una revisión pedida.
  El punto (azul) se apaga al abrir GitHub (todo) o Proyectos (commits), y solo al hacer pull para los commits.
- [x] RED `tests/unit/test_dev_section.py` (PR nueva, no repetir con la bandeja, DevNews, monitor principal) y
  `test_events.py` (behind/PR nueva encienden el punto y alertan) → GREEN en `services/devnews.py` (nuevo),
  `util/screens.py` (nuevo), `services/github.py`, `events.py`, `core.py`, `ui/widgets/charts.py`, `window.py`,
  `pages/home.py`, `pages/github.py`, `pages/projects.py`.
- [x] Capturas de los dos monitores: eDP-1 completo con DEV y Más opciones; HDMI-A-1 con «Opciones» cerrado y
  abierto; punto azul en la píldora. Arreglo: `show_all()` no muestra una caja con `no_show_all`.
  393 pruebas OK, instalado. No visto aún con una PR nueva ni un commit por bajar reales.

## Ampliación P9 (2026-11-22): Inicio igual en los dos monitores
- Pedido: quitar el desplegable «Opciones» y dejar «Más opciones»; tras una prueba intermedia (ajustes arriba de
  «Más» en el secundario), el usuario mandó una captura: Inicio completo (ajustes, accesos, DEV, Más opciones)
  como en el portátil. Decisión: Inicio igual en todos los monitores, sin trato especial del secundario.
- Hecho: quitados el desplegable, `_on_primary`, `Page._opts_slot` y `util/screens.py` (`primary_index`) con su
  prueba (código muerto). 410 pruebas OK, instalado; captura de los dos monitores igual a la del usuario.

## Seguridad 2 (2026-11-22): revisión del código nuevo (GitHub/git, terminales, servidores, Docker)
Revisión previa (S1–S9, 2026-11-21) cubría Wi-Fi, URLs, portapapeles, bloqueo, descargas y config 0600.
Modelo de amenaza: otro usuario local; un repo o rama de terceros (clonado, descargado o de un colaborador);
el contenido de GitHub. El propio usuario y sus archivos (config.json 0600) se consideran de confianza.

| # | Gravedad | Riesgo | Corrección | Prueba (RED primero) |
|---|---|---|---|---|
| S10 | Alta | La isla ejecuta git sola (estado cada 4 s, fetch cada 5 min) en cada repo de las carpetas vigiladas. Un `.git/config` no confiable (repo descargado en un zip) ejecuta comandos: `core.fsmonitor` en cada `git status`, hooks (p. ej. `reference-transaction` en fetch), o un remoto local con `remote.<r>.uploadpack`. | Entorno de git con `core.fsmonitor=false` siempre; en lo automático además `core.hooksPath=/dev/null`, `protocol.ext.allow=never`, `protocol.file.allow=never`, y el fetch automático solo a remotos de red (https, ssh). Pull/push/merge/commit pedidos por el usuario conservan sus hooks. | `test_sec_git.py`: un fsmonitor malicioso no se ejecuta en `repo_status`; un hook no corre en el fetch automático; no se hace fetch automático de un remoto local con uploadpack; el token sigue solo para github.com. |
| S11 | Media | Inyección en las consultas GraphQL a GitHub: `owner/repo` sale de la URL del remoto (`.git/config`) y se mete entre comillas en la consulta enviada con tu token; el login tampoco se valida. | `github_slug` solo acepta los caracteres válidos de GitHub; el login se valida antes de consultar. | `test_sec_github.py` |
| S12 | Media | Inyección de instrucciones al asistente (Claude/OpenCode) con nombres de archivo en conflicto que vienen de la rama de otro. | Nombres sin caracteres de control ni saltos, recortados, como mucho 30, entre comillas y con la indicación de que son datos, no instrucciones. | `test_conflict_tools.py` |
| S13 | Media | Relanzar un servidor con un PATH que tenga entradas relativas (`.` o vacías) ejecuta un `node` plantado en la carpeta del proyecto. | PATH solo con rutas absolutas; `argv[0]` se resuelve a ruta absoluta antes de ejecutar. | `test_servers_relaunch.py` |
| S14 | Media | Detener/reiniciar manda SIGTERM a un PID guardado hace hasta 4 s: si ese PID se reutilizó, mataría otro proceso (o su grupo). | Se guarda la hora de arranque de cada PID y se comprueba antes de la señal. | `test_servers_relaunch.py` |
| S15 | Baja | Los logs de los servidores relanzados quedan legibles por otros usuarios (0644) y pueden tener secretos. | Carpeta 0700 y archivos 0600. | `test_servers_relaunch.py` |
| S16 | Baja | Nombres de contenedor de `servers_recent` sin validar: «--algo» se tomaría como opción de `docker start`. | Validar con el formato de nombres de Docker al cargar y al ejecutar; `--` antes de los nombres. | `test_servers_docker.py` |
| S17 | Baja | Una rama remota cuyo nombre empiece por «-» se pasaría a `git switch/merge` como opción. | Validar con `check-ref-format` y rechazar «-» al inicio; `--end-of-options` antes del nombre. | `test_git_branches.py` |

Estado: S10–S17 hechas con TDD (cada prueba vista en rojo por el motivo correcto; S10 confirmó que fsmonitor,
hooks y uploadpack SÍ se ejecutaban; S17 confirmó que `git switch --orphan=x` SÍ se aplicaba). 413 pruebas OK,
instalada; repo real comprobado (remoto de red, estado, fetch, página GitHub). Sin commit.
Efecto visible: los repos con remoto local (ruta o file://) ya no se bajan solos con el fetch automático.
Pruebas nuevas: `test_sec_git.py`, `test_sec_github.py`; ampliadas `test_conflict_tools.py`,
`test_servers_relaunch.py`, `test_servers_docker.py`, `test_git_branches.py`; ajustadas sin aflojar
`test_github_accounts.py` (índices de GIT_CONFIG y parámetro `user`) y `test_conflict_tools.py` (nombres entre «»).

## Registro de decisiones
- 2026-11-22 D1 bloquear cambio de rama con cambios; D2 PR solo avisa si falta subir; D3 stash ver/aplicar/borrar.
