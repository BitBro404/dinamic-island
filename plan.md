# Plan: Sensor de presencia con cámara → bloquear y apagar pantalla (integrado en la isla)

## Objetivo y resultado esperado
Que la isla dinámica detecte con la webcam si hay alguien frente al equipo. Si pasan **5 min sin teclado/ratón
y la cámara no ve a nadie**, la isla avisa con una cuenta atrás de 30 s y luego **bloquea la sesión y apaga la
pantalla**. Mientras la cámara te ve, no bloquea. Todo se ve y se controla desde la isla.

## Alcance
- Repositorios incluidos: `/home/luis/dinamic island` (único repo, rama `main`, limpio al empezar).
- Repositorios excluidos: ninguno más. No se toca la configuración del sistema (el `swayidle` de Budgie sigue igual).

## Contexto actual (verificado el 2026-11-21)
- Ubuntu 26.10, Budgie sobre **Wayland (labwc)**, Python 3.14, GTK 3 (PyGObject).
- Webcam UVC `USB2.0 HD UVC WebCam` en `/dev/video0` (índice 0), MJPEG/YUYV hasta 1280x720.
- `swayidle` del sistema ya corre: atenúa a 30 s (`BudgieScreenlock.Dim`), `wlopm --off *` a 300 s,
  `swaylock` antes de suspender y suspende a 900 s solo con batería.
- D-Bus `org.buddiesofbudgie.BudgieScreenlock /org/buddiesofbudgie/Screenlock`: `Lock()`, `Dim()`, `Undim()`, `OnBattery()`.
- Disponibles: `swayidle`, `wlopm`, `loginctl`, `ffmpeg`. **No** instalados: `python3-opencv`, `opencv-data`,
  numpy, pytest (hay candidatos en apt: `4.10.0+dfsg-9ubuntu1`).
- Estructura del proyecto: servicios sin UI en `isla_dinamica/services/*.py` (hilo + `GLib.idle_add`,
  callbacks `on_change`, `enabled`), páginas mixin en `isla_dinamica/pages/*.py` con `PAGES`, `feature()`, `tool()`,
  núcleo en `core.py` (`Core.changed`, `show_event`, `feature`), píldora en `window.py`
  (`refresh()` con prioridades y `_activities()` para burbujas). Config en `~/.config/isla-dinamica/config.json`
  (`common.py: DEFAULTS/Config`).
- `services/privacy.py: camera_users()` marca cualquier proceso con `/dev/video*` abierto → hoy la propia isla
  aparecería como «Python está usando la cámara».
- Pruebas actuales: solo el arnés de capturas `tests/harness.py` + `tests/fixtures/*.py`. No hay pruebas unitarias.

## Decisiones confirmadas (usuario, 2026-11-21)
1. Acción: **bloquear + apagar pantalla** (no cerrar sesión real, no suspender el equipo).
2. Disparo: **sin input y sin cara durante 5 min**. La cámara solo se usa tras ~1 min sin teclado/ratón.
   Si te ve, no hace nada.
3. Detección: **OpenCV desde apt** (`sudo apt install python3-opencv opencv-data`, lo ejecuta el usuario).
   Haar local; YuNet opcional si existe el modelo.
4. Isla: aviso con cuenta atrás, página de ajustes, indicador en la píldora y pausar desde la isla.
5. **Horario según la hora del sistema**: una franja diaria desde/hasta + días de la semana, configurable en la
   página. Por defecto **L–V 08:00–18:00**. Fuera de la franja el sensor no usa la cámara ni bloquea. La franja puede
   cruzar la medianoche (p. ej. 22:00–02:00: el tramo de madrugada pertenece al día en que empezó).
6. **Botón de acceso rápido «Presencia»** en la cuadrícula de ajustes rápidos de la página principal (junto a
   Wi‑Fi, No molestar…): el círculo enciende/apaga la función (igual que el interruptor de «Más», se guarda); el
   nombre «Presencia ›» abre la página; el texto inferior muestra el estado: «Vigilando», «Fuera de horario»,
   «En pausa», «Sin OpenCV» o «Apagado».

## Suposiciones y restricciones
- Se usa `swayidle` propio como subproceso para saber cuándo no hay input (ext-idle-notify de labwc):
  `swayidle -w timeout 60 'echo idle' resume 'echo active'`, leyendo líneas de stdout. **Suposición** a verificar en la
  tarea 3 (que labwc lo acepte junto al swayidle del sistema; ambos son clientes independientes del protocolo).
- La cámara se abre solo durante cada revisión (~1 s, cada 10 s mientras estás inactivo) y se libera. El LED parpadeará
  en esos momentos: es aceptable y además honesto.
- Si la cámara está ocupada por otra app (Meet, Teams…) o hay una llamada (`core.audio.call`), se considera
  **presente** (no bloquear).
- Si OpenCV no está instalado o la cámara falla, el sensor **no bloquea nunca** y la página lo dice
  («Instala python3-opencv opencv-data»). Nunca se bloquea por falta de datos.
- Bloqueo: `BudgieScreenlock.Lock()`; si falla, `loginctl lock-session`. Pantalla: `wlopm --off '*'`;
  al volver el input (línea `active`) → `wlopm --on '*'` si la apagamos nosotros.
- Función activable `presence` en «Más». Como usa la cámara, **queda desactivada por defecto** hasta que la enciendas
  (excepción explícita al «activado por defecto» del resto). Se puede cambiar si prefieres lo contrario.
- **Fuera de alcance** (posible mejora futura): impedir que el `swayidle` del sistema apague la pantalla a los 5 min
  mientras la cámara te ve leyendo. Inhibir el idle en Wayland/labwc desde GTK3 no está garantizado; se hará un
  intento acotado en la tarea 9 y, si no funciona, se documenta y se consulta.

## Contratos/dependencias entre módulos
`services/presence.py` expone:
```python
class PresenceLogic:              # pura, sin GTK ni cámara: se prueba con reloj falso
    def __init__(self, minutes=5, warn=30, check_after=60): ...
    def input_idle(self, now): ...      # llegó «idle» (sin input desde now - check_after)
    def input_active(self, now): ...    # llegó «active»
    def face(self, now, seen: bool, busy=False): ...   # resultado de una revisión de cámara
    def pause_until(self, ts): ...      # 0 = reanudar
    def step(self, now, scheduled=True) -> str
    # estado: "off"|"off_hours"|"paused"|"active"|"watching"|"present"|"warning"|"lock"|"locked"
    def seconds_left(self, now) -> float | None   # hasta el bloqueo, en "watching"/"warning"
    def needs_check(self, now) -> bool  # ¿toca revisar la cámara? (cada 10 s en watching/warning)
```
Horario (función pura, hora local del sistema):
```python
def in_schedule(dt: datetime, start="08:00", end="18:00", days=(0, 1, 2, 3, 4)) -> bool
# days: 0 = lunes … 6 = domingo (datetime.weekday()). start == end → todo el día.
```
| dt | start–end, days | Resultado |
|---|---|---|
| vie 17:59 | 08:00–18:00, L–V | True |
| vie 18:00 | 08:00–18:00, L–V | False (fin exclusivo) |
| sáb 10:00 | 08:00–18:00, L–V | False |
| lun 07:59 | 08:00–18:00, L–V | False |
| sáb 01:00 | 22:00–02:00, solo V | True (empezó el viernes) |
| vie 01:00 | 22:00–02:00, solo V | False (sería del jueves) |
| mar 03:00 | 00:00–00:00, L–V | True (todo el día) |

`PresenceLogic.step(now, scheduled=True)`: si `scheduled` es False → estado `"off_hours"`, no revisa cámara y
reinicia los contadores (al entrar en horario empieza de cero, no bloquea al instante por inactividad previa).

Reglas: `ausente_desde = max(inicio_inactividad, última_cara_vista)`; `warning` si
`now - ausente_desde >= minutes*60 - warn`; `lock` una sola vez al llegar a `minutes*60`; cualquier input o cara
reinicia; tras `lock` no vuelve a disparar hasta un `input_active`.

Ejemplos (minutes=5, warn=30, check_after=60):
| Secuencia | Resultado |
|---|---|
| idle en t=100 (inactivo desde 40), sin caras | `watching` a t=100; `warning` a t=310; `lock` a t=340 |
| idle t=100, cara en t=200, luego nada | `warning` a t=470, `lock` a t=500 |
| `lock` a t=340, sigue sin input | `step` devuelve `"locked"` estable, no vuelve a `lock` |
| cámara ocupada (`busy=True`) | cuenta como cara vista |
| pausa hasta t=1000 | `paused` hasta 1000 aunque no haya nadie |

`class Presence` (envoltorio con hilos, como `Privacy`): `Presence(config, on_change, on_lock, enabled, in_call)`,
atributos `state`, `last_seen`, `error`, métodos `pause(secs)`, `pause_tomorrow()`, `resume()`, `check_now()`.
`FaceDetector.detect() -> bool | None` (None = cámara ocupada/error), import perezoso de `cv2`.
`IdleWatch` → lanza swayidle y llama `on_idle(now)` / `on_active(now)`; `parse_line(str) -> "idle"|"active"|None`.

Config nueva en `DEFAULTS["presence"] = {"minutes": 5, "warn": 30, "paused_until": 0, "start": "08:00",
"end": "18:00", "days": [0, 1, 2, 3, 4]}` (fusionada en `Config.__init__` como `pomodoro`, filtrando claves y tipos:
`start`/`end` deben ser `HH:MM` válidas; `days` lista de enteros 0–6 sin repetir; si algo es inválido se usa el
valor por defecto). Encendido/apagado = `features["presence"]` (lo que usan «Más» y el botón rápido).

## Archivos o módulos a inspeccionar/modificar
- Nuevo: `isla_dinamica/services/presence.py`, `isla_dinamica/pages/presence.py`,
  `tests/unit/test_presence_logic.py`, `tests/unit/test_idle_parse.py`, `tests/unit/test_privacy_self.py`,
  `tests/unit/test_config_presence.py`, `tests/unit/test_detector.py`, `tests/fixtures/presence_demo.py`.
- Modificar: `services/__init__.py`, `pages/__init__.py`, `common.py` (DEFAULTS/Config), `core.py` (crear servicio,
  `_on_presence_lock`, avisos), `window.py` (rama `warning` de alta prioridad en `refresh()`, indicador/burbuja en
  `_activities()`), `services/privacy.py` (excluir el propio PID), `pages/home.py` (casilla rápida «Presencia»:
  `Tile` nuevo en la cuadrícula y su `set(...)` en el relleno), `pages/more.py` solo si hace falta para el `tool()`.
- Nuevo test: `tests/unit/test_schedule.py`.

## Criterios de aceptación
1. Con la función activada y OpenCV instalado: sin tocar nada y fuera de cámara, a los ~4:30 sin input la píldora
   muestra «Nadie frente a la pantalla · bloqueando en 30 s» con cuenta atrás; a los 5:00 se bloquea y se apaga la pantalla.
2. Mover el ratón durante la cuenta atrás la cancela; al volver tras el bloqueo la pantalla se enciende.
3. Sentado frente a la cámara sin tocar nada durante 6 min: **no** bloquea la isla (el swayidle del sistema puede
   seguir apagando la pantalla, ver restricción).
4. Con Meet/otra app usando la cámara o en llamada: no bloquea.
5. Página «Presencia»: interruptor, minutos (1–60), estado actual, «visto hace N s», pausar 1 h / hasta mañana /
   reanudar, «Probar ahora». La pausa «hasta mañana» sobrevive a reiniciar la isla.
6. Indicador en la píldora (burbuja con ojo) mientras el sensor está vigilando; la isla **no** aparece como
   «Python está usando la cámara» en los puntos de privacidad.
7. Sin OpenCV: la página indica cómo instalarlo y nunca bloquea.
8. Horario: fuera de L–V 08:00–18:00 (por defecto) la cámara no se abre y no bloquea; la página permite cambiar
   desde/hasta y días, y se guarda. Al entrar en horario empieza a contar desde cero.
9. Botón rápido «Presencia» en la página principal: un toque enciende/apaga (se refleja en «Más» y al revés),
   «Presencia ›» abre la página, el subtítulo muestra el estado. Con la cuadrícula a 9–10 casillas pasa a 5 columnas
   sin descuadrarse.
10. Todas las pruebas unitarias pasan; capturas del arnés revisadas.

## Estrategia de pruebas
- Nuevas pruebas unitarias con `unittest` de la stdlib (no hay pytest):
  `python3 -m unittest discover -s tests/unit -v`.
- La lógica (`PresenceLogic`) se prueba con reloj inyectado: sin cámara, sin GTK, sin esperar 5 min.
- `FaceDetector` se prueba con `skipUnless(cv2)`: con una imagen sintética sin cara → `False`; cámara ocupada /
  dispositivo inexistente → `None`. Si OpenCV no está instalado se reportará como **omitida**, no como pasada.
- UI con el arnés de capturas: `python3 tests/harness.py presence pill --setup tests/fixtures/presence_demo.py`.
- Prueba manual real (usuario) con `minutes=1` para no esperar 5 min.

## Tareas
- [x] **0. Prerrequisito (usuario):** `sudo apt install python3-opencv opencv-data` y confirmar que existe
  `/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml`.
  - Dependencias: ninguna; las tareas 1–4 y 6–8 no lo necesitan.
- [x] **1. Lógica de presencia (`PresenceLogic`)**
  - Repositorio: este. Archivos: `services/presence.py`, `tests/unit/test_presence_logic.py`.
  - RED: pruebas de la tabla de ejemplos (watching → warning → lock, cara reinicia, input reinicia, lock una vez,
    busy = presente, pausa, `needs_check` cada 10 s, `seconds_left`). Fallan por `ImportError`/aserción.
  - GREEN: clase pura mínima.
  - Refactor: nombres, constantes `CHECK_EVERY = 10`; repetir pruebas.
- [x] **1b. Horario (`in_schedule`) y estado `off_hours`**
  - Archivos: `services/presence.py`, `tests/unit/test_schedule.py`, `tests/unit/test_presence_logic.py`.
  - RED: la tabla de horario (incluye fin exclusivo, fin de semana, cruce de medianoche, start == end);
    `step(now, scheduled=False)` → `"off_hours"`, `needs_check` False, y al volver `scheduled=True` con input
    inactivo desde hace 10 min no pasa a `warning` de inmediato (empieza de cero).
  - GREEN: función pura + rama en `step`.
- [x] **2. Config `presence`**
  - Archivos: `common.py`, `tests/unit/test_config_presence.py` (apunta `CONFIG_PATH` a un archivo temporal).
  - RED: cargar config sin `presence` → valores por defecto (incluye L–V 08:00–18:00); con `minutes: "x"`,
    `start: "25:00"`, `days: [9]` o claves extra → se ignoran/se usa el defecto; `paused_until` se conserva.
  - GREEN: `DEFAULTS["presence"]` + fusión en `Config.__init__`.
- [x] **3. `IdleWatch` (swayidle propio)**
  - Archivos: `services/presence.py`, `tests/unit/test_idle_parse.py`.
  - RED: `parse_line("idle\n") == "idle"`, `"active"`, basura → `None`; el comando construido incluye
    `timeout 60 'echo idle' resume 'echo active'`.
  - GREEN: parser + constructor del comando + hilo lector (el hilo no se prueba unitariamente).
  - Verificación manual: lanzar el comando 70 s sin tocar nada y ver `idle`, mover ratón y ver `active`.
- [x] **4. Excluir la propia isla de los puntos de privacidad**
  - Archivos: `services/privacy.py`, `tests/unit/test_privacy_self.py`.
  - RED: con un `/proc` falso (directorio temporal con `fd` → `/dev/video0` para `os.getpid()` y otro PID),
    `camera_users()` no incluye el propio proceso. Requiere parametrizar la raíz de `/proc` (`proc="/proc"`).
  - GREEN: saltar `pid == os.getpid()`.
- [x] **5. `FaceDetector`** (necesita tarea 0 para la prueba real)
  - Archivos: `services/presence.py`, `tests/unit/test_detector.py`.
  - RED: imagen gris sintética → `False`; dispositivo inexistente (`/dev/video99`) → `None`; sin `cv2` →
    `available() == False` y `error` con el texto de instalación.
  - GREEN: abrir `cv2.VideoCapture(index, cv2.CAP_V4L2)` a 320x240, descartar 3 fotogramas (autoexposición),
    Haar frontal + perfil (y YuNet si existe `~/.local/share/isla-dinamica/face_detection_yunet.onnx`), liberar siempre.
- [x] **6. Servicio `Presence` + conexión en `core.py`**
  - Archivos: `services/presence.py`, `services/__init__.py`, `core.py`.
  - RED: prueba unitaria de `Presence` con detector, idle y reloj falsos (sin hilos: método `_tick(now)` público
    para pruebas) → llama `on_lock` una vez y ejecuta acciones inyectadas (`lock`, `screen_off`); `in_call()` → no bloquea;
    `enabled()=False` → `off` y no abre la cámara; fecha/hora inyectada fuera de horario → `off_hours` y el
    detector falso no se llama nunca.
  - GREEN: hilo cada 1 s que llama `logic.step`, revisa cámara si `needs_check`, ejecuta `Lock()` + `wlopm --off`
    y `wlopm --on` al volver input. En `core.py`: `self.presence = Presence(...)` y `changed("presence")`.
- [x] **7. Página «Presencia» y acceso en «Más»**
  - Archivos: `pages/presence.py`, `pages/__init__.py`.
  - Contenido: `feature("presence", "Presencia (cámara)", "Bloquea y apaga la pantalla si no hay nadie …")`,
    `tool("eye-…-symbolic", "Presencia", …, "presence", feature="presence")`, estado, «visto hace N s», minutos,
    horario (desde/hasta con dos `SpinButton` hora:minuto o `Gtk.Entry` HH:MM validada, y 7 botones-chip L M X J V S D),
    botones pausar 1 h / hasta mañana / reanudar / probar ahora, aviso si falta OpenCV.
- [x] **7b. Botón rápido en la página principal**
  - Archivos: `pages/home.py`.
  - Cambio: `self.t_presence = Tile(<icono ojo>, "Presencia", lambda: c.set_feature("presence", not c.feature("presence")),
    lambda: self.go("presence"))`, añadido a `tiles` (siempre visible); en el relleno
    `self.t_presence.set(on, texto_estado)` con: Apagado / Vigilando / Te ve / Fuera de horario / En pausa / Sin OpenCV.
    Añadir `"presence"` y `"features"` a las claves vigiladas del relleno de inicio si no lo están.
  - Prueba: función pura `presence_label(state, enabled, available) -> str` en `services/presence.py` con prueba
    unitaria (RED/GREEN); la casilla se verifica con captura `home` del arnés (encendida y apagada).
  - Verificación: arnés de capturas `presence` con `tests/fixtures/presence_demo.py` (estados falsos).
- [x] **8. Píldora: cuenta atrás e indicador**
  - Archivos: `window.py`.
  - Cuenta atrás: rama de máxima prioridad (antes de «call») cuando `presence.state == "warning"`:
    icono ojo naranja, «Nadie frente a la pantalla», derecha «0:25». Al pasar el ratón abre la página «Presencia».
  - Indicador: entrada `presence` en `_activities()` (burbuja ojo, gris/azul) mientras el estado es `watching`/`present`.
  - Verificación: capturas `pill` y `bubble` con la fixture en `warning` y en `watching`.
- [ ] **9. (Acotada, PENDIENTE de decisión del usuario) Mantener la pantalla encendida mientras te ve**
  - Intento: `Gtk.Application.inhibit(None, Gtk.ApplicationInhibitFlags.IDLE, …)` en estado `present` y comprobar
    si el swayidle del sistema deja de apagar a los 300 s. Si no funciona → documentarlo y **consultar** (no se cambia
    la config del sistema sin permiso).
- [x] **10. Verificación final (automática + manual del usuario)**: todas las pruebas, `python3 -m compileall -q isla_dinamica`, capturas, y guía de
  prueba manual para el usuario (con minutos = 1). `install.sh` solo si el usuario lo pide.

## Riesgos y casos límite
- **Falsos negativos** (no detecta tu cara con poca luz, de perfil o mirando al móvil) → bloqueo inesperado.
  Mitigación: cuenta atrás de 30 s, perfil + frontal, revisar cada 10 s (basta 1 acierto en 5 min), YuNet opcional.
- **Falsos positivos** (foto/póster detectado como cara) → no bloquea; el swayidle del sistema sigue como respaldo.
- Cámara ocupada por otra app → se trata como presente.
- El LED de la cámara parpadeará cada 10 s mientras estás inactivo.
- labwc podría no aceptar un segundo cliente de idle-notify → se verifica en la tarea 3; alternativa: leer
  `IdleHint` de logind (hoy está en `no` y swayidle no lo marca, así que sería peor).
- Tras suspender/reanudar, `swayidle` puede emitir `active`: se maneja como input normal.
- Multi-monitor: `wlopm --off '*'` apaga todas; correcto.
- Privacidad: ninguna imagen se guarda ni sale del equipo; se procesa en memoria y se descarta.

## Pendientes/preguntas abiertas
- ¿Desactivada por defecto (propuesta) o activada al instalar? (Con el botón rápido, encenderla es un toque.)
- ¿Incluir YuNet? Requiere descargar un `.onnx` (~230 KB) de opencv_zoo: pediría permiso antes de descargarlo.
  Por defecto solo Haar (sin descargas).

## Comandos de verificación
```bash
python3 -m unittest discover -s tests/unit -v
python3 -m compileall -q isla_dinamica
python3 tests/harness.py home presence pill bubble --setup tests/fixtures/presence_demo.py
swayidle -w timeout 60 'echo idle' resume 'echo active'   # manual, tarea 3
```

## Estado y siguiente paso
- Estado (2026-11-21): **validado por el usuario y en commit**. OpenCV 4.10 instalado: 49 pruebas OK sin omisiones;
  detección real 3/3. Tarea 9 queda pendiente (opcional). Resumen: `.ai/summaries/2026-11-21-sensor-presencia.md`.
- Archivos nuevos: `isla_dinamica/services/presence.py` (in_schedule, presence_label, PresenceLogic, IdleWatch,
  FaceDetector, Presence), `isla_dinamica/pages/presence.py`, `tests/unit/*.py` (8 archivos), `tests/fixtures/presence_demo.py`.
- Modificados: `common.py` (DEFAULTS["presence"], FEATURE_DEFAULTS, validación `_PRESENCE_OK`), `core.py`
  (crea `self.presence`; `feature()` usa FEATURE_DEFAULTS), `services/__init__.py`, `pages/__init__.py`,
  `pages/home.py` (casilla «Presencia»), `window.py` (cuenta atrás + burbuja), `services/privacy.py`
  (ignora el propio PID, parámetro `proc`, `scandir` cerrado).
- Pruebas: `python3 -W error::ResourceWarning -m unittest discover -s tests/unit` → 49 ok, 3 omitidas
  (las de OpenCV real: no está instalado). `compileall` ok. Capturas del arnés revisadas: píldora en aviso,
  burbuja «vigilando», página (aviso, vigilando, sin OpenCV), casilla rápida en inicio.
- Decisiones tomadas en ejecución:
  - `check_after` (umbral de swayidle) = `min(60, max(10, minutos*60 - aviso - 20))`, para que con 1 min haya revisiones
    y aviso; IdleWatch se reinicia si cambia.
  - Al estar apagado / sin OpenCV / en pausa / fuera de horario, al volver se cuenta desde cero.
  - Resultado `None` del detector (error) o cámara ocupada o llamada = «presente».
- **Sin verificar**: (a) que swayidle propio emita `idle` en labwc — en 2 min de prueba no emitió ninguno; durante la
  prueba sonaba música en Chrome, que inhibe la inactividad (comportamiento esperado: con vídeo/música sonando el sensor
  no actúa, igual que el apagado de pantalla del sistema). (b) Detección real con la cámara (falta OpenCV).
  (c) Bloqueo Budgie + `wlopm` reales.
- Siguiente paso: usuario instala OpenCV, ejecuta `./install.sh` (o `python3 isla.py`), activa «Presencia» y prueba con
  minutos = 1 sin música sonando. Decidir tarea 9.

## Registro de decisiones
- 2026-11-21: bloquear + apagar pantalla (no logout). Motivo: logout cierra apps y se pierde trabajo.
- 2026-11-21: disparo = sin input y sin cara 5 min; cámara solo tras 1 min de inactividad (menos uso del LED/CPU).
- 2026-11-21: OpenCV de apt, Haar local; sin red.
- 2026-11-21: isla con cuenta atrás, página, indicador y pausa.
- 2026-11-21: horario por hora del sistema = franja diaria + días, por defecto L–V 08:00–18:00, cruza medianoche.
- 2026-11-21: botón rápido «Presencia» en ajustes rápidos de la página principal = encender/apagar la función.
- 2026-11-21 (propuesta, pendiente de confirmar): función `presence` desactivada por defecto; ante cualquier error
  de cámara/OpenCV, nunca bloquear.
