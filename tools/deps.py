"""Generador puro de la lista de paquetes que hacen falta según distro, familia y sesión.

`install.sh --deps` muestra el plan y pide confirmación antes de ejecutar la orden; este módulo solo
calcula el plan, para que se pueda probar sin instalar nada.
"""
import re

_BASE = {
    "apt": ["python3-gi", "gir1.2-gtk-3.0", "python3-dbus", "wl-clipboard", "grim", "slurp",
            "wf-recorder", "wireplumber", "pactl"],
    "dnf": ["python3-gobject", "gtk3", "python3-dbus", "wl-clipboard", "grim", "slurp",
            "wf-recorder", "wireplumber"],
    "pacman": ["python-gobject", "gtk3", "wl-clipboard", "grim", "slurp", "wf-recorder", "wireplumber"],
    "zypper": ["python3-gobject-Gdk", "gtk3", "typelib-1_0-GtkLayerShell-0_1", "wl-clipboard", "grim",
               "slurp", "wf-recorder", "wireplumber"],
}
_SESSION = {
    "apt": {"wayland": ["gir1.2-gtklayershell-0.1"], "x11": ["x11-xserver-utils", "xset"]},
    "dnf": {"wayland": ["gtk-layer-shell"], "x11": ["xset"]},
    "pacman": {"wayland": ["gtk-layer-shell"], "x11": ["xset"]},
    "zypper": {"wayland": ["typelib-1_0-GtkLayerShell-0_1"], "x11": ["xset"]},
}
_FAMILY = {
    "apt": {"budgie": ["budgie-control-center"], "gnome": ["gnome-control-center"],
            "kde": ["plasma-workspace-wayland"], "cinnamon": ["cinnamon-control-center"],
            "mate": ["mate-control-center"], "xfce": ["xfce4-settings-manager"],
            "lxde": ["lxappearance"], "lxqt": ["lxqt-config"],
            "sway": ["swayidle", "swaylock", "wlopm"], "hyprland": ["hypridle", "hyprlock", "wlopm"],
            "labwc": ["wlopm"], "wayfire": ["wlopm"], "river": ["wlopm"]},
    "dnf": {"budgie": ["budgie-desktop"], "gnome": ["gnome-control-center"],
            "kde": ["plasma-workspace"], "cinnamon": ["cinnamon-control-center"],
            "mate": ["mate-control-center"], "xfce": ["xfce4-settings-manager"],
            "sway": ["swayidle", "swaylock", "wlopm"], "hyprland": ["hypridle", "hyprlock"]},
    "pacman": {"budgie": ["budgie-desktop"], "gnome": ["gnome-control-center"],
               "kde": ["plasma-workspace"], "cinnamon": ["cinnamon-control-center"],
               "mate": ["mate-control-center"], "xfce": ["xfce4-settings-manager"],
               "sway": ["swayidle", "swaylock", "wlopm"], "hyprland": ["hypridle", "hyprlock"]},
    "zypper": {"gnome": ["gnome-control-center"], "kde": ["plasma-workspace"],
               "xfce": ["xfce4-settings-manager"], "sway": ["swayidle", "swaylock"]},
}
_PREFIXES = {
    "apt": ("debian", "ubuntu", "linuxmint", "pop", "elementary", "raspbian", "zorin"),
    "dnf": ("fedora", "rhel", "centos", "almalinux", "rocky"),
    "pacman": ("arch", "manjaro", "endeavouros"),
    "zypper": ("suse", "opensuse"),
}


def detect_manager(os_release):
    """Gestor de paquetes a partir del contenido de /etc/os-release."""
    ids = []
    for line in (os_release or "").splitlines():
        if line.startswith(("ID=", "ID_LIKE=")):
            ids += re.split(r"[\s]+", line.split("=", 1)[1].strip().strip('"').lower())
    for manager, prefixes in _PREFIXES.items():
        if any(any(i.startswith(p) for p in prefixes) for i in ids):
            return manager
    return "apt"


def packages(manager, family, session):
    """Lista ordenada y sin duplicados de paquetes (accuracy antes que exhaustividad)."""
    out = list(_BASE.get(manager, _BASE["apt"]))
    out += _SESSION.get(manager, {}).get(session, [])
    out += _FAMILY.get(manager, {}).get(family, [])
    return list(dict.fromkeys(out))


def install_command(manager, pkgs):
    """Orden a ejecutar (install.sh pide confirmación antes)."""
    return {
        "apt": ["sudo", "apt", "install", "-y"],
        "dnf": ["sudo", "dnf", "install", "-y"],
        "pacman": ["sudo", "pacman", "-S", "--noconfirm"],
        "zypper": ["sudo", "zypper", "install", "-y"],
    }.get(manager, ["sudo", "apt", "install", "-y"]) + list(pkgs)
