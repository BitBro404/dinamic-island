# Plan: identidad facial en el sensor de presencia («solo yo») con calibración diaria

Plan anterior (GitHub/git/servidores/dev, ya terminado) archivado en
`.ai/plans/2026-11-22-github-git-servidores-dev.md`.

## Objetivo y resultado esperado
Que el sensor de presencia distinga **al usuario** de **otra persona**: si ve una cara que no coincide con la
plantilla del usuario, esa cara **no** cuenta como «hay alguien» y puede llegar a bloquear; si no puede saber
quién hay (duda, cámara ocupada, error, modelos ausentes), sigue la regla actual de **no bloquear a ciegas**.
Además, una **muestra aleatoria al día** y las **lecturas dudosas** muestran la foto en memoria y preguntan
«¿eras tú?»: al confirmar se añade ese embedding a una galería pequeña, que mejora el reconocimiento con
distintas luces y ángulos. Nunca se guarda la foto.

## Alcance
- Repositorios incluidos: único repo `/home/luis/dinamic island` (rama `main`, `main...origin/main`, sin cambios).
  No hay repos anidados.
- Repositorios excluidos: ninguno. No se tocan otros repos ni la cámara/config de otros usuarios.
- Fuera: login/logout, cambiar el temporizador de inactividad del compositor, detección de vida (antifoto),
  reconocimiento en vídeo o fotos archivadas, subir la plantilla a ningún servidor, ajustar el umbral en la UI.

## Contexto actual
- OpenCV `4.10.0` instalado con `cv2.FaceDetectorYN` y `cv2.FaceRecognizerSF` (contrib). No hacen falta
  `dlib`, `face_recognition` ni `onnxruntime`. Modelos **no** descargados.
- Modelos de OpenCV Zoo (Apache-2.0): `face_recognition_sface_2021dec.onnx` (38 696 353 B, sha256
  `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`) y
  `face_detection_yunet_2023mar.onnx` (232 589 B, sha256
  `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`). Umbral de referencia SFace:
  similitud cosine ≥ `0.363` (`sface.py` del zoo). YuNet da 5 puntos clave para alinear; hoy se usa Haar
  porque YuNet no está presente.
- `services/presence.py`: `FaceDetector.detect()` → `True/False/None`; `PresenceLogic.face(now, seen, busy)`
  guarda `seen = bool(seen or busy)`; `Presence._tick()` llama a la cámara cada 10 s y decide. `None` (llamada,
  cámara ocupada o error) se trata como «presente»: nunca bloquea a ciegas.
- `install.sh` sustituye solo `$DEST/isla_dinamica`, no `$DEST/models`: los modelos sobreviven a una reinstalación.
- Config real del usuario: `features.presence = true`, `minutes = 15`, `warn = 30`, L–V 08:00–18:00.
- Sin operaciones Git durante el análisis: `git status` limpio en `main` antes de escribir el plan.

## Decisiones confirmadas (usuario, 2026-11-22)
- **D1** Cara detectada y no reconocida → cuenta como ausente (puede bloquear). Sin datos, duda, cámara
  ocupada, llamada, error o modelos no descargados → **no bloquea** (fail-open, como hoy).
- **D2** Registro y borrado mediante botones en la página «Presencia».
- **D3** Descarga automática de los modelos al registrar, verificando tamaño y hash.
- **D4** La foto de la muestra se usa **solo en memoria**: se muestra al preguntar y se descarta al responder.
  Si confirmas «sí», se guarda únicamente el embedding.
- **D5** La pregunta «¿eras tú?» aparece por una **muestra aleatoria al día** (con actividad reciente) y
  también cuando el parecido caiga en **zona dudosa**.
- **D6** Al confirmar «sí» se **añade el embedding a una galería**: la plantilla original queda como ancla y
  las nuevas muestras rotan con límite. Borrar la plantilla restaura el modo actual.

## Suposiciones y restricciones
- **A1** Sin plantilla registrada, el comportamiento es el actual (cualquier cara cuenta como presente).
- **A2** Solo se guardan vectores de rasgos (embeddings) localmente: **nunca imágenes ni capturas**. Archivo
  `0600` dentro de carpeta `0700`; se borra con el botón. No se versiona en git.
- **A3** La única red que se usa es la descarga de los modelos desde OpenCV Zoo; ningún dato de la cámara sale
  del equipo.
- **A4** Bandas de decisión centralizadas y probadas: `score ≥ 0.363` → «yo»; `score < 0.25` → «otra persona»;
  entre medias → duda con pregunta. Sin control de estos valores en la UI.
- **A5** Una sola apertura de cámara por revisión: se capturan varias muestras y se compara la mejor contra todas
  las plantillas de la galería. Si hay varias caras y alguna coincide con la galería, cuenta como «yo».
- **A6** No se hace commit, push ni reinstalación sin autorización explícita. `./install.sh` reinicia la isla.
- **A7** La pregunta solo aparece con input en los últimos ~60 s, dentro de horario y sin pausa; se espera
  respuesta ≤ 20 s. Mientras está pendiente, esa revisión cuenta como duda (no bloquea) y no consume la cuenta
  atrás; sin respuesta se descarta sin guardar nada.
- **A8** La hora de la muestra diaria se guarda como metadato del archivo de la galería (JSON), sin añadir
  claves a `config.json`.
- **A9** Galería: 1 plantilla ancla + hasta 5 muestras rotativas; al llenarse se sustituye la más antigua.
  Rechazar, dejar caducar o no responder nunca modifica la galería.

## Contratos/dependencias entre módulos
- `services/identity.py` (nuevo):
  - `MODELS`, `MODEL_DIR`, `ensure_models(fetch=..., dir=...)` → descarga/verifica YuNet y SFace.
  - `Gallery` → `templates` (ancla + rotativas), `add(embedding, meta)`, `best(features)` → `(score, coincide)`,
    `load/save` (`0700/0600`, sin imágenes) y `next_sample_at`.
  - `IdentityVerifier.verify(frame, faces, gallery)` → `"me" | "other" | "unknown"` según las bandas de A4;
    `unknown` también si no hay modelo, cara o datos válidos.
  - `decide(identity, detected, busy, enrolled)` → `(seen, busy)` para `PresenceLogic.face`.
- `FaceDetector` gana `capture()` → `(frame, faces)`; `detect()` conserva su firma para no romper llamadores
  ni pruebas. Un `mutex` evita abrir la cámara dos veces mientras se registra o se calibra.
- `Presence(..., identity=None)` acepta el verificador inyectado. `pending_prompt` guarda la foto **en memoria**
  mientras se espera; `Presence.answer(yes)` (llamado por la UI) añade o descarta la muestra y limpia el estado.
  `identity=None` o sin plantilla → modo actual.

| Situación | `seen` | `busy` | Efecto |
|---|---|---|---|
| Sin plantilla | `bool(detect())` | `detect() is None` | Igual que hoy |
| Cara con score ≥ `0.363` | `True` | `False` | Reinicia la cuenta; no bloquea |
| Cara con score < `0.25` | `False` | `False` | No reinicia; bloquea al cumplirse el plazo |
| Cara con score en `[0.25, 0.363)` | – | `True` | Duda: pregunta «¿eras tú?»; no bloquea |
| Sin cara con plantilla | `False` | `False` | Ausencia real: bloquea al cumplirse el plazo |
| Muestra diaria pendiente (foto en memoria) | – | `True` | Pregunta; no bloquea |
| Respuesta «sí» | – | – | Añade embedding a la galería (ancla intacta, tope 5) |
| Respuesta «no», caducidad o sin respuesta | – | – | Descarta la foto; la galería no cambia |
| Llamada, cámara ocupada, error, sin OpenCV o sin modelos | – | `True` | No bloquea |

## Archivos o módulos a inspeccionar/modificar
- Nuevo: `isla_dinamica/services/identity.py` (modelos, galería, verificador, bandas y programación).
- Modificar: `isla_dinamica/services/presence.py`, `isla_dinamica/pages/presence.py`, `README.md`.
- No está previsto modificar `isla_dinamica/config.py` (la hora de muestra vive con la galería).
- Pruebas nuevas: `tests/unit/test_identity.py`, `tests/unit/test_presence_identity.py`,
  `tests/unit/test_presence_identity_page.py`, `tests/unit/test_detector.py` (ampliable).
- Opcional: `tests/fixtures/presence_identity_demo.py` para capturas del arnés.
- Documentación: `.ai/summaries/`, `INDEX.md`, `PROJECT_MEMORY.md` y `HANDOFF.md` actualizados; la aceptación
  queda condicionada a la validación manual C8–C11.

## Criterios de aceptación
- **C1** Con plantilla y el usuario delante, no bloquea aunque pasen 15 min sin teclado/ratón.
- **C2** Con otra persona delante y sin input, bloquea al cumplirse el plazo y apaga la pantalla; si el bloqueo
  falla, la pantalla sigue encendida (regla S2).
- **C3** Duda, sin datos, cámara ocupada, en llamada, sin OpenCV o sin modelos → nunca bloquea.
- **C4** Sin plantilla → comportamiento idéntico al actual (prueba de regresión).
- **C5** «Registrar mi rostro» guarda la plantilla con `0700/0600`, sin imágenes; «Borrar mi rostro» la elimina
  y devuelve al modo actual.
- **C6** Los modelos se descargan una vez, se validan por tamaño/hash y, si falla, se muestra el error sin
  bloquear.
- **C7** `make check` pasa (se reportará el número real de pruebas ejecutadas).
- **C8** Validación manual del usuario con cámara real: registrar, no bloquearse con él, bloquear con otra
  persona y borrar la plantilla.
- **C9** Como máximo una muestra al día, a hora aleatoria, solo con actividad reciente y dentro de horario;
  la foto se muestra y se descarta, nunca se escribe en disco.
- **C10** «Sí» añade un embedding (ancla intacta, tope 5 rotativas); «no» o caducar no cambia la galería y
  no bloquea; se puede borrar toda la galería.
- **C11** Una lectura dudosa muestra la pregunta; la galería queda protegida frente a confirmaciones
  accidentales (solo tras actividad reciente, con caducidad y borrado disponible).

## Estrategia de pruebas
- Unitarias puras con dobles (sin cámara ni red): bandas de umbral, mejor muestra, varias caras, galería con
  ancla/rotación, carga corrupta, persistencia `0700/0600` sin imágenes, `fetch` falso para la descarga.
- Integración de servicio con detector y verificador falsos: cuenta atrás, bloqueo, fail-open, regresión y
  `pending_prompt`/`answer`.
- Calibración con reloj falso: una muestra al día, solo con input reciente, respeto de horario/pausa,
  caducidad de 20 s sin guardar, respuesta «sí» frente a «no» (sin envenenar la galería).
- TDD estricto: cada tarea se ve en ROJO por el motivo correcto, GREEN mínimo y REFACTOR con la suite en verde.
- Visual: arnés con fixture para la página «Presencia»; la prueba real con cámara la hace el usuario.
- No se debilitan ni se saltan pruebas existentes.

## Tareas
- [x] **T1** `ensure_models` en `services/identity.py` (descarga, hash y permisos).
  - RED: `fetch` que devuelve tamaño o hash malos → error y ningún archivo; correcto → archivos `0600` en
    carpeta `0700`, segunda llamada no descarga.
  - GREEN: `urllib.request` con timeout, `hashlib.sha256`, `os.open`/`fchmod`.
  - REFACTOR: inyectar `fetch` y `dir`; verificar.
- [x] **T2** `Gallery` + `IdentityVerifier` (SFace/YuNet, bandas de umbral y votación).
  - RED: rasgos simulados → `me` / `other` / `unknown` según `0.363` y `0.25`; varias caras con una coincidente
    → `me`; ancla intacta y rotación a 5; plantilla o JSON corrupto → sin plantilla; guardado sin imágenes.
  - GREEN: `alignCrop`/`feature`/`match`, mejor cosine de las muestras, galería persistida en JSON.
  - REFACTOR: separar OpenCV de la lógica pura; verificar.
  - Dependencias: T1.
- [x] **T3** `decide()` puro y estados de interfaz.
  - RED: tabla completa del contrato, incluida la duda → `busy=True`; etiquetas «Otra persona» y
    «¿Eras tú?».
  - GREEN: función pura + entradas en `_LABELS`/`_ACCENT` de `presence.py`.
  - REFACTOR: verificar.
  - Dependencias: T2.
- [x] **T4** Integración en `Presence`.
  - RED: con verificador falso, `other` → bloqueo tras el plazo; `me` → sin bloqueo; `unknown` → sin bloqueo
    y `pending_prompt`; sin plantilla → regresión exacta; `answer(True)` añade muestra, `answer(False)` no;
    `enrolling` → no abre la cámara.
  - GREEN: parámetro `identity`, `capture()`, `mutex`, mapeo en `_tick`, `answer()`.
  - REFACTOR: `detect()` sigue igual; verificar.
  - Dependencias: T1–T3.
- [x] **T5** Interfaz: registro, borrado y pregunta «¿eras tú?».
  - RED: prueba de servicio y captura del arnés con «Registrar mi rostro», «Borrar mi rostro» y la tarjeta
    de pregunta (foto en memoria, «Sí» / «No»).
  - GREEN: botones en `pages/presence.py`, texto de privacidad y estados; `answer()` conectado a los botones.
  - REFACTOR: verificar.
  - Dependencias: T2, T4.
- [x] **T6** Programación de la muestra diaria y caducidad del prompt.
  - RED: reloj falso → una muestra al día a hora aleatoria, solo con input reciente, respeta pausa/horario,
    caducidad de 20 s sin guardar ni bloquear, «no» no modifica la galería.
  - GREEN: `next_sample_at` en la galería y gestión de `pending_prompt` en `Presence`.
  - REFACTOR: verificar.
  - Dependencias: T4, T5.
- [x] **T7** Cierre y documentación.
  - README (qué se guarda, modelos, privacidad, limitación de foto/no liveness, calibración diaria),
    `make check`, `./install.sh` **solo con aprobación** y validación real del usuario (C8–C11: forzar una
    muestra/duda, responder «sí» y «no»).
  - Dependencias: T1–T6.

## Riesgos y casos límite
- **Falso negativo** (el usuario delante pero no reconocido: luz, gafas, mascarilla, ángulo): varias muestras,
  galería multi-luz, banda de duda con pregunta, aviso de 30 s cancelable y pausa rápida siempre disponibles.
- **Falso positivo** (foto o pantalla, o otra persona parecida): no hay detección de vida; la galería amplía
  los rasgos aceptados, por lo que se documenta que no es control de acceso de alta seguridad.
- **Envenenamiento**: si otra persona pulsa «sí», se añadiría una plantilla errónea. Mitigación: solo se
  pregunta tras actividad reciente, respuesta con caducidad y borrado siempre disponible.
- **Molestia**: una muestra al día como máximo, dentro de horario, respetando la pausa; la duda también pregunta,
  así que se limitó con el plazo de 20 s.
- **Deriva de la galería**: plantilla ancla inmutable + 5 rotativas; al borrar se vuelve al modo actual.
- **Privacidad**: la foto vive solo en memoria; en disco solo un vector y metadatos, con `0700/0600`, sin git.
- **Sin red**: la descarga falla → error visible y fail-open; se puede reintentar al volver a registrar.
- **Cámara ocupada por la isla al registrar o calibrar**: flags `enrolling` y `pending_prompt` impiden dos
  aperturas simultáneas.
- **Varias personas en cuadro**: si una coincide con la galería, gana «yo» para no bloquear al usuario.
- **Horario/pausa**: las reglas actuales siguen mandando; fuera de horario no se bloquea ni se pregunta.
- **`./install.sh`**: no borra `models/`, pero sí reinicia la isla; avisar antes de ejecutarlo.

## Pendientes/preguntas abiertas
- Ninguna de alcance después de D1–D6. Al aprobar se pueden ajustar los números propuestos (`0.25`, `0.363`,
  5 rotativas, 20 s de espera); son constantes centralizadas y probadas.
- Plan aprobado el 2026-11-22; la aprobación no cubre `./install.sh` ni commits.

## Comandos de verificación
```bash
python3 -W error::ResourceWarning -m unittest discover -s tests/unit
make check
python3 tests/harness.py presence home --wait 6 --setup tests/fixtures/presence_identity_demo.py
./install.sh   # solo con aprobación; reinicia la isla
```

## Estado y siguiente paso
- 2026-11-22: plan aprobado; T1–T6 ejecutados con TDD (rojo verificado en cada change) y `make check` en
  verde: **456 pruebas**. Arnés visual ejecutado con foto sintética: `/tmp/opencode/presence-identity/presence.png`.
  Se corrigieron dos fallos detectados en validación: con plantilla y **sin cara** el sistema trataba la
  ausencia como duda y nunca bloqueaba; y los hashes publicados de los modelos estaban mal escritos (63
  caracteres), por lo que la descarga real siempre fallaba. Añadida prueba que exige SHA-256 de 64 hex.
- `./install.sh` **ejecutado con autorización**: versión nueva activa y reiniciada. Modelos descargados y
  verificados en `~/.local/share/isla-dinamica/models` (`0600` en carpeta `0700`); SFace y YuNet cargan
  correctamente con el código instalado.
- T7 cerrado: `README.md` y `docs/DOCUMENTACION.md` documentan identidad, privacidad y limitaciones;
  `gallery.json` ignorado por git; resumen, índice, memoria y handoff actualizados; todo preparado en un único
  commit firmado (sin push).
- C1–C7 cubiertos por pruebas y verificación técnica. **Pendiente de validación real (C8–C11)**: registrar,
  comprobar que no bloquea con el usuario, que bloquea con otra persona, forzar duda/muestra diaria, responder
  «sí» y «no», y borrar la galería. Hasta entonces no se marca como aceptado.

## Registro de decisiones
- 2026-11-22 **D1** desconocido → bloquea; duda/sin datos → no bloquea.
- 2026-11-22 **D2** registro y borrado desde la página «Presencia».
- 2026-11-22 **D3** descarga automática verificada de modelos al registrar.
- 2026-11-22 **D4** foto solo en memoria; se guarda únicamente el embedding confirmado.
- 2026-11-22 **D5** pregunta por muestra diaria aleatoria y por lectura dudosa.
- 2026-11-22 **D6** confirmar añade embedding a galería (ancla + 5 rotativas); borrar restaura modo actual.
- 2026-11-22 **A1** sin plantilla, comportamiento actual (suposición no contradicha).
