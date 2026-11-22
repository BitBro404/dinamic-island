"""Apagar y encender la pantalla con el mejor método disponible.

Cada método trae las dos acciones (off, on) como especificaciones: `("cmd", argv)` o
`("dbus", (dest, path, iface, method, valor))`. Así se puede probar el argv sin pantalla ni escritorio.
"""
import os
import subprocess

from gi.repository import GLib

from .chain import Method, Tools, pick
from .desktop import detect
from .shell import BUS as SHELL_BUS, LABEL as SHELL_LABEL, PATH as SHELL_PATH


def _run(argv):
    try:
        subprocess.run(argv, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def _cmd(off, on):
    return ("cmd", off), ("cmd", on)


def _shell(value):
    return ("dbus", (SHELL_BUS, SHELL_PATH, SHELL_BUS, "SetPowerSave", value))


METHODS = [
    Method("wlopm", lambda t, d: t.has("wlopm"),
           _cmd(["wlopm", "--off", "*"], ["wlopm", "--on", "*"]), hint="wlopm"),
    Method("swaymsg", lambda t, d: t.has("swaymsg"),
           _cmd(["swaymsg", "output", "*", "dpms", "off"], ["swaymsg", "output", "*", "dpms", "on"])),
    Method("hyprctl", lambda t, d: t.has("hyprctl"),
           _cmd(["hyprctl", "dispatch", "dpms", "off"], ["hyprctl", "dispatch", "dpms", "on"])),
    Method("kscreen-doctor", lambda t, d: t.has("kscreen-doctor"),
           _cmd(["kscreen-doctor", "output.*.disable"], ["kscreen-doctor", "output.*.enable"]),
           hint="kscreen-doctor"),
    Method(SHELL_LABEL, lambda t, d: t.has_name(SHELL_BUS), (_shell(False), _shell(True))),
    Method("xset", lambda t, d: t.has("xset"),
           _cmd(["xset", "dpms", "force", "off"], ["xset", "dpms", "force", "on"]), hint="x11-xserver-utils"),
]
FEATURE = ("Apagar pantalla", METHODS)


class Screen:
    """Apaga o enciende con el método elegido una sola vez."""

    def __init__(self, bus, tools=None, desktop=None, methods=METHODS, run=None):
        self.bus, self.run = bus, run or _run
        self.method = pick(methods, tools or Tools(), desktop or detect(os.environ))

    @property
    def supported(self):
        return self.method is not None

    def off(self):
        return self._apply(0)

    def on(self):
        return self._apply(1)

    def _apply(self, index):
        if not self.method:
            return False
        kind, payload = self.method.act[index]
        try:
            if kind == "cmd":
                return bool(self.run(payload))
            if kind == "dbus":
                dest, path, iface, method, value = payload
                self.bus.call(dest, path, iface, method, GLib.Variant("(b)", (value,)), None,
                              0, 2000, None, lambda *_: None)
                return True
        except Exception:
            return False
        return False
