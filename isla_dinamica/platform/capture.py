"""Capturas de pantalla: la herramienta disponible decide cómo se toma (área o pant completa).

`Method.act = (kind, builder, area)`: kind «cmd» usa `builder(geom, path)`; «dbus» y «portal» se ejecutan
mediante D-Bus; `area` indica «slurp» (se elige con slurp), «self» (la herramienta selecciona) o «none».
"""
import os
import shlex

from .chain import Method, Tools, pick
from .desktop import detect
from .shell import BUS as SHELL_BUS, LABEL as SHELL_LABEL, PATH as SHELL_PATH  # noqa: F401 (compatible)


def to_maim(geom):
    """«x,y WxH» → «WxH+x+y»."""
    pos, size = geom.split()
    x, y = pos.split(",")
    return f"{size}+{x}+{y}"


def to_scrot(geom):
    """«x,y WxH» → «x,y,W,H»."""
    pos, size = geom.split()
    w, h = size.split("x")
    return f"{pos},{w},{h}"


def grim_argv(geom, path):
    return ["grim", "-g", geom, path]


def spectacle_argv(_geom, path):
    return ["spectacle", "-b", "-f", "-o", path]


def maim_argv(geom, path):
    return ["maim", "-g", to_maim(geom), path] if geom else ["maim", "-s", path]


def scrot_argv(geom, path):
    return ["scrot", "-a", to_scrot(geom), path] if geom else ["scrot", "-s", path]


METHODS = [
    Method("grim + slurp", lambda t, d: t.has("grim", "slurp"), ("cmd", grim_argv, "slurp"),
           hint="grim slurp"),
    Method("spectacle", lambda t, d: t.has("spectacle"), ("cmd", spectacle_argv, "none"), hint="spectacle"),
    Method(SHELL_LABEL, lambda t, d: t.has_name(SHELL_BUS), ("dbus", None, "self")),
    Method("maim", lambda t, d: t.has("maim"), ("cmd", maim_argv, "self"), hint="maim"),
    Method("scrot", lambda t, d: t.has("scrot"), ("cmd", scrot_argv, "self"), hint="scrot"),
    Method("portal", lambda t, d: True, ("portal", None, "none"), hint="xdg-desktop-portal"),
]
FEATURE = ("Captura de pantalla", METHODS)


def choose(tools=None, desktop=None):
    return pick(METHODS, tools or Tools(), desktop or detect(os.environ))


def build(method, geom, path):
    """Argv de un método «cmd», o None si es D-Bus/portal."""
    kind, builder, _area = method.act
    return builder(geom, path) if kind == "cmd" else None


def image_copy_argv(path, tools=None, desktop=None):
    """Cómo copiar el PNG al portapapeles (se usa con redirección de stdin desde `path`)."""
    tools, desktop = tools or Tools(), desktop or detect(os.environ)
    if desktop.wayland and tools.has("wl-copy"):
        return ["wl-copy", "-t", "image/png"]
    if tools.has("xclip"):
        return ["xclip", "-selection", "clipboard", "-t", "image/png"]
    return []


def copy_image(path, tools=None, desktop=None, run=None):
    from ..util.proc import run as _run
    argv = image_copy_argv(path, tools, desktop)
    if argv:
        (run or _run)(["sh", "-c", shlex.join(argv) + ' < "$1"', "sh", path])
