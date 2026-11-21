"""Dólar: TRM de hoy, últimos 30 días y conversor USD ⇄ COP."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from ..services.fx import cop
from .registry import feature, page, tool

feature("fx", "Dólar (TRM)", "TRM del día, su variación y un conversor USD ⇄ COP")


def _num(text):
    """«1.234,5» / «1,234.5» / «1234.5» → float."""
    t = text.strip().replace("$", "").replace(" ", "")
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".") if len(t.rsplit(",", 1)[1]) != 3 else t.replace(",", "")
    elif t.count(".") == 1 and len(t.rsplit(".", 1)[1]) == 3 and len(t) > 4:
        t = t.replace(".", "")
    else:
        t = t.replace(".", "", t.count(".") - 1) if t.count(".") > 1 else t
    try:
        return float(t)
    except ValueError:
        return None


class FxPage:
    PAGES = {
        "fx": page("_build_fx", "_fill_fx", ("fx",)),
    }
    TOOLS = (tool("money-symbolic", "Dólar", "TRM y conversor USD ⇄ COP", "fx", feature="fx"),)

    def _build_fx(self):
        box = self._page("Dólar hoy", button("ctrl", icon("view-refresh-symbolic"), self.core.fx.refresh,
                                             "Actualizar"))
        top = Gtk.Box(spacing=10)
        self.fx_big = label("—", "huge")
        top.pack_start(self.fx_big, False, False, 0)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.fx_change = label("", "subtitle")
        self.fx_day = label("", "dim small")
        side.pack_start(self.fx_change, False, False, 0)
        side.pack_start(self.fx_day, False, False, 0)
        top.pack_start(side, True, True, 0)
        box.pack_start(top, False, False, 0)

        tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        tile.get_style_context().add_class("wtile")
        head = Gtk.Box()
        head.pack_start(label("Últimos 30 días", "dim small"), True, True, 0)
        self.fx_range = label("", "dim small", xalign=1.0)
        head.pack_end(self.fx_range, False, False, 0)
        tile.pack_start(head, False, False, 0)
        self.fx_spark = Spark((0.19, 0.82, 0.35), h=48)
        tile.pack_start(self.fx_spark, False, False, 0)
        box.pack_start(tile, False, False, 0)

        box.pack_start(label("CONVERTIR", "section"), False, False, 0)
        grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        self.fx_usd = Gtk.Entry(hexpand=True, placeholder_text="1", input_purpose=Gtk.InputPurpose.NUMBER)
        self.fx_cop = Gtk.Entry(hexpand=True, placeholder_text="", input_purpose=Gtk.InputPurpose.NUMBER)
        self._fx_lock = False
        self.fx_usd.connect("changed", lambda *_: self._fx_convert("usd"))
        self.fx_cop.connect("changed", lambda *_: self._fx_convert("cop"))
        for i, (name, entry) in enumerate((("USD", self.fx_usd), ("COP", self.fx_cop))):
            grid.attach(label(name, "subtitle"), 0, i, 1, 1)
            grid.attach(entry, 1, i, 1, 1)
        box.pack_start(grid, False, False, 0)
        self.fx_src = label("", "dim small")
        box.pack_start(self.fx_src, False, False, 0)
        return box

    def _fx_convert(self, frm):
        fx = self.core.fx
        if self._fx_lock or not fx.trm:
            return
        src, dst = (self.fx_usd, self.fx_cop) if frm == "usd" else (self.fx_cop, self.fx_usd)
        v = _num(src.get_text())
        self._fx_lock = True
        if v is None:
            dst.set_text("")
        elif frm == "usd":
            dst.set_text(cop(v * fx.trm)[1:])
        else:
            dst.set_text(f"{v / fx.trm:,.2f}")
        self._fx_lock = False

    def _fill_fx(self):
        fx = self.core.fx
        if not fx.trm:
            self.fx_big.set_text("—")
            self.fx_change.set_text("")
            self.fx_day.set_text("No se pudo consultar" if fx.error else "Consultando…")
            return
        self.fx_big.set_text(cop(fx.trm))
        ch = fx.change()
        if ch is None:
            self.fx_change.set_text("")
        else:
            arrow = "▲" if ch > 0 else "▼" if ch < 0 else "="
            self.fx_change.set_text(f"{arrow} {abs(ch):.2f} % · {cop(abs(fx.trm - fx.prev))}".replace(".", ",", 1))
            set_accent(self.fx_change, "red" if ch > 0 else "green" if ch < 0 else None)
        y, mo, d = (int(x) for x in fx.day.split("-"))
        self.fx_day.set_text(f"TRM vigente · {d} de {MESES[mo - 1]}")
        vals = [v for _d, v in fx.history]
        lo, hi = min(vals), max(vals)
        pad = max(1.0, (hi - lo) * 0.15)
        self.fx_spark.set_values(vals, lo - pad, hi + pad)
        self.fx_range.set_text(f"mín {cop(lo, 0)} · máx {cop(hi, 0)}")
        self.fx_cop.set_placeholder_text(cop(fx.trm)[1:])
        self._fx_convert("usd")
        self.fx_src.set_text(f"{fx.source} · actualizado {ago_long(fx.updated)}" +
                             (" · sin conexión ahora" if fx.error else ""))
