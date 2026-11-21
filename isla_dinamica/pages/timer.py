"""Temporizador."""
from gi.repository import Gtk

from ..ui.gtk import button, label, set_accent
from ..util.fmt import fmt_secs
from .base import Page
from .registry import page


class TimerPage(Page):
    """Alarma: temporizador de cuenta atrás."""
    PAGES = {
        "timer": page("_build_timer"),
    }

    def _build_timer(self):
        self.t_stop = button("chip danger", cb=self.core.stop_timer, text="Detener")
        self.t_stop.set_no_show_all(True)
        self.t_stop.get_child().show()
        box = self._page("Temporizador", self.t_stop)
        self.t_big = label("", "huge", xalign=0.5, ellipsize=False)
        box.pack_start(self.t_big, False, False, 0)
        chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=5,
                            min_children_per_line=5, homogeneous=True, column_spacing=6, row_spacing=6)
        for m in (1, 3, 5, 10, 15, 25, 30, 45, 60, 90):
            chips.add(button("chip", cb=lambda m=m: self.core.start_timer(m * 60), text=f"{m} min"))
        box.pack_start(chips, False, False, 0)
        return box

    def live(self, c, m, playing, timer_left):
        """Cuenta atrás del temporizador, cada segundo."""
        self.t_big.set_text(fmt_secs(timer_left) if timer_left is not None else "—")
        set_accent(self.t_big, "orange" if timer_left is not None else None)
        self.t_stop.set_visible(timer_left is not None)
