"""Pull requests de GitHub."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import feature, page

feature("github", "GitHub", "Tus pull requests y avisos de revisiones y CI (consulta cada 3 min)")


class GitHubPage:
    PAGES = {
        "github": page("_build_github", "_fill_github", ("github",), "_open_github"),
    }

    # ── GitHub ──
    def _build_github(self):
        gh = self.core.github
        box = self._page("GitHub", button("ctrl", icon("view-refresh-symbolic"), gh.refresh, "Actualizar"))
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
        if gh.state == "ok" or gh.review or gh.mine:
            for title, prs, mine, empty in (("REVISIÓN PEDIDA", gh.review, False, "Nadie te pidió revisar nada"),
                                            ("MIS PR ABIERTAS", gh.mine, True, "No tienes PR abiertas"),
                                            ("FUSIONADAS · ÚLTIMOS 7 DÍAS", gh.merged, True,
                                             "Ninguna fusionada esta semana")):
                head = label(f"{title} · {len(prs)}", "section")
                head.set_margin_top(6)
                self.gh_list.pack_start(head, False, False, 0)
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
        self.gh_list.show_all()
        st = ("Actualizando…" if gh.loading else gh.error if gh.state == "error" else
              f"@{gh.login} · actualizado {time.strftime('%H:%M', time.localtime(gh.updated))}"
              if gh.state == "ok" else "")
        self.gh_status.set_text(st)
        set_accent(self.gh_status, "red" if gh.state == "error" and not gh.loading else None)

    def _open_github(self):
        gh = self.core.github
        if gh.state != "ok" or time.time() - gh.updated > 60:
            gh.refresh()
