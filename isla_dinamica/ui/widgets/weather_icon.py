"""Iconos del clima dibujados con Cairo (sol, luna, nubes, lluvia, tormenta…)."""
import math

import cairo
from gi.repository import Gtk


# ───────────────────────────── clima, privacidad y gráficas ─────────────────────────────
class WeatherIcon(Gtk.DrawingArea):
    """Ícono del clima a color dibujado con Cairo (sol, luna, nubes, lluvia, tormenta, nieve, niebla).
    Con animated=True la lluvia cae, la nieve flota y los rayos del sol giran."""
    SUN, MOON = (1.0, 0.84, 0.04), (0.93, 0.93, 0.95)
    WHITE, GREY, DARK = (0.95, 0.95, 0.97), (0.64, 0.64, 0.68), (0.42, 0.42, 0.46)
    DROP, BOLT = (0.39, 0.82, 1.0), (1.0, 0.84, 0.04)

    def __init__(self, px, animated=False):
        super().__init__()
        self.px, self.kind, self.animated = px, "cloudy", animated
        self._tick, self.t = None, 0.0
        self.set_size_request(px, px)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.connect("draw", self._draw)
        if animated:
            self.connect("map", lambda *_: self._start())
            self.connect("unmap", lambda *_: self._stop())

    def set_kind(self, kind):
        if kind != self.kind:
            self.kind = kind
            self.queue_draw()

    def _start(self):
        if self._tick is None:
            self._tick = self.add_tick_callback(self._on_tick)

    def _stop(self):
        if self._tick is not None:
            self.remove_tick_callback(self._tick)
            self._tick = None

    def _on_tick(self, _w, clock):
        self.t = clock.get_frame_time() / 1e6
        self.queue_draw()
        return True

    # ── piezas ──
    @staticmethod
    def _sun(cr, cx, cy, r, t, rays=True):
        cr.set_source_rgb(*WeatherIcon.SUN)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()
        if rays:
            cr.set_line_width(r * 0.28)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            for i in range(8):
                a = i * math.pi / 4 + t * 0.4
                cr.move_to(cx + math.cos(a) * r * 1.45, cy + math.sin(a) * r * 1.45)
                cr.line_to(cx + math.cos(a) * r * 1.85, cy + math.sin(a) * r * 1.85)
            cr.stroke()

    @staticmethod
    def _moon(cr, cx, cy, r):
        cr.push_group()
        cr.set_source_rgb(*WeatherIcon.MOON)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.arc(cx + r * 0.55, cy - r * 0.35, r * 0.82, 0, 2 * math.pi)
        cr.fill()
        cr.pop_group_to_source()
        cr.paint()

    @staticmethod
    def _cloud(cr, dx, dy, k, color):
        cr.save()
        cr.translate(dx, dy)
        cr.scale(k, k)
        cr.set_source_rgb(*color)
        for x, y, r in ((0.32, 0.56, 0.16), (0.52, 0.45, 0.22), (0.72, 0.57, 0.15)):
            cr.arc(x, y, r, 0, 2 * math.pi)
            cr.fill()
        r = 0.08
        x0, x1, y0, y1 = 0.16, 0.87, 0.52, 0.72
        cr.new_sub_path()
        cr.arc(x1 - r, y1 - r, r, 0, math.pi / 2)
        cr.arc(x0 + r, y1 - r, r, math.pi / 2, math.pi)
        cr.line_to(x0, y0)
        cr.line_to(x1, y0)
        cr.close_path()
        cr.fill()
        cr.restore()

    def _drops(self, cr, n, length, y0=0.66, color=None):
        cr.set_source_rgb(*(color or self.DROP))
        cr.set_line_width(0.055)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for i in range(n):
            x = 0.3 + i * (0.42 / max(1, n - 1)) if n > 1 else 0.5
            ph = ((self.t * 1.6 + i * 0.37) % 1.0) if self.animated else (0.35 + 0.3 * (i % 2))
            y = y0 + ph * 0.22
            cr.move_to(x, y)
            cr.line_to(x - length * 0.35, y + length)
        cr.stroke()

    def _flakes(self, cr):
        cr.set_source_rgb(*self.WHITE)
        for i, x in enumerate((0.32, 0.5, 0.68)):
            ph = ((self.t * 0.6 + i * 0.33) % 1.0) if self.animated else (0.3 + 0.35 * (i % 2))
            y = 0.72 + ph * 0.2
            cr.arc(x + math.sin(self.t * 2 + i) * 0.02, y, 0.045, 0, 2 * math.pi)
            cr.fill()

    def _draw(self, _w, cr):
        a = self.get_allocation()
        s = min(a.width, a.height)
        cr.translate((a.width - s) / 2, (a.height - s) / 2)
        cr.scale(s, s)
        k, t = self.kind, (self.t if self.animated else 0.0)
        if k == "clear":
            self._sun(cr, 0.5, 0.5, 0.2, t)
        elif k == "clear-night":
            self._moon(cr, 0.48, 0.52, 0.27)
            cr.set_source_rgb(*self.MOON)
            for x, y, r in ((0.8, 0.22, 0.03), (0.86, 0.5, 0.02)):
                cr.arc(x, y, r * (1 + 0.4 * math.sin(t * 2 + x * 9)), 0, 2 * math.pi)
                cr.fill()
        elif k in ("partly", "partly-night"):
            if k == "partly":
                self._sun(cr, 0.36, 0.34, 0.15, t)
            else:
                self._moon(cr, 0.36, 0.34, 0.19)
            self._cloud(cr, 0.12, 0.14, 0.86, self.WHITE)
        elif k == "cloudy":
            self._cloud(cr, -0.06, -0.05, 0.78, self.GREY)
            self._cloud(cr, 0.06, 0.04, 0.92, self.WHITE)
        elif k == "fog":
            self._cloud(cr, 0.0, -0.1, 0.9, self.GREY)
            cr.set_source_rgb(*self.WHITE)
            cr.set_line_width(0.06)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            for i, y in enumerate((0.7, 0.82)):
                off = math.sin(t * 1.2 + i) * 0.04
                cr.move_to(0.2 + off + i * 0.08, y)
                cr.line_to(0.8 + off - i * 0.04, y)
            cr.stroke()
        elif k == "drizzle":
            self._cloud(cr, 0.0, -0.14, 0.95, self.WHITE)
            self._drops(cr, 3, 0.08)
        elif k == "rain":
            self._cloud(cr, 0.0, -0.14, 0.95, self.GREY)
            self._drops(cr, 4, 0.13)
        elif k == "heavy-rain":
            self._cloud(cr, 0.0, -0.14, 0.95, self.DARK)
            self._drops(cr, 5, 0.17)
        elif k == "storm":
            self._cloud(cr, 0.0, -0.16, 0.95, self.DARK)
            self._drops(cr, 2, 0.12)
            flash = 1.0 if not self.animated or (t % 2.4) > 0.25 else 0.35
            cr.set_source_rgba(*self.BOLT, flash)
            for x, y in ((0.55, 0.5), (0.4, 0.72), (0.52, 0.72), (0.44, 0.94), (0.66, 0.66), (0.54, 0.66),
                         (0.62, 0.5)):
                cr.line_to(x, y)
            cr.close_path()
            cr.fill()
        elif k == "snow":
            self._cloud(cr, 0.0, -0.14, 0.95, self.WHITE)
            self._flakes(cr)
        return False
