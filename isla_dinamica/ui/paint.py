"""Dibujo de la ventana con Cairo: fondo de la píldora, tarjetas con degradado y sombra, y el brillo al ritmo."""
import math

import cairo

from .widgets.art import vivid_color


class PaintMixin:
    """Pinta la forma de la isla. Lo usa IslandWindow (self.view, self.cur, self.pad, self.bubbles…)."""
    # color de fondo de las tarjetas según la app que avisa
    CARD_COLORS = (("teams", (0.38, 0.39, 0.85)), ("outlook", (0.06, 0.47, 0.85)), ("correo", (0.06, 0.47, 0.85)),
                   ("github", (0.62, 0.66, 0.78)), ("pomodoro", (1.0, 0.27, 0.23)), ("grabación", (1.0, 0.27, 0.23)),
                   ("fallido", (1.0, 0.27, 0.23)), ("recordatorio", (0.04, 0.52, 1.0)),
                   ("descarga", (0.04, 0.52, 1.0)), ("medio", (1.0, 0.62, 0.04)), ("captura", (0.6, 0.62, 0.7)))

    def _draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        a = self.get_allocation()
        pl, pt, pr, pb = self.pad
        w, h = a.width - pl - pr, a.height - pt - pb
        cr.translate(pl, pt)
        if any(self.pad):
            self._draw_card_back(cr, w, h)
            return False
        if self.bubbles and self._bub_ext:
            self._draw_bubbles(cr, w, h)
            if self.vertical:
                h = max(1, h - self._bub_ext)
            else:
                w = max(1, w - self._bub_ext)
        r = min(w / 2, h / 2, 30)
        cr.new_sub_path()
        cr.arc(w - r, r, r, -math.pi / 2, 0)
        cr.arc(w - r, h - r, r, 0, math.pi / 2)
        cr.arc(r, h - r, r, math.pi / 2, math.pi)
        cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgb(0, 0, 0)
        cr.fill_preserve()
        if self._glow > 0.02:
            cr.set_source_rgba(*self.c_eq.color, 0.10 + 0.6 * self._glow)
            cr.set_line_width(1.5)
        else:
            cr.set_source_rgba(1, 1, 1, 0.07)
            cr.set_line_width(1)
        cr.stroke()
        return False

    @staticmethod
    def _rrect(cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def _draw_card_back(self, cr, w, h):
        """Notificación: sombra suave alrededor y un degradado del color de la app sobre el negro."""
        r = min(w / 2, h / 2, 30)
        dx, dy = {"top": (0, 5), "bottom": (0, -5), "left": (5, 0), "right": (-5, 0)}[self.core.dock["edge"]]
        rr, gg, bb = self._card_rgb
        steps = 12
        for i in range(steps, 0, -1):          # sombra: capas cada vez más grandes y más tenues
            self._rrect(cr, dx - i, dy - i, w + 2 * i, h + 2 * i, r + i)
            a = 0.05 * (1 - i / (steps + 1)) ** 1.6
            cr.set_source_rgba(rr * 0.25, gg * 0.25, bb * 0.25, a * 2.2)
            cr.fill()
        self._rrect(cr, 0, 0, w, h, r)
        cr.set_source_rgb(0, 0, 0)
        cr.fill_preserve()
        g = cairo.LinearGradient(0, 0, w, h)
        g.add_color_stop_rgba(0, rr, gg, bb, 0.42)
        g.add_color_stop_rgba(0.45, rr, gg, bb, 0.10)
        g.add_color_stop_rgba(1, rr, gg, bb, 0.0)
        cr.set_source(g)
        cr.fill_preserve()
        top = cairo.LinearGradient(0, 0, 0, h)       # brillo arriba, como un vidrio
        top.add_color_stop_rgba(0, 1, 1, 1, 0.07)
        top.add_color_stop_rgba(0.5, 1, 1, 1, 0.0)
        cr.set_source(top)
        cr.fill_preserve()
        border = cairo.LinearGradient(0, 0, w, 0)
        border.add_color_stop_rgba(0, rr, gg, bb, 0.55)
        border.add_color_stop_rgba(1, 1, 1, 1, 0.06)
        cr.set_source(border)
        cr.set_line_width(1.2)
        cr.stroke()


    def _card_color(self, ev):
        if ev.get("pixbuf") is not None:
            return vivid_color(ev["pixbuf"], (0.35, 0.45, 0.95))
        acc = ev.get("accent")
        if acc in self.RING and acc:
            return self.RING[acc]
        app = (ev.get("app") or "").lower()
        for key, rgb in self.CARD_COLORS:
            if key in app:
                return rgb
        return (0.35, 0.45, 0.95)

    def _set_pad(self, on):
        e = self.core.dock["edge"]
        if not on:
            pad = (0, 0, 0, 0)
        else:   # poca sombra del lado pegado al borde, más del lado contrario (la luz viene del borde)
            pad = {"top": (16, 4, 16, 24), "bottom": (16, 24, 16, 4),
                   "left": (4, 16, 24, 16), "right": (24, 16, 4, 16)}[e]
        if pad == self.pad:
            return
        self.pad = pad
        self.outer.set_margin_start(pad[0])
        self.outer.set_margin_top(pad[1])
        self.outer.set_margin_end(pad[2])
        self.outer.set_margin_bottom(pad[3])
        self._layout = None
        self._kick()

    def _set_glow(self, on):
        """Mientras suena algo, el borde de la píldora brilla al ritmo del volumen."""
        if on and self._glow_tick is None:
            self._glow_tick = self.add_tick_callback(self._glow_step)
        elif not on and self._glow_tick is not None:
            self.remove_tick_callback(self._glow_tick)
            self._glow_tick = None
            self._glow = 0.0
            self.queue_draw()

    def _glow_step(self, *_):
        lv = self.core.audio.level if self.core.audio.levels else 0.0
        self._glow += (lv - self._glow) * (0.5 if lv > self._glow else 0.12)
        if abs(self._glow - self._glow_drawn) > 0.04:     # redibujar solo si se nota
            self._glow_drawn = self._glow
            self.queue_draw()
        return True

