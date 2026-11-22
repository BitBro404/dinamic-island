"""Base de las páginas del panel: lo único que una página puede usar de la ventana (segregación de interfaces).

Antes la ventana heredaba de TODAS las páginas y cada página veía (y tocaba) todo lo de la ventana y de las
demás páginas. Ahora cada página es un objeto aparte que recibe la ventana como `host` y solo usa:
  host.core, host.monitor, host.page, host.hover, host.go(), host.refresh(), host._set_hover(),
  host.set_focus() y host._art_color.
Además ofrece a sus hijas las piezas de interfaz comunes (cabecera, filas, secciones plegables…).

Ganchos que una página puede definir (todos opcionales):
  live(c, m, playing, timer_left)  se llama en cada refresco (cosas que cambian cada segundo);
  on_collapse()                    al cerrarse el panel (olvidar confirmaciones, contraseñas a medio escribir);
  typing()                         True si el usuario está escribiendo (no empezar a arrastrar la isla);
  waiting()                        True si espera un segundo clic de confirmación (no cerrar tan rápido).
"""
import subprocess

from gi.repository import GLib, Gtk

from ..ui.gtk import button, icon, label, set_accent
from ..ui.widgets.art import Art
from ..util.fmt import hm


class Page:
    """Página del panel. Recibe la ventana como `host` y solo usa la interfaz descrita arriba."""
    PAGES = {}      # nombre → registry.page(...)
    TOOLS = ()      # accesos en «Más → Herramientas»

    def __init__(self, host):
        self.host = host
        self.core = host.core

    # ── lo que la página puede pedir a la ventana ──
    @property
    def monitor(self):
        return self.host.monitor

    @property
    def hover(self):
        return self.host.hover

    def go(self, page):
        self.host.go(page)

    def refresh(self):
        self.host.refresh()

    def _set_hover(self, value):
        self.host._set_hover(value)

    def _collapse_then(self, fn):
        """Cierra el panel y después hace `fn` (abrir una app, una URL…)."""
        self.host._set_hover(False)
        fn()

    def _settings(self, panel):
        """Abre un panel de la configuración del sistema con la app de este escritorio."""
        from ..platform.apps import settings_command
        from ..platform.chain import Tools

        argv = settings_command(panel, Tools(), self.core.desktop)
        if argv:
            subprocess.Popen(argv, stderr=subprocess.DEVNULL)
        self.host._set_hover(False)

    def _copy(self, text):
        self.core.clip.copy(text)
        self.host._set_hover(False)
        self.core.show_event(1.5, kind="pill", icon="edit-copy-symbolic", accent="green", text="Copiado")

    # ── ganchos (por defecto no hacen nada) ──
    def live(self, c, m, playing, timer_left):
        pass

    def on_collapse(self):
        pass

    def typing(self):
        return False

    def waiting(self):
        """True si espera una confirmación (entonces el panel tarda más en cerrarse al salir el ratón)."""
        return False

    # ── piezas de interfaz comunes ──
    def _page(self, title, right=None):
        """Caja de una página con su cabecera: volver, título, hora y (opcional) un control a la derecha."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_start=16, margin_end=16, margin_top=12, margin_bottom=14)
        head = Gtk.Box(spacing=6)
        head.pack_start(button("ctrl", icon("go-previous-symbolic"), lambda: self.go("home"), "Volver"),
                        False, False, 0)
        head.pack_start(label(title, "title"), True, True, 0)
        clk = label(hm(), "c-time", ellipsize=False)
        clk.set_valign(Gtk.Align.CENTER)
        self.host.page_clocks.append(clk)          # la ventana las pone en hora mientras el panel está abierto
        if right is not None:
            right.set_valign(Gtk.Align.CENTER)
            head.pack_end(right, False, False, 0)
            head.pack_end(clk, False, False, 4)
        else:
            head.pack_end(clk, False, False, 0)
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
        """Cambia el interruptor sin disparar su callback (para reflejar el estado real)."""
        if sw.get_active() != value:
            sw.handler_block(sw._cb)
            sw.set_active(value)
            sw.handler_unblock(sw._cb)

    @staticmethod
    def _row(ic, title, sub=None, cb=None, extra=None, pixbuf=None, sub_accent=None):
        """Fila de lista: icono o imagen, título, subtítulo (con color opcional), clic y botones extra."""
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

    def _fold(self, box, key, title, total, today=0, refill=None, top=True):
        """Encabezado de sección plegable (se recuerda en config «collapsed»); devuelve True si está abierta.
        `today`: novedades del día, en un contador azul visible aunque la sección esté plegada.
        `refill`: función que vuelve a dibujar la página al plegar/desplegar."""
        closed = key in self.core.config.data["collapsed"]
        row = Gtk.Box(spacing=6)
        row.pack_start(icon("pan-end-symbolic" if closed else "pan-down-symbolic", px=12), False, False, 0)
        row.pack_start(label(f"{title} · {total}", "section"), False, False, 0)
        if today:
            b = label(f"{today}  hoy", "badge new", ellipsize=False, xalign=0.5)
            b.set_valign(Gtk.Align.CENTER)
            row.pack_end(b, False, False, 0)
        head = button("sechead", row, lambda: self._fold_toggle(key, refill), "Mostrar" if closed else "Ocultar")
        if top:
            head.set_margin_top(4)
        box.pack_start(head, False, False, 0)
        return not closed

    def _fold_toggle(self, key, refill):
        cfg = self.core.config
        cur = cfg.data["collapsed"]
        cfg.data["collapsed"] = [k for k in cur if k != key] if key in cur else cur + [key]
        cfg.save()
        if refill:
            GLib.idle_add(lambda: refill() and False)   # no destruir el botón dentro de su propio clic

    @staticmethod
    def _empty(box, text):
        """Texto gris centrado para una lista vacía."""
        lb = label(text, "dim", xalign=0.5)
        lb.set_margin_top(10)
        lb.set_margin_bottom(10)
        box.pack_start(lb, False, False, 0)
