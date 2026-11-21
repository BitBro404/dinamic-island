"""Modos del sistema y medios extraíbles."""
import os
import re

from gi.repository import GLib, Gio

from ..util.proc import open_uri


class Modes:
    """Modo oscuro, luz nocturna, ahorro de energía y mantener despierto."""

    def __init__(self, sysbus, bus, on_change):
        self.on_change, self.sysbus, self.bus = on_change, sysbus, bus
        src = Gio.SettingsSchemaSource.get_default()
        self.iface = Gio.Settings.new("org.gnome.desktop.interface")
        self.iface.connect("changed::color-scheme", lambda *_: on_change())
        self.color = None
        if src.lookup("org.gnome.settings-daemon.plugins.color", True):
            self.color = Gio.Settings.new("org.gnome.settings-daemon.plugins.color")
            self.color.connect("changed::night-light-enabled", lambda *_: on_change())
        try:
            self.pp = Gio.DBusProxy.new_sync(sysbus, Gio.DBusProxyFlags.NONE, None, "net.hadess.PowerProfiles",
                                             "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles", None)
            self.pp.connect("g-properties-changed", lambda *_: on_change())
        except GLib.Error:
            self.pp = None
        self.inhibit_cookie = None

    @property
    def dark(self):
        return self.iface.get_string("color-scheme") == "prefer-dark"

    def toggle_dark(self):
        dark = not self.dark
        self.iface.set_string("color-scheme", "prefer-dark" if dark else "default")
        theme = self.iface.get_string("gtk-theme")
        base = re.sub(r"-(dark|darkest|light)$", "", theme)
        cand = base + "-dark" if dark else base
        dirs = ["/usr/share/themes", os.path.expanduser("~/.themes"), os.path.expanduser("~/.local/share/themes")]
        if cand != theme and any(os.path.isdir(os.path.join(d, cand)) for d in dirs):
            self.iface.set_string("gtk-theme", cand)

    @property
    def night(self):
        return bool(self.color and self.color.get_boolean("night-light-enabled"))

    def toggle_night(self):
        if self.color:
            self.color.set_boolean("night-light-enabled", not self.night)

    @property
    def profile(self):
        v = self.pp.get_cached_property("ActiveProfile") if self.pp else None
        return v.unpack() if v is not None else None

    def toggle_saver(self):
        if not self.pp:
            return
        new = "balanced" if self.profile == "power-saver" else "power-saver"
        self.sysbus.call("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "org.freedesktop.DBus.Properties",
                         "Set", GLib.Variant("(ssv)", ("net.hadess.PowerProfiles", "ActiveProfile",
                                                       GLib.Variant("s", new))),
                         None, 0, 2000, None, lambda *_: self.on_change())

    @property
    def awake(self):
        return self.inhibit_cookie is not None

    def toggle_awake(self):
        if self.inhibit_cookie is not None:
            try:
                self.bus.call_sync("org.gnome.SessionManager", "/org/gnome/SessionManager",
                                   "org.gnome.SessionManager", "Uninhibit",
                                   GLib.Variant("(u)", (self.inhibit_cookie,)), None, 0, 1000, None)
            except GLib.Error:
                pass
            self.inhibit_cookie = None
        else:
            try:
                self.inhibit_cookie = self.bus.call_sync(
                    "org.gnome.SessionManager", "/org/gnome/SessionManager", "org.gnome.SessionManager", "Inhibit",
                    GLib.Variant("(susu)", ("isla-dinamica", 0, "Mantener despierto", 4 | 8)),
                    GLib.VariantType("(u)"), 0, 1000, None).unpack()[0]
            except GLib.Error:
                self.inhibit_cookie = None
        self.on_change()


class Drives:
    """Medios extraíbles (USB, tarjetas SD, teléfonos)."""

    def __init__(self, on_change, on_event):
        self.on_change, self.on_event = on_change, on_event
        self.vm = Gio.VolumeMonitor.get()
        for sig in ("volume-removed", "mount-added", "mount-removed", "volume-changed"):
            self.vm.connect(sig, lambda *_: self.on_change())
        self.vm.connect("volume-added", self._added)

    @staticmethod
    def _removable(v):
        d = v.get_drive()
        return v.can_eject() or (d is not None and (d.is_removable() or d.can_eject()))

    def items(self):
        return [v for v in self.vm.get_volumes() if self._removable(v)]

    def _added(self, _vm, v):
        self.on_change()
        if self._removable(v):
            self.on_event("usb", v.get_name(), v)

    def open(self, v):
        m = v.get_mount()
        if m:
            open_uri(m.get_root().get_uri())
            return

        def done(vol, res):
            try:
                vol.mount_finish(res)
                open_uri(vol.get_mount().get_root().get_uri())
            except (GLib.Error, AttributeError):
                pass
            self.on_change()
        v.mount(Gio.MountMountFlags.NONE, Gio.MountOperation(), None, done)

    def eject(self, v):
        name = v.get_name()

        def done_eject(obj, res):
            self._finish(obj.eject_with_operation_finish, res, name)

        def done_unmount(obj, res):
            self._finish(obj.unmount_with_operation_finish, res, name)
        if v.can_eject():
            v.eject_with_operation(Gio.MountUnmountFlags.NONE, None, None, done_eject)
        elif v.get_mount():
            v.get_mount().unmount_with_operation(Gio.MountUnmountFlags.NONE, None, None, done_unmount)

    def _finish(self, fn, res, name):
        try:
            fn(res)
            self.on_event("ejected", name, None)
        except GLib.Error as e:
            self.on_event("eject-failed", f"{name}: {e.message}", None)
        self.on_change()
