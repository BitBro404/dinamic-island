"""Lista de funciones que dependen del escritorio, con su cadena de métodos (para --doctor).

Cada módulo de platform/ declara FEATURE = (título, [Method…]); aquí se juntan en orden de aparición.
"""
from . import appearance, audio, capture, clipboard, dnd, idle, lock, notify, record, screen, session

ALL = [notify.FEATURE, dnd.FEATURE, dnd.CENTER_FEATURE, lock.FEATURE, screen.FEATURE, idle.FEATURE,
       clipboard.FEATURE, capture.FEATURE, record.FEATURE, appearance.DARK_FEATURE, appearance.NIGHT_FEATURE,
       session.LOGOUT_FEATURE, session.INHIBIT_FEATURE, audio.VOLUME_FEATURE, audio.SOUND_FEATURE]
