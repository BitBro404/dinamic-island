"""Sensor de presencia: bloquear y apagar la pantalla si no hay nadie frente a la cámara."""
import threading
import time

from gi.repository import GdkPixbuf, GLib, Gtk

from ..services.presence import FaceDetector, presence_label
from ..ui.gtk import button, label, set_accent, set_class
from ..ui.widgets.art import Art
from ..util.fmt import ago, hm
from .base import Page
from .registry import feature, page, tool

feature("presence", "Presencia (cámara)",
        "Si no hay nadie frente a la cámara ni usas el teclado o el ratón, bloquea y apaga la pantalla")

_DAYS = "LMXJVSD"
_ACCENT = {"present": "green", "watching": None, "active": None, "warning": "orange", "locked": "red", "lock_failed": "red",
           "no_cv": "orange", "off_hours": None, "paused": "blue", "off": None, "other": "orange",
           "confirm": "blue"}


def _identity_text(enrolled, samples):
    """Resumen de la galería; `samples` excluye la plantilla ancla."""
    if not enrolled:
        return "Sin rostro registrado: cualquier cara cuenta como presente", False
    return f"Rostro registrado · {samples} muestra" + ("s" if samples != 1 else ""), True


def _identity_hint(state):
    if state == "other":
        return "Hay otra persona delante: si sigue sin haber input, se bloqueará la pantalla"
    if state == "confirm":
        return "Confirma si eras tú: mientras esperamos no se bloquea y la foto se descarta"
    return ""


def _frame_pixbuf(frame):
    """Imagen de la revisión en memoria; nunca se escribe en disco. Foto inválida → None."""
    if frame is None:
        return None
    try:
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ch = rgb.shape
        return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgb.tobytes()),
                                               GdkPixbuf.Colorspace.RGB, False, 8, w, h, w * 3)
    except Exception:
        return None


class PresencePage(Page):
    """Presencia: estado del sensor de cámara, horario y opciones de bloqueo automático."""
    PAGES = {
        "presence": page("_build_presence", "_fill_presence", ("presence", "features")),
    }
    TOOLS = (tool("view-reveal-symbolic", "Presencia", "Bloquear si no hay nadie frente a la cámara", "presence"),)

    def _build_presence(self):
        c = self.core
        self.pr_switch = self._switch(lambda on: c.set_feature("presence", on))
        box = self._page("Presencia", self.pr_switch)
        self.pr_state = label("", "subtitle")
        self.pr_sub = label("", "dim small", lines=2)
        box.pack_start(self.pr_state, False, False, 0)
        box.pack_start(self.pr_sub, False, False, 0)

        grid = Gtk.Grid(row_spacing=6, column_spacing=10)
        lb = label("Bloquear tras (min sin nadie)", "artist", xalign=0.0)
        lb.set_hexpand(True)
        self.pr_min = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.pr_min.set_value(c.presence.conf["minutes"])
        self.pr_min.connect("value-changed", lambda s: c.presence.set_conf("minutes", int(s.get_value())))
        grid.attach(lb, 0, 0, 1, 1)
        grid.attach(self.pr_min, 1, 0, 1, 1)
        box.pack_start(grid, False, False, 0)

        box.pack_start(label("HORARIO", "section"), False, False, 0)
        row = Gtk.Box(spacing=6)
        self.pr_times = {}
        for key, text in (("start", "Desde"), ("end", "Hasta")):
            row.pack_start(label(text, "artist", ellipsize=False), False, False, 0)
            e = Gtk.Entry(width_chars=5, max_length=5, text=c.presence.conf[key])
            e.connect("activate", lambda w, k=key: self._pr_time(k, w))
            e.connect("focus-out-event", lambda w, _e, k=key: self._pr_time(k, w) and False)
            self.pr_times[key] = e
            row.pack_start(e, False, False, 0)
        box.pack_start(row, False, False, 0)
        days = Gtk.Box(spacing=4, homogeneous=True)
        self.pr_days = []
        for i, d in enumerate(_DAYS):
            b = button("chip", cb=lambda i=i: self._pr_day(i), text=d)
            self.pr_days.append(b)
            days.pack_start(b, True, True, 0)
        box.pack_start(days, False, False, 0)

        box.pack_start(label("PAUSA", "section"), False, False, 0)
        acts = Gtk.Box(spacing=6, homogeneous=True)
        p = c.presence
        self.pr_pause1 = button("chip", cb=lambda: p.pause(3600), text="1 hora")
        self.pr_pause2 = button("chip", cb=p.pause_tomorrow, text="Hasta mañana")
        self.pr_resume = button("chip", cb=p.resume, text="Reanudar")
        for b in (self.pr_pause1, self.pr_pause2, self.pr_resume):
            acts.pack_start(b, True, True, 0)
        box.pack_start(acts, False, False, 0)

        box.pack_start(label("IDENTIDAD", "section"), False, False, 0)
        self.pr_enrolled = label("", "dim small", lines=2)
        box.pack_start(self.pr_enrolled, False, False, 0)
        ident = Gtk.Box(spacing=6, homogeneous=True)
        self.pr_register = button("chip", cb=self._pr_enroll, text="Registrar mi rostro")
        self.pr_clear = button("chip", cb=p.clear_identity, text="Borrar mi rostro")
        ident.pack_start(self.pr_register, True, True, 0)
        ident.pack_start(self.pr_clear, True, True, 0)
        box.pack_start(ident, False, False, 0)
        box.pack_start(label("Solo se guarda un vector en este equipo; la foto se usa en memoria y se descarta.",
                             "dim small", lines=2), False, False, 0)

        self.pr_confirm = Gtk.Box(spacing=10)
        self.pr_face = Art(72, 10)
        self.pr_confirm.pack_start(self.pr_face, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        txt.pack_start(label("¿Eras tú?", "subtitle"), False, False, 0)
        txt.pack_start(label("Confirma para calibrar con esta luz; solo se guarda el vector.",
                             "dim small", lines=2), False, False, 0)
        ans = Gtk.Box(spacing=6)
        self.pr_yes = button("chip", cb=lambda: p.answer(True), text="Sí")
        self.pr_no = button("chip", cb=lambda: p.answer(False), text="No")
        ans.pack_start(self.pr_yes, True, True, 0)
        ans.pack_start(self.pr_no, True, True, 0)
        txt.pack_start(ans, False, False, 0)
        self.pr_confirm.pack_start(txt, True, True, 0)
        self.pr_confirm.set_no_show_all(True)
        self.pr_confirm.set_visible(False)
        box.pack_start(self.pr_confirm, False, False, 0)

        foot = Gtk.Box(spacing=6)
        self.pr_test = label("", "dim small")
        foot.pack_start(self.pr_test, True, True, 0)
        foot.pack_end(button("chip", cb=p.check_now, text="Probar cámara"), False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _pr_time(self, key, entry):
        text = entry.get_text().strip()
        if len(text) == 4 and text[1] == ":":
            text = "0" + text                       # «8:00» → «08:00»
        if not self.core.presence.set_conf(key, text):
            entry.set_text(self.core.presence.conf[key])   # inválida: vuelve al valor guardado
        else:
            entry.set_text(text)
        return False

    def _pr_day(self, i):
        days = set(self.core.presence.conf["days"])
        days ^= {i}
        self.core.presence.set_conf("days", sorted(days))

    def _pr_enroll(self):
        # descargar modelos y mirar la cámara puede tardar: nunca en el hilo de la interfaz
        threading.Thread(target=self.core.presence.enroll, daemon=True).start()

    def _fill_presence(self):
        c = self.core
        p = c.presence
        on = c.feature("presence")
        self._set_switch(self.pr_switch, on)
        st = p.state if on else "off"
        if on and st == "off":
            st = "active"                           # recién encendido, antes del primer ciclo
        conf = p.conf
        text = presence_label(st)
        left = p.seconds_left()
        if st == "warning" and left is not None:
            text = f"Bloqueando en {int(left)} s · mueve el ratón para cancelar"
        self.pr_state.set_text(text)
        set_accent(self.pr_state, _ACCENT.get(st))

        if st == "off":
            sub = "Apagado: no usa la cámara ni bloquea"
        elif st == "no_cv":
            sub = p.error or FaceDetector.INSTALL
        elif st == "lock_failed":
            sub = p.error + " · revisa el bloqueo de pantalla del sistema"
        elif st == "off_hours":
            sub = f"Funciona de {conf['start']} a {conf['end']} ({self._pr_days_text()})"
        elif st == "paused":
            sub = f"En pausa hasta {hm(conf['paused_until'])}" + \
                  ("" if conf["paused_until"] - time.time() < 86400 - 3600 else " de mañana")
        elif st in ("other", "confirm"):
            sub = _identity_hint(st)
        else:
            sub = f"Sin teclado ni ratón y sin nadie a la vista {conf['minutes']} min → bloquea y apaga la pantalla"
        if p.last_seen and st not in ("off", "no_cv"):
            sub += f" · te vio {ago(p.last_seen)}"
        self.pr_sub.set_text(sub)

        for i, b in enumerate(self.pr_days):
            set_class(b, "on", i in conf["days"])
        for key, e in self.pr_times.items():
            if not e.has_focus() and e.get_text() != conf[key]:
                e.set_text(conf[key])
        if int(self.pr_min.get_value()) != conf["minutes"]:
            self.pr_min.set_value(conf["minutes"])
        paused = conf["paused_until"] > time.time()
        self.pr_resume.set_visible(paused)
        self.pr_test.set_text(p.test_result or "")

        gallery = getattr(p, "gallery", None)
        templates = len(gallery.templates) if gallery else 0
        text, can_clear = _identity_text(bool(templates), max(0, templates - 1))
        self.pr_enrolled.set_text(text)
        self.pr_clear.set_visible(can_clear)
        prompt = getattr(p, "pending_prompt", None)
        self.pr_confirm.set_visible(prompt is not None and on)
        if prompt is None:
            if getattr(self, "_pr_prompt_frame", None) is not None:
                self._pr_prompt_frame = None
                self.pr_face.set_pixbuf(None)     # la foto también sale de memoria al responder/caducar
        elif getattr(self, "_pr_prompt_frame", None) is not prompt.get("frame"):
            self._pr_prompt_frame = prompt.get("frame")
            self.pr_face.set_pixbuf(_frame_pixbuf(self._pr_prompt_frame))

    def _pr_days_text(self):
        days = self.core.presence.conf["days"]
        if days == [0, 1, 2, 3, 4]:
            return "lunes a viernes"
        if len(days) == 7:
            return "todos los días"
        return " ".join(_DAYS[d] for d in days) or "ningún día"
