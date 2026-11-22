"""Servidores de desarrollo que escuchan en este equipo (Vite, Next, Nest, Django, Spring…): detenerlos,
recordar el comando que los arrancó y relanzarlos."""
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
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

# procesos que lanzan el servidor de verdad: se sube hasta ellos para recordar «npm run dev» y no el node interno
LAUNCHERS = {"npm", "pnpm", "yarn", "npx", "bun", "bunx", "deno", "nodemon", "turbo", "nx", "ng", "mvn",
             "gradle", "gradlew", "cargo", "make", "poetry", "pipenv", "uv", "npm-cli", "yarn.cjs"}
SHELLS = {"sh", "dash", "bash", "zsh"}
RECENT_MAX = 8
LOGS = os.path.join(os.path.expanduser("~"), ".cache", "isla-dinamica", "servers")


def _exe(pid):
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return ""


def runtime(comm, exe):
    """Entorno de un proceso que escucha («node», «python», «uvicorn»…) o None si no es de desarrollo.
    Se mira el nombre de `ss` y el ejecutable real: Node 24 se presenta como «MainThread» y Python como
    «python3.12»; así tampoco se cuela VS Code («code») ni Chrome."""
    for name in (comm or "", os.path.basename(exe or "")):
        name = re.sub(r"^python[\d.]*$", "python", name)
        if name in DEV_RUNTIMES:
            return name
    return None


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


def proc_info(pid):
    """{ppid, cwd, argv, path} de un proceso propio leyendo /proc; None si no se puede."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            ppid = int(f.read().rsplit(")", 1)[1].split()[1])
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
        cwd = os.readlink(f"/proc/{pid}/cwd")
    except (OSError, ValueError, IndexError):
        return None
    path = ""
    try:                                   # solo PATH del entorno: el resto puede llevar secretos
        with open(f"/proc/{pid}/environ", "rb") as f:
            path = next((v[5:].decode(errors="replace") for v in f.read().split(b"\0") if v.startswith(b"PATH=")), "")
    except OSError:
        pass
    return {"ppid": ppid, "cwd": cwd, "argv": argv, "path": path}


def _argv(p):
    """argv real; npm y compañía cambian su título a una sola cadena («npm run dev»)."""
    argv = list(p["argv"])
    if len(argv) == 1 and " " in argv[0]:
        try:
            argv = shlex.split(argv[0])
        except ValueError:
            pass
    return argv


def _is_launcher(argv):
    if not argv:
        return False
    names = [re.sub(r"\.(c|m)?js$", "", os.path.basename(a)) for a in argv[:2]]
    if names[0] in SHELLS:
        return "-c" in argv[1:3]
    return any(n in LAUNCHERS for n in names) or argv[0].endswith("yarn.cjs")


def launch_spec(pid, info=proc_info):
    """Cómo se arrancó el servidor que escucha en `pid`: sube por los padres de la misma carpeta mientras sean
    lanzadores (npm, pnpm, nodemon, `sh -c`…). → {top, pid, argv, cwd, path} o None."""
    p = info(pid)
    if not p:
        return None
    top, cur = pid, p
    for _ in range(8):
        parent = info(cur["ppid"]) if cur["ppid"] > 1 else None
        if not parent or parent["cwd"] != p["cwd"] or not _is_launcher(_argv(parent)):
            break
        top, cur = cur["ppid"], parent
    return {"top": top, "pid": pid, "argv": _argv(cur), "cwd": p["cwd"], "path": cur.get("path") or p.get("path", "")}


def _key(r):
    """Identidad de un recordado: sus contenedores de Docker, o carpeta + comando."""
    if r.get("docker"):
        return ("docker", r.get("name") or r["docker"][0])
    return (r.get("cwd"), tuple(r.get("argv") or ()))


def remember(recent, entry, now=None):
    """Lista de comandos recordados (el más nuevo primero, sin repetir, como mucho RECENT_MAX)."""
    keys = ("name", "port", "kind", "docker") if entry.get("docker") else ("name", "port", "kind", "cwd", "argv", "path")
    item = {k: entry.get(k) for k in keys}
    item["when"] = time.time() if now is None else now
    old = next((r for r in recent if _key(r) == _key(item)), None)
    if old and item.get("docker"):        # mismo proyecto de compose: una entrada con todos sus contenedores
        item["docker"] = sorted(set(old["docker"]) | set(item["docker"]))
        item["port"] = item.get("port") or old.get("port")
    rest = [r for r in recent if _key(r) != _key(item)]
    return ([item] + rest)[:RECENT_MAX]


def stopped(recent, running, docker=None):
    """Los recordados que no están corriendo ahora (mismo comando en la misma carpeta, o sus contenedores)."""
    live = {(s.get("cwd"), tuple(s.get("launch") or ())) for s in running.values()}
    up = {c for g in (docker or {}).values() for c in g["containers"]}
    return [r for r in recent
            if not (r.get("docker") and set(r["docker"]) <= up) and (r.get("docker") or _key(r) not in live)]


def log_path(spec, logs=LOGS):
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", spec.get("name") or "servidor").strip("-") or "servidor"
    return os.path.join(logs, f"{name}-{spec.get('port')}.log")


def launch(spec, logs=LOGS):
    """Arranca el comando en su carpeta, en segundo plano y en su propia sesión (no muere con la isla); la salida
    va a un log. → (ok, mensaje, pid)."""
    cwd, argv = spec.get("cwd") or "", list(spec.get("argv") or [])
    if not os.path.isdir(cwd):
        return False, f"La carpeta ya no existe: {cwd}", None
    if not argv:
        return False, "No hay comando que relanzar", None
    path = spec.get("path") or os.environ.get("PATH", "")
    prog = argv[0]
    found = (os.path.join(cwd, prog) if "/" in prog else shutil.which(prog, path=path))
    if not found or not os.access(found, os.X_OK):
        return False, f"No se encuentra «{prog}»", None
    env = dict(os.environ, PATH=path)
    os.makedirs(logs, exist_ok=True)
    try:
        with open(log_path(spec, logs), "ab") as log:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as e:
        return False, f"No se pudo arrancar: {e.strerror or e}", None
    threading.Thread(target=proc.wait, daemon=True).start()     # recoger al hijo cuando termine (sin zombis)
    return True, f"Relanzado: {shlex.join(argv)}", proc.pid


def terminate(spec):
    """SIGTERM al lanzador y al servidor; si el lanzador encabeza su grupo (un trabajo de terminal o uno que
    relanzó la isla), a todo el grupo, para que no queden hijos sueltos."""
    pids = [p for p in dict.fromkeys((spec.get("top"), spec.get("pid"))) if p]
    for pid in pids:
        try:
            if pid == spec.get("top") and os.getpgid(pid) == pid and pid != os.getpgid(0):
                os.killpg(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


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
        if comm:
            comm = runtime(comm, _exe(pid))
            if not comm:
                continue                   # Claude, Chrome, VS Code…: puertos internos
        if not comm and not _dev_port(port):
            continue                       # de otro usuario (root, Docker) y fuera de los puertos típicos
        if port in found:
            continue
        cwd, cmd = _proc(pid) if pid else ("", "")
        low = cmd.lower()
        fw = next((name for key, name in FRAMEWORKS if key in low), None)
        project = os.path.basename(cwd.rstrip("/")) if cwd and cwd != os.path.expanduser("~") else ""
        spec = launch_spec(pid) if pid else None
        found[port] = {"port": port, "pid": pid, "comm": comm or "", "cwd": cwd, "cmd": cmd,
                       "spec": spec, "launch": spec["argv"] if spec else None,
                       "name": project or fw or (comm or "Docker / sistema"),
                       "kind": fw or (comm.capitalize() if comm else "Otro usuario o Docker"),
                       "mine": pid is not None, "url": f"http://localhost:{port}",
                       "started": _started(pid) if pid else None}
    return found


# ── Docker: contenedores en marcha agrupados por proyecto de compose (o uno solo si no es de compose) ──
DOCKER_PS = ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.State}}\t{{.Ports}}\t"
             '{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.service"}}\t{{.Image}}']
_HOST_PORT = re.compile(r":(\d+)(?:-(\d+))?->")


def host_ports(text):
    """Puertos del equipo publicados por un contenedor («0.0.0.0:8080->80/tcp, [::]:8080->80/tcp» → [8080])."""
    ports = set()
    for m in _HOST_PORT.finditer(text or ""):
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        ports.update(range(a, min(b, a + 50) + 1))
    return sorted(ports)


def parse_docker_ps(text):
    out = []
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 7:
            continue
        cid, name, state, ports, project, service, image = cols[:7]
        out.append({"id": cid, "name": name, "state": state, "ports": host_ports(ports), "project": project,
                    "service": service, "image": image})
    return out


def docker_groups(containers):
    """{clave: grupo} de los contenedores en marcha: uno por proyecto de compose o por contenedor suelto."""
    groups = {}
    for c in containers:
        if c["state"] != "running":
            continue
        name = c["project"] or c["name"]
        g = groups.setdefault("docker:" + name, {
            "key": "docker:" + name, "name": name, "kind": "Docker Compose" if c["project"] else "Docker",
            "containers": [], "services": [], "ports": [], "images": [], "docker": True, "mine": True,
            "pid": None, "started": None})
        g["containers"].append(c["name"])
        g["services"].append(c["service"] or c["name"])
        g["ports"] = sorted(set(g["ports"]) | set(c["ports"]))
        g["images"].append(c["image"])
    for g in groups.values():
        order = sorted(range(len(g["containers"])), key=lambda i: g["containers"][i])
        for k in ("containers", "services", "images"):
            g[k] = [g[k][i] for i in order]
        g["port"] = g["ports"][0] if g["ports"] else None
        g["url"] = f"http://localhost:{g['port']}" if g["port"] else None
    return groups


def without_docker(items, groups):
    """Quita de los puertos de `ss` los que publica Docker (ya salen como su proyecto)."""
    taken = {p for g in groups.values() for p in g["ports"]}
    return {p: s for p, s in items.items() if p not in taken or s["mine"]}


class Servers:
    """Revisa cada 4 s; avisa cuando un servidor arranca o se cae."""

    def __init__(self, on_change, on_event, enabled=lambda: True, recent=lambda: [], save_recent=lambda _l: None,
                 logs=LOGS):
        self.on_change, self.on_event, self.enabled = on_change, on_event, enabled
        self._recent, self._save_recent, self.logs = recent, save_recent, logs
        self.items, self.since = {}, {}
        self._first = True
        self._stopping = set()             # puertos que detuvimos desde la isla (no es una caída)
        self._restart = {}                 # puerto → comando a relanzar cuando se libere
        self.docker = {}                   # clave → proyecto/contenedor de Docker en marcha
        self._docker_busy = set()          # claves con un docker stop/restart en curso (no es una caída)
        self._has_docker = bool(shutil.which("docker"))
        self._waiters = []                 # quienes esperan el resultado de un escaneo a mano
        self.refresh()
        GLib.timeout_add_seconds(4, lambda: (self.refresh(), True)[1])

    def refresh(self):
        if not self.enabled():
            if self.items:
                self.items = {}
                self.on_change()
            return
        run(["ss", "-ltnpH"], self._done)

    def scan(self, cb):
        """Escaneo a mano (botón de la página): `cb(cuántos hay)` al terminar, o `cb(None)` si `ss` falló."""
        self._waiters.append(cb)
        run(["ss", "-ltnpH"], self._done)

    def _answer(self, found):
        waiters, self._waiters = self._waiters, []
        for cb in waiters:
            cb(found)

    def _done(self, ok, out, _err):
        if not ok:
            self._answer(None)
            return
        items = parse_ss(out)
        if not self._has_docker:
            self.apply(items, {})
            self._answer(len(self.items) + len(self.docker))
            return

        def docker_done(dok, dout, _e):
            # si el demonio no responde, se deja Docker como estaba (no es que se hayan caído todos)
            self.apply(items, docker_groups(parse_docker_ps(dout)) if dok else None)
            self._answer(len(self.items) + len(self.docker))
        run(DOCKER_PS, docker_done)

    def apply(self, items, docker=None):
        now = time.time()
        if docker is not None:
            for key in self._docker_busy:
                if key in self.docker and key not in docker:
                    docker[key] = self.docker[key]          # se está reiniciando o deteniendo
            items = without_docker(items, docker)
            self._apply_docker(docker)
        if not self._first:
            for port, s in items.items():
                if port not in self.items:
                    self.on_event("up", s)
            for port, s in self.items.items():
                if port not in items:
                    if port in self._restart:
                        self._stopping.discard(port)
                        ok, msg, _pid = launch(self._restart.pop(port), self.logs)
                        self.on_event("restarting" if ok else "failed", dict(s, msg=msg))
                    elif port in self._stopping:
                        self._stopping.discard(port)
                        self.on_event("stopped", s)
                    else:
                        self._remember(s)
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

    def _apply_docker(self, docker):
        if not self._first:
            for key, g in docker.items():
                if key not in self.docker:
                    self.on_event("up", g)
            for key, g in self.docker.items():
                if key not in docker:
                    if key in self._stopping:
                        self._stopping.discard(key)
                        self.on_event("stopped", g)
                    else:
                        self._remember_docker(g)
                        self.on_event("down", g)
        changed = set(docker) != set(self.docker) or any(
            docker[k]["ports"] != self.docker[k]["ports"] for k in docker)
        self.docker = docker
        if changed:                       # también en la primera pasada: si no, la página no se entera
            self.on_change()

    def _remember_docker(self, g):
        entry = {"name": g["name"], "port": g["port"], "kind": g["kind"], "docker": list(g["containers"])}
        self._save_recent(remember(self.recent, entry))
        return entry

    def _docker(self, verb, key, after=None):
        g = self.docker.get(key)
        if not g:
            return False
        self._docker_busy.add(key)

        def done(ok, _out, err):
            self._docker_busy.discard(key)
            if not ok:
                self._stopping.discard(key)
                self.on_event("failed", dict(g, msg=(err or "").strip()))
            self._refresh_soon()
        run(["docker", verb, *g["containers"]], done)
        return True

    def _refresh_soon(self):
        GLib.timeout_add(400, lambda: (self.refresh(), False)[1])

    def docker_stop(self, key):
        g = self.docker.get(key)
        if not g:
            return False
        self._remember_docker(g)
        self._stopping.add(key)
        return self._docker("stop", key)

    def docker_restart(self, key):
        g = self.docker.get(key)
        if not g:
            return False
        self.on_event("restarting", g)
        return self._docker("restart", key)

    def all(self):
        """Lo que corre: servidores sueltos y proyectos de Docker, los propios primero."""
        rows = list(self.items.values()) + list(self.docker.values())
        return sorted(rows, key=lambda s: (not s["mine"], s.get("docker", False), s.get("port") or 0))

    @property
    def recent(self):
        return list(self._recent() or [])

    def stopped(self):
        """Comandos recordados que no están corriendo, con su índice en `recent` (para relanzar u olvidar)."""
        rec = self.recent
        keep = stopped(rec, self.items, self.docker)
        return [(rec.index(r), r) for r in keep]

    def _remember(self, s):
        spec = s.get("spec")
        if not spec or not spec.get("argv"):
            return None
        entry = dict(spec, name=s.get("name"), port=s.get("port"), kind=s.get("kind"))
        self._save_recent(remember(self.recent, entry))
        return entry

    def stop(self, port):
        """Detiene el servidor (SIGTERM, que cierre ordenadamente) y recuerda cómo se arrancó."""
        s = self.items.get(port)
        if s and s["pid"]:
            self._remember(s)
            self._stopping.add(port)
            terminate(s.get("spec") or {"top": s["pid"], "pid": s["pid"]})

    def restart(self, port):
        """Detiene y, en cuanto el puerto queda libre, vuelve a lanzar el mismo comando en la misma carpeta."""
        s = self.items.get(port)
        if not (s and s["pid"]):
            return False
        entry = self._remember(s)
        if not entry:
            return False
        self._restart[port] = entry
        self._stopping.add(port)
        terminate(s["spec"])
        return True

    def relaunch(self, index):
        """Vuelve a lanzar un comando recordado (índice en `recent`). → (ok, mensaje)."""
        rec = self.recent
        if not 0 <= index < len(rec):
            return False, "Ya no está en la lista"
        if rec[index].get("docker"):
            entry = rec[index]

            def done(ok, _out, err):
                if not ok:
                    self.on_event("failed", dict(entry, msg=(err or "").strip()))
                self._refresh_soon()
            run(["docker", "start", *entry["docker"]], done)
            self._save_recent(remember(rec, entry))
            return True, f"Arrancando {entry['name']} (docker start)"
        ok, msg, _pid = launch(rec[index], self.logs)
        if ok:
            self._save_recent(remember(rec, rec[index]))      # sube al principio de la lista
            GLib.timeout_add(1500, lambda: (self.refresh(), False)[1])     # que aparezca al arrancar
        return ok, msg

    def forget(self, index):
        rec = self.recent
        if 0 <= index < len(rec):
            del rec[index]
            self._save_recent(rec)

    def sorted(self):
        return sorted(self.items.values(), key=lambda s: (not s["mine"], s["port"]))
