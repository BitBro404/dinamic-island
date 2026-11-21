# Memoria del proyecto: isla dinámica

- Entorno: Ubuntu, Budgie sobre Wayland (labwc), Python 3 + GTK3 (PyGObject). Instalar/reiniciar: `./install.sh`.
- Estructura: servicios sin UI en `isla_dinamica/services/` (hilo + `GLib.idle_add`), páginas mixin en
  `isla_dinamica/pages/` (`PAGES`, `feature()`, `tool()`), núcleo `core.py`, píldora y prioridades en `window.py`.
- Funciones activables: vienen encendidas salvo las de `common.FEATURE_DEFAULTS` (p. ej. `presence`).
- Pruebas unitarias: `python3 -W error::ResourceWarning -m unittest discover -s tests/unit` (no hay pytest).
  Capturas de UI: `python3 tests/harness.py <páginas> --setup tests/fixtures/<x>.py` (reinicia la isla instalada).
- Lógica testeable separada de hilos/hardware (reloj, detector y acciones inyectados), como `services/presence.py`.
