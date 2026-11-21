"""Música (MPRIS) y volumen."""
from ..common import *  # noqa: F401,F403


class Media:
    """Reproductores MPRIS por D-Bus."""
    PREFIX, PATH, IFACE = "org.mpris.MediaPlayer2.", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player"

    def __init__(self, bus):
        self.bus = bus
        self.last_active = None

    def _call(self, name, path, iface, method, params, rtype, timeout=300):
        return self.bus.call_sync(name, path, iface, method, params,
                                  GLib.VariantType(rtype) if rtype else None,
                                  Gio.DBusCallFlags.NONE, timeout, None)

    def poll(self):
        try:
            names = self._call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                               "ListNames", None, "(as)").unpack()[0]
        except GLib.Error:
            return None
        found = {}
        for n in names:
            if not n.startswith(self.PREFIX):
                continue
            try:
                props = self._call(n, self.PATH, "org.freedesktop.DBus.Properties", "GetAll",
                                   GLib.Variant("(s)", (self.IFACE,)), "(a{sv})").unpack()[0]
            except GLib.Error:
                continue
            meta = props.get("Metadata") or {}
            title = meta.get("xesam:title") or ""
            status = props.get("PlaybackStatus", "Stopped")
            if not title or status not in ("Playing", "Paused"):
                continue
            artist = meta.get("xesam:artist") or []
            if isinstance(artist, str):
                artist = [artist]
            found[n] = {
                "name": n, "title": title,
                "artist": ", ".join(a for a in artist if a),
                "album": meta.get("xesam:album") or "",
                "art": meta.get("mpris:artUrl") or "",
                "length": (meta.get("mpris:length") or 0) / 1e6,
                "position": (props.get("Position") or 0) / 1e6,
                "playing": status == "Playing",
            }
        if not found:
            self.last_active = None
            return None
        playing = [p for p in found.values() if p["playing"]]
        if playing:
            pick = next((p for p in playing if p["name"] == self.last_active), playing[0])
        else:
            pick = found.get(self.last_active) or next(iter(found.values()))
        self.last_active = pick["name"]
        return pick

    def command(self, name, method):
        self.bus.call(name, self.PATH, self.IFACE, method, None, None,
                      Gio.DBusCallFlags.NONE, 1000, None, None, None)


class Volume:
    def __init__(self, on_change):
        self.on_change = on_change
        self.value, self.muted = self.read()
        self._pending = None
        try:
            launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE)
            launcher.setenv("LC_ALL", "C", True)
            self.proc = launcher.spawnv(tied(["pactl", "subscribe"]))
            self.stream = Gio.DataInputStream.new(self.proc.get_stdout_pipe())
            self.stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line)
        except GLib.Error:
            self.proc = None

    @staticmethod
    def read():
        try:
            out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                                 capture_output=True, text=True, timeout=1).stdout
            m = re.search(r"([\d.]+)", out)
            return (float(m.group(1)) if m else 0.0), ("MUTED" in out)
        except Exception:
            return 0.0, False

    def _on_line(self, stream, res):
        try:
            line, _ = stream.read_line_finish_utf8(res)
        except GLib.Error:
            return
        if line is None:
            return
        if "on sink" in line or "on server" in line:
            if self._pending is None:
                self._pending = GLib.timeout_add(40, self._check)
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line)

    def _check(self):
        self._pending = None
        v, m = self.read()
        if abs(v - self.value) > 0.004 or m != self.muted:
            self.value, self.muted = v, m
            self.on_change(v, m)
        return False

    @staticmethod
    def step(up):
        subprocess.Popen(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%+" if up else "5%-"])

    @staticmethod
    def set(value):
        subprocess.Popen(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", f"{value:.2f}"])

    @staticmethod
    def toggle_mute():
        subprocess.Popen(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
