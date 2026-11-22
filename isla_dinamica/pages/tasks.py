"""Tareas en curso: todo lo que la isla tiene en marcha (lo de la píldora y todas las burbujas, también las
que no caben). Se llega con la burbuja «+N»; cada fila abre la página de su actividad."""
from gi.repository import Gtk

from ..ui.bubbles import activities
from ..ui.gtk import button, clear, icon, label
from .base import Page
from .registry import feature, page


feature("bub_more", "Burbuja de tareas",
        "Si hay más actividades de las que caben, muestra una burbuja «+N» que abre la lista de tareas en curso")

FALLBACK_ICON = "audio-x-generic-symbolic"   # la música usa la carátula en la burbuja y no trae icono


def task_rows(acts):
    """Filas (clave, icono, título, estado, página) en el orden de prioridad de las actividades.
    Bluetooth no lleva `label`: el título es el nombre del dispositivo (el tip hasta « · »)."""
    rows = []
    for a in acts:
        tip = a.get("tip") or ""
        title = a.get("label") or tip.split(" · ")[0] or a["key"]
        rows.append((a["key"], a.get("icon") or FALLBACK_ICON, title, tip, a["page"]))
    return rows


class TasksPage(Page):
    """Lista de las actividades en curso; se actualiza cada segundo mientras está abierta."""
    PAGES = {
        "tasks": page("_build_tasks"),
    }

    def _build_tasks(self):
        self._keys = None
        self._subs = {}
        box = self._page("Tareas en curso")
        self.tk_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.tk_list), False, False, 0)
        return box

    def live(self, c, m, playing, timer_left):
        if self.host.page != "tasks":
            self._keys = None          # al volver se redibuja con lo que haya entonces
            return
        rows = task_rows(activities(c, m, playing, timer_left))
        keys = tuple(r[0] for r in rows)
        if keys != self._keys:         # solo se reconstruye si cambia qué hay en curso (sin parpadeo)
            self._keys = keys
            self._fill(rows)
        for key, _ic, _title, sub, _page in rows:
            lb = self._subs.get(key)
            if lb is not None and lb.get_text() != sub:
                lb.set_text(sub)

    def _fill(self, rows):
        clear(self.tk_list)
        self._subs = {}
        if not rows:
            self._empty(self.tk_list, "No hay tareas en curso")
        for key, ic, title, sub, target in rows:
            inner = Gtk.Box(spacing=10)
            inner.pack_start(icon(ic, px=24), False, False, 0)
            txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            txt.pack_start(label(title, "subtitle"), False, False, 0)
            self._subs[key] = label(sub, "dim")
            txt.pack_start(self._subs[key], False, False, 0)
            inner.pack_start(txt, True, True, 0)
            self.tk_list.pack_start(button("row", inner, lambda t=target: self.go(t), "Abrir"), False, False, 0)
        self.tk_list.show_all()
