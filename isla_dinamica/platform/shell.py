"""Puente con la extensión de GNOME Shell: su nombre D-Bus y cuándo se usa.

Toda la isla (cadenas de funciones y colocación de la ventana) pregunta aquí; el JavaScript de
`extras/gnome-shell/` debe mantener los mismos BUS y PATH. Es código provisional: si GNOME cambia su
API, `--doctor` sigue indicando qué método se eligió y la isla cae a gsettings, portal o XWayland.
"""
from .chain import Tools

FAMILY = "gnome"
BUS = "io.github.bitbro404.IslaDinamica.Shell"
PATH = "/io/github/bitbro404/IslaDinamica/Shell"
BACKEND = "gnome-shell"
LABEL = "GNOME Shell (extensión)"


def present(tools=None):
    """True si el nombre D-Bus de la extensión está disponible en la sesión."""
    return (tools or Tools()).has_name(BUS)
