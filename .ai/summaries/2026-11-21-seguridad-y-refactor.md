# 2026-11-21 · Seguridad y refactor SOLID

## Solicitud
«Refactoriza el código, coméntalo, borra redundancia, mejora lectura y mantenibilidad. Usa SOLID. Además busca
potenciales riesgos de seguridad y arma un plan para corregirlos.» Orden decidido: seguridad primero, después refactor.

## Resultado validado por el usuario
Fase S (S1–S9) y refactor R0–R6 validados en la isla instalada. Plan: `plan.md`.

## Seguridad
| # | Corrección | Dónde | Prueba |
|---|---|---|---|
| S1 | Contraseña Wi-Fi por stdin (`nmcli --ask`), nunca en argv | `services/network.py` (`wifi_connect_command`) | `test_sec_wifi.py` |
| S2 | Si el bloqueo falla no se apaga la pantalla; estado `lock_failed` | `services/presence.py` | `test_presence_service.py` |
| S3 | Solo se abren URLs https (o http a localhost) | `util/safety.py` (`is_safe_web_url`, `open_web`), `services/deploys.deploy_url` | `test_sec_urls.py` |
| S4 | El portapapeles no guarda secretos y caduca a los 30 min | `services/clipboard.py` (`looks_secret`, `History`) | `test_sec_clipboard.py` |
| S5 | Isla oculta y portapapeles vacío con la sesión bloqueada (logind) | `services/lockguard.py` | `test_sec_lockguard.py` |
| S6 | Descargas ejecutables o desconocidas: se abre la carpeta | `util/safety.safe_to_open` | `test_sec_low.py` |
| S7 | Un aviso solo lanza la app que lo envió | `util/safety.desktop_matches_app` | `test_sec_low.py` |
| S8 | El registro de depuración no incluye el texto de los avisos | `util/safety.notif_debug_line` | `test_sec_low.py` |
| S9 | `config.json` con permisos 0600 | `config.Config.save` | `test_sec_low.py` |

## Refactor (arquitectura nueva)
- `common.py`, `widgets.py` e `isla_v1.py` borrados. Nuevos: `config.py`, `util/{fmt,proc,safety,net,links}.py`,
  `ui/{style,gtk,pill,pill_view,bubbles,dock,paint}.py`, `ui/widgets/{art,audio,weather_icon,charts,tile}.py`,
  `events.py` (EventRouter), `capture.py`, `services/poller.py`, `pages/base.py` (Page).
- Sin `import *`; `gi.require_version` solo en `isla_dinamica/__init__.py`; `services/__init__.py` no reexporta.
- Píldora: `PillState` + `PILL_ORDER` + `pick_pill` (puro) y un método `_pill_<clave>` por estado.
- Ventana = mixins de `ui/`; páginas = objetos `Page(host)` con ganchos `live/on_collapse/typing/waiting`.
- Docstring en todos los módulos y clases; README «Desarrollo» reescrito; `PROJECT_MEMORY.md` actualizado.
- Descartado: R3.3 `refresh_if_stale` (solo dos usos).

## Pruebas
- 118 pruebas unitarias en verde: `python3 -W error::ResourceWarning -m unittest discover -s tests/unit`.
- Nuevas: `test_sec_*` (5), `test_pill_priority`, `test_bubbles`, `test_poller`, `test_events`, `test_dock`,
  `test_volume_parse`, `test_play_sound`.
- `python3 -m compileall -q isla_dinamica` OK; arnés de capturas en 23 páginas sin errores.
- No vistas en rojo (escritas junto o después del código): S5 y `test_play_sound` (caracterización).

## Limitaciones y pendientes
- S1 no se probó con una red Wi-Fi real desde el agente.
- S5 depende de que el bloqueador de Budgie avise a logind.
- `services/presence.py` sigue en 426 líneas.
- Sin commit: lo hace el usuario (firma GPG).
