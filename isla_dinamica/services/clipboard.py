"""Historial del portapapeles."""
import re
import time

from gi.repository import GLib, Gio

from ..util.proc import run, tied


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

    def __init__(self, on_change):
        self.on_change = on_change
        self.history = History()
        GLib.timeout_add_seconds(60, self._prune)
        script = ("wl-paste -l 2>/dev/null | grep -q x-kde-passwordManagerHint && exit 0; "
                  "cat; printf '\\036'")
        try:
            self.proc = Gio.Subprocess.new(tied(["wl-paste", "-n", "-t", "text", "--watch", "sh", "-c", script]),
                                           Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
            self.stream = Gio.DataInputStream.new(self.proc.get_stdout_pipe())
            self._read()
        except GLib.Error:
            self.proc = None

    def _read(self):
        self.stream.read_upto_async(self.SEP, -1, GLib.PRIORITY_DEFAULT, None, self._on_data)

    def _on_data(self, stream, res):
        try:
            text, _ln = stream.read_upto_finish(res)
            stream.read_byte(None)
        except GLib.Error:
            return
        if self.history.add(text):
            self.on_change()
        self._read()

    @property
    def items(self):
        return self.history.items

    def _prune(self):
        if self.history.prune():
            self.on_change()
        return True

    def copy(self, text):
        run(["wl-copy"], stdin=text)

    def remove(self, text):
        if self.history.remove(text):
            self.on_change()

    def clear(self):
        self.history.clear()
        self.on_change()
