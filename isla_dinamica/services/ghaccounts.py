"""Cuentas de GitHub con sesión en `gh`: las detecta todas y cambia la de la isla pidiendo la contraseña.

La isla no toca la cuenta activa de `gh` en la terminal: cada consulta lleva el token de la cuenta
elegida en la variable GH_TOKEN. Cambiar de cuenta pide la contraseña del usuario con polkit (pkexec),
así la isla nunca ve ni guarda la contraseña.
"""
import os
import re
import subprocess

from gi.repository import GLib

from ..util.proc import dbg, run

_LOGGED = re.compile(r"Logged in to (\S+) account (\S+)")
_ACTIVE = re.compile(r"Active account:\s*(true|false)")


def parse_status(text, host="github.com"):
    """Salida de `gh auth status` → (logins en orden, login activo o None)."""
    logins, active, cur = [], None, None
    for line in text.splitlines():
        m = _LOGGED.search(line)
        if m:
            cur = m.group(2) if m.group(1) == host else None
            if cur and cur not in logins:
                logins.append(cur)
            continue
        m = _ACTIVE.search(line)
        if m and cur and m.group(1) == "true":
            active = cur
    return logins, active


def _sh(argv, timeout=8):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, LC_ALL="C"))
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "", str(e)
    return r.returncode == 0, r.stdout, r.stderr


class Accounts:
    """Cuentas de `gh` y la cuenta elegida en la isla (config «github_account»)."""
    def __init__(self, config, on_change, sh=_sh, runner=run):
        self.config, self.on_change, self._sh, self._run = config, on_change, sh, runner
        self.logins, self.gh_active = [], None
        self.switching = None        # cuenta a la que se está cambiando (esperando la contraseña)
        self.error = ""
        self._tokens = {}
        self.load()

    def load(self):
        """Vuelve a leer las cuentas de `gh auth status` (se llama al abrir la página de cuentas)."""
        if not GLib.find_program_in_path("gh"):
            self.logins, self.gh_active = [], None
            return
        ok, out, err = self._sh(["gh", "auth", "status", "--hostname", "github.com"])
        self.logins, self.gh_active = parse_status(out + "\n" + err)
        self._tokens = {k: v for k, v in self._tokens.items() if k in self.logins}

    @property
    def current(self):
        """Cuenta elegida: la guardada si sigue con sesión; si no, la activa de `gh`."""
        saved = self.config.data.get("github_account")
        if saved in self.logins:
            return saved
        return self.gh_active or (self.logins[0] if self.logins else None)

    def token(self, login=None):
        login = login or self.current
        if not login:
            return None
        if login not in self._tokens:
            ok, out, _err = self._sh(["gh", "auth", "token", "--hostname", "github.com", "--user", login])
            self._tokens[login] = out.strip() if ok and out.strip() else None
        return self._tokens[login]

    def env(self, login=None):
        """Variables para que `gh` actúe como esa cuenta sin cambiar la activa de la terminal."""
        tok = self.token(login)
        return {"GH_TOKEN": tok} if tok else {}

    def switch(self, login, done=lambda ok, msg: None):
        """Cambia la cuenta de la isla tras pedir la contraseña del usuario (polkit)."""
        if login == self.current or login not in self.logins or self.switching:
            return
        if not GLib.find_program_in_path("pkexec"):
            self.error = "Falta pkexec (polkit) para pedir la contraseña"
            self.on_change()
            return done(False, self.error)
        self.switching, self.error = login, ""
        self.on_change()

        def authed(ok, _out, err):
            self.switching = None
            try:
                if ok:
                    self.config.data["github_account"] = login
                    try:
                        self.config.save()
                    except OSError:
                        pass
                    done(True, f"Ahora usas @{login}")
                else:
                    dbg("pkexec:", err.strip()[:200])
                    self.error = "Contraseña cancelada o incorrecta: sigues con @" + str(self.current)
                    done(False, self.error)
            finally:
                self.on_change()        # pase lo que pase después, la página deja de decir «Esperando…»

        self._run(["pkexec", "/bin/true"], authed)
