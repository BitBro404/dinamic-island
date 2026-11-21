"""Qué muestra la píldora cerrada: una sola cosa, la primera activa según su prioridad.

La decisión es una función pura (`pick_pill`) sobre un `PillState` sencillo, así se puede probar sin GTK.
Para añadir algo nuevo a la píldora (principio abierto/cerrado):
  1. una entrada en PILL_ORDER, en el lugar que le toque, con su condición;
  2. un método `_pill_<clave>` en la ventana que la dibuje (ver IslandWindow.refresh).
"""
from typing import NamedTuple


class PillState(NamedTuple):
    """Fotografía de lo que está pasando, en booleanos. `activities` son las claves de las actividades
    en curso que calcula `ui.bubbles.activities` (call, reminder, deploy, download, audio…)."""
    alert: bool = False             # alarma del temporizador sonando
    card_hold: bool = False         # el ratón está encima de una tarjeta de aviso
    hover: bool = False             # el panel está expandido
    presence_warning: bool = False  # cuenta atrás de la presencia antes de bloquear
    event: bool = False             # aviso puntual vigente (tarjeta o píldora)
    activities: frozenset = frozenset()
    playing: bool = False           # música sonando (MPRIS)
    pomodoro: bool = False
    recording: bool = False
    timer: bool = False


# (clave, condición) en orden de prioridad: gana la primera cuya condición se cumple.
PILL_ORDER = (
    ("alert", lambda s: s.alert),
    ("card_hold", lambda s: s.card_hold),
    ("expanded", lambda s: s.hover),
    ("presence", lambda s: s.presence_warning),
    ("event", lambda s: s.event),
    ("call", lambda s: "call" in s.activities),
    ("media", lambda s: s.playing),
    ("pomodoro", lambda s: s.pomodoro),
    ("recording", lambda s: s.recording),
    ("reminder", lambda s: "reminder" in s.activities),
    ("deploy", lambda s: "deploy" in s.activities),
    ("download", lambda s: "download" in s.activities),
    ("audio", lambda s: "audio" in s.activities),
    ("timer", lambda s: s.timer),
    ("idle", lambda s: True),
)


def pick_pill(state):
    """Clave de lo que debe mostrar la píldora para `state` (siempre devuelve algo: «idle» al final)."""
    return next(key for key, cond in PILL_ORDER if cond(state))
