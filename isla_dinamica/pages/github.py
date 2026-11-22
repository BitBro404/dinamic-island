"""Pull requests de GitHub."""
import os
import subprocess
import time

from gi.repository import GLib, Gtk

from ..services.github import GitHub
from ..services.gitwatch import changes, compare_url, expand, pr_check, short, summary
from ..platform.terminal import conflict_prompt, resolver_command, resolvers, terminal_argv
from ..ui.gtk import button, clear, icon, label, set_accent, set_class
from ..util.fmt import ago_long, fmt_secs, hm, iso_ts, today_count
from ..util.links import GITHUB_APP
from ..util.safety import open_web
from .base import Page
from .registry import feature, page

feature("github", "GitHub", "PR, revisiones, CI, commits por subir/bajar y cuentas de gh (consulta cada 5 min)")
feature("deploys", "Despliegues en vivo",
        "Despliegues de tus repos (Railway) en la pestaña GitHub: progreso en la píldora y aviso al terminar")

DEPLOY_TXT = {"SUCCESS": ("Desplegado", "green", "emblem-ok-symbolic"),
              "FAILURE": ("Falló", "red", "dialog-error-symbolic"),
              "ERROR": ("Error", "red", "dialog-error-symbolic"),
              "INACTIVE": ("Reemplazado", None, "emblem-ok-symbolic")}


class GitHubPage(Page):
    """GitHub de la cuenta elegida: PR (ver, aprobar, pedir cambios, fusionar, cerrar), commits por subir o
    bajar de sus repos, despliegues y cambio de cuenta con contraseña."""
    PAGES = {
        "github": page("_build_github", "_fill_github", ("github", "deploys", "features", "git"), "_open_github"),
        "ghacct": page("_build_acct", "_fill_acct", ("github",), "_open_acct"),
        "ghproj": page("_build_proj", "_fill_proj", ("git", "github")),
        "ghrepo": page("_build_repo", "_fill_repo", ("git", "github"), "_open_repo"),
        "ghpr": page("_build_pr", "_fill_pr", ("github",), "_open_pr"),
    }

    def __init__(self, host):
        super().__init__(host)
        self.sel_repo = None       # ruta del repo abierto en «ghrepo»
        self.sel_pr = None         # PR abierta en «ghpr»
        self.pr_data, self.pr_err, self.pr_busy = None, "", None
        self._confirm = None       # acción que espera el segundo clic («merge», «close»)
        self._msgs = {}            # página → (texto, color)
        self.rp_branches, self.rp_default, self._combo_sig = [], None, None

    # ── GitHub ──
    def _build_github(self):
        box = self._page("GitHub", button("ctrl", icon("view-refresh-symbolic"), self._gh_refresh,
                                          "Actualizar y hacer fetch de tus repos"))
        acct = Gtk.Box(spacing=8)
        self.gh_acct = label("", "subtitle")
        acct.pack_start(icon("avatar-default-symbolic", px=18), False, False, 0)
        acct.pack_start(self.gh_acct, True, True, 0)
        acct.pack_end(button("chip", cb=lambda: self.go("ghacct"), text="Cuentas"), False, False, 0)
        acct.pack_end(button("chip", cb=self._show_proj, text="Proyectos"), False, False, 0)
        box.pack_start(acct, False, False, 0)
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

    def _account_repos(self):
        """Repos vigilados que son de la cuenta elegida (tiene acceso en GitHub)."""
        gh = self.core.github
        return [s for s in self.core.git.repos if not s.get("error") and
                (s.get("mine") or (s.get("slug") and gh.access.get(s["slug"])))]

    def _fill_github(self):
        gh, c, acc = self.core.github, self.core, self.core.gh_accounts
        n = len(acc.logins)
        self.gh_acct.set_text(f"@{acc.current}" + (f"  ·  {n} cuentas" if n > 1 else "") if acc.current
                              else "Sin cuenta de GitHub")
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
            self._fill_prs("gh_review", "REVISIÓN PEDIDA", gh.review, False, "Nadie te pidió revisar nada")
            if gh.theirs or gh.my_repos():
                self._fill_prs("gh_theirs", "PR EN TUS REPOS", gh.theirs, False, "No hay PR de otros abiertas")
            self._fill_prs("gh_mine", "MIS PR ABIERTAS", gh.mine, True, "No tienes PR abiertas")
        if c.feature("git"):
            self._fill_sync()
            self._fill_my_repos()
        if gh.state == "ok" or gh.merged:
            self._fill_prs("gh_merged", "FUSIONADAS · ÚLTIMOS 7 DÍAS", gh.merged, True,
                           "Ninguna fusionada esta semana", when="merged")
        if deploys:
            self._fill_deploys_recent()
        self.gh_list.show_all()
        g = c.git
        fetch = "haciendo fetch…" if g.fetching else f"fetch en {max(1, -(-g.next_fetch // 60))} min"
        st = ("Actualizando…" if gh.loading else gh.error if gh.state == "error" else
              f"actualizado {hm(gh.updated)}" if gh.state == "ok" else "")
        st = " · ".join(x for x in (st, fetch if c.feature("git") else "") if x)
        dp = c.deploys
        if deploys and dp.loading and not gh.loading:
            st = "Actualizando despliegues…"
        elif deploys and dp.error and gh.state == "ok":
            st += f" · despliegues: {dp.error}"
        self.gh_status.set_text(st)
        set_accent(self.gh_status, "red" if gh.state == "error" and not gh.loading else None)

    def _fill_prs(self, key, title, prs, mine, empty, when="updated"):
        if not self._gh_section(key, title, len(prs), today_count(p.get(when) for p in prs)):
            return
        for p in prs:
            sub, acc = GitHub.describe(p, mine)
            ic = ("emblem-ok-symbolic" if p.get("merged") else
                  "document-edit-symbolic" if p["draft"] else GITHUB_APP)
            web = button("ctrl", icon("web-browser-symbolic"),
                         lambda p=p: self._collapse_then(lambda: self.core.open_github(p["url"])), "Abrir en GitHub")
            self.gh_list.pack_start(self._row(ic, p["title"], sub, lambda p=p: self._show_pr(p), [web],
                                              sub_accent=acc), False, False, 0)
        if not prs:
            self._empty(self.gh_list, empty)

    def _fill_sync(self):
        repos = [s for s in self._account_repos() if s["ahead"] or s["behind"]]
        if not self._gh_section("gh_sync", "COMMITS POR SINCRONIZAR", len(repos)):
            return
        for s in repos:
            bits = []
            if s["behind"]:
                bits.append(f"↓{s['behind']} por bajar")
            if s["ahead"]:
                bits.append(f"↑{s['ahead']} por subir")
            last = (s["incoming"] or s["outgoing"] or [{}])[0]
            if last.get("author"):
                bits.append(f"{last['author']} {ago_long(last['ts'])}" if last.get("ts") else last["author"])
            busy = self.core.git.syncing.get(s["path"])
            sub = {"pull": "Bajando…", "push": "Subiendo…"}.get(busy) or " · ".join(bits)
            self.gh_list.pack_start(self._row("emblem-synchronizing-symbolic", f"{s['name']} · {s['branch']}", sub,
                                              lambda p=s["path"]: self._show_repo(p),
                                              sub_accent="blue" if s["behind"] else "orange"), False, False, 0)
        if not repos:
            n = len(self._account_repos())
            self._empty(self.gh_list, f"Tus {n} repos están al día" if n else
                        "Comprobando qué repos son de esta cuenta…" if self.core.github.unchecked() or
                        not self.core.git.updated else "Ninguno de los repos vigilados es de esta cuenta")

    def _fill_my_repos(self):
        repos = self._account_repos()
        if not repos or not self._gh_section("gh_repos", "TUS REPOS", len(repos)):
            return
        for s in repos:
            sub = f"{s['branch'] or '(sin rama)'} · {summary(s)}"
            self.gh_list.pack_start(self._row("folder-symbolic", s["name"], sub, lambda p=s["path"]: self._show_repo(p),
                                              sub_accent="orange" if changes(s) or s["stash"] else None),
                                    False, False, 0)

    def _gh_refresh(self):
        self.core.github.refresh()
        self.core.git.refresh(fetch=True)
        if self.core.feature("deploys"):
            self.core.deploys.refresh()

    def _open_github(self):
        self.core.dev.seen()                  # aquí se ven PR y commits por sincronizar: se apaga el punto
        gh = self.core.github
        if gh.state != "ok" or time.time() - gh.updated > 60:
            gh.refresh()
        if self.core.feature("deploys") and time.time() - self.core.deploys.updated > 30:
            self.core.deploys.refresh()

    # ── mensajes y confirmaciones ──
    def _msg(self, page_name, text, accent=None):
        self._msgs[page_name] = (text, accent)
        self.core.changed("github")

    def _show_msg(self, page_name, lb):
        text, accent = self._msgs.get(page_name, ("", None))
        lb.set_text(text)
        lb.set_visible(bool(text))
        set_accent(lb, accent)

    def _confirmed(self, key):
        """Primer clic: pide confirmación; segundo clic (antes de 8 s): True."""
        if self._confirm == key:
            self._confirm = None
            return True
        self._confirm = key
        GLib.timeout_add(8000, self._reset_confirm, key)
        self.core.changed("github")
        return False

    def _reset_confirm(self, key):
        if self._confirm == key:
            self._confirm = None
            self.core.changed("github")
        return False

    def on_collapse(self):
        self._confirm = None
        if hasattr(self, "pr_entry"):
            self.pr_entry.set_text("")

    def waiting(self):
        """Confirmación pendiente, contraseña pedida o un desplegable de ramas abierto (su menú queda fuera de
        la isla: sin esto se cerraría al ir a elegir)."""
        combos = [getattr(self, n, None) for n in ("rp_branch", "rp_from", "rp_to", "rp_newbase")]
        return bool(self._confirm) or bool(self.core.gh_accounts.switching) or \
            any(c is not None and c.get_property("popup-shown") for c in combos)

    def typing(self):
        return any(hasattr(self, n) and getattr(self, n).has_focus() for n in ("pr_entry", "pj_entry", "rp_new"))

    # ── proyectos de la cuenta (se recuerdan por cuenta en config.json) ──
    def _show_proj(self):
        self._msgs.pop("ghproj", None)
        self.go("ghproj")

    def _build_proj(self):
        box = self._page("Proyectos", back="github")
        self.pj_title = label("", "dim small", lines=2)
        box.pack_start(self.pj_title, False, False, 0)
        self.pj_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.pj_list, 280), False, False, 0)
        row = Gtk.Box(spacing=6)
        self.pj_entry = Gtk.Entry(hexpand=True, placeholder_text="Ruta del proyecto, p. ej. ~/proyectos/api")
        self.pj_entry.connect("activate", lambda *_: self._proj_add())
        row.pack_start(self.pj_entry, True, True, 0)
        row.pack_start(button("ctrl", icon("folder-open-symbolic"), self._proj_choose, "Elegir carpeta…"),
                       False, False, 0)
        row.pack_start(button("chip", cb=self._proj_add, text="Añadir"), False, False, 0)
        box.pack_start(row, False, False, 0)
        self.pj_msg = label("", "small", lines=2)
        box.pack_start(self.pj_msg, False, False, 0)
        return box

    def _fill_proj(self):
        g, login = self.core.git, self.core.gh_accounts.current
        self.pj_title.set_text(f"Proyectos que sigue @{login}: se recuerdan para esta cuenta y se vigilan con git y "
                               "GitHub mientras la uses. Puede ser un repo o una carpeta con varios." if login else
                               "Inicia sesión en gh para añadir proyectos a una cuenta.")
        clear(self.pj_list)
        folders = g.account_folders()
        for f in folders:
            root = expand(f)
            repos = [s for s in g.repos if s["path"] == root or s["path"].startswith(root + os.sep)]
            n = len(repos)
            if n == 1 and not repos[0].get("error"):
                sub = f"{repos[0]['name']} · {repos[0]['branch']} · {summary(repos[0])}"
            elif n:
                sub = f"{n} repos"
            elif os.path.isdir(root):
                sub = "Buscando repos…"
            else:
                sub = "La carpeta ya no existe"
            key = f"proj:{f}"
            if self._confirm == key:
                rm = button("chip danger", cb=lambda f=f: self._proj_remove(f), text="¿Seguro?")
                set_class(rm, "confirm", True)
            else:
                rm = button("ctrl", icon("list-remove-symbolic"), lambda f=f: self._proj_remove(f),
                            "Quitar de la cuenta")
            if root in self.core.git.ignored:
                sub = "Desconectado de la isla · vuelve a conectarlo en Proyectos"
            cb = (lambda p=repos[0]["path"]: self._show_repo(p)) if n == 1 else None
            self.pj_list.pack_start(self._row("folder-symbolic", f, sub, cb, [rm]), False, False, 0)
        if not folders:
            self._empty(self.pj_list, "Aún no añadiste proyectos a esta cuenta")
        self.pj_list.show_all()
        self._show_msg("ghproj", self.pj_msg)

    def _proj_add(self, path=None):
        path = path or self.pj_entry.get_text().strip()
        if not path:
            return self._msg("ghproj", "Escribe la ruta del proyecto o elígelo con el botón de carpeta", "orange")
        err = self.core.git.add_account_folder(path)
        if err:
            return self._msg("ghproj", f"{err}: {short(expand(path))}", "orange")
        self.pj_entry.set_text("")
        self._msg("ghproj", f"Añadido a @{self.core.gh_accounts.current}: {short(expand(path))}", "green")

    def _proj_remove(self, folder):
        if not self._confirmed(f"proj:{folder}"):
            return self._msg("ghproj", f"¿Quitar {folder} de @{self.core.gh_accounts.current}? Pulsa «¿Seguro?» "
                             "(no se borra nada del disco)", "orange")
        self.core.git.remove_account_folder(folder)
        self._msg("ghproj", f"Quitado de @{self.core.gh_accounts.current}: {folder} (no se borra nada del disco)",
                  "green")

    def _proj_choose(self):
        dlg = Gtk.FileChooserNative.new("Proyecto a seguir", None, Gtk.FileChooserAction.SELECT_FOLDER,
                                        "Seguir", "Cancelar")
        dlg.set_current_folder(os.path.expanduser("~"))
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self._proj_add(dlg.get_filename())
        dlg.destroy()

    # ── cuentas ──
    def _build_acct(self):
        box = self._page("Cuentas de GitHub", back="github")
        self.ac_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.ac_list, 300), False, False, 0)
        self.ac_msg = label("", "small", lines=2)
        box.pack_start(self.ac_msg, False, False, 0)
        hint = Gtk.Box(spacing=8)
        hint.pack_start(label("Cambiar de cuenta pide tu contraseña. Para añadir otra: gh auth login",
                              "dim small", lines=2), True, True, 0)
        hint.pack_end(button("chip", cb=lambda: self._copy("gh auth login"), text="Copiar"), False, False, 0)
        box.pack_start(hint, False, False, 0)
        return box

    def _open_acct(self):
        self.core.gh_accounts.load()
        self.core.changed("github")

    def _fill_acct(self):
        acc = self.core.gh_accounts
        clear(self.ac_list)
        for login in acc.logins:
            bits = []
            if login == acc.current:
                bits.append("En uso en la isla")
            if login == acc.gh_active:
                bits.append("activa en la terminal")
            if acc.switching == login:
                bits = ["Esperando tu contraseña…"]
            ic = "object-select-symbolic" if login == acc.current else "avatar-default-symbolic"
            cb = None if login == acc.current else (lambda l=login: self._switch_account(l))
            self.ac_list.pack_start(self._row(ic, f"@{login}", " · ".join(bits) or "Clic para usarla (pide contraseña)",
                                              cb, sub_accent="green" if login == acc.current else None),
                                    False, False, 0)
        if not acc.logins:
            self._empty(self.ac_list, "No hay sesiones en gh. Corre: gh auth login")
        self.ac_list.show_all()
        if acc.error:
            self._msgs["ghacct"] = (acc.error, "red")
        self._show_msg("ghacct", self.ac_msg)

    def _switch_account(self, login):
        self._msg("ghacct", f"Pidiendo tu contraseña para usar @{login}…")

        def done(ok, msg):
            self._msg("ghacct", msg, "green" if ok else "red")
            if ok:
                self.core.show_event(2.5, kind="pill", icon=GITHUB_APP, accent="green", text=msg)
        self.core.switch_github_account(login, done)

    # ── un repo: commits por bajar y por subir ──
    def _show_repo(self, path):
        self.sel_repo = path
        self._msgs.pop("ghrepo", None)
        self.rp_branches, self.rp_default, self._combo_sig = [], None, None
        self.go("ghrepo")

    def _repo(self):
        return next((s for s in self.core.git.repos if s["path"] == self.sel_repo), None)

    def _open_repo(self):
        s = self._repo()
        if not s:
            return

        def got(branches, default):
            if self.sel_repo == s["path"]:
                self.rp_branches, self.rp_default = branches, default
                self.core.changed("git")
        self.core.git.branches(s, got)

    @staticmethod
    def _combo():
        cb = Gtk.ComboBoxText(hexpand=True)
        cb.set_size_request(120, -1)
        return cb

    def _build_repo(self):
        box = self._page("Repo", back="github")
        self.rp_head = label("", "subtitle")
        self.rp_sub = label("", "dim small")
        box.pack_start(self.rp_head, False, False, 0)
        box.pack_start(self.rp_sub, False, False, 0)
        br = Gtk.Box(spacing=6)
        br.pack_start(label("Rama", "dim small", ellipsize=False), False, False, 0)
        self.rp_branch = self._combo()
        br.pack_start(self.rp_branch, True, True, 0)
        self.rp_switch = button("chip", cb=self._do_switch, text="Cambiar")
        br.pack_start(self.rp_switch, False, False, 0)
        self.rp_merge = button("chip", cb=self._do_merge, text="Merge aquí")
        self.rp_merge.set_tooltip_text("Fusiona la rama elegida en la rama actual")
        br.pack_start(self.rp_merge, False, False, 0)
        box.pack_start(br, False, False, 0)
        nb = Gtk.Box(spacing=6)
        nb.pack_start(label("Nueva", "dim small", ellipsize=False), False, False, 0)
        self.rp_new = Gtk.Entry(hexpand=True, placeholder_text="feat/login", width_chars=10)
        self.rp_new.connect("activate", lambda *_: self._do_create())
        nb.pack_start(self.rp_new, True, True, 0)
        nb.pack_start(label("desde", "dim small", ellipsize=False), False, False, 0)
        self.rp_newbase = self._combo()
        nb.pack_start(self.rp_newbase, True, True, 0)
        self.rp_newswitch = Gtk.CheckButton(label="ir", active=True)
        self.rp_newswitch.set_tooltip_text("Cambiar a la rama nueva al crearla")
        nb.pack_start(self.rp_newswitch, False, False, 0)
        nb.pack_start(button("chip", cb=self._do_create, text="Crear"), False, False, 0)
        box.pack_start(nb, False, False, 0)
        pr = Gtk.Box(spacing=6)
        pr.pack_start(label("PR", "dim small", ellipsize=False), False, False, 0)
        self.rp_from = self._combo()
        self.rp_to = self._combo()
        pr.pack_start(self.rp_from, True, True, 0)
        pr.pack_start(label("→", "dim", ellipsize=False), False, False, 0)
        pr.pack_start(self.rp_to, True, True, 0)
        pr.pack_start(button("chip", cb=self._do_pr, text="Crear PR en GitHub"), False, False, 0)
        box.pack_start(pr, False, False, 0)
        self.rp_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.rp_conflict = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.pack_start(self.rp_conflict, False, False, 0)
        box.pack_start(self._scroller(self.rp_list, 220), False, False, 0)
        self.rp_msg = label("", "small", lines=3)
        box.pack_start(self.rp_msg, False, False, 0)
        row = Gtk.Box(spacing=6)
        self.rp_pull = button("chip", cb=lambda: self._sync("pull"), text="Bajar (pull)")
        self.rp_push = button("chip", cb=lambda: self._sync("push"), text="Subir (push)")
        row.pack_start(self.rp_pull, False, False, 0)
        row.pack_start(self.rp_push, False, False, 0)
        row.pack_end(button("chip", cb=lambda: self.core.git.refresh(fetch=True), text="Fetch"), False, False, 0)
        box.pack_start(row, False, False, 0)
        return box

    def _fill_combos(self, s):
        """Rellena los selectores solo si cambió la lista (así no se pierde lo que el usuario eligió)."""
        names = [b["name"] for b in self.rp_branches]
        cur = s["branch"] if s["branch"] and s["branch"] != "(detached)" else None
        sig = (tuple(names), cur, self.rp_default)
        if sig == self._combo_sig:
            return
        self._combo_sig = sig
        for cb in (self.rp_branch, self.rp_from, self.rp_to, self.rp_newbase):
            cb.remove_all()
        for b in self.rp_branches:
            self.rp_branch.append(b["name"], b["name"] + ("  (remota)" if b["remote"] else ""))
        self.rp_branch.set_active(0 if names else -1)
        everything = ([cur] if cur else []) + names
        for n in everything:
            self.rp_from.append(n, n)
            self.rp_to.append(n, n)
            self.rp_newbase.append(n, n)
        if everything:
            self.rp_newbase.set_active(0)            # la rama actual
        if cur:
            self.rp_from.set_active_id(cur)
        base = self.rp_default if self.rp_default in everything and self.rp_default != cur else \
            next((n for n in everything if n != cur), None)
        if base:
            self.rp_to.set_active_id(base)

    def _commit_rows(self, commits, ic):
        for cm in commits:
            when = ago_long(cm["ts"]) if cm.get("ts") else ""
            sub = " · ".join(x for x in (cm["author"], when, cm["sha"]) if x)
            body = " ".join(ln for ln in cm.get("body", "").splitlines()
                            if ln.strip() and not ln.lower().startswith(("co-authored-by", "signed-off-by")))
            if body:
                sub += f"\n{body[:160]}"
            self.rp_list.pack_start(self._row(ic, cm["subject"], sub), False, False, 0)

    def _fill_repo(self):
        s = self._repo()
        clear(self.rp_list)
        if not s:
            self.rp_head.set_text("El repo ya no está en las carpetas vigiladas")
            self.rp_sub.set_text("")
            self.rp_pull.set_visible(False)
            self.rp_push.set_visible(False)
            self.rp_list.show_all()
            return
        gh = self.core.github
        can_push = bool((gh.access.get(s.get("slug")) or {}).get("push"))
        self.rp_head.set_text(f"{s['name']} · {s['branch']}")
        self.rp_sub.set_text(f"{s.get('slug') or s['path']} → {s['upstream'] or 'sin remoto'} · {summary(s)}"
                             f" · como @{self.core.gh_accounts.current}")
        busy = self.core.git.syncing.get(s["path"])
        self._fill_combos(s)
        self.rp_switch.set_sensitive(not busy and bool(self.rp_branches) and not s["merging"])
        self.rp_switch.set_label("Cambiando…" if busy == "switch" else "Cambiar")
        self.rp_merge.set_sensitive(not busy and bool(self.rp_branches) and not s["merging"])
        self.rp_merge.set_label("Fusionando…" if busy == "merge" else
                                "¿Seguro?" if self._confirm == "merge_repo" else "Merge aquí")
        set_class(self.rp_merge, "confirm", self._confirm == "merge_repo")
        self._fill_conflict(s, busy)
        if s["stashes"] and self._fold(self.rp_list, "rp_stash", "STASH", len(s["stashes"]), refill=self._fill_repo):
            for st in s["stashes"]:
                bits = [x for x in (f"en {st['branch']}" if st["branch"] else "",
                                    ago_long(st["ts"]) if st.get("ts") else "", st["ref"]) if x]
                key = f"drop:{st['sha']}"
                apply_b = button("chip", cb=lambda st=st: self._stash("stash_pop", st), text="Aplicar")
                drop_b = button("chip danger", cb=lambda st=st: self._stash("stash_drop", st),
                                text="¿Seguro?" if self._confirm == key else "Borrar")
                set_class(drop_b, "confirm", self._confirm == key)
                for b in (apply_b, drop_b):
                    b.set_sensitive(not busy)
                self.rp_list.pack_start(self._row("document-save-symbolic", st["msg"] or "(sin mensaje)",
                                                  " · ".join(bits), extra=[apply_b, drop_b]), False, False, 0)
        if self._fold(self.rp_list, "rp_in", "POR BAJAR", s["behind"], refill=self._fill_repo):
            self._commit_rows(s["incoming"], "go-down-symbolic")
            if not s["behind"]:
                self._empty(self.rp_list, "Nada nuevo en el remoto")
        if self._fold(self.rp_list, "rp_out", "POR SUBIR", s["ahead"], refill=self._fill_repo):
            self._commit_rows(s["outgoing"], "go-up-symbolic")
            if not s["ahead"]:
                self._empty(self.rp_list, "No tienes commits sin subir")
        self.rp_list.show_all()
        self.rp_pull.set_visible(bool(s["behind"]))
        self.rp_push.set_visible(bool(s["ahead"]))
        self.rp_pull.set_sensitive(not busy)
        self.rp_push.set_sensitive(not busy and can_push)
        self.rp_pull.set_label("Bajando…" if busy == "pull" else f"Bajar {s['behind']} (pull)")
        self.rp_push.set_label("Subiendo…" if busy == "push" else
                               f"Subir {s['ahead']} (push)" if can_push else "Sin permiso para subir")
        self._show_msg("ghrepo", self.rp_msg)

    def _fill_conflict(self, s, busy):
        """Merge en curso: archivos en conflicto y cómo resolverlos (asistente, editor, cancelar o terminar)."""
        clear(self.rp_conflict)
        self.rp_conflict.set_visible(s["merging"])
        if not s["merging"]:
            return
        files, src = s["conflict_files"], s.get("merge_from") or "otra rama"
        head = label(f"MERGE EN CURSO · {src} → {s['branch']}", "section")
        self.rp_conflict.pack_start(head, False, False, 0)
        if files:
            txt = label(f"{len(files)} archivo{'s' if len(files) != 1 else ''} en conflicto: {', '.join(files)}",
                        "small", lines=3)
            set_accent(txt, "red")
        else:
            txt = label("Sin conflictos pendientes: revisa los cambios y termina el merge.", "small", lines=2)
            set_accent(txt, "green")
        self.rp_conflict.pack_start(txt, False, False, 0)
        row = Gtk.Box(spacing=6)
        tools = resolvers()
        names = {"claude": "Claude", "opencode": "OpenCode", "code": "VS Code"}
        if any(k in tools for k in names):
            row.pack_start(label("Resolver con", "dim small", ellipsize=False), False, False, 0)
        for key in ("claude", "opencode", "code"):
            if key in tools and (files or key == "code"):
                b = button("chip", cb=lambda k=key: self._resolve(k), text=names[key])
                b.set_sensitive(not busy)
                row.pack_start(b, False, False, 0)
        abort = button("chip danger", cb=self._merge_abort,
                       text="¿Seguro?" if self._confirm == "merge_abort" else "Cancelar merge")
        set_class(abort, "confirm", self._confirm == "merge_abort")
        abort.set_sensitive(not busy)
        row.pack_end(abort, False, False, 0)
        if not files:
            fin = button("chip", cb=self._merge_finish, text="Terminando…" if busy == "merge_finish" else "Terminar merge")
            fin.set_sensitive(not busy)
            row.pack_end(fin, False, False, 0)
        self.rp_conflict.pack_start(row, False, False, 0)
        self.rp_conflict.show_all()

    def _do_merge(self):
        s, branch = self._repo(), self.rp_branch.get_active_id()
        if not s or not branch:
            return
        if changes(s):
            return self._msg("ghrepo", "Haz commit o descarta los cambios antes del merge", "orange")
        if not self._confirmed("merge_repo"):
            return self._msg("ghrepo", f"Vuelve a pulsar para fusionar {branch} en {s['branch']}", "orange")
        remote = next((b["remote"] for b in self.rp_branches if b["name"] == branch), False)
        self._msg("ghrepo", f"Fusionando {branch} en {s['branch']}…")
        self.core.git.op(s, "merge", lambda ok, msg: self._msg("ghrepo", msg, "green" if ok else "red"),
                         branch=branch, remote=remote)

    def _do_create(self):
        s = self._repo()
        name, base = self.rp_new.get_text().strip(), self.rp_newbase.get_active_id()
        if not s or not base:
            return
        remote = next((b["remote"] for b in self.rp_branches if b["name"] == base), False)
        switch = self.rp_newswitch.get_active()
        if switch and changes(s):
            return self._msg("ghrepo", "Haz commit o descarta los cambios antes de cambiar de rama "
                                       "(o desmarca «y cambiar»)", "orange")

        def done(ok, msg):
            self._msg("ghrepo", msg, "green" if ok else "red")
            if ok:
                self.rp_new.set_text("")
                self._open_repo()
        self.core.git.op(s, "create", done, name=name, base=base, base_remote=remote, switch=switch)

    def _resolve(self, tool):
        s = self._repo()
        tools = resolvers()
        if not s or tool not in tools:
            return
        files = s["conflict_files"]
        argv = resolver_command(tool, tools, s["path"], files,
                                conflict_prompt(files, s.get("merge_from") or "otra rama", s["branch"]))
        if tool != "code":
            argv = terminal_argv(s["path"], argv)
            if not argv:
                return self._msg("ghrepo", "No encontré una terminal para abrir el asistente", "red")
        try:
            subprocess.Popen(argv, cwd=s["path"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError as e:
            return self._msg("ghrepo", f"No se pudo abrir: {e}", "red")
        self._msg("ghrepo", {"claude": "Claude está resolviendo el conflicto en una terminal",
                             "opencode": "OpenCode está resolviendo el conflicto en una terminal",
                             "code": "Abierto en VS Code: resuélvelo y guarda"}[tool] +
                  "; cuando acabe, vuelve aquí y pulsa Terminar merge", "green")

    def _merge_abort(self):
        s = self._repo()
        if not s:
            return
        if not self._confirmed("merge_abort"):
            return self._msg("ghrepo", "Vuelve a pulsar para cancelar el merge (se descarta lo resuelto)", "orange")
        self.core.git.op(s, "merge_abort", lambda ok, msg: self._msg("ghrepo", msg, "green" if ok else "red"))

    def _merge_finish(self):
        s = self._repo()
        if s:
            self._msg("ghrepo", "Terminando el merge (puede pedir la contraseña de tu llave GPG)…")
            self.core.git.op(s, "merge_finish", lambda ok, msg: self._msg("ghrepo", msg, "green" if ok else "red"))

    def _do_switch(self):
        s, branch = self._repo(), self.rp_branch.get_active_id()
        if not s or not branch:
            return
        if changes(s):
            return self._msg("ghrepo", "Haz commit o descarta los cambios antes de cambiar de rama", "orange")
        remote = next((b["remote"] for b in self.rp_branches if b["name"] == branch), False)
        self._msg("ghrepo", f"Cambiando a {branch}…")

        def done(ok, msg):
            self._msg("ghrepo", msg, "green" if ok else "red")
            if ok:
                self._open_repo()          # la lista de ramas cambió (la actual ya no aparece)
        self.core.git.op(s, "switch", done, branch=branch, remote=remote)

    def _do_pr(self):
        s = self._repo()
        head, base = self.rp_from.get_active_id(), self.rp_to.get_active_id()
        if not s or not head or not base:
            return self._msg("ghrepo", "Elige la rama de origen y la de destino", "orange")
        if not s.get("slug"):
            return self._msg("ghrepo", "Este repo no tiene remoto en GitHub", "orange")
        problem = pr_check(s["path"], base, head)
        if problem:
            return self._msg("ghrepo", problem, "orange")
        self._msg("ghrepo", f"Abriendo GitHub: PR de {head} a {base}", "green")
        url = compare_url(s["slug"], base, head)
        self._collapse_then(lambda: open_web(url))

    def _stash(self, kind, st):
        s = self._repo()
        if not s:
            return
        if kind == "stash_drop" and not self._confirmed(f"drop:{st['sha']}"):
            return self._msg("ghrepo", "Vuelve a pulsar para borrar el stash", "orange")
        self._msg("ghrepo", "Aplicando stash…" if kind == "stash_pop" else "Borrando stash…")
        self.core.git.op(s, kind, lambda ok, msg: self._msg("ghrepo", msg, "green" if ok else "red"),
                         ref=st["ref"], sha=st["sha"])

    def _sync(self, op):
        s = self._repo()
        if not s:
            return
        self._msg("ghrepo", "Bajando commits…" if op == "pull" else "Subiendo commits…")

        def done(ok, last):
            if ok:
                self._msg("ghrepo", "Bajados: el repo está al día" if op == "pull" else "Subidos al remoto", "green")
            else:
                self._msg("ghrepo", f"No se pudo: {last}", "red")
        self.core.git.sync(s, op, done)

    # ── una PR: ver, aprobar, pedir cambios, fusionar o cerrar ──
    def _show_pr(self, p):
        self.sel_pr, self.pr_data, self.pr_err, self._confirm = p, None, "", None
        self._msgs.pop("ghpr", None)
        self.go("ghpr")

    def _open_pr(self):
        p = self.sel_pr
        if not p:
            return

        def got(d, err):
            if p is self.sel_pr:
                self.pr_data, self.pr_err = d, err
                self.core.changed("github")
        self.core.github.pr_detail(p, got)

    def _build_pr(self):
        box = self._page("Pull request", back="github")
        self.pr_title = label("", "subtitle", lines=2)
        self.pr_sub = label("", "dim small", lines=2)
        box.pack_start(self.pr_title, False, False, 0)
        box.pack_start(self.pr_sub, False, False, 0)
        self.pr_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.pack_start(self._scroller(self.pr_list, 230), False, False, 0)
        self.pr_entry = Gtk.Entry(hexpand=True, placeholder_text="Comentario (obligatorio para pedir cambios)")
        box.pack_start(self.pr_entry, False, False, 0)
        self.pr_msg = label("", "small", lines=3)
        box.pack_start(self.pr_msg, False, False, 0)
        row = Gtk.Box(spacing=6)
        self.pr_btns = {}
        for key, txt, cls in (("approve", "Aprobar", "chip"), ("changes", "Pedir cambios", "chip"),
                              ("merge", "Fusionar", "chip"), ("close", "Cerrar", "chip danger")):
            b = button(cls, cb=lambda k=key: self._pr_do(k), text=txt)
            self.pr_btns[key] = (b, txt)
            row.pack_start(b, False, False, 0)
        row.pack_end(button("ctrl", icon("web-browser-symbolic"), lambda: self._collapse_then(
            lambda: self.core.open_github(self.sel_pr["url"])), "Abrir en GitHub"), False, False, 0)
        box.pack_start(row, False, False, 0)
        return box

    def _fill_pr(self):
        p, d = self.sel_pr, self.pr_data
        clear(self.pr_list)
        if not p:
            return
        self.pr_title.set_text(p["title"])
        sub, acc = GitHub.describe(p, p["author"] == self.core.github.login)
        self.pr_sub.set_text(sub)
        set_accent(self.pr_sub, acc)
        login = self.core.github.login
        is_open = not p.get("merged") and (not d or d.get("state") == "OPEN")
        if d:
            ci = {"SUCCESS": "✓ CI", "FAILURE": "✗ CI", "PENDING": "● CI en curso"}.get(d["ci"], "sin CI")
            mg = {"MERGEABLE": "se puede fusionar", "CONFLICTING": "tiene conflictos"}.get(d.get("mergeable"), "")
            stats = (f"{d.get('headRefName')} → {d.get('baseRefName')} · +{d.get('additions', 0)} "
                     f"−{d.get('deletions', 0)} · {d.get('changedFiles', 0)} archivos · {ci}" + (f" · {mg}" if mg else ""))
            st = label(stats, "small", lines=2)
            set_accent(st, "red" if d["ci"] == "FAILURE" or d.get("mergeable") == "CONFLICTING" else None)
            self.pr_list.pack_start(st, False, False, 0)
            body = (d.get("body") or "").strip()
            self.pr_list.pack_start(label(body[:500] + ("…" if len(body) > 500 else "") if body else "Sin descripción",
                                          "dim", lines=8), False, False, 0)
            commits = d.get("commits") or []
            if commits:
                self.pr_list.pack_start(label(f"COMMITS · {len(commits)}", "section"), False, False, 0)
            for cm in commits[-6:][::-1]:
                who = ", ".join(a.get("login") or a.get("name", "") for a in cm.get("authors") or []) or "?"
                when = ago_long(iso_ts(cm.get("committedDate"))) if cm.get("committedDate") else ""
                self.pr_list.pack_start(self._row("go-up-symbolic", cm.get("messageHeadline", ""),
                                                  " · ".join(x for x in (who, when, cm.get("oid", "")[:7]) if x)),
                                        False, False, 0)
        else:
            self.pr_list.pack_start(label(self.pr_err or "Cargando…", "dim"), False, False, 0)
        self.pr_list.show_all()
        own = p["author"] == login
        show = {"approve": is_open and not own, "changes": is_open and not own, "merge": is_open, "close": is_open}
        for key, (b, txt) in self.pr_btns.items():
            b.set_visible(show[key])
            b.set_sensitive(self.pr_busy is None)
            confirming = self._confirm == key
            set_class(b, "confirm", confirming)
            b.set_label("¿Seguro?" if confirming else ("…" if self.pr_busy == key else txt))
        self.pr_entry.set_visible(is_open)
        self._show_msg("ghpr", self.pr_msg)

    def _pr_do(self, action):
        p = self.sel_pr
        if not p or self.pr_busy:
            return
        body = self.pr_entry.get_text().strip()
        if action == "changes" and not body:
            return self._msg("ghpr", "Escribe qué cambios pides", "orange")
        if action in ("merge", "close") and not self._confirmed(action):
            return self._msg("ghpr", "Vuelve a pulsar para " + ("fusionar" if action == "merge" else "cerrar la PR"),
                             "orange")
        self.pr_busy = action
        self._msg("ghpr", "Enviando…")

        def done(ok, msg):
            self.pr_busy = None
            if ok:
                self.pr_entry.set_text("")
                self.core.show_event(2.5, kind="pill", icon=GITHUB_APP, accent="green",
                                     text=f"{msg} · {p['repo']}#{p['num']}")
                self._open_pr()
            self._msg("ghpr", msg if ok else f"No se pudo: {msg}", "green" if ok else "red")
        self.core.github.pr_action(p, action, body, done)

    def _gh_section(self, key, title, total, today=0, top=True):
        return self._fold(self.gh_list, key, title, total, today, self._fill_github, top)

    # ── Despliegues (Railway u otras plataformas que reportan a GitHub) ──
    def _deploy_row(self, ic, d, sub, acc):
        return self._row(ic, d["name"], sub, lambda: self._collapse_then(lambda: open_web(d["url"])),
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
