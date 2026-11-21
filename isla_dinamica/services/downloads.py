"""Descargas en curso (Chrome: *.crdownload, Firefox: *.part) y terminadas en la carpeta Descargas."""
from ..common import *  # noqa: F401,F403

PARTIAL = (".crdownload", ".part")
STALL = 60          # un parcial que no cambia en este tiempo está detenido (o abandonado)


def downloads_dir():
    return GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or os.path.expanduser("~/Downloads")


def fmt_size(b):
    for unit, k in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if b >= k:
            return f"{b / k:.1f} {unit}"
    return f"{b} B"


def _final_name(name):
    for suf in PARTIAL:
        if name.endswith(suf):
            name = name[: -len(suf)]
    # Chrome usa «Sin confirmar 123456.crdownload» hasta saber el nombre: no hay nombre final todavía
    return name


class Downloads:
    """Vigila la carpeta con un FileMonitor; mientras hay descargas, mide tamaño y velocidad cada segundo."""

    def __init__(self, on_change, on_event, enabled=lambda: True):
        self.on_change, self.on_event, self.enabled = on_change, on_event, enabled
        self.dir = downloads_dir()
        self.active = {}           # ruta parcial → {name, size, speed, started}
        self.recent = []           # [{name, path, size, mtime}]
        self.stalled = []          # parciales que ya no avanzan
        self._timer = None
        gf = Gio.File.new_for_path(self.dir)
        try:
            self._mon = gf.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
            self._mon.connect("changed", lambda *_: self._kick())
        except GLib.Error:
            self._mon = None
        self.scan()
        GLib.timeout_add_seconds(30, lambda: (self.scan(), True)[1])   # por si el monitor se pierde algo

    def _kick(self):
        if self._timer is None:
            self._timer = GLib.timeout_add(400, self._tick)

    def _tick(self):
        self._timer = None
        self.scan()
        if self.active:
            self._timer = GLib.timeout_add(1000, self._tick)
        return False

    def scan(self):
        if not self.enabled():
            return True
        now = time.time()
        try:
            entries = list(os.scandir(self.dir))
        except OSError:
            return True
        partial = {}
        stalled = []
        files = []
        for e in entries:
            try:
                if not e.is_file():
                    continue
                st = e.stat()
            except OSError:
                continue
            if e.name.endswith(PARTIAL) and now - st.st_mtime > STALL:
                stalled.append({"name": _final_name(e.name), "path": e.path, "size": st.st_size,
                                "mtime": st.st_mtime})
            elif e.name.endswith(PARTIAL):
                old = self.active.get(e.path)
                speed = 0.0
                if old:
                    dt = max(0.2, now - old["t"])
                    speed = max(0.0, (st.st_size - old["size"]) / dt) * 0.6 + old["speed"] * 0.4
                partial[e.path] = {"name": _final_name(e.name), "size": st.st_size, "speed": speed, "t": now,
                                   "started": old["started"] if old else now}
            elif not e.name.startswith("."):
                files.append({"name": e.name, "path": e.path, "size": st.st_size, "mtime": st.st_mtime})
        files.sort(key=lambda f: -f["mtime"])
        # terminadas: el parcial desapareció y existe un archivo nuevo reciente
        stalled_paths = {s["path"] for s in stalled}
        for path, d in self.active.items():
            if path in stalled_paths:
                continue                   # se detuvo, no terminó
            if path not in partial:
                done = next((f for f in files if now - f["mtime"] < 120 and
                             (f["name"] == d["name"] or d["name"].startswith("Sin confirmar") or
                              d["name"].startswith("Unconfirmed"))), None)
                if done:
                    self.on_event("done", done)
                else:
                    self.on_event("cancelled", d)
        for path, d in partial.items():
            if path not in self.active:
                self.on_event("start", d)
        changed = set(partial) != set(self.active) or [f["path"] for f in files[:8]] != [f["path"] for f in self.recent]
        changed = changed or [s["path"] for s in stalled] != [s["path"] for s in self.stalled]
        self.active, self.recent, self.stalled = partial, files[:8], stalled
        if changed or partial:
            self.on_change()
        return True

    def main(self):
        """La descarga más reciente en curso (para la píldora)."""
        return max(self.active.values(), key=lambda d: d["started"]) if self.active else None
