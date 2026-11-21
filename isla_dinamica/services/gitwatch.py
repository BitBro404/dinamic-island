"""Proyectos: estado git de los repos dentro de las carpetas vigiladas."""
import threading

__all__ = ["GitWatch"]

import os
import subprocess
import time

from gi.repository import GLib
from .poller import Poller

SKIP = {"node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", "vendor", "target", ".next",
        ".cache", ".idea", ".vscode", "uploads"}
DEPTH = 4
EVERY = 60            # estado local
FETCH_EVERY = 15 * 60  # git fetch en segundo plano (para saber si estás atrás)
GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="true", LC_ALL="C",
               GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=8")


def expand(p):
    return os.path.abspath(os.path.expanduser(p))


def short(p):
    home = os.path.expanduser("~")
    return "~" + p[len(home):] if p == home or p.startswith(home + os.sep) else p


def find_repos(folder, depth=DEPTH):
    """El propio folder si es repo; si no, los repos que contiene (sin entrar en repos ni en dependencias)."""
    folder = expand(folder)
    if os.path.isdir(os.path.join(folder, ".git")) or os.path.isfile(os.path.join(folder, ".git")):
        return [folder]
    out = []
    if depth <= 0:
        return out
    try:
        entries = sorted(os.scandir(folder), key=lambda e: e.name.lower())
    except OSError:
        return out
    for e in entries:
        if e.is_dir(follow_symlinks=False) and not e.name.startswith(".") and e.name not in SKIP:
            out.extend(find_repos(e.path, depth - 1))
    return out


def _git(repo, *args, timeout=10):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=timeout, env=GIT_ENV)
    return r.stdout if r.returncode == 0 else None


def repo_status(repo):
    """{path, name, branch, upstream, ahead, behind, staged, modified, untracked, conflicts, stash,
        last_ts, last_msg}"""
    s = {"path": repo, "name": os.path.basename(repo), "branch": None, "upstream": None, "ahead": 0,
         "behind": 0, "staged": 0, "modified": 0, "untracked": 0, "conflicts": 0, "stash": 0,
         "last_ts": None, "last_msg": "", "error": None}
    out = _git(repo, "status", "--porcelain=v2", "--branch")
    if out is None:
        s["error"] = "no se pudo leer"
        return s
    for line in out.splitlines():
        if line.startswith("# branch.head "):
            s["branch"] = line[14:]
        elif line.startswith("# branch.upstream "):
            s["upstream"] = line[18:]
        elif line.startswith("# branch.ab "):
            a, b = line[12:].split()
            s["ahead"], s["behind"] = int(a), abs(int(b))
        elif line.startswith(("1 ", "2 ")):
            xy = line[2:4]
            s["staged"] += xy[0] != "."
            s["modified"] += xy[1] != "."
        elif line.startswith("u "):
            s["conflicts"] += 1
        elif line.startswith("? "):
            s["untracked"] += 1
    st = _git(repo, "stash", "list")
    s["stash"] = len(st.splitlines()) if st else 0
    log = _git(repo, "log", "-1", "--format=%ct%x09%s")
    if log and "\t" in log:
        ts, msg = log.strip().split("\t", 1)
        s["last_ts"], s["last_msg"] = int(ts), msg
    return s


def changes(s):
    return s["staged"] + s["modified"] + s["untracked"] + s["conflicts"]


def summary(s):
    """«↑2 ↓1 · 3 cambios · 1 stash» o «al día»."""
    parts = []
    if s["ahead"] or s["behind"]:
        parts.append(" ".join(x for x in (f"↑{s['ahead']}" if s["ahead"] else "",
                                          f"↓{s['behind']}" if s["behind"] else "") if x))
    if s["conflicts"]:
        parts.append(f"{s['conflicts']} en conflicto")
    n = s["staged"] + s["modified"] + s["untracked"]
    if n:
        parts.append(f"{n} cambio{'s' if n != 1 else ''}")
    if s["stash"]:
        parts.append(f"{s['stash']} stash")
    if not s["upstream"] and s["branch"] and s["branch"] != "(detached)":
        parts.append("sin remoto")
    return " · ".join(parts) or "al día"


class GitWatch:
    """Vigila repos git locales: cambios sin confirmar y commits nuevos en el remoto."""
    def __init__(self, config, on_change, on_event, enabled=lambda: True):
        self.config, self.on_change, self.on_event, self.enabled = config, on_change, on_event, enabled
        self.repos = []            # [status] ordenados: con algo pendiente primero
        self.updated = None
        self.fetched = None
        self._busy = False
        self._last_fetch = 0.0
        self._behind = {}
        self.poll = Poller(self._kick).soon(6).every(EVERY)

    @property
    def folders(self):
        return self.config.data["git_folders"]

    def add_folder(self, path):
        p = short(expand(path))
        if not os.path.isdir(expand(p)):
            return "No existe esa carpeta"
        if any(expand(f) == expand(p) for f in self.folders):
            return "Ya la estoy vigilando"
        if not find_repos(p):
            return "No encontré repos git ahí"
        self.folders.append(p)
        self._save()
        return None

    def remove_folder(self, path):
        self.config.data["git_folders"] = [f for f in self.folders if f != path]
        self._save()

    def _save(self):
        try:
            self.config.save()
        except OSError:
            pass
        self.on_change()
        self.refresh()

    def refresh(self, fetch=False):
        if fetch:
            self._last_fetch = 0.0
        self._kick()

    def _kick(self):
        if self.enabled() and not self._busy:
            self._busy = True
            folders = list(self.folders)
            fetch = time.time() - self._last_fetch > FETCH_EVERY
            threading.Thread(target=self._scan, args=(folders, fetch), daemon=True).start()
        return True

    def _scan(self, folders, fetch):
        repos, seen = [], set()
        for f in folders:
            for r in find_repos(f):
                if r not in seen:
                    seen.add(r)
                    repos.append(r)
        if fetch:
            for r in repos:
                try:
                    _git(r, "fetch", "--quiet", "--no-tags", "--prune", timeout=25)
                except subprocess.TimeoutExpired:
                    pass
        out = []
        for r in repos:
            try:
                out.append(repo_status(r))
            except (subprocess.TimeoutExpired, OSError) as e:
                out.append({"path": r, "name": os.path.basename(r), "error": str(e)})
        GLib.idle_add(self._apply, out, fetch)

    def _apply(self, repos, fetched):
        self._busy = False
        if fetched:
            self._last_fetch = self.fetched = time.time()
        for s in repos:
            behind, old = s.get("behind", 0), self._behind.get(s["path"])
            if old is not None and behind > old:
                self.on_event("behind", s)
            self._behind[s["path"]] = behind
        repos.sort(key=lambda s: (s.get("error") is None and not (changes(s) or s["ahead"] or s["behind"]
                                                                   or s["stash"]), s["name"].lower()))
        self.repos = repos
        self.updated = time.time()
        self.on_change()
        return False
