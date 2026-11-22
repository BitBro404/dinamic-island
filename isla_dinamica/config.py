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
            "github_account": None,               # cuenta de gh que usa la isla (None = la activa de gh)
            "account_folders": {},                # cuenta de gh → proyectos (carpetas) que sigue esa cuenta
            "servers_recent": [],                 # servidores detenidos: carpeta, comando y PATH para relanzarlos
            "pomodoro": {"work": 25, "short": 5, "long": 15, "every": 4, "auto": True},
            # sensor de presencia: minutos sin nadie, aviso previo (s), pausa (epoch) y horario (0 = lunes)
            "presence": {"minutes": 5, "warn": 30, "paused_until": 0, "start": "08:00", "end": "18:00",
                         "days": [0, 1, 2, 3, 4]}}


# funciones que vienen apagadas hasta que el usuario las encienda (el resto viene encendido)
FEATURE_DEFAULTS = {"presence": False}


_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")      # nombre de usuario de GitHub


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


def _server_entry(r):
    """Comando recordado de un servidor (o sus contenedores de Docker), o None si no es válido."""
    if isinstance(r, dict) and "docker" in r:
        names = r["docker"]
        from .services.servers import DOCKER_NAME          # «--privileged» no es un contenedor
        if not (isinstance(names, list) and names and all(isinstance(n, str) and DOCKER_NAME.fullmatch(n)
                                                          for n in names)):
            return None
        port = r.get("port")
        return {"name": r.get("name") if isinstance(r.get("name"), str) else names[0],
                "port": port if isinstance(port, int) and not isinstance(port, bool) else None,
                "kind": r.get("kind") if isinstance(r.get("kind"), str) else "Docker", "docker": list(names),
                "when": r.get("when") if _num(r.get("when"), 0, float("inf")) else 0}
    if not (isinstance(r, dict) and isinstance(r.get("cwd"), str) and r["cwd"] and isinstance(r.get("argv"), list)
            and r["argv"] and all(isinstance(a, str) for a in r["argv"])):
        return None
    port = r.get("port")
    return {"name": r.get("name") if isinstance(r.get("name"), str) else "",
            "port": port if isinstance(port, int) and not isinstance(port, bool) else None,
            "kind": r.get("kind") if isinstance(r.get("kind"), str) else "",
            "cwd": r["cwd"], "argv": list(r["argv"]),
            "path": r.get("path") if isinstance(r.get("path"), str) else "",
            "when": r.get("when") if _num(r.get("when"), 0, float("inf")) else 0}


class Config:
    """Preferencias guardadas en ~/.config/isla-dinamica/config.json."""

    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULTS))
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            self.data["city"] = loaded.get("city") or None
            # «dock» no se carga: la isla siempre arranca arriba y centrada (se puede mover durante la sesión)
            self.data["features"] = {k: v for k, v in (loaded.get("features") or {}).items()
                                     if isinstance(v, bool)}
            if isinstance(loaded.get("collapsed"), list):
                self.data["collapsed"] = [k for k in loaded["collapsed"] if isinstance(k, str)]
            acct = loaded.get("github_account")
            if isinstance(acct, str) and _LOGIN.fullmatch(acct):
                self.data["github_account"] = acct
            folders = loaded.get("account_folders")
            if isinstance(folders, dict):
                self.data["account_folders"] = {
                    k: [p for p in v if isinstance(p, str) and p] for k, v in folders.items()
                    if isinstance(k, str) and _LOGIN.fullmatch(k) and isinstance(v, list)}
                self.data["account_folders"] = {k: v for k, v in self.data["account_folders"].items() if v}
            if isinstance(loaded.get("servers_recent"), list):
                from .services.servers import remember      # une proyectos de Docker repetidos
                recent = []
                for r in reversed([_server_entry(r) for r in loaded["servers_recent"] if _server_entry(r)]):
                    recent = remember(recent, r, now=r["when"])
                self.data["servers_recent"] = recent
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
