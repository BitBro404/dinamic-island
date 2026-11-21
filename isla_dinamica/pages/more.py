"""Página «Más»: herramientas extra y activar o desactivar funciones."""
from ..common import *  # noqa: F401,F403
from .registry import FEATURES, page


class MorePage:
    PAGES = {
        "more": page("_build_more", "_fill_more", ("features",)),
    }

    @classmethod
    def _tools(cls):
        """Accesos declarados por las páginas (TOOLS = (tool(...),)), en orden."""
        out = []
        for klass in reversed(cls.__mro__):
            out.extend(klass.__dict__.get("TOOLS", ()))
        return out

    def _build_more(self):
        box = self._page("Más")
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        self.more_tools = []
        tools = self._tools()
        if tools:
            body.pack_start(label("HERRAMIENTAS", "section"), False, False, 0)
            grid = Gtk.Grid(column_spacing=5, row_spacing=5, column_homogeneous=True, halign=Gtk.Align.START)
            for i, t in enumerate(tools):
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
                inner.pack_start(icon(t["icon"], px=18), False, False, 0)
                inner.pack_start(label(t["text"], "time-small", xalign=0.5, ellipsize=False), False, False, 0)
                b = button("act", inner, lambda pg=t["page"]: self.go(pg), t["tip"])
                b.set_size_request(76, -1)
                grid.attach(b, i % 5, i // 5, 1, 1)
                self.more_tools.append((b, t))
            body.pack_start(grid, False, False, 0)

        head = label("FUNCIONES", "section")
        head.set_margin_top(6 if tools else 0)
        body.pack_start(head, False, False, 0)
        self.more_switches = {}
        for f in FEATURES:
            row = Gtk.Box(spacing=10)
            txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            txt.pack_start(label(f["title"], "subtitle"), False, False, 0)
            txt.pack_start(label(f["desc"], "dim small", lines=2), False, False, 0)
            row.pack_start(txt, True, True, 0)
            sw = self._switch(lambda on, k=f["key"]: self.core.set_feature(k, on))
            sw.set_valign(Gtk.Align.CENTER)
            row.pack_end(sw, False, False, 0)
            self.more_switches[f["key"]] = sw
            body.pack_start(row, False, False, 0)
        box.pack_start(self._scroller(body, 420), False, False, 0)
        return box

    def _fill_more(self):
        for key, sw in self.more_switches.items():
            self._set_switch(sw, self.core.feature(key))
        for b, t in self.more_tools:
            b.set_visible(not t["feature"] or self.core.feature(t["feature"]))
