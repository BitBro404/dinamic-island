"""Historial del portapapeles."""
import os
import re
import time

from gi.repository import GLib, Gio

from ..platform.chain import Tools, pick
from ..platform.clipboard import GtkSource, METHODS as CLIP_METHODS, WATCH_ARGV, copy_text
from ..platform.desktop import detect
from ..util.proc import tied


# Prefijos de claves y tokens conocidos (GitHub, OpenAI/Stripe, AWS, Slack, GitLab, npm, Google…).
_SECRET_RE = re.compile(
    r"^(gh[pousr]_|github_pat_|sk-|sk_live_|rk_live_|pk_live_|AKIA[0-9A-Z]{12}|ASIA[0-9A-Z]{12}|"
    r"xox[abprs]-|glpat-|npm_|AIza[0-9A-Za-z_-]{20}|ya29\.)")
_JWT_RE = re.compile(r"^eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+$")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def looks_secret(text):
    """Heurística: ¿parece una contraseña, clave o token? Se usa para NO guardarlo en el historial.
    Detecta prefijos de proveedores conocidos, JWT, claves privadas PEM y cadenas sueltas de 16+
    caracteres que mezclan mayúsculas, minúsculas y al menos 3 dígitos (lo típico de algo aleatorio).
    No marca URLs, rutas, correos, UUID ni hashes de git."""
    t = (text or "").strip()
    if "PRIVATE KEY-----" in t:
        return True
    if not t or any(ch.isspace() for ch in t):
        return False
    if _SECRET_RE.match(t) or _JWT_RE.match(t):
        return True
    if len(t) < 16 or "/" in t or "@" in t or _UUID_RE.match(t):
        return False
    digits = sum(ch.isdigit() for ch in t)
    return digits >= 3 and any(ch.islower() for ch in t) and any(ch.isupper() for ch in t)


class History:
    """Lista de textos copiados, del más reciente al más viejo. Lógica pura (testeable):
    descarta secretos, evita duplicados, limita el tamaño y olvida lo que tiene más de `max_age` s."""

    def __init__(self, clock=time.monotonic, limit=40, max_age=30 * 60):
        self.clock, self.limit, self.max_age = clock, limit, max_age
        self.items, self._at = [], {}

    def add(self, text):
        """Guarda `text` arriba. Devuelve False si no se guardó (vacío o parece un secreto)."""
        if not text or not text.strip() or looks_secret(text):
            return False
        if text in self.items:
            self.items.remove(text)
        self.items.insert(0, text)
        self._at[text] = self.clock()
        for old in self.items[self.limit:]:
            self._at.pop(old, None)
        del self.items[self.limit:]
        return True

    def remove(self, text):
        if text in self.items:
            self.items.remove(text)
            self._at.pop(text, None)
            return True
        return False

    def prune(self):
        """Quita lo que pasó de `max_age`. Devuelve si quitó algo."""
        limit = self.clock() - self.max_age
        old = [t for t in self.items if self._at.get(t, 0) < limit]
        for t in old:
            self.remove(t)
        return bool(old)

    def clear(self):
        self.items.clear()
        self._at.clear()


class Clipboard:
    """Vigila el portapapeles (wl-paste --watch) y guarda un historial solo en memoria (nunca en disco).
    Lo que marca un gestor de contraseñas o parece un secreto no se guarda; lo demás caduca a los 30 min."""
    SEP = "\x1e"

    def __init__(self, on_change, tools=None, desktop=None):
        self.on_change = on_change
        self.history = History()
        self.tools, self.desktop = tools or Tools(), desktop or detect(os.environ)
        GLib.timeout_add_seconds(60, self._prune)
        self.method = pick(CLIP_METHODS, self.tools, self.desktop)
        self.proc = None
        self.stream = None
        if self.method and self.method.act[0] == "process":
            try:
                self.proc = Gio.Subprocess.new(tied(WATCH_ARGV),
                                               Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
                self.stream = Gio.DataInputStream.new(self.proc.get_stdout_pipe())
                self._read()
            except GLib.Error:
                self.proc = None
        if self.method and self.method.act[0] == "gtk":
            GtkSource(self._on_text)

    def _read(self):
        self.stream.read_upto_async(self.SEP, -1, GLib.PRIORITY_DEFAULT, None, self._on_data)

    def _on_data(self, stream, res):
        try:
            text, _ln = stream.read_upto_finish(res)
            stream.read_byte(None)
        except GLib.Error:
            return
        self._on_text(text)
        self._read()

    def _on_text(self, text):
        if self.history.add(text):
            self.on_change()

    @property
    def items(self):
        return self.history.items

    def _prune(self):
        if self.history.prune():
            self.on_change()
        return True

    def copy(self, text):
        copy_text(text, self.tools, self.desktop)

    def remove(self, text):
        if self.history.remove(text):
            self.on_change()

    def clear(self):
        self.history.clear()
        self.on_change()
