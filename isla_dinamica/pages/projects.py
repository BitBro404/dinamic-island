"""Proyectos: estado git de los repos vigilados y las carpetas que se vigilan."""
from ..common import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from ..services.gitwatch import changes, expand, short, summary
from .registry import feature, page, tool

feature("git", "Proyectos (git)", "Rama, cambios sin commit, commits por subir o bajar y stashes de tus repos")


def open_in_editor(path):
    for ed in ("code", "cursor", "codium", "subl"):
        if GLib.find_program_in_path(ed):
            subprocess.Popen([ed, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return
    open_uri(Gio.File.new_for_path(path).get_uri())


class ProjectsPage:
    PAGES = {
        "projects": page("_build_projects", "_fill_projects", ("git",), "_open_projects"),
    }
    TOOLS = (tool("folder-symbolic", "Proyectos", "Estado git de tus repos", "projects", feature="git"),)

    def _build_projects(self):
        box = self._page("Proyectos", button("ctrl", icon("view-refresh-symbolic"),
                                             lambda: self.core.git.refresh(fetch=True),
                                             "Actualizar (incluye git fetch)"))
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.pj_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        body.pack_start(self.pj_list, False, False, 0)

        head = label("CARPETAS VIGILADAS", "section")
        head.set_margin_top(8)
        body.pack_start(head, False, False, 0)
        self.pj_folders = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        body.pack_start(self.pj_folders, False, False, 0)
        row = Gtk.Box(spacing=6, margin_top=4)
        self.pj_entry = Gtk.Entry(hexpand=True, placeholder_text="Agregar carpeta, p. ej. ~/proyectos")
        self.pj_entry.connect("activate", lambda *_: self._pj_add())
        row.pack_start(self.pj_entry, True, True, 0)
        row.pack_start(button("ctrl", icon("folder-open-symbolic"), self._pj_choose, "Elegir carpeta…"),
                       False, False, 0)
        row.pack_start(button("chip", cb=self._pj_add, text="Agregar"), False, False, 0)
        body.pack_start(row, False, False, 0)
        self.pj_msg = label("Puedes agregar un repo o una carpeta que contenga varios", "dim small")
        body.pack_start(self.pj_msg, False, False, 0)
        box.pack_start(self._scroller(body, 470), False, False, 0)
        return box

    def _open_projects(self):
        if not self.core.git.updated or time.time() - self.core.git.updated > 20:
            self.core.git.refresh()

    def _pj_msg(self, text, accent=None):
        self.pj_msg.set_text(text)
        set_accent(self.pj_msg, accent)

    def _pj_add(self, path=None):
        path = path or self.pj_entry.get_text().strip()
        if not path:
            self._pj_msg("Escribe la ruta de la carpeta o elígela con el botón", "orange")
            return
        err = self.core.git.add_folder(path)
        if err:
            self._pj_msg(f"{err}: {short(expand(path))}", "orange")
        else:
            self.pj_entry.set_text("")
            self._pj_msg(f"Vigilando {short(expand(path))}", "green")

    def _pj_choose(self):
        dlg = Gtk.FileChooserNative.new("Carpeta a vigilar", None, Gtk.FileChooserAction.SELECT_FOLDER,
                                        "Vigilar", "Cancelar")
        dlg.set_current_folder(os.path.expanduser("~/Documentos"))
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self._pj_add(dlg.get_filename())
        dlg.destroy()

    def _fill_projects(self):
        g = self.core.git
        clear(self.pj_list)
        if g.repos:
            dirty = sum(1 for s in g.repos if not s.get("error") and summary(s) != "al día")
            self.pj_list.pack_start(label(f"REPOS · {len(g.repos)}" + (f" · {dirty} con pendientes" if dirty else ""),
                                          "section"), False, False, 0)
        for s in g.repos:
            if s.get("error"):
                self.pj_list.pack_start(self._row("dialog-warning-symbolic", s["name"], s["error"],
                                                  sub_accent="red"), False, False, 0)
                continue
            text = summary(s)
            accent = ("red" if s["conflicts"] else "blue" if s["behind"] else
                      "orange" if changes(s) or s["ahead"] else None)
            sub = f"{s['branch'] or '?'} · {text}"
            if s["last_ts"]:
                sub += f" · último commit {ago_long(s['last_ts'])}"
            extra = [button("ctrl", icon("folder-open-symbolic"), lambda p=s["path"]: self._collapse_then(
                lambda: open_uri(Gio.File.new_for_path(p).get_uri())), "Abrir carpeta")]
            self.pj_list.pack_start(self._row("emblem-ok-symbolic" if text == "al día" else "document-edit-symbolic",
                                              s["name"], sub, lambda p=s["path"]: self._collapse_then(
                                                  lambda: open_in_editor(p)), extra, sub_accent=accent),
                                    False, False, 0)
        if not g.repos:
            self._empty(self.pj_list, "Buscando repos…" if not g.updated else "No hay repos en las carpetas vigiladas")
        clear(self.pj_folders)
        for f in g.folders:
            extra = [button("ctrl", icon("list-remove-symbolic"), lambda p=f: self.core.git.remove_folder(p),
                            "Dejar de vigilar")]
            n = sum(1 for s in g.repos if s["path"] == expand(f) or s["path"].startswith(expand(f) + os.sep))
            self.pj_folders.pack_start(self._row("folder-symbolic", f, f"{n} repo{'s' if n != 1 else ''}",
                                                 extra=extra), False, False, 0)
        self.pj_list.show_all()
        self.pj_folders.show_all()
