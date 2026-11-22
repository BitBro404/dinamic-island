"""Generación de la entrada de autoarranque y pistas para compositores sin panel de ajustes."""
import shlex

_HINTS = {
    "sway": "exec isla-dinamica",
    "hyprland": "exec = isla-dinamica",
    "river": "isla-dinamica &",
    "labwc": "isla-dinamica &",
    "wayfire": "isla-dinamica &",
    "niri": "exec isla-dinamica",
}


def autostart_entry(exec_path):
    """Contenido de ~/.config/autostart/isla-dinamica.desktop (ruta real del usuario)."""
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Isla dinámica\n"
            "Comment=Píldora tipo Dynamic Island arriba al centro\n"
            f"Exec={shlex.quote(exec_path)}\n"
            "Hidden=false\n"
            "NoDisplay=true\n"
            "X-GNOME-Autostart-enabled=true\n"
            "X-GNOME-Autostart-Delay=3\n")


def compositor_hint(family):
    """Línea que el usuario debe añadir a su configuración, o None si hay autoarranque estándar."""
    return _HINTS.get(family)
