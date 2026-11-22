"""Pull requests de GitHub con la herramienta gh."""
import json
import re
import time

from gi.repository import GLib

from ..util.fmt import ago_long, iso_ts
from ..util.proc import dbg, run
from .poller import Poller

_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")      # usuario de GitHub

KINDS = {"PullRequest": "PR", "Issue": "Issue", "Commit": "Commit", "Release": "Release",
         "Discussion": "Discusión", "CheckSuite": "CI", "WorkflowRun": "CI"}
REASONS = {"review_requested": "te piden revisión", "mention": "te mencionaron", "team_mention": "mencionan a tu equipo",
           "assign": "te asignaron", "author": "novedad en lo tuyo", "comment": "nuevo comentario",
           "state_change": "cambió de estado", "ci_activity": "actividad de CI", "subscribed": "repo que sigues",
           "manual": "hilo que sigues", "security_alert": "alerta de seguridad", "invitation": "invitación"}


def html_url(api_url, repo):
    """URL de la web a partir de la URL de la API de una notificación (las PR usan /pull/, no /pulls/)."""
    prefix = "https://api.github.com/repos/"
    if not api_url or not api_url.startswith(prefix):
        return f"https://github.com/{repo}" if repo else "https://github.com/notifications"
    path = api_url[len(prefix):]
    parts = path.split("/")
    if len(parts) >= 4 and parts[2] == "pulls":
        parts[2] = "pull"
    elif len(parts) >= 4 and parts[2] == "commits":
        parts[2] = "commit"
    elif len(parts) >= 4 and parts[2] == "releases":
        return f"https://github.com/{parts[0]}/{parts[1]}/releases"
    return "https://github.com/" + "/".join(parts)


def inbox_item(raw):
    """Una notificación de la API de GitHub → {key, title, repo, kind, reason, url, updated}."""
    subj = raw.get("subject") or {}
    repo = (raw.get("repository") or {}).get("full_name", "")
    return {"key": f"{raw.get('id')}@{raw.get('updated_at')}", "title": subj.get("title") or "(sin título)",
            "repo": repo, "kind": KINDS.get(subj.get("type"), subj.get("type") or ""),
            "reason": REASONS.get(raw.get("reason"), raw.get("reason") or ""),
            "url": html_url(subj.get("url"), repo), "updated": iso_ts(raw.get("updated_at"))}


EVERY = 5 * 60
PR_VIEW = ("number,title,body,author,url,state,isDraft,additions,deletions,changedFiles,baseRefName,"
           "headRefName,mergeable,reviewDecision,statusCheckRollup,commits,createdAt")


def merge_flag(repo_info):
    """Método de fusión permitido por el repo: merge, si no squash, si no rebase."""
    for key, flag in (("mergeCommitAllowed", "--merge"), ("squashMergeAllowed", "--squash"),
                      ("rebaseMergeAllowed", "--rebase")):
        if (repo_info or {}).get(key, key == "mergeCommitAllowed"):
            return flag
    return "--merge"


def ci_state(rollup):
    """statusCheckRollup de `gh pr view` → SUCCESS / FAILURE / PENDING / None."""
    states = set()
    for c in rollup or []:
        st = (c.get("conclusion") or c.get("state") or c.get("status") or "").upper()
        states.add(st)
    if not states:
        return None
    if states & {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "FAILURE"
    if states & {"PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "WAITING", ""}:
        return "PENDING"
    return "SUCCESS"


class GitHub:
    """PR de GitHub de UNA cuenta de `gh` (su token va en GH_TOKEN). Se actualiza cada 5 minutos."""
    FIELDS = """... on PullRequest { id number title url isDraft updatedAt mergedAt reviewDecision
        repository { nameWithOwner } author { login }
        commits(last: 1) { nodes { commit { statusCheckRollup { state } } } } }"""

    def __init__(self, on_change, on_event, enabled=lambda: True, login=None, env=dict, repos=list, start=True):
        self.on_change, self.on_event, self.enabled = on_change, on_event, enabled
        self.env = env                 # () → {"GH_TOKEN": …} de esta cuenta
        self.repos = repos             # () → estados git de los repos vigilados (para «en tus repos»)
        self.state, self.error = "loading", ""
        self.login, self.review, self.mine, self.merged = login, [], [], []
        self.theirs = []               # PR abiertas de otros en repos a los que tienes acceso
        self.access = {}               # «owner/repo» → {"push": bool} | None (sin acceso)
        self.repo_info = {}            # «owner/repo» → métodos de fusión permitidos
        self.recheck = False           # llegaron repos nuevos mientras consultaba: volver a mirar al terminar
        self.updated, self.loading = 0.0, False
        self._known = None        # PR con revisión pedida ya vistas (None = primera carga, no avisar)
        self._prev = {}           # estado anterior de mis PR (CI y revisión)
        self._merged = None       # PR mías ya vistas fusionadas (None = primera carga)
        self._seen = None         # notificaciones de la bandeja ya avisadas («id@fecha»)
        self._theirs = None       # PR de otros ya vistas (None = primera carga, no avisar)
        self._alerted = set()     # URL de PR ya avisadas (por la bandeja o como PR nueva), para no repetir
        self.inbox = []           # bandeja de GitHub sin leer
        self.poll = Poller(self.refresh).every(EVERY)
        if start:               # start=False: quien lo crea lo registra antes y llama a refresh() después
            self.refresh()

    def _run(self, argv, cb):
        run(argv, cb, env=self.env())

    def refresh(self):
        if self.loading or not self.enabled():
            return
        if not GLib.find_program_in_path("gh"):
            self.state = "nogh"
            self.on_change()
            return
        self.loading = True
        self.on_change()
        if self.login is None:
            self._run(["gh", "api", "user", "--jq", ".login"], self._got_login)
        else:
            self._query()

    def _got_login(self, ok, out, err):
        if not ok:
            return self._fail(err)
        self.login = out.strip()
        self._query()

    def my_repos(self):
        """Slugs de los repos vigilados a los que esta cuenta tiene acceso."""
        return sorted({s["slug"] for s in self.repos() if s.get("slug") and self.access.get(s["slug"])})

    def _check_access(self, then):
        """Pregunta a GitHub (una vez por repo) si esta cuenta puede leer/escribir cada repo vigilado."""
        todo = sorted({s["slug"] for s in self.repos() if s.get("slug")} - set(self.access))
        if not todo:
            return then()
        parts = []
        for i, slug in enumerate(todo):
            owner, name = slug.split("/", 1)
            parts.append(f'r{i}: repository(owner: "{owner}", name: "{name}") {{ viewerPermission '
                         'mergeCommitAllowed squashMergeAllowed rebaseMergeAllowed }')

        def got(ok, out, err):
            data = {}
            try:
                data = json.loads(out).get("data") or {}
            except ValueError:
                pass
            if not ok and not data:
                dbg("github access:", err.strip()[:200])
                return then()
            for i, slug in enumerate(todo):
                r = data.get(f"r{i}")
                perm = (r or {}).get("viewerPermission")
                self.access[slug] = {"push": perm in ("ADMIN", "MAINTAIN", "WRITE")} if perm else None
                if r:
                    self.repo_info[slug] = r
            then()

        self._run(["gh", "api", "graphql", "-f", "query=query { " + " ".join(parts) + " }"], got)

    def _query(self):
        self._check_access(self._query_prs)

    def _query_prs(self):
        if not _LOGIN.fullmatch(self.login or ""):       # va dentro de la consulta: nada de comillas ni espacios
            self.loading = False
            self.state, self.error = "error", "La cuenta de gh tiene un nombre no válido"
            self.on_change()
            return
        theirs = ""
        mine = self.my_repos()
        if mine:
            theirs = ("theirs: search(query: \"is:pr is:open archived:false -author:%s %s\", type: ISSUE, first: 25) "
                      "{ nodes { %s } } ") % (self.login, " ".join("repo:" + r for r in mine), self.FIELDS)
        q = ("query { " + theirs + "mine: search(query: \"is:pr is:open archived:false author:%s\", type: ISSUE, first: 25) "
             "{ nodes { %s } } review: search(query: \"is:pr is:open archived:false review-requested:%s\", "
             "type: ISSUE, first: 25) { nodes { %s } } "
             "merged: search(query: \"is:pr is:merged author:%s merged:>=%s\", type: ISSUE, first: 10) "
             "{ nodes { %s } } }") % (self.login, self.FIELDS, self.login, self.FIELDS, self.login,
                                      time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400)),
                                      self.FIELDS)
        self._run(["gh", "api", "graphql", "-f", "query=" + q], self._done)

    def _fail(self, err):
        self.loading = False
        low = err.lower()
        if "auth login" in low or "not logged" in low or "authentication" in low or "401" in low:
            self.state, self.login = "noauth", None
        else:
            self.state, self.error = "error", "No se pudo consultar GitHub (¿sin conexión?)"
        dbg("github error:", err.strip()[:200])
        self.on_change()

    @staticmethod
    def _pr(node):
        commits = (node.get("commits") or {}).get("nodes") or []
        roll = (commits[0]["commit"].get("statusCheckRollup") or {}) if commits else {}
        return {"id": node["id"], "num": node["number"], "title": node["title"], "url": node["url"],
                "repo": node["repository"]["nameWithOwner"], "author": (node.get("author") or {}).get("login", ""),
                "draft": node.get("isDraft"), "updated": iso_ts(node.get("updatedAt")),
                "merged": iso_ts(node["mergedAt"]) if node.get("mergedAt") else None,
                "review": node.get("reviewDecision"), "ci": roll.get("state")}

    def _done(self, ok, out, err):
        if not ok:
            return self._fail(err)
        try:
            data = json.loads(out)["data"]
            mine = [self._pr(n) for n in data["mine"]["nodes"] if n]
            review = [self._pr(n) for n in data["review"]["nodes"] if n]
            merged = [self._pr(n) for n in data["merged"]["nodes"] if n]
            theirs = [self._pr(n) for n in (data.get("theirs") or {}).get("nodes", []) if n]
        except (ValueError, KeyError, TypeError) as e:
            return self._fail(str(e))
        self.loading, self.state, self.updated = False, "ok", time.time()
        self.mine = sorted(mine, key=lambda p: -p["updated"])
        self.review = sorted(review, key=lambda p: -p["updated"])
        self.merged = sorted(merged, key=lambda p: -p["merged"])
        rv = {p["id"] for p in review}
        self.theirs = sorted((p for p in theirs if p["id"] not in rv), key=lambda p: -p["updated"])
        self._notify_changes()
        self.on_change()
        self._run(["gh", "api", "notifications?per_page=30"], self._got_inbox)
        if self.recheck:
            self.recheck = False
            GLib.idle_add(lambda: self.refresh() and False)

    def unchecked(self):
        """Repos vigilados de GitHub de los que aún no sabemos si son de esta cuenta."""
        return {s["slug"] for s in self.repos() if s.get("slug")} - set(self.access)

    def _got_inbox(self, ok, out, err):
        """Bandeja de GitHub: PR nuevas, comentarios, menciones, issues, releases… de los repos que sigues."""
        if not ok:
            dbg("github inbox error:", err.strip()[:200])
            return
        try:
            items = [inbox_item(r) for r in json.loads(out) if r.get("unread", True)]
        except (ValueError, TypeError, AttributeError) as e:
            dbg("github inbox error:", e)
            return
        self.inbox = sorted(items, key=lambda i: -(i["updated"] or 0))
        self._notify_inbox()
        self.on_change()

    def _notify_inbox(self):
        keys = {i["key"] for i in self.inbox}
        if self._seen is None:                  # al arrancar: un resumen, no una alerta por cada una
            if self.inbox:
                self.on_event("inbox_summary", {"count": len(self.inbox), "items": self.inbox})
        else:
            new = [i for i in self.inbox if i["key"] not in self._seen]
            if len(new) > 5:                     # muchas de golpe: un resumen
                self.on_event("inbox_summary", {"count": len(new), "items": new})
            else:
                for i in reversed(new):          # la más reciente queda arriba
                    self._alerted.add(i["url"])
                    self.on_event("inbox", i)
        self._seen = (self._seen or set()) | keys

    def _notify_changes(self):
        # primero CI y revisiones de mis PR; al final las revisiones pedidas, que son lo más importante
        for p in self.mine:
            old = self._prev.get(p["id"])
            if old:
                if old["ci"] in ("PENDING", "EXPECTED") and p["ci"] in ("SUCCESS", "FAILURE", "ERROR"):
                    self.on_event("ci", p)
                if p["review"] != old["review"] and p["review"] in ("APPROVED", "CHANGES_REQUESTED"):
                    self.on_event("decision", p)
        self._prev = {p["id"]: {"ci": p["ci"], "review": p["review"]} for p in self.mine}
        merged = {p["id"] for p in self.merged}
        if self._merged is not None:
            for p in self.merged:
                if p["id"] not in self._merged:
                    self.on_event("merged", p)
        self._merged = merged
        theirs = {p["id"] for p in self.theirs}
        if self._theirs is not None:
            for p in reversed(self.theirs):
                if p["id"] not in self._theirs and p["url"] not in self._alerted:
                    self._alerted.add(p["url"])
                    self.on_event("new_pr", p)
        self._theirs = theirs
        ids = {p["id"] for p in self.review}
        if self._known is not None:
            for p in self.review:
                if p["id"] not in self._known:
                    self.on_event("review", p)
        self._known = ids

    # ── una PR: detalle y acciones (como esta cuenta) ──
    def pr_detail(self, p, cb):
        """cb(detalle | None, error)."""
        def got(ok, out, err):
            if not ok:
                return cb(None, (err.strip().splitlines() or ["No se pudo abrir la PR"])[-1])
            try:
                d = json.loads(out)
            except ValueError as e:
                return cb(None, str(e))
            d["ci"] = ci_state(d.get("statusCheckRollup"))
            cb(d, "")
        self._run(["gh", "pr", "view", str(p["num"]), "-R", p["repo"], "--json", PR_VIEW], got)

    def pr_action(self, p, action, body="", cb=lambda ok, msg: None):
        """approve | changes (con comentario) | merge | close."""
        n, repo = str(p["num"]), p["repo"]
        argv = {"approve": ["gh", "pr", "review", n, "-R", repo, "--approve"] + (["-b", body] if body else []),
                "changes": ["gh", "pr", "review", n, "-R", repo, "--request-changes", "-b", body or "Pido cambios"],
                "merge": ["gh", "pr", "merge", n, "-R", repo, merge_flag(self.repo_info.get(repo))],
                "close": ["gh", "pr", "close", n, "-R", repo] + (["-c", body] if body else [])}.get(action)
        if not argv:
            return cb(False, "Acción desconocida")
        done = {"approve": "Aprobada", "changes": "Cambios pedidos", "merge": "Fusionada", "close": "Cerrada"}

        def fin(ok, out, err):
            msg = done[action] if ok else (err.strip().splitlines() or ["Falló"])[-1]
            cb(ok, msg)
            if ok:
                self.refresh()
        self._run(argv, fin)

    @staticmethod
    def describe(p, mine):
        """Texto secundario y color de una PR."""
        bits = [f"{p['repo']}#{p['num']}"]
        if p.get("merged"):
            return " · ".join(bits + [f"fusionada {ago_long(p['merged'])}"]), None
        if not mine and p["author"]:
            bits.append(p["author"])
        if p["draft"]:
            bits.append("Borrador")
        ci = {"SUCCESS": "✓ CI", "FAILURE": "✗ CI", "ERROR": "✗ CI", "PENDING": "● CI en curso",
              "EXPECTED": "● CI en curso"}.get(p["ci"])
        if ci:
            bits.append(ci)
        rv = {"APPROVED": "Aprobada", "CHANGES_REQUESTED": "Cambios pedidos",
              "REVIEW_REQUIRED": "Falta revisión"}.get(p["review"])
        if rv and mine:
            bits.append(rv)
        bits.append(ago_long(p["updated"]))
        accent = None
        if p["ci"] in ("FAILURE", "ERROR"):
            accent = "red"
        elif p["review"] == "CHANGES_REQUESTED":
            accent = "orange"
        elif mine and p["review"] == "APPROVED" and p["ci"] in (None, "SUCCESS"):
            accent = "green"
        return " · ".join(bits), accent
