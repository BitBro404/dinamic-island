"""Modos del sistema y medios extraíbles."""
from gi.repository import GLib, Gio

from ..platform.appearance import Appearance
from ..platform.session import Session
from ..util.proc import open_uri


class Modes:
    """Modo oscuro, luz nocturna, ahorro de energía y mantener despierto."""

    def __init__(self, sysbus, bus, on_change, desktop=None, appearance=None, session=None):
        self.on_change, self.sysbus, self.bus = on_change, sysbus, bus
        self.appearance = appearance or Appearance(on_change, desktop=desktop, bus=bus)
        self.session = session
        try:
            self.pp = Gio.DBusProxy.new_sync(sysbus, Gio.DBusProxyFlags.NONE, None, "net.hadess.PowerProfiles",
                                             "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles", None)
            self.pp.connect("g-properties-changed", lambda *_: on_change())
        except GLib.Error:
            self.pp = None

    @property
    def dark(self):
        return self.appearance.dark

    @property
    def dark_available(self):
        return self.appearance.has_dark and not (self.appearance._dark and self.appearance._dark.readonly)

    def toggle_dark(self):
        return self.appearance.toggle_dark()

    @property
    def night(self):
        return self.appearance.night

    @property
    def night_available(self):
        return self.appearance.has_night

    def toggle_night(self):
        return self.appearance.toggle_night()

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
    def awake_available(self):
        return bool(self.session and self.session.supported)

    @property
    def awake(self):
        return bool(self.session and self.session.awake)

    def toggle_awake(self):
        return bool(self.session and self.session.set_awake(not self.awake))


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
