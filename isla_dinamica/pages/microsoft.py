"""Teams y correo de Outlook (a partir de sus notificaciones)."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import feature, page

feature("ms", "Teams y correo", "Mensajes de Teams y Outlook a partir de sus notificaciones")


class MicrosoftPage:
    PAGES = {
        "ms": page("_build_ms", "_fill_ms", ("ms", "notifs"), "_open_ms"),
    }

    # ── Microsoft: Teams y Outlook (a partir de sus notificaciones) ──
    def _build_ms(self):
        box = self._page("Teams y correo")
        self.ms_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.ms_list, 400), False, False, 0)
        foot = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        foot.pack_start(button("chip", cb=lambda: self._collapse_then(self.core.open_teams), text="Abrir Teams"),
                        False, False, 0)
        foot.pack_start(button("chip", cb=lambda: self._collapse_then(lambda: open_uri(OUTLOOK_URL)),
                               text="Abrir Outlook"), False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _fill_ms(self):
        c = self.core
        clear(self.ms_list)
        for kind, title, empty in (
                ("teams", "TEAMS", "Sin mensajes. Aparecen aquí cuando Teams (abierto) te envía una notificación."),
                ("outlook", "CORREO · OUTLOOK", "Sin correos. Aparecen aquí cuando Outlook web (abierto en "
                                                "Chrome) avisa de un correo nuevo.")):
            items = [n for n in c.notifs if n.get("ms") == kind][:8]
            head = label(f"{title} · {len(items)}", "section")
            head.set_margin_top(6)
            self.ms_list.pack_start(head, False, False, 0)
            for n in items:
                sub = (n["body"] + " · " if n["body"] else "") + ago(n["time"])
                self.ms_list.pack_start(self._row(n["icon"], n["summary"] or n["app"], sub,
                                                  lambda n=n: self._collapse_then(lambda: c.open_notif(n)),
                                                  pixbuf=n["pixbuf"]), False, False, 0)
            if not items:
                self._empty(self.ms_list, empty)
        self.ms_list.show_all()

    def _open_ms(self):
        self.core.ms_unread = {"teams": 0, "outlook": 0}
        self.core.changed("ms")
