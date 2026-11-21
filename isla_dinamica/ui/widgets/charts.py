"""Pequeños gráficos: puntos de privacidad, línea de historial y barra de temperaturas."""
import math

import cairo
from gi.repository import Gtk


class PrivacyDots(Gtk.DrawingArea):
    """Puntos de privacidad: verde = cámara, naranja = micrófono."""
    CAM, MIC = (0.19, 0.82, 0.35), (1.0, 0.62, 0.04)

    def __init__(self):
        super().__init__()
        self.cam = self.mic = False
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.connect("draw", self._draw)
        self._resize()

    def set_state(self, cam, mic):
        if (cam, mic) != (self.cam, self.mic):
            self.cam, self.mic = bool(cam), bool(mic)
            self._resize()
            self.queue_draw()

    def count(self):
        return int(self.cam) + int(self.mic)

    def _resize(self):
        n = self.count()
        self.set_size_request(max(1, n * 8 + (n - 1) * 4), 8)

    def _draw(self, _w, cr):
        a = self.get_allocation()
        x = (a.width - (self.count() * 8 + max(0, self.count() - 1) * 4)) / 2
        for on, col in ((self.cam, self.CAM), (self.mic, self.MIC)):
            if on:
                cr.set_source_rgb(*col)
                cr.arc(x + 4, a.height / 2, 4, 0, 2 * math.pi)
                cr.fill()
                x += 12
        return False


class Spark(Gtk.DrawingArea):
    """Gráfica pequeña (línea con relleno) de una serie de valores entre lo y hi."""

    def __init__(self, color, lo=0.0, hi=100.0, h=34):
        super().__init__()
        self.color, self.lo, self.hi, self.values = color, lo, hi, []
        self.set_size_request(-1, h)
        self.connect("draw", self._draw)

    def set_values(self, values, lo=None, hi=None):
        self.values = list(values)
        if lo is not None:
            self.lo = lo
        if hi is not None:
            self.hi = hi
        self.queue_draw()

    def _draw(self, _w, cr):
        a = self.get_allocation()
        w, h = a.width, a.height
        v = self.values
        if len(v) < 2:
            return False
        span = max(1e-6, self.hi - self.lo)
        step = w / (len(v) - 1)
        pts = [(i * step, h - 1 - (min(max(x, self.lo), self.hi) - self.lo) / span * (h - 2)) for i, x in enumerate(v)]
        cr.move_to(0, h)
        for x, y in pts:
            cr.line_to(x, y)
        cr.line_to(w, h)
        cr.close_path()
        cr.set_source_rgba(*self.color, 0.22)
        cr.fill()
        for i, (x, y) in enumerate(pts):
            (cr.move_to if i == 0 else cr.line_to)(x, y)
        cr.set_source_rgb(*self.color)
        cr.set_line_width(1.6)
        cr.stroke()
        return False


class TempBar(Gtk.DrawingArea):
    """Barra de rango mín–máx de un día, relativa al rango de toda la semana."""

    def __init__(self, lo, hi, wlo, whi):
        super().__init__()
        self.v = (lo, hi, wlo, whi)
        self.set_size_request(80, 6)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self._draw)

    def _draw(self, _w, cr):
        a = self.get_allocation()
        w, h = a.width, a.height
        lo, hi, wlo, whi = self.v
        span = max(1e-6, whi - wlo)

        def bar(x0, x1):
            r = h / 2
            cr.new_sub_path()
            cr.arc(x0 + r, r, r, math.pi / 2, 3 * math.pi / 2)
            cr.arc(max(x0 + r, x1 - r), r, r, -math.pi / 2, math.pi / 2)
            cr.close_path()

        bar(0, w)
        cr.set_source_rgba(1, 1, 1, 0.14)
        cr.fill()
        x0, x1 = (lo - wlo) / span * w, (hi - wlo) / span * w
        g = cairo.LinearGradient(0, 0, w, 0)
        g.add_color_stop_rgb(0, 0.39, 0.82, 1.0)
        g.add_color_stop_rgb(0.55, 0.19, 0.82, 0.35)
        g.add_color_stop_rgb(1, 1.0, 0.62, 0.04)
        bar(x0, max(x1, x0 + h))
        cr.set_source(g)
        cr.fill()
        return False
