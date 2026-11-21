"""Red: velocidad de bajada y subida, VPN activa y si hay Internet."""
from collections import deque

import time

from gi.repository import GLib

from ..util.fmt import nm_split
from ..util.proc import run

VPN_TYPES = ("vpn", "wireguard", "tun")


def default_iface():
    try:
        with open("/proc/net/route") as f:
            for ln in f.readlines()[1:]:
                c = ln.split()
                if c[1] == "00000000":
                    return c[0]
    except OSError:
        pass
    return None


def _bytes(iface):
    try:
        with open(f"/sys/class/net/{iface}/statistics/rx_bytes") as a, \
                open(f"/sys/class/net/{iface}/statistics/tx_bytes") as b:
            return int(a.read()), int(b.read())
    except (OSError, ValueError):
        return None


def fmt_rate(bps):
    if bps >= 1024 ** 2:
        return f"{bps / 1024 ** 2:.1f} MB/s"
    if bps >= 1024:
        return f"{bps / 1024:.0f} KB/s"
    return f"{bps:.0f} B/s"


def _pretty_vpn(name):
    low = name.lower()
    if "tailscale" in low:
        return "Tailscale"
    if low.startswith("wg"):
        return f"WireGuard ({name})"
    return name


class NetMon:
    """Velocidad de bajada y subida, VPN activa y si hay Internet (avisa al perderla o recuperarla)."""
    def __init__(self, on_change, on_event, enabled=lambda: True):
        self.on_change, self.on_event, self.enabled = on_change, on_event, enabled
        self.down = deque(maxlen=40)
        self.up = deque(maxlen=40)
        self.iface, self.ip = None, ""
        self.vpns, self.online = [], None
        self._first = True
        self._prev = None
        GLib.timeout_add(2000, self._sample)
        self._status()
        GLib.timeout_add_seconds(10, lambda: (self._status(), True)[1])

    def _sample(self):
        if not self.enabled():
            self._prev = None
            return True
        iface = default_iface()
        now = time.monotonic()
        b = _bytes(iface) if iface else None
        if iface != self.iface:
            self.iface, self._prev = iface, None
            self._read_ip()
        if b and self._prev:
            dt = max(0.1, now - self._prev[0])
            self.down.append(max(0, b[0] - self._prev[1][0]) / dt)
            self.up.append(max(0, b[1] - self._prev[1][1]) / dt)
            self.on_change()
        self._prev = (now, b) if b else None
        return True

    def _read_ip(self):
        if not self.iface:
            self.ip = ""
            return
        run(["ip", "-4", "-o", "addr", "show", "dev", self.iface],
            lambda ok, out, _e: setattr(self, "ip", out.split()[3].split("/")[0] if ok and out.split()[3:] else ""))

    def _status(self):
        if not self.enabled():
            return
        run(["nmcli", "-t", "-f", "TYPE,NAME", "con", "show", "--active"], self._got_vpns)
        run(["nmcli", "networking", "connectivity"], self._got_online)   # estado que NetworkManager ya conoce

    def _got_vpns(self, ok, out, _err):
        if not ok:
            return
        vpns = sorted(_pretty_vpn(nm_split(ln)[1]) for ln in out.splitlines()
                      if ln and nm_split(ln)[0] in VPN_TYPES)
        if vpns != self.vpns:
            if not self._first:
                for v in set(vpns) - set(self.vpns):
                    self.on_event("vpn_on", v)
                for v in set(self.vpns) - set(vpns):
                    self.on_event("vpn_off", v)
            self.vpns = vpns
            self.on_change()
        self._first = False

    def _got_online(self, ok, out, _err):
        if not ok:
            return
        online = out.strip() == "full"
        if self.online is not None and online != self.online:
            self.on_event("online" if online else "offline", "")
        if online != self.online:
            self.online = online
            self._read_ip()
            self.on_change()
