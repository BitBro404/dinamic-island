"""Descargas: en curso (con velocidad) y las últimas terminadas."""
from ..common import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import feature, page, tool

feature("downloads", "Descargas", "Progreso de las descargas de Chrome en la píldora y aviso al terminar")


class DownloadsPage:
    PAGES = {
        "downloads": page("_build_downloads", "_fill_downloads", ("downloads",)),
    }
    TOOLS = (tool("folder-download-symbolic", "Descargas", "Descargas en curso y recientes", "downloads",
                  feature="downloads"),)

    def _build_downloads(self):
        box = self._page("Descargas", button("chip", cb=lambda: self._collapse_then(
            lambda: open_uri(Gio.File.new_for_path(self.core.downloads.dir).get_uri())), text="Abrir carpeta"))
        self.dl_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.dl_list, 400), False, False, 0)
        return box

    @staticmethod
    def _show_in_folder(path):
        try:
            Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
                "org.freedesktop.FileManager1", "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1",
                "ShowItems", GLib.Variant("(ass)", ([Gio.File.new_for_path(path).get_uri()], "")),
                None, 0, 2000, None)
        except GLib.Error:
            open_uri(Gio.File.new_for_path(os.path.dirname(path)).get_uri())

    def _fill_downloads(self):
        dl = self.core.downloads
        clear(self.dl_list)
        if dl.active:
            self.dl_list.pack_start(label(f"EN CURSO · {len(dl.active)}", "section"), False, False, 0)
            for d in sorted(dl.active.values(), key=lambda d: -d["started"]):
                sub = f"{fmt_size(d['size'])} · {fmt_size(int(d['speed']))}/s" if d["speed"] else fmt_size(d["size"])
                self.dl_list.pack_start(self._row("folder-download-symbolic", d["name"], sub, sub_accent="blue"),
                                        False, False, 0)
        if dl.stalled:
            head = label("DETENIDAS", "section")
            head.set_margin_top(6 if dl.active else 0)
            self.dl_list.pack_start(head, False, False, 0)
            for s in dl.stalled:
                extra = [button("ctrl", icon("folder-open-symbolic"), lambda p=s["path"]: self._collapse_then(
                    lambda: self._show_in_folder(p)), "Mostrar en la carpeta")]
                self.dl_list.pack_start(self._row("folder-download-symbolic", s["name"],
                                                  f"{fmt_size(s['size'])} · sin avanzar desde {ago_long(s['mtime'])}",
                                                  None, extra), False, False, 0)
        head = label("RECIENTES", "section")
        head.set_margin_top(6 if dl.active or dl.stalled else 0)
        self.dl_list.pack_start(head, False, False, 0)
        for f in dl.recent:
            gicon = Gio.content_type_get_symbolic_icon(Gio.content_type_guess(f["name"], None)[0])
            names = gicon.get_names() if isinstance(gicon, Gio.ThemedIcon) else []
            extra = [button("ctrl", icon("folder-open-symbolic"), lambda p=f["path"]: self._collapse_then(
                lambda: self._show_in_folder(p)), "Mostrar en la carpeta")]
            self.dl_list.pack_start(self._row(names[0] if names else "text-x-generic-symbolic", f["name"],
                                              f"{fmt_size(f['size'])} · {ago_long(f['mtime'])}",
                                              lambda p=f["path"]: self._collapse_then(
                                                  lambda: open_uri(Gio.File.new_for_path(p).get_uri())),
                                              extra), False, False, 0)
        if not dl.recent:
            self._empty(self.dl_list, "La carpeta de descargas está vacía")
        self.dl_list.show_all()
