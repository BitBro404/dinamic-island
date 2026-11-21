"""Pull requests de GitHub con la herramienta gh."""
from ..common import *  # noqa: F401,F403


class GitHub:
    """PR de GitHub usando la sesión de la herramienta `gh` (gh auth login). Se actualiza cada 3 minutos."""
    FIELDS = """... on PullRequest { id number title url isDraft updatedAt mergedAt reviewDecision
        repository { nameWithOwner } author { login }
        commits(last: 1) { nodes { commit { statusCheckRollup { state } } } } }"""

    def __init__(self, on_change, on_event, enabled=lambda: True):
        self.on_change, self.on_event, self.enabled = on_change, on_event, enabled
        self.state, self.error = "loading", ""
        self.login, self.review, self.mine, self.merged = None, [], [], []
        self.updated, self.loading = 0.0, False
        self._known = None        # PR con revisión pedida ya vistas (None = primera carga, no avisar)
        self._prev = {}           # estado anterior de mis PR (CI y revisión)
        self.refresh()
        GLib.timeout_add_seconds(180, lambda: (self.refresh(), True)[1])

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
            run(["gh", "api", "user", "--jq", ".login"], self._got_login)
        else:
            self._query()

    def _got_login(self, ok, out, err):
        if not ok:
            return self._fail(err)
        self.login = out.strip()
        self._query()

    def _query(self):
        q = ("query { mine: search(query: \"is:pr is:open archived:false author:%s\", type: ISSUE, first: 25) "
             "{ nodes { %s } } review: search(query: \"is:pr is:open archived:false review-requested:%s\", "
             "type: ISSUE, first: 25) { nodes { %s } } "
             "merged: search(query: \"is:pr is:merged author:%s merged:>=%s\", type: ISSUE, first: 10) "
             "{ nodes { %s } } }") % (self.login, self.FIELDS, self.login, self.FIELDS, self.login,
                                      time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400)),
                                      self.FIELDS)
        run(["gh", "api", "graphql", "-f", "query=" + q], self._done)

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
        except (ValueError, KeyError, TypeError) as e:
            return self._fail(str(e))
        self.loading, self.state, self.updated = False, "ok", time.time()
        self.mine = sorted(mine, key=lambda p: -p["updated"])
        self.review = sorted(review, key=lambda p: -p["updated"])
        self.merged = sorted(merged, key=lambda p: -p["merged"])
        self._notify_changes()
        self.on_change()

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
        ids = {p["id"] for p in self.review}
        if self._known is not None:
            for p in self.review:
                if p["id"] not in self._known:
                    self.on_event("review", p)
        self._known = ids

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
