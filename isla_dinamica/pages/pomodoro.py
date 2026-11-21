"""Pomodoro."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import page


class PomodoroPage:
    PAGES = {
        "pomo": page("_build_pomo"),
    }

    def _build_pomo(self):
        box = self._page("Pomodoro", button("chip", cb=self.core.pomo.reset, text="Reiniciar"))
        self.po_phase = label("", "subtitle", xalign=0.5)
        self.po_time = label("", "huge", xalign=0.5, ellipsize=False)
        self.po_cycle = label("", "dim", xalign=0.5)
        for w in (self.po_phase, self.po_time, self.po_cycle):
            box.pack_start(w, False, False, 0)
        ctr = Gtk.Box(spacing=16, halign=Gtk.Align.CENTER)
        self.po_play = icon("media-playback-start-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        ctr.pack_start(button("ctrl", self.po_play, self.core.pomo.toggle, "Iniciar / pausar"), False, False, 0)
        ctr.pack_start(button("ctrl", icon("media-skip-forward-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                              self.core.pomo.skip, "Saltar a la siguiente fase"), False, False, 0)
        box.pack_start(ctr, False, False, 0)

        grid = Gtk.Grid(row_spacing=6, column_spacing=10)
        conf = self.core.pomo.conf
        for r, (key, text, lo, hi) in enumerate((("work", "Enfoque (min)", 1, 180),
                                                 ("short", "Descanso corto (min)", 1, 60),
                                                 ("long", "Descanso largo (min)", 1, 120),
                                                 ("every", "Descanso largo cada (sesiones)", 2, 12))):
            lb = label(text, "artist", xalign=0.0)
            lb.set_hexpand(True)
            spin = Gtk.SpinButton.new_with_range(lo, hi, 1)
            spin.set_value(conf[key])
            spin.connect("value-changed", lambda s, k=key: self.core.pomo.set_conf(k, int(s.get_value())))
            grid.attach(lb, 0, r, 1, 1)
            grid.attach(spin, 1, r, 1, 1)
        auto_lb = label("Empezar la siguiente fase sola", "artist", xalign=0.0)
        auto = Gtk.Switch(active=bool(conf["auto"]), halign=Gtk.Align.END)
        auto.connect("notify::active", lambda s, _p: self.core.pomo.set_conf("auto", s.get_active()))
        grid.attach(auto_lb, 0, 4, 1, 1)
        grid.attach(auto, 1, 4, 1, 1)
        box.pack_start(grid, False, False, 0)
        return box
