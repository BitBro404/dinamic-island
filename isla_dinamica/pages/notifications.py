"""Lista de notificaciones."""
from gi.repository import Gtk

from ..ui.gtk import button, clear, icon
from ..util.fmt import ago
from .base import Page
from .registry import page


class NotificationsPage(Page):
    """Avisos: historial de notificaciones del escritorio."""
    PAGES = {
        "notifs": page("_build_notifs", "_fill_notifs", ("notifs",), "_open_notifs"),
    }

    def _build_notifs(self):
        def clear_all():
            self.core.notifs.clear()
            self.core.unread = 0
            self.core.changed("notifs")
        box = self._page("Notificaciones", button("chip danger", cb=clear_all, text="Borrar"))
        self.n_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.n_list, 290), False, False, 0)
        foot = Gtk.Box()
        foot.pack_end(button("chip", cb=self.core.notif.open_center, text="Centro de notificaciones"),
                      False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _fill_notifs(self):
        c = self.core
        clear(self.n_list)
        for n in c.notifs:
            title = n["summary"] or n["app"]
            sub = f"{n['app']} · {ago(n['time'])}" + (f" — {n['body']}" if n["body"] else "")
            rm = button("ctrl", icon("window-close-symbolic"), lambda n=n: self._remove_notif(n), "Quitar")
            self.n_list.pack_start(self._row(n["icon"], title, sub,
                                             lambda n=n: (self._set_hover(False), c.open_notif(n)),
                                             [rm], pixbuf=n["pixbuf"]), False, False, 0)
        if not c.notifs:
            self._empty(self.n_list, "No hay notificaciones")
        self.n_list.show_all()

    def _remove_notif(self, n):
        if n in self.core.notifs:
            self.core.notifs.remove(n)
            self.core.changed("notifs")

    def _open_notifs(self):
        if self.core.unread:
            self.core.unread = 0
            self.core.changed()
