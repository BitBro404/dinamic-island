"""Isla dinámica para escritorio Linux (Budgie / labwc, Wayland + layer-shell, GTK3).

Una "píldora" negra arriba al centro de cada pantalla que cambia de forma:
  reposo ........ hora
  música ........ carátula, título y ecualizador (MPRIS: Spotify, navegador, VLC...)
  avisos ........ notificaciones de apps (Teams, correo...) y del sistema, volumen,
                  batería, USB, Bluetooth, bienvenida al iniciar sesión / al despertar
Al pasar el ratón (o hacer clic) se expande con:
  reproductor, volumen, ajustes rápidos (Wi-Fi, Bluetooth, modo avión, no molestar,
  modo oscuro, luz nocturna, ahorro de energía, mantener despierto) y accesos a
  captura de pantalla, portapapeles, notificaciones, medios extraíbles,
  temporizador y energía (bloquear, cerrar sesión, suspender, reiniciar, apagar).
"""
import calendar
import html
import json
import math
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_foreign("cairo")
import cairo  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, GtkLayerShell, Pango  # noqa: E402

H = 34            # alto de la píldora compacta
W_EXP = 460       # ancho de la isla expandida
W_CARD = 420      # ancho de las tarjetas de aviso
GAP = 6           # separación con el borde de la pantalla
DRAG_MIN = 8      # píxeles que hay que mover el ratón para empezar a arrastrar

CSS = b"""
window { background: transparent; }
* { color: #f5f5f7; font-family: "Inter", "Cantarell", sans-serif; }
.c-text { font-weight: 600; font-size: 13px; }
.dim { color: #8e8e93; font-size: 12px; }
.small { font-size: 11px; }
.title { font-weight: 700; font-size: 15px; }
.subtitle { font-weight: 600; font-size: 13px; }
.artist { color: #a1a1a6; font-size: 13px; }
.bigclock { font-weight: 700; font-size: 30px; }
.huge { font-weight: 700; font-size: 36px; font-feature-settings: "tnum"; }
.time-small { color: #8e8e93; font-size: 11px; }
.orange { color: #ff9f0a; }
.green { color: #30d158; }
.red { color: #ff453a; }
.blue { color: #0a84ff; }

button { background: none; background-image: none; border: none; box-shadow: none;
         text-shadow: none; outline: none; }
button.ctrl { min-width: 36px; min-height: 36px; padding: 0; border-radius: 18px; }
button.ctrl:hover, button.act:hover, button.row:hover, button.link:hover { background: rgba(255,255,255,0.10); }
button.chip { background: rgba(255,255,255,0.10); border-radius: 14px; padding: 3px 12px; min-height: 0; }
button.chip:hover { background: rgba(255,255,255,0.22); }
button.chip label { font-weight: 600; font-size: 12px; }
button.chip.danger label { color: #ff453a; }
button.tile { min-width: 44px; min-height: 44px; padding: 0; border-radius: 22px;
              background: rgba(255,255,255,0.12); }
button.tile:hover { background: rgba(255,255,255,0.22); }
button.tile.on { background: #0a84ff; }
button.tile.on:hover { background: #3d9bff; }
button.link { padding: 1px 6px; border-radius: 8px; min-height: 0; }
button.link label { font-size: 11px; font-weight: 600; }
button.act { min-width: 49px; min-height: 46px; padding: 2px 0; border-radius: 12px;
             background: rgba(255,255,255,0.07); }
button.row { padding: 6px 8px; border-radius: 10px; }
button.big { min-width: 70px; min-height: 64px; border-radius: 16px; background: rgba(255,255,255,0.08); padding: 4px; }
button.big:hover { background: rgba(255,255,255,0.18); }
button.big.confirm { background: #ff453a; }
.badge { background: #ff453a; border-radius: 8px; min-width: 16px; min-height: 16px;
         font-size: 10px; font-weight: 700; padding: 0 3px; }
levelbar trough { min-height: 4px; border: none; border-radius: 2px; background: rgba(255,255,255,0.18); padding: 0; }
levelbar block.filled { border: none; border-radius: 2px; background: #f5f5f7; }
levelbar block.empty { border: none; background: transparent; }
scale trough { min-height: 6px; border-radius: 3px; background: rgba(255,255,255,0.18); border: none; }
scale highlight { background: #f5f5f7; border-radius: 3px; border: none; }
scale slider { min-width: 14px; min-height: 14px; border-radius: 7px; background: #f5f5f7; border: none; box-shadow: none; }
entry { background: rgba(255,255,255,0.10); border: none; border-radius: 10px; padding: 4px 10px; box-shadow: none; }
scrolledwindow, viewport { background: transparent; border: none; }
spinbutton { background: rgba(255,255,255,0.10); border: none; border-radius: 10px; box-shadow: none; min-height: 0; }
spinbutton entry { background: transparent; min-width: 30px; min-height: 0; padding: 2px 6px; }
spinbutton button { border-radius: 10px; min-width: 20px; min-height: 20px; padding: 0 3px; }
spinbutton button:hover { background: rgba(255,255,255,0.15); }
button.wlink { padding: 0 4px; border-radius: 8px; min-height: 0; }
button.wlink:hover { background: rgba(255,255,255,0.10); }
button.close { min-width: 24px; min-height: 24px; padding: 0; border-radius: 12px; background: rgba(255,255,255,0.10); }
button.close:hover { background: rgba(255,255,255,0.25); }
.hour { font-size: 11px; color: #a1a1a6; }
.wtile { background: rgba(255,255,255,0.07); border-radius: 12px; padding: 6px 10px; }
.wtile-v { font-weight: 600; font-size: 13px; }
.pop { color: #64d2ff; font-size: 11px; font-weight: 600; }
.section { color: #8e8e93; font-size: 11px; font-weight: 700; }
button.work { background: rgba(255,255,255,0.07); border-radius: 12px; padding: 5px 10px; min-height: 0; }
button.work:hover { background: rgba(255,255,255,0.16); }
.cmd { font-family: monospace; font-size: 12px; background: rgba(255,255,255,0.08); border-radius: 8px;
       padding: 4px 8px; }
"""

ACCENTS = ("orange", "green", "red", "blue")



# ───────────────────────────── utilidades ─────────────────────────────
def dbg(*a):
    if os.environ.get("ISLA_DEBUG"):
        print(*a, flush=True)


def set_accent(widget, accent=None):
    ctx = widget.get_style_context()
    for a in ACCENTS:
        ctx.remove_class(a)
    if accent:
        ctx.add_class(accent)


def set_class(widget, cls, on):
    ctx = widget.get_style_context()
    (ctx.add_class if on else ctx.remove_class)(cls)


def fmt_secs(s):
    s = max(0, int(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def label(text="", cls=None, xalign=0.0, ellipsize=True, lines=1):
    lb = Gtk.Label(label=text, xalign=xalign)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if lines > 1:
        lb.set_line_wrap(True)
        lb.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lb.set_lines(lines)
    if cls:
        for c in cls.split():
            lb.get_style_context().add_class(c)
    return lb


def icon(name, size=Gtk.IconSize.MENU, px=None):
    img = Gtk.Image.new_from_icon_name(name, size)
    if px:
        img.set_pixel_size(px)
    return img


def button(cls, child=None, cb=None, tooltip=None, text=None):
    b = Gtk.Button(label=text) if text else Gtk.Button()
    for c in cls.split():
        b.get_style_context().add_class(c)
    if child is not None:
        b.add(child)
    if cb:
        b.connect("clicked", lambda *_: cb())
    if tooltip:
        b.set_tooltip_text(tooltip)
    return b


def clear(box):
    for ch in box.get_children():
        box.remove(ch)
        ch.destroy()


def run(argv, cb=None, stdin=None):
    """Lanza un proceso sin bloquear; cb(ok, stdout, stderr)."""
    flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
    if stdin is not None:
        flags |= Gio.SubprocessFlags.STDIN_PIPE
    launcher = Gio.SubprocessLauncher.new(flags)
    launcher.setenv("LC_ALL", "C", True)
    try:
        proc = launcher.spawnv(argv)
    except GLib.Error as e:
        if cb:
            cb(False, "", str(e))
        return

    def done(p, res):
        try:
            _ok, out, err = p.communicate_utf8_finish(res)
        except GLib.Error as e:
            if cb:
                cb(False, "", str(e))
            return
        if cb:
            cb(p.get_exit_status() == 0, out or "", err or "")

    proc.communicate_utf8_async(stdin, None, done)


def tied(argv):
    """Para procesos que viven tanto como la isla (vigilantes): mueren con ella aunque la maten a la
    fuerza. Sin esto quedan huérfanos y se acumulan en cada reinicio."""
    if GLib.find_program_in_path("setpriv"):
        return ["setpriv", "--pdeathsig", "TERM", "--"] + argv
    return argv


def launch_desktop(entry):
    for name in (entry, entry.lower()):
        if not name:
            continue
        try:
            info = Gio.DesktopAppInfo.new(name if name.endswith(".desktop") else name + ".desktop")
        except TypeError:
            info = None
        if info:
            try:
                info.launch([], None)
                return True
            except GLib.Error:
                pass
    return False


def open_uri(uri):
    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
    except GLib.Error:
        subprocess.Popen(["xdg-open", uri])


def strip_markup(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def nm_split(line):
    parts = re.split(r"(?<!\\):", line)
    return [p.replace("\\:", ":").replace("\\\\", "\\") for p in parts]


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha():
    t = time.localtime()
    return f"{DIAS[t.tm_wday].capitalize()} {t.tm_mday} de {MESES[t.tm_mon - 1]}"


def play_sound(*names):
    """Reproduce el primer sonido freedesktop que exista."""
    for n in names:
        snd = os.path.join("/usr/share/sounds/freedesktop/stereo", n)
        if os.path.exists(snd):
            try:
                subprocess.Popen(["pw-play", snd], stderr=subprocess.DEVNULL)
            except OSError:
                pass
            return


def bat_icon(pct, charging):
    lvl = "full" if pct > 85 else "good" if pct > 50 else "low" if pct > 20 else "caution"
    return f"battery-{lvl}{'-charging' if charging else ''}-symbolic"


def ago(ts):
    d = time.time() - ts
    if d < 60:
        return "ahora"
    if d < 3600:
        return f"hace {int(d // 60)} min"
    return time.strftime("%H:%M", time.localtime(ts))


TEAMS_APP = "chrome-ompifgpmddkgmclendfeacglnodjjndh-Default"      # PWA de Teams en Chrome


GITHUB_APP = "chrome-mjoklplbddabcmpepnokjaffbmgbkkgg-Default"     # PWA de GitHub en Chrome


OUTLOOK_URL = "https://outlook.office.com/mail/"


def ago_long(ts):
    """«hace 5 min», «hace 3 h», «ayer», «hace 4 días», «13 nov»."""
    d = time.time() - ts
    if d < 60:
        return "ahora"
    if d < 3600:
        return f"hace {int(d // 60)} min"
    if d < 86400:
        return f"hace {int(d // 3600)} h"
    days = int(d // 86400)
    if days == 1:
        return "ayer"
    if days < 7:
        return f"hace {days} días"
    meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    t = time.localtime(ts)
    return f"{t.tm_mday} {meses[t.tm_mon - 1]}"


def iso_ts(s):
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return time.time()


# ───────────────────────────── configuración, clima y pomodoro ─────────────────────────────
CONFIG_PATH = os.path.join(GLib.get_user_config_dir(), "isla-dinamica", "config.json")


DEFAULTS = {"city": None,
            "dock": {"edge": "top", "pos": 0.5},
            "features": {},       # función → activada (las que no aparecen están activadas)
            "pomodoro": {"work": 25, "short": 5, "long": 15, "every": 4, "auto": True}}


class Config:
    """Preferencias guardadas en ~/.config/isla-dinamica/config.json."""

    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULTS))
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            self.data["city"] = loaded.get("city") or None
            dock = loaded.get("dock") or {}
            if dock.get("edge") in ("top", "bottom", "left", "right"):
                self.data["dock"] = {"edge": dock["edge"],
                                     "pos": min(1.0, max(0.0, float(dock.get("pos", 0.5))))}
            self.data["features"] = {k: v for k, v in (loaded.get("features") or {}).items()
                                     if isinstance(v, bool)}
            self.data["pomodoro"].update({k: v for k, v in (loaded.get("pomodoro") or {}).items()
                                          if k in DEFAULTS["pomodoro"]})
        except (OSError, ValueError, AttributeError):
            pass

    def save(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)


def tz_city():
    try:
        tz = os.path.realpath("/etc/localtime").split("zoneinfo/")[-1]
        return tz.split("/")[-1].replace("_", " ")
    except OSError:
        return "Bogota"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "isla-dinamica/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)
