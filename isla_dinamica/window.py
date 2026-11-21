"""La ventana de la isla: forma, animación, arrastre, eventos y vista compacta."""
from .common import *  # noqa: F401,F403
from .widgets import *  # noqa: F401,F403
from .services import *  # noqa: F401,F403
from .pages import PAGE_CLASSES


class IslandWindow(*PAGE_CLASSES, Gtk.Window):
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
        self.pw_net = None
        self._confirm = None
        self._vol_lock = False
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
        ev.add(self.stack)

        for name, builder in (("compact", self._build_compact), ("card", self._build_card),
                              ("alert", self._build_alert)):
            self.stack.add_named(builder(), name)
        for name, spec in self._page_specs().items():
            self.stack.add_named(getattr(self, spec["build"])(), name)

        self.connect("draw", self._draw)
        self.connect("realize", lambda *_: self.get_frame_clock().connect("after-paint", self._after_paint))
        self._set_vertical(self.core.dock["edge"] in ("left", "right"))
        self._place()
        self.show_all()
        self.refresh()

    # ── construcción ──
    def _build_compact(self):
        box = self.c_box = Gtk.Box(spacing=9, margin_start=14, margin_end=14)
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

    def _page(self, title, right=None):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_start=16, margin_end=16, margin_top=12, margin_bottom=14)
        head = Gtk.Box(spacing=6)
        head.pack_start(button("ctrl", icon("go-previous-symbolic"), lambda: self.go("home"), "Volver"),
                        False, False, 0)
        head.pack_start(label(title, "title"), True, True, 0)
        if right is not None:
            right.set_valign(Gtk.Align.CENTER)
            head.pack_end(right, False, False, 0)
        box.pack_start(head, False, False, 0)
        return box

    @staticmethod
    def _scroller(child, max_h=250):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_propagate_natural_height(True)
        sw.set_max_content_height(max_h)
        sw.add(child)
        return sw

    @staticmethod
    def _switch(cb):
        sw = Gtk.Switch()
        sw._cb = sw.connect("notify::active", lambda s, _p: cb(s.get_active()))
        return sw

    @staticmethod
    def _set_switch(sw, value):
        if sw.get_active() != value:
            sw.handler_block(sw._cb)
            sw.set_active(value)
            sw.handler_unblock(sw._cb)

    def go(self, page):
        self.page = page
        self._nav_t = time.monotonic()
        spec = self._page_specs().get(page)
        if spec and spec["open"]:
            getattr(self, spec["open"])()
        self.refresh()

    @classmethod
    def _page_specs(cls):
        """Todas las páginas declaradas por las clases de pages/ (nombre → spec)."""
        if "_specs" not in cls.__dict__:
            specs = {}
            for klass in reversed(cls.__mro__):
                specs.update(klass.__dict__.get("PAGES", {}))
            cls._specs = specs
        return cls._specs

    def _fill_lists(self):
        """Rellena cada página cuyos datos vigilados cambiaron desde la última vez."""
        ver = self.core.ver
        for name, spec in self._page_specs().items():
            if not spec["fill"]:
                continue
            key = tuple(ver.get(k) for k in spec["watch"])
            if self.seen.get(name) != key:
                self.seen[name] = key
                getattr(self, spec["fill"])()

    def _settings(self, panel):
        subprocess.Popen(["budgie-control-center", panel], stderr=subprocess.DEVNULL)
        self._set_hover(False)

    def _collapse_then(self, fn):
        self._set_hover(False)
        fn()

    # ── listas ──
    def _row(self, ic, title, sub=None, cb=None, extra=None, pixbuf=None, sub_accent=None):
        inner = Gtk.Box(spacing=10)
        if pixbuf is not None:
            a = Art(32, 8)
            a.set_pixbuf(pixbuf)
            inner.pack_start(a, False, False, 0)
        elif ic:
            inner.pack_start(icon(ic, px=24), False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        txt.pack_start(label(title, "subtitle"), False, False, 0)
        if sub:
            s = label(sub, "dim", lines=2)
            set_accent(s, sub_accent)
            txt.pack_start(s, False, False, 0)
        inner.pack_start(txt, True, True, 0)
        row = Gtk.Box(spacing=4)
        if cb:
            row.pack_start(button("row", inner, cb), True, True, 0)
        else:
            inner.set_margin_start(8)
            inner.set_margin_top(6)
            inner.set_margin_bottom(6)
            row.pack_start(inner, True, True, 0)
        for w in extra or ():
            w.set_valign(Gtk.Align.CENTER)
            row.pack_start(w, False, False, 0)
        return row

    @staticmethod
    def _empty(box, text):
        lb = label(text, "dim", xalign=0.5)
        lb.set_margin_top(10)
        lb.set_margin_bottom(10)
        box.pack_start(lb, False, False, 0)

    def _copy(self, text):
        self.core.clip.copy(text)
        self._set_hover(False)
        self.core.show_event(1.5, kind="pill", icon="edit-copy-symbolic", accent="green", text="Copiado")

    # ── dibujo ──
    def _draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        a = self.get_allocation()
        w, h = a.width, a.height
        r = min(w / 2, h / 2, 30)
        cr.new_sub_path()
        cr.arc(w - r, r, r, -math.pi / 2, 0)
        cr.arc(w - r, h - r, r, 0, math.pi / 2)
        cr.arc(r, h - r, r, math.pi / 2, math.pi)
        cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgb(0, 0, 0)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.07)
        cr.set_line_width(1)
        cr.stroke()
        return False

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
        self.stack.set_size_request(w, h)
        self.resize(w, h)
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
        if self._confirm:
            return 8000           # esperando la confirmación de apagar/reiniciar/salir
        return 1000 if self.page == "home" else 3000

    def _leave_timeout(self):
        self._hover_src = None
        if (self.pw_net and self.w_entry.has_focus()) or self.we_entry.has_focus():
            return False          # escribiendo (contraseña del Wi-Fi o ciudad): no cerrar
        if self._inside:
            return False          # el ratón volvió
        self._set_hover(False)
        return False

    def _set_hover(self, value):
        if self._hover_src:
            GLib.source_remove(self._hover_src)
            self._hover_src = None
        if value and not self.hover:
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
            self.page = "home"
            self.pw_net = None
            self.w_pw.hide()
            self._confirm = None
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

    # ── arrastre y acople a los bordes ──
    def _mon_size(self):
        g = self.monitor.get_geometry()
        return g.width, g.height

    def _pointer(self):
        """Posición del ratón relativa a la ventana (en Wayland no hay coordenadas globales)."""
        win = self.get_window()
        dev = self.get_display().get_default_seat().get_pointer()
        _, x, y, _ = win.get_device_position(dev)
        return x, y

    @staticmethod
    def _nearest_edge(cx, cy, mw, mh):
        dist = {"top": cy, "bottom": mh - cy, "left": cx, "right": mw - cx}
        return min(dist, key=dist.get)

    def _target_xy(self, w, h):
        mw, mh = self._mon_size()
        if self.drag and self.drag["moving"]:
            cx, cy = self.drag["c"]
        else:
            e, p = self.core.dock["edge"], self.core.dock["pos"]
            if e in ("top", "bottom"):
                cx = p * mw
                cy = GAP + h / 2 if e == "top" else mh - GAP - h / 2
            else:
                cy = p * mh
                cx = GAP + w / 2 if e == "left" else mw - GAP - w / 2
        x = max(GAP, min(cx - w / 2, mw - w - GAP))
        y = max(GAP, min(cy - h / 2, mh - h - GAP))
        return x, y

    def _place(self):
        """Coloca la ventana según el borde al que está pegada (o donde se esté arrastrando)."""
        w, h = max(1, round(self.cur[0])), max(1, round(self.cur[1]))
        mw, mh = self._mon_size()
        x, y = self._target_xy(w, h)
        x, y = round(x + self.poff[0]), round(y + self.poff[1])
        self._last_xy = (x, y)
        edge = None if self.drag and self.drag["moving"] else self.core.dock["edge"]
        E = GtkLayerShell.Edge
        if edge == "bottom":        # crece hacia arriba
            layout = ((E.BOTTOM, E.LEFT), {E.BOTTOM: mh - y - h, E.LEFT: x})
        elif edge == "right":       # crece hacia la izquierda
            layout = ((E.TOP, E.RIGHT), {E.TOP: y, E.RIGHT: mw - x - w})
        else:
            layout = ((E.TOP, E.LEFT), {E.TOP: y, E.LEFT: x})
        if layout == self._layout:
            return
        anchors, margins = layout
        if self._layout is None or anchors != self._layout[0]:
            for e in (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT):
                GtkLayerShell.set_anchor(self, e, e in anchors)
        for e in (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT):
            GtkLayerShell.set_margin(self, e, int(margins.get(e, 0)))
        self._layout = layout
        if self._applied == (0, 0) and not self.get_realized():
            self._applied = (x, y)

    def _after_paint(self, _clock):
        self._applied = self._last_xy

    def _kick(self):
        if self._anim_src is None:
            self._anim_src = GLib.timeout_add(16, self._anim_step)

    def _set_vertical(self, v):
        if v == self.vertical:
            return
        self.vertical = v
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
        if re.fullmatch(r"\d{1,2}:\d{2}", text):     # hora o temporizador: 14 / 05
            lb.set_angle(0)
            lb.set_text(text.replace(":", "\n"))
        elif len(text) <= 3:
            lb.set_angle(0)
            lb.set_text(text)
        else:
            lb.set_angle(90)
            lb.set_text(text if len(text) <= maxc else text[:maxc - 1].rstrip() + "…")

    def dock_changed(self):
        self._set_vertical(self.core.dock["edge"] in ("left", "right"))
        self.refresh()
        self._place()
        self._kick()

    def _set_cursor(self, name):
        win = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), name) if name else None)

    def _on_drag_end(self, *_):
        d, self.drag = self.drag, None
        dbg("drag-end", bool(d and d["moving"]))
        if d and d["moving"]:
            self._drop()

    def _on_press(self, _g, x, y):
        self.drag = {"start": self._pointer(), "moving": False}
        dbg("press", self.drag["start"], "view", self.view)
        # los hijos con ventana propia (Stack, ScrolledWindow) se tragan el movimiento:
        # se consulta el ratón en cada cuadro mientras el botón siga pulsado
        if not getattr(self, "_drag_src", None):
            self._drag_src = GLib.timeout_add(12, self._drag_poll)

    def _drag_poll(self):
        if not self.drag:
            self._drag_src = None
            return False
        win = self.get_window()
        dev = self.get_display().get_default_seat().get_pointer()
        _, x, y, mask = win.get_device_position(dev)
        if not mask & Gdk.ModifierType.BUTTON1_MASK:
            d, self.drag = self.drag, None
            self._drag_src = None
            dbg("poll: botón suelto", d["moving"])
            if d["moving"]:
                self._drop()
            return False
        self._drag_move(x, y)
        return True

    def _on_motion(self, _w, ev):
        if not self.drag:
            return False
        self._drag_move(*self._pointer())
        return True

    def _drag_move(self, lx, ly):
        d = self.drag
        if not d["moving"]:
            if math.hypot(lx - d["start"][0], ly - d["start"][1]) < DRAG_MIN:
                return
            if (self.pw_net and self.w_entry.has_focus()) or self.we_entry.has_focus():
                self.drag = None
                return
            dbg("arrastre empieza")
            self._gdrag.set_state(Gtk.EventSequenceState.CLAIMED)   # que ningún botón reciba el clic
            w, h = self.cur
            # en la píldora se agarra por donde se pulsó; si estaba abierta, se cierra bajo el ratón
            d["off"] = ((d["start"][0] - w / 2, d["start"][1] - h / 2)
                        if self.view == "compact" else (0.0, 0.0))
            d["c"] = (self._applied[0] + d["start"][0] - d["off"][0],
                      self._applied[1] + d["start"][1] - d["off"][1])
            d["moving"] = True
            self.poff, self.pvel = [0.0, 0.0], [0.0, 0.0]
            self._set_cursor("grabbing")
            if self._hover_src:
                GLib.source_remove(self._hover_src)
                self._hover_src = None
            if self.hover:
                self._set_hover(False)
        ax, ay = self._applied[0] + lx, self._applied[1] + ly
        d["c"] = (ax - d["off"][0], ay - d["off"][1])
        mw, mh = self._mon_size()
        vertical = self._nearest_edge(*d["c"], mw, mh) in ("left", "right")
        if vertical != self.vertical:
            self._set_vertical(vertical)
            self.refresh()
        self._place()
        self.queue_draw()

    def _drop(self):
        self._drag_end = time.monotonic()
        self._set_cursor(None)
        mw, mh = self._mon_size()
        w, h = self.cur
        x0, y0 = self._last_xy
        cx, cy = x0 + w / 2, y0 + h / 2
        edge = self._nearest_edge(cx, cy, mw, mh)
        pos = cx / mw if edge in ("top", "bottom") else cy / mh
        dbg("soltada en", edge, round(pos, 2))
        self.core.set_dock(edge, pos)
        # que viaje con suavidad desde donde se soltó hasta el borde
        tx, ty = self._target_xy(w, h)
        self.poff = [x0 - tx, y0 - ty]
        self.pvel = [0.0, 0.0]
        self._layout = None
        self._place()
        self._kick()

    # ── compacta ──
    def _compact(self, left=None, icon_name=None, accent=None, text="", level=None,
                 right=None, right_text="", right_accent=None, xalign=0.0, text_accent=None, wkind=None):
        self.c_wicon.set_visible(wkind is not None)
        if wkind:
            self.c_wicon.set_kind(wkind)
        if left == "icon":
            self.c_icon.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
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

    # ── decide qué mostrar ──
    def refresh(self):
        c = self.core
        now = time.monotonic()
        m = c.media
        playing = bool(m and m["playing"])
        timer_left = (c.timer_end - now) if c.timer_end else None
        self._update_home(c, m, playing, timer_left)
        self._fill_lists()
        eq_on = False
        p = c.pomo
        pomo_on = p.active
        pomo_acc = "red" if p.phase == "work" else "green"

        if c.alert_until and now < c.alert_until:
            self.a_sub.set_text(f"Temporizador de {fmt_secs(c.timer_total)}")
            self._show("alert", (360, 64))
        elif self.card_hold and c.event and c.event.get("kind") == "card":
            c.event["until"] = max(c.event["until"], now + 2.0)   # sigue abierta mientras el ratón esté encima
            self._show_event(c.event)
        elif self.hover:
            self._show(self.page, (W_EXP, min(580, self._natural(self.page, W_EXP))))
        elif c.event and now < c.event["until"]:
            self._show_event(c.event)
        elif c.feature("deploys") and c.deploys.active():
            d = c.deploys.active()[0]
            more = len(c.deploys.active()) - 1
            self._compact("icon", "emblem-synchronizing-symbolic", "orange",
                          text=f"{d['name']} · {d['env']}" + (f" (+{more})" if more else ""),
                          right="label", right_text=fmt_secs(time.time() - d["created"]), right_accent="orange")
            nat = self._natural("compact", 0)
            self._show("compact", (max(220, min(380, nat + 4)), H))
        elif c.feature("downloads") and c.downloads.active:
            d = c.downloads.main()
            n = len(c.downloads.active)
            rate = f"{fmt_size(int(d['speed']))}/s" if d["speed"] > 1024 else fmt_size(d["size"])
            self._compact("icon", "folder-download-symbolic", "blue",
                          text=d["name"] + (f" (+{n - 1})" if n > 1 else ""),
                          right="label", right_text=rate, right_accent="blue")
            self._show("compact", (300, H))
        elif playing:
            if pomo_on:
                self._compact("art", text=m["title"], right="label", right_text=fmt_secs(p.left()),
                              right_accent=pomo_acc)
            elif timer_left is not None:
                self._compact("art", text=m["title"], right="label", right_text=fmt_secs(timer_left),
                              right_accent="orange")
            else:
                self._compact("art", text=m["title"], right="eq")
                eq_on = True
            self._show("compact", (300, H))
        elif pomo_on:
            self._compact("icon", "timer-symbolic", pomo_acc,
                          text=f"{Pomodoro.LABEL[p.phase]}  {fmt_secs(p.left())}", text_accent=pomo_acc,
                          right="label" if not p.running else None, right_text="En pausa")
            nat = self._natural("compact", 0)
            self._show("compact", (max(190, min(320, nat + 4)), H))
        elif timer_left is not None:
            self._compact("icon", "alarm-symbolic", "orange", text=fmt_secs(timer_left), xalign=0.5,
                          text_accent="orange")
            self._show("compact", (170, H))
        else:
            dot = c.unread > 0
            wd = c.weather.data if c.feature("weather") else None
            self._compact("icon" if dot else None, "preferences-system-notifications-symbolic", "red",
                          text=time.strftime("%H:%M"), xalign=0.5 if not wd else 0.0,
                          right="label" if wd else None, right_text=f"{wd['temp']:.0f}°" if wd else "",
                          wkind=wd.get("kind") if wd else None)
            self._show("compact", ((209 if dot else 189) if wd else (150 if dot else 130), H))
        if c.alert_until and now >= c.alert_until:
            c.alert_until = None
        self.c_eq.set_playing(eq_on)
        return False

    def _show_event(self, ev):
        if ev["kind"] == "card":
            if ev.get("pixbuf") is not None:
                self.k_art.set_pixbuf(ev["pixbuf"])
                self.k_left.set_visible_child_name("art")
            else:
                self.k_icon.set_from_icon_name(ev.get("icon") or "dialog-information-symbolic", Gtk.IconSize.DND)
                self.k_left.set_visible_child_name("icon")
            self.k_app.set_text(ev.get("app", ""))
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
            self._show("compact", (290, H))
        else:
            self._compact("icon", ev.get("icon"), ev.get("accent"), text=ev.get("text", ""),
                          right="label" if ev.get("right") else None, right_text=ev.get("right", ""),
                          right_accent=ev.get("right_accent"))
            nat = self._natural("compact", 0)
            self._show("compact", (max(200, min(400, nat + 4)), H))
