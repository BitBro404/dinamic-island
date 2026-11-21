#!/usr/bin/env python3
"""Isla dinámica para escritorio Linux (Wayland + layer-shell, GTK3).

Muestra arriba al centro una "píldora" negra que cambia de forma:
  - reposo: hora
  - música (MPRIS: Spotify, Firefox, VLC...): carátula, título y ecualizador
  - volumen: aparece al cambiarlo (también con la rueda del ratón sobre la isla)
  - batería: al enchufar el cargador o con batería baja
  - temporizador: 5/15/25 min desde la vista expandida
Pasa el ratón por encima para expandirla.
"""
import math
import os
import re
import subprocess
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_foreign("cairo")
import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, GtkLayerShell, Pango  # noqa: E402

COMPACT_H = 34
SIZES = {
    "clock": (130, COMPACT_H),
    "timer": (170, COMPACT_H),
    "media_c": (300, COMPACT_H),
    "osd": (290, COMPACT_H),
    "event": (260, COMPACT_H),
    "media": (410, 172),
    "home": (410, 112),
    "alert": (360, 64),
}

CSS = b"""
window { background: transparent; }
* { color: #f5f5f7; font-family: "Inter", "Cantarell", sans-serif; }
.c-text { font-weight: 600; font-size: 13px; }
.dim { color: #8e8e93; font-size: 12px; }
.title { font-weight: 700; font-size: 15px; }
.artist { color: #a1a1a6; font-size: 13px; }
.bigclock { font-weight: 700; font-size: 34px; }
.time-small { color: #8e8e93; font-size: 11px; font-feature-settings: "tnum"; }
.orange { color: #ff9f0a; }
.green { color: #30d158; }
.red { color: #ff453a; }
button.ctrl {
  background: none; background-image: none; border: none; box-shadow: none;
  min-width: 40px; min-height: 40px; padding: 0; border-radius: 20px;
}
button.ctrl:hover { background: rgba(255,255,255,0.12); }
button.chip {
  background: rgba(255,255,255,0.10); background-image: none; border: none;
  box-shadow: none; border-radius: 14px; padding: 3px 12px; min-height: 0;
}
button.chip:hover { background: rgba(255,255,255,0.22); }
button.chip label { font-weight: 600; font-size: 12px; }
button.chip.stop label { color: #ff453a; }
levelbar trough { min-height: 4px; border: none; border-radius: 2px; background: rgba(255,255,255,0.18); padding: 0; }
levelbar block.filled { border: none; border-radius: 2px; background: #f5f5f7; }
levelbar block.empty { border: none; background: transparent; }
levelbar.thin trough { min-height: 3px; }
"""

ACCENTS = ("orange", "green", "red")


def set_accent(widget, accent=None):
    ctx = widget.get_style_context()
    for a in ACCENTS:
        ctx.remove_class(a)
    if accent:
        ctx.add_class(accent)


def fmt_secs(s):
    s = max(0, int(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def label(text="", cls=None, xalign=0.0, ellipsize=True):
    lb = Gtk.Label(label=text, xalign=xalign)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if cls:
        for c in cls.split():
            lb.get_style_context().add_class(c)
    return lb


# ───────────────────────────── widgets dibujados ─────────────────────────────
class Art(Gtk.DrawingArea):
    """Carátula con esquinas redondeadas (o un placeholder con nota musical)."""

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
            self._scaled = pb.scale_simple(self.size * sf, self.size * sf, GdkPixbuf.InterpType.BILINEAR)
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
            # nota musical dibujada a mano (cabeza + plica + bandera)
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
    """Barritas animadas mientras suena música."""

    def __init__(self, w=22, h=16):
        super().__init__()
        self.w, self.h, self.playing, self._tick = w, h, False, None
        self.set_size_request(w, h)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self._draw)

    def set_playing(self, playing):
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
            x = i * (bw + gap)
            y = (self.h - hh) / 2
            r = bw / 2
            cr.new_sub_path()
            cr.arc(x + r, y + r, r, math.pi, 0)
            cr.arc(x + r, y + hh - r, r, 0, math.pi)
            cr.close_path()
            cr.fill()
        return False


# ───────────────────────────── fuentes de datos ─────────────────────────────
class Media:
    """Lee reproductores MPRIS por D-Bus (sin playerctl)."""

    PREFIX = "org.mpris.MediaPlayer2."
    PATH = "/org/mpris/MediaPlayer2"
    IFACE = "org.mpris.MediaPlayer2.Player"

    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.last_active = None

    def _call(self, name, path, iface, method, params, rtype, timeout=300):
        return self.bus.call_sync(name, path, iface, method, params,
                                  GLib.VariantType(rtype) if rtype else None,
                                  Gio.DBusCallFlags.NONE, timeout, None)

    def poll(self):
        """Devuelve dict con el reproductor relevante o None."""
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
                "name": n,
                "title": title,
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
    """Escucha cambios de volumen con `pactl subscribe`; lee/escribe con wpctl."""

    def __init__(self, on_change):
        self.on_change = on_change
        self.value, self.muted = self.read()
        self._pending = None
        try:
            self.proc = Gio.Subprocess.new(["env", "LC_ALL=C", "pactl", "subscribe"], Gio.SubprocessFlags.STDOUT_PIPE)
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


class Battery:
    """Batería vía UPower (D-Bus del sistema)."""

    CHARGING, DISCHARGING, FULL = 1, 2, 4

    def __init__(self, on_event):
        self.on_event = on_event
        self.proxy = None
        self.low_warned = False
        try:
            self.proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.UPower",
                "/org/freedesktop/UPower/devices/DisplayDevice", "org.freedesktop.UPower.Device", None)
            self.proxy.connect("g-properties-changed", self._changed)
        except GLib.Error:
            self.proxy = None
        self.state = self._get("State", 0)

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

    def _changed(self, *_):
        st = self._get("State", 0)
        pct = self.percent
        if st != self.state:
            if st == self.CHARGING and self.state != self.FULL:
                self.on_event("charging", pct)
            elif st == self.DISCHARGING and self.state in (self.CHARGING, self.FULL):
                self.on_event("unplugged", pct)
            self.state = st
        if st == self.DISCHARGING and pct <= 15 and not self.low_warned:
            self.low_warned = True
            self.on_event("low", pct)
        if st != self.DISCHARGING or pct > 20:
            self.low_warned = False


# ───────────────────────────── la isla ─────────────────────────────
class Island(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Isla dinámica")
        self.set_decorated(False)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "isla-dinamica")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 6)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # estado
        self.hover = False
        self._hover_src = None
        self.media = None
        self.osd = None          # dict(kind, until, ...)
        self.timer_end = None
        self.timer_total = 0
        self.alert_until = None
        self.view = None
        self.pending_view = None
        self.target = SIZES["clock"]
        self.cur = list(self.target)
        self.vel = [0.0, 0.0]
        self._anim_src = None
        self._art_url = None
        self._art_cache = {}

        # contenedor + eventos
        ev = Gtk.EventBox()
        ev.set_visible_window(False)
        ev.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK |
                      Gdk.EventMask.SCROLL_MASK)
        ev.connect("enter-notify-event", self._on_enter)
        ev.connect("leave-notify-event", self._on_leave)
        ev.connect("scroll-event", self._on_scroll)
        self.add(ev)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(160)
        self.stack.set_hhomogeneous(False)
        self.stack.set_vhomogeneous(False)
        self.stack.set_size_request(*self.cur)
        ev.add(self.stack)

        self.stack.add_named(self._build_compact(), "compact")
        self.stack.add_named(self._build_media(), "media")
        self.stack.add_named(self._build_home(), "home")
        self.stack.add_named(self._build_alert(), "alert")

        self.connect("draw", self._draw)

        self.mpris = Media()
        self.volume = Volume(self._on_volume)
        self.battery = Battery(self._on_battery)

        self._tick()
        GLib.timeout_add(1000, self._tick)
        self.show_all()

    # ── construcción de vistas ──
    def _build_compact(self):
        box = Gtk.Box(spacing=9, margin_start=14, margin_end=14)
        self.c_left = Gtk.Stack()
        self.c_icon = Gtk.Image()
        self.c_art = Art(22, 6)
        self.c_left.add_named(self.c_icon, "icon")
        self.c_left.add_named(self.c_art, "art")
        self.c_left.add_named(Gtk.Box(), "none")
        box.pack_start(self.c_left, False, False, 0)

        self.c_center = Gtk.Stack(hexpand=True)
        self.c_label = label("", "c-text")
        self.c_level = Gtk.LevelBar(valign=Gtk.Align.CENTER)
        self.c_level.set_min_value(0)
        self.c_level.set_max_value(1)
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
        self.c_right.add_named(Gtk.Box(), "none")
        box.pack_end(self.c_right, False, False, 0)
        return box

    def _ctrl(self, icon, cb, size=Gtk.IconSize.LARGE_TOOLBAR):
        b = Gtk.Button()
        b.get_style_context().add_class("ctrl")
        img = Gtk.Image.new_from_icon_name(icon, size)
        b.add(img)
        b.connect("clicked", cb)
        return b, img

    def _build_media(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_start=18, margin_end=18, margin_top=16, margin_bottom=10)
        top = Gtk.Box(spacing=12)
        self.m_art = Art(56, 12)
        top.pack_start(self.m_art, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=2)
        self.m_title = label("", "title")
        self.m_artist = label("", "artist")
        txt.pack_start(self.m_title, False, False, 0)
        txt.pack_start(self.m_artist, False, False, 0)
        top.pack_start(txt, True, True, 0)
        self.m_eq = Equalizer(24, 20)
        top.pack_end(self.m_eq, False, False, 0)
        box.pack_start(top, False, False, 0)

        prog = Gtk.Box(spacing=8)
        self.m_pos = label("0:00", "time-small", ellipsize=False)
        self.m_len = label("0:00", "time-small", ellipsize=False)
        self.m_bar = Gtk.LevelBar(valign=Gtk.Align.CENTER, hexpand=True)
        self.m_bar.get_style_context().add_class("thin")
        for off in ("low", "high", "full"):
            self.m_bar.remove_offset_value(off)
        prog.pack_start(self.m_pos, False, False, 0)
        prog.pack_start(self.m_bar, True, True, 0)
        prog.pack_start(self.m_len, False, False, 0)
        box.pack_start(prog, False, False, 0)

        ctr = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
        ctr.pack_start(self._ctrl("media-skip-backward-symbolic", lambda *_: self._media_cmd("Previous"))[0], False, False, 0)
        b, self.m_play_img = self._ctrl("media-playback-pause-symbolic", lambda *_: self._media_cmd("PlayPause"), Gtk.IconSize.DND)
        ctr.pack_start(b, False, False, 0)
        ctr.pack_start(self._ctrl("media-skip-forward-symbolic", lambda *_: self._media_cmd("Next"))[0], False, False, 0)
        box.pack_start(ctr, False, False, 0)
        return box

    def _chip(self, text, cb, extra=None):
        b = Gtk.Button(label=text)
        b.get_style_context().add_class("chip")
        if extra:
            b.get_style_context().add_class(extra)
        b.connect("clicked", cb)
        return b

    def _build_home(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin_start=20, margin_end=20, margin_top=12, margin_bottom=14)
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
        top.pack_end(side, True, True, 0)
        box.pack_start(top, False, False, 0)

        row = Gtk.Box(spacing=8)
        icon = Gtk.Image.new_from_icon_name("alarm-symbolic", Gtk.IconSize.MENU)
        row.pack_start(icon, False, False, 0)
        self.h_timer_lbl = label("Temporizador", "dim", ellipsize=False)
        row.pack_start(self.h_timer_lbl, False, False, 0)
        self.h_chips = Gtk.Box(spacing=6, halign=Gtk.Align.END, hexpand=True)
        for m in (5, 15, 25):
            self.h_chips.pack_start(self._chip(f"{m} min", lambda _b, m=m: self.start_timer(m * 60)), False, False, 0)
        self.h_stop = self._chip("Detener", lambda *_: self.stop_timer(), "stop")
        row.pack_end(self.h_stop, False, False, 0)
        row.pack_end(self.h_chips, True, True, 0)
        box.pack_start(row, False, False, 0)
        return box

    def _build_alert(self):
        box = Gtk.Box(spacing=12, margin_start=18, margin_end=14)
        self.a_icon = Gtk.Image.new_from_icon_name("alarm-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        set_accent(self.a_icon, "orange")
        box.pack_start(self.a_icon, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        txt.pack_start(label("¡Tiempo cumplido!", "title"), False, False, 0)
        self.a_sub = label("", "artist")
        txt.pack_start(self.a_sub, False, False, 0)
        box.pack_start(txt, True, True, 0)
        ok = self._chip("OK", lambda *_: self._dismiss_alert())
        ok.set_valign(Gtk.Align.CENTER)
        box.pack_end(ok, False, False, 0)
        return box

    # ── dibujo de la píldora ──
    def _draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        a = self.get_allocation()
        w, h = a.width, a.height
        r = min(h / 2, 30)
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
    def _animate_to(self, size):
        self.target = size
        if self._anim_src is None:
            self._anim_src = GLib.timeout_add(16, self._anim_step)

    def _anim_step(self):
        settled = True
        for i in (0, 1):
            d = self.target[i] - self.cur[i]
            self.vel[i] = self.vel[i] * 0.66 + d * 0.15
            self.cur[i] += self.vel[i]
            if abs(d) > 0.5 or abs(self.vel[i]) > 0.5:
                settled = False
        if settled:
            self.cur = list(self.target)
            self.vel = [0.0, 0.0]
        if self.pending_view and (settled or (self.cur[0] >= self.target[0] * 0.8 and
                                              self.cur[1] >= self.target[1] * 0.8)):
            self.stack.set_visible_child_name(self.pending_view)
            self.pending_view = None
        w, h = max(1, round(self.cur[0])), max(1, round(self.cur[1]))
        self.stack.set_size_request(w, h)
        self.resize(w, h)
        self.queue_draw()
        if settled:
            self._anim_src = None
            return False
        return True

    def _show(self, stack_child, size_key):
        size = SIZES[size_key]
        if (stack_child, size_key) == self.view:
            if size != self.target:
                self._animate_to(size)
            return
        growing = size[1] > self.cur[1] + 4 and stack_child != "compact"
        self.view = (stack_child, size_key)
        if growing:
            self.pending_view = stack_child
        else:
            self.pending_view = None
            self.stack.set_visible_child_name(stack_child)
        self._animate_to(size)

    # ── eventos ──
    def _on_enter(self, _w, ev):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False
        if self._hover_src:
            GLib.source_remove(self._hover_src)
        self._hover_src = GLib.timeout_add(110, self._set_hover, True)
        return False

    def _on_leave(self, _w, ev):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False
        if self._hover_src:
            GLib.source_remove(self._hover_src)
        self._hover_src = GLib.timeout_add(260, self._set_hover, False)
        return False

    def _set_hover(self, value):
        self._hover_src = None
        self.hover = value
        self.refresh()
        return False

    def _on_scroll(self, _w, ev):
        if ev.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.DOWN):
            Volume.step(ev.direction == Gdk.ScrollDirection.UP)
        return True

    def _on_volume(self, value, muted):
        self.osd = {"kind": "volume", "value": value, "muted": muted, "until": time.monotonic() + 1.8}
        self.refresh()
        GLib.timeout_add(1850, self.refresh)

    def _on_battery(self, kind, pct):
        self.osd = {"kind": kind, "value": pct, "until": time.monotonic() + 3.0}
        self.refresh()
        GLib.timeout_add(3050, self.refresh)

    def _media_cmd(self, method):
        if self.media:
            self.mpris.command(self.media["name"], method)
            GLib.timeout_add(180, self._poll_media)

    def _poll_media(self):
        self.media = self.mpris.poll()
        self._load_art()
        self.refresh()
        return False

    # ── temporizador ──
    def start_timer(self, secs):
        self.timer_total = secs
        self.timer_end = time.monotonic() + secs
        self.refresh()

    def stop_timer(self):
        self.timer_end = None
        self.refresh()

    def _dismiss_alert(self):
        self.alert_until = None
        self.refresh()

    def _tick(self):
        now = time.monotonic()
        if self.timer_end and now >= self.timer_end:
            self.timer_end = None
            self.alert_until = now + 10
            self.a_sub.set_text(f"Temporizador de {fmt_secs(self.timer_total)}")
            for snd in ("/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
                        "/usr/share/sounds/freedesktop/stereo/complete.oga"):
                if os.path.exists(snd):
                    subprocess.Popen(["pw-play", snd], stderr=subprocess.DEVNULL)
                    break
        self.media = self.mpris.poll()
        self._load_art()
        self.refresh()
        return True

    # ── carátula ──
    def _load_art(self):
        url = self.media["art"] if self.media else None
        if url == self._art_url:
            return
        self._art_url = url
        if not url:
            self._set_art(None)
            return
        if url in self._art_cache:
            self._set_art(self._art_cache[url])
            return

        def done(f, res):
            pb = None
            try:
                _ok, data, _etag = f.load_contents_finish(res)
                loader = GdkPixbuf.PixbufLoader()
                loader.write(data)
                loader.close()
                pb = loader.get_pixbuf()
                w, h = pb.get_width(), pb.get_height()
                side = min(w, h)
                pb = pb.new_subpixbuf((w - side) // 2, (h - side) // 2, side, side)
                pb = pb.scale_simple(128, 128, GdkPixbuf.InterpType.BILINEAR)
            except (GLib.Error, AttributeError):
                pb = None
            self._art_cache[url] = pb
            if self._art_url == url:
                self._set_art(pb)

        Gio.File.new_for_uri(url).load_contents_async(None, done)

    def _set_art(self, pb):
        self.c_art.set_pixbuf(pb)
        self.m_art.set_pixbuf(pb)

    # ── decide qué mostrar ──
    def _compact(self, left=None, icon=None, accent=None, text="", level=None,
                 right=None, right_text="", right_accent=None, xalign=0.0):
        set_accent(self.c_label, None)
        if left == "icon":
            self.c_icon.set_from_icon_name(icon, Gtk.IconSize.MENU)
            set_accent(self.c_icon, accent)
        self.c_left.set_visible_child_name(left or "none")
        self.c_left.set_visible(left is not None)
        if level is not None:
            self.c_level.set_value(level)
            self.c_center.set_visible_child_name("level")
        else:
            self.c_label.set_text(text)
            self.c_label.set_xalign(xalign)
            self.c_center.set_visible_child_name("label")
        if right == "label":
            self.c_rlabel.set_text(right_text)
            set_accent(self.c_rlabel, right_accent)
        self.c_right.set_visible_child_name(right or "none")
        self.c_right.set_visible(right is not None)

    def refresh(self):
        now = time.monotonic()
        m = self.media
        playing = bool(m and m["playing"])
        self.c_eq.set_playing(bool(playing and self.view and self.view[1] == "media_c"))
        self.m_eq.set_playing(bool(playing and self.view and self.view[0] == "media"))
        timer_left = (self.timer_end - now) if self.timer_end else None

        # contenido de las vistas expandidas (barato, se actualiza siempre)
        self.h_clock.set_text(time.strftime("%H:%M"))
        self.h_date.set_text(_fecha())
        if self.battery.present:
            pct = self.battery.percent
            charging = self.battery.state in (Battery.CHARGING, Battery.FULL)
            self.h_bat.set_text(f"{pct:.0f}%")
            self.h_bat_icon.set_from_icon_name(_bat_icon(pct, charging), Gtk.IconSize.MENU)
            set_accent(self.h_bat_icon, "green" if charging else ("red" if pct <= 15 else None))
        self.h_bat.set_visible(self.battery.present)
        self.h_bat_icon.set_visible(self.battery.present)
        if timer_left is not None:
            self.h_timer_lbl.set_text(f"Quedan {fmt_secs(timer_left)}")
            set_accent(self.h_timer_lbl, "orange")
        else:
            self.h_timer_lbl.set_text("Temporizador")
            set_accent(self.h_timer_lbl, None)
        self.h_chips.set_visible(timer_left is None)
        self.h_stop.set_visible(timer_left is not None)
        if m:
            self.m_title.set_text(m["title"])
            self.m_artist.set_text(m["artist"] or m["album"])
            self.m_play_img.set_from_icon_name(
                "media-playback-pause-symbolic" if playing else "media-playback-start-symbolic", Gtk.IconSize.DND)
            self.m_pos.set_text(fmt_secs(m["position"]))
            self.m_len.set_text(fmt_secs(m["length"]) if m["length"] else "--:--")
            self.m_bar.set_value(min(1.0, m["position"] / m["length"]) if m["length"] else 0)

        # 1. alerta del temporizador
        if self.alert_until and now < self.alert_until:
            self._show("alert", "alert")
            return False
        self.alert_until = None

        # 2. ratón encima → expandida
        if self.hover:
            self._show("media" if m else "home", "media" if m else "home")
            self.m_eq.set_playing(playing)
            return False

        # 3. avisos temporales (volumen / batería)
        if self.osd and now < self.osd["until"]:
            o = self.osd
            if o["kind"] == "volume":
                v, muted = o["value"], o["muted"]
                ic = ("audio-volume-muted-symbolic" if muted or v == 0 else
                      "audio-volume-low-symbolic" if v < 0.34 else
                      "audio-volume-medium-symbolic" if v < 0.67 else "audio-volume-high-symbolic")
                self._compact("icon", ic, level=0 if muted else min(v, 1.0),
                              right="label", right_text="Silencio" if muted else f"{round(v * 100)}%")
                self._show("compact", "osd")
            else:
                pct = o["value"]
                txt, acc, ic = {
                    "charging": ("Cargando", "green", _bat_icon(pct, True)),
                    "unplugged": ("Con batería", None, _bat_icon(pct, False)),
                    "low": ("Batería baja", "red", "battery-caution-symbolic"),
                }[o["kind"]]
                self._compact("icon", ic, acc, text=txt, right="label", right_text=f"{pct:.0f}%", right_accent=acc)
                self._show("compact", "event")
            return False
        self.osd = None

        # 4. compacta
        if playing:
            if timer_left is not None:
                self._compact("art", text=m["title"], right="label", right_text=fmt_secs(timer_left),
                              right_accent="orange")
            else:
                self._compact("art", text=m["title"], right="eq")
            self._show("compact", "media_c")
            self.c_eq.set_playing(timer_left is None)
        elif timer_left is not None:
            self._compact("icon", "alarm-symbolic", "orange", text=fmt_secs(timer_left), xalign=0.5)
            set_accent(self.c_label, "orange")
            self._show("compact", "timer")
            return False
        else:
            self._compact(text=time.strftime("%H:%M"), xalign=0.5)
            self._show("compact", "clock")
        set_accent(self.c_label, None)
        return False


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha():
    t = time.localtime()
    return f"{DIAS[t.tm_wday].capitalize()} {t.tm_mday} de {MESES[t.tm_mon - 1]}"


def _bat_icon(pct, charging):
    lvl = "full" if pct > 85 else "good" if pct > 50 else "low" if pct > 20 else "caution"
    return f"battery-{lvl}{'-charging' if charging else ''}-symbolic"


def main():
    app = Gtk.Application(application_id="cl.luis.IslaDinamica")
    app.connect("activate", lambda a: a.get_windows() or Island(a))
    app.run(None)


if __name__ == "__main__":
    main()
