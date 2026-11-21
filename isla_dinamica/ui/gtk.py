"""Fábricas de widgets GTK que usan todas las páginas: etiquetas, iconos, botones y clases CSS."""
from gi.repository import Gtk, Pango

from .style import ACCENTS


def set_accent(widget, accent=None):
    ctx = widget.get_style_context()
    for a in ACCENTS:
        ctx.remove_class(a)
    if accent:
        ctx.add_class(accent)


def set_class(widget, cls, on):
    ctx = widget.get_style_context()
    (ctx.add_class if on else ctx.remove_class)(cls)


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
