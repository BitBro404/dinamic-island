"""Batería, límite de carga y energía."""
from gi.repository import GLib, Gio

from ..platform.lock import Locker
from ..platform.session import Session


class ChargeLimit:
    """Cuidado de batería: UPower limita la carga (normalmente al 80 %) si el portátil lo soporta."""

    def __init__(self, sysbus, on_change):
        self.bus, self.on_change, self.proxy = sysbus, on_change, None
        try:
            paths = sysbus.call_sync("org.freedesktop.UPower", "/org/freedesktop/UPower", "org.freedesktop.UPower",
                                     "EnumerateDevices", None, GLib.VariantType("(ao)"), 0, 2000, None).unpack()[0]
            for path in paths:
                px = Gio.DBusProxy.new_sync(sysbus, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.UPower",
                                            path, "org.freedesktop.UPower.Device", None)
                typ, sup = px.get_cached_property("Type"), px.get_cached_property("ChargeThresholdSupported")
                if typ is not None and typ.unpack() == 2 and sup is not None and sup.unpack():
                    self.proxy = px
                    px.connect("g-properties-changed", lambda *_: on_change())
                    break
        except GLib.Error:
            self.proxy = None

    def _get(self, prop, default):
        v = self.proxy.get_cached_property(prop) if self.proxy else None
        return v.unpack() if v is not None else default

    @property
    def supported(self):
        return self.proxy is not None

    @property
    def enabled(self):
        return bool(self._get("ChargeThresholdEnabled", False))

    @property
    def end(self):
        return int(self._get("ChargeEndThreshold", 80))

    def toggle(self):
        if not self.proxy:
            return
        self.bus.call("org.freedesktop.UPower", self.proxy.get_object_path(), "org.freedesktop.UPower.Device",
                      "EnableChargeThreshold", GLib.Variant("(b)", (not self.enabled,)), None,
                      Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, 30000, None,
                      lambda *_: self.on_change())


class Battery:
    """Batería por UPower: nivel, carga y avisos (llena, baja, cargando)."""
    CHARGING, DISCHARGING, FULL, PENDING = 1, 2, 4, 5
    LOW = 20

    def __init__(self, on_event, target=lambda: 100):
        """target(): porcentaje al que se considera «carga completa» (100 o el tope de cuidado)."""
        self.on_event, self.target = on_event, target
        self.low_warned = False
        try:
            self.proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.UPower",
                "/org/freedesktop/UPower/devices/DisplayDevice", "org.freedesktop.UPower.Device", None)
            self.proxy.connect("g-properties-changed", self._changed)
        except GLib.Error:
            self.proxy = None
        self.state = self._get("State", 0)
        # si al arrancar ya está llena y enchufada, no avisar de nuevo
        self.full_warned = self.state != self.DISCHARGING and self._is_full(self.state, self.percent)

    def _is_full(self, st, pct):
        return st == self.FULL or pct >= self.target() - 1

    def _get(self, prop, default):
        if not self.proxy:
            return default
        v = self.proxy.get_cached_property(prop)
        return v.unpack() if v is not None else default

    @property
    def present(self):
        return bool(self._get("IsPresent", False))

    @property
    def percent(self):
        return float(self._get("Percentage", 0))

    @property
    def charging(self):
        return self.state in (self.CHARGING, self.FULL)

    def _changed(self, *_):
        st, pct = self._get("State", 0), self.percent
        if st != self.state:
            if st == self.CHARGING and self.state not in (self.FULL, self.PENDING):
                self.on_event("charging", pct)
            elif st == self.DISCHARGING and self.state in (self.CHARGING, self.FULL, self.PENDING):
                self.on_event("unplugged", pct)
            self.state = st
        # batería baja: una vez al bajar del 20 %, se rearma al cargar o subir del 22 %
        if st == self.DISCHARGING and pct <= self.LOW and not self.low_warned:
            self.low_warned = True
            self.on_event("low", pct)
        if st != self.DISCHARGING or pct > self.LOW + 2:
            self.low_warned = False
        # carga completa (100 % o el tope): una vez por ciclo, se rearma al desenchufar o bajar del tope
        if st != self.DISCHARGING and self._is_full(st, pct) and not self.full_warned:
            self.full_warned = True
            self.on_event("full", pct)
        if st == self.DISCHARGING or pct < self.target() - 3:
            self.full_warned = False


class Power:
    """Acciones de energía: bloquear, cerrar sesión, suspender, reiniciar y apagar."""
    def __init__(self, sysbus, bus, desktop=None, session=None):
        self.sysbus, self.bus = sysbus, bus
        self.locker = Locker(bus, desktop=desktop)
        self.session = session or Session(bus, lambda: None, desktop=desktop)

    def _login1(self, method):
        self.sysbus.call("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
                         method, GLib.Variant("(b)", (True,)), None, 0, 10000, None, lambda *_: None)

    def lock(self):
        """False si ningún bloqueador aceptó la orden (quien llama decide qué hacer)."""
        return self.locker.lock()

    def logout(self):
        """Cierra sesión con el método del escritorio (GNOME, KDE, XFCE… o loginctl)."""
        return self.session.logout()

    def suspend(self):
        self._login1("Suspend")

    def reboot(self):
        self._login1("Reboot")

    def poweroff(self):
        self._login1("PowerOff")
