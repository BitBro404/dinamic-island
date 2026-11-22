"""Volver a Wayland si la isla heredó un entorno X11 (sin gi: se usa antes de que GTK abra la pantalla).

PyGObject abre la pantalla en cuanto se importa Gtk, así que esto corre desde `isla_dinamica/__init__.py`,
antes de cualquier `from gi.repository import Gtk`.
"""
import os


def wayland_env(env, runtime_files):
    """Entorno corregido si la isla heredó X11 (GDK_BACKEND=x11, p. ej. al lanzarla desde Plank, que corre en
    XWayland) pero hay una sesión Wayland viva; None si no hay nada que cambiar.

    Sin esto la isla sería una ventana X11 «siempre encima» y las ventanas maximizadas la taparían; en Wayland
    usa la capa overlay de layer-shell. Respeta el relanzamiento deliberado en XWayland (ISLA_RELAUNCHED) y
    ISLA_FORCE_X11=1. `runtime_files`: nombres dentro de XDG_RUNTIME_DIR."""
    if env.get("ISLA_RELAUNCHED") or env.get("ISLA_FORCE_X11") or env.get("WAYLAND_DISPLAY"):
        return None
    if env.get("GDK_BACKEND") != "x11":
        return None
    sockets = sorted((f for f in runtime_files if f.startswith("wayland-") and not f.endswith(".lock")),
                     key=lambda f: (len(f), f))
    if not sockets:
        return None
    fixed = {k: v for k, v in env.items() if k != "GDK_BACKEND"}
    fixed.update(WAYLAND_DISPLAY=sockets[0], XDG_SESSION_TYPE="wayland")
    return fixed


def fix_environ(environ=os.environ):
    """Aplica `wayland_env` al entorno del proceso (sin efecto si no hace falta)."""
    run = environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    try:
        files = [f for f in os.listdir(run) if os.path.exists(os.path.join(run, f))]
    except OSError:
        return False
    fixed = wayland_env(environ, files)
    if not fixed:
        return False
    for k in [k for k in environ if k not in fixed]:
        del environ[k]
    environ.update(fixed)
    return True
