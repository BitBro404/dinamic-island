"""Acople a los bordes: arrastrar la isla y pegarla arriba, abajo, a la izquierda o a la derecha.

Las funciones de geometría son puras (se prueban en tests/unit/test_dock.py); `DockMixin` las usa desde la
ventana para colocarla (con `ui/placement.py`: layer-shell, X11…) y para el arrastre con el ratón.
"""
import math
import time

from gi.repository import GLib, Gdk, Gtk

from ..util.proc import dbg
from .style import DRAG_MIN, GAP


def nearest_edge(cx, cy, mw, mh):
    """Borde de la pantalla (mw×mh) más cercano al punto (cx, cy)."""
    dist = {"top": cy, "bottom": mh - cy, "left": cx, "right": mw - cx}
    return min(dist, key=dist.get)


def dock_xy(edge, pos, w, h, mw, mh, gap=GAP, center=None):
    """Esquina (x, y) de una isla de w×h pegada a `edge` en la posición relativa `pos` (0–1 a lo largo del
    borde). Con `center` (durante un arrastre) se centra ahí. Nunca se sale de la pantalla."""
    if center is not None:
        cx, cy = center
    elif edge in ("top", "bottom"):
        cx = pos * mw
        cy = gap + h / 2 if edge == "top" else mh - gap - h / 2
    else:
        cy = pos * mh
        cx = gap + w / 2 if edge == "left" else mw - gap - w / 2
    return max(gap, min(cx - w / 2, mw - w - gap)), max(gap, min(cy - h / 2, mh - h - gap))


def drop_position(cx, cy, mw, mh):
    """Al soltar en (cx, cy): (borde más cercano, posición relativa a lo largo de ese borde)."""
    edge = nearest_edge(cx, cy, mw, mh)
    return edge, (cx / mw if edge in ("top", "bottom") else cy / mh)


def layer_layout(edge, x, y, w, h, mw, mh):
    """Anclas y márgenes de layer-shell para que la isla crezca alejándose de su borde:
    abajo crece hacia arriba, a la derecha crece hacia la izquierda; el resto, desde arriba-izquierda."""
    if edge == "bottom":
        return ("bottom", "left"), {"bottom": mh - y - h, "left": x}
    if edge == "right":
        return ("top", "right"), {"top": y, "right": mw - x - w}
    return ("top", "left"), {"top": y, "left": x}


class DockMixin:
    """Arrastre y colocación de la ventana. Lo usa IslandWindow; necesita self.monitor, self.core, self.cur, self.pad, self.drag y los métodos de animación."""

    def _mon_size(self):
        g = self.monitor.get_geometry()
        return g.width, g.height

    def _pointer(self):
        """Posición del ratón relativa a la ventana (en Wayland no hay coordenadas globales)."""
        win = self.get_window()
        dev = self.get_display().get_default_seat().get_pointer()
        _, x, y, _ = win.get_device_position(dev)
        return x, y


    def _target_xy(self, w, h):
        mw, mh = self._mon_size()
        center = self.drag["c"] if self.drag and self.drag["moving"] else None
        return dock_xy(self.core.dock["edge"], self.core.dock["pos"], w, h, mw, mh, GAP, center)

    def _place(self):
        """Coloca la ventana según el borde al que está pegada (o donde se esté arrastrando)."""
        w, h = max(1, round(self.cur[0])), max(1, round(self.cur[1]))
        mw, mh = self._mon_size()
        x, y = self._target_xy(w, h)
        pl, pt, pr, pb = self.pad
        w, h = w + pl + pr, h + pt + pb                    # la ventana incluye el espacio de la sombra
        x = max(0, min(round(x + self.poff[0]) - pl, mw - w))
        y = max(0, min(round(y + self.poff[1]) - pt, mh - h))
        self._last_xy = (x, y)
        edge = None if self.drag and self.drag["moving"] else self.core.dock["edge"]
        self.placement.apply(edge, x, y, w, h, mw, mh)
        if self._applied == (0, 0) and not self.get_realized():
            self._applied = (x, y)

    def _after_paint(self, _clock):
        self._applied = self._last_xy

    def dock_changed(self):
        self._set_vertical(self.core.dock["edge"] in ("left", "right"))
        self.refresh()
        self._place()
        self._kick()

    def _set_cursor(self, name):
        win = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), name) if name else None)

    def _on_drag_end(self, *_):
        d, self.drag = self.drag, None
        dbg("drag-end", bool(d and d["moving"]))
        if d and d["moving"]:
            self._drop()

    def _on_press(self, _g, x, y):
        self.drag = {"start": self._pointer(), "moving": False}
        dbg("press", self.drag["start"], "view", self.view)
        # los hijos con ventana propia (Stack, ScrolledWindow) se tragan el movimiento:
        # se consulta el ratón en cada cuadro mientras el botón siga pulsado
        if not getattr(self, "_drag_src", None):
            self._drag_src = GLib.timeout_add(12, self._drag_poll)

    def _drag_poll(self):
        if not self.drag:
            self._drag_src = None
            return False
        win = self.get_window()
        dev = self.get_display().get_default_seat().get_pointer()
        _, x, y, mask = win.get_device_position(dev)
        if not mask & Gdk.ModifierType.BUTTON1_MASK:
            d, self.drag = self.drag, None
            self._drag_src = None
            dbg("poll: botón suelto", d["moving"])
            if d["moving"]:
                self._drop()
            return False
        self._drag_move(x, y)
        return True

    def _on_motion(self, _w, ev):
        if not self.drag:
            return False
        self._drag_move(*self._pointer())
        return True

    def _drag_move(self, lx, ly):
        d = self.drag
        if not d["moving"]:
            if math.hypot(lx - d["start"][0], ly - d["start"][1]) < DRAG_MIN:
                return
            if self.typing():
                self.drag = None
                return
            dbg("arrastre empieza")
            self._gdrag.set_state(Gtk.EventSequenceState.CLAIMED)   # que ningún botón reciba el clic
            w, h = self.cur
            # en la píldora se agarra por donde se pulsó; si estaba abierta, se cierra bajo el ratón
            d["off"] = ((d["start"][0] - w / 2, d["start"][1] - h / 2)
                        if self.view == "compact" else (0.0, 0.0))
            d["c"] = (self._applied[0] + d["start"][0] - d["off"][0],
                      self._applied[1] + d["start"][1] - d["off"][1])
            d["moving"] = True
            self.poff, self.pvel = [0.0, 0.0], [0.0, 0.0]
            self._set_cursor("grabbing")
            if self._hover_src:
                GLib.source_remove(self._hover_src)
                self._hover_src = None
            if self.hover:
                self._set_hover(False)
        ax, ay = self._applied[0] + lx, self._applied[1] + ly
        d["c"] = (ax - d["off"][0], ay - d["off"][1])
        mw, mh = self._mon_size()
        vertical = nearest_edge(*d["c"], mw, mh) in ("left", "right")
        if vertical != self.vertical:
            self._set_vertical(vertical)
            self.refresh()
        self._place()
        self.queue_draw()

    def _drop(self):
        self._drag_end = time.monotonic()
        self._set_cursor(None)
        mw, mh = self._mon_size()
        w, h = self.cur
        x0, y0 = self._last_xy
        edge, pos = drop_position(x0 + w / 2, y0 + h / 2, mw, mh)
        dbg("soltada en", edge, round(pos, 2))
        self.core.set_dock(edge, pos)
        # que viaje con suavidad desde donde se soltó hasta el borde
        tx, ty = self._target_xy(w, h)
        self.poff = [x0 - tx, y0 - ty]
        self.pvel = [0.0, 0.0]
        self.placement.reset()
        self._place()
        self._kick()
