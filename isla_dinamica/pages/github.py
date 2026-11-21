"""Pull requests de GitHub."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import feature, page

feature("github", "GitHub", "Tus pull requests y avisos de revisiones y CI (consulta cada 3 min)")
feature("deploys", "Despliegues en vivo",
        "Despliegues de tus repos (Railway) en la pestaña GitHub: progreso en la píldora y aviso al terminar")

DEPLOY_TXT = {"SUCCESS": ("Desplegado", "green", "emblem-ok-symbolic"),
              "FAILURE": ("Falló", "red", "dialog-error-symbolic"),
              "ERROR": ("Error", "red", "dialog-error-symbolic"),
              "INACTIVE": ("Reemplazado", None, "emblem-ok-symbolic")}


class GitHubPage:
    PAGES = {
        "github": page("_build_github", "_fill_github", ("github", "deploys", "features"), "_open_github"),
    }

    # ── GitHub ──
    def _build_github(self):
        gh = self.core.github
        box = self._page("GitHub", button("ctrl", icon("view-refresh-symbolic"), self._gh_refresh, "Actualizar"))
        self.gh_setup = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.gh_setup_msg = label("", "subtitle", lines=3)
        self.gh_setup.pack_start(self.gh_setup_msg, False, False, 0)
        self.gh_cmds = label("", "cmd", ellipsize=False)
        self.gh_cmds.set_selectable(True)
        self.gh_cmds.set_xalign(0.0)
        self.gh_setup.pack_start(self.gh_cmds, False, False, 0)
        hint = Gtk.Box(spacing=8)
        hint.pack_start(label("Córrelos en una terminal y luego pulsa Actualizar.", "dim small", lines=2),
                        True, True, 0)
        hint.pack_end(button("chip", cb=lambda: self._copy(self.gh_cmds.get_text()), text="Copiar"),
                      False, False, 0)
        self.gh_setup.pack_start(hint, False, False, 0)
        box.pack_start(self.gh_setup, False, False, 0)
        self.gh_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.gh_list, 380), False, False, 0)
        foot = Gtk.Box()
        self.gh_status = label("", "dim small")
        foot.pack_start(self.gh_status, True, True, 0)
        foot.pack_end(button("chip", cb=lambda: self._collapse_then(self.core.open_github), text="Abrir GitHub"),
                      False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _fill_github(self):
        gh, c = self.core.github, self.core
        setup = {"nogh": ("Para ver tus PR, instala la herramienta de GitHub e inicia sesión:",
                          "sudo apt install gh\ngh auth login"),
                 "noauth": ("Inicia sesión en GitHub con la herramienta gh:", "gh auth login")}.get(gh.state)
        self.gh_setup.set_visible(setup is not None)
        if setup:
            self.gh_setup_msg.set_text(setup[0])
            self.gh_cmds.set_text(setup[1])
        clear(self.gh_list)
        deploys = c.feature("deploys")
        if deploys and c.deploys.active():
            self._fill_deploys_active()
        if gh.state == "ok" or gh.review or gh.mine:
            for key, title, prs, mine, empty, when in (
                    ("gh_review", "REVISIÓN PEDIDA", gh.review, False, "Nadie te pidió revisar nada", "updated"),
                    ("gh_mine", "MIS PR ABIERTAS", gh.mine, True, "No tienes PR abiertas", "updated"),
                    ("gh_merged", "FUSIONADAS · ÚLTIMOS 7 DÍAS", gh.merged, True,
                     "Ninguna fusionada esta semana", "merged")):
                if not self._gh_section(key, title, len(prs), today_count(p.get(when) for p in prs)):
                    continue
                for p in prs:
                    sub, acc = GitHub.describe(p, mine)
                    ic = ("emblem-ok-symbolic" if p.get("merged") else
                          "document-edit-symbolic" if p["draft"] else GITHUB_APP)
                    self.gh_list.pack_start(self._row(ic, p["title"], sub,
                                                      lambda p=p: self._collapse_then(
                                                          lambda: c.open_github(p["url"])),
                                                      sub_accent=acc), False, False, 0)
                if not prs:
                    self._empty(self.gh_list, empty)
        if deploys:
            self._fill_deploys_recent()
        self.gh_list.show_all()
        st = ("Actualizando…" if gh.loading else gh.error if gh.state == "error" else
              f"@{gh.login} · actualizado {hm(gh.updated)}"
              if gh.state == "ok" else "")
        dp = c.deploys
        if deploys and dp.loading and not gh.loading:
            st = "Actualizando despliegues…"
        elif deploys and dp.error and gh.state == "ok":
            st += f" · despliegues: {dp.error}"
        self.gh_status.set_text(st)
        set_accent(self.gh_status, "red" if gh.state == "error" and not gh.loading else None)

    def _gh_refresh(self):
        self.core.github.refresh()
        if self.core.feature("deploys"):
            self.core.deploys.refresh()

    def _open_github(self):
        gh = self.core.github
        if gh.state != "ok" or time.time() - gh.updated > 60:
            gh.refresh()
        if self.core.feature("deploys") and time.time() - self.core.deploys.updated > 30:
            self.core.deploys.refresh()

    def _gh_section(self, key, title, total, today=0, top=True):
        return self._fold(self.gh_list, key, title, total, today, self._fill_github, top)

    # ── Despliegues (Railway u otras plataformas que reportan a GitHub) ──
    def _deploy_row(self, ic, d, sub, acc):
        return self._row(ic, d["name"], sub, lambda: self._collapse_then(lambda: open_uri(d["url"])),
                         sub_accent=acc)

    def _fill_deploys_active(self):
        act = self.core.deploys.active()
        if not self._gh_section("dp_active", "DESPLEGANDO", len(act), top=False):
            return
        for d in act:
            sub = f"{d['env']} · {d['commit']} · desde hace {fmt_secs(time.time() - d['created'])}"
            self.gh_list.pack_start(self._deploy_row("emblem-synchronizing-symbolic", d, sub, "orange"),
                                    False, False, 0)

    def _fill_deploys_recent(self):
        dp = self.core.deploys
        recent = dp.recent()
        if not self._gh_section("dp_recent", "DESPLIEGUES RECIENTES", len(recent),
                                today_count(d["changed"] for d in recent)):
            return
        for d in recent:
            txt, acc, ic = DEPLOY_TXT.get(d["state"], (d["state"].capitalize(), None, "emblem-ok-symbolic"))
            if dp.stuck(d):
                txt, acc, ic = "Sin terminar (la plataforma no avisó el final)", None, "dialog-question-symbolic"
            sub = f"{d['env']} · {txt} {ago_long(d['changed'])} · {d['commit']}"
            self.gh_list.pack_start(self._deploy_row(ic, d, sub, acc), False, False, 0)
        if not recent:
            self._empty(self.gh_list, "Sin despliegues recientes en tus repos")
