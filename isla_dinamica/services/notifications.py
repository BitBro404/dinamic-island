"""Notificaciones del escritorio, de cualquier servidor (Budgie, GNOME, Plasma, mako…).

El servicio no conoce escritorios: pregunta a las cadenas de `platform/` cuál fuente de avisos, qué
«No molestar» y qué centro de notificaciones usar. Las herramientas y el escritorio se inyectan para
probarlo sin bus real; en producción se usan los reales.
"""
import os

from gi.repository import GLib

from ..platform import dnd as pdnd
from ..platform.chain import Tools, pick
from ..platform.desktop import detect
from ..platform.notify import SOURCES


class Notifications:
    """Avisos, «No molestar» y centro, elegidos según lo que haya en este escritorio."""

    def __init__(self, bus, on_notify, on_dnd, tools=None, desktop=None,
                 sources=SOURCES, dnd_methods=None, centers=None, timeout_add=GLib.timeout_add_seconds):
        self.bus, self.on_notify, self.on_dnd = bus, on_notify, on_dnd
        tools = tools or Tools()
        desktop = desktop or detect(os.environ)
        dnd_methods = pdnd.METHODS if dnd_methods is None else dnd_methods
        centers = pdnd.CENTER if centers is None else centers
        self.dnd = False

        source = pick(sources, tools, desktop)
        self.source = source.act(bus, self._notify) if source else None

        method = pick(dnd_methods, tools, desktop)
        self.dnd_backend = method.act(bus) if method else None
        if self.dnd_backend:
            self.dnd = bool(self.dnd_backend.get())
            self.dnd_backend.watch(self._dnd_changed)
            if getattr(self.dnd_backend, "polls", False):
                timeout_add(3, self._poll_dnd)

        # los métodos del centro son acciones listas para ejecutar con el bus (no fábricas)
        self._center = pick(centers, tools, desktop)

    @property
    def supported(self):
        return self.dnd_backend is not None

    @property
    def has_center(self):
        return self._center is not None

    def _notify(self, n):
        self.on_notify(n)

    def _dnd_changed(self, *_args):
        self.dnd = bool(self.dnd_backend.get())
        self.on_dnd()

    def _poll_dnd(self):
        value = bool(self.dnd_backend.get())
        if value != self.dnd:
            self.dnd = value
            self.on_dnd()
        return True

    def toggle_dnd(self):
        if self.dnd_backend:
            self.dnd_backend.toggle()

    def open_center(self):
        if self._center:
            self._center.act(self.bus)
