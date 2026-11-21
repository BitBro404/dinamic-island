# 2026-11-21 · Sensor de presencia con cámara

## Solicitud
Detectar con la webcam si hay alguien frente al equipo; si no hay nadie tras 5 min de inactividad, bloquear y apagar
la pantalla; integrarlo en la isla. Ampliación: usarlo solo según la hora del sistema (horario) y un botón rápido para
activar/desactivar.

## Resultado validado por el usuario
- Servicio `isla_dinamica/services/presence.py`: `in_schedule`, `presence_label`, `PresenceLogic` (pura), `IdleWatch`
  (swayidle propio, ext-idle-notify de labwc), `FaceDetector` (OpenCV Haar frontal + perfil, YuNet opcional si existe
  `~/.local/share/isla-dinamica/face_detection_yunet.onnx`), `Presence` (hilo 1 s, acciones Budgie `Lock()` + `wlopm`).
- Página `pages/presence.py` (función `presence`, desactivada por defecto vía `FEATURE_DEFAULTS`), casilla rápida
  «Presencia» en `pages/home.py`, cuenta atrás de máxima prioridad y burbuja en `window.py`.
- `services/privacy.py` ignora el propio PID (la isla no aparece usando la cámara).
- Config `presence` en `common.py` con validación (`_PRESENCE_OK`), horario por defecto L–V 08:00–18:00.

## Decisiones
Bloquear + apagar pantalla (no logout). Disparo: sin input y sin cara N min. Sin datos (llamada, cámara ocupada,
error, sin OpenCV) = no bloquear. `check_after = min(60, max(10, min*60 - aviso - 20))`. Al volver de apagado / pausa /
fuera de horario se cuenta desde cero. Horario cruza medianoche (la madrugada pertenece al día de inicio).

## Pruebas
`python3 -W error::ResourceWarning -m unittest discover -s tests/unit` → 49 OK (con OpenCV 4.10 instalado).
Detección real con la webcam: 3/3 en ~0,5 s. Capturas: `python3 tests/harness.py pill presence home --setup
tests/fixtures/presence_demo.py` (variable `PRESENCE_STATE`). Prueba manual del bloqueo hecha por el usuario.

## Limitaciones / pendientes
- Con música o vídeo sonando (Chrome inhibe la inactividad) el sensor no actúa.
- Tarea 9 sin hacer: mantener la pantalla encendida mientras te ve (el swayidle del sistema la apaga a los 300 s).
  Opción propuesta: reutilizar `org.gnome.SessionManager.Inhibit` como la casilla «Despierto».

Plan: `plan.md`.
