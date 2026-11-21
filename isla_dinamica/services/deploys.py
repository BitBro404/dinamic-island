"""Despliegues en vivo: los que Railway (u otra plataforma) reporta a GitHub como «deployments»."""
import json
import time

from gi.repository import GLib

from ..util.fmt import iso_ts
from ..util.proc import dbg, run
from ..util.safety import is_safe_web_url
from .poller import Poller

ACTIVE_STATES = ("IN_PROGRESS", "QUEUED", "PENDING", "WAITING")
STUCK_AFTER = 45 * 60      # «en curso» hace más de esto: la plataforma no informó el final (trabado)
DONE_STATES = ("SUCCESS", "FAILURE", "ERROR")

_REPOS_Q = """query { viewer {
  organizations(first: 10) { nodes { repositories(first: 20, orderBy: {field: PUSHED_AT, direction: DESC}) {
    nodes { nameWithOwner pushedAt isArchived } } } }
  repositories(first: 10, ownerAffiliations: [OWNER], orderBy: {field: PUSHED_AT, direction: DESC}) {
    nodes { nameWithOwner pushedAt isArchived } } } }"""

_DEPLOY_FIELDS = """nameWithOwner deployments(last: 4, orderBy: {field: CREATED_AT, direction: ASC}) { nodes {
  id environment createdAt state creator { login } commit { messageHeadline abbreviatedOid }
  latestStatus { state createdAt environmentUrl logUrl } } }"""


def deploy_url(status, repo):
    """Enlace del despliegue: el log o la web que informó la plataforma si es una URL segura;
    si no, la lista de despliegues del repo en GitHub."""
    st = status or {}
    for url in (st.get("logUrl"), st.get("environmentUrl")):
        if url and is_safe_web_url(url):
            return url
    return f"https://github.com/{repo}/deployments"


class Deploys:
    """Consulta con `gh` los despliegues recientes de los repos con actividad en las últimas 3 semanas.
    Cada 30 s si hay alguno en curso; si no, cada 90 s. Una sola consulta GraphQL por vuelta."""

    def __init__(self, on_change, on_event, enabled=lambda: True):
        self.on_change, self.on_event, self.enabled = on_change, on_event, enabled
        self.items = {}            # id → despliegue
        self.repos, self._repos_t = [], 0.0
        self.loading, self.updated, self.error = False, 0.0, ""
        self._known = None         # ids vistos (None = primera carga: no avisar de lo viejo)
        self.poll = Poller(self.refresh).soon(6)

    # ── consultas ──
    def refresh(self):
        if self.loading:
            return
        if not self.enabled() or not GLib.find_program_in_path("gh"):
            self.poll.soon(120)
            return
        self.loading = True
        if not self.repos or time.time() - self._repos_t > 1800:
            run(["gh", "api", "graphql", "-f", "query=" + _REPOS_Q], self._got_repos)
        else:
            self._query()

    def _got_repos(self, ok, out, err):
        if ok:
            try:
                v = json.loads(out)["data"]["viewer"]
                nodes = [n for o in v["organizations"]["nodes"] for n in o["repositories"]["nodes"]]
                nodes += v["repositories"]["nodes"]
                cutoff = time.time() - 21 * 86400
                fresh = [n for n in nodes if not n["isArchived"] and iso_ts(n["pushedAt"]) > cutoff]
                fresh.sort(key=lambda n: -iso_ts(n["pushedAt"]))
                self.repos, self._repos_t = [n["nameWithOwner"] for n in fresh][:15], time.time()
            except (ValueError, KeyError, TypeError) as e:
                dbg("deploys repos:", e)
        if not self.repos:
            return self._fail(err or "sin repos")
        self._query()

    def _query(self):
        parts = []
        for i, full in enumerate(self.repos):
            owner, name = full.split("/", 1)
            parts.append(f'r{i}: repository(owner: "{owner}", name: "{name}") {{ {_DEPLOY_FIELDS} }}')
        run(["gh", "api", "graphql", "-f", "query=query { " + " ".join(parts) + " }"], self._done)

    def _fail(self, err):
        self.loading = False
        self.error = "No se pudo consultar GitHub"
        dbg("deploys error:", (err or "").strip()[:200])
        self.on_change()
        self.poll.soon(120)

    @staticmethod
    def _item(repo, n):
        st = n.get("latestStatus") or {}
        env = n.get("environment") or ""
        return {"id": n["id"], "repo": repo, "name": repo.split("/")[-1],
                "env": env.split(" / ")[-1], "project": env.split(" / ")[0] if " / " in env else "",
                "state": st.get("state") or n.get("state") or "PENDING",
                "created": iso_ts(n["createdAt"]), "changed": iso_ts(st.get("createdAt") or n["createdAt"]),
                "url": deploy_url(st, repo),
                "commit": ((n.get("commit") or {}).get("messageHeadline") or "")[:80],
                "by": (n.get("creator") or {}).get("login", "")}

    def _done(self, ok, out, err):
        if not ok:
            return self._fail(err)
        try:
            data = json.loads(out)["data"]
        except (ValueError, KeyError, TypeError) as e:
            return self._fail(str(e))
        items = {}
        for repo in (data or {}).values():
            if not repo:
                continue
            for n in repo["deployments"]["nodes"]:
                d = self._item(repo["nameWithOwner"], n)
                items[d["id"]] = d
        self.apply(items)

    def apply(self, items):
        """Actualiza con despliegues nuevos (también lo usan las pruebas) y avisa de los que terminaron."""
        if self._known is not None:
            for i, d in items.items():
                old = self.items.get(i)
                was_active = old is not None and old["state"] in ACTIVE_STATES
                fresh_done = old is None and time.time() - d["changed"] < 600
                if d["state"] in DONE_STATES and (was_active or fresh_done):
                    self.on_event("done", d)
                elif d["state"] in ACTIVE_STATES and old is None:
                    self.on_event("start", d)
        self._known = set(items)
        self.items = items
        self.loading, self.updated, self.error = False, time.time(), ""
        self.on_change()
        self.poll.soon(30 if self.active() else 90)

    # ── consultas para la interfaz ──
    @staticmethod
    def stuck(d):
        return d["state"] in ACTIVE_STATES and time.time() - d["created"] > STUCK_AFTER

    def active(self):
        return sorted((d for d in self.items.values() if d["state"] in ACTIVE_STATES and not self.stuck(d)),
                      key=lambda d: d["created"])

    def recent(self, n=12):
        done = [d for d in self.items.values() if d["state"] not in ACTIVE_STATES or self.stuck(d)]
        return sorted(done, key=lambda d: -d["changed"])[:n]
