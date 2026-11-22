# Handoff

## Solicitud y objetivo
Sin tarea activa. Último trabajo (2026-11-22) validado por el usuario y en commit: ver
`.ai/summaries/2026-11-22-github-git-servidores-dev.md`.

## Repositorios dentro del alcance
- Único repo: `/home/luis/dinamic island` (rama `main`).

## Estado actual
- Todo en commit (firmado con GPG). El push lo hace el usuario.
- Plan de referencia: `plan.md` (P1–P8 hechas).

## Pruebas ejecutadas y resultados
- `make check` → 393 pruebas OK.

## Fallos conocidos/bloqueos
- Ninguno abierto. Pendientes de prueba real: ver «Limitaciones» del resumen.

## Próximo paso exacto
Ninguno: esperar una nueva petición.

## Qué no se debe repetir
- No usar `hasattr(o, "_switch")` para buscar la página GitHub: `Page` base también tiene `_switch`.
- No lanzar el arnés con `| tail` sin `timeout`: si se cuelga no hay salida (usar `PYTHONUNBUFFERED=1` y archivo).
- `show_all()` no muestra una caja con `set_no_show_all(True)`: mostrar los hijos y luego `show()`.
- Las pruebas que hacen commits usan config de git temporal sin `gpgsign`.
