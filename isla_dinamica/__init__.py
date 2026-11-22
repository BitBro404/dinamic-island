"""Isla dinámica para escritorio Linux (cualquier escritorio: Wayland o X11, GTK3).

Aquí se fijan las versiones de GObject Introspection una sola vez, antes de que cualquier
módulo haga `from gi.repository import Gtk`.
"""
from .platform.session_env import fix_environ

fix_environ()     # lanzada desde Plank (XWayland): volver a Wayland antes de que GTK abra la pantalla

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_foreign("cairo")
try:                                   # opcional: sin él (GNOME, X11) la isla usa otra colocación
    gi.require_version("GtkLayerShell", "0.1")
except ValueError:
    pass
