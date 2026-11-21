"""Wi-Fi, Bluetooth y modo avión."""
from gi.repository import GLib, Gio

from ..util.fmt import nm_split
from ..util.proc import run


class Bluetooth:
    """Estado y control de Bluetooth (bluetoothctl)."""
    def __init__(self, sysbus, on_change, on_connect):
        self.bus, self.on_change, self.on_connect = sysbus, on_change, on_connect
        self.adapter, self.powered, self.devices, self.busy = None, False, {}, set()
        sysbus.signal_subscribe("org.bluez", "org.freedesktop.DBus.Properties", "PropertiesChanged", None,
                                None, Gio.DBusSignalFlags.NONE, self._props)
        for sig in ("InterfacesAdded", "InterfacesRemoved"):
            sysbus.signal_subscribe("org.bluez", "org.freedesktop.DBus.ObjectManager", sig, None, None,
                                    Gio.DBusSignalFlags.NONE, lambda *_: self.refresh())
        self.refresh()

    @property
    def available(self):
        return self.adapter is not None

    def refresh(self):
        def done(bus, res):
            try:
                objs = bus.call_finish(res).unpack()[0]
            except GLib.Error:
                self.adapter = None
                return
            self.adapter, devs = None, {}
            for path, ifaces in objs.items():
                if "org.bluez.Adapter1" in ifaces and self.adapter is None:
                    self.adapter = path
                    self.powered = bool(ifaces["org.bluez.Adapter1"].get("Powered"))
                d = ifaces.get("org.bluez.Device1")
                if d and (d.get("Paired") or d.get("Connected")):
                    bat = ifaces.get("org.bluez.Battery1", {}).get("Percentage")
                    devs[path] = {"path": path, "name": d.get("Alias") or d.get("Name") or "Dispositivo",
                                  "connected": bool(d.get("Connected")),
                                  "icon": (d.get("Icon") or "bluetooth-active") + "-symbolic", "battery": bat}
            self.devices = devs
            self.on_change()
        self.bus.call("org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", None,
                      GLib.VariantType("(a{oa{sa{sv}}})"), 0, 2000, None, done)

    def _props(self, _c, _s, path, _i, _sig, params):
        iface, changed, _inv = params.unpack()
        if iface == "org.bluez.Device1" and "Connected" in changed and path in self.devices:
            self.on_connect(self.devices[path]["name"], bool(changed["Connected"]),
                            self.devices[path]["icon"])
        if iface in ("org.bluez.Adapter1", "org.bluez.Device1", "org.bluez.Battery1"):
            self.refresh()

    def set_powered(self, on):
        if not self.adapter:
            return
        self.bus.call("org.bluez", self.adapter, "org.freedesktop.DBus.Properties", "Set",
                      GLib.Variant("(ssv)", ("org.bluez.Adapter1", "Powered", GLib.Variant("b", on))),
                      None, 0, 3000, None, lambda *_: self.refresh())

    def toggle_device(self, path):
        dev = self.devices.get(path)
        if not dev or path in self.busy:
            return
        self.busy.add(path)
        self.on_change()

        def done(bus, res):
            self.busy.discard(path)
            try:
                bus.call_finish(res)
            except GLib.Error:
                pass
            self.refresh()
        self.bus.call("org.bluez", path, "org.bluez.Device1", "Disconnect" if dev["connected"] else "Connect",
                      None, None, 0, 30000, None, done)


def wifi_connect_command(net, password, known):
    """Orden de nmcli para conectarse a `net`: (argv, stdin), o None si hace falta pedir la contraseña.
    La contraseña va por la entrada estándar con `--ask`, nunca en argv: los argumentos de un proceso
    los puede leer cualquier usuario del equipo en /proc/<pid>/cmdline o con `ps`."""
    ssid = net["ssid"]
    if ssid in known and password is None:
        return ["nmcli", "connection", "up", "id", ssid], None
    if net["secure"] and password is None:
        return None
    if password:
        return ["nmcli", "--ask", "device", "wifi", "connect", ssid], password + "\n"
    return ["nmcli", "device", "wifi", "connect", ssid], None


class Wifi:
    """Redes Wi-Fi y conexión con nmcli."""
    def __init__(self, sysbus, on_change):
        self.on_change = on_change
        self.enabled, self.active, self.wired, self.nets, self.known = False, None, False, [], set()
        self.busy, self.error, self.scanning = None, None, False
        try:
            self.nm = Gio.DBusProxy.new_sync(sysbus, Gio.DBusProxyFlags.NONE, None,
                                             "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
                                             "org.freedesktop.NetworkManager", None)
            self.nm.connect("g-properties-changed", lambda *_: self.refresh())
        except GLib.Error:
            self.nm = None
        self.refresh()

    def refresh(self):
        if self.nm:
            v = self.nm.get_cached_property("WirelessEnabled")
            self.enabled = bool(v.unpack()) if v is not None else False

        def active(ok, out, _err):
            self.active, self.wired = None, False
            for line in out.splitlines():
                f = nm_split(line)
                if len(f) >= 2 and f[1] == "802-11-wireless":
                    self.active = f[0]
                elif len(f) >= 2 and f[1] == "802-3-ethernet":
                    self.wired = True
            self.on_change()
        run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"], active)

        def known(ok, out, _err):
            self.known = {f[0] for f in map(nm_split, out.splitlines()) if len(f) > 1 and f[1] == "802-11-wireless"}
        run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], known)

    def scan(self):
        if not self.enabled or self.scanning:
            return
        self.scanning = True
        self.on_change()

        def done(ok, out, _err):
            self.scanning = False
            nets = {}
            for line in out.splitlines():
                f = nm_split(line)
                if len(f) < 4 or not f[1]:
                    continue
                inuse, ssid, sig, sec = f[0] == "*", f[1], int(f[2] or 0), f[3]
                prev = nets.get(ssid)
                if prev is None or sig > prev["signal"] or inuse:
                    nets[ssid] = {"ssid": ssid, "signal": sig, "secure": bool(sec and sec != "--"),
                                  "inuse": inuse or bool(prev and prev["inuse"])}
            self.nets = sorted(nets.values(), key=lambda n: (not n["inuse"], -n["signal"]))[:15]
            self.on_change()
        run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "auto"], done)

    def set_enabled(self, on):
        run(["nmcli", "radio", "wifi", "on" if on else "off"], lambda *_: GLib.timeout_add(800, self._later))

    def _later(self):
        self.refresh()
        GLib.timeout_add(300, lambda: (self.scan(), False)[1])
        return False

    def connect(self, net, password=None, on_need_password=None):
        cmd = wifi_connect_command(net, password, self.known)
        if cmd is None:
            if on_need_password:
                on_need_password(net)
            return
        argv, stdin = cmd
        self.busy, self.error = net["ssid"], None
        self.on_change()

        def done(ok, _out, err):
            self.busy = None
            if not ok:
                low = err.lower()
                self.error = "No se pudo conectar" + (" (¿contraseña?)" if "secret" in low or "password" in low
                                                      else "")
            self.refresh()
            self.scan()
        run(argv, done, stdin=stdin)


class Radios:
    """Modo avión con rfkill."""

    def __init__(self, on_change):
        self.on_change = on_change
        self.airplane = False
        self.refresh()

    def refresh(self):
        def done(ok, out, _err):
            states = [s.strip() for s in out.splitlines() if s.strip()]
            self.airplane = bool(states) and all(s == "blocked" for s in states)
            self.on_change()
        run(["rfkill", "-n", "-o", "SOFT"], done)

    def toggle(self):
        run(["rfkill", "unblock" if self.airplane else "block", "all"], lambda *_: GLib.timeout_add(400, self._r))

    def _r(self):
        self.refresh()
        return False
