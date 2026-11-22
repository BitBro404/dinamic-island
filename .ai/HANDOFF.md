# Handoff

## Solicitud y objetivo
Añadir una burbuja de Bluetooth junto a la píldora, como la del pomodoro en curso, para el primer dispositivo
Bluetooth conectado: icono del dispositivo, anillo con el porcentaje de batería y tooltip `Nombre · NN%`. Sin
batería se muestra solo el nombre. Interruptor `bt_bubble` en «Más → Funciones», activo por defecto.

**Ampliación B6 (misma sesión):** el usuario pidió además que el **hover** de una burbuja solo muestre un tooltip
(nombre de la opción y qué está pasando; en Bluetooth, dispositivo y batería) sin expandir la isla, y que el
**clic** abra la página de esa actividad. El clic en la píldora sigue abriendo Inicio.

## Repositorios dentro del alcance
- Único repo: `/home/luis/dinamic island` (rama `main`). No hay repos anidados.
- Estado Git al empezar esta tarea: limpio, `main...origin/main`. El trabajo anterior ya fue **commiteado y subido**
  como `3c7eab2` («Universalizar la isla…») en `origin/main`.
- Para esta tarea **no se ha hecho commit ni push**; tampoco merge/rebase/reset.

## Estado actual
- Plan activo: `plan.md` (raíz). Plan universal anterior conservado en `.ai/plans/2026-11-21-isla-universal.md`.
- B0–B5 y B6.1–B6.7 terminados con TDD; falta únicamente la validación visual del usuario en su escritorio.
- Incidencia resuelta: el usuario no veía la burbuja con sus auriculares reales porque la isla en marcha usaba
  la copia instalada antigua (19:05). Se ejecutó `./install.sh`, la copia instalada ya contiene el cambio y la
  captura real muestra la burbuja (693 px de ancho, 203 px azules frente a 646/0 sin ella).
- No se ha escrito el resumen final en `.ai/summaries/`; depende de la validación visual del usuario.

## Decisiones confirmadas
- D1 burbuja redonda con anillo de batería; nombre y `%` en tooltip.
- D2 solo el primer dispositivo conectado, elegido por orden alfabético de nombre (estabilidad entre refrescos).
- D3 sin batería → nombre sin porcentaje, sin anillo.
- D4 función `bt_bubble` en «Más → Funciones», activada por defecto (no entra en `FEATURE_DEFAULTS`).
- D5 sin commit/push/merge/reset sin autorización nueva y explícita.
- La burbuja se inserta en `activities()` justo tras `pomo`; no se toca `PILL_ORDER` ni `BUB_MAX` (2).
- B6-D1 hover sobre burbuja = solo tooltip, isla compacta; hover sobre píldora = expande a inicio.
- B6-D2 clic en burbuja = abrir su página; clic en píldora = expandir a inicio.
- B6-D3 etiquetas: Llamada, Música, Pomodoro, Grabación, Recordatorio, Despliegues, Descargas, Audio,
  Presencia, Temporizador. Bluetooth sin etiqueta (usa el nombre del dispositivo).
- B6-D4 se quita la redundancia: `Grabando`→`Grabación`, `Descargando x`→`Descargas · x`,
  `En llamada`→`Llamada`. Sin cambios en colores ni geometría (B6-D5).

## Archivos modificados (esta tarea)
- `isla_dinamica/ui/bubbles.py`: `bluetooth_activity(devices)`, `_battery_pct(value)`, rama en `activities()`
  controlada por `c.feature("bt_bubble")`, campo `label` en cada actividad y `bubble_tip(act)`; `_set_bubbles`
  usa `bubble_tip`.
- `isla_dinamica/pages/bluetooth.py`: `feature("bt_bubble", "Burbuja Bluetooth", …)`.
- `isla_dinamica/ui/dock.py`: `_on_drag_end(_g, dx, dy)` → clic sin movimiento llama a `_tap()` (B6.8).
- `isla_dinamica/window.py`: `_tap()`/`_tapped()` (B6.8), `_set_hover(value, bubble=None)` (hover sobre burbuja no expande; con `bubble`
  abre esa página), `_bubble_clicked(i, ev)` conectado a cada widget de burbuja (clic real navega aunque
  `_bubble_at()` falle) y `_on_click` que delega en él.
- `tests/unit/test_bubbles.py`: 6 pruebas Bluetooth + 4 de `bubble_tip`/etiquetas; `tests/unit/test_bt_feature.py`:
  2 pruebas; `tests/unit/test_bubble_interaction.py` (nuevo): 7 pruebas de hover/clic (B6.7 incluido).
- `tests/fixtures/bluetooth_demo.py`: dispositivo falso para el arnés (`BT_NAME`, `BT_BATTERY`, `BT_ICON`,
  `BT_CONNECTED`, `BT_DEBUG`); imprime `bubble_tip`.
- `tests/harness.py`: «bubble»/`bubble2` simulan clic (`_set_hover(True, bubble=i)`).
- `README.md`, `docs/DOCUMENTACION.md`, `plan.md`, este handoff.

## Pruebas ejecutadas y resultados
- `make check` → `compileall` OK + **226 pruebas OK** (218 previas + 8 nuevas).
- RED inicial confirmado: `ImportError: cannot import name 'bluetooth_activity'`; RED del interruptor:
  `AssertionError: 0 != 1`; ambos corregidos en GREEN.
- `BT_DEBUG=1 BT_NAME=Auriculares BT_BATTERY=82 python3 tests/harness.py pill --setup
  tests/fixtures/bluetooth_demo.py --out /tmp/opencode/isla-bt` → tooltip `Auriculares · 82%`, PNG generado,
  sin tracebacks.
- Misma prueba con `BT_BATTERY=none` → tooltip `Auriculares`; con `BT_CONNECTED=0` → sin burbuja.
- Comprobación programática de las PNG: ancho 694 px con burbuja frente a 646 px sin ella; 191 px azules en
  la zona de la burbuja con batería frente a 35 px sin batería (solo el acento del icono).
- B5 ejecutado: `make check` → 226 OK; `make doctor` → 15 funciones sin cambios (Budgie/layer-shell);
  `make check-x11` (Docker + Xvfb + Openbox) → 0 tracebacks, ventana DOCK/arriba/arrastrable.
- B6 ejecutado: RED de `bubble_tip` (`ImportError`) y de hover (`AssertionError: True is not false`), ambos
  corregidos. B6.7 (clic real no navegaba) RED por `AttributeError: _bubble_clicked`, GREEN con manejador por widget.
  `make check` → **237 pruebas OK** (226 + 4 de tooltips + 7 de interacción); `make doctor` sin
  cambios; `make check-x11` → 0 tracebacks. Arnés `pill`, `bubble` y `bt` en `/tmp/opencode/isla-b6/` con tooltip
  `Auriculares · 82%`; el clic abrió la página (769×660 y 767×190 frente a 695×59 de la píldora).

## Fallos conocidos / bloqueos
- Este modelo no puede ver imágenes: las capturas se generaron y se comprobaron por píxeles, pero la revisión
  visual la debe hacer el usuario.
- El primer `GetManagedObjects` asíncrono de BlueZ sobrescribía el dispositivo falso del fixture; se corrigió
  restaurando el dict en `on_change`. No afecta al código de producción.
- Del trabajo universal anterior sigue pendiente la validación en VM de GNOME, KDE, XFCE, Cinnamon, LXQt y sway;
  la extensión GNOME es provisional (solo `node --check`). No es parte de esta tarea.

## Próximo paso exacto
**B7 (nueva, 2026-11-21):** burbuja «+N» + página «Tareas en curso». Plan escrito en `plan.md` → «Ampliación B7»,
decisiones B7-D1…D4 confirmadas; aprobado y **hecho con TDD** (259 pruebas OK, X11 sin tracebacks, instalado).
Archivos B7: `ui/bubbles.py`, `ui/style.py`, `window.py`, `pages/tasks.py` (nuevo), `pages/__init__.py`,
`tests/unit/test_tasks_page.py` (nuevo), `test_bubbles.py`, `test_bubble_interaction.py`,
`tests/fixtures/tasks_demo.py` (nuevo), `tests/harness.py`, README, DOCUMENTACION. Falta validación del usuario.

B6.8 hecho (segunda sesión, 2026-11-21): el clic real no navegaba porque el `Gtk.GestureDrag` en fase CAPTURE se
queda con el botón (log real: solo `_on_press`/`_on_drag_end`, nunca `_on_click`/`_bubble_clicked`). Ahora
`ui/dock.py::_on_drag_end` trata soltar sin moverse como clic → `window.py::_tap()`; `_tapped()` evita doble
acción. `make check` → 244 OK. `./install.sh` ejecutado: copia instalada = repo, sin la instrumentación temporal.
B6.9: comprobado que hover/clic valen para las 11 burbujas; +2 pruebas de caracterización (246 OK), sin
cambios de producción.
1. Pedir al usuario que confirme en su escritorio: hover sobre burbuja → tooltip sin expandir; clic en burbuja →
   abre su página; clic en la píldora → Inicio; arrastrar la isla sigue funcionando.
2. Solo tras esa confirmación: escribir `.ai/summaries/2026-11-21-burbuja-bluetooth.md`, actualizar
   `summaries/INDEX.md` y dejar este handoff sin tarea activa. Preguntar si quiere commit/push; no hacerlo por
   defecto.

## Preguntas pendientes
- ¿Confirma el usuario el nuevo comportamiento de hover (tooltip) y clic (abrir página)?
- ¿Quiere commit/push de esta tarea? (No autorizado todavía.)

## Qué no se debe repetir
- No validar clics emitiendo señales directamente sobre widgets: en el escritorio real el gesto de arrastre
  se queda con el `button-release`; el clic se trata en `drag-end`.
- No dejar instrumentación temporal en la copia instalada; `./install.sh` la sustituye por el repo.
- No leer `org.bluez` en pruebas unitarias: la lógica de selección es pura y ya está cubierta.
- No escribir nombres de escritorio fuera de `platform/` (lo comprueba `test_architecture.py`).
- No ampliar `BUB_MAX` ni meter Bluetooth en `PILL_ORDER` sin pedirlo.
- No ejecutar `install.sh` ni el arnés sin antes revisar `git status`: el arnés detiene y reinicia la isla
  instalada.
- No dar por aceptada la tarea ni escribir el resumen sin la validación del usuario.
