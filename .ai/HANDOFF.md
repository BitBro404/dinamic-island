# Handoff

## Solicitud y objetivo
«Actualiza las docs y prepara el commit final» para la tarea de identidad facial del sensor de presencia
(aprobada antes con «si»). Se documenta y se deja todo listo para el commit; el push lo hace el usuario.

## Repositorios dentro del alcance
- Único repo: `/home/luis/dinamic island` (rama `main`).

## Estado actual
- T1–T7 ejecutados con TDD; `make check` → **456 pruebas OK**.
- `./install.sh` ejecutado con autorización: versión nueva activa, modelos descargados y verificados.
- Documentación actualizada: `README.md`, `docs/DOCUMENTACION.md`, `plan.md`, resumen nuevo
  `.ai/summaries/2026-11-22-presencia-identidad.md`, índice de resúmenes, memoria y este handoff.
- Todos los cambios (código, pruebas, fixture, `.gitignore` de `gallery.json` y docs) se incluyen en un único
  commit firmado con GPG. Sin push.

## Pruebas ejecutadas y resultados
- `make check` → 456 OK. Arnés visual con foto sintética: `/tmp/opencode/presence-identity/presence.png`.
- Verificación real de descarga: YuNet y SFace con sha-ok, `0600` en carpeta `0700`, cargan con el código
  instalado.

## Fallos conocidos/bloqueos
- **Pendiente de validación manual (C8–C11)** con cámara real: registrar, no bloquear con el usuario, bloquear
  con otra persona, forzar duda/muestra diaria, responder «sí» y «no» y borrar. Hasta entonces no se marca
  la tarea como aceptada.
- No hay detección de vida: foto/pantalla pueden engañar al reconocimiento (documentado como limitación).

## Próximo paso exacto
Usuario: validar C8–C11; si algo falla, ajustar. Después, marcar la tarea como aceptada y hacer push.

## Qué no se debe repetir
- No copiar hashes a ojo: los originales tenían 63 caracteres y la descarga real fallaba; hay prueba que exige
  SHA-256 de 64 hex.
- Los fixtures de arnés nunca deben usar la galería real (`~/.config/isla-dinamica/identity/gallery.json`):
  el primer arnés la escribió falsa y hubo que borrarla; usar `Gallery` con ruta temporal.
- Con plantilla y **sin cara** es ausencia real (bloquea); solo se pregunta si hay una cara dudosa.
- La miniatura de la tarjeta también debe liberarse al responder/caducar, no solo `pending_prompt["frame"]`.
- No usar `hasattr(o, "_switch")` para buscar la página GitHub: `Page` base también tiene `_switch`.
- No lanzar el arnés con `| tail` sin `timeout`: si se cuelga no hay salida (usar `PYTHONUNBUFFERED=1` y archivo).
- `show_all()` no muestra una caja con `set_no_show_all(True)`: mostrar los hijos y luego `show()`.
- Las pruebas que hacen commits usan config de git temporal sin `gpgsign`.
