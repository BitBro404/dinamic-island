"""Bloquear, suspender, reiniciar y apagar."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import page


class PowerPage:
    PAGES = {
        "power": page("_build_power"),
    }

    def _build_power(self):
        box = self._page("Energía")
        row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        p = self.core.power
        self.pw_buttons = {}
        for key, ic, txt, cb, confirm in (("lock", "system-lock-screen-symbolic", "Bloquear", p.lock, False),
                                          ("logout", "system-log-out-symbolic", "Salir", p.logout, True),
                                          ("suspend", "system-suspend-symbolic", "Suspender", p.suspend, False),
                                          ("reboot", "system-reboot-symbolic", "Reiniciar", p.reboot, True),
                                          ("off", "system-shutdown-symbolic", "Apagar", p.poweroff, True)):
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            inner.pack_start(icon(ic, px=22), False, False, 0)
            lb = label(txt, "small", xalign=0.5, ellipsize=False)
            inner.pack_start(lb, False, False, 0)
            b = button("big", inner, lambda k=key, cb=cb, c=confirm: self._power(k, cb, c))
            self.pw_buttons[key] = (b, lb, txt)
            row.pack_start(b, False, False, 0)
        box.pack_start(row, False, False, 0)
        self.pw_hint = label("", "dim small", xalign=0.5)
        box.pack_start(self.pw_hint, False, False, 0)
        return box

    def _power(self, key, cb, confirm):
        if confirm and self._confirm != key:
            self._confirm = key
            self.pw_hint.set_text("Vuelve a pulsar para confirmar")
            GLib.timeout_add(8000, self._reset_confirm, key)
            self.refresh()
            return
        self._confirm = None
        self._set_hover(False)
        cb()

    def _reset_confirm(self, key):
        if self._confirm == key:
            self._confirm = None
            self.refresh()
        return False
