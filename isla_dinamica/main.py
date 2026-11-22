"""Punto de entrada: detecta el escritorio, elige cómo colocar la ventana y arranca (o hace el diagnóstico).

  isla-dinamica            arranca la isla
  isla-dinamica --doctor   muestra el escritorio detectado y qué método usa cada función
"""
import os
import sys

from gi.repository import Gdk, Gtk

from .platform import shell
from .platform.desktop import detect
from .platform.placement import choose_backend
from .ui.placement import layer_shell_supported
from .ui.style import CSS


def window_backend(desktop):
    """Elige la colocación; si conviene XWayland, relanza el proceso una sola vez con GDK_BACKEND=x11."""
    Gtk.init_check(sys.argv)
    backend = choose_backend(desktop, os.environ, layer_shell_supported(), shell.present())
    if backend == "relaunch-x11":
        env = dict(os.environ, GDK_BACKEND="x11", ISLA_RELAUNCHED="1")
        os.execve(sys.executable, [sys.executable] + sys.argv, env)
    return backend


def doctor(desktop, backend):
    from .platform.chain import Tools
    from .platform.doctor import all_features, report
    from .ui.placement import BACKENDS
    sys.stdout.write(report(desktop, Tools(), all_features(), BACKENDS[backend].name))


def main():
    desktop = detect(os.environ)
    if "--doctor" in sys.argv:
        Gtk.init_check(sys.argv)
        env = dict(os.environ)
        backend = choose_backend(desktop, env, layer_shell_supported(), shell.present())
        doctor(desktop, "x11" if backend == "relaunch-x11" else backend)
        return
    backend = window_backend(desktop)

    from .core import Core
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
        state["core"] = Core(a, desktop, backend)
    app.connect("activate", activate)
    app.run(None)
