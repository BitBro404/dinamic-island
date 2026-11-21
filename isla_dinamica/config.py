"""Preferencias guardadas en ~/.config/isla-dinamica/config.json: valores por defecto, validación y guardado (0600)."""
import json
import os
import re

from gi.repository import GLib


# ───────────────────────────── configuración, clima y pomodoro ─────────────────────────────
CONFIG_PATH = os.path.join(GLib.get_user_config_dir(), "isla-dinamica", "config.json")


DEFAULTS = {"city": None,
            "dock": {"edge": "top", "pos": 0.5},
            "features": {},       # función → activada (las que no aparecen están activadas)
            "collapsed": [],      # secciones plegadas (p. ej. «gh_merged»)
            "git_folders": ["~/Documentos/WM"],   # carpetas con repos que vigila «Proyectos»
            "pomodoro": {"work": 25, "short": 5, "long": 15, "every": 4, "auto": True},
            # sensor de presencia: minutos sin nadie, aviso previo (s), pausa (epoch) y horario (0 = lunes)
            "presence": {"minutes": 5, "warn": 30, "paused_until": 0, "start": "08:00", "end": "18:00",
                         "days": [0, 1, 2, 3, 4]}}


# funciones que vienen apagadas hasta que el usuario las encienda (el resto viene encendido)
FEATURE_DEFAULTS = {"presence": False}


def _hhmm(v):
    return isinstance(v, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v) is not None


def _num(v, lo, hi):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


_PRESENCE_OK = {"minutes": lambda v: _num(v, 1, 60) and v == int(v),
                "warn": lambda v: _num(v, 0, 120),
                "paused_until": lambda v: _num(v, 0, float("inf")),
                "start": _hhmm, "end": _hhmm,
                "days": lambda v: isinstance(v, list) and len(set(v)) == len(v) and
                all(isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 6 for d in v)}


class Config:
    """Preferencias guardadas en ~/.config/isla-dinamica/config.json."""

    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULTS))
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            self.data["city"] = loaded.get("city") or None
            dock = loaded.get("dock") or {}
            if dock.get("edge") in ("top", "bottom", "left", "right"):
                self.data["dock"] = {"edge": dock["edge"],
                                     "pos": min(1.0, max(0.0, float(dock.get("pos", 0.5))))}
            self.data["features"] = {k: v for k, v in (loaded.get("features") or {}).items()
                                     if isinstance(v, bool)}
            if isinstance(loaded.get("collapsed"), list):
                self.data["collapsed"] = [k for k in loaded["collapsed"] if isinstance(k, str)]
            if isinstance(loaded.get("git_folders"), list):
                self.data["git_folders"] = [str(p) for p in loaded["git_folders"] if p]
            self.data["pomodoro"].update({k: v for k, v in (loaded.get("pomodoro") or {}).items()
                                          if k in DEFAULTS["pomodoro"]})
            pres = loaded.get("presence") or {}
            self.data["presence"].update({k: v for k, v in pres.items() if k in _PRESENCE_OK and _PRESENCE_OK[k](v)})
        except (OSError, ValueError, AttributeError):
            pass

    def save(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        # 0600: solo el dueño puede leer sus preferencias (carpetas, horario…), sea cual sea la umask
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
