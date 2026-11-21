#!/usr/bin/env python3
"""Isla dinámica para escritorio Linux (Budgie / labwc, Wayland + layer-shell, GTK3).

Una "píldora" negra arriba al centro de cada pantalla que cambia de forma:
  reposo ........ hora
  música ........ carátula, título y ecualizador (MPRIS: Spotify, navegador, VLC...)
  avisos ........ notificaciones de apps (Teams, correo...) y del sistema, volumen,
                  batería, USB, Bluetooth, bienvenida al iniciar sesión / al despertar
Al pasar el ratón (o hacer clic) se expande con:
  reproductor, volumen, ajustes rápidos (Wi-Fi, Bluetooth, modo avión, no molestar,
  modo oscuro, luz nocturna, ahorro de energía, mantener despierto) y accesos a
  captura de pantalla, portapapeles, notificaciones, medios extraíbles,
  temporizador y energía (bloquear, cerrar sesión, suspender, reiniciar, apagar).
"""
import calendar
import html
import json
import math
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_foreign("cairo")
import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, GtkLayerShell, Pango  # noqa: E402

H = 34            # alto de la píldora compacta
W_EXP = 460       # ancho de la isla expandida
W_CARD = 420      # ancho de las tarjetas de aviso
GAP = 6           # separación con el borde de la pantalla
DRAG_MIN = 8      # píxeles que hay que mover el ratón para empezar a arrastrar

CSS = b"""
window { background: transparent; }
* { color: #f5f5f7; font-family: "Inter", "Cantarell", sans-serif; }
.c-text { font-weight: 600; font-size: 13px; }
.dim { color: #8e8e93; font-size: 12px; }
.small { font-size: 11px; }
.title { font-weight: 700; font-size: 15px; }
.subtitle { font-weight: 600; font-size: 13px; }
.artist { color: #a1a1a6; font-size: 13px; }
.bigclock { font-weight: 700; font-size: 30px; }
.huge { font-weight: 700; font-size: 36px; font-feature-settings: "tnum"; }
.time-small { color: #8e8e93; font-size: 11px; }
.orange { color: #ff9f0a; }
.green { color: #30d158; }
.red { color: #ff453a; }
.blue { color: #0a84ff; }

button { background: none; background-image: none; border: none; box-shadow: none;
         text-shadow: none; outline: none; }
button.ctrl { min-width: 36px; min-height: 36px; padding: 0; border-radius: 18px; }
button.ctrl:hover, button.act:hover, button.row:hover, button.link:hover { background: rgba(255,255,255,0.10); }
button.chip { background: rgba(255,255,255,0.10); border-radius: 14px; padding: 3px 12px; min-height: 0; }
button.chip:hover { background: rgba(255,255,255,0.22); }
button.chip label { font-weight: 600; font-size: 12px; }
button.chip.danger label { color: #ff453a; }
button.tile { min-width: 44px; min-height: 44px; padding: 0; border-radius: 22px;
              background: rgba(255,255,255,0.12); }
button.tile:hover { background: rgba(255,255,255,0.22); }
button.tile.on { background: #0a84ff; }
button.tile.on:hover { background: #3d9bff; }
button.link { padding: 1px 6px; border-radius: 8px; min-height: 0; }
button.link label { font-size: 11px; font-weight: 600; }
button.act { min-width: 49px; min-height: 46px; padding: 2px 0; border-radius: 12px;
             background: rgba(255,255,255,0.07); }
button.row { padding: 6px 8px; border-radius: 10px; }
button.big { min-width: 70px; min-height: 64px; border-radius: 16px; background: rgba(255,255,255,0.08); padding: 4px; }
button.big:hover { background: rgba(255,255,255,0.18); }
button.big.confirm { background: #ff453a; }
.badge { background: #ff453a; border-radius: 8px; min-width: 16px; min-height: 16px;
         font-size: 10px; font-weight: 700; padding: 0 3px; }
levelbar trough { min-height: 4px; border: none; border-radius: 2px; background: rgba(255,255,255,0.18); padding: 0; }
levelbar block.filled { border: none; border-radius: 2px; background: #f5f5f7; }
levelbar block.empty { border: none; background: transparent; }
scale trough { min-height: 6px; border-radius: 3px; background: rgba(255,255,255,0.18); border: none; }
scale highlight { background: #f5f5f7; border-radius: 3px; border: none; }
scale slider { min-width: 14px; min-height: 14px; border-radius: 7px; background: #f5f5f7; border: none; box-shadow: none; }
entry { background: rgba(255,255,255,0.10); border: none; border-radius: 10px; padding: 4px 10px; box-shadow: none; }
scrolledwindow, viewport { background: transparent; border: none; }
spinbutton { background: rgba(255,255,255,0.10); border: none; border-radius: 10px; box-shadow: none; min-height: 0; }
spinbutton entry { background: transparent; min-width: 30px; min-height: 0; padding: 2px 6px; }
spinbutton button { border-radius: 10px; min-width: 20px; min-height: 20px; padding: 0 3px; }
spinbutton button:hover { background: rgba(255,255,255,0.15); }
button.wlink { padding: 0 4px; border-radius: 8px; min-height: 0; }
button.wlink:hover { background: rgba(255,255,255,0.10); }
button.close { min-width: 24px; min-height: 24px; padding: 0; border-radius: 12px; background: rgba(255,255,255,0.10); }
button.close:hover { background: rgba(255,255,255,0.25); }
.hour { font-size: 11px; color: #a1a1a6; }
.wtile { background: rgba(255,255,255,0.07); border-radius: 12px; padding: 6px 10px; }
.wtile-v { font-weight: 600; font-size: 13px; }
.pop { color: #64d2ff; font-size: 11px; font-weight: 600; }
.section { color: #8e8e93; font-size: 11px; font-weight: 700; }
button.work { background: rgba(255,255,255,0.07); border-radius: 12px; padding: 5px 10px; min-height: 0; }
button.work:hover { background: rgba(255,255,255,0.16); }
.cmd { font-family: monospace; font-size: 12px; background: rgba(255,255,255,0.08); border-radius: 8px;
       padding: 4px 8px; }
"""

ACCENTS = ("orange", "green", "red", "blue")


# ───────────────────────────── utilidades ─────────────────────────────
def dbg(*a):
    if os.environ.get("ISLA_DEBUG"):
        print(*a, flush=True)


def set_accent(widget, accent=None):
    ctx = widget.get_style_context()
    for a in ACCENTS:
        ctx.remove_class(a)
    if accent:
        ctx.add_class(accent)


def set_class(widget, cls, on):
    ctx = widget.get_style_context()
    (ctx.add_class if on else ctx.remove_class)(cls)


def fmt_secs(s):
    s = max(0, int(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def label(text="", cls=None, xalign=0.0, ellipsize=True, lines=1):
    lb = Gtk.Label(label=text, xalign=xalign)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if lines > 1:
        lb.set_line_wrap(True)
        lb.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lb.set_lines(lines)
    if cls:
        for c in cls.split():
            lb.get_style_context().add_class(c)
    return lb


def icon(name, size=Gtk.IconSize.MENU, px=None):
    img = Gtk.Image.new_from_icon_name(name, size)
    if px:
        img.set_pixel_size(px)
    return img


def button(cls, child=None, cb=None, tooltip=None, text=None):
    b = Gtk.Button(label=text) if text else Gtk.Button()
    for c in cls.split():
        b.get_style_context().add_class(c)
    if child is not None:
        b.add(child)
    if cb:
        b.connect("clicked", lambda *_: cb())
    if tooltip:
        b.set_tooltip_text(tooltip)
    return b


def clear(box):
    for ch in box.get_children():
        box.remove(ch)
        ch.destroy()


def run(argv, cb=None, stdin=None):
    """Lanza un proceso sin bloquear; cb(ok, stdout, stderr)."""
    flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
    if stdin is not None:
        flags |= Gio.SubprocessFlags.STDIN_PIPE
    launcher = Gio.SubprocessLauncher.new(flags)
    launcher.setenv("LC_ALL", "C", True)
    try:
        proc = launcher.spawnv(argv)
    except GLib.Error as e:
        if cb:
            cb(False, "", str(e))
        return

    def done(p, res):
        try:
            _ok, out, err = p.communicate_utf8_finish(res)
        except GLib.Error as e:
            if cb:
                cb(False, "", str(e))
            return
        if cb:
            cb(p.get_exit_status() == 0, out or "", err or "")

    proc.communicate_utf8_async(stdin, None, done)


def launch_desktop(entry):
    for name in (entry, entry.lower()):
        if not name:
            continue
        try:
            info = Gio.DesktopAppInfo.new(name if name.endswith(".desktop") else name + ".desktop")
        except TypeError:
            info = None
        if info:
            try:
                info.launch([], None)
                return True
            except GLib.Error:
                pass
    return False


def open_uri(uri):
    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
    except GLib.Error:
        subprocess.Popen(["xdg-open", uri])


def strip_markup(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def nm_split(line):
    parts = re.split(r"(?<!\\):", line)
    return [p.replace("\\:", ":").replace("\\\\", "\\") for p in parts]


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha():
    t = time.localtime()
    return f"{DIAS[t.tm_wday].capitalize()} {t.tm_mday} de {MESES[t.tm_mon - 1]}"


def play_sound(*names):
    """Reproduce el primer sonido freedesktop que exista."""
    for n in names:
        snd = os.path.join("/usr/share/sounds/freedesktop/stereo", n)
        if os.path.exists(snd):
            try:
                subprocess.Popen(["pw-play", snd], stderr=subprocess.DEVNULL)
            except OSError:
                pass
            return


def bat_icon(pct, charging):
    lvl = "full" if pct > 85 else "good" if pct > 50 else "low" if pct > 20 else "caution"
    return f"battery-{lvl}{'-charging' if charging else ''}-symbolic"


def ago(ts):
    d = time.time() - ts
    if d < 60:
        return "ahora"
    if d < 3600:
        return f"hace {int(d // 60)} min"
    return time.strftime("%H:%M", time.localtime(ts))


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


class Media:
    """Reproductores MPRIS por D-Bus."""
    PREFIX, PATH, IFACE = "org.mpris.MediaPlayer2.", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player"

    def __init__(self, bus):
        self.bus = bus
        self.last_active = None

    def _call(self, name, path, iface, method, params, rtype, timeout=300):
        return self.bus.call_sync(name, path, iface, method, params,
                                  GLib.VariantType(rtype) if rtype else None,
                                  Gio.DBusCallFlags.NONE, timeout, None)

    def poll(self):
        try:
            names = self._call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                               "ListNames", None, "(as)").unpack()[0]
        except GLib.Error:
            return None
        found = {}
        for n in names:
            if not n.startswith(self.PREFIX):
                continue
            try:
                props = self._call(n, self.PATH, "org.freedesktop.DBus.Properties", "GetAll",
                                   GLib.Variant("(s)", (self.IFACE,)), "(a{sv})").unpack()[0]
            except GLib.Error:
                continue
            meta = props.get("Metadata") or {}
            title = meta.get("xesam:title") or ""
            status = props.get("PlaybackStatus", "Stopped")
            if not title or status not in ("Playing", "Paused"):
                continue
            artist = meta.get("xesam:artist") or []
            if isinstance(artist, str):
                artist = [artist]
            found[n] = {
                "name": n, "title": title,
                "artist": ", ".join(a for a in artist if a),
                "album": meta.get("xesam:album") or "",
                "art": meta.get("mpris:artUrl") or "",
                "length": (meta.get("mpris:length") or 0) / 1e6,
                "position": (props.get("Position") or 0) / 1e6,
                "playing": status == "Playing",
            }
        if not found:
            self.last_active = None
            return None
        playing = [p for p in found.values() if p["playing"]]
        if playing:
            pick = next((p for p in playing if p["name"] == self.last_active), playing[0])
        else:
            pick = found.get(self.last_active) or next(iter(found.values()))
        self.last_active = pick["name"]
        return pick

    def command(self, name, method):
        self.bus.call(name, self.PATH, self.IFACE, method, None, None,
                      Gio.DBusCallFlags.NONE, 1000, None, None, None)


class Volume:
    def __init__(self, on_change):
        self.on_change = on_change
        self.value, self.muted = self.read()
        self._pending = None
        try:
            launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE)
            launcher.setenv("LC_ALL", "C", True)
            self.proc = launcher.spawnv(["pactl", "subscribe"])
            self.stream = Gio.DataInputStream.new(self.proc.get_stdout_pipe())
            self.stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line)
        except GLib.Error:
            self.proc = None

    @staticmethod
    def read():
        try:
            out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                                 capture_output=True, text=True, timeout=1).stdout
            m = re.search(r"([\d.]+)", out)
            return (float(m.group(1)) if m else 0.0), ("MUTED" in out)
        except Exception:
            return 0.0, False

    def _on_line(self, stream, res):
        try:
            line, _ = stream.read_line_finish_utf8(res)
        except GLib.Error:
            return
        if line is None:
            return
        if "on sink" in line or "on server" in line:
            if self._pending is None:
                self._pending = GLib.timeout_add(40, self._check)
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line)

    def _check(self):
        self._pending = None
        v, m = self.read()
        if abs(v - self.value) > 0.004 or m != self.muted:
            self.value, self.muted = v, m
            self.on_change(v, m)
        return False

    @staticmethod
    def step(up):
        subprocess.Popen(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%+" if up else "5%-"])

    @staticmethod
    def set(value):
        subprocess.Popen(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", f"{value:.2f}"])

    @staticmethod
    def toggle_mute():
        subprocess.Popen(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])


class ChargeLimit:
    """Cuidado de batería: UPower limita la carga (normalmente al 80 %) si el portátil lo soporta."""

    def __init__(self, sysbus, on_change):
        self.bus, self.on_change, self.proxy = sysbus, on_change, None
        try:
            paths = sysbus.call_sync("org.freedesktop.UPower", "/org/freedesktop/UPower", "org.freedesktop.UPower",
                                     "EnumerateDevices", None, GLib.VariantType("(ao)"), 0, 2000, None).unpack()[0]
            for path in paths:
                px = Gio.DBusProxy.new_sync(sysbus, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.UPower",
                                            path, "org.freedesktop.UPower.Device", None)
                typ, sup = px.get_cached_property("Type"), px.get_cached_property("ChargeThresholdSupported")
                if typ is not None and typ.unpack() == 2 and sup is not None and sup.unpack():
                    self.proxy = px
                    px.connect("g-properties-changed", lambda *_: on_change())
                    break
        except GLib.Error:
            self.proxy = None

    def _get(self, prop, default):
        v = self.proxy.get_cached_property(prop) if self.proxy else None
        return v.unpack() if v is not None else default

    @property
    def supported(self):
        return self.proxy is not None

    @property
    def enabled(self):
        return bool(self._get("ChargeThresholdEnabled", False))

    @property
    def end(self):
        return int(self._get("ChargeEndThreshold", 80))

    def toggle(self):
        if not self.proxy:
            return
        self.bus.call("org.freedesktop.UPower", self.proxy.get_object_path(), "org.freedesktop.UPower.Device",
                      "EnableChargeThreshold", GLib.Variant("(b)", (not self.enabled,)), None,
                      Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, 30000, None,
                      lambda *_: self.on_change())


class Battery:
    CHARGING, DISCHARGING, FULL, PENDING = 1, 2, 4, 5
    LOW = 20

    def __init__(self, on_event, target=lambda: 100):
        """target(): porcentaje al que se considera «carga completa» (100 o el tope de cuidado)."""
        self.on_event, self.target = on_event, target
        self.low_warned = False
        try:
            self.proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.UPower",
                "/org/freedesktop/UPower/devices/DisplayDevice", "org.freedesktop.UPower.Device", None)
            self.proxy.connect("g-properties-changed", self._changed)
        except GLib.Error:
            self.proxy = None
        self.state = self._get("State", 0)
        # si al arrancar ya está llena y enchufada, no avisar de nuevo
        self.full_warned = self.state != self.DISCHARGING and self._is_full(self.state, self.percent)

    def _is_full(self, st, pct):
        return st == self.FULL or pct >= self.target() - 1

    def _get(self, prop, default):
        if not self.proxy:
            return default
        v = self.proxy.get_cached_property(prop)
        return v.unpack() if v is not None else default

    @property
    def present(self):
        return bool(self._get("IsPresent", False))

    @property
    def percent(self):
        return float(self._get("Percentage", 0))

    @property
    def charging(self):
        return self.state in (self.CHARGING, self.FULL)

    def _changed(self, *_):
        st, pct = self._get("State", 0), self.percent
        if st != self.state:
            if st == self.CHARGING and self.state not in (self.FULL, self.PENDING):
                self.on_event("charging", pct)
            elif st == self.DISCHARGING and self.state in (self.CHARGING, self.FULL, self.PENDING):
                self.on_event("unplugged", pct)
            self.state = st
        # batería baja: una vez al bajar del 20 %, se rearma al cargar o subir del 22 %
        if st == self.DISCHARGING and pct <= self.LOW and not self.low_warned:
            self.low_warned = True
            self.on_event("low", pct)
        if st != self.DISCHARGING or pct > self.LOW + 2:
            self.low_warned = False
        # carga completa (100 % o el tope): una vez por ciclo, se rearma al desenchufar o bajar del tope
        if st != self.DISCHARGING and self._is_full(st, pct) and not self.full_warned:
            self.full_warned = True
            self.on_event("full", pct)
        if st == self.DISCHARGING or pct < self.target() - 3:
            self.full_warned = False


class Notifications:
    """Escucha las notificaciones que recibe el servidor de Budgie (Teams, correo, sistema...)."""
    DEST, PATH, IFACE = "org.budgie_desktop.Notifications", "/org/budgie_desktop/Notifications", \
        "org.buddiesofbudgie.budgie.Dispatcher"

    def __init__(self, bus, on_notify, on_dnd):
        self.bus, self.on_notify, self.on_dnd = bus, on_notify, on_dnd
        self.dnd = False
        bus.signal_subscribe(None, self.IFACE, "NotificationAdded", self.PATH, None,
                             Gio.DBusSignalFlags.NONE, self._added)
        bus.signal_subscribe(None, self.IFACE, "DoNotDisturbChanged", self.PATH, None,
                             Gio.DBusSignalFlags.NONE, self._dnd_changed)
        try:
            self.dnd = bus.call_sync(self.DEST, self.PATH, self.IFACE, "GetDoNotDisturb", None,
                                     GLib.VariantType("(b)"), 0, 500, None).unpack()[0]
        except GLib.Error:
            pass

    def _added(self, _c, _s, _p, _i, _sig, params):
        app, nid, app_icon, summary, body, _actions, hints, _exp = params.unpack()
        pb = None
        data = hints.get("image-data") or hints.get("image_data") or hints.get("icon_data")
        if data:
            try:
                w, h, stride, alpha, bits, _ch, raw = data
                pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(raw)), GdkPixbuf.Colorspace.RGB,
                                                     alpha, bits, w, h, stride)
            except Exception:
                pb = None
        path = hints.get("image-path") or hints.get("image_path") or ""
        if not pb and app_icon and (app_icon.startswith("/") or app_icon.startswith("file://")):
            path = path or app_icon
            app_icon = ""
        if not pb and path:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path.replace("file://", ""), 96, 96)
            except GLib.Error:
                pb = None
        self.on_notify({
            "id": nid, "app": app or "Sistema", "icon": app_icon or "preferences-system-notifications-symbolic",
            "pixbuf": pb, "summary": strip_markup(summary), "body": strip_markup(body),
            "desktop": hints.get("desktop-entry") or "", "time": time.time(),
            "urgent": hints.get("urgency") == 2,
        })

    def _dnd_changed(self, _c, _s, _p, _i, _sig, params):
        self.dnd = params.unpack()[0]
        self.on_dnd()

    def toggle_dnd(self):
        self.bus.call(self.DEST, self.PATH, self.IFACE, "ToggleDoNotDisturb", None, None, 0, 1000, None,
                      lambda *_: None)

    def open_center(self):
        self.bus.call("org.budgie_desktop.Raven", "/org/budgie_desktop/Raven", "org.budgie_desktop.Raven",
                      "ToggleNotificationsView", None, None, 0, 1000, None, lambda *_: None)


TEAMS_APP = "chrome-ompifgpmddkgmclendfeacglnodjjndh-Default"      # PWA de Teams en Chrome
GITHUB_APP = "chrome-mjoklplbddabcmpepnokjaffbmgbkkgg-Default"     # PWA de GitHub en Chrome
OUTLOOK_URL = "https://outlook.office.com/mail/"
_ORIGIN_LINE = re.compile(r"^\s*[\w.-]+\.(?:com|net|org|io|us)\s*$", re.I)


def ms_kind(n):
    """¿Esta notificación viene de Teams o de Outlook? (llegan desde Chrome / sus PWA)."""
    text = " ".join((n.get("app", ""), n.get("desktop", ""), n.get("summary", ""), n.get("body", ""))).lower()
    if "ompifgpmddkgmclendfeacglnodjjndh" in text or "teams" in text:
        return "teams"
    if "outlook" in text or "office.com" in text or "office365" in text:
        return "outlook"
    return None


def clean_body(body):
    """Quita la línea con el dominio (p. ej. «teams.microsoft.com») que Chrome agrega al texto."""
    lines = [ln for ln in (body or "").splitlines() if ln.strip() and not _ORIGIN_LINE.match(ln)]
    return "\n".join(lines)


def ago_long(ts):
    """«hace 5 min», «hace 3 h», «ayer», «hace 4 días», «13 nov»."""
    d = time.time() - ts
    if d < 60:
        return "ahora"
    if d < 3600:
        return f"hace {int(d // 60)} min"
    if d < 86400:
        return f"hace {int(d // 3600)} h"
    days = int(d // 86400)
    if days == 1:
        return "ayer"
    if days < 7:
        return f"hace {days} días"
    meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    t = time.localtime(ts)
    return f"{t.tm_mday} {meses[t.tm_mon - 1]}"


def iso_ts(s):
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return time.time()


class GitHub:
    """PR de GitHub usando la sesión de la herramienta `gh` (gh auth login). Se actualiza cada 3 minutos."""
    FIELDS = """... on PullRequest { id number title url isDraft updatedAt mergedAt reviewDecision
        repository { nameWithOwner } author { login }
        commits(last: 1) { nodes { commit { statusCheckRollup { state } } } } }"""

    def __init__(self, on_change, on_event):
        self.on_change, self.on_event = on_change, on_event
        self.state, self.error = "loading", ""
        self.login, self.review, self.mine, self.merged = None, [], [], []
        self.updated, self.loading = 0.0, False
        self._known = None        # PR con revisión pedida ya vistas (None = primera carga, no avisar)
        self._prev = {}           # estado anterior de mis PR (CI y revisión)
        self.refresh()
        GLib.timeout_add_seconds(180, lambda: (self.refresh(), True)[1])

    def refresh(self):
        if self.loading:
            return
        if not GLib.find_program_in_path("gh"):
            self.state = "nogh"
            self.on_change()
            return
        self.loading = True
        self.on_change()
        if self.login is None:
            run(["gh", "api", "user", "--jq", ".login"], self._got_login)
        else:
            self._query()

    def _got_login(self, ok, out, err):
        if not ok:
            return self._fail(err)
        self.login = out.strip()
        self._query()

    def _query(self):
        q = ("query { mine: search(query: \"is:pr is:open archived:false author:%s\", type: ISSUE, first: 25) "
             "{ nodes { %s } } review: search(query: \"is:pr is:open archived:false review-requested:%s\", "
             "type: ISSUE, first: 25) { nodes { %s } } "
             "merged: search(query: \"is:pr is:merged author:%s merged:>=%s\", type: ISSUE, first: 10) "
             "{ nodes { %s } } }") % (self.login, self.FIELDS, self.login, self.FIELDS, self.login,
                                      time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400)),
                                      self.FIELDS)
        run(["gh", "api", "graphql", "-f", "query=" + q], self._done)

    def _fail(self, err):
        self.loading = False
        low = err.lower()
        if "auth login" in low or "not logged" in low or "authentication" in low or "401" in low:
            self.state, self.login = "noauth", None
        else:
            self.state, self.error = "error", "No se pudo consultar GitHub (¿sin conexión?)"
        dbg("github error:", err.strip()[:200])
        self.on_change()

    @staticmethod
    def _pr(node):
        commits = (node.get("commits") or {}).get("nodes") or []
        roll = (commits[0]["commit"].get("statusCheckRollup") or {}) if commits else {}
        return {"id": node["id"], "num": node["number"], "title": node["title"], "url": node["url"],
                "repo": node["repository"]["nameWithOwner"], "author": (node.get("author") or {}).get("login", ""),
                "draft": node.get("isDraft"), "updated": iso_ts(node.get("updatedAt")),
                "merged": iso_ts(node["mergedAt"]) if node.get("mergedAt") else None,
                "review": node.get("reviewDecision"), "ci": roll.get("state")}

    def _done(self, ok, out, err):
        if not ok:
            return self._fail(err)
        try:
            data = json.loads(out)["data"]
            mine = [self._pr(n) for n in data["mine"]["nodes"] if n]
            review = [self._pr(n) for n in data["review"]["nodes"] if n]
            merged = [self._pr(n) for n in data["merged"]["nodes"] if n]
        except (ValueError, KeyError, TypeError) as e:
            return self._fail(str(e))
        self.loading, self.state, self.updated = False, "ok", time.time()
        self.mine = sorted(mine, key=lambda p: -p["updated"])
        self.review = sorted(review, key=lambda p: -p["updated"])
        self.merged = sorted(merged, key=lambda p: -p["merged"])
        self._notify_changes()
        self.on_change()

    def _notify_changes(self):
        # primero CI y revisiones de mis PR; al final las revisiones pedidas, que son lo más importante
        for p in self.mine:
            old = self._prev.get(p["id"])
            if old:
                if old["ci"] in ("PENDING", "EXPECTED") and p["ci"] in ("SUCCESS", "FAILURE", "ERROR"):
                    self.on_event("ci", p)
                if p["review"] != old["review"] and p["review"] in ("APPROVED", "CHANGES_REQUESTED"):
                    self.on_event("decision", p)
        self._prev = {p["id"]: {"ci": p["ci"], "review": p["review"]} for p in self.mine}
        ids = {p["id"] for p in self.review}
        if self._known is not None:
            for p in self.review:
                if p["id"] not in self._known:
                    self.on_event("review", p)
        self._known = ids

    @staticmethod
    def describe(p, mine):
        """Texto secundario y color de una PR."""
        bits = [f"{p['repo']}#{p['num']}"]
        if p.get("merged"):
            return " · ".join(bits + [f"fusionada {ago_long(p['merged'])}"]), None
        if not mine and p["author"]:
            bits.append(p["author"])
        if p["draft"]:
            bits.append("Borrador")
        ci = {"SUCCESS": "✓ CI", "FAILURE": "✗ CI", "ERROR": "✗ CI", "PENDING": "● CI en curso",
              "EXPECTED": "● CI en curso"}.get(p["ci"])
        if ci:
            bits.append(ci)
        rv = {"APPROVED": "Aprobada", "CHANGES_REQUESTED": "Cambios pedidos",
              "REVIEW_REQUIRED": "Falta revisión"}.get(p["review"])
        if rv and mine:
            bits.append(rv)
        bits.append(ago_long(p["updated"]))
        accent = None
        if p["ci"] in ("FAILURE", "ERROR"):
            accent = "red"
        elif p["review"] == "CHANGES_REQUESTED":
            accent = "orange"
        elif mine and p["review"] == "APPROVED" and p["ci"] in (None, "SUCCESS"):
            accent = "green"
        return " · ".join(bits), accent


class Clipboard:
    """Historial de texto copiado (solo en memoria, no se guarda en disco)."""
    SEP = "\x1e"

    def __init__(self, on_change):
        self.on_change = on_change
        self.items = []
        script = ("wl-paste -l 2>/dev/null | grep -q x-kde-passwordManagerHint && exit 0; "
                  "cat; printf '\\036'")
        try:
            self.proc = Gio.Subprocess.new(["wl-paste", "-n", "-t", "text", "--watch", "sh", "-c", script],
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


class Bluetooth:
    def __init__(self, sysbus, on_change, on_connect):
        self.bus, self.on_change, self.on_connect = sysbus, on_change, on_connect
        self.adapter, self.powered, self.devices, self.busy = None, False, {}, set()
        sysbus.signal_subscribe("org.bluez", "org.freedesktop.DBus.Properties", "PropertiesChanged", None,
                                None, Gio.DBusSignalFlags.NONE, self._props)
        for sig in ("InterfacesAdded", "InterfacesRemoved"):
            sysbus.signal_subscribe("org.bluez", "org.freedesktop.DBus.ObjectManager", sig, None, None,
                                    Gio.DBusSignalFlags.NONE, lambda *_: self.refresh())
        self.refresh()

    @property
    def available(self):
        return self.adapter is not None

    def refresh(self):
        def done(bus, res):
            try:
                objs = bus.call_finish(res).unpack()[0]
            except GLib.Error:
                self.adapter = None
                return
            self.adapter, devs = None, {}
            for path, ifaces in objs.items():
                if "org.bluez.Adapter1" in ifaces and self.adapter is None:
                    self.adapter = path
                    self.powered = bool(ifaces["org.bluez.Adapter1"].get("Powered"))
                d = ifaces.get("org.bluez.Device1")
                if d and (d.get("Paired") or d.get("Connected")):
                    bat = ifaces.get("org.bluez.Battery1", {}).get("Percentage")
                    devs[path] = {"path": path, "name": d.get("Alias") or d.get("Name") or "Dispositivo",
                                  "connected": bool(d.get("Connected")),
                                  "icon": (d.get("Icon") or "bluetooth-active") + "-symbolic", "battery": bat}
            self.devices = devs
            self.on_change()
        self.bus.call("org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", None,
                      GLib.VariantType("(a{oa{sa{sv}}})"), 0, 2000, None, done)

    def _props(self, _c, _s, path, _i, _sig, params):
        iface, changed, _inv = params.unpack()
        if iface == "org.bluez.Device1" and "Connected" in changed and path in self.devices:
            self.on_connect(self.devices[path]["name"], bool(changed["Connected"]),
                            self.devices[path]["icon"])
        if iface in ("org.bluez.Adapter1", "org.bluez.Device1", "org.bluez.Battery1"):
            self.refresh()

    def set_powered(self, on):
        if not self.adapter:
            return
        self.bus.call("org.bluez", self.adapter, "org.freedesktop.DBus.Properties", "Set",
                      GLib.Variant("(ssv)", ("org.bluez.Adapter1", "Powered", GLib.Variant("b", on))),
                      None, 0, 3000, None, lambda *_: self.refresh())

    def toggle_device(self, path):
        dev = self.devices.get(path)
        if not dev or path in self.busy:
            return
        self.busy.add(path)
        self.on_change()

        def done(bus, res):
            self.busy.discard(path)
            try:
                bus.call_finish(res)
            except GLib.Error:
                pass
            self.refresh()
        self.bus.call("org.bluez", path, "org.bluez.Device1", "Disconnect" if dev["connected"] else "Connect",
                      None, None, 0, 30000, None, done)


class Wifi:
    def __init__(self, sysbus, on_change):
        self.on_change = on_change
        self.enabled, self.active, self.wired, self.nets, self.known = False, None, False, [], set()
        self.busy, self.error, self.scanning = None, None, False
        try:
            self.nm = Gio.DBusProxy.new_sync(sysbus, Gio.DBusProxyFlags.NONE, None,
                                             "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
                                             "org.freedesktop.NetworkManager", None)
            self.nm.connect("g-properties-changed", lambda *_: self.refresh())
        except GLib.Error:
            self.nm = None
        self.refresh()

    def refresh(self):
        if self.nm:
            v = self.nm.get_cached_property("WirelessEnabled")
            self.enabled = bool(v.unpack()) if v is not None else False

        def active(ok, out, _err):
            self.active, self.wired = None, False
            for line in out.splitlines():
                f = nm_split(line)
                if len(f) >= 2 and f[1] == "802-11-wireless":
                    self.active = f[0]
                elif len(f) >= 2 and f[1] == "802-3-ethernet":
                    self.wired = True
            self.on_change()
        run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"], active)

        def known(ok, out, _err):
            self.known = {f[0] for f in map(nm_split, out.splitlines()) if len(f) > 1 and f[1] == "802-11-wireless"}
        run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], known)

    def scan(self):
        if not self.enabled or self.scanning:
            return
        self.scanning = True
        self.on_change()

        def done(ok, out, _err):
            self.scanning = False
            nets = {}
            for line in out.splitlines():
                f = nm_split(line)
                if len(f) < 4 or not f[1]:
                    continue
                inuse, ssid, sig, sec = f[0] == "*", f[1], int(f[2] or 0), f[3]
                prev = nets.get(ssid)
                if prev is None or sig > prev["signal"] or inuse:
                    nets[ssid] = {"ssid": ssid, "signal": sig, "secure": bool(sec and sec != "--"),
                                  "inuse": inuse or bool(prev and prev["inuse"])}
            self.nets = sorted(nets.values(), key=lambda n: (not n["inuse"], -n["signal"]))[:15]
            self.on_change()
        run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "auto"], done)

    def set_enabled(self, on):
        run(["nmcli", "radio", "wifi", "on" if on else "off"], lambda *_: GLib.timeout_add(800, self._later))

    def _later(self):
        self.refresh()
        GLib.timeout_add(300, lambda: (self.scan(), False)[1])
        return False

    def connect(self, net, password=None, on_need_password=None):
        ssid = net["ssid"]
        if ssid in self.known and password is None:
            argv = ["nmcli", "connection", "up", "id", ssid]
        elif net["secure"] and password is None:
            if on_need_password:
                on_need_password(net)
            return
        else:
            argv = ["nmcli", "device", "wifi", "connect", ssid] + (["password", password] if password else [])
        self.busy, self.error = ssid, None
        self.on_change()

        def done(ok, _out, err):
            self.busy = None
            if not ok:
                low = err.lower()
                self.error = "No se pudo conectar" + (" (¿contraseña?)" if "secret" in low or "password" in low
                                                      else "")
            self.refresh()
            self.scan()
        run(argv, done)


class Radios:
    """Modo avión con rfkill."""

    def __init__(self, on_change):
        self.on_change = on_change
        self.airplane = False
        self.refresh()

    def refresh(self):
        def done(ok, out, _err):
            states = [s.strip() for s in out.splitlines() if s.strip()]
            self.airplane = bool(states) and all(s == "blocked" for s in states)
            self.on_change()
        run(["rfkill", "-n", "-o", "SOFT"], done)

    def toggle(self):
        run(["rfkill", "unblock" if self.airplane else "block", "all"], lambda *_: GLib.timeout_add(400, self._r))

    def _r(self):
        self.refresh()
        return False


class Modes:
    """Modo oscuro, luz nocturna, ahorro de energía y mantener despierto."""

    def __init__(self, sysbus, bus, on_change):
        self.on_change, self.sysbus, self.bus = on_change, sysbus, bus
        src = Gio.SettingsSchemaSource.get_default()
        self.iface = Gio.Settings.new("org.gnome.desktop.interface")
        self.iface.connect("changed::color-scheme", lambda *_: on_change())
        self.color = None
        if src.lookup("org.gnome.settings-daemon.plugins.color", True):
            self.color = Gio.Settings.new("org.gnome.settings-daemon.plugins.color")
            self.color.connect("changed::night-light-enabled", lambda *_: on_change())
        try:
            self.pp = Gio.DBusProxy.new_sync(sysbus, Gio.DBusProxyFlags.NONE, None, "net.hadess.PowerProfiles",
                                             "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles", None)
            self.pp.connect("g-properties-changed", lambda *_: on_change())
        except GLib.Error:
            self.pp = None
        self.inhibit_cookie = None

    @property
    def dark(self):
        return self.iface.get_string("color-scheme") == "prefer-dark"

    def toggle_dark(self):
        dark = not self.dark
        self.iface.set_string("color-scheme", "prefer-dark" if dark else "default")
        theme = self.iface.get_string("gtk-theme")
        base = re.sub(r"-(dark|darkest|light)$", "", theme)
        cand = base + "-dark" if dark else base
        dirs = ["/usr/share/themes", os.path.expanduser("~/.themes"), os.path.expanduser("~/.local/share/themes")]
        if cand != theme and any(os.path.isdir(os.path.join(d, cand)) for d in dirs):
            self.iface.set_string("gtk-theme", cand)

    @property
    def night(self):
        return bool(self.color and self.color.get_boolean("night-light-enabled"))

    def toggle_night(self):
        if self.color:
            self.color.set_boolean("night-light-enabled", not self.night)

    @property
    def profile(self):
        v = self.pp.get_cached_property("ActiveProfile") if self.pp else None
        return v.unpack() if v is not None else None

    def toggle_saver(self):
        if not self.pp:
            return
        new = "balanced" if self.profile == "power-saver" else "power-saver"
        self.sysbus.call("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "org.freedesktop.DBus.Properties",
                         "Set", GLib.Variant("(ssv)", ("net.hadess.PowerProfiles", "ActiveProfile",
                                                       GLib.Variant("s", new))),
                         None, 0, 2000, None, lambda *_: self.on_change())

    @property
    def awake(self):
        return self.inhibit_cookie is not None

    def toggle_awake(self):
        if self.inhibit_cookie is not None:
            try:
                self.bus.call_sync("org.gnome.SessionManager", "/org/gnome/SessionManager",
                                   "org.gnome.SessionManager", "Uninhibit",
                                   GLib.Variant("(u)", (self.inhibit_cookie,)), None, 0, 1000, None)
            except GLib.Error:
                pass
            self.inhibit_cookie = None
        else:
            try:
                self.inhibit_cookie = self.bus.call_sync(
                    "org.gnome.SessionManager", "/org/gnome/SessionManager", "org.gnome.SessionManager", "Inhibit",
                    GLib.Variant("(susu)", ("isla-dinamica", 0, "Mantener despierto", 4 | 8)),
                    GLib.VariantType("(u)"), 0, 1000, None).unpack()[0]
            except GLib.Error:
                self.inhibit_cookie = None
        self.on_change()


class Drives:
    """Medios extraíbles (USB, tarjetas SD, teléfonos)."""

    def __init__(self, on_change, on_event):
        self.on_change, self.on_event = on_change, on_event
        self.vm = Gio.VolumeMonitor.get()
        for sig in ("volume-removed", "mount-added", "mount-removed", "volume-changed"):
            self.vm.connect(sig, lambda *_: self.on_change())
        self.vm.connect("volume-added", self._added)

    @staticmethod
    def _removable(v):
        d = v.get_drive()
        return v.can_eject() or (d is not None and (d.is_removable() or d.can_eject()))

    def items(self):
        return [v for v in self.vm.get_volumes() if self._removable(v)]

    def _added(self, _vm, v):
        self.on_change()
        if self._removable(v):
            self.on_event("usb", v.get_name(), v)

    def open(self, v):
        m = v.get_mount()
        if m:
            open_uri(m.get_root().get_uri())
            return

        def done(vol, res):
            try:
                vol.mount_finish(res)
                open_uri(vol.get_mount().get_root().get_uri())
            except (GLib.Error, AttributeError):
                pass
            self.on_change()
        v.mount(Gio.MountMountFlags.NONE, Gio.MountOperation(), None, done)

    def eject(self, v):
        name = v.get_name()

        def done_eject(obj, res):
            self._finish(obj.eject_with_operation_finish, res, name)

        def done_unmount(obj, res):
            self._finish(obj.unmount_with_operation_finish, res, name)
        if v.can_eject():
            v.eject_with_operation(Gio.MountUnmountFlags.NONE, None, None, done_eject)
        elif v.get_mount():
            v.get_mount().unmount_with_operation(Gio.MountUnmountFlags.NONE, None, None, done_unmount)

    def _finish(self, fn, res, name):
        try:
            fn(res)
            self.on_event("ejected", name, None)
        except GLib.Error as e:
            self.on_event("eject-failed", f"{name}: {e.message}", None)
        self.on_change()


class Power:
    def __init__(self, sysbus, bus):
        self.sysbus, self.bus = sysbus, bus

    def _login1(self, method):
        self.sysbus.call("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
                         method, GLib.Variant("(b)", (True,)), None, 0, 10000, None, lambda *_: None)

    def lock(self):
        run(["loginctl", "lock-session"])

    def logout(self):
        self.bus.call("org.gnome.SessionManager", "/org/gnome/SessionManager", "org.gnome.SessionManager",
                      "Logout", GLib.Variant("(u)", (1,)), None, 0, 5000, None, lambda *_: None)

    def suspend(self):
        self._login1("Suspend")

    def reboot(self):
        self._login1("Reboot")

    def poweroff(self):
        self._login1("PowerOff")


# ───────────────────────────── configuración, clima y pomodoro ─────────────────────────────
CONFIG_PATH = os.path.join(GLib.get_user_config_dir(), "isla-dinamica", "config.json")
DEFAULTS = {"city": None,
            "dock": {"edge": "top", "pos": 0.5},
            "pomodoro": {"work": 25, "short": 5, "long": 15, "every": 4, "auto": True}}


class Config:
    """Preferencias guardadas en ~/.config/isla-dinamica/config.json."""

    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULTS))
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            self.data["city"] = loaded.get("city") or None
            dock = loaded.get("dock") or {}
            if dock.get("edge") in ("top", "bottom", "left", "right"):
                self.data["dock"] = {"edge": dock["edge"],
                                     "pos": min(1.0, max(0.0, float(dock.get("pos", 0.5))))}
            self.data["pomodoro"].update({k: v for k, v in (loaded.get("pomodoro") or {}).items()
                                          if k in DEFAULTS["pomodoro"]})
        except (OSError, ValueError, AttributeError):
            pass

    def save(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)


def tz_city():
    try:
        tz = os.path.realpath("/etc/localtime").split("zoneinfo/")[-1]
        return tz.split("/")[-1].replace("_", " ")
    except OSError:
        return "Bogota"


WMO = {0: ("Despejado", "clear"), 1: ("Mayormente despejado", "clear"), 2: ("Parcialmente nublado", "few-clouds"),
       3: ("Nublado", "overcast"), 45: ("Niebla", "fog"), 48: ("Niebla", "fog"),
       51: ("Llovizna ligera", "showers-scattered"), 53: ("Llovizna", "showers-scattered"),
       55: ("Llovizna intensa", "showers"), 56: ("Llovizna helada", "showers"), 57: ("Llovizna helada", "showers"),
       61: ("Lluvia ligera", "showers-scattered"), 63: ("Lluvia", "showers"), 65: ("Lluvia fuerte", "showers"),
       66: ("Lluvia helada", "showers"), 67: ("Lluvia helada", "showers"), 71: ("Nieve ligera", "snow"),
       73: ("Nieve", "snow"), 75: ("Nieve intensa", "snow"), 77: ("Granizo", "snow"),
       80: ("Chubascos", "showers-scattered"), 81: ("Chubascos", "showers"), 82: ("Chubascos fuertes", "showers"),
       85: ("Chubascos de nieve", "snow"), 86: ("Chubascos de nieve", "snow"), 95: ("Tormenta", "storm"),
       96: ("Tormenta con granizo", "storm"), 99: ("Tormenta con granizo", "storm")}


WMO_KIND = {0: "clear", 1: "clear", 2: "partly", 3: "cloudy", 45: "fog", 48: "fog",
            51: "drizzle", 53: "drizzle", 55: "drizzle", 56: "drizzle", 57: "drizzle",
            61: "rain", 63: "rain", 65: "heavy-rain", 66: "rain", 67: "heavy-rain",
            80: "rain", 81: "rain", 82: "heavy-rain",
            71: "snow", 73: "snow", 75: "snow", 77: "snow", 85: "snow", 86: "snow",
            95: "storm", 96: "storm", 99: "storm"}
RAINY = ("drizzle", "rain", "heavy-rain", "storm")


def weather_kind(code, day=True):
    k = WMO_KIND.get(code, "cloudy")
    if not day and k in ("clear", "partly"):
        k += "-night"
    return k


def weather_icon(code, day=True):
    kind = WMO.get(code, ("", "overcast"))[1]
    if not day and kind in ("clear", "few-clouds"):
        kind += "-night"
    return f"weather-{kind}-symbolic"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "isla-dinamica/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


class Weather:
    """Clima de Open-Meteo (gratis, sin cuenta). Se actualiza cada 20 minutos."""

    def __init__(self, config, on_change):
        self.cfg, self.on_change = config, on_change
        self.data, self.place, self.error, self.loading = None, None, None, False
        self.refresh()
        GLib.timeout_add_seconds(1200, lambda: (self.refresh(), True)[1])

    @property
    def city(self):
        return self.cfg.data.get("city") or tz_city()

    def set_city(self, name):
        self.cfg.data["city"] = name.strip() or None
        self.cfg.save()
        self.place = None
        self.refresh()

    def refresh(self):
        if self.loading:
            return
        self.loading = True
        self.on_change()
        city, place = self.city, self.place

        def work():
            try:
                if place is None or place["query"] != city:
                    g = fetch_json("https://geocoding-api.open-meteo.com/v1/search?count=1&language=es&name="
                                   + urllib.parse.quote(city))
                    res = (g.get("results") or [None])[0]
                    if not res:
                        raise LookupError(f"No encontré «{city}»")
                    pl = {"query": city, "name": res["name"], "lat": res["latitude"], "lon": res["longitude"]}
                else:
                    pl = place
                w = fetch_json(
                    f"https://api.open-meteo.com/v1/forecast?latitude={pl['lat']}&longitude={pl['lon']}"
                    "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,"
                    "wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,precipitation,uv_index"
                    "&hourly=temperature_2m,weather_code,is_day,precipitation_probability"
                    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                    "precipitation_sum,sunrise,sunset,uv_index_max"
                    "&timezone=auto&forecast_days=7")
                GLib.idle_add(self._done, pl, w, None)
            except LookupError as e:
                GLib.idle_add(self._done, None, None, str(e))
            except Exception:
                GLib.idle_add(self._done, None, None, "Sin conexión con el servicio del clima")

        threading.Thread(target=work, daemon=True).start()

    def _done(self, place, w, err):
        self.loading = False
        if err:
            self.error = err
        else:
            cur, daily, hourly = w["current"], w["daily"], w["hourly"]
            now_h = cur["time"][:13]
            idx = next((i for i, t in enumerate(hourly["time"]) if t[:13] > now_h), 0)
            pops = hourly.get("precipitation_probability") or [None] * len(hourly["time"])
            hours = [{"hour": hourly["time"][i][11:16], "temp": hourly["temperature_2m"][i],
                      "icon": weather_icon(hourly["weather_code"][i], hourly["is_day"][i]),
                      "kind": weather_kind(hourly["weather_code"][i], hourly["is_day"][i]),
                      "pop": pops[i]}
                     for i in range(idx, min(idx + 24, len(hourly["time"])))]
            names = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
            days = []
            for i, day in enumerate(daily["time"]):
                wd = time.strptime(day, "%Y-%m-%d").tm_wday
                days.append({"name": "Hoy" if i == 0 else "Mañana" if i == 1 else names[wd],
                             "kind": weather_kind(daily["weather_code"][i]),
                             "max": daily["temperature_2m_max"][i], "min": daily["temperature_2m_min"][i],
                             "pop": daily["precipitation_probability_max"][i]})
            # ¿lluvia o tormenta en las próximas 3 horas?
            kind_now = weather_kind(cur["weather_code"], cur["is_day"])
            soon = None
            if kind_now not in RAINY:
                soon = next((h for h in hours[:3] if h["kind"] in RAINY and (h["pop"] or 0) >= 50), None)
            self.place, self.error = place, None
            self.data = {"temp": cur["temperature_2m"], "feels": cur["apparent_temperature"],
                         "humidity": cur["relative_humidity_2m"], "wind": cur["wind_speed_10m"],
                         "code": cur["weather_code"], "day": bool(cur["is_day"]),
                         "desc": WMO.get(cur["weather_code"], ("—", ""))[0],
                         "icon": weather_icon(cur["weather_code"], cur["is_day"]),
                         "max": daily["temperature_2m_max"][0], "min": daily["temperature_2m_min"][0],
                         "rain": (daily.get("precipitation_probability_max") or [None])[0],
                         "kind": kind_now, "hours": hours, "days": days, "soon": soon,
                         "wind_dir": cur.get("wind_direction_10m"), "gusts": cur.get("wind_gusts_10m"),
                         "clouds": cur.get("cloud_cover"), "uv": cur.get("uv_index"),
                         "rain_mm": daily["precipitation_sum"][0], "uv_max": daily["uv_index_max"][0],
                         "sunrise": daily["sunrise"][0][11:16], "sunset": daily["sunset"][0][11:16],
                         "updated": time.time()}
        self.on_change()
        return False


class Pomodoro:
    LABEL = {"work": "Enfoque", "short": "Descanso", "long": "Descanso largo"}

    def __init__(self, config, on_phase_end, on_change):
        self.cfg, self.on_phase_end, self.on_change = config, on_phase_end, on_change
        self.phase, self.running, self.end, self.done, self.active = "work", False, None, 0, False
        self.remaining = self.length("work")

    @property
    def conf(self):
        return self.cfg.data["pomodoro"]

    def length(self, phase):
        return max(1, int(self.conf[phase])) * 60

    def left(self):
        return max(0.0, self.end - time.monotonic()) if self.running else self.remaining

    def start(self):
        if not self.running:
            self.end = time.monotonic() + self.remaining
            self.running = self.active = True
            self.on_change()

    def pause(self):
        if self.running:
            self.remaining = self.left()
            self.running = False
            self.on_change()

    def toggle(self):
        self.pause() if self.running else self.start()

    def reset(self):
        self.phase, self.running, self.done, self.active = "work", False, 0, False
        self.remaining = self.length("work")
        self.on_change()

    def skip(self):
        self._advance(False)

    def tick(self):
        if self.running and time.monotonic() >= self.end:
            self._advance(True)

    def _advance(self, finished):
        prev, was_running = self.phase, self.running
        every = max(1, int(self.conf["every"]))
        if prev == "work":
            self.done += 1
            nxt = "long" if self.done % every == 0 else "short"
        else:
            nxt = "work"
            if prev == "long":
                self.done = 0
        self.phase, self.running = nxt, False
        self.remaining = self.length(nxt)
        if self.conf["auto"] and (finished or was_running):
            self.start()
        if finished:
            self.on_phase_end(prev, nxt)
        self.on_change()

    def set_conf(self, key, value):
        if self.conf.get(key) == value:
            return
        self.conf[key] = value
        self.cfg.save()
        if not self.running and key == self.phase:
            self.remaining = self.length(self.phase)
        self.on_change()

    def cycle_text(self):
        every = max(1, int(self.conf["every"]))
        n = self.done % every + (1 if self.phase == "work" else 0)
        if self.phase == "long":
            n = every
        return f"Sesión {n} de {every}"


# ───────────────────────────── núcleo compartido ─────────────────────────────
class Core:
    """Estado y servicios compartidos por las islas de todas las pantallas."""

    def __init__(self, app):
        self.app = app
        self.windows = {}
        self.ver = {}
        self.media = None
        self.event = None
        self.timer_end, self.timer_total, self.alert_until = None, 0, None
        self.notifs = []
        self.unread = 0
        self._art_url, self._art_cache, self.art = None, {}, None

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sysbus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.mpris = Media(bus)
        self.volume = Volume(self._on_volume)
        self.charge_limit = ChargeLimit(sysbus, lambda: self.changed("modes"))
        self.battery = Battery(self._on_battery, self._charge_target)
        self.notif = Notifications(bus, self._on_notify, lambda: self.changed("modes"))
        self.clip = Clipboard(lambda: self.changed("clip"))
        self.bt = Bluetooth(sysbus, lambda: self.changed("bt"), self._on_bt_connect)
        self.wifi = Wifi(sysbus, lambda: self.changed("wifi"))
        self.radios = Radios(lambda: self.changed("modes"))
        self.modes = Modes(sysbus, bus, lambda: self.changed("modes"))
        self.drives = Drives(lambda: self.changed("usb"), self._on_drive)
        self.power = Power(sysbus, bus)
        self.config = Config()
        self._rain_warned = None
        self.weather = Weather(self.config, self._on_weather)
        self.pomo = Pomodoro(self.config, self._on_pomo_end, lambda: self.changed("pomo"))
        self.ms_unread = {"teams": 0, "outlook": 0}
        self.github = GitHub(lambda: self.changed("github"), self._on_github)

        # bienvenida al despertar / desbloquear
        sysbus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep",
                                "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, self._on_sleep)
        sysbus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Session", "Unlock",
                                None, None, Gio.DBusSignalFlags.NONE, lambda *_: self.welcome(True))

        display = Gdk.Display.get_default()
        display.connect("monitor-added", lambda d, m: self._add_window(m))
        display.connect("monitor-removed", self._remove_window)
        for i in range(display.get_n_monitors()):
            self._add_window(display.get_monitor(i))

        self.tick()
        GLib.timeout_add(1000, self.tick)
        if os.environ.get("ISLA_NO_WELCOME") != "1":
            GLib.timeout_add(900, self.welcome)

    # ── ventanas por pantalla ──
    def _add_window(self, monitor):
        if monitor not in self.windows:
            self.windows[monitor] = IslandWindow(self, monitor)

    def _remove_window(self, _d, monitor):
        w = self.windows.pop(monitor, None)
        if w:
            w.destroy()

    @property
    def dock(self):
        return self.config.data["dock"]

    def set_dock(self, edge, pos):
        self.config.data["dock"] = {"edge": edge, "pos": min(1.0, max(0.0, pos))}
        try:
            self.config.save()
        except OSError:
            pass
        for w in list(self.windows.values()):
            w.dock_changed()

    def changed(self, kind=None):
        if kind:
            self.ver[kind] = self.ver.get(kind, 0) + 1
        self.refresh()

    def refresh(self):
        for w in list(self.windows.values()):
            w.refresh()
        return False

    def set_hidden(self, hidden):
        for w in self.windows.values():
            (w.hide if hidden else w.show)()

    # ── avisos ──
    def show_event(self, secs=3.0, **ev):
        ev["until"] = time.monotonic() + secs
        self.event = ev
        self.refresh()
        GLib.timeout_add(int(secs * 1000) + 60, self.refresh)

    def welcome(self, back=False):
        name = (GLib.get_real_name() or "").split(" ")[0]
        if not name or name == "Unknown":
            name = GLib.get_user_name()
        if back:
            right = f"{self.battery.percent:.0f}%" if self.battery.present else time.strftime("%H:%M")
            self.show_event(3.5, kind="pill", icon="weather-clear-symbolic", text=f"Bienvenido de vuelta, {name}",
                            right=right)
        else:
            self.show_event(3.5, kind="pill", icon="face-smile-symbolic", text=f"Hola, {name}",
                            right=time.strftime("%H:%M"))
        return False

    def _on_sleep(self, _c, _s, _p, _i, _sig, params):
        if not params.unpack()[0]:          # al despertar
            self.wifi.refresh()
            self.bt.refresh()
            GLib.timeout_add(1200, lambda: self.welcome(True))

    def _on_weather(self):
        self.changed("weather")
        w = getattr(self, "weather", None)     # el primer aviso llega antes de asignarlo
        d = w and w.data
        soon = d and d.get("soon")
        if soon:
            key = time.strftime("%Y-%m-%d ") + soon["hour"]
            if key != self._rain_warned:
                self._rain_warned = key
                storm = soon["kind"] == "storm"
                self.show_event(4.0, kind="pill",
                                icon="weather-storm-symbolic" if storm else "weather-showers-symbolic",
                                accent="blue", text=f"{'Tormenta' if storm else 'Lluvia'} hacia las {soon['hour']}",
                                right=f"{soon['pop']}%", right_accent="blue")

    def _on_volume(self, v, muted):
        self.show_event(1.8, kind="volume", value=v, muted=muted)

    def _charge_target(self):
        cl = getattr(self, "charge_limit", None)
        return cl.end if cl and cl.supported and cl.enabled else 100

    def _on_battery(self, kind, pct):
        if kind == "low":
            play_sound("dialog-warning.oga", "bell.oga")
            self.show_event(12.0, kind="card", icon="battery-caution-symbolic", app="Batería",
                            title=f"Batería baja · {pct:.0f} %",
                            body="Conecta el cargador para no perder tu trabajo.", action=None)
            return
        if kind == "full":
            play_sound("complete.oga")
            target = self._charge_target()
            if target < 100:
                title = f"Batería al {target} % · tope de cuidado"
                body = (f"Se detuvo la carga en {target} % para cuidar la batería. "
                        "Si necesitas el 100 %, apaga «Cuidar batería».")
            else:
                title = "Carga completa · 100 %"
                body = "Ya puedes desconectar el cargador."
            self.show_event(10.0, kind="card", icon="battery-full-charged-symbolic", app="Batería",
                            title=title, body=body, action=None)
            return
        txt, acc, ic = {
            "charging": ("Cargando", "green", bat_icon(pct, True)),
            "unplugged": ("Con batería", None, bat_icon(pct, False)),
            "low": ("Batería baja", "red", "battery-caution-symbolic"),
        }[kind]
        right = f"{pct:.0f}%"
        if kind == "charging" and self.charge_limit.enabled:
            right += f" · hasta {self.charge_limit.end}%"
        self.show_event(4.5, kind="pill", icon=ic, accent=acc, text=txt, right=right, right_accent=acc)

    def _on_notify(self, n):
        n["ms"] = ms_kind(n)
        dbg("aviso:", n["app"], "|", n["desktop"], "|", n["summary"], "->", n["ms"])
        if n["ms"]:
            n["body"] = clean_body(n["body"])
            n["app"] = "Microsoft Teams" if n["ms"] == "teams" else "Outlook"
            n["icon"] = TEAMS_APP if n["ms"] == "teams" else "mail-unread-symbolic"
            self.ms_unread[n["ms"]] += 1
            self.ver["ms"] = self.ver.get("ms", 0) + 1
        self.notifs.insert(0, n)
        del self.notifs[60:]
        self.unread += 1
        self.changed("notifs")
        if not self.notif.dnd or n["urgent"]:
            self.show_event(9.0, kind="card", pixbuf=n["pixbuf"], icon=n["icon"], app=n["app"],
                            title=n["summary"], body=n["body"], action=lambda n=n: self.open_notif(n))

    def open_notif(self, n):
        if n.get("ms") == "teams":
            self.open_teams()
        elif n.get("ms") == "outlook":
            open_uri(OUTLOOK_URL)
        elif not launch_desktop(n.get("desktop") or "") and not launch_desktop(n["app"]):
            self.notif.open_center()

    def open_teams(self):
        if not launch_desktop(TEAMS_APP):
            open_uri("https://teams.microsoft.com/")

    def open_github(self, url=None):
        if url:
            open_uri(url)
        elif not launch_desktop(GITHUB_APP):
            open_uri("https://github.com/pulls")

    def _on_github(self, kind, p):
        ref = f"{p['repo']}#{p['num']}"
        if kind == "review":
            self.show_event(9.0, kind="card", icon=GITHUB_APP, app="GitHub · Revisión pedida",
                            title=p["title"], body=f"{ref} · {p['author']}",
                            action=lambda: self.open_github(p["url"]))
        elif kind == "ci":
            good = p["ci"] == "SUCCESS"
            self.show_event(4.0, kind="pill", icon="emblem-ok-symbolic" if good else "dialog-error-symbolic",
                            accent="green" if good else "red", text=f"CI {'pasó' if good else 'falló'} · {ref}")
        elif kind == "decision":
            good = p["review"] == "APPROVED"
            self.show_event(4.0, kind="pill", icon="emblem-ok-symbolic" if good else "document-edit-symbolic",
                            accent="green" if good else "orange",
                            text=f"{'Aprobada' if good else 'Piden cambios'} · {ref}")

    def _on_bt_connect(self, name, connected, ic):
        self.show_event(4.0, kind="pill", icon=ic, accent="blue" if connected else None,
                        text=name, right="Conectado" if connected else "Desconectado",
                        right_accent="blue" if connected else None)

    def _on_drive(self, kind, name, vol):
        if kind == "usb":
            self.show_event(7.0, kind="card", icon="media-removable-symbolic", app="Medio extraíble",
                            title=name, body="Haz clic para abrirlo", action=lambda: self.drives.open(vol))
        elif kind == "ejected":
            self.show_event(3.0, kind="pill", icon="media-eject-symbolic", accent="green",
                            text=f"Ya puedes retirar {name}")
        else:
            self.show_event(3.5, kind="pill", icon="dialog-warning-symbolic", accent="red", text=name)

    # ── temporizador ──
    def _on_pomo_end(self, prev, nxt):
        for snd in ("/usr/share/sounds/freedesktop/stereo/complete.oga",
                    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"):
            if os.path.exists(snd):
                subprocess.Popen(["pw-play", snd], stderr=subprocess.DEVNULL)
                break
        mins = self.pomo.conf[nxt]
        title = "¡Buen trabajo! Toca descansar" if prev == "work" else "¡Fin del descanso! A enfocarse"
        auto = self.pomo.running
        body = f"Siguiente: {Pomodoro.LABEL[nxt].lower()} de {mins} min" + \
            ("" if auto else " · haz clic para empezar")
        self.show_event(10.0, kind="card", icon="timer-symbolic", app="Pomodoro", title=title, body=body,
                        action=None if auto else self.pomo.start)

    def start_timer(self, secs):
        self.timer_total, self.timer_end = secs, time.monotonic() + secs
        self.refresh()

    def stop_timer(self):
        self.timer_end = None
        self.refresh()

    def dismiss_alert(self):
        self.alert_until = None
        self.refresh()

    # ── captura ──
    def screenshot(self, monitor=None):
        """Sin monitor: eliges un área con un rectángulo sobre la pantalla sombreada.
        Con monitor: captura esa pantalla completa."""
        folder = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
                              or os.path.expanduser("~/Imágenes"), "Capturas")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, time.strftime("Captura %Y-%m-%d %H-%M-%S.png"))
        self.set_hidden(True)

        def grab(geom):
            def saved(ok, _o, _err):
                self.set_hidden(False)
                if not ok:
                    self.show_event(3, kind="pill", icon="dialog-warning-symbolic", accent="red",
                                    text="No se pudo capturar")
                    return
                run(["sh", "-c", 'wl-copy -t image/png < "$1"', "sh", path])
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 160, 160)
                except GLib.Error:
                    pb = None
                self.show_event(7.0, kind="card", pixbuf=pb, icon="camera-photo-symbolic", app="Captura",
                                title="Guardada y copiada al portapapeles", body=os.path.basename(path),
                                action=lambda: open_uri(GLib.filename_to_uri(path, None)))
            run(["grim", "-g", geom, path], saved)

        def start():
            if monitor is not None:
                g = monitor.get_geometry()
                grab(f"{g.x},{g.y} {g.width}x{g.height}")
            else:
                def picked(ok, out, _e):
                    if ok and out.strip():
                        grab(out.strip())
                    else:
                        self.set_hidden(False)
                run(["slurp", "-d", "-b", "00000099", "-c", "ffffffff", "-s", "00000000", "-w", "2",
                     "-B", "ffffff22"], picked)
            return False
        GLib.timeout_add(250, start)

    # ── tic de 1 s ──
    def tick(self):
        now = time.monotonic()
        if self.timer_end and now >= self.timer_end:
            self.timer_end = None
            self.alert_until = now + 10
            for snd in ("/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
                        "/usr/share/sounds/freedesktop/stereo/complete.oga"):
                if os.path.exists(snd):
                    subprocess.Popen(["pw-play", snd], stderr=subprocess.DEVNULL)
                    break
        self.pomo.tick()
        self.media = self.mpris.poll()
        self._load_art()
        self.refresh()
        return True

    def media_cmd(self, method):
        if self.media:
            self.mpris.command(self.media["name"], method)
            GLib.timeout_add(180, lambda: (setattr(self, "media", self.mpris.poll()), self.refresh())[1])

    def _load_art(self):
        url = self.media["art"] if self.media else None
        if url == self._art_url:
            return
        self._art_url = url
        if not url:
            self.art = None
            return
        if url in self._art_cache:
            self.art = self._art_cache[url]
            return

        def done(f, res):
            pb = None
            try:
                _ok, data, _etag = f.load_contents_finish(res)
                loader = GdkPixbuf.PixbufLoader()
                loader.write(data)
                loader.close()
                pb = loader.get_pixbuf()
            except (GLib.Error, AttributeError):
                pb = None
            self._art_cache[url] = pb
            if self._art_url == url:
                self.art = pb
                self.refresh()
        Gio.File.new_for_uri(url).load_contents_async(None, done)


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


class IslandWindow(Gtk.Window):
    def __init__(self, core, monitor):
        super().__init__(title="Isla dinámica")
        core.app.add_window(self)
        self.core, self.monitor = core, monitor
        self.set_decorated(False)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "isla-dinamica")
        GtkLayerShell.set_monitor(self, monitor)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        self.hover = False
        self._hover_src = None
        self.page = "home"
        self.view = None
        self.pending = None
        self.cur = [130.0, float(H)]
        self.target = (130, H)
        self.vel = [0.0, 0.0]
        self._anim_src = None
        self.seen = {}
        self.pw_net = None
        self._confirm = None
        self._vol_lock = False
        self.card_hold = False      # ratón sobre una notificación: no se cierra
        # arrastre y acople a los bordes
        self.vertical = False       # píldora en vertical (pegada a un borde lateral)
        self.drag = None            # arrastre en curso
        self._drag_end = 0.0
        self.poff = [0.0, 0.0]      # desfase que se anima hacia 0 al soltar
        self.pvel = [0.0, 0.0]
        self._last_xy = (0, 0)      # posición (arriba-izquierda) pedida por última vez
        self._applied = (0, 0)      # posición ya aplicada por el compositor
        self._nav_t = 0.0           # cuándo se cambió de página por última vez
        self._inside = False        # ratón dentro de la ventana (según enter/leave)
        self._layout = None

        ev = Gtk.EventBox()
        ev.set_visible_window(False)
        ev.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                      Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK)
        ev.connect("scroll-event", self._on_scroll)
        # arrastre: gesto en fase de captura sobre la ventana, así recibe el clic antes que
        # cualquier hijo (botones, Stack, ScrolledWindow) y lo reclama al empezar a mover
        self._gdrag = Gtk.GestureDrag.new(self)
        self._gdrag.set_button(1)
        self._gdrag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self._gdrag.connect("drag-begin", self._on_press)
        self._gdrag.connect("drag-end", self._on_drag_end)
        ev.connect("motion-notify-event", self._on_motion)
        # entrar/salir se escucha en la ventana: GTK no propaga esos eventos desde los hijos
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        ev.connect("button-release-event", self._on_click)
        self.add(ev)

        self.stack = Gtk.Stack(hhomogeneous=False, vhomogeneous=False)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        self.stack.set_size_request(*self.target)
        ev.add(self.stack)

        for name, builder in (("compact", self._build_compact), ("card", self._build_card),
                              ("alert", self._build_alert), ("home", self._build_home),
                              ("wifi", self._build_wifi), ("bt", self._build_bt), ("clip", self._build_clip),
                              ("notifs", self._build_notifs), ("usb", self._build_usb),
                              ("timer", self._build_timer), ("power", self._build_power),
                              ("weather", self._build_weather), ("pomo", self._build_pomo),
                              ("github", self._build_github), ("ms", self._build_ms)):
            self.stack.add_named(builder(), name)

        self.connect("draw", self._draw)
        self.connect("realize", lambda *_: self.get_frame_clock().connect("after-paint", self._after_paint))
        self._set_vertical(self.core.dock["edge"] in ("left", "right"))
        self._place()
        self.show_all()
        self.refresh()

    # ── construcción ──
    def _build_compact(self):
        box = self.c_box = Gtk.Box(spacing=9, margin_start=14, margin_end=14)
        self.c_left = Gtk.Stack()
        self.c_icon = Gtk.Image()
        self.c_art = Art(22, 6)
        self.c_left.add_named(self.c_icon, "icon")
        self.c_left.add_named(self.c_art, "art")
        box.pack_start(self.c_left, False, False, 0)
        self.c_center = Gtk.Stack(hexpand=True)
        self.c_label = label("", "c-text")
        self.c_level = Gtk.LevelBar(valign=Gtk.Align.CENTER, min_value=0, max_value=1)
        for off in ("low", "high", "full"):
            self.c_level.remove_offset_value(off)
        self.c_center.add_named(self.c_label, "label")
        self.c_center.add_named(self.c_level, "level")
        box.pack_start(self.c_center, True, True, 0)
        self.c_right = Gtk.Stack()
        self.c_rlabel = label("", "c-text", xalign=1.0, ellipsize=False)
        self.c_eq = Equalizer()
        self.c_right.add_named(self.c_rlabel, "label")
        self.c_right.add_named(self.c_eq, "eq")
        box.pack_end(self.c_right, False, False, 0)
        self.c_wicon = WeatherIcon(18)
        self.c_wicon.set_no_show_all(True)
        box.pack_end(self.c_wicon, False, False, 0)
        return box

    def _build_card(self):
        box = Gtk.Box(spacing=12, margin_start=14, margin_end=18, margin_top=12, margin_bottom=12)
        self.k_left = Gtk.Stack(valign=Gtk.Align.CENTER)
        self.k_icon = Gtk.Image(pixel_size=30)
        self.k_art = Art(42, 10)
        self.k_left.add_named(self.k_icon, "icon")
        self.k_left.add_named(self.k_art, "art")
        box.pack_start(self.k_left, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, valign=Gtk.Align.CENTER)
        self.k_app = label("", "dim small")
        self.k_title = label("", "subtitle")
        self.k_body = label("", "artist", lines=2)
        self.k_hint = label("Clic para abrir", "time-small")
        self.k_hint.set_no_show_all(True)
        for w in (self.k_app, self.k_title, self.k_body, self.k_hint):
            txt.pack_start(w, False, False, 0)
        box.pack_start(txt, True, True, 0)
        close = button("close", icon("window-close-symbolic", px=12), self._close_card, "Cerrar")
        close.set_valign(Gtk.Align.START)
        box.pack_end(close, False, False, 0)
        return box

    def _close_card(self):
        """Descarta la notificación; si el ratón sigue encima, se ve el panel con las demás opciones."""
        self.core.event = None
        self.card_hold = False
        self.core.refresh()

    def _build_alert(self):
        box = Gtk.Box(spacing=12, margin_start=18, margin_end=14)
        a = icon("alarm-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        set_accent(a, "orange")
        box.pack_start(a, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        txt.pack_start(label("¡Tiempo cumplido!", "title"), False, False, 0)
        self.a_sub = label("", "artist")
        txt.pack_start(self.a_sub, False, False, 0)
        box.pack_start(txt, True, True, 0)
        ok = button("chip", cb=self.core.dismiss_alert, text="OK")
        ok.set_valign(Gtk.Align.CENTER)
        box.pack_end(ok, False, False, 0)
        return box

    def _page(self, title, right=None):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_start=16, margin_end=16, margin_top=12, margin_bottom=14)
        head = Gtk.Box(spacing=6)
        head.pack_start(button("ctrl", icon("go-previous-symbolic"), lambda: self.go("home"), "Volver"),
                        False, False, 0)
        head.pack_start(label(title, "title"), True, True, 0)
        if right is not None:
            right.set_valign(Gtk.Align.CENTER)
            head.pack_end(right, False, False, 0)
        box.pack_start(head, False, False, 0)
        return box

    @staticmethod
    def _scroller(child, max_h=250):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_propagate_natural_height(True)
        sw.set_max_content_height(max_h)
        sw.add(child)
        return sw

    def _build_home(self):
        c = self.core
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_start=14, margin_end=14, margin_top=12, margin_bottom=14)
        top = Gtk.Box(spacing=12)
        self.h_clock = label("", "bigclock", ellipsize=False)
        top.pack_start(self.h_clock, False, False, 0)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=2)
        self.h_date = label("", "artist", xalign=1.0)
        bat = Gtk.Box(spacing=5, halign=Gtk.Align.END)
        self.h_bat_icon = Gtk.Image()
        self.h_bat = label("", "dim", xalign=1.0, ellipsize=False)
        bat.pack_start(self.h_bat_icon, False, False, 0)
        bat.pack_start(self.h_bat, False, False, 0)
        side.pack_start(self.h_date, False, False, 0)
        side.pack_start(bat, False, False, 0)
        wbox = Gtk.Box(spacing=5)
        self.h_w_icon = WeatherIcon(18)
        self.h_w = label("Clima", "dim", ellipsize=False)
        wbox.pack_start(self.h_w_icon, False, False, 0)
        wbox.pack_start(self.h_w, False, False, 0)
        wbtn = button("wlink", wbox, lambda: self.go("weather"), "Ver el clima")
        wbtn.set_halign(Gtk.Align.END)
        side.pack_start(wbtn, False, False, 0)
        top.pack_end(side, True, True, 0)
        box.pack_start(top, False, False, 0)

        # reproductor
        self.h_media = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        row = Gtk.Box(spacing=10)
        self.m_art = Art(44, 10)
        row.pack_start(self.m_art, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=1)
        self.m_title = label("", "subtitle")
        self.m_artist = label("", "artist")
        txt.pack_start(self.m_title, False, False, 0)
        txt.pack_start(self.m_artist, False, False, 0)
        row.pack_start(txt, True, True, 0)
        row.pack_start(button("ctrl", icon("media-skip-backward-symbolic"), lambda: c.media_cmd("Previous")),
                       False, False, 0)
        self.m_play_img = icon("media-playback-pause-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        row.pack_start(button("ctrl", self.m_play_img, lambda: c.media_cmd("PlayPause")), False, False, 0)
        row.pack_start(button("ctrl", icon("media-skip-forward-symbolic"), lambda: c.media_cmd("Next")),
                       False, False, 0)
        self.h_media.pack_start(row, False, False, 0)
        prog = Gtk.Box(spacing=8)
        self.m_pos = label("0:00", "time-small", ellipsize=False)
        self.m_len = label("0:00", "time-small", ellipsize=False)
        self.m_bar = Gtk.LevelBar(valign=Gtk.Align.CENTER, hexpand=True, min_value=0, max_value=1)
        for off in ("low", "high", "full"):
            self.m_bar.remove_offset_value(off)
        prog.pack_start(self.m_pos, False, False, 0)
        prog.pack_start(self.m_bar, True, True, 0)
        prog.pack_start(self.m_len, False, False, 0)
        self.h_media.pack_start(prog, False, False, 0)
        self.h_media.set_no_show_all(True)
        for ch in (row, prog):
            ch.show_all()
        box.pack_start(self.h_media, False, False, 0)

        # volumen
        vol = Gtk.Box(spacing=8)
        self.v_img = icon("audio-volume-high-symbolic")
        vol.pack_start(button("ctrl", self.v_img, Volume.toggle_mute, "Silenciar"), False, False, 0)
        self.v_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.v_scale.set_draw_value(False)
        self.v_scale.set_hexpand(True)
        self.v_scale.connect("value-changed", self._on_vol_scale)
        vol.pack_start(self.v_scale, True, True, 0)
        self.v_pct = label("", "time-small", ellipsize=False)
        self.v_pct.set_width_chars(4)
        vol.pack_start(self.v_pct, False, False, 0)
        box.pack_start(vol, False, False, 0)

        # ajustes rápidos
        grid = Gtk.Grid(column_homogeneous=True, row_spacing=8, column_spacing=4)
        m = c.modes
        self.t_wifi = Tile("network-wireless-symbolic", "Wi-Fi",
                           lambda: c.wifi.set_enabled(not c.wifi.enabled), lambda: self.go("wifi"))
        self.t_bt = Tile("bluetooth-active-symbolic", "Bluetooth",
                         lambda: c.bt.set_powered(not c.bt.powered), lambda: self.go("bt"))
        self.t_air = Tile("airplane-mode-symbolic", "Avión", c.radios.toggle)
        self.t_dnd = Tile("notifications-disabled-symbolic", "No molestar", c.notif.toggle_dnd)
        self.t_dark = Tile("dark-mode-symbolic", "Oscuro", m.toggle_dark)
        self.t_night = Tile("night-light-symbolic", "Luz nocturna", m.toggle_night)
        self.t_saver = Tile("power-profile-power-saver-symbolic", "Ahorro", m.toggle_saver)
        self.t_awake = Tile("caffeine-cup-full-symbolic", "Despierto", m.toggle_awake)
        self.t_care = Tile("battery-level-80-symbolic", "Cuidar batería", c.charge_limit.toggle)
        tiles = [self.t_wifi, self.t_bt, self.t_air, self.t_dnd, self.t_dark,
                 self.t_night, self.t_saver, self.t_awake]
        if c.charge_limit.supported:
            tiles.append(self.t_care)
        cols = 5 if len(tiles) > 8 else 4
        for i, t in enumerate(tiles):
            grid.attach(t, i % cols, i // cols, 1, 1)
        box.pack_start(grid, False, False, 0)

        # accesos
        acts = Gtk.Box(spacing=5, halign=Gtk.Align.CENTER)

        def act_btn(ic, txt, tip, cb):
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
            inner.pack_start(icon(ic, px=18), False, False, 0)
            inner.pack_start(label(txt, "time-small", xalign=0.5, ellipsize=False), False, False, 0)
            return button("act", inner, cb, tip)

        def act(ic, txt, tip, cb):
            acts.pack_start(act_btn(ic, txt, tip, cb), False, False, 0)
        act("applets-screenshooter-symbolic", "Recorte", "Capturar un área (arrastra un rectángulo)",
            lambda: self._collapse_then(c.screenshot))
        act("view-fullscreen-symbolic", "Pantalla", "Capturar esta pantalla completa",
            lambda: self._collapse_then(lambda: c.screenshot(self.monitor)))
        act("edit-paste-symbolic", "Copias", "Historial del portapapeles", lambda: self.go("clip"))
        ov = Gtk.Overlay()
        ov.add(act_btn("preferences-system-notifications-symbolic", "Avisos", "Notificaciones",
                       lambda: self.go("notifs")))
        self.badge = label("", "badge", xalign=0.5, ellipsize=False)
        self.badge.set_halign(Gtk.Align.END)
        self.badge.set_valign(Gtk.Align.START)
        self.badge.set_no_show_all(True)
        ov.add_overlay(self.badge)
        acts.pack_start(ov, False, False, 0)
        act("media-removable-symbolic", "USB", "Medios extraíbles", lambda: self.go("usb"))
        act("timer-symbolic", "Pomodoro", "Pomodoro", lambda: self.go("pomo"))
        act("alarm-symbolic", "Alarma", "Temporizador", lambda: self.go("timer"))
        act("system-shutdown-symbolic", "Energía", "Bloquear, suspender, reiniciar, apagar", lambda: self.go("power"))
        box.pack_start(acts, False, False, 0)

        # trabajo: GitHub, Teams y correo
        work = Gtk.Box(spacing=6, homogeneous=True)
        self.work_labels = {}
        for key, ic, txt, tip, page in (("github", GITHUB_APP, "GitHub", "Pull requests", "github"),
                                        ("teams", TEAMS_APP, "Teams", "Mensajes de Teams", "ms"),
                                        ("outlook", "mail-unread-symbolic", "Correo", "Correo de Outlook", "ms")):
            inner = Gtk.Box(spacing=7)
            inner.pack_start(icon(ic, px=18), False, False, 0)
            inner.pack_start(label(txt, "small", ellipsize=False), False, False, 0)
            cnt = label("", "badge", xalign=0.5, ellipsize=False)
            cnt.set_valign(Gtk.Align.CENTER)
            cnt.set_no_show_all(True)
            inner.pack_end(cnt, False, False, 0)
            self.work_labels[key] = cnt
            work.pack_start(button("work", inner, lambda pg=page: self.go(pg), tip), True, True, 0)
        box.pack_start(work, False, False, 0)
        return box

    def _set_count(self, key, n):
        lb = self.work_labels[key]
        lb.set_text(str(min(n, 99)))
        lb.set_visible(n > 0)

    # ── GitHub ──
    def _build_github(self):
        gh = self.core.github
        box = self._page("GitHub", button("ctrl", icon("view-refresh-symbolic"), gh.refresh, "Actualizar"))
        self.gh_setup = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.gh_setup_msg = label("", "subtitle", lines=3)
        self.gh_setup.pack_start(self.gh_setup_msg, False, False, 0)
        self.gh_cmds = label("", "cmd", ellipsize=False)
        self.gh_cmds.set_selectable(True)
        self.gh_cmds.set_xalign(0.0)
        self.gh_setup.pack_start(self.gh_cmds, False, False, 0)
        hint = Gtk.Box(spacing=8)
        hint.pack_start(label("Córrelos en una terminal y luego pulsa Actualizar.", "dim small", lines=2),
                        True, True, 0)
        hint.pack_end(button("chip", cb=lambda: self._copy(self.gh_cmds.get_text()), text="Copiar"),
                      False, False, 0)
        self.gh_setup.pack_start(hint, False, False, 0)
        box.pack_start(self.gh_setup, False, False, 0)
        self.gh_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.gh_list, 380), False, False, 0)
        foot = Gtk.Box()
        self.gh_status = label("", "dim small")
        foot.pack_start(self.gh_status, True, True, 0)
        foot.pack_end(button("chip", cb=lambda: self._collapse_then(self.core.open_github), text="Abrir GitHub"),
                      False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _fill_github(self):
        gh, c = self.core.github, self.core
        setup = {"nogh": ("Para ver tus PR, instala la herramienta de GitHub e inicia sesión:",
                          "sudo apt install gh\ngh auth login"),
                 "noauth": ("Inicia sesión en GitHub con la herramienta gh:", "gh auth login")}.get(gh.state)
        self.gh_setup.set_visible(setup is not None)
        if setup:
            self.gh_setup_msg.set_text(setup[0])
            self.gh_cmds.set_text(setup[1])
        clear(self.gh_list)
        if gh.state == "ok" or gh.review or gh.mine:
            for title, prs, mine, empty in (("REVISIÓN PEDIDA", gh.review, False, "Nadie te pidió revisar nada"),
                                            ("MIS PR ABIERTAS", gh.mine, True, "No tienes PR abiertas"),
                                            ("FUSIONADAS · ÚLTIMOS 7 DÍAS", gh.merged, True,
                                             "Ninguna fusionada esta semana")):
                head = label(f"{title} · {len(prs)}", "section")
                head.set_margin_top(6)
                self.gh_list.pack_start(head, False, False, 0)
                for p in prs:
                    sub, acc = GitHub.describe(p, mine)
                    ic = ("emblem-ok-symbolic" if p.get("merged") else
                          "document-edit-symbolic" if p["draft"] else GITHUB_APP)
                    self.gh_list.pack_start(self._row(ic, p["title"], sub,
                                                      lambda p=p: self._collapse_then(
                                                          lambda: c.open_github(p["url"])),
                                                      sub_accent=acc), False, False, 0)
                if not prs:
                    self._empty(self.gh_list, empty)
        self.gh_list.show_all()
        st = ("Actualizando…" if gh.loading else gh.error if gh.state == "error" else
              f"@{gh.login} · actualizado {time.strftime('%H:%M', time.localtime(gh.updated))}"
              if gh.state == "ok" else "")
        self.gh_status.set_text(st)
        set_accent(self.gh_status, "red" if gh.state == "error" and not gh.loading else None)

    # ── Microsoft: Teams y Outlook (a partir de sus notificaciones) ──
    def _build_ms(self):
        box = self._page("Teams y correo")
        self.ms_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.ms_list, 400), False, False, 0)
        foot = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        foot.pack_start(button("chip", cb=lambda: self._collapse_then(self.core.open_teams), text="Abrir Teams"),
                        False, False, 0)
        foot.pack_start(button("chip", cb=lambda: self._collapse_then(lambda: open_uri(OUTLOOK_URL)),
                               text="Abrir Outlook"), False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _fill_ms(self):
        c = self.core
        clear(self.ms_list)
        for kind, title, empty in (
                ("teams", "TEAMS", "Sin mensajes. Aparecen aquí cuando Teams (abierto) te envía una notificación."),
                ("outlook", "CORREO · OUTLOOK", "Sin correos. Aparecen aquí cuando Outlook web (abierto en "
                                                "Chrome) avisa de un correo nuevo.")):
            items = [n for n in c.notifs if n.get("ms") == kind][:8]
            head = label(f"{title} · {len(items)}", "section")
            head.set_margin_top(6)
            self.ms_list.pack_start(head, False, False, 0)
            for n in items:
                sub = (n["body"] + " · " if n["body"] else "") + ago(n["time"])
                self.ms_list.pack_start(self._row(n["icon"], n["summary"] or n["app"], sub,
                                                  lambda n=n: self._collapse_then(lambda: c.open_notif(n)),
                                                  pixbuf=n["pixbuf"]), False, False, 0)
            if not items:
                self._empty(self.ms_list, empty)
        self.ms_list.show_all()

    @staticmethod
    def _switch(cb):
        sw = Gtk.Switch()
        sw._cb = sw.connect("notify::active", lambda s, _p: cb(s.get_active()))
        return sw

    @staticmethod
    def _set_switch(sw, value):
        if sw.get_active() != value:
            sw.handler_block(sw._cb)
            sw.set_active(value)
            sw.handler_unblock(sw._cb)

    def _build_wifi(self):
        self.w_switch = self._switch(self.core.wifi.set_enabled)
        box = self._page("Wi-Fi", self.w_switch)
        self.w_status = label("", "dim")
        box.pack_start(self.w_status, False, False, 0)
        self.w_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.w_list, 230), False, False, 0)
        self.w_pw = Gtk.Box(spacing=8)
        self.w_entry = Gtk.Entry(hexpand=True, visibility=False)
        self.w_entry.connect("activate", lambda *_: self._wifi_password())
        self.w_pw.pack_start(self.w_entry, True, True, 0)
        self.w_pw.pack_start(button("chip", cb=self._wifi_password, text="Conectar"), False, False, 0)
        self.w_pw.set_no_show_all(True)
        box.pack_start(self.w_pw, False, False, 0)
        foot = Gtk.Box(spacing=8)
        foot.pack_start(button("chip", cb=self.core.wifi.scan, text="Buscar redes"), False, False, 0)
        foot.pack_end(button("chip", cb=lambda: self._settings("wifi"), text="Más ajustes"), False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _build_bt(self):
        self.b_switch = self._switch(self.core.bt.set_powered)
        box = self._page("Bluetooth", self.b_switch)
        self.b_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.b_list, 230), False, False, 0)
        foot = Gtk.Box()
        foot.pack_end(button("chip", cb=lambda: self._settings("bluetooth"), text="Añadir dispositivo"),
                      False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _build_clip(self):
        box = self._page("Portapapeles", button("chip danger", cb=self.core.clip.clear, text="Borrar todo"))
        self.p_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.p_list, 280), False, False, 0)
        return box

    def _build_notifs(self):
        def clear_all():
            self.core.notifs.clear()
            self.core.unread = 0
            self.core.changed("notifs")
        box = self._page("Notificaciones", button("chip danger", cb=clear_all, text="Borrar"))
        self.n_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.n_list, 290), False, False, 0)
        foot = Gtk.Box()
        foot.pack_end(button("chip", cb=self.core.notif.open_center, text="Centro de notificaciones"),
                      False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _build_usb(self):
        box = self._page("Medios extraíbles")
        self.u_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.u_list, 250), False, False, 0)
        return box

    def _build_timer(self):
        self.t_stop = button("chip danger", cb=self.core.stop_timer, text="Detener")
        self.t_stop.set_no_show_all(True)
        self.t_stop.get_child().show()
        box = self._page("Temporizador", self.t_stop)
        self.t_big = label("", "huge", xalign=0.5, ellipsize=False)
        box.pack_start(self.t_big, False, False, 0)
        chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=5,
                            min_children_per_line=5, homogeneous=True, column_spacing=6, row_spacing=6)
        for m in (1, 3, 5, 10, 15, 25, 30, 45, 60, 90):
            chips.add(button("chip", cb=lambda m=m: self.core.start_timer(m * 60), text=f"{m} min"))
        box.pack_start(chips, False, False, 0)
        return box

    def _build_weather(self):
        box = self._page("Clima", button("ctrl", icon("view-refresh-symbolic"), self.core.weather.refresh,
                                         "Actualizar"))
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        now = Gtk.Box(spacing=14)
        self.we_icon = WeatherIcon(64, animated=True)
        now.pack_start(self.we_icon, False, False, 0)
        self.we_temp = label("—", "huge", ellipsize=False)
        now.pack_start(self.we_temp, False, False, 0)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=2)
        self.we_desc = label("", "subtitle")
        self.we_place = label("", "dim")
        self.we_range = label("", "dim")
        for w in (self.we_desc, self.we_place, self.we_range):
            info.pack_start(w, False, False, 0)
        now.pack_start(info, True, True, 0)
        body.pack_start(now, False, False, 0)

        # detalles en mosaicos
        grid = Gtk.Grid(column_spacing=6, row_spacing=6, column_homogeneous=True)
        self.we_tiles = {}
        for n, (key, title) in enumerate((("feels", "Sensación"), ("humidity", "Humedad"),
                                          ("wind", "Viento"), ("clouds", "Nubes"),
                                          ("rain", "Lluvia hoy"), ("uv", "Índice UV"),
                                          ("sunrise", "Amanecer"), ("sunset", "Atardecer"))):
            t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            t.get_style_context().add_class("wtile")
            t.pack_start(label(title, "dim small"), False, False, 0)
            v = label("—", "wtile-v")
            t.pack_start(v, False, False, 0)
            self.we_tiles[key] = v
            grid.attach(t, n % 4, n // 4, 1, 1)
        body.pack_start(grid, False, False, 0)

        body.pack_start(label("PRÓXIMAS 24 HORAS", "section"), False, False, 0)
        self.we_hours = Gtk.Box(spacing=2)
        hsw = Gtk.ScrolledWindow()
        hsw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        hsw.set_propagate_natural_height(True)
        hsw.add(self.we_hours)
        body.pack_start(hsw, False, False, 0)

        body.pack_start(label("PRÓXIMOS 7 DÍAS", "section"), False, False, 0)
        self.we_days = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        body.pack_start(self.we_days, False, False, 0)

        row = Gtk.Box(spacing=8, margin_top=4)
        self.we_entry = Gtk.Entry(hexpand=True, placeholder_text="Ciudad (p. ej. Medellín)")
        self.we_entry.connect("activate", lambda *_: self._set_city())
        row.pack_start(icon("find-location-symbolic"), False, False, 0)
        row.pack_start(self.we_entry, True, True, 0)
        row.pack_start(button("chip", cb=self._set_city, text="Cambiar"), False, False, 0)
        body.pack_start(row, False, False, 0)
        self.we_status = label("", "dim small")
        body.pack_start(self.we_status, False, False, 0)
        box.pack_start(self._scroller(body, 470), False, False, 0)
        return box

    def _fill_weather(self, w, d):
        self.we_icon.set_kind(d.get("kind", "cloudy"))
        self.we_temp.set_text(f"{d['temp']:.0f}°")
        self.we_desc.set_text(d["desc"])
        self.we_place.set_text(w.place["name"] if w.place else w.city)
        self.we_range.set_text(f"Máx {d['max']:.0f}° · Mín {d['min']:.0f}°")
        dirs = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
        wind = f"{d['wind']:.0f} km/h"
        if d.get("wind_dir") is not None:
            wind += " " + dirs[round(d["wind_dir"] / 45) % 8]
        uv = d.get("uv_max") or 0
        uv_txt = "Bajo" if uv < 3 else "Moderado" if uv < 6 else "Alto" if uv < 8 else "Muy alto" if uv < 11 else "Extremo"
        rain = f"{d['rain']}%" if d.get("rain") is not None else "—"
        if d.get("rain_mm"):
            rain += f" · {d['rain_mm']:.1f} mm"
        vals = {"feels": f"{d['feels']:.0f}°", "humidity": f"{d['humidity']}%", "wind": wind,
                "clouds": f"{d['clouds']}%" if d.get("clouds") is not None else "—",
                "rain": rain, "uv": f"{uv:.0f} {uv_txt}",
                "sunrise": d.get("sunrise", "—"), "sunset": d.get("sunset", "—")}
        for k, v in vals.items():
            self.we_tiles[k].set_text(v)
            self.we_tiles[k].set_tooltip_text(v)
        if d.get("gusts"):
            self.we_tiles["wind"].set_tooltip_text(f"{wind} · ráfagas de {d['gusts']:.0f} km/h")

        clear(self.we_hours)
        for i, hr in enumerate(d.get("hours", [])):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, margin_bottom=2)
            col.set_size_request(44, -1)
            col.pack_start(label(hr["hour"][:2] + " h", "hour", xalign=0.5,
                                 ellipsize=False), False, False, 0)
            col.pack_start(WeatherIcon(24), False, False, 0)
            col.pack_start(label(f"{hr['temp']:.0f}°", "subtitle", xalign=0.5, ellipsize=False), False, False, 0)
            pop = hr.get("pop") or 0
            col.pack_start(label(f"{pop}%" if pop >= 20 else " ", "pop", xalign=0.5, ellipsize=False),
                           False, False, 0)
            col.get_children()[1].set_kind(hr.get("kind", "cloudy"))
            self.we_hours.pack_start(col, False, False, 0)
        self.we_hours.show_all()

        clear(self.we_days)
        days = d.get("days", [])
        if days:
            wlo, whi = min(x["min"] for x in days), max(x["max"] for x in days)
            for day in days:
                row = Gtk.Box(spacing=10)
                name = label(day["name"], "subtitle", ellipsize=False)
                name.set_size_request(62, -1)
                row.pack_start(name, False, False, 0)
                ic = WeatherIcon(22)
                ic.set_kind(day["kind"])
                row.pack_start(ic, False, False, 0)
                pop = day.get("pop") or 0
                pl = label(f"{pop}%" if pop >= 20 else "", "pop", ellipsize=False)
                pl.set_size_request(34, -1)
                row.pack_start(pl, False, False, 0)
                lo = label(f"{day['min']:.0f}°", "dim", xalign=1.0, ellipsize=False)
                lo.set_size_request(30, -1)
                row.pack_start(lo, False, False, 0)
                row.pack_start(TempBar(day["min"], day["max"], wlo, whi), True, True, 0)
                hi = label(f"{day['max']:.0f}°", "subtitle", ellipsize=False)
                hi.set_size_request(30, -1)
                row.pack_start(hi, False, False, 0)
                self.we_days.pack_start(row, False, False, 0)
        self.we_days.show_all()

    def _set_city(self):
        text = self.we_entry.get_text().strip()
        self.set_focus(None)
        if text:
            self.core.weather.set_city(text)

    def _build_pomo(self):
        box = self._page("Pomodoro", button("chip", cb=self.core.pomo.reset, text="Reiniciar"))
        self.po_phase = label("", "subtitle", xalign=0.5)
        self.po_time = label("", "huge", xalign=0.5, ellipsize=False)
        self.po_cycle = label("", "dim", xalign=0.5)
        for w in (self.po_phase, self.po_time, self.po_cycle):
            box.pack_start(w, False, False, 0)
        ctr = Gtk.Box(spacing=16, halign=Gtk.Align.CENTER)
        self.po_play = icon("media-playback-start-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        ctr.pack_start(button("ctrl", self.po_play, self.core.pomo.toggle, "Iniciar / pausar"), False, False, 0)
        ctr.pack_start(button("ctrl", icon("media-skip-forward-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                              self.core.pomo.skip, "Saltar a la siguiente fase"), False, False, 0)
        box.pack_start(ctr, False, False, 0)

        grid = Gtk.Grid(row_spacing=6, column_spacing=10)
        conf = self.core.pomo.conf
        for r, (key, text, lo, hi) in enumerate((("work", "Enfoque (min)", 1, 180),
                                                 ("short", "Descanso corto (min)", 1, 60),
                                                 ("long", "Descanso largo (min)", 1, 120),
                                                 ("every", "Descanso largo cada (sesiones)", 2, 12))):
            lb = label(text, "artist", xalign=0.0)
            lb.set_hexpand(True)
            spin = Gtk.SpinButton.new_with_range(lo, hi, 1)
            spin.set_value(conf[key])
            spin.connect("value-changed", lambda s, k=key: self.core.pomo.set_conf(k, int(s.get_value())))
            grid.attach(lb, 0, r, 1, 1)
            grid.attach(spin, 1, r, 1, 1)
        auto_lb = label("Empezar la siguiente fase sola", "artist", xalign=0.0)
        auto = Gtk.Switch(active=bool(conf["auto"]), halign=Gtk.Align.END)
        auto.connect("notify::active", lambda s, _p: self.core.pomo.set_conf("auto", s.get_active()))
        grid.attach(auto_lb, 0, 4, 1, 1)
        grid.attach(auto, 1, 4, 1, 1)
        box.pack_start(grid, False, False, 0)
        return box

    def _build_power(self):
        box = self._page("Energía")
        row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        p = self.core.power
        self.pw_buttons = {}
        for key, ic, txt, cb, confirm in (("lock", "system-lock-screen-symbolic", "Bloquear", p.lock, False),
                                          ("logout", "system-log-out-symbolic", "Salir", p.logout, True),
                                          ("suspend", "system-suspend-symbolic", "Suspender", p.suspend, False),
                                          ("reboot", "system-reboot-symbolic", "Reiniciar", p.reboot, True),
                                          ("off", "system-shutdown-symbolic", "Apagar", p.poweroff, True)):
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            inner.pack_start(icon(ic, px=22), False, False, 0)
            lb = label(txt, "small", xalign=0.5, ellipsize=False)
            inner.pack_start(lb, False, False, 0)
            b = button("big", inner, lambda k=key, cb=cb, c=confirm: self._power(k, cb, c))
            self.pw_buttons[key] = (b, lb, txt)
            row.pack_start(b, False, False, 0)
        box.pack_start(row, False, False, 0)
        self.pw_hint = label("", "dim small", xalign=0.5)
        box.pack_start(self.pw_hint, False, False, 0)
        return box

    # ── acciones ──
    def go(self, page):
        self.page = page
        self._nav_t = time.monotonic()
        if page == "wifi":
            self.core.wifi.refresh()
            self.core.wifi.scan()
        elif page == "bt":
            self.core.bt.refresh()
        elif page == "weather":
            self.we_entry.set_text("")
            w = self.core.weather
            if not w.data or time.time() - w.data["updated"] > 600:
                w.refresh()
        elif page == "github":
            gh = self.core.github
            if gh.state != "ok" or time.time() - gh.updated > 60:
                gh.refresh()
        elif page == "ms":
            self.core.ms_unread = {"teams": 0, "outlook": 0}
            self.core.changed("ms")
        elif page == "notifs" and self.core.unread:
            self.core.unread = 0
            self.core.changed()
        if page == "home" or page == "usb":
            self.core.radios.refresh()
        self.refresh()

    def _settings(self, panel):
        subprocess.Popen(["budgie-control-center", panel], stderr=subprocess.DEVNULL)
        self._set_hover(False)

    def _collapse_then(self, fn):
        self._set_hover(False)
        fn()

    def _power(self, key, cb, confirm):
        if confirm and self._confirm != key:
            self._confirm = key
            self.pw_hint.set_text("Vuelve a pulsar para confirmar")
            GLib.timeout_add(8000, self._reset_confirm, key)
            self.refresh()
            return
        self._confirm = None
        self._set_hover(False)
        cb()

    def _reset_confirm(self, key):
        if self._confirm == key:
            self._confirm = None
            self.refresh()
        return False

    def _wifi_password(self):
        if self.pw_net:
            self.core.wifi.connect(self.pw_net, password=self.w_entry.get_text())
            self.w_entry.set_text("")
            self.pw_net = None
            self.w_pw.hide()

    def _need_password(self, net):
        self.pw_net = net
        self.w_entry.set_placeholder_text(f"Contraseña de «{net['ssid']}»")
        self.w_pw.show_all()
        self.w_entry.grab_focus()
        self.refresh()

    def _on_vol_scale(self, scale):
        if not self._vol_lock:
            Volume.set(scale.get_value() / 100)

    # ── listas ──
    def _row(self, ic, title, sub=None, cb=None, extra=None, pixbuf=None, sub_accent=None):
        inner = Gtk.Box(spacing=10)
        if pixbuf is not None:
            a = Art(32, 8)
            a.set_pixbuf(pixbuf)
            inner.pack_start(a, False, False, 0)
        elif ic:
            inner.pack_start(icon(ic, px=24), False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        txt.pack_start(label(title, "subtitle"), False, False, 0)
        if sub:
            s = label(sub, "dim", lines=2)
            set_accent(s, sub_accent)
            txt.pack_start(s, False, False, 0)
        inner.pack_start(txt, True, True, 0)
        row = Gtk.Box(spacing=4)
        if cb:
            row.pack_start(button("row", inner, cb), True, True, 0)
        else:
            inner.set_margin_start(8)
            inner.set_margin_top(6)
            inner.set_margin_bottom(6)
            row.pack_start(inner, True, True, 0)
        for w in extra or ():
            w.set_valign(Gtk.Align.CENTER)
            row.pack_start(w, False, False, 0)
        return row

    @staticmethod
    def _empty(box, text):
        lb = label(text, "dim", xalign=0.5)
        lb.set_margin_top(10)
        lb.set_margin_bottom(10)
        box.pack_start(lb, False, False, 0)

    def _fill_lists(self):
        c = self.core
        ver = c.ver
        if self.seen.get("wifi", -1) != ver.get("wifi"):
            self.seen["wifi"] = ver.get("wifi")
            w = c.wifi
            self._set_switch(self.w_switch, w.enabled)
            status = ("Conectado a " + w.active) if w.active else ("Conectado por cable" if w.wired else
                                                                   ("Sin conexión" if w.enabled else "Wi-Fi desactivado"))
            if w.busy:
                status = f"Conectando a {w.busy}…"
            self.w_status.set_text(w.error or status)
            set_accent(self.w_status, "red" if w.error else None)
            clear(self.w_list)
            if w.enabled:
                for n in w.nets:
                    q = ("excellent" if n["signal"] > 75 else "good" if n["signal"] > 50 else
                         "ok" if n["signal"] > 25 else "weak")
                    sub = "Conectada" if n["inuse"] else ("Guardada" if n["ssid"] in w.known else
                                                          ("Protegida" if n["secure"] else "Abierta"))
                    extra = [icon("changes-prevent-symbolic")] if n["secure"] else []
                    cb = None if n["inuse"] else (lambda n=n: c.wifi.connect(n, on_need_password=self._need_password))
                    self.w_list.pack_start(self._row(f"network-wireless-signal-{q}-symbolic", n["ssid"], sub, cb,
                                                     extra, sub_accent="blue" if n["inuse"] else None),
                                           False, False, 0)
                if not w.nets:
                    self._empty(self.w_list, "Buscando redes…" if w.scanning else "No se encontraron redes")
            self.w_list.show_all()

        if self.seen.get("bt", -1) != ver.get("bt"):
            self.seen["bt"] = ver.get("bt")
            b = c.bt
            self._set_switch(self.b_switch, b.powered)
            clear(self.b_list)
            if not b.available:
                self._empty(self.b_list, "No hay adaptador Bluetooth")
            elif not b.powered:
                self._empty(self.b_list, "Bluetooth desactivado")
            else:
                for d in sorted(b.devices.values(), key=lambda d: (not d["connected"], d["name"].lower())):
                    sub = ("Conectando…" if d["path"] in b.busy else "Conectado" if d["connected"] else
                           "Desconectado · clic para conectar")
                    if d["connected"] and d["battery"] is not None:
                        sub += f" · {d['battery']}%"
                    self.b_list.pack_start(self._row(d["icon"], d["name"], sub,
                                                     lambda p=d["path"]: b.toggle_device(p),
                                                     sub_accent="blue" if d["connected"] else None),
                                           False, False, 0)
                if not b.devices:
                    self._empty(self.b_list, "No hay dispositivos vinculados")
            self.b_list.show_all()

        if self.seen.get("clip", -1) != ver.get("clip"):
            self.seen["clip"] = ver.get("clip")
            clear(self.p_list)
            for t in c.clip.items:
                one = re.sub(r"\s+", " ", t.strip())[:160]
                lines = t.count("\n") + 1
                sub = f"{lines} líneas · {len(t)} caracteres" if lines > 1 else f"{len(t)} caracteres"
                rm = button("ctrl", icon("window-close-symbolic"), lambda t=t: c.clip.remove(t), "Quitar")
                self.p_list.pack_start(self._row(None, one, sub, lambda t=t: self._copy(t), [rm]), False, False, 0)
            if not c.clip.items:
                self._empty(self.p_list, "Copia algo y aparecerá aquí")
            self.p_list.show_all()

        if self.seen.get("notifs", -1) != ver.get("notifs"):
            self.seen["notifs"] = ver.get("notifs")
            clear(self.n_list)
            for n in c.notifs:
                title = n["summary"] or n["app"]
                sub = f"{n['app']} · {ago(n['time'])}" + (f" — {n['body']}" if n["body"] else "")
                rm = button("ctrl", icon("window-close-symbolic"), lambda n=n: self._remove_notif(n), "Quitar")
                self.n_list.pack_start(self._row(n["icon"], title, sub,
                                                 lambda n=n: (self._set_hover(False), c.open_notif(n)),
                                                 [rm], pixbuf=n["pixbuf"]), False, False, 0)
            if not c.notifs:
                self._empty(self.n_list, "No hay notificaciones")
            self.n_list.show_all()

        if self.seen.get("github", -1) != ver.get("github"):
            self.seen["github"] = ver.get("github")
            self._fill_github()

        if self.seen.get("ms", -1) != ver.get("ms") or self.seen.get("ms_n", -1) != ver.get("notifs"):
            self.seen["ms"], self.seen["ms_n"] = ver.get("ms"), ver.get("notifs")
            self._fill_ms()

        if self.seen.get("weather", -1) != ver.get("weather"):
            self.seen["weather"] = ver.get("weather")
            w = c.weather
            d = w.data
            if d:
                self._fill_weather(w, d)
            status = "Actualizando…" if w.loading else (w.error or
                                                         (f"Actualizado a las {time.strftime('%H:%M', time.localtime(d['updated']))} · Open-Meteo" if d else ""))
            self.we_status.set_text(status)
            set_accent(self.we_status, "red" if w.error and not w.loading else None)

        if self.seen.get("usb", -1) != ver.get("usb"):
            self.seen["usb"] = ver.get("usb")
            clear(self.u_list)
            vols = c.drives.items()
            for v in vols:
                gicon = v.get_symbolic_icon()
                names = gicon.get_names() if isinstance(gicon, Gio.ThemedIcon) else []
                mounted = v.get_mount() is not None
                ej = button("ctrl", icon("media-eject-symbolic"), lambda v=v: c.drives.eject(v), "Expulsar")
                self.u_list.pack_start(self._row(names[0] if names else "drive-removable-media-symbolic",
                                                 v.get_name(),
                                                 "Montado · clic para abrir" if mounted else "Clic para montar y abrir",
                                                 lambda v=v: (self._set_hover(False), c.drives.open(v)), [ej]),
                                       False, False, 0)
            if not vols:
                self._empty(self.u_list, "No hay medios extraíbles conectados")
            self.u_list.show_all()

    def _remove_notif(self, n):
        if n in self.core.notifs:
            self.core.notifs.remove(n)
            self.core.changed("notifs")

    def _copy(self, text):
        self.core.clip.copy(text)
        self._set_hover(False)
        self.core.show_event(1.5, kind="pill", icon="edit-copy-symbolic", accent="green", text="Copiado")

    # ── dibujo ──
    def _draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        a = self.get_allocation()
        w, h = a.width, a.height
        r = min(w / 2, h / 2, 30)
        cr.new_sub_path()
        cr.arc(w - r, r, r, -math.pi / 2, 0)
        cr.arc(w - r, h - r, r, 0, math.pi / 2)
        cr.arc(r, h - r, r, math.pi / 2, math.pi)
        cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgb(0, 0, 0)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.07)
        cr.set_line_width(1)
        cr.stroke()
        return False

    # ── animación tipo resorte ──
    def _anim_step(self):
        settled = True
        for i in (0, 1):
            d = self.target[i] - self.cur[i]
            self.vel[i] = self.vel[i] * 0.66 + d * 0.15
            self.cur[i] += self.vel[i]
            if abs(d) > 0.5 or abs(self.vel[i]) > 0.5:
                settled = False
        for i in (0, 1):
            self.pvel[i] = self.pvel[i] * 0.66 - self.poff[i] * 0.15
            self.poff[i] += self.pvel[i]
            if abs(self.poff[i]) > 0.5 or abs(self.pvel[i]) > 0.5:
                settled = False
        if settled:
            self.cur = [float(self.target[0]), float(self.target[1])]
            self.vel = [0.0, 0.0]
            self.poff, self.pvel = [0.0, 0.0], [0.0, 0.0]
        if self.pending and (settled or (self.cur[0] >= self.target[0] * 0.8 and
                                         self.cur[1] >= self.target[1] * 0.8)):
            self.stack.set_visible_child_name(self.pending)
            self.pending = None
        w, h = max(1, round(self.cur[0])), max(1, round(self.cur[1]))
        self.stack.set_size_request(w, h)
        self.resize(w, h)
        self._place()
        self.queue_draw()
        if settled:
            self._anim_src = None
            return False
        return True

    def _natural(self, name, width):
        child = self.stack.get_child_by_name(name)
        if name == "compact":
            return child.get_preferred_width()[1]
        return child.get_preferred_height_for_width(width)[1]

    def _show(self, name, size):
        if name == "compact" and self.vertical:
            nat = self.c_box.get_preferred_height_for_width(H)[1]
            low = 150 if self.c_center.get_visible_child_name() == "level" else 84
            size = (H, max(low, min(300, nat + 4)))
        size = (int(size[0]), int(size[1]))
        if name != self.view:
            grow = size[1] > self.cur[1] + 4 or size[0] > self.cur[0] + 40
            if grow and self.view is not None:
                self.pending = name
            else:
                self.pending = None
                self.stack.set_visible_child_name(name)
            self.view = name
        if size != self.target:
            self.target = size
            if self._anim_src is None:
                self._anim_src = GLib.timeout_add(16, self._anim_step)

    # ── eventos ──
    def _on_enter(self, _w, ev):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._inside = True
        if (self.drag and self.drag["moving"]) or time.monotonic() - self._drag_end < 0.4:
            return False          # recién soltada tras arrastrar: no abrir
        if self._hover_src:
            GLib.source_remove(self._hover_src)
        self._hover_src = GLib.timeout_add(110, self._set_hover, True)
        return False

    def _on_leave(self, _w, ev):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._inside = False
        if self.drag and self.drag["moving"]:
            return False
        if self._hover_src:
            GLib.source_remove(self._hover_src)
        self._hover_src = GLib.timeout_add(self._leave_delay(), self._leave_timeout)
        return False

    def _leave_delay(self):
        """Cuánto esperar antes de cerrar cuando el ratón sale de la isla."""
        if time.monotonic() - self._nav_t < 1.5:
            return 8000           # se achicó al cambiar de página y el ratón quedó fuera: no es que se fuera
        if self._confirm:
            return 8000           # esperando la confirmación de apagar/reiniciar/salir
        return 1000 if self.page == "home" else 3000

    def _leave_timeout(self):
        self._hover_src = None
        if (self.pw_net and self.w_entry.has_focus()) or self.we_entry.has_focus():
            return False          # escribiendo (contraseña del Wi-Fi o ciudad): no cerrar
        if self._inside:
            return False          # el ratón volvió
        self._set_hover(False)
        return False

    def _set_hover(self, value):
        if self._hover_src:
            GLib.source_remove(self._hover_src)
            self._hover_src = None
        if value and not self.hover:
            self.core.radios.refresh()
            ev = self.core.event
            self.card_hold = bool(self.view == "card" and ev and time.monotonic() < ev["until"])
        self.hover = value
        if not value:
            if self.card_hold and self.core.event:
                # al salir de la notificación, darle unos segundos más antes de cerrarla
                self.core.event["until"] = max(self.core.event["until"], time.monotonic() + 3.0)
                GLib.timeout_add(3100, self.core.refresh)
            self.card_hold = False
            self.page = "home"
            self.pw_net = None
            self.w_pw.hide()
            self._confirm = None
        self.refresh()
        return False

    def _on_click(self, _w, ev):
        if ev.button != 1:
            return False
        d, self.drag = self.drag, None
        if d and d["moving"]:
            self._drop()
            return True
        if time.monotonic() - self._drag_end < 0.3:
            return True           # fin de un arrastre: no es un clic
        if self.view == "card" and self.core.event and self.core.event.get("action"):
            act = self.core.event["action"]
            self.core.event = None
            self.card_hold = False
            act()
            self.core.refresh()
            return True
        if self.view == "compact":
            self._set_hover(True)
            return True
        return False

    def _on_scroll(self, _w, ev):
        if self.view in ("compact", "card") and ev.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.DOWN):
            Volume.step(ev.direction == Gdk.ScrollDirection.UP)
            return True
        return False

    # ── arrastre y acople a los bordes ──
    def _mon_size(self):
        g = self.monitor.get_geometry()
        return g.width, g.height

    def _pointer(self):
        """Posición del ratón relativa a la ventana (en Wayland no hay coordenadas globales)."""
        win = self.get_window()
        dev = self.get_display().get_default_seat().get_pointer()
        _, x, y, _ = win.get_device_position(dev)
        return x, y

    @staticmethod
    def _nearest_edge(cx, cy, mw, mh):
        dist = {"top": cy, "bottom": mh - cy, "left": cx, "right": mw - cx}
        return min(dist, key=dist.get)

    def _target_xy(self, w, h):
        mw, mh = self._mon_size()
        if self.drag and self.drag["moving"]:
            cx, cy = self.drag["c"]
        else:
            e, p = self.core.dock["edge"], self.core.dock["pos"]
            if e in ("top", "bottom"):
                cx = p * mw
                cy = GAP + h / 2 if e == "top" else mh - GAP - h / 2
            else:
                cy = p * mh
                cx = GAP + w / 2 if e == "left" else mw - GAP - w / 2
        x = max(GAP, min(cx - w / 2, mw - w - GAP))
        y = max(GAP, min(cy - h / 2, mh - h - GAP))
        return x, y

    def _place(self):
        """Coloca la ventana según el borde al que está pegada (o donde se esté arrastrando)."""
        w, h = max(1, round(self.cur[0])), max(1, round(self.cur[1]))
        mw, mh = self._mon_size()
        x, y = self._target_xy(w, h)
        x, y = round(x + self.poff[0]), round(y + self.poff[1])
        self._last_xy = (x, y)
        edge = None if self.drag and self.drag["moving"] else self.core.dock["edge"]
        E = GtkLayerShell.Edge
        if edge == "bottom":        # crece hacia arriba
            layout = ((E.BOTTOM, E.LEFT), {E.BOTTOM: mh - y - h, E.LEFT: x})
        elif edge == "right":       # crece hacia la izquierda
            layout = ((E.TOP, E.RIGHT), {E.TOP: y, E.RIGHT: mw - x - w})
        else:
            layout = ((E.TOP, E.LEFT), {E.TOP: y, E.LEFT: x})
        if layout == self._layout:
            return
        anchors, margins = layout
        if self._layout is None or anchors != self._layout[0]:
            for e in (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT):
                GtkLayerShell.set_anchor(self, e, e in anchors)
        for e in (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT):
            GtkLayerShell.set_margin(self, e, int(margins.get(e, 0)))
        self._layout = layout
        if self._applied == (0, 0) and not self.get_realized():
            self._applied = (x, y)

    def _after_paint(self, _clock):
        self._applied = self._last_xy

    def _kick(self):
        if self._anim_src is None:
            self._anim_src = GLib.timeout_add(16, self._anim_step)

    def _set_vertical(self, v):
        if v == self.vertical:
            return
        self.vertical = v
        b = self.c_box
        b.set_orientation(Gtk.Orientation.VERTICAL if v else Gtk.Orientation.HORIZONTAL)
        b.set_margin_start(0 if v else 14)
        b.set_margin_end(0 if v else 14)
        b.set_margin_top(12 if v else 0)
        b.set_margin_bottom(12 if v else 0)
        self.c_center.set_hexpand(not v)
        self.c_center.set_vexpand(v)
        self.c_level.set_orientation(Gtk.Orientation.VERTICAL if v else Gtk.Orientation.HORIZONTAL)
        self.c_level.set_inverted(v)
        self.c_level.set_halign(Gtk.Align.CENTER if v else Gtk.Align.FILL)
        self.c_level.set_valign(Gtk.Align.FILL if v else Gtk.Align.CENTER)

    def _vtext(self, lb, text, maxc):
        """Pone el texto de la píldora; en vertical lo gira o lo apila para que quepa."""
        ell = lb is self.c_label
        if not self.vertical:
            lb.set_angle(0)
            lb.set_justify(Gtk.Justification.LEFT)
            lb.set_ellipsize(Pango.EllipsizeMode.END if ell else Pango.EllipsizeMode.NONE)
            lb.set_text(text)
            return
        lb.set_ellipsize(Pango.EllipsizeMode.NONE)   # GTK ignora el giro si hay elipsis
        lb.set_justify(Gtk.Justification.CENTER)
        if re.fullmatch(r"\d{1,2}:\d{2}", text):     # hora o temporizador: 14 / 05
            lb.set_angle(0)
            lb.set_text(text.replace(":", "\n"))
        elif len(text) <= 3:
            lb.set_angle(0)
            lb.set_text(text)
        else:
            lb.set_angle(90)
            lb.set_text(text if len(text) <= maxc else text[:maxc - 1].rstrip() + "…")

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
            if (self.pw_net and self.w_entry.has_focus()) or self.we_entry.has_focus():
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
        vertical = self._nearest_edge(*d["c"], mw, mh) in ("left", "right")
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
        cx, cy = x0 + w / 2, y0 + h / 2
        edge = self._nearest_edge(cx, cy, mw, mh)
        pos = cx / mw if edge in ("top", "bottom") else cy / mh
        dbg("soltada en", edge, round(pos, 2))
        self.core.set_dock(edge, pos)
        # que viaje con suavidad desde donde se soltó hasta el borde
        tx, ty = self._target_xy(w, h)
        self.poff = [x0 - tx, y0 - ty]
        self.pvel = [0.0, 0.0]
        self._layout = None
        self._place()
        self._kick()

    # ── compacta ──
    def _compact(self, left=None, icon_name=None, accent=None, text="", level=None,
                 right=None, right_text="", right_accent=None, xalign=0.0, text_accent=None, wkind=None):
        self.c_wicon.set_visible(wkind is not None)
        if wkind:
            self.c_wicon.set_kind(wkind)
        if left == "icon":
            self.c_icon.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
            set_accent(self.c_icon, accent)
        if left:
            self.c_left.set_visible_child_name(left)
        self.c_left.set_visible(left is not None)
        if level is not None:
            self.c_level.set_value(level)
            self.c_center.set_visible_child_name("level")
        else:
            self._vtext(self.c_label, text, 16)
            self.c_label.set_xalign(0.5 if self.vertical else xalign)
            set_accent(self.c_label, text_accent)
            self.c_center.set_visible_child_name("label")
        if right == "label":
            self._vtext(self.c_rlabel, right_text, 10)
            set_accent(self.c_rlabel, right_accent)
        if right:
            self.c_right.set_visible_child_name(right)
        self.c_right.set_visible(right is not None)

    # ── decide qué mostrar ──
    def refresh(self):
        c = self.core
        now = time.monotonic()
        m = c.media
        playing = bool(m and m["playing"])
        timer_left = (c.timer_end - now) if c.timer_end else None
        self._update_home(c, m, playing, timer_left)
        self._fill_lists()
        eq_on = False
        p = c.pomo
        pomo_on = p.active
        pomo_acc = "red" if p.phase == "work" else "green"

        if c.alert_until and now < c.alert_until:
            self.a_sub.set_text(f"Temporizador de {fmt_secs(c.timer_total)}")
            self._show("alert", (360, 64))
        elif self.card_hold and c.event and c.event.get("kind") == "card":
            c.event["until"] = max(c.event["until"], now + 2.0)   # sigue abierta mientras el ratón esté encima
            self._show_event(c.event)
        elif self.hover:
            self._show(self.page, (W_EXP, min(580, self._natural(self.page, W_EXP))))
        elif c.event and now < c.event["until"]:
            self._show_event(c.event)
        elif playing:
            if pomo_on:
                self._compact("art", text=m["title"], right="label", right_text=fmt_secs(p.left()),
                              right_accent=pomo_acc)
            elif timer_left is not None:
                self._compact("art", text=m["title"], right="label", right_text=fmt_secs(timer_left),
                              right_accent="orange")
            else:
                self._compact("art", text=m["title"], right="eq")
                eq_on = True
            self._show("compact", (300, H))
        elif pomo_on:
            self._compact("icon", "timer-symbolic", pomo_acc,
                          text=f"{Pomodoro.LABEL[p.phase]}  {fmt_secs(p.left())}", text_accent=pomo_acc,
                          right="label" if not p.running else None, right_text="En pausa")
            nat = self._natural("compact", 0)
            self._show("compact", (max(190, min(320, nat + 4)), H))
        elif timer_left is not None:
            self._compact("icon", "alarm-symbolic", "orange", text=fmt_secs(timer_left), xalign=0.5,
                          text_accent="orange")
            self._show("compact", (170, H))
        else:
            dot = c.unread > 0
            wd = c.weather.data
            self._compact("icon" if dot else None, "preferences-system-notifications-symbolic", "red",
                          text=time.strftime("%H:%M"), xalign=0.5 if not wd else 0.0,
                          right="label" if wd else None, right_text=f"{wd['temp']:.0f}°" if wd else "",
                          wkind=wd.get("kind") if wd else None)
            self._show("compact", ((209 if dot else 189) if wd else (150 if dot else 130), H))
        if c.alert_until and now >= c.alert_until:
            c.alert_until = None
        self.c_eq.set_playing(eq_on)
        return False

    def _show_event(self, ev):
        if ev["kind"] == "card":
            if ev.get("pixbuf") is not None:
                self.k_art.set_pixbuf(ev["pixbuf"])
                self.k_left.set_visible_child_name("art")
            else:
                self.k_icon.set_from_icon_name(ev.get("icon") or "dialog-information-symbolic", Gtk.IconSize.DND)
                self.k_left.set_visible_child_name("icon")
            self.k_app.set_text(ev.get("app", ""))
            self.k_title.set_text(ev.get("title", ""))
            self.k_body.set_text(ev.get("body", ""))
            self.k_body.set_visible(bool(ev.get("body")))
            self.k_body.set_lines(10 if self.card_hold else 2)
            self.k_hint.set_visible(self.card_hold and bool(ev.get("action")))
            self._show("card", (W_CARD, self._natural("card", W_CARD)))
        elif ev["kind"] == "volume":
            v, muted = ev["value"], ev["muted"]
            ic = ("audio-volume-muted-symbolic" if muted or v == 0 else
                  "audio-volume-low-symbolic" if v < 0.34 else
                  "audio-volume-medium-symbolic" if v < 0.67 else "audio-volume-high-symbolic")
            self._compact("icon", ic, level=0 if muted else min(v, 1.0), right="label",
                          right_text="Silencio" if muted else f"{round(v * 100)}%")
            self._show("compact", (290, H))
        else:
            self._compact("icon", ev.get("icon"), ev.get("accent"), text=ev.get("text", ""),
                          right="label" if ev.get("right") else None, right_text=ev.get("right", ""),
                          right_accent=ev.get("right_accent"))
            nat = self._natural("compact", 0)
            self._show("compact", (max(200, min(400, nat + 4)), H))

    def _update_home(self, c, m, playing, timer_left):
        self.h_clock.set_text(time.strftime("%H:%M"))
        self.h_date.set_text(fecha())
        b = c.battery
        if b.present:
            lim = c.charge_limit
            self.h_bat.set_text(f"{b.percent:.0f}%" + (" · cargando" if b.charging else "") +
                                (f" · límite {lim.end}%" if lim.enabled else ""))
            self.h_bat_icon.set_from_icon_name(bat_icon(b.percent, b.charging), Gtk.IconSize.MENU)
            set_accent(self.h_bat_icon, "green" if b.charging else ("red" if b.percent <= 15 else None))
        self.h_bat.set_visible(b.present)
        self.h_bat_icon.set_visible(b.present)

        self.h_media.set_visible(m is not None)
        self.c_art.set_pixbuf(c.art)
        self.m_art.set_pixbuf(c.art)
        if m:
            self.m_title.set_text(m["title"])
            self.m_artist.set_text(m["artist"] or m["album"])
            self.m_play_img.set_from_icon_name(
                "media-playback-pause-symbolic" if playing else "media-playback-start-symbolic",
                Gtk.IconSize.LARGE_TOOLBAR)
            self.m_pos.set_text(fmt_secs(m["position"]))
            self.m_len.set_text(fmt_secs(m["length"]) if m["length"] else "--:--")
            self.m_bar.set_value(min(1.0, m["position"] / m["length"]) if m["length"] else 0)

        v, muted = c.volume.value, c.volume.muted
        if not self.v_scale.has_grab():
            self._vol_lock = True
            self.v_scale.set_value(round(v * 100))
            self._vol_lock = False
        self.v_pct.set_text("—" if muted else f"{round(v * 100)}%")
        self.v_img.set_from_icon_name("audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic",
                                      Gtk.IconSize.MENU)

        w = c.wifi
        self.t_wifi.set(w.enabled, (w.active or ("Cable" if w.wired else "Sin red")) if w.enabled else "Apagado",
                        "network-wireless-symbolic" if w.enabled else "network-wireless-disabled-symbolic")
        connected = [d["name"] for d in c.bt.devices.values() if d["connected"]]
        self.t_bt.set(c.bt.powered, (connected[0] if connected else "Encendido") if c.bt.powered else "Apagado",
                      "bluetooth-active-symbolic" if c.bt.powered else "bluetooth-disabled-symbolic")
        self.t_air.set(c.radios.airplane, "Activado" if c.radios.airplane else "")
        self.t_dnd.set(c.notif.dnd, "Activado" if c.notif.dnd else "")
        md = c.modes
        self.t_dark.set(md.dark, "Activado" if md.dark else "")
        self.t_night.set(md.night, "Activada" if md.night else "")
        self.t_saver.set(md.profile == "power-saver",
                         {"power-saver": "Activado", "performance": "Rendimiento"}.get(md.profile, ""))
        self.t_awake.set(md.awake, "Activado" if md.awake else "")
        lim = c.charge_limit
        self.t_care.set(lim.enabled, f"Hasta {lim.end}%" if lim.enabled else "Hasta 100%")

        if c.unread:
            self.badge.set_text(str(min(c.unread, 99)))
            self.badge.show()
        else:
            self.badge.hide()
        self._set_count("github", len(c.github.review))
        self._set_count("teams", c.ms_unread["teams"])
        self._set_count("outlook", c.ms_unread["outlook"])

        wd = c.weather.data
        if wd:
            self.h_w.set_text(f"{wd['temp']:.0f}° · {wd['desc']}")
            self.h_w_icon.set_kind(wd.get("kind", "cloudy"))
        else:
            self.h_w.set_text("Cargando clima…" if c.weather.loading else "Clima")

        p = c.pomo
        acc = "red" if p.phase == "work" else "green"
        self.po_phase.set_text(Pomodoro.LABEL[p.phase] + ("" if p.running or not p.active else " · en pausa"))
        set_accent(self.po_phase, acc)
        self.po_time.set_text(fmt_secs(p.left()))
        set_accent(self.po_time, acc if p.active else None)
        self.po_cycle.set_text(p.cycle_text())
        self.po_play.set_from_icon_name("media-playback-pause-symbolic" if p.running else
                                        "media-playback-start-symbolic", Gtk.IconSize.LARGE_TOOLBAR)

        self.t_big.set_text(fmt_secs(timer_left) if timer_left is not None else "—")
        set_accent(self.t_big, "orange" if timer_left is not None else None)
        self.t_stop.set_visible(timer_left is not None)

        for key, (btn, lb, txt) in self.pw_buttons.items():
            confirming = self._confirm == key
            set_class(btn, "confirm", confirming)
            lb.set_text("¿Seguro?" if confirming else txt)
        if not self._confirm:
            self.pw_hint.set_text("")


def main():
    app = Gtk.Application(application_id="cl.luis.IslaDinamica")
    state = {}

    prov = Gtk.CssProvider()
    prov.load_from_data(CSS)

    def activate(a):
        if "core" in state:
            return
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        a.hold()
        state["core"] = Core(a)
    app.connect("activate", activate)
    app.run(None)


if __name__ == "__main__":
    main()
