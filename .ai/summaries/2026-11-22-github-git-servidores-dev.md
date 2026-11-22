# 2026-11-22 · GitHub multicuenta, git por repo, servidores/Docker, isla centrada y sección DEV

## Solicitud
Varias peticiones encadenadas en una sesión (todas validadas por el usuario el 2026-11-22, «acepto el desarrollo»):
1. Cuentas de GitHub (cambio con contraseña del sistema), commits por subir/bajar con autor y mensaje, ver/aprobar/
   rechazar PR, fetch manual y automático cada 5 min por cuenta; arreglo del cambio de cuenta que se quedaba en
   «Esperando tu contraseña».
2. Por repo: cambiar de rama, PR de una rama a otra (abre GitHub), stash (ver, aplicar, borrar); proyectos por cuenta;
   crear rama desde otra, merge y resolución de conflictos con Claude/OpenCode/VS Code.
3. La isla siempre centrada, crece hacia los dos lados; arranca arriba al centro.
4. Servidores: detener, recordar el comando y relanzar; Docker (compose); escaneo a mano; puertos de Node y Python.
5. Inicio: sección DEV (GitHub, Servidores, Proyectos, Teams y correo), «Más opciones», opciones ocultas en el
   monitor secundario y punto azul + alerta con commits por bajar o PR nuevas.

## Resultado validado
- Servicios: `ghaccounts.py` (nuevo), `github.py` (PR de otros, bandeja, acciones, `new_pr`), `gitwatch.py` (ramas,
  merge, stash, PR, proyectos por cuenta, fetch 5 min), `servers.py` (lanzador real, recordar/relanzar, Docker,
  `scan`, `runtime`), `devnews.py` (nuevo, punto de novedades), `platform/terminal.py` (nuevo), `util/screens.py` (nuevo).
- UI: `pages/github.py`, `pages/servers.py`, `pages/home.py` (DEV, Más opciones, «Opciones» en el secundario),
  `ui/dock.py` (ancla solo al borde si está centrada), `ui/widgets/charts.py` (punto azul), `window.py`.
- Config: `github_account`, `account_folders`, `servers_recent`; `dock` ya no se carga (siempre arriba al centro).

## Decisiones
Ver `plan.md` (P1–P8 y registro). Destacadas: el token de gh va por entorno (`GH_TOKEN`, helper de credenciales
por `GIT_CONFIG_*`), nunca en argv; de un servidor se guarda carpeta, argv, puerto y solo `PATH`; relanzados en
su propia sesión con log en `~/.cache/isla-dinamica/servers/`; Docker agrupado por proyecto de compose; monitor
principal = el declarado o el de arriba a la izquierda; el punto azul se apaga al abrir GitHub/Proyectos o al hacer pull.

## Pruebas
`make check` → 393 pruebas OK. Capturas con `tests/harness.py` y `grim` de ambos monitores (centro 959±1 px en la
animación; Docker real con `tests/fixtures/docker_demo.py`; `servers_relaunch_demo.py`, `git_branches_demo.py`,
`account_projects_demo.py`, `github_pages_demo.py`).

## Limitaciones / pendientes
- No se lanzaron de verdad Claude/OpenCode/VS Code para conflictos (solo sus argv).
- No probados con datos reales: detener/relanzar un `yarn dev` del usuario, una PR nueva ni un commit por bajar
  (el punto azul se probó con datos de prueba).
- Fuera de la posición centrada, el crecimiento puede seguir viéndose desigual (márgenes y tamaño en commits distintos).
