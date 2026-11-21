"""La ventana de la isla: forma, animación, arrastre, eventos y vista compacta."""
import time

from gi.repository import GLib, Gdk, Gtk, GtkLayerShell

from .services.media import Volume
from .ui.style import BUB_GAP, BUB_MAX, H
from .ui.widgets.art import Art, GREEN, vivid_color
from .util.fmt import hm
from .pages import PAGE_CLASSES
from .ui.pill import PillState, pick_pill
from .ui.bubbles import activities
from .ui.dock import DockMixin
from .ui.paint import PaintMixin
from .ui.bubbles import BubblesMixin
from .ui.pill_view import PillViewMixin


class IslandWindow(PillViewMixin, BubblesMixin, PaintMixin, DockMixin, Gtk.Window):
    """Ventana de la isla: une píldora, burbujas, dibujo y acople (mixins) con las páginas (objetos Page)."""
    def __init__(self, core, monitor):
        super().__init__(title="Isla dinámica")
        core.app.add_window(self)
        self.core, self.monitor = core, monitor
        self.set_decorated(False)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "isla-dinamica")
        GtkLayerShell.set_monitor(self, monitor)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        self.hover = False
        self._hover_src = None
        self.page = "home"
        self.view = None
        self.pending = None
        self.cur = [130.0, float(H)]
        self.target = (130, H)
        self.vel = [0.0, 0.0]
        self._anim_src = None
        self.seen = {}
        self.page_clocks = []       # relojes de las cabeceras de página (Page._page los registra)
        self.card_hold = False      # ratón sobre una notificación: no se cierra
        # arrastre y acople a los bordes
        self.vertical = False       # píldora en vertical (pegada a un borde lateral)
        self.drag = None            # arrastre en curso
        self._drag_end = 0.0
        self.poff = [0.0, 0.0]      # desfase que se anima hacia 0 al soltar
        self.pvel = [0.0, 0.0]
        self._last_xy = (0, 0)      # posición (arriba-izquierda) pedida por última vez
        self._applied = (0, 0)      # posición ya aplicada por el compositor
        self._nav_t = 0.0           # cuándo se cambió de página por última vez
        self._inside = False        # ratón dentro de la ventana (según enter/leave)
        self._layout = None
        self._acts = []             # actividades en curso (grabación, descarga, música, pomodoro…)
        self._shown = set()         # las que muestra la píldora; el resto va en burbujas
        self.bubbles = []           # actividades que se ven como burbujas
        self._bub_ext = 0           # largo que ocupan las burbujas (ancho u alto según orientación)
        self.pad = (0, 0, 0, 0)     # espacio alrededor para la sombra de las notificaciones (izq, arr, der, abj)
        self._card_rgb = (0.35, 0.45, 0.95)

        ev = Gtk.EventBox()
        ev.set_visible_window(False)
        ev.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                      Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK)
        ev.connect("scroll-event", self._on_scroll)
        # arrastre: gesto en fase de captura sobre la ventana, así recibe el clic antes que
        # cualquier hijo (botones, Stack, ScrolledWindow) y lo reclama al empezar a mover
        self._gdrag = Gtk.GestureDrag.new(self)
        self._gdrag.set_button(1)
        self._gdrag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self._gdrag.connect("drag-begin", self._on_press)
        self._gdrag.connect("drag-end", self._on_drag_end)
        ev.connect("motion-notify-event", self._on_motion)
        # entrar/salir se escucha en la ventana: GTK no propaga esos eventos desde los hijos
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        ev.connect("button-release-event", self._on_click)
        self.add(ev)

        self.stack = Gtk.Stack(hhomogeneous=False, vhomogeneous=False)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        self.stack.set_size_request(*self.target)
        self.outer = Gtk.Box()
        self.outer.pack_start(self.stack, False, False, 0)
        self.bub_box = Gtk.Box(spacing=BUB_GAP)
        self.bub_box.set_no_show_all(True)
        self.bub_widgets = []
        for _ in range(BUB_MAX):
            st = Gtk.Stack()
            st.set_size_request(H, H)
            img = Gtk.Image()
            art = Art(20, 10)
            art.set_halign(Gtk.Align.CENTER)
            st.add_named(img, "icon")
            st.add_named(art, "art")
            img.show()
            art.show()
            st.set_no_show_all(True)
            self.bub_box.pack_start(st, False, False, 0)
            self.bub_widgets.append((st, img, art))
        self.outer.pack_start(self.bub_box, False, False, 0)
        ev.add(self.outer)

        for name, builder in (("compact", self._build_compact), ("card", self._build_card),
                              ("alert", self._build_alert)):
            self.stack.add_named(builder(), name)
        # páginas: un objeto por clase de pages/, que recibe esta ventana como «host» (composición)
        self.page_objs = [cls(self) for cls in PAGE_CLASSES]
        self.specs = {name: (obj, spec) for obj in self.page_objs for name, spec in obj.PAGES.items()}
        for name, (obj, spec) in self.specs.items():
            self.stack.add_named(getattr(obj, spec["build"])(), name)

        self.connect("draw", self._draw)
        self.connect("realize", lambda *_: self.get_frame_clock().connect("after-paint", self._after_paint))
        self._set_vertical(self.core.dock["edge"] in ("left", "right"))
        self._place()
        self.show_all()
        self.refresh()

    # ── construcción ──
    def go(self, page):
        self.page = page
        self._nav_t = time.monotonic()
        self._opened(page)
        self.refresh()

    def _opened(self, page):
        """Avisa a la página que se acaba de abrir (para que refresque sus datos si están viejos)."""
        obj, spec = self.specs.get(page, (None, None))
        if spec and spec["open"]:
            getattr(obj, spec["open"])()

    def _fill_lists(self):
        """Rellena cada página cuyos datos vigilados cambiaron desde la última vez."""
        ver = self.core.ver
        for name, (obj, spec) in self.specs.items():
            if not spec["fill"]:
                continue
            key = tuple(ver.get(k) for k in spec["watch"])
            if self.seen.get(name) != key:
                self.seen[name] = key
                getattr(obj, spec["fill"])()

    # ── animación tipo resorte ──
    def _anim_step(self):
        settled = True
        for i in (0, 1):
            d = self.target[i] - self.cur[i]
            self.vel[i] = self.vel[i] * 0.66 + d * 0.15
            self.cur[i] += self.vel[i]
            if abs(d) > 0.5 or abs(self.vel[i]) > 0.5:
                settled = False
        for i in (0, 1):
            self.pvel[i] = self.pvel[i] * 0.66 - self.poff[i] * 0.15
            self.poff[i] += self.pvel[i]
            if abs(self.poff[i]) > 0.5 or abs(self.pvel[i]) > 0.5:
                settled = False
        if settled:
            self.cur = [float(self.target[0]), float(self.target[1])]
            self.vel = [0.0, 0.0]
            self.poff, self.pvel = [0.0, 0.0], [0.0, 0.0]
        if self.pending and (settled or (self.cur[0] >= self.target[0] * 0.8 and
                                         self.cur[1] >= self.target[1] * 0.8)):
            self.stack.set_visible_child_name(self.pending)
            self.pending = None
        w, h = max(1, round(self.cur[0])), max(1, round(self.cur[1]))
        if self.vertical:
            self.stack.set_size_request(w, max(1, h - self._bub_ext))
        else:
            self.stack.set_size_request(max(1, w - self._bub_ext), h)
        self.resize(w + self.pad[0] + self.pad[2], h + self.pad[1] + self.pad[3])
        self._place()
        self.queue_draw()
        if settled:
            self._anim_src = None
            return False
        return True

    def _natural(self, name, width):
        child = self.stack.get_child_by_name(name)
        if name == "compact":
            return child.get_preferred_width()[1]
        return child.get_preferred_height_for_width(width)[1]

    def _show(self, name, size):
        if name == "compact":
            p = self.core.privacy
            self.c_dots.set_state(p.cam, p.mic)
            self.c_dots.set_visible(bool(p.cam or p.mic))
            if (p.cam or p.mic) and not self.vertical:
                size = (size[0] + self.c_dots.count() * 12 + 6, size[1])   # sitio para los puntos
        if name == "compact" and self.vertical:
            nat = self.c_box.get_preferred_height_for_width(H)[1]
            low = 150 if self.c_center.get_visible_child_name() == "level" else 84
            size = (H, max(low, min(300, nat + 4)))
        self._set_pad(name == "card")
        bub = [a for a in self._acts if a["key"] not in self._shown][:BUB_MAX] if name == "compact" else []
        if [a["key"] for a in bub] != [a["key"] for a in self.bubbles] or bub:
            self._set_bubbles(bub)
        ext = len(bub) * (H + BUB_GAP)
        size = (size[0], size[1] + ext) if self.vertical else (size[0] + ext, size[1])
        size = (int(size[0]), int(size[1]))
        if name != self.view:
            grow = size[1] > self.cur[1] + 4 or size[0] > self.cur[0] + 40
            if grow and self.view is not None:
                self.pending = name
            else:
                self.pending = None
                self.stack.set_visible_child_name(name)
            self.view = name
        if size != self.target:
            self.target = size
            if self._anim_src is None:
                self._anim_src = GLib.timeout_add(16, self._anim_step)

    # ── eventos ──
    def _on_enter(self, _w, ev):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._inside = True
        if (self.drag and self.drag["moving"]) or time.monotonic() - self._drag_end < 0.4:
            return False          # recién soltada tras arrastrar: no abrir
        if self._hover_src:
            GLib.source_remove(self._hover_src)
        self._hover_src = GLib.timeout_add(110, self._set_hover, True)
        return False

    def _on_leave(self, _w, ev):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._inside = False
        if self.drag and self.drag["moving"]:
            return False
        if self._hover_src:
            GLib.source_remove(self._hover_src)
        self._hover_src = GLib.timeout_add(self._leave_delay(), self._leave_timeout)
        return False

    def _leave_delay(self):
        """Cuánto esperar antes de cerrar cuando el ratón sale de la isla."""
        if time.monotonic() - self._nav_t < 1.5:
            return 8000           # se achicó al cambiar de página y el ratón quedó fuera: no es que se fuera
        if any(obj.waiting() for obj in self.page_objs):
            return 8000           # esperando la confirmación de apagar/reiniciar/salir
        return 1000 if self.page == "home" else 3000

    def _leave_timeout(self):
        self._hover_src = None
        if isinstance(self.get_focus(), Gtk.Entry) and self.get_focus().has_focus():
            return False          # escribiendo (Wi-Fi, ciudad, recordatorio, carpeta…): no cerrar
        if self._inside:
            return False          # el ratón volvió
        self._set_hover(False)
        return False

    def _set_hover(self, value):
        if self._hover_src:
            GLib.source_remove(self._hover_src)
            self._hover_src = None
        if value and not self.hover:
            i = self._bubble_at()
            if i is not None:
                self.page = self.bubbles[i]["page"]
                self._nav_t = time.monotonic()
                self._opened(self.page)
            self.core.radios.refresh()
            ev = self.core.event
            self.card_hold = bool(self.view == "card" and ev and time.monotonic() < ev["until"])
        self.hover = value
        if not value:
            if self.card_hold and self.core.event:
                # al salir de la notificación, darle unos segundos más antes de cerrarla
                self.core.event["until"] = max(self.core.event["until"], time.monotonic() + 3.0)
                GLib.timeout_add(3100, self.core.refresh)
            self.card_hold = False
            self.page = "record" if self.core.recorder.active else "home"
            for obj in self.page_objs:
                obj.on_collapse()
        self.refresh()
        return False

    def _on_click(self, _w, ev):
        if ev.button != 1:
            return False
        d, self.drag = self.drag, None
        if d and d["moving"]:
            self._drop()
            return True
        if time.monotonic() - self._drag_end < 0.3:
            return True           # fin de un arrastre: no es un clic
        if self.view == "card" and self.core.event and self.core.event.get("action"):
            act = self.core.event["action"]
            self.core.event = None
            self.card_hold = False
            act()
            self.core.refresh()
            return True
        if self.view == "compact":
            self._set_hover(True)
            return True
        return False

    def _on_scroll(self, _w, ev):
        if self.view in ("compact", "card") and ev.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.DOWN):
            Volume.step(ev.direction == Gdk.ScrollDirection.UP)
            return True
        return False

    # ── animación: arrancar el resorte ──
    def _kick(self):
        if self._anim_src is None:
            self._anim_src = GLib.timeout_add(16, self._anim_step)

    # ── decide qué mostrar ──
    def refresh(self):
        c = self.core
        now = time.monotonic()
        m = c.media
        playing = bool(m and m["playing"])
        timer_left = (c.timer_end - now) if c.timer_end else None
        for obj in self.page_objs:
            obj.live(c, m, playing, timer_left)
        self._fill_lists()
        if self.hover:
            now_hm = hm()
            for clk in self.page_clocks:
                if clk.get_text() != now_hm:
                    clk.set_text(now_hm)
            if playing and self.page == "home":
                c.audio.detail_until = time.monotonic() + 1.5     # espectro detallado para el reproductor
        self._acts = activities(c, m, playing, timer_left)
        akeys = {a["key"] for a in self._acts}
        self._shown = set()
        if c.art is not self._eq_art:             # color de las barras y del brillo según la carátula
            self._eq_art = c.art
            self._art_color = vivid_color(c.art)
        self.c_eq.color = self._art_color if playing else GREEN
        self.c_art.set_pixbuf(c.art)

        state = PillState(
            alert=bool(c.alert_until and now < c.alert_until),
            card_hold=bool(self.card_hold and c.event and c.event.get("kind") == "card"),
            hover=self.hover,
            presence_warning=c.feature("presence") and c.presence.state == "warning",
            event=bool(c.event and now < c.event["until"]),
            activities=frozenset(akeys), playing=playing, pomodoro=c.pomo.active,
            recording=c.recorder.active, timer=timer_left is not None)
        eq_on = bool(getattr(self, "_pill_" + pick_pill(state))(c, now, m, timer_left))
        if c.alert_until and now >= c.alert_until:
            c.alert_until = None
        self.c_eq.set_playing(eq_on)
        self._set_glow(eq_on and self.view == "compact" and c.feature("audio") and c.audio.levels is not None)
        return False

    def typing(self):
        """¿Se está escribiendo en algún campo de texto? (entonces no se empieza a arrastrar la isla)"""
        return any(obj.typing() for obj in self.page_objs)
