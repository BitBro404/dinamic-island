"""Portapapeles: watcher y copia según el escritorio.

wl-clipboard (wlroots, KDE) permite observar cambios con `wl-paste --watch`; en X11/XWayland se usa
`Gtk.Clipboard` y su señal `owner-change`. En ambos casos el servicio mantiene el mismo historial y el
mismo filtro de secretos (S4).
"""
import os

from gi.repository import Gdk, Gtk

from ..util.proc import run as _run, tied
from .chain import Method, Tools, pick
from .desktop import detect

# Evita guardar lo que un gestor de contraseñas marca como tal (KDE).
_WATCH_SCRIPT = ("wl-paste -l 2>/dev/null | grep -q x-kde-passwordManagerHint && exit 0; "
                 "cat; printf '\\036'")
WATCH_ARGV = ["wl-paste", "-n", "-t", "text", "--watch", "sh", "-c", _WATCH_SCRIPT]

METHODS = [
    Method("wl-paste --watch", lambda t, d: t.has("wl-paste") and (d.wlr or d.family == "kde"),
           ("process", WATCH_ARGV), hint="wl-clipboard"),
    Method("Gtk.Clipboard", lambda t, d: True, ("gtk", None)),
]
FEATURE = ("Portapapeles", METHODS)


class GtkSource:
    """Observa `owner-change` de Gtk.Clipboard (X11 y XWayland)."""

    def __init__(self, on_text, clipboard=None):
        self.on_text = on_text
        self.clipboard = clipboard or Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clipboard.connect("owner-change", self._changed)

    def _changed(self, *_args):
        text = (self.clipboard.wait_for_text() or "").strip()
        if text:
            self.on_text(text)


def copy_text(text, tools=None, desktop=None, run=None, clipboard=None):
    """Copia texto con wl-copy si está, si no con Gtk.Clipboard.set_text + store."""
    tools, desktop = tools or Tools(), desktop or detect(os.environ)
    if tools.has("wl-copy") and (desktop.wlr or desktop.wayland):
        (run or _run)(["wl-copy"], stdin=text)
        return
    cb = clipboard or Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    cb.set_text(text, -1)
    cb.store()
