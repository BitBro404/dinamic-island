"""Isla dinámica para escritorio Linux (Budgie / labwc, Wayland + layer-shell, GTK3).

Aquí se fijan las versiones de GObject Introspection una sola vez, antes de que cualquier
módulo haga `from gi.repository import Gtk`.
"""
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_foreign("cairo")
