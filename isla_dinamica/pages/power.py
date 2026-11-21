"""Bloquear, suspender, reiniciar y apagar."""
from gi.repository import GLib, Gtk

from ..ui.gtk import button, icon, label, set_class
from .base import Page
from .registry import page


class PowerPage(Page):
    """Energía: bloquear, cerrar sesión, suspender, reiniciar y apagar (las peligrosas piden un segundo clic)."""
    PAGES = {
        "power": page("_build_power"),
    }

    def _build_power(self):
        box = self._page("Energía")
        self._confirm = None        # acción que espera un segundo clic para confirmarse
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

    def live(self, c, m, playing, timer_left):
        """Botones en modo «¿Seguro?» mientras se espera la confirmación."""
        for key, (btn, lb, txt) in self.pw_buttons.items():
            confirming = self._confirm == key
            set_class(btn, "confirm", confirming)
            lb.set_text("¿Seguro?" if confirming else txt)
        if not self._confirm:
            self.pw_hint.set_text("")

    def on_collapse(self):
        self._confirm = None

    def waiting(self):
        return bool(self._confirm)
