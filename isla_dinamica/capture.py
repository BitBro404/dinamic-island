"""Capturas y grabación de pantalla: elegir el área (slurp), capturar (grim), copiar y avisar.

Se separó de Core para que el núcleo solo cree servicios y guarde el estado. Usa del núcleo lo justo:
show_event, set_hidden (ocultar la isla mientras se elige el área), recorder y windows.
"""
import os
import time

from gi.repository import GLib, GdkPixbuf, Gio

from .services.downloads import fmt_size
from .util.fmt import fmt_secs
from .util.proc import open_uri, run


class Capture:
    """Capturas de pantalla y grabación: lanza la herramienta, y muestra el aviso con el archivo al terminar."""
    def __init__(self, core):
        self.core = core

    def record(self, monitor=None):
        """Con monitor: graba esa pantalla. Sin monitor: eliges área con slurp o el propio método."""
        from .platform.chain import Tools
        from .platform.record import choose

        method = choose(Tools(), self.core.desktop)
        area = method.act[2] if method else None

        def go(geom):
            if self.core.recorder.start(geom):
                for w in self.core.windows.values():
                    w.page = "record"
            else:
                self.core.show_event(4.0, kind="pill", icon="dialog-error-symbolic", accent="red",
                                text="No se pudo empezar a grabar")

        def start():
            if monitor is not None:
                g = monitor.get_geometry()
                go(f"{g.x},{g.y} {g.width}x{g.height}")
            elif area == "slurp":
                self.core.set_hidden(True)

                def picked(ok, out, _e):
                    self.core.set_hidden(False)
                    if ok and out.strip():
                        go(out.strip())
                run(["slurp", "-d", "-b", "00000099", "-c", "ff453aff", "-s", "00000000", "-w", "2"], picked)
            else:
                go(None)                    # la extensión o el portal eligen la fuente
            return False
        GLib.timeout_add(250, start)

    def recording_done(self, path, secs):
        for w in self.core.windows.values():
            if w.page == "record" and not w.hover:
                w.page = "home"
        if not path:
            self.core.show_event(6.0, kind="pill", icon="dialog-error-symbolic", accent="red",
                            text=f"La grabación falló · {self.core.recorder.error or ''}".rstrip(" ·"))
            return
        size = os.path.getsize(path)
        self.core.show_event(8.0, kind="card", icon="media-record-symbolic", app="Grabación guardada",
                        title=os.path.basename(path), body=f"{fmt_secs(secs)} · {fmt_size(size)} · clic para abrir",
                        action=lambda: open_uri(Gio.File.new_for_path(path).get_uri()))

    def screenshot(self, monitor=None):
        """Captura con el método del escritorio. Sin monitor se elige área (slurp o la propia herramienta)."""
        from .platform.chain import Tools
        from .platform.capture import SHELL_BUS, SHELL_PATH, build, choose, copy_image

        tools = Tools()
        method = choose(tools, self.core.desktop)
        kind, _builder, area = method.act
        folder = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
                              or os.path.expanduser("~/Imágenes"), "Capturas")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, time.strftime("Captura %Y-%m-%d %H-%M-%S.png"))
        self.core.set_hidden(True)

        def saved(ok, _o, _err):
            self.core.set_hidden(False)
            if not ok:
                self.core.show_event(3, kind="pill", icon="dialog-warning-symbolic", accent="red",
                                     text="No se pudo capturar")
                return
            copy_image(path, tools, self.core.desktop)
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 160, 160)
            except GLib.Error:
                pb = None
            self.core.show_event(7.0, kind="card", pixbuf=pb, icon="camera-photo-symbolic", app="Captura",
                                 title="Guardada y copiada al portapapeles", body=os.path.basename(path),
                                 action=lambda: open_uri(GLib.filename_to_uri(path, None)))

        def grab(geom):
            argv = build(method, geom, path)
            if argv:
                run(argv, saved)
            elif kind == "dbus":
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                bus.call(SHELL_BUS, SHELL_PATH, SHELL_BUS, "Screenshot", GLib.Variant("(s)", (geom or "",)),
                         None, 0, 2000, None, lambda *_: saved(True, "", ""))
            else:                              # portal de escritorio (último recurso)
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                opts = {"interactive": GLib.Variant("b", True)}
                bus.call("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                         "org.freedesktop.portal.Screenshot", "Screenshot", GLib.Variant("(sa{sv})", ("", opts)),
                         GLib.VariantType("(o)"), 0, 5000, None, lambda *_: saved(True, "", ""))

        def start():
            if monitor is not None:
                g = monitor.get_geometry()
                grab(f"{g.x},{g.y} {g.width}x{g.height}")
            elif area == "slurp":
                def picked(ok, out, _e):
                    if ok and out.strip():
                        grab(out.strip())
                    else:
                        self.core.set_hidden(False)
                run(["slurp", "-d", "-b", "00000099", "-c", "ffffffff", "-s", "00000000", "-w", "2",
                     "-B", "ffffff22"], picked)
            else:
                grab(None)                    # la herramienta o el portal eligen el área
            return False
        GLib.timeout_add(250, start)
