"""Colocación de la ventana de la isla: el único sitio que sabe CÓMO se pone una ventana encima de todo.

Todas tienen la misma interfaz (`apply(edge, x, y, w, h, mw, mh)` y `reset()`), así la ventana y el acople no
saben si debajo hay layer-shell, X11 o la extensión de GNOME:
  layer-shell   Wayland con wlr-layer-shell (KDE, sway, Hyprland, labwc, Wayfire, Budgie, LXQt-Wayland…);
  x11           sesiones X11 (Cinnamon, MATE, XFCE, LXDE…) y XWayland (GNOME Wayland sin extensión);
  gnome-shell   GNOME Wayland con la extensión de extras/gnome-shell (ella mueve la ventana);
  toplevel      último recurso: ventana normal sin decoración (el compositor decide dónde va).
"""
from gi.repository import Gdk, Gio, GLib

from ..platform import shell
from ..platform.placement import choose_backend  # noqa: F401  (reexportado por compatibilidad)


def x11_origin(x, y, monitor_origin):
    """En X11 las coordenadas son globales: se suma el origen del monitor."""
    return monitor_origin[0] + x, monitor_origin[1] + y


def layer_shell_supported():
    """GtkLayerShell instalado Y el compositor lo admite (False en GNOME, Cinnamon, X11…)."""
    try:
        from gi.repository import GtkLayerShell
        return bool(GtkLayerShell.is_supported())
    except (ImportError, ValueError, AttributeError):
        return False


class LayerShellPlacement:
    """Capa «overlay» de wlr-layer-shell: anclas y márgenes; crece alejándose de su borde."""
    name = "layer-shell"

    def __init__(self, win, monitor):
        from gi.repository import GtkLayerShell as L
        self.L, self.win, self._layout = L, win, None
        self._edges = {"top": L.Edge.TOP, "bottom": L.Edge.BOTTOM, "left": L.Edge.LEFT, "right": L.Edge.RIGHT}
        L.init_for_window(win)
        L.set_namespace(win, "isla-dinamica")
        L.set_monitor(win, monitor)
        L.set_layer(win, L.Layer.OVERLAY)
        L.set_keyboard_mode(win, L.KeyboardMode.ON_DEMAND)

    def reset(self):
        self._layout = None

    def apply(self, edge, x, y, w, h, mw, mh):
        from .dock import layer_layout
        layout = layer_layout(edge, x, y, w, h, mw, mh)
        if layout == self._layout:
            return
        anchors, margins = layout
        if self._layout is None or anchors != self._layout[0]:
            for name, e in self._edges.items():
                self.L.set_anchor(self.win, e, name in anchors)
        for name, e in self._edges.items():
            self.L.set_margin(self.win, e, int(margins.get(name, 0)))
        self._layout = layout

    def focus(self):
        pass                          # ON_DEMAND: el compositor da el teclado al pulsar


class X11Placement:
    """Ventana X11 sin bordes, siempre encima, en todos los escritorios y fuera de la barra de tareas."""
    name = "X11"

    def __init__(self, win, monitor):
        self.win, self.monitor, self._last = win, monitor, None
        win.set_type_hint(Gdk.WindowTypeHint.DOCK)
        win.set_keep_above(True)
        win.stick()
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_accept_focus(True)
        win.set_resizable(False)

    def reset(self):
        self._last = None

    def apply(self, edge, x, y, w, h, mw, mh):
        g = self.monitor.get_geometry()
        geo = (*x11_origin(x, y, (g.x, g.y)), w, h)
        if geo == self._last:
            return
        self.win.move(geo[0], geo[1])
        self.win.resize(w, h)
        self._last = geo

    def focus(self):
        """Algunos gestores no dan el teclado a una ventana DOCK sin pedirlo (campo de contraseña Wi-Fi)."""
        gw = self.win.get_window()
        if gw:
            gw.focus(Gdk.CURRENT_TIME)


class ShellPlacement(X11Placement):
    """Wayland con la extensión: la ventana es normal y la extensión la mueve y la deja encima.
    PROVISIONAL: no se ha podido probar sin GNOME (ver docs/ESCRITORIOS.md)."""
    name = shell.LABEL
    BUS = shell.BUS
    PATH = shell.PATH

    def __init__(self, win, monitor):
        self.win, self.monitor, self._last = win, monitor, None
        win.set_skip_taskbar_hint(True)
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def apply(self, edge, x, y, w, h, mw, mh):
        g = self.monitor.get_geometry()
        geo = (*x11_origin(x, y, (g.x, g.y)), w, h)
        if geo == self._last:
            return
        self._last = geo
        self.win.resize(w, h)
        self.bus.call(self.BUS, self.PATH, self.BUS, "Place", GLib.Variant("(iiii)", geo), None, 0, 500, None,
                      lambda *_: None)

    def focus(self):
        pass


class ToplevelPlacement(X11Placement):
    """Último recurso (Wayland sin layer-shell ni XWayland): ventana normal; el compositor decide la posición."""
    name = "ventana normal (sin layer-shell)"

    def __init__(self, win, monitor):
        self.win, self.monitor, self._last = win, monitor, None
        win.set_keep_above(True)
        win.set_skip_taskbar_hint(True)

    def apply(self, edge, x, y, w, h, mw, mh):
        if (w, h) != self._last:
            self.win.resize(w, h)
            self._last = (w, h)


BACKENDS = {"layer-shell": LayerShellPlacement, "x11": X11Placement, shell.BACKEND: ShellPlacement,
            "toplevel": ToplevelPlacement}
