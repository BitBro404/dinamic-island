"""Punto de entrada."""
from .common import *  # noqa: F401,F403
from .core import Core


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
