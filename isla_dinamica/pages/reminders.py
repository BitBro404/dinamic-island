"""Recordatorios: escribe «qué y cuándo» y la isla te avisa."""
from ..common import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from ..services.reminders import parse, when
from .registry import feature, page, tool

feature("reminders", "Recordatorios", "Avisos a la hora que digas: «llamar a Ana en 20 min», «daily a las 9:30»")

QUICK = (("5 min", 5), ("15 min", 15), ("30 min", 30), ("1 h", 60), ("2 h", 120), ("Mañana", None))


class RemindersPage:
    PAGES = {
        "reminders": page("_build_reminders", "_fill_reminders", ("reminders",), "_open_reminders"),
    }
    TOOLS = (tool("alarm-symbolic", "Recordar", "Recordatorios", "reminders", feature="reminders"),)

    def _build_reminders(self):
        box = self._page("Recordatorios")
        self.rm_entry = Gtk.Entry(hexpand=True, placeholder_text="¿Qué te recuerdo? «llamar a Ana en 20 min»")
        self.rm_entry.connect("activate", lambda *_: self._rm_add())
        self.rm_entry.connect("changed", lambda *_: self._rm_hint())
        box.pack_start(self.rm_entry, False, False, 0)
        self.rm_hint = label("Escribe la hora en la frase o elige una abajo", "dim small")
        box.pack_start(self.rm_hint, False, False, 0)
        chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6,
                            min_children_per_line=6, homogeneous=True, column_spacing=6, row_spacing=6)
        for text, mins in QUICK:
            chips.add(button("chip", cb=lambda m=mins: self._rm_add(m if m else "tomorrow"), text=text))
        box.pack_start(chips, False, False, 0)
        self.rm_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.rm_list, 300), False, False, 0)
        return box

    def _open_reminders(self):
        GLib.idle_add(lambda: (self.rm_entry.grab_focus(), False)[1])

    def _rm_hint(self):
        txt = self.rm_entry.get_text().strip()
        _clean, at = parse(txt) if txt else ("", None)
        set_accent(self.rm_hint, "blue" if at else None)
        self.rm_hint.set_text(f"Te aviso {when(at)}" if at else
                              "Escribe la hora en la frase o elige una abajo" if not txt else
                              "Sin hora: elige una abajo o Enter para dentro de 30 min")

    def _rm_add(self, mins=None):
        txt = self.rm_entry.get_text().strip()
        if not txt:
            set_accent(self.rm_hint, "orange")
            self.rm_hint.set_text("Primero escribe qué te recuerdo")
            self.rm_entry.grab_focus()
            return
        at = None
        if mins == "tomorrow":
            lt = time.localtime()
            at = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, 9, 0, 0, 0, 0, -1))
        elif mins:
            at = time.time() + mins * 60
        r = self.core.reminders.add(txt, at)
        if r:
            self.rm_entry.set_text("")
            set_accent(self.rm_hint, "green")
            self.rm_hint.set_text(f"Listo: «{r['text']}» {when(r['at'])}")

    def _fill_reminders(self):
        clear(self.rm_list)
        items = self.core.reminders.items
        if items:
            self.rm_list.pack_start(label(f"PENDIENTES · {len(items)}", "section"), False, False, 0)
        for r in items:
            soon = r["at"] - time.time() < 600
            extra = [button("ctrl", icon("edit-delete-symbolic"), lambda i=r["id"]: self.core.reminders.remove(i),
                            "Borrar")]
            self.rm_list.pack_start(self._row("alarm-symbolic", r["text"], when(r["at"]), extra=extra,
                                              sub_accent="orange" if soon else None), False, False, 0)
        if not items:
            self._empty(self.rm_list, "No tienes recordatorios")
        self.rm_list.show_all()
