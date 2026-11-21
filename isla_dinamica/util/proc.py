"""Procesos y apps externas: lanzar comandos sin bloquear, abrir URIs y apps, sonidos y depuración."""
import os
import subprocess

from gi.repository import GLib, Gio


# ───────────────────────────── utilidades ─────────────────────────────
def dbg(*a):
    if os.environ.get("ISLA_DEBUG"):
        print(*a, flush=True)


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
