"""Ecualizador de la píldora y espectro del reproductor (barras que siguen el sonido)."""
import math
import time

import cairo
from gi.repository import Gtk

from .art import GREEN


def resample(levels, n):
    """Lleva una lista de niveles a n valores (interpolando)."""
    if not levels:
        return [0.0] * n
    if len(levels) == n:
        return list(levels)
    out = []
    for j in range(n):
        p = j * (len(levels) - 1) / max(1, n - 1)
        i = int(p)
        f = p - i
        b = levels[min(i + 1, len(levels) - 1)]
        out.append(levels[i] * (1 - f) + b * f)
    return out


class Spectrum(Gtk.DrawingArea):
    """Ecualizador grande del reproductor: barras en espejo (graves al centro) que siguen el sonido,
    con el color de la carátula. levels_fn → lista 0..1 o None."""
    BW, GAP = 4, 3

    def __init__(self, h=40):
        super().__init__(hexpand=True)
        self.h, self.levels_fn, self.color, self.playing = h, None, GREEN, False
        self._shown, self._tick = [], None
        self.set_size_request(-1, h)
        self.connect("draw", self._draw)
        self.connect("unmap", lambda *_: self._stop())
        self.connect("map", lambda *_: self.set_playing(self.playing, force=True))

    def _stop(self):
        if self._tick is not None:
            self.remove_tick_callback(self._tick)
            self._tick = None

    def set_playing(self, playing, force=False):
        playing = bool(playing)
        if playing == self.playing and not force:
            return
        self.playing = playing
        if playing and self._tick is None and self.get_mapped():
            self._tick = self.add_tick_callback(lambda *_: (self.queue_draw(), True)[1])
        elif not playing:
            self._stop()
        self.queue_draw()

    def _draw(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        side = max(2, int((w / 2 + self.GAP) // (self.BW + self.GAP)))
        if len(self._shown) != side:
            self._shown = [0.0] * side
        real = self.levels_fn() if (self.playing and self.levels_fn) else None
        t = time.monotonic()
        if real:
            tgt = resample(real, side)
            for j in range(side):    # un poco de vida propia en cada barra para que no se vean en bloques
                tgt[j] *= 0.82 + 0.18 * math.sin(t * (5.0 + j * 0.7) + j * 1.9)
        elif self.playing:
            tgt = [0.25 + 0.2 * math.sin(t * (3 + j * 0.4) + j) for j in range(side)]
        else:
            tgt = [0.0] * side
        for j in range(side):
            k = 0.5 if tgt[j] > self._shown[j] else 0.15
            self._shown[j] += (tgt[j] - self._shown[j]) * k
        r, g, b = self.color
        cx, cy = w / 2, h / 2
        for j, v in enumerate(self._shown):
            hh = 3 + (h - 3) * min(1.0, v)
            a = 1.0 - 0.55 * j / max(1, side - 1)           # se desvanece hacia los lados
            for sgn in (1, -1):
                x = cx + sgn * (self.GAP / 2 + j * (self.BW + self.GAP)) - (0 if sgn > 0 else self.BW)
                if x < 0 or x + self.BW > w:
                    continue
                grad = cairo.LinearGradient(0, cy - hh / 2, 0, cy + hh / 2)
                grad.add_color_stop_rgba(0, min(1, r + 0.25), min(1, g + 0.25), min(1, b + 0.25), a)
                grad.add_color_stop_rgba(0.5, r, g, b, a)
                grad.add_color_stop_rgba(1, r * 0.6, g * 0.6, b * 0.6, a * 0.8)
                cr.set_source(grad)
                rad = self.BW / 2
                y0 = cy - hh / 2
                cr.new_sub_path()
                cr.arc(x + rad, y0 + rad, rad, math.pi, 0)
                cr.arc(x + rad, y0 + hh - rad, rad, 0, math.pi)
                cr.close_path()
                cr.fill()
        return False


class Equalizer(Gtk.DrawingArea):
    """Barras de audio. Con levels_fn (→ lista 0..1 o None) siguen el sonido real;
    sin datos, se mueven solas."""

    def __init__(self, w=22, h=16):
        super().__init__()
        self.w, self.h, self.playing, self._tick = w, h, False, None
        self.levels_fn, self.color, self._shown = None, GREEN, [0.0] * 4
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
        cr.set_source_rgb(*self.color)
        real = self.levels_fn() if (self.playing and self.levels_fn) else None
        if real:
            real = resample(real, n)
        for i in range(n):
            if self.playing and real:
                target = real[i] if i < len(real) else 0.0
                k = 0.55 if target > self._shown[i] else 0.18      # sube rápido, baja suave
                self._shown[i] += (target - self._shown[i]) * k
                hh = 3 + (self.h - 3) * self._shown[i]
            elif self.playing:
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
