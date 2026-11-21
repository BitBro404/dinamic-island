"""Widgets dibujados a mano."""
from .common import *  # noqa: F401,F403


# ───────────────────────────── widgets dibujados ─────────────────────────────
class Art(Gtk.DrawingArea):
    """Imagen cuadrada con esquinas redondeadas (o una nota musical de relleno)."""

    def __init__(self, size, radius):
        super().__init__()
        self.size, self.radius, self.pixbuf, self._scaled = size, radius, None, None
        self.set_size_request(size, size)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self._draw)

    def set_pixbuf(self, pb):
        if pb is self.pixbuf:
            return
        self.pixbuf = pb
        self._scaled = None
        if pb:
            sf = self.get_scale_factor()
            w, h = pb.get_width(), pb.get_height()
            side = min(w, h)
            sq = pb.new_subpixbuf((w - side) // 2, (h - side) // 2, side, side)
            self._scaled = sq.scale_simple(self.size * sf, self.size * sf, GdkPixbuf.InterpType.BILINEAR)
        self.queue_draw()

    def _draw(self, _w, cr):
        s, r = self.size, self.radius
        cr.new_sub_path()
        cr.arc(s - r, r, r, -math.pi / 2, 0)
        cr.arc(s - r, s - r, r, 0, math.pi / 2)
        cr.arc(r, s - r, r, math.pi / 2, math.pi)
        cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.clip()
        if self._scaled:
            sf = self.get_scale_factor()
            cr.scale(1 / sf, 1 / sf)
            Gdk.cairo_set_source_pixbuf(cr, self._scaled, 0, 0)
            cr.paint()
        else:
            cr.set_source_rgb(0.17, 0.17, 0.18)
            cr.paint()
            cr.set_source_rgb(0.55, 0.55, 0.58)
            cr.arc(s * 0.42, s * 0.66, s * 0.12, 0, 2 * math.pi)
            cr.fill()
            cr.rectangle(s * 0.50, s * 0.26, s * 0.06, s * 0.42)
            cr.fill()
            cr.move_to(s * 0.56, s * 0.26)
            cr.curve_to(s * 0.66, s * 0.30, s * 0.72, s * 0.36, s * 0.66, s * 0.48)
            cr.curve_to(s * 0.66, s * 0.40, s * 0.62, s * 0.36, s * 0.56, s * 0.36)
            cr.close_path()
            cr.fill()
        return False


class Equalizer(Gtk.DrawingArea):
    def __init__(self, w=22, h=16):
        super().__init__()
        self.w, self.h, self.playing, self._tick = w, h, False, None
        self.set_size_request(w, h)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self._draw)

    def set_playing(self, playing):
        playing = bool(playing)
        if playing == self.playing:
            return
        self.playing = playing
        if playing and self._tick is None:
            self._tick = self.add_tick_callback(lambda *_: (self.queue_draw(), True)[1])
        elif not playing and self._tick is not None:
            self.remove_tick_callback(self._tick)
            self._tick = None
        self.queue_draw()

    def _draw(self, _w, cr):
        t = time.monotonic()
        n, gap = 4, 3
        bw = (self.w - gap * (n - 1)) / n
        cr.set_source_rgb(0.19, 0.82, 0.35)
        for i in range(n):
            if self.playing:
                v = 0.5 + 0.5 * math.sin(t * (6.0 + i * 1.7) + i * 1.3) * math.sin(t * (2.3 + i * 0.9))
                hh = max(3, self.h * (0.25 + 0.75 * abs(v)))
            else:
                hh = 3
            x, y, r = i * (bw + gap), (self.h - hh) / 2, bw / 2
            cr.new_sub_path()
            cr.arc(x + r, y + r, r, math.pi, 0)
            cr.arc(x + r, y + hh - r, r, 0, math.pi)
            cr.close_path()
            cr.fill()
        return False


# ───────────────────────────── servicios ─────────────────────────────
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


# ───────────────────────────── la isla (una por pantalla) ─────────────────────────────
class Tile(Gtk.Box):
    """Ajuste rápido: círculo que activa/desactiva + nombre (que abre el detalle si existe)."""

    def __init__(self, icon_name, title, on_toggle, on_open=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=3, halign=Gtk.Align.CENTER)
        self.img = icon(icon_name, px=24)
        self.btn = button("tile", self.img, on_toggle, tooltip=title)
        self.btn.set_halign(Gtk.Align.CENTER)
        self.pack_start(self.btn, False, False, 0)
        if on_open:
            self.name = button("link", cb=on_open, text=title + " ›")
        else:
            self.name = label(title, "dim small", xalign=0.5)
        self.pack_start(self.name, False, False, 0)
        self.sub = label("", "time-small", xalign=0.5)
        self.sub.set_max_width_chars(11)
        self.pack_start(self.sub, False, False, 0)

    def set(self, on, sub="", icon_name=None):
        set_class(self.btn, "on", on)
        if icon_name:
            self.img.set_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
            self.img.set_pixel_size(24)
        self.sub.set_text(sub)
