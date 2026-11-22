"""Abrir los ajustes del escritorio y el monitor del sistema con la app nativa de cada uno.

Es la única pieza que sabe que GNOME usa `gnome-control-center` y KDE `systemsettings`: el resto del
código pide «abre los ajustes de wifi», no un comando concreto.
"""
import os

from .chain import Tools
from .desktop import detect

# familia → (binario, {panel: argumento}). Sin argumento: se abre el centro completo.
_SETTINGS = {
    "budgie": ("budgie-control-center", {"wifi": "wifi", "bluetooth": "bluetooth", "power": "power",
                                         "display": "display"}),
    "gnome": ("gnome-control-center", {"wifi": "wifi", "bluetooth": "bluetooth", "power": "power",
                                       "display": "display"}),
    "kde": ("systemsettings", {"wifi": "kcm_networkmanagement", "bluetooth": "kcm_bluetooth",
                               "power": "kcm_power", "display": "kcm_screen"}),
    "cinnamon": ("cinnamon-settings", {"wifi": "network", "bluetooth": "bluetooth", "power": "power",
                                       "display": "display"}),
    "mate": ("mate-control-center", {"wifi": "network", "bluetooth": "bluetooth", "power": "power",
                                     "display": "display"}),
    "xfce": ("xfce4-settings-manager", {}),
    "lxqt": ("lxqt-config", {}),
    "lxde": ("lxappearance", {}),
}

_MONITORS = {
    "kde": ("plasma-systemmonitor",),
    "xfce": ("xfce4-taskmanager",),
    "mate": ("mate-system-monitor",),
    "gnome": ("gnome-system-monitor",),
    "budgie": ("gnome-system-monitor",),
    "cinnamon": ("gnome-system-monitor",),
}
_GENERIC_MONITORS = ("gnome-system-monitor", "plasma-systemmonitor", "mate-system-monitor", "xfce4-taskmanager")


def settings_command(panel, tools=None, desktop=None):
    """Argv para abrir un panel de ajustes, o None si este escritorio no ofrece uno."""
    tools, desktop = tools or Tools(), desktop or detect(os.environ)
    binary, args = _SETTINGS.get(desktop.family, (None, {}))
    if binary and tools.has(binary):
        arg = args.get(panel)
        return [binary, arg] if arg else [binary]
    return None


def monitor_command(tools=None, desktop=None):
    """Argv del monitor del sistema: nativo si hay, y `top` en terminal como último recurso."""
    tools, desktop = tools or Tools(), desktop or detect(os.environ)
    for name in _MONITORS.get(desktop.family, ()) + _GENERIC_MONITORS:
        if tools.has(name):
            return [name]
    return ["x-terminal-emulator", "-e", "top"]
