"""Historial del portapapeles."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import page


class ClipboardPage:
    PAGES = {
        "clip": page("_build_clip", "_fill_clip", ("clip",)),
    }

    def _build_clip(self):
        box = self._page("Portapapeles", button("chip danger", cb=self.core.clip.clear, text="Borrar todo"))
        self.p_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.p_list, 280), False, False, 0)
        return box

    def _fill_clip(self):
        c = self.core
        clear(self.p_list)
        for t in c.clip.items:
            one = re.sub(r"\s+", " ", t.strip())[:160]
            lines = t.count("\n") + 1
            sub = f"{lines} líneas · {len(t)} caracteres" if lines > 1 else f"{len(t)} caracteres"
            rm = button("ctrl", icon("window-close-symbolic"), lambda t=t: c.clip.remove(t), "Quitar")
            self.p_list.pack_start(self._row(None, one, sub, lambda t=t: self._copy(t), [rm]), False, False, 0)
        if not c.clip.items:
            self._empty(self.p_list, "Copia algo y aparecerá aquí")
        self.p_list.show_all()
