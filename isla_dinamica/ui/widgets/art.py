"""Carátulas e imágenes redondeadas, y el color vivo que se saca de una carátula."""
import math

from gi.repository import GLib, Gdk, GdkPixbuf, Gtk


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


GREEN = (0.19, 0.82, 0.35)


def vivid_color(pb, fallback=GREEN):
    """Color llamativo de una carátula (para las barras y el brillo), legible sobre negro."""
    import colorsys
    if pb is None:
        return fallback
    try:
        small = pb.scale_simple(12, 12, GdkPixbuf.InterpType.BILINEAR)
    except (GLib.Error, TypeError):
        return fallback
    px, n, stride = small.get_pixels(), small.get_n_channels(), small.get_rowstride()
    best, score = None, -1.0
    buckets = {}
    for y in range(12):
        for x in range(12):
            i = y * stride + x * n
            r, g, b = px[i] / 255, px[i + 1] / 255, px[i + 2] / 255
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            if v < 0.15:
                continue
            k = int(h * 12)
            acc = buckets.setdefault(k, [0.0, 0.0, 0.0, 0.0])
            w = s * v
            acc[0] += w
            acc[1] += h * w
            acc[2] += s * w
            acc[3] += v * w
    for k, (w, hs, ss, vs) in buckets.items():
        if w > score and w > 0:
            score, best = w, (hs / w, ss / w, vs / w)
    if not best or best[1] < 0.18:
        return fallback
    h, s, v = best
    return colorsys.hsv_to_rgb(h, min(0.85, max(0.5, s)), max(0.88, v))
