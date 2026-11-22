"""Elección pura del backend de ventana según escritorio y sesión.

Vive en `platform/` porque es la única pieza que decide en función de la familia de escritorio; `ui/`
solo implementa las cuatro formas de colocar la ventana, sin volver a preguntar por GNOME, KDE, etc.
"""
from . import shell


def choose_backend(desktop, env, layer_shell_ok, gnome_ext=False):
    """Qué colocación usar. `layer_shell_ok`: GtkLayerShell.is_supported() en la pantalla actual."""
    if desktop.x11 or (env.get("GDK_BACKEND") == "x11" and env.get("DISPLAY")):
        return "x11"
    if desktop.wayland and layer_shell_ok:
        return "layer-shell"
    if desktop.wayland and gnome_ext and desktop.family == shell.FAMILY:
        return shell.BACKEND
    if desktop.wayland and env.get("DISPLAY") and not env.get("ISLA_RELAUNCHED"):
        return "relaunch-x11"        # sin layer-shell: mejor XWayland (siempre encima, posición libre)
    return "toplevel"
