"""Servidores de desarrollo que escuchan en este equipo (Vite, Next, Nest, Django, Spring…)."""
import os
import re
import time

from gi.repository import GLib

from ..util.proc import run

DEV_RUNTIMES = {"node", "bun", "deno", "python", "python3", "java", "php", "ruby", "dotnet", "go", "air",
                "uvicorn", "gunicorn", "puma", "rails", "beam.smp", "npm", "pnpm", "yarn", "esbuild"}
DEV_PORTS = [(3000, 3999), (4000, 4999), (5000, 5999), (8000, 8999), (9000, 9999)]
FRAMEWORKS = (("vite", "Vite"), ("next", "Next.js"), ("nest", "NestJS"), ("react-scripts", "React"),
              ("nodemon", "Nodemon"), ("ts-node", "ts-node"), ("uvicorn", "Uvicorn"), ("gunicorn", "Gunicorn"),
              ("runserver", "Django"), ("flask", "Flask"), ("spring", "Spring"), ("artisan", "Laravel"),
              ("rails", "Rails"), ("express", "Express"), ("http.server", "Servidor estático"))
_USERS = re.compile(r'\("([^"]+)",pid=(\d+)')


def _dev_port(p):
    return any(a <= p <= b for a, b in DEV_PORTS)


def _proc(pid):
    """(carpeta del proyecto, línea de comandos) de un proceso propio."""
    try:
        cwd = os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        cwd = ""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmd = f.read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        cmd = ""
    return cwd, cmd


def _started(pid):
    """Hora (epoch) en que arrancó un proceso, a partir de /proc."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            ticks = int(f.read().rsplit(")", 1)[1].split()[19])
        with open("/proc/stat") as f:
            btime = next(int(ln.split()[1]) for ln in f if ln.startswith("btime"))
        return btime + ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, StopIteration, IndexError):
        return None


def parse_ss(text):
    """Servidores (uno por puerto) a partir de `ss -ltnpH`."""
    found = {}
    for line in text.splitlines():
        cols = line.split()
        if len(cols) < 4:
            continue
        addr = cols[3]
        host, _, port = addr.rpartition(":")
        if not port.isdigit():
            continue
        port = int(port)
        if "%" in host and "lo" not in host.split("%")[1]:
            continue                       # sólo en una interfaz como tailscale0: no es de desarrollo
        m = _USERS.search(line)
        comm, pid = (m.group(1), int(m.group(2))) if m else (None, None)
        if comm and comm not in DEV_RUNTIMES:
            continue                       # Claude, Chrome, opencode…: puertos internos
        if not comm and not _dev_port(port):
            continue                       # de otro usuario (root, Docker) y fuera de los puertos típicos
        if port in found:
            continue
        cwd, cmd = _proc(pid) if pid else ("", "")
        low = cmd.lower()
        fw = next((name for key, name in FRAMEWORKS if key in low), None)
        project = os.path.basename(cwd.rstrip("/")) if cwd and cwd != os.path.expanduser("~") else ""
        found[port] = {"port": port, "pid": pid, "comm": comm or "", "cwd": cwd, "cmd": cmd,
                       "name": project or fw or (comm or "Docker / sistema"),
                       "kind": fw or (comm.capitalize() if comm else "Otro usuario o Docker"),
                       "mine": pid is not None, "url": f"http://localhost:{port}",
                       "started": _started(pid) if pid else None}
    return found


class Servers:
    """Revisa cada 4 s; avisa cuando un servidor arranca o se cae."""

    def __init__(self, on_change, on_event, enabled=lambda: True):
        self.on_change, self.on_event, self.enabled = on_change, on_event, enabled
        self.items, self.since = {}, {}
        self._first = True
        self._stopping = set()             # puertos que detuvimos desde la isla (no es una caída)
        self.refresh()
        GLib.timeout_add_seconds(4, lambda: (self.refresh(), True)[1])

    def refresh(self):
        if not self.enabled():
            if self.items:
                self.items = {}
                self.on_change()
            return
        run(["ss", "-ltnpH"], self._done)

    def _done(self, ok, out, _err):
        if not ok:
            return
        self.apply(parse_ss(out))

    def apply(self, items):
        now = time.time()
        if not self._first:
            for port, s in items.items():
                if port not in self.items:
                    self.on_event("up", s)
            for port, s in self.items.items():
                if port not in items:
                    if port in self._stopping:
                        self._stopping.discard(port)
                        self.on_event("stopped", s)
                    else:
                        self.on_event("down", s)
        self._first = False
        for port in items:
            self.since.setdefault(port, now)
        for port in list(self.since):
            if port not in items:
                del self.since[port]
        if set(items) != set(self.items) or any(items[p]["name"] != self.items[p]["name"] for p in items):
            self.items = items
            self.on_change()
        else:
            self.items = items

    def stop(self, port):
        s = self.items.get(port)
        if s and s["pid"]:
            self._stopping.add(port)
            try:
                os.kill(s["pid"], 15)      # SIGTERM: que cierre ordenadamente
            except OSError:
                self._stopping.discard(port)

    def sorted(self):
        return sorted(self.items.values(), key=lambda s: (not s["mine"], s["port"]))
