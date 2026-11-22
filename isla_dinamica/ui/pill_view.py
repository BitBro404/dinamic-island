"""Vista compacta de la píldora y tarjetas de aviso: construcción de sus widgets y un método por cada cosa que puede mostrar (ver ui.pill.PILL_ORDER)."""
import re
import time

from gi.repository import Gtk, Pango

from ..services.downloads import fmt_size
from ..services.pomodoro import Pomodoro
from ..util.fmt import fmt_secs, hm
from .gtk import button, icon, label, set_accent
from .gtk import icon_name as resolve_name   # «icon_name» ya es nombre de variable aquí
from .style import H, W_CARD, W_EXP
from .widgets.art import Art, GREEN
from .widgets.audio import Equalizer
from .widgets.charts import PrivacyDots
from .widgets.weather_icon import WeatherIcon


class PillViewMixin:
    """Construye la píldora compacta, la tarjeta y la alarma, y las rellena. Lo usa IslandWindow."""

    def _build_compact(self):
        box = self.c_box = Gtk.Box(spacing=9, margin_start=14, margin_end=14)
        self.c_time = label("", "c-time", ellipsize=False)     # la hora, siempre a la vista
        self.c_time.set_no_show_all(True)
        box.pack_start(self.c_time, False, False, 0)
        self.c_left = Gtk.Stack()
        self.c_icon = Gtk.Image()
        self.c_art = Art(22, 6)
        self.c_left.add_named(self.c_icon, "icon")
        self.c_left.add_named(self.c_art, "art")
        box.pack_start(self.c_left, False, False, 0)
        self.c_center = Gtk.Stack(hexpand=True)
        self.c_label = label("", "c-text")
        self.c_level = Gtk.LevelBar(valign=Gtk.Align.CENTER, min_value=0, max_value=1)
        for off in ("low", "high", "full"):
            self.c_level.remove_offset_value(off)
        self.c_center.add_named(self.c_label, "label")
        self.c_center.add_named(self.c_level, "level")
        box.pack_start(self.c_center, True, True, 0)
        self.c_right = Gtk.Stack()
        self.c_rlabel = label("", "c-text", xalign=1.0, ellipsize=False)
        self.c_eq = Equalizer()
        self.c_eq.levels_fn = lambda: self.core.audio.levels if self.core.feature("audio") else None
        self._eq_art = object()     # carátula de la que salió el color actual
        self._art_color = GREEN
        self._glow = 0.0            # brillo del borde (sigue el volumen)
        self._glow_tick = None
        self._glow_drawn = 0.0
        self.c_right.add_named(self.c_rlabel, "label")
        self.c_right.add_named(self.c_eq, "eq")
        self.c_dots = PrivacyDots()           # puntos de privacidad: en el extremo derecho
        self.c_dots.set_no_show_all(True)
        box.pack_end(self.c_dots, False, False, 0)
        box.pack_end(self.c_right, False, False, 0)
        self.c_wicon = WeatherIcon(18)
        self.c_wicon.set_no_show_all(True)
        box.pack_end(self.c_wicon, False, False, 0)
        return box

    def _build_card(self):
        box = Gtk.Box(spacing=12, margin_start=14, margin_end=18, margin_top=12, margin_bottom=12)
        self.k_left = Gtk.Stack(valign=Gtk.Align.CENTER)
        self.k_icon = Gtk.Image(pixel_size=30)
        self.k_art = Art(42, 10)
        self.k_left.add_named(self.k_icon, "icon")
        self.k_left.add_named(self.k_art, "art")
        box.pack_start(self.k_left, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, valign=Gtk.Align.CENTER)
        self.k_app = label("", "dim small")
        self.k_title = label("", "subtitle")
        self.k_body = label("", "artist", lines=2)
        self.k_hint = label("Clic para abrir", "time-small")
        self.k_hint.set_no_show_all(True)
        for w in (self.k_app, self.k_title, self.k_body, self.k_hint):
            txt.pack_start(w, False, False, 0)
        box.pack_start(txt, True, True, 0)
        close = button("close", icon("window-close-symbolic", px=12), self._close_card, "Cerrar")
        close.set_valign(Gtk.Align.START)
        box.pack_end(close, False, False, 0)
        return box

    def _close_card(self):
        """Descarta la notificación; si el ratón sigue encima, se ve el panel con las demás opciones."""
        self.core.event = None
        self.card_hold = False
        self.core.refresh()

    def _build_alert(self):
        box = Gtk.Box(spacing=12, margin_start=18, margin_end=14)
        a = icon("alarm-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        set_accent(a, "orange")
        box.pack_start(a, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        txt.pack_start(label("¡Tiempo cumplido!", "title"), False, False, 0)
        self.a_sub = label("", "artist")
        txt.pack_start(self.a_sub, False, False, 0)
        box.pack_start(txt, True, True, 0)
        ok = button("chip", cb=self.core.dismiss_alert, text="OK")
        ok.set_valign(Gtk.Align.CENTER)
        box.pack_end(ok, False, False, 0)
        return box

    def _set_vertical(self, v):
        if v == self.vertical:
            return
        self.vertical = v
        o = Gtk.Orientation.VERTICAL if v else Gtk.Orientation.HORIZONTAL
        self.outer.set_orientation(o)
        self.bub_box.set_orientation(o)
        b = self.c_box
        b.set_orientation(Gtk.Orientation.VERTICAL if v else Gtk.Orientation.HORIZONTAL)
        b.set_margin_start(0 if v else 14)
        b.set_margin_end(0 if v else 14)
        b.set_margin_top(12 if v else 0)
        b.set_margin_bottom(12 if v else 0)
        self.c_center.set_hexpand(not v)
        self.c_center.set_vexpand(v)
        self.c_level.set_orientation(Gtk.Orientation.VERTICAL if v else Gtk.Orientation.HORIZONTAL)
        self.c_level.set_inverted(v)
        self.c_level.set_halign(Gtk.Align.CENTER if v else Gtk.Align.FILL)
        self.c_level.set_valign(Gtk.Align.FILL if v else Gtk.Align.CENTER)

    def _vtext(self, lb, text, maxc):
        """Pone el texto de la píldora; en vertical lo gira o lo apila para que quepa."""
        ell = lb is self.c_label
        if not self.vertical:
            lb.set_angle(0)
            lb.set_justify(Gtk.Justification.LEFT)
            lb.set_ellipsize(Pango.EllipsizeMode.END if ell else Pango.EllipsizeMode.NONE)
            lb.set_text(text)
            return
        lb.set_ellipsize(Pango.EllipsizeMode.NONE)   # GTK ignora el giro si hay elipsis
        lb.set_justify(Gtk.Justification.CENTER)
        hmm = re.fullmatch(r"(\d{1,2}):(\d{2})(?: ?[ap]m)?", text)
        if hmm:                                      # hora o temporizador: 14 / 05
            lb.set_angle(0)
            lb.set_text(f"{hmm.group(1)}\n{hmm.group(2)}")
        elif len(text) <= 3:
            lb.set_angle(0)
            lb.set_text(text)
        else:
            lb.set_angle(90)
            lb.set_text(text if len(text) <= maxc else text[:maxc - 1].rstrip() + "…")

    def _compact(self, left=None, icon_name=None, accent=None, text="", level=None,
                 right=None, right_text="", right_accent=None, xalign=0.0, text_accent=None, wkind=None,
                 clock=True):
        self.c_time.set_visible(clock)
        if clock:
            self._vtext(self.c_time, hm(), 8)
        self.c_wicon.set_visible(wkind is not None)
        if wkind:
            self.c_wicon.set_kind(wkind)
        if left == "icon":
            self.c_icon.set_from_icon_name(resolve_name(icon_name), Gtk.IconSize.MENU)
            set_accent(self.c_icon, accent)
        if left:
            self.c_left.set_visible_child_name(left)
        self.c_left.set_visible(left is not None)
        if level is not None:
            self.c_level.set_value(level)
            self.c_center.set_visible_child_name("level")
        else:
            self._vtext(self.c_label, text, 16)
            self.c_label.set_xalign(0.5 if self.vertical else xalign)
            set_accent(self.c_label, text_accent)
            self.c_center.set_visible_child_name("label")
        if right == "label":
            self._vtext(self.c_rlabel, right_text, 10)
            set_accent(self.c_rlabel, right_accent)
        if right:
            self.c_right.set_visible_child_name(right)
        self.c_right.set_visible(right is not None)

    def _fit(self, lo, hi):
        """Ancho de la píldora compacta según su contenido natural, entre `lo` y `hi`."""
        self._show("compact", (max(lo, min(hi, self._natural("compact", 0) + 4)), H))

    def _pill_alert(self, c, now, m, timer_left):
        self.a_sub.set_text(f"Temporizador de {fmt_secs(c.timer_total)}")
        self._show("alert", (360, 64))

    def _pill_card_hold(self, c, now, m, timer_left):
        c.event["until"] = max(c.event["until"], now + 2.0)   # sigue abierta mientras el ratón esté encima
        self._show_event(c.event)

    def _pill_expanded(self, c, now, m, timer_left):
        self._show(self.page, (W_EXP, min(580, self._natural(self.page, W_EXP))))

    def _pill_presence(self, c, now, m, timer_left):
        self._shown = {a["key"] for a in self._acts}          # cuenta atrás antes de bloquear: lo primero
        self._compact("icon", "view-reveal-symbolic", "orange", text="Nadie frente a la pantalla",
                      text_accent="orange", right="label",
                      right_text=fmt_secs(c.presence.seconds_left() or 0), right_accent="orange")
        self._fit(260, 380)

    def _pill_event(self, c, now, m, timer_left):
        self._shown = {a["key"] for a in self._acts}          # durante un aviso, sin burbujas
        self._show_event(c.event)

    def _pill_call(self, c, now, m, timer_left):
        self._shown = {"call"}
        self._compact("icon", "call-start-symbolic", "green",
                      text=f"En llamada · {fmt_secs(time.monotonic() - c.audio.call_since)}", text_accent="green",
                      right="eq")
        self.c_eq.color = GREEN
        self._fit(200, 360)
        return True

    def _pill_media(self, c, now, m, timer_left):
        self._shown = {"media"}
        self._compact("art", text=m["title"], right="eq")
        self._show("compact", (300 + self._tw(), H))
        return True

    def _pill_pomodoro(self, c, now, m, timer_left):
        p = c.pomo
        acc = "red" if p.phase == "work" else "green"
        self._shown = {"pomo"}
        self._compact("icon", "timer-symbolic", acc,
                      text=f"{Pomodoro.LABEL[p.phase]}  {fmt_secs(p.left())}", text_accent=acc,
                      right="label" if not p.running else None, right_text="En pausa")
        self._fit(190, 360)

    def _pill_recording(self, c, now, m, timer_left):
        self._shown = {"rec"}
        self._compact("icon", "media-record-symbolic", "red", text="Grabando", text_accent="red",
                      right="label", right_text=fmt_secs(c.recorder.elapsed()), right_accent="red")
        self._show("compact", (190 + self._tw(), H))

    def _pill_reminder(self, c, now, m, timer_left):
        self._shown = {"reminder"}
        r = c.reminders.next()
        self._compact("icon", "alarm-symbolic", "blue", text=r["text"],
                      right="label", right_text=fmt_secs(max(0, r["at"] - time.time())), right_accent="blue")
        self._fit(200, 380)

    def _pill_deploy(self, c, now, m, timer_left):
        self._shown = {"deploy"}
        act = c.deploys.active()
        d, more = act[0], len(act) - 1
        self._compact("icon", "emblem-synchronizing-symbolic", "orange",
                      text=f"{d['name']} · {d['env']}" + (f" (+{more})" if more else ""),
                      right="label", right_text=fmt_secs(time.time() - d["created"]), right_accent="orange")
        self._fit(220, 420)

    def _pill_download(self, c, now, m, timer_left):
        self._shown = {"download"}
        d = c.downloads.main()
        n = len(c.downloads.active)
        rate = f"{fmt_size(int(d['speed']))}/s" if d["speed"] > 1024 else fmt_size(d["size"])
        self._compact("icon", "folder-download-symbolic", "blue",
                      text=d["name"] + (f" (+{n - 1})" if n > 1 else ""),
                      right="label", right_text=rate, right_accent="blue")
        self._show("compact", (300 + self._tw(), H))

    def _pill_audio(self, c, now, m, timer_left):
        self._shown = {"audio"}
        outs = c.audio.outputs
        self._compact("icon", "audio-speakers-symbolic", None,
                      text=outs[0] + (f" (+{len(outs) - 1})" if len(outs) > 1 else ""), right="eq")
        self.c_eq.color = GREEN
        self._fit(190, 340)
        return True

    def _pill_timer(self, c, now, m, timer_left):
        self._shown = {"timer"}
        self._compact("icon", "alarm-symbolic", "orange", text=fmt_secs(timer_left), xalign=0.5,
                      text_accent="orange")
        self._show("compact", (170 + self._tw(), H))

    def _pill_idle(self, c, now, m, timer_left):
        """En reposo: la hora, un punto rojo si hay avisos sin leer y la temperatura."""
        dot = c.unread > 0
        wd = c.weather.data if c.feature("weather") else None
        self._compact("icon" if dot else None, "preferences-system-notifications-symbolic", "red",
                      text=hm(), xalign=0.5 if not wd else 0.0,
                      right="label" if wd else None, right_text=f"{wd['temp']:.0f}°" if wd else "",
                      wkind=wd.get("kind") if wd else None, clock=False)
        low = (209 if dot else 189) if wd else (150 if dot else 130)
        self._show("compact", (max(low, self._natural("compact", 0) + 4), H))

    def _tw(self):
        """Ancho extra de la hora en la píldora horizontal (para los tamaños fijos)."""
        if self.vertical or not self.c_time.get_visible():
            return 0
        return self.c_time.get_preferred_width()[1] + 9

    def _show_event(self, ev):
        if ev["kind"] == "card":
            if ev.get("pixbuf") is not None:
                self.k_art.set_pixbuf(ev["pixbuf"])
                self.k_left.set_visible_child_name("art")
            else:
                self.k_icon.set_from_icon_name(resolve_name(ev.get("icon") or "dialog-information-symbolic"), Gtk.IconSize.DND)
                self.k_left.set_visible_child_name("icon")
            self.k_app.set_text(f"{ev.get('app', '')}  ·  {hm()}".lstrip(" ·"))
            rgb = self._card_color(ev)
            if rgb != self._card_rgb:
                self._card_rgb = rgb
                self.queue_draw()
            self.k_title.set_text(ev.get("title", ""))
            self.k_body.set_text(ev.get("body", ""))
            self.k_body.set_visible(bool(ev.get("body")))
            self.k_body.set_lines(10 if self.card_hold else 2)
            self.k_hint.set_visible(self.card_hold and bool(ev.get("action")))
            self._show("card", (W_CARD, self._natural("card", W_CARD)))
        elif ev["kind"] == "volume":
            v, muted = ev["value"], ev["muted"]
            ic = ("audio-volume-muted-symbolic" if muted or v == 0 else
                  "audio-volume-low-symbolic" if v < 0.34 else
                  "audio-volume-medium-symbolic" if v < 0.67 else "audio-volume-high-symbolic")
            self._compact("icon", ic, level=0 if muted else min(v, 1.0), right="label",
                          right_text="Silencio" if muted else f"{round(v * 100)}%")
            self._show("compact", (290 + self._tw(), H))
        else:
            self._compact("icon", ev.get("icon"), ev.get("accent"), text=ev.get("text", ""),
                          right="label" if ev.get("right") else None, right_text=ev.get("right", ""),
                          right_accent=ev.get("right_accent"))
            nat = self._natural("compact", 0)
            self._show("compact", (max(200, min(400, nat + 4)), H))
