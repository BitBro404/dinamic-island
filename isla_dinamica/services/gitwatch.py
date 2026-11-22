"""Proyectos: estado git de los repos dentro de las carpetas vigiladas."""
import threading

__all__ = ["GitWatch"]

import os
import re
import subprocess
import time
from urllib.parse import quote

from gi.repository import GLib
from .poller import Poller

SKIP = {"node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", "vendor", "target", ".next",
        ".cache", ".idea", ".vscode", "uploads"}
DEPTH = 4
EVERY = 60            # estado local
FETCH_EVERY = 5 * 60   # git fetch en segundo plano (para saber si estás atrás)
AHEAD_GRACE = 15 * 60  # commits locales sin subir durante este tiempo → aviso (una vez)
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


COMMITS_MAX = 15
_SLUG = re.compile(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
# helper de credenciales que entrega el token de la cuenta elegida, leído de una variable de entorno
# (nunca en la línea de comandos); va después de uno vacío para ignorar los demás helpers configurados
_HELPER = '!f() { test "$1" = get || exit 0; echo username=x-access-token; echo "password=$ISLA_GH_TOKEN"; }; f'


def github_slug(url):
    """«owner/repo» de una URL remota de GitHub (https o ssh); None si no es de GitHub."""
    m = _SLUG.search(url or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def auth_env(token):
    """Entorno de git que usa `token` para los remotos https de GitHub."""
    if not token:
        return GIT_ENV
    return dict(GIT_ENV, ISLA_GH_TOKEN=token, GIT_CONFIG_COUNT="2",
                GIT_CONFIG_KEY_0="credential.https://github.com.helper", GIT_CONFIG_VALUE_0="",
                GIT_CONFIG_KEY_1="credential.https://github.com.helper", GIT_CONFIG_VALUE_1=_HELPER)


def _git_run(repo, *args, timeout=10, token=None):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=timeout,
                       env=auth_env(token))
    return r


def _git(repo, *args, timeout=10, token=None):
    r = _git_run(repo, *args, timeout=timeout, token=token)
    return r.stdout if r.returncode == 0 else None


def parse_log(out):
    """Salida de `git log --format=%h%x1f%an%x1f%ct%x1f%s%x1f%b%x1e` → [{sha, author, ts, subject, body}]."""
    commits = []
    for rec in (out or "").split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) < 4 or not parts[0]:
            continue
        body = parts[4].strip() if len(parts) > 4 else ""
        try:
            ts = int(parts[2])
        except ValueError:
            ts = None
        commits.append({"sha": parts[0], "author": parts[1], "ts": ts, "subject": parts[3], "body": body})
    return commits


_STASH_SUBJ = re.compile(r"^(?:WIP on|On) ([^:]+): (.*)$")


def parse_stashes(out):
    """`git stash list --format=%gd␟%H␟%gs␟%ct` → [{ref, sha, branch, msg, ts}], del más nuevo al más viejo."""
    res = []
    for line in (out or "").splitlines():
        parts = line.split("\x1f")
        if len(parts) < 4:
            continue
        m = _STASH_SUBJ.match(parts[2])
        try:
            ts = int(parts[3])
        except ValueError:
            ts = None
        res.append({"ref": parts[0], "sha": parts[1], "branch": m.group(1) if m else None,
                    "msg": m.group(2) if m else parts[2], "ts": ts})
    return res


def commit_list(repo, rng):
    out = _git(repo, "log", f"-n{COMMITS_MAX}", "--format=%h%x1f%an%x1f%ct%x1f%s%x1f%b%x1e", rng)
    return parse_log(out)


def repo_status(repo):
    """{path, name, branch, upstream, ahead, behind, staged, modified, untracked, conflicts, stash,
        last_ts, last_msg}"""
    s = {"path": repo, "name": os.path.basename(repo), "branch": None, "upstream": None, "ahead": 0,
         "behind": 0, "staged": 0, "modified": 0, "untracked": 0, "conflicts": 0, "stash": 0,
         "last_ts": None, "last_msg": "", "error": None, "remote": None, "slug": None,
         "incoming": [], "outgoing": [], "stashes": [], "merging": False, "conflict_files": [], "merge_from": None}
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
    s["merging"] = _git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD") is not None
    if s["merging"]:
        s["merge_from"] = merge_source(repo)
    if s["conflicts"]:
        s["conflict_files"] = conflict_files(repo)
    s["stashes"] = parse_stashes(_git(repo, "stash", "list", "--format=%gd%x1f%H%x1f%gs%x1f%ct"))
    s["stash"] = len(s["stashes"])
    if s["upstream"]:
        remote = _git(repo, "remote", "get-url", s["upstream"].split("/", 1)[0])
        s["remote"] = remote.strip() if remote else None
        s["slug"] = github_slug(s["remote"])
        if s["behind"]:
            s["incoming"] = commit_list(repo, "HEAD..@{u}")
        if s["ahead"]:
            s["outgoing"] = commit_list(repo, "@{u}..HEAD")
    log = _git(repo, "log", "-1", "--format=%ct%x09%s")
    if log and "\t" in log:
        ts, msg = log.strip().split("\t", 1)
        s["last_ts"], s["last_msg"] = int(ts), msg
    return s


def changes(s):
    return s["staged"] + s["modified"] + s["untracked"] + s["conflicts"]


# ── ramas ──
def parse_branches(out, current):
    """`git for-each-ref` (refname␟unix␟asunto) → ramas a las que se puede cambiar: primero las locales y luego
    las de origin sin copia local, cada grupo de la más reciente a la más vieja; sin la actual ni HEAD."""
    local, remote = [], []
    for line in (out or "").splitlines():
        parts = line.split("\x1f")
        if len(parts) < 3:
            continue
        ref, ts, subject = parts[0], parts[1], parts[2]
        try:
            ts = int(ts)
        except ValueError:
            ts = 0
        if ref.startswith("refs/heads/"):
            local.append({"name": ref[11:], "remote": False, "ts": ts, "subject": subject})
        elif ref.startswith("refs/remotes/origin/") and ref != "refs/remotes/origin/HEAD":
            remote.append({"name": ref[20:], "remote": True, "ts": ts, "subject": subject})
    names = {b["name"] for b in local}
    remote = [b for b in remote if b["name"] not in names]
    out = [b for grp in (local, remote) for b in sorted(grp, key=lambda b: -b["ts"]) if b["name"] != current]
    return out


def list_branches(repo):
    out = _git(repo, "for-each-ref", "--format=%(refname)%1f%(committerdate:unix)%1f%(subject)",
               "refs/heads", "refs/remotes/origin")
    head = _git(repo, "branch", "--show-current")
    return parse_branches(out, (head or "").strip())


# ── PR de una rama a otra ──
def compare_url(slug, base, head):
    """Página de GitHub para crear la PR de `head` hacia `base` (se confirma allí)."""
    return f"https://github.com/{slug}/compare/{quote(base, safe='/')}...{quote(head, safe='/')}?expand=1"


def default_branch(repo):
    """Rama por defecto del remoto (origin/HEAD); si no se conoce, main, master o devel si existen."""
    ref = _git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if ref and ref.strip().startswith("origin/"):
        return ref.strip()[7:]
    for name in ("main", "master", "devel", "develop"):
        if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{name}") is not None:
            return name
    return None


def pr_check(repo, base, head):
    """None si se puede abrir la PR de `head` a `base`; si no, el aviso (la rama de origen debe estar subida)."""
    if base == head:
        return "Elige dos ramas distintas"

    def in_remote(name):
        return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{name}") is not None
    if not in_remote(base):
        return f"La rama {base} no está en GitHub"
    if not in_remote(head):
        return f"Sube la rama {head} primero"
    n = _git(repo, "rev-list", "--count", f"refs/remotes/origin/{head}..refs/heads/{head}")
    n = int(n.strip()) if n and n.strip().isdigit() else 0
    if n:
        return f"La rama {head} tiene {n} commit{'s' if n != 1 else ''} sin subir: súbelos primero"
    return None


BLOCK_SWITCH = "Haz commit o descarta los cambios antes de cambiar de rama"
BLOCK_MERGE = "Haz commit o descarta los cambios antes del merge"


_MERGE_MSG = re.compile(r"^Merge (?:remote-tracking )?branch '([^']+)'")


def parse_merge_msg(text):
    """Rama que se está fusionando, según la primera línea de MERGE_MSG."""
    m = _MERGE_MSG.match(text or "")
    return m.group(1) if m else None


def merge_source(repo):
    path = _git(repo, "rev-parse", "--git-path", "MERGE_MSG")
    try:
        with open(os.path.join(repo, path.strip()) if path else "", encoding="utf-8", errors="replace") as f:
            return parse_merge_msg(f.readline())
    except OSError:
        return None


def conflict_files(repo):
    out = _git(repo, "diff", "--name-only", "--diff-filter=U")
    return [ln for ln in (out or "").splitlines() if ln]


def _files_msg(files, suffix=""):
    """«2 archivos en conflicto: a.txt, b.py» (como mucho 4 nombres)."""
    n = len(files)
    names = ", ".join(files[:4]) + ("…" if n > 4 else "")
    return f"{n} archivo{'s' if n != 1 else ''}{suffix}" + (f": {names}" if n else "")


def run_op(repo, kind, token=None, **kw):
    """Operación git sobre un repo (bloqueante: llamarla en un hilo). Devuelve (ok, mensaje)."""
    def git(*args, timeout=90):
        r = _git_run(repo, *args, timeout=timeout, token=token)
        lines = (r.stderr or r.stdout).strip().splitlines()
        return r.returncode == 0, lines[-1] if lines else ""

    try:
        if kind == "pull":
            return git("pull", "--ff-only")
        if kind == "push":
            return git("push")
        if kind == "switch":
            if changes(repo_status(repo)):           # se mira al momento, no con el estado de hace un minuto
                return False, BLOCK_SWITCH
            branch = kw["branch"]
            ok, msg = git("switch", "--track", f"origin/{branch}") if kw.get("remote") else git("switch", branch)
            return ok, f"Ahora estás en {branch}" if ok else msg
        if kind == "create":
            name, base = kw.get("name", "").strip(), kw["base"]
            if not name:
                return False, "Escribe el nombre de la rama nueva"
            if _git(repo, "check-ref-format", "--branch", name) is None:
                return False, f"Nombre de rama no válido: {name}"
            if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}") is not None:
                return False, f"Ya existe la rama {name}"
            ref = f"origin/{base}" if kw.get("base_remote") else base
            if kw.get("switch", True):
                if changes(repo_status(repo)):
                    return False, BLOCK_SWITCH
                ok, msg = git("switch", "--no-track", "-c", name, ref)
                return ok, f"Creada {name} desde {base}; ahora estás en ella" if ok else msg
            ok, msg = git("branch", "--no-track", name, ref)
            return ok, f"Creada {name} desde {base}" if ok else msg
        if kind == "merge":
            if changes(repo_status(repo)):
                return False, BLOCK_MERGE
            branch = kw["branch"]
            cur = (_git(repo, "branch", "--show-current") or "").strip() or "HEAD"
            ok, msg = git("merge", "--no-edit", f"origin/{branch}" if kw.get("remote") else branch)
            if ok:
                return True, f"Fusionada {branch} en {cur}"
            files = conflict_files(repo)
            return False, f"Conflictos en {_files_msg(files)}" if files else msg
        if kind == "merge_abort":
            ok, msg = git("merge", "--abort")
            return ok, "Merge cancelado: todo quedó como antes" if ok else msg
        if kind == "merge_finish":
            files = conflict_files(repo)
            if files:
                return False, f"Aún hay {_files_msg(files, ' en conflicto')}"
            ok, msg = git("commit", "--no-edit", timeout=180)   # puede pedir la contraseña de la llave GPG
            return ok, "Merge terminado" if ok else msg
        if kind in ("stash_pop", "stash_drop"):
            ref = kw["ref"]
            cur = _git(repo, "rev-parse", "--verify", "--quiet", ref)
            if not cur or cur.strip() != kw["sha"]:       # la lista se movió: no tocar otro stash
                return False, "La lista de stash cambió; vuelve a intentarlo"
            ok, msg = git("stash", "pop" if kind == "stash_pop" else "drop", ref)
            if ok:
                msg = "Stash aplicado" if kind == "stash_pop" else "Stash borrado"
            return ok, msg
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)
    return False, f"Operación desconocida: {kind}"


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
    def __init__(self, config, on_change, on_event, enabled=lambda: True, token_for=lambda s: None,
                 account=lambda: None):
        self.config, self.on_change, self.on_event, self.enabled = config, on_change, on_event, enabled
        self.account = account         # () → cuenta de GitHub elegida (sus proyectos también se vigilan)
        self.token_for = token_for     # status → token de la cuenta elegida si el repo es suyo
        self.syncing = {}              # ruta → "push" | "pull" en curso
        self.fetching = False
        self.repos = []            # [status] ordenados: con algo pendiente primero
        self.updated = None
        self.fetched = None
        self._busy = False
        # el primer escaneo lee los repos al momento; el primer fetch (lento, va a la red) llega 30 s después
        self._last_fetch = time.time() - FETCH_EVERY + 30
        self._behind = {}
        self._ahead_since = {}     # repo → desde cuándo tiene commits sin subir
        self._ahead_warned = set()
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

    # ── proyectos de cada cuenta de GitHub ──
    def account_folders(self, login=None):
        login = login or self.account()
        return list(self.config.data.setdefault("account_folders", {}).get(login, [])) if login else []

    def add_account_folder(self, path):
        """Añade un proyecto (repo o carpeta con repos) a la cuenta elegida; None si fue bien, si no el error."""
        login = self.account()
        if not login:
            return "Elige primero una cuenta de GitHub"
        p = short(expand(path))
        if not os.path.isdir(expand(p)):
            return "No existe esa carpeta"
        if any(expand(f) == expand(p) for f in self.account_folders(login)):
            return f"Ya está en los proyectos de @{login}"
        if not find_repos(p):
            return "No encontré repos git ahí"
        self.config.data.setdefault("account_folders", {})[login] = self.account_folders(login) + [p]
        self._save()
        return None

    def remove_account_folder(self, path):
        login = self.account()
        if not login:
            return
        left = [f for f in self.account_folders(login) if f != path]
        folders = self.config.data.setdefault("account_folders", {})
        if left:
            folders[login] = left
        else:
            folders.pop(login, None)
        self._save()

    def scan_folders(self):
        """(carpetas a escanear, proyectos de la cuenta): las globales de «Proyectos» y las de la cuenta."""
        mine = self.account_folders()
        return list(self.folders) + [f for f in mine if f not in self.folders], mine

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
            folders, mine = self.scan_folders()
            fetch = time.time() - self._last_fetch > FETCH_EVERY
            self.fetching = fetch
            if fetch:
                self.on_change()
            tokens = {s["path"]: self.token_for(s) for s in self.repos if not s.get("error")}
            threading.Thread(target=self._scan, args=(folders, fetch, tokens, mine), daemon=True).start()
        return True

    @property
    def next_fetch(self):
        """Segundos hasta el próximo fetch automático."""
        return max(0, int(self._last_fetch + FETCH_EVERY - time.time()))

    def sync(self, s, op, done=lambda ok, msg: None):
        """`op` = "pull" (bajar, solo avance rápido) o "push" (subir), con el token de la cuenta elegida."""
        if op in ("pull", "push"):
            self.op(s, op, done)

    def op(self, s, kind, done=lambda ok, msg: None, **kw):
        """Lanza run_op en un hilo (una operación a la vez por repo) y avisa con done(ok, mensaje)."""
        path = s["path"]
        if path in self.syncing:
            return
        self.syncing[path] = kind
        self.on_change()
        token = self.token_for(s)

        def work():
            ok, msg = run_op(path, kind, token, **kw)
            GLib.idle_add(finish, ok, msg)

        def finish(ok, msg):
            self.syncing.pop(path, None)
            done(ok, msg)
            self.refresh()
            return False

        threading.Thread(target=work, daemon=True).start()

    def branches(self, s, cb):
        """cb(ramas, rama_por_defecto) del repo (en un hilo: no bloquea la isla)."""
        def work():
            try:
                res, default = list_branches(s["path"]), default_branch(s["path"])
            except (subprocess.TimeoutExpired, OSError):
                res, default = [], None
            GLib.idle_add(lambda: cb(res, default) and False)
        threading.Thread(target=work, daemon=True).start()

    def _scan(self, folders, fetch, tokens=None, mine=()):
        repos, seen = [], set()
        for f in folders:
            for r in find_repos(f):
                if r not in seen:
                    seen.add(r)
                    repos.append(r)
        if fetch:
            for r in repos:
                try:
                    _git(r, "fetch", "--quiet", "--no-tags", "--prune", timeout=25, token=(tokens or {}).get(r))
                except subprocess.TimeoutExpired:
                    pass
        roots = [expand(f) for f in mine]
        out = []
        for r in repos:
            try:
                st = repo_status(r)
            except (subprocess.TimeoutExpired, OSError) as e:
                st = {"path": r, "name": os.path.basename(r), "error": str(e)}
            st["mine"] = any(r == m or r.startswith(m + os.sep) for m in roots)   # proyecto de la cuenta
            out.append(st)
        GLib.idle_add(self._apply, out, fetch)

    def _check_ahead(self, s, now=None):
        """Avisa una vez cuando un repo lleva AHEAD_GRACE con commits sin subir; se rearma al sincronizar."""
        path, now = s["path"], time.time() if now is None else now
        if s.get("ahead", 0) > 0 and s.get("upstream"):
            since = self._ahead_since.setdefault(path, now)
            if now - since >= AHEAD_GRACE and path not in self._ahead_warned:
                self._ahead_warned.add(path)
                self.on_event("ahead", s)
        else:
            self._ahead_since.pop(path, None)
            self._ahead_warned.discard(path)

    def _apply(self, repos, fetched):
        self._busy = False
        self.fetching = False
        if fetched:
            self._last_fetch = self.fetched = time.time()
        for s in repos:
            behind, old = s.get("behind", 0), self._behind.get(s["path"])
            if old is not None and behind > old:
                self.on_event("behind", s)
            self._behind[s["path"]] = behind
            self._check_ahead(s)
        repos.sort(key=lambda s: (s.get("error") is None and not (changes(s) or s["ahead"] or s["behind"]
                                                                   or s["stash"]), s["name"].lower()))
        self.repos = repos
        self.updated = time.time()
        self.on_change()
        return False
