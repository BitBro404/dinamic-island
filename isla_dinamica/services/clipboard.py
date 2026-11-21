"""Historial del portapapeles."""
from ..common import *  # noqa: F401,F403


class Clipboard:
    """Historial de texto copiado (solo en memoria, no se guarda en disco)."""
    SEP = "\x1e"

    def __init__(self, on_change):
        self.on_change = on_change
        self.items = []
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
        if text and text.strip():
            if text in self.items:
                self.items.remove(text)
            self.items.insert(0, text)
            del self.items[40:]
            self.on_change()
        self._read()

    def copy(self, text):
        run(["wl-copy"], stdin=text)

    def remove(self, text):
        if text in self.items:
            self.items.remove(text)
            self.on_change()

    def clear(self):
        self.items.clear()
        self.on_change()
