# Memoria del proyecto: isla dinámica

- Entorno: Ubuntu, Budgie sobre Wayland (labwc), Python 3 + GTK3 (PyGObject). Instalar/reiniciar: `./install.sh`.
- Estructura (tras el refactor SOLID de 2026-11-21): servicios sin UI en `isla_dinamica/services/` (hilo +
  `GLib.idle_add`; temporizadores con `services/poller.py`); páginas = clases `Page` (`pages/base.py`) listadas en
  `PAGE_CLASSES`, con ganchos `live/on_collapse/typing/waiting`; núcleo `core.py`; avisos en `events.py`
  (EventRouter); prioridad de la píldora en `ui/pill.py` (`PILL_ORDER` + `pick_pill`, puro); ventana = mixins de
  `ui/` (pill_view, bubbles, paint, dock). Utilidades en `util/` (fmt, proc, safety, net, links), estilo en
  `ui/style.py`, fábricas GTK en `ui/gtk.py`, preferencias en `config.py`. Ya no existen `common.py` ni `widgets.py`.
- Sin `import *`: imports explícitos. `gi.require_version` solo en `isla_dinamica/__init__.py`.
- Seguridad: URLs solo con `util.safety.open_web`; contraseñas Wi-Fi por stdin (`nmcli --ask`); no apagar pantalla
  si el bloqueo falla; portapapeles sin secretos y con caducidad; isla oculta con la sesión bloqueada (LockGuard).
- Funciones activables: vienen encendidas salvo las de `config.FEATURE_DEFAULTS` (p. ej. `presence`).
- Pruebas unitarias: `python3 -W error::ResourceWarning -m unittest discover -s tests/unit` (no hay pytest).
  Capturas de UI: `python3 tests/harness.py <páginas> --setup tests/fixtures/<x>.py` (reinicia la isla instalada).
- Lógica testeable separada de hilos/hardware (reloj, detector y acciones inyectados), como `services/presence.py`.
