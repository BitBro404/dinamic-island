# Plan: burbuja de Bluetooth conectado (nombre y batería)

## Objetivo y resultado esperado
Cuando haya **un dispositivo Bluetooth conectado**, la isla debe mostrar una **burbuja separada junto a la píldora**,
 igual que la burbuja del pomodoro en curso:

- redonda, con el icono del dispositivo y un **anillo con el porcentaje de batería**;
- al pasar el ratón: tooltip `Auriculares · 82%` (o solo el nombre si el dispositivo no informa de batería);
- al hacer clic en la burbuja: abre la página de Bluetooth (comportamiento ya existente para cualquier burbuja);
- se puede desactivar en **⋯ (Más) → Funciones** (función `bt_bubble`, activada por defecto);
- si hay varios dispositivos conectados, solo se muestra **el primero en orden alfabético de nombre**
  (elección estable entre refrescos);
- sin batería conocida se muestra el nombre **sin porcentaje** y sin anillo de progreso.

No se modifica la píldora: Bluetooth nunca entra en `PILL_ORDER`; solo añade una actividad al cálculo de burbujas.

## Alcance
- Repositorios incluidos: único repo `/home/luis/dinamic island`, rama `main`. No hay repos anidados.
- Repositorios excluidos: ninguno.
- Dentro: selección pura del dispositivo, entrada en `activities()`, registro de la función, prueba unitaria,
  fixture visual con el arnés y documentación.
- Fuera: emparejar/conectar dispositivos, nuevos backends de Bluetooth, `--doctor`, ventanas/arrastre,
  prioridades de la píldora, otros escritorios (la detección de BlueZ ya funciona en todos).

## Contexto actual
- Estado Git verificado al empezar: `main...origin/main`, árbol limpio. Commit `3c7eab2` subido a `origin/main`
  (universalización). **No se hizo merge, rebase ni reset.**
- `isla_dinamica/services/network.py` → `Bluetooth.devices` ya expone
  `dict[ruta] = {"path", "name", "connected", "icon", "battery"}`; `battery` es `int` 0–100 o `None`.
  `PropertiesChanged` de `org.bluez.Battery1`/`Device1` ya llama a `refresh()` → `on_change()` → `core.changed("bt")`.
  `core.tick()` refresca la ventana cada segundo; no hace falta sondeo nuevo.
- `isla_dinamica/ui/bubbles.py`: `activities(c, m, playing, timer_left, now, wall)` devuelve una lista de dicts
  `{key, icon, accent, page, tip, [art], [progress]}` en orden de prioridad; el anillo de progreso se dibuja en
  `BubblesMixin._draw_bubbles` con `progress` (0–1); `BUB_MAX = 2` limita las burbujas visibles.
- `isla_dinamica/window.py`: `_show()` toma las actividades que no muestra la píldora y llama a `_set_bubbles()`;
  el clic/entrar en una burbuja abre `act["page"]` (`_set_hover`, `_bubble_at`).
- `isla_dinamica/pages/bluetooth.py`: página `bt` con la lista de dispositivos; muestra `" · {battery}%"` en la
  fila del dispositivo conectado. `pages/registry.py:feature(key, title, desc)` registra los interruptores que
  `pages/more.py` dibuja; `Core.feature()` usa `FEATURE_DEFAULTS` (por defecto `True` si no aparece).
- `tests/unit/test_bubbles.py` cubre `activities()` con un `core` falso (`SimpleNamespace`); el arnés
  `tests/harness.py --setup archivo.py` permite inyectar `setup(core)` y capturar la píldora (`pill`) o una burbuja
  (`bubble`, `bubble2`) con `grim`.
- Plan anterior archivado, sin sobrescribir: `.ai/plans/2026-11-21-isla-universal.md` (copia exacta de `plan.md`).

## Decisiones confirmadas (usuario, 2026-11-21)
- **D1** Burbuja redonda como la del pomodoro: icono + anillo de batería; nombre y `%` en el tooltip.
- **D2** Solo el primer dispositivo conectado; se elige por orden alfabético de nombre para que no cambie entre
  refrescos (suposición documentada abajo).
- **D3** Sin porcentaje: se muestra el nombre, sin anillo ni `%`.
- **D4** Interruptor `bt_bubble` en «Más → Funciones», activado por defecto.
- **D5** El plan se ejecuta solo con aprobación explícita; sin commit/push/merge/reset sin autorización.

## Suposiciones y restricciones
- «Primero» = `sorted(devices_connector, key=lambda d: str(d.get("name") or "").lower())[0]`. Es estable aunque el
  orden del `dict` de D-Bus cambie.
- Porcentaje válido: `int`/`float` (no `bool`) en `[0, 100]`; cualquier otro valor se trata como desconocido. El
  tooltip usa el entero más cercano (`82%`); el anillo usa `battery / 100`.
- El icono viene de `device["icon"]` (p. ej. `audio-headphones-symbolic`); `ui.gtk.icon_name` ya aplica
  sustitutos si el tema no lo tiene. No se añaden nuevos nombres de escritorio fuera de `platform/`
  (regla AST de `tests/unit/test_architecture.py`).
- La burbuja se inserta en `activities()` justo después de `pomo` y antes de `rec`, para que conviva con la
  burbuja del pomodoro. Con dos actividades anteriores activas, `BUB_MAX = 2` puede dejarla fuera: comportamiento
  aceptado, no se amplía el límite.
- No se guardan datos nuevos en `config.json`: la ausencia de `features.bt_bubble` significa activada.
- El nombre y el porcentaje son datos locales; no salen a la red ni se escriben en logs.

## Contratos / dependencias entre módulos
| Productor | Contrato | Consumidor |
| --- | --- | --- |
| `services/network.py::Bluetooth` | `devices: dict[str, {"path","name","connected","icon","battery"}]`, `battery: int 0–100 \| None` | `ui/bubbles.py::bluetooth_activity` |
| `ui/bubbles.py::activities` | actividad `{"key":"bt", "icon", "accent":"blue", "page":"bt", "tip", "progress"}` | `window.py::_show` → `_set_bubbles` → `_draw_bubbles` |
| `pages/registry.py::FEATURES` | `{"key":"bt_bubble","title","desc"}` | `pages/more.py::_build_more` → `Core.set_feature` → `changed("features")` |
| `tests/fixtures/bluetooth_demo.py` | `setup(core)` inyecta `core.bt.devices` y desactiva el `refresh` real | `tests/harness.py` (capturas) |

## Archivos o módulos a inspeccionar / modificar
- `isla_dinamica/ui/bubbles.py`: función pura nueva `bluetooth_activity(devices)` y enganche en `activities()`.
- `isla_dinamica/pages/bluetooth.py`: registrar `feature("bt_bubble", ...)` a nivel de módulo.
- `tests/unit/test_bubbles.py`: pruebas RED de selección, batería y feature.
- `tests/unit/test_bt_feature.py` (nuevo): prueba del registro en «Más» y del valor por defecto.
- `tests/fixtures/bluetooth_demo.py` (nuevo): dispositivo falso para el arnés.
- `README.md`, `docs/DOCUMENTACION.md`: burbuja y función nueva.
- `.ai/HANDOFF.md`, `plan.md`, `.ai/summaries/` (solo tras la validación del usuario).

## Criterios de aceptación
1. Con `bt_bubble` activo y un dispositivo conectado, `activities()` incluye una entrada `bt` con icono del
   dispositivo, `page="bt"`, `tip` con nombre y porcentaje, y `progress = battery / 100`.
2. Con ningún dispositivo conectado, con la función desactivada o sin servicio `bt`, no aparece la entrada `bt` y
    las pruebas existentes siguen pasando.
3. Sin batería o con batería inválida: `tip` contiene solo el nombre y `progress is None`.
4. Con varios conectados, se elige el de nombre alfabético menor; el orden de inserción del `dict` no afecta.
5. «Más → Funciones» muestra «Burbuja Bluetooth» activada por defecto; al desactivarla desaparece la burbuja.
6. `make check` en verde (218 pruebas previas + nuevas), sin tracebacks en el arnés con el fixture falso.
7. Captura visual de `pill` y `bubble` revisada; documentación actualizada.

## Estrategia de pruebas
- TDD estricto por cambio de comportamiento: RED (prueba falla por la razón correcta) → GREEN (cambio mínimo) →
  REFACTOR (simplificar y repetir).
- Pruebas puras sin GTK: `activities()` y `bluetooth_activity()` con `SimpleNamespace`, `now`/`wall` inyectados.
- Prueba de registro de función sin construir la UI: importar `pages.bluetooth` y comprobar `registry.FEATURES`.
- Verificación visual real: fixture + `tests/harness.py`, `grim`, revisión de PNG; opcional `make check-x11`
  (Docker Xvfb + Openbox) porque el cambio toca el dibujo de las burbujas.
- El usuario valida la captura antes de marcar la tarea aceptada y de escribir el resumen final.

## Tareas
### B0 — Contexto y plan (esta fase, sin código)
- [x] Leer memoria/plan/handoff y verificar `git status` y commits.
- [x] Copiar el plan anterior a `.ai/plans/2026-11-21-isla-universal.md` (sin borrar nada).
- [x] Escribir este plan y esperar aprobación explícita.
- **Repositorio:** único. **Verificación:** `git status --short --branch` sigue limpio salvo `plan.md` y la copia.

### B1 — RED: la actividad Bluetooth es lógica pura ✅ (GREEN + REFACTOR, 2026-11-21)
- **Repositorio:** único. **Archivos:** `tests/unit/test_bubbles.py`.
- Pruebas nuevas (fallan porque `bluetooth_activity` no existe / `activities` no emite `bt`):
  - `test_no_connected_device`: `bluetooth_activity({})` y solo desconectados → `None`.
  - `test_connected_device_first_by_name`: dict con `Z·mouse` y `A·Auriculares`, ambos conectados → gana
    `A·Auriculares`; comprueba `icon`, `accent`, `page` y `progress`.
  - `test_tip_includes_name_and_battery`: `battery=82` → `"Auriculares · 82%"`.
  - `test_unknown_battery_shows_only_name`: `battery=None` y también `True`, `"82"`, `-1`, `101` → sin `%`,
    `progress is None`.
  - `test_missing_name_falls_back`: sin `name` → `"Dispositivo"`.
  - `test_activities_respects_feature_and_order`: `core(("bt_bubble",), bt=NS(devices=…), pomo=…activo…)` →
    claves `["pomo", "bt", …]`; con `core(())` → sin `bt`; con un `core` sin atributo `bt` → no falla.
- **Cambio mínimo GREEN:** importar desde `isla_dinamica.ui.bubbles` e implementar `bluetooth_activity(devices)`;
  añadir en `activities()` una rama `if c.feature("bt_bubble") and getattr(c, "bt", None):` justo tras `pomo`,
  usando `bluetooth_activity(c.bt.devices)`.
- **REFACTOR/verificación:** extraer `_battery_pct(value)` (única validación), sin duplicar lógica en la página;
  `python3 -W error::ResourceWarning -m unittest tests.unit.test_bubbles -v`.

### B2 — RED/GREEN: interruptor en «Más» ✅ (2026-11-21)
- **Repositorio:** único. **Archivos:** `tests/unit/test_bt_feature.py` (nuevo), `pages/bluetooth.py`.
- RED: comprobar que `registry.FEATURES` contiene un `{"key": "bt_bubble", "title": "Burbuja Bluetooth", ...}`
  y que `Core.feature("bt_bubble")` por defecto es `True` (sin entradas en `config.json`).
- GREEN: en `pages/bluetooth.py`, importar `feature` de `.registry` y registrar la función con una descripción
  que diga que muestra el dispositivo conectado y su batería junto a la píldora.
- REFACTOR: sin entrada nueva en `FEATURE_DEFAULTS` (el valor por defecto ya es `True`); verificar que el texto
  no menciona nombres de escritorio (regla AST).

### B3 — Fixture visual y comprobación real ✅ (2026-11-21)
- **Repositorio:** único. **Archivos:** `tests/fixtures/bluetooth_demo.py` (nuevo).
- `setup(core)`: `core.config.save = lambda: None`, activa `features["bt_bubble"]`, rellena
  `core.bt.devices` con `{"/dev/A": {"path":…, "name": os.environ.get("BT_NAME","Auriculares"), "connected": True,
  "icon":"audio-headphones-symbolic", "battery": 82}}`, y neutraliza `core.bt.refresh` para que BlueZ no
  sobrescriba el estado falso. Variable `BT_BATTERY=none` para el caso sin batería.
- Comandos: `python3 tests/harness.py pill bubble --setup tests/fixtures/bluetooth_demo.py --out /tmp/opencode/isla-bt`
  y revisar las dos PNG; el arnés reinicia la isla instalada al terminar.
- Verificar a mano que el tooltip de la burbuja dice `Auriculares · 82%` (el arnés captura la burbuja; si el
  tooltip no aparece en `grim`, comprobarlo con `BT_BATTERY=none` y con el valor de `core.bubbles[0]["tip"]`
  impreso por el fixture).

### B4 — Documentación y cierre ✅ (2026-11-21)
- **Repositorio:** único. **Archivos:** `README.md` (sección de burbujas, tabla de Funciones y ejemplo de
  `config.json`), `docs/DOCUMENTACION.md` (section «Burbujas de actividades»), `.ai/HANDOFF.md`, `plan.md`.
- Actualizar el handoff con el estado real: commit/push ya hechos, nueva tarea en curso y qué falta para aceptarla.
- **No** escribir `.ai/summaries/` ni marcar aceptada la tarea hasta que el usuario valide las capturas.
- Tras la validación: resumen `2026-11-21-burbuja-bluetooth.md`, índice y handoff sin tarea activa. Solo entonces
  preguntar al usuario si quiere commit/push (no se hacen por defecto).

### B5 — Verificación final ✅ (2026-11-21; pendiente la validación visual del usuario)
- `make check` → `compileall` + todas las unitarias (218 anteriores + nuevas).
- `python3 tests/harness.py …` con el fixture (B3), sin tracebacks.
- Opcional recomendado: `make check-x11` (Docker + Xvfb + Openbox) y `make doctor` (no debe cambiar).
- `git status --short --branch` antes de cualquier commit (no autorizado todavía).

## Riesgos y casos límite
- `BUB_MAX = 2`: con llamada + música activas, la burbuja Bluetooth no entra; se prefiere no agrandar la isla.
- El dispositivo se desconecta mientras la burbuja está visible: `PropertiesChanged` invoca `refresh()` y la
  burbuja desaparece en el siguiente ciclo.
- BlueZ no siempre expone `org.bluez.Battery1` (ratones y altavoces sin batería): D3 cubre el caso.
- Un `Icon` raro puede no existir en el tema: ya hay fallback en `ui/gtk.py`; no se amplía su tabla salvo que la
  captura demuestre lo contrario.
- Máscara X11 sin compositor: `_shape_key` ya incluye `len(self.bubbles)`, así que el recorte se recalcula al
  aparecer/desaparecer la burbuja; verificar con `make check-x11`.
- No se toca `PILL_ORDER`: Bluetooth jamás usurpa la píldora de una llamada o el pomodoro.

## Pendientes / preguntas abiertas
- **Aprobación del plan**: no se ejecuta B1–B5 hasta que el usuario diga explícitamente que continúe.
- Validación visual del usuario (capturas del arnés) antes de escribir el resumen final.
- Queda fuera de alcance la validación en VM de los otros escritorios del plan universal anterior; sigue en
  `docs/ESCRITORIOS.md`.
- Sin commit, push, merge, rebase ni reset sin autorización nueva y explícita.

## Comandos de verificación
```bash
git status --short --branch
make check
python3 -W error::ResourceWarning -m unittest tests.unit.test_bubbles tests.unit.test_bt_feature -v
BT_NAME=Auriculares BT_BATTERY=82 python3 tests/harness.py pill bubble \
  --setup tests/fixtures/bluetooth_demo.py --out /tmp/opencode/isla-bt
BT_BATTERY=none python3 tests/harness.py bubble \
  --setup tests/fixtures/bluetooth_demo.py --out /tmp/opencode/isla-bt-none
make doctor
make check-x11   # opcional; Docker + Xvfb + Openbox
```

## Estado y siguiente paso
**Estado (2026-11-21):** aprobado por el usuario; B0–B5 terminados con TDD, pendiente solo la validación visual.
`make check` → 226 pruebas OK; `make doctor` → 15 funciones sin cambios; `make check-x11` → 0 tracebacks.
Capturas reales generadas: `/tmp/opencode/isla-bt/pill.png` (82 %), `/tmp/opencode/isla-bt-none/pill.png`
(sin batería) y `/tmp/opencode/isla-bt-off/pill.png` (desconectado, sin burbuja). Los tooltips calculados fueron
`Auriculares · 82%` y `Auriculares`; la zona de la burbuja crece 48 px y el anillo azul aparece solo con batería.

**Incidencia de despliegue (2026-11-21):** el usuario vio sus auriculares reales conectados (`BT`, 80 %) pero no
veía la burbuja. Diagnóstico: el proceso en marcha era `~/.local/bin/isla-dinamica`, que importa la copia de
`~/.local/share/isla-dinamica/isla_dinamica` de las 19:05, anterior al cambio (19:24); el arnés había reiniciado
esa copia al terminar. No era un fallo de código: BlueZ reportaba `Connected=True`, `battery=80`. Se ejecutó
`./install.sh` (copia + reinicio), se verificó que la copia instalada contiene `bluetooth_activity`/`bt_bubble`
y se capturó la isla real: 693 px de ancho y 203 px azules en la zona de la burbuja (frente a 646/0 sin ella).
Se añadió la entrada correspondiente a la tabla de problemas frecuentes del README.

**Ampliación B6 (2026-11-21):** el usuario pidió además separar hover de clic en las burbujas. B6.1–B6.6
terminados con TDD; `make check` → 234 pruebas OK, `make doctor` sin cambios, `make check-x11` → 0 tracebacks.
Tooltips con nombre de opción + estado (`bubble_tip`), hover no expande y clic abre la página; ver la sección
B6 más abajo y `/tmp/opencode/isla-b6/`.

**Siguiente paso exacto:** ver «Estado de B6» al final (B6.8 hecho e instalado; falta la validación del usuario).

## Registro de decisiones
| Fecha | Decisión | Origen |
| --- | --- | --- |
| 2026-11-21 | Burbuja redonda con anillo; nombre y `%` en tooltip | Usuario (D1) |
| 2026-11-21 | Un solo dispositivo; primero por nombre (suposición de estabilidad) | Usuario (D2) + suposición |
| 2026-11-21 | Sin batería → nombre sin porcentaje ni anillo | Usuario (D3) |
| 2026-11-21 | Función `bt_bubble` en «Más», activa por defecto | Usuario (D4) |
| 2026-11-21 | Sin commit/push sin autorización; plan anterior conservado en `.ai/plans/` | Usuario (D5) + flujo TDD |

---

# Ampliación B6 — interacción de las burbujas (solicitud del usuario, 2026-11-21)

## Objetivo y resultado esperado
El usuario pidió cambiar el comportamiento de las burbujas:

- **Hover sobre una burbuja → solo tooltip**, sin expandir la isla ni abrir la página. El tooltip debe decir:
  - Bluetooth: nombre del dispositivo y batería (`BT · 80%`, o solo `BT` si no reporta batería).
  - Resto de actividades: **nombre de la opción y qué está pasando ahora dentro de ella**, p. ej.
    `Pomodoro · Enfoque · 12:30`, `Música · Canción · Artista`, `Grabación · 00:12`.
- **Clic sobre una burbuja → abrir su página** (lo que antes hacía el hover). El clic en la píldora sigue
  expandiendo el panel de inicio igual que antes.

## Contexto técnico
- `window.py::_set_hover(True)` abre hoy la página de la burbuja bajo el ratón (`_bubble_at()`) y expande el panel
  110 ms después de entrar (`_on_enter` → `GLib.timeout_add`). Por eso el tooltip no llega a verse.
- `window.py::_on_click` expansiona siempre en vista `compact`; no distingue si el clic fue sobre una burbuja.
- `ui/bubbles.py::_set_bubbles` ya hace `st.set_tooltip_text(a.get("tip"))`, pero los `tip` actuales no incluyen
  el nombre de la opción (`Trabajo · 12:30`, `Canción · Artista`…).
- `tests/harness.py` simula «bubble» con `_set_hover(True)`; debe pasar a simular clic.
- La actividad `bt` no lleva prefijo de opción (D1: nombre del dispositivo + batería).

## Decisiones y suposiciones de B6
- **B6-D1** Al entrar el ratón en una burbuja la isla permanece compacta; el tooltip GTK aparece sobre la burbuja.
  Al entrar en la píldora (no en una burbuja) se sigue expandiendo a inicio tras 110 ms.
- **B6-D2** Clic en burbuja = abrir `act["page"]` y expandir; clic en píldora = expandir a inicio.
- **B6-D3** Etiquetas de tooltip: `Llamada`, `Música`, `Pomodoro`, `Grabación`, `Recordatorio`, `Despliegues`,
  `Descargas`, `Audio`, `Presencia`, `Temporizador`. Bluetooth sin etiqueta (usa el nombre del dispositivo).
- **B6-D4** Se elimina la redundancia de los textos actuales: `Grabando · 00:12` → `Grabación · 00:12`,
  `Descargando x.zip` → `Descargas · x.zip`, `En llamada · Meet · 02:34` → `Llamada · Meet · 02:34`.
- **B6-D5** Sin cambios en `PILL_ORDER`, `BUB_MAX`, colores ni geometría.

## Archivos a modificar
- `isla_dinamica/ui/bubbles.py`: campo `label` en cada actividad, función pura `bubble_tip(act)` y uso en
  `_set_bubbles`.
- `isla_dinamica/window.py`: `_set_hover(value, bubble=None)` (no expande sobre burbuja; abre la página si se
  pasa `bubble`) y `_on_click` (clic en burbuja → `_set_hover(True, bubble=i)`).
- `tests/unit/test_bubbles.py`: etiquetas y `bubble_tip`.
- `tests/unit/test_bubble_interaction.py` (nuevo): prueba de `_on_click`/`_set_hover` con un objeto falso que
  usa los métodos reales de `IslandWindow` (sin GTK).
- `tests/harness.py`: «bubble» simula clic; `tests/fixtures/bluetooth_demo.py`: imprime `bubble_tip`.
- `README.md`, `docs/DOCUMENTACION.md`, `.ai/HANDOFF.md`, `plan.md`.

## Tareas (TDD)
### B6.1 RED — tooltips con nombre de opción ✅ (2026-11-21)
- Pruebas: `bubble_tip({"tip": "BT · 80%"})`→`BT · 80%`; `bubble_tip({"label":"Pomodoro","tip":"Enfoque · 12:30"})`
  →`Pomodoro · Enfoque · 12:30`; `activities()` con varias actividades activas devuelve las etiquetas de B6-D3.
- Verificar que fallan por `bubble_tip` inexistente y por falta de `label`.

### B6.2 GREEN — tooltip ✅ (2026-11-21)
- Añadir `bubble_tip` y los `label`; `_set_bubbles` usa `bubble_tip(a)`. Ajustar los textos redundantes de B6-D4.

### B6.3 RED — clic abre, hover no expande ✅ (2026-11-21)
- Pruebas con objeto falso: (a) `_set_hover(True)` con `_bubble_at()=0` deja `hover=False` y no llama a `_opened`;
  (b) `_on_click` en compact con `_bubble_at()=0` deja `hover=True`, `page` = el de la burbuja y llama a
  `_opened` con esa página; (c) `_on_click` en compact sin burbuja expande a `home`; (d) en vista `card` no cambia.
- Verificar RED por la firma antigua de `_set_hover` y por `_on_click` no distingue burbuja.

### B6.4 GREEN — interacción ✅ (2026-11-21)
- `_set_hover(value, bubble=None)`: si `value` y `bubble is None` y hay burbuja bajo el ratón → `return False`;
  si se pasa `bubble`, abrir esa página antes de expandir.
- `_on_click`: en compact, `i = self._bubble_at()`; si `i is not None` → `_set_hover(True, bubble=i)`, si no →
  `_set_hover(True)`.

### B6.5 — arnés y verificación real ✅ (2026-11-21)
- `tests/harness.py`: «bubble»/`bubble2` deben invocar el clic (`_set_hover(True, bubble=i)` o `_on_click` con
  evento falso) y verificar que se abre la página; añadir comprobación del tooltip calculado.
- Repetir capturas con el dispositivo real (`BT` 80 %) y con el fixture.
- `make check`, `make doctor`, `make check-x11`; revisar que no haya tracebacks.

### B6.6 — documentación y cierre ✅ (2026-11-21)

### B6.7 — ARREGLO: clic real en la burbuja no navegaba (2026-11-21)
**Síntoma del usuario:** con pomodoro + Bluetooth visibles, hacer clic en cualquiera no abría su pantalla.
**Diagnóstico:** el arnés llamaba `_set_hover(True, bubble=i)` directamente y pasaba, pero el clic real depende de
`_bubble_at()` (coordenadas del puntero contra rectángulos calculados) y podía caer fuera → se expandía Inicio.
**Solución TDD:** RED con `AttributeError: _bubble_clicked`; GREEN: cada widget de burbuja conecta su propio
`button-release-event` a `_bubble_clicked(i, ev)` (devuelve True para no propagar al EventBox) y `_on_click`
delega en él cuando `_bubble_at()` sí acierta. +3 pruebas (237 en total). Evento GTK real emitido sobre el widget
en el arnés → `page=bt`, `visible=bt`, sin llamada al `_on_click` del EventBox.
- README y `docs/DOCUMENTACION.md`: «pasar el ratón = tooltip; clic = abrir la página», ejemplos de tooltips.
- Actualizar handoff y plan; pedir validación al usuario antes del resumen; sin commit/push sin autorización.

### B6.8 — ARREGLO: el clic real seguía sin navegar ✅ (2026-11-21, segunda sesión)
**Evidencia:** log de la instrumentación temporal de la copia instalada (`/tmp/opencode/isla-real-click.log`):
3 clics reales sobre la burbuja (`bubble_at 0`) generaron `_on_press` + `_on_drag_end` (desplazamiento 0,0) pero
**ni `_on_click` ni `_bubble_clicked`**. El `Gtk.GestureDrag` en fase CAPTURE sobre la ventana se queda con el
botón y el `button-release-event` no llega al EventBox ni a la burbuja (el `Gtk.Stack` de la burbuja tampoco
tiene ventana propia). El arnés de B6.7 pasaba porque emitía la señal directamente sobre el widget.
(La alternancia de `SHOW` entre dos monitores del log es normal: hay una ventana por monitor.)
**Solución TDD:** RED con 4 fallos (`False is not true`, `'home' != 'bt'`, `['bt','bt'] != ['bt']`).
GREEN: `ui/dock.py::_on_drag_end(_g, dx, dy)` trata soltar sin moverse (`hypot < DRAG_MIN`, sin arrastre
reciente) como clic → `window.py::_tap()` (solo en vista compacta: burbuja → su página, píldora → Inicio).
`_tapped()` evita repetir la acción donde el `button-release` sí llega (X11). +7 pruebas (244 en total).
`./install.sh` ejecutado: la copia instalada es idéntica al repo y ya no lleva la instrumentación.
Limitación: el arnés no puede simular el puntero real; la confirmación es del usuario.

### B6.9 — mismo comportamiento en todas las burbujas ✅ (2026-11-21, segunda sesión)
Solicitud: «replica el comportamiento en las otras opciones que tengan burbujas». Verificado que ya es genérico:
`_tap`/`_set_hover(bubble=i)` usan `self.bubbles[i]["page"]` y `_set_bubbles` usa `bubble_tip(a)` para cualquier
actividad. Las 11 (llamada, música, pomodoro, Bluetooth, grabación, recordatorio, despliegues, descargas, audio,
presencia, temporizador) apuntan a páginas registradas. Sin cambios de producción; +2 pruebas de caracterización
(pasan de entrada, no son RED): `test_every_bubble_opens_a_registered_page_and_has_a_tooltip` y
`test_real_click_opens_the_page_of_any_bubble`. `make check` → 246 OK. No hace falta reinstalar.

## Criterios de aceptación B6
1. Al poner el ratón sobre la burbuja Bluetooth se ve `BT · 80%` y la isla **no** se expande.
2. Al poner el ratón sobre las demás burbujas se ve `Nombre de la opción · estado actual`.
3. Al hacer clic en una burbuja se abre su página (p. ej. Bluetooth, Pomodoro, Inicio para música).
4. Al hacer clic en la píldora sigue abriéndose el inicio.
5. Suite en verde (226 pruebas previas + nuevas), capturas/arnés sin tracebacks, documentación actualizada.

## Estado de B6
Aprobado por el usuario («si»); B6.1–B6.7 terminados con TDD. RED comprobado en B6.1 (`ImportError: cannot
import name 'bubble_tip'`) y en B6.3 (`AssertionError: True is not false`). `make check` → **237 pruebas OK**
(226 previas + 4 de tooltips + 7 de interacción, incluido el arreglo B6.7). `make doctor` sin cambios;
`make check-x11` → 0 tracebacks. Arnés: `pill`, `bubble` y `bt` capturados con tooltip `Auriculares · 82%`;
el clic en «bubble» abrió la página (capturas de 769×660 y 767×190 frente a 695×59 de la píldora).

B6.8 (clic real capturado por el gesto de arrastre) terminado con TDD: `make check` → **244 pruebas OK**;
`./install.sh` ejecutado y verificado (copia instalada = repo).

**Siguiente paso exacto:** pedir la validación del usuario en su escritorio (hover → tooltip sin expandir;
clic en burbuja → abre su página; clic en píldora → Inicio; arrastrar sigue funcionando) y solo entonces
escribir el resumen; sin commit/push sin autorización. Quedan fuera de alcance las VM de otros
escritorios del plan universal anterior.

---

# Ampliación B7 — burbuja «+N» y pantalla «Tareas en curso» (solicitud del usuario, 2026-11-21)

> **Estado (2026-11-21): aprobado («si, empieza»); B7.1–B7.5 terminados con TDD. Pendiente: validación del usuario.**
> RED: `ImportError: bubble_slots` (B7.1), `ModuleNotFoundError: pages.tasks` (B7.2/B7.3); B7.4 (clic en «+N») pasó
> sin cambios por B6.9. `make check` → **259 OK**; `make doctor` sin errores; `make check-x11` → Tracebacks: 0.
> Arnés `pill bubble3 tasks` con `tests/fixtures/tasks_demo.py` → `/tmp/opencode/isla-b7/` (revisadas: píldora con
> música real + pomodoro + Bluetooth + `+2`; página con 5 filas). `./install.sh` ejecutado (copia = repo).
> Implementación: `ui/bubbles.py::bubble_slots`/`MORE_KEY`, hijo «count» en `_set_bubbles`; `window.py` `BUB_MAX + 1`
> huecos; `pages/tasks.py` (`task_rows`, `TasksPage`, función `bub_more`); estilo `.bub-count` en `ui/style.py`.
> B1–B6.9 siguen pendientes solo de la validación visual del usuario (ver «Estado de B6»).

## Objetivo y resultado esperado
Solicitud: «añade una burbuja extra para que por defecto muestre cuántas burbujas extra no se muestran y esa
pantalla me muestre todas las tareas que se están ejecutando».

- Cuando haya más actividades de las que caben (`BUB_MAX = 2` burbujas), aparece **una burbuja extra «+N»**
  al final, con N = actividades ocultas. Ejemplo: píldora = llamada; burbujas = pomodoro, Bluetooth;
  ocultas = grabación, descargas → se ve `[píldora] (pomo) (bt) (+2)`.
- Hover sobre «+N» → tooltip `Tareas en curso · 2 más` (misma regla B6: no expande).
- Clic sobre «+N» → abre la página nueva **`tasks` («Tareas en curso»)**.
- La página lista **todas** las actividades en curso (la de la píldora, las burbujas visibles y las ocultas), en
  el orden de prioridad de `activities()`: icono, nombre de la opción (`label`, o el nombre del dispositivo en
  Bluetooth) y estado (`tip`). **Clic en una fila → abre la página de esa actividad.**
- Interruptor **«Burbuja de tareas»** (`bub_more`) en «Más → Funciones», activo por defecto.

## Decisiones confirmadas (usuario, 2026-11-21)
- **B7-D1** «+N» es un hueco **extra**: siguen 2 burbujas reales + «+N» (la isla crece `H + BUB_GAP` = 40 px solo
  con desbordamiento).
- **B7-D2** «+N» aparece **solo si hay ocultas** (N ≥ 1).
- **B7-D3** La página lista **todas** las actividades y cada fila es clicable (abre su página).
- **B7-D4** Interruptor `bub_more` en «Más → Funciones», activo por defecto (sin entrada en `FEATURE_DEFAULTS`).

## Suposiciones y restricciones
- N cuenta actividades que no están ni en la píldora (`_shown`) ni en las 2 burbujas visibles.
- Con la función desactivada: comportamiento actual (2 burbujas, el resto oculto sin aviso).
- «+N» no tiene anillo de progreso; dibujo: círculo negro igual que las demás, texto `+N` blanco centrado
  (Gtk.Label en el `Gtk.Stack` de la burbuja, hijo nuevo «count»). Con N ≥ 10 se muestra `+9…`? → **no**: se
  muestra el número real (`+10`); con 11 actividades posibles, N ≤ 9 en la práctica.
- En vertical (isla pegada a un borde lateral) «+N» va debajo de las otras, igual que hoy.
- La página `tasks` no aparece en «Más → Herramientas» (solo se llega por la burbuja). Sin actividades muestra
  «No hay tareas en curso» (puede ocurrir si se abre justo cuando terminan).
- Sin nombres de escritorio fuera de `platform/` (regla AST). Sin datos nuevos en `config.json`.

## Contratos
| Productor | Contrato | Consumidor |
| --- | --- | --- |
| `ui/bubbles.py::bubble_slots(acts, shown, limit, more)` (pura, nueva) | lista de burbujas visibles; si sobran y `more`, añade `{"key":"more","label":"Tareas en curso","icon":None,"count":N,"page":"tasks","tip":"N más"}` | `window.py::_show` → `_set_bubbles` |
| `ui/bubbles.py::_set_bubbles` | `count` → hijo «count» del Stack con texto `+N` | dibujo / tooltip (`bubble_tip`) |
| `pages/tasks.py::TasksPage` (nueva, `PAGES={"tasks": …}`) | filas a partir de `activities()` en `live()`; clic → `host.go(act["page"])` | usuario |
| `pages/registry.py::feature("bub_more", …)` | interruptor en «Más» | `bubble_slots(..., more=c.feature("bub_more"))` |

## Archivos a modificar
- `isla_dinamica/ui/bubbles.py`: `bubble_slots`, `MORE_KEY`, rama «count» en `_set_bubbles`; `_draw_bubbles` sin anillo
  para «more» (ya ocurre: no lleva `progress`).
- `isla_dinamica/window.py`: crear `BUB_MAX + 1` widgets de burbuja (el último admite el texto) y usar
  `bubble_slots` en `_show`.
- `isla_dinamica/pages/tasks.py` (nuevo) + `pages/__init__.py` (`PAGE_CLASSES`).
- `tests/unit/test_bubbles.py`, `tests/unit/test_tasks_page.py` (nuevo, lógica pura de filas),
  `tests/unit/test_bubble_interaction.py` (clic en «+N» abre `tasks`).
- `tests/fixtures/tasks_demo.py` (nuevo): 5 actividades a la vez para el arnés.
- `README.md`, `docs/DOCUMENTACION.md`, `.ai/HANDOFF.md`, `plan.md`.

## Tareas (TDD)
### B7.1 RED/GREEN — `bubble_slots` (lógica pura)
- RED en `test_bubbles.py` (falla por `ImportError: bubble_slots`):
  - 2 actividades no mostradas → las 2, sin «more».
  - 4 no mostradas (`pomo, bt, rec, download`), `more=True` → `[pomo, bt, more(count=2)]`.
  - 3 no mostradas, `more=False` → `[pomo, bt]` (comportamiento actual).
  - las de `shown` (píldora) no cuentan para N.
  - `bubble_tip(more)` → `Tareas en curso · 2 más`.
- GREEN: implementar `bubble_slots`; REFACTOR: `_show` usa `bubble_slots` en lugar del corte `[:BUB_MAX]`.

### B7.2 RED/GREEN — interruptor `bub_more`
- RED en `test_bt_feature.py` (o nuevo `test_tasks_page.py`): `registry.FEATURES` contiene `bub_more` con título
  «Burbuja de tareas»; `Core.feature("bub_more")` es `True` sin config.
- GREEN: `feature(...)` en `pages/tasks.py`.

### B7.3 RED/GREEN — página «Tareas en curso»
- Función pura `task_rows(acts)` en `pages/tasks.py` → `[(icon, title, sub, page)]`; título = `label` o, si no hay
  (Bluetooth), el `tip` hasta el primer « · »; `sub` = `tip`. Pruebas: orden preservado, Bluetooth `("…", "BT",
  "BT · 80%", "bt")`, lista vacía → `[]`.
- GREEN: `TasksPage` con `PAGES={"tasks": page("_build_tasks")}`; `live()` recalcula `activities()` y redibuja las
  filas solo si cambian las claves; actualiza los subtítulos cada segundo; fila → `self.go(page)`.
- Prueba de que `tasks` está en `PAGE_CLASSES` y que todas las `page` de las filas existen.

### B7.4 RED/GREEN — clic en «+N»
- En `test_bubble_interaction.py`: `bubbles=[{page:"pomo"},{page:"bt"},{key:"more",page:"tasks"}]`, `_on_drag_end`
  con `_bubble_at()=2` → `page == "tasks"`. Debería pasar sin cambios (B6.9); si no, RED real y arreglo.
- `window.py`: `BUB_MAX + 1` widgets; `_set_bubbles` muestra el hijo «count».

### B7.5 — arnés, verificación y documentación
- `tests/fixtures/tasks_demo.py`: pomodoro + Bluetooth + grabación falsa + descarga falsa + temporizador.
- `python3 tests/harness.py pill bubble3 tasks --setup tests/fixtures/tasks_demo.py --out /tmp/opencode/isla-b7`
  (añadir «bubble3» al arnés), revisar PNG por píxeles (ancho +40 px) y sin tracebacks.
- `make check`, `make doctor`, `make check-x11`; `./install.sh` tras revisar `git status`.
- README/DOCUMENTACION: burbuja «+N», página y función nueva.

## Criterios de aceptación B7
1. Con ≥ 3 actividades fuera de la píldora y `bub_more` activa: 2 burbujas + «+N» con N correcto.
2. Con ≤ 2 o con la función desactivada: igual que hoy, sin «+N».
3. Hover «+N» → `Tareas en curso · N más`, sin expandir; clic → página «Tareas en curso».
4. La página lista todas las actividades en orden; clic en una fila abre su página.
5. «Más → Funciones» muestra «Burbuja de tareas» activa por defecto.
6. `make check` en verde (246 previas + nuevas), arnés sin tracebacks, documentación actualizada.

## Riesgos
- Isla 40 px más ancha con desbordamiento: en monitores pequeños puede acercarse a los iconos del panel; aceptado (D1).
- Recalcular `activities()` en `live()` de la página cada segundo: coste bajo (lógica pura), pero solo se
  reconstruyen widgets si cambian las claves, para no parpadear ni perder el hover.
- Recorte X11 sin compositor: `_shape_key` incluye `len(self.bubbles)` → verificar con `make check-x11`.

## Comandos de verificación B7
```bash
python3 -W error::ResourceWarning -m unittest tests.unit.test_bubbles tests.unit.test_tasks_page tests.unit.test_bubble_interaction -v
make check && make doctor
python3 tests/harness.py pill bubble3 tasks --setup tests/fixtures/tasks_demo.py --out /tmp/opencode/isla-b7
make check-x11
```

## Registro de decisiones B7
| Fecha | Decisión | Origen |
| --- | --- | --- |
| 2026-11-21 | «+N» como hueco extra (2 + 1) | Usuario (B7-D1) |
| 2026-11-21 | Solo con actividades ocultas | Usuario (B7-D2) |
| 2026-11-21 | Página con todas las actividades, filas clicables | Usuario (B7-D3) |
| 2026-11-21 | Interruptor `bub_more`, activo por defecto | Usuario (B7-D4) |
