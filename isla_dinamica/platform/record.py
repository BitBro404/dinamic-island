"""Grabación de pantalla con el método que haya: wf-recorder, ffmpeg x11grab, extensión GNOME o portal.

Igual que `platform/capture.py`, la decisión y el argv de cada método viven aquí; `services/recorder.py`
solo gestiona estado (inicio, duración, fin) y lanza lo que esta cadena elige.
"""
import os

from .chain import Method, Tools, pick
from .desktop import detect
from .shell import BUS as SHELL_BUS, LABEL as SHELL_LABEL, PATH as SHELL_PATH  # noqa: F401 (compatible)
PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"


def geometry(geom):
    """«x,y WxH» → («DISPLAY+x+y», «WxH») para wf-recorder."""
    pos, size = geom.split()
    x, y = pos.split(",")
    return f":0+{x}+{y}", size


def to_ffmpeg(geom, display=":0"):
    """«x,y WxH» → («DISPLAY+x,y», «WxH») para ffmpeg (x11grab)."""
    pos, size = geom.split()
    return f"{display}+{pos}", size


def audio_argv(device):
    """Parámetros de ffmpeg para mezclar audio de PulseAudio (el dispositivo lo resuelve Recorder)."""
    return ["-f", "pulse", "-i", device] if device else []


def wf_argv(geom, path, audio_device=None, display=":0"):
    argv = ["wf-recorder", "-y", "-g", geom, "-f", path, "-c", "libx264",
            "-p", "preset=veryfast", "-p", "crf=23", "-x", "yuv420p"]
    if audio_device:
        argv.append(f"--audio={audio_device}")
    return argv


def ffmpeg_argv(geom, path, audio_device=None, display=":0"):
    """ffmpeg con x11grab: área (`-video_size`/`-i :0+x,y`) o pantalla completa."""
    argv = ["ffmpeg", "-y", "-f", "x11grab"]
    if geom:
        _input, size = to_ffmpeg(geom, display)
        argv += ["-video_size", size, "-framerate", "30", "-i", _input]
    else:
        argv += ["-framerate", "30", "-i", display]
    argv += audio_argv(audio_device)
    argv += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    if audio_device:
        argv += ["-c:a", "aac"]
    return argv + [path]


METHODS = [
    Method("wf-recorder", lambda t, d: t.has("wf-recorder") and (d.wlr or d.xwayland),
           ("cmd", wf_argv, "slurp"), hint="wf-recorder"),
    Method("ffmpeg (X11)", lambda t, d: t.has("ffmpeg") and (d.x11 or d.xwayland),
           ("cmd", ffmpeg_argv, "slurp"), hint="ffmpeg"),
    Method(SHELL_LABEL, lambda t, d: t.has_name(SHELL_BUS), ("dbus", None, "self")),
    Method("portal", lambda t, d: True, ("portal", None, "self"), hint="xdg-desktop-portal"),
]
FEATURE = ("Grabación", METHODS)


def choose(tools=None, desktop=None):
    return pick(METHODS, tools or Tools(), desktop or detect(os.environ))


def build(method, geom, output, audio_device=None, display=":0"):
    """Argv del método «cmd»; None si es D-Bus/portal (Recorder los gestiona aparte)."""
    if not method:
        return None
    kind, builder, _area = method.act
    if kind != "cmd":
        return None
    return builder(geom, output, audio_device, display)
