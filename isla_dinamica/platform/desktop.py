"""¿En qué escritorio y en qué tipo de sesión corre la isla? (función pura sobre las variables de entorno).

Es la única pieza que interpreta XDG_CURRENT_DESKTOP y compañía. El resto del código pregunta a `Desktop`
(familia, sesión, si el compositor es de la familia wlroots) y nunca vuelve a mirar el entorno.
"""
from typing import NamedTuple

# token de XDG_CURRENT_DESKTOP / DESKTOP_SESSION → familia. Se recorre en orden: «Budgie:GNOME» es budgie.
_TOKENS = (
    ("budgie", "budgie"), ("cinnamon", "cinnamon"), ("x-cinnamon", "cinnamon"), ("kde", "kde"),
    ("plasma", "kde"), ("mate", "mate"), ("xfce", "xfce"), ("lxqt", "lxqt"), ("lxde", "lxde"),
    ("pantheon", "pantheon"), ("deepin", "deepin"), ("dde", "deepin"), ("unity", "unity"),
    ("cosmic", "cosmic"), ("sway", "sway"), ("hyprland", "hyprland"), ("wayfire", "wayfire"),
    ("river", "river"), ("labwc", "labwc"), ("niri", "niri"), ("gnome", "gnome"),
)
# variables que deja cada compositor (cuando no hay XDG_CURRENT_DESKTOP)
_COMPOSITOR_ENV = (("SWAYSOCK", "sway"), ("HYPRLAND_INSTANCE_SIGNATURE", "hyprland"),
                   ("WAYFIRE_SOCKET", "wayfire"), ("LABWC_PID", "labwc"), ("NIRI_SOCKET", "niri"))
# compositores con los protocolos wlr (data-control, screencopy, output-power, ext-idle-notify)
_WLR = {"sway", "hyprland", "wayfire", "river", "labwc"}

_NAMES = {"budgie": "Budgie", "gnome": "GNOME", "kde": "KDE Plasma", "cinnamon": "Cinnamon", "mate": "MATE",
          "xfce": "XFCE", "lxde": "LXDE", "lxqt": "LXQt", "pantheon": "Pantheon", "deepin": "Deepin",
          "unity": "Unity", "cosmic": "COSMIC", "sway": "sway", "hyprland": "Hyprland", "wayfire": "Wayfire",
          "river": "river", "labwc": "labwc", "niri": "niri", "other": "Otro escritorio"}


class Desktop(NamedTuple):
    family: str          # budgie, gnome, kde, cinnamon, … u «other»
    session: str         # wayland, x11 o unknown
    compositor: str      # compositor wlroots detectado por su variable (labwc, sway…) o ""
    xwayland: bool       # hay DISPLAY dentro de una sesión Wayland

    @property
    def wayland(self):
        return self.session == "wayland"

    @property
    def x11(self):
        return self.session == "x11"

    @property
    def wlr(self):
        """Compositor con protocolos wlr (solo tiene sentido en Wayland)."""
        return self.wayland and (self.family in _WLR or self.compositor in _WLR)

    @property
    def label(self):
        return f"{_NAMES.get(self.family, self.family)} · {'X11' if self.x11 else self.session.capitalize()}"


def _family_from(value):
    tokens = [t.strip().lower() for t in value.replace("/", ":").split(":") if t.strip()]
    for key, fam in _TOKENS:
        if any(key == t or (len(key) > 3 and key in t) for t in tokens):
            return fam
    return None


def detect(env):
    """Desktop a partir de un dict tipo os.environ."""
    session = (env.get("XDG_SESSION_TYPE") or "").lower()
    if session not in ("wayland", "x11"):
        session = "wayland" if env.get("WAYLAND_DISPLAY") else "x11" if env.get("DISPLAY") else "unknown"
    compositor = next((name for var, name in _COMPOSITOR_ENV if env.get(var)), "")
    family = None
    for var in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION", "GDMSESSION"):
        if env.get(var):
            family = _family_from(env[var])
            if family:
                break
    family = family or compositor or "other"
    return Desktop(family, session, compositor, session == "wayland" and bool(env.get("DISPLAY")))
