"""Clima detallado."""
import time

from gi.repository import Gtk

from ..ui.gtk import button, clear, icon, label, set_accent
from ..ui.widgets.charts import TempBar
from ..ui.widgets.weather_icon import WeatherIcon
from ..util.fmt import hm
from .base import Page
from .registry import feature, page

feature("weather", "Clima", "Temperatura en la píldora, página de clima y avisos de lluvia")


class WeatherPage(Page):
    """Clima: ahora, próximas horas y días, y búsqueda de ciudad."""
    PAGES = {
        "weather": page("_build_weather", "_fill_weather_page", ("weather",), "_open_weather"),
    }

    def _build_weather(self):
        box = self._page("Clima", button("ctrl", icon("view-refresh-symbolic"), self.core.weather.refresh,
                                         "Actualizar"))
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        now = Gtk.Box(spacing=14)
        self.we_icon = WeatherIcon(64, animated=True)
        now.pack_start(self.we_icon, False, False, 0)
        self.we_temp = label("—", "huge", ellipsize=False)
        now.pack_start(self.we_temp, False, False, 0)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=2)
        self.we_desc = label("", "subtitle")
        self.we_place = label("", "dim")
        self.we_range = label("", "dim")
        for w in (self.we_desc, self.we_place, self.we_range):
            info.pack_start(w, False, False, 0)
        now.pack_start(info, True, True, 0)
        body.pack_start(now, False, False, 0)

        # detalles en mosaicos
        grid = Gtk.Grid(column_spacing=6, row_spacing=6, column_homogeneous=True)
        self.we_tiles = {}
        for n, (key, title) in enumerate((("feels", "Sensación"), ("humidity", "Humedad"),
                                          ("wind", "Viento"), ("clouds", "Nubes"),
                                          ("rain", "Lluvia hoy"), ("uv", "Índice UV"),
                                          ("sunrise", "Amanecer"), ("sunset", "Atardecer"))):
            t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            t.get_style_context().add_class("wtile")
            t.pack_start(label(title, "dim small"), False, False, 0)
            v = label("—", "wtile-v")
            t.pack_start(v, False, False, 0)
            self.we_tiles[key] = v
            grid.attach(t, n % 4, n // 4, 1, 1)
        body.pack_start(grid, False, False, 0)

        body.pack_start(label("PRÓXIMAS 24 HORAS", "section"), False, False, 0)
        self.we_hours = Gtk.Box(spacing=2)
        hsw = Gtk.ScrolledWindow()
        hsw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        hsw.set_propagate_natural_height(True)
        hsw.add(self.we_hours)
        body.pack_start(hsw, False, False, 0)

        body.pack_start(label("PRÓXIMOS 7 DÍAS", "section"), False, False, 0)
        self.we_days = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        body.pack_start(self.we_days, False, False, 0)

        row = Gtk.Box(spacing=8, margin_top=4)
        self.we_entry = Gtk.Entry(hexpand=True, placeholder_text="Ciudad (p. ej. Medellín)")
        self.we_entry.connect("activate", lambda *_: self._set_city())
        row.pack_start(icon("find-location-symbolic"), False, False, 0)
        row.pack_start(self.we_entry, True, True, 0)
        row.pack_start(button("chip", cb=self._set_city, text="Cambiar"), False, False, 0)
        body.pack_start(row, False, False, 0)
        self.we_status = label("", "dim small")
        body.pack_start(self.we_status, False, False, 0)
        box.pack_start(self._scroller(body, 470), False, False, 0)
        return box

    def _fill_weather(self, w, d):
        self.we_icon.set_kind(d.get("kind", "cloudy"))
        self.we_temp.set_text(f"{d['temp']:.0f}°")
        self.we_desc.set_text(d["desc"])
        self.we_place.set_text(w.place["name"] if w.place else w.city)
        self.we_range.set_text(f"Máx {d['max']:.0f}° · Mín {d['min']:.0f}°")
        dirs = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
        wind = f"{d['wind']:.0f} km/h"
        if d.get("wind_dir") is not None:
            wind += " " + dirs[round(d["wind_dir"] / 45) % 8]
        uv = d.get("uv_max") or 0
        uv_txt = "Bajo" if uv < 3 else "Moderado" if uv < 6 else "Alto" if uv < 8 else "Muy alto" if uv < 11 else "Extremo"
        rain = f"{d['rain']}%" if d.get("rain") is not None else "—"
        if d.get("rain_mm"):
            rain += f" · {d['rain_mm']:.1f} mm"
        vals = {"feels": f"{d['feels']:.0f}°", "humidity": f"{d['humidity']}%", "wind": wind,
                "clouds": f"{d['clouds']}%" if d.get("clouds") is not None else "—",
                "rain": rain, "uv": f"{uv:.0f} {uv_txt}",
                "sunrise": d.get("sunrise", "—"), "sunset": d.get("sunset", "—")}
        for k, v in vals.items():
            self.we_tiles[k].set_text(v)
            self.we_tiles[k].set_tooltip_text(v)
        if d.get("gusts"):
            self.we_tiles["wind"].set_tooltip_text(f"{wind} · ráfagas de {d['gusts']:.0f} km/h")

        clear(self.we_hours)
        for i, hr in enumerate(d.get("hours", [])):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, margin_bottom=2)
            col.set_size_request(44, -1)
            col.pack_start(label(hr["hour"][:2] + " h", "hour", xalign=0.5,
                                 ellipsize=False), False, False, 0)
            col.pack_start(WeatherIcon(24), False, False, 0)
            col.pack_start(label(f"{hr['temp']:.0f}°", "subtitle", xalign=0.5, ellipsize=False), False, False, 0)
            pop = hr.get("pop") or 0
            col.pack_start(label(f"{pop}%" if pop >= 20 else " ", "pop", xalign=0.5, ellipsize=False),
                           False, False, 0)
            col.get_children()[1].set_kind(hr.get("kind", "cloudy"))
            self.we_hours.pack_start(col, False, False, 0)
        self.we_hours.show_all()

        clear(self.we_days)
        days = d.get("days", [])
        if days:
            wlo, whi = min(x["min"] for x in days), max(x["max"] for x in days)
            for day in days:
                row = Gtk.Box(spacing=10)
                name = label(day["name"], "subtitle", ellipsize=False)
                name.set_size_request(62, -1)
                row.pack_start(name, False, False, 0)
                ic = WeatherIcon(22)
                ic.set_kind(day["kind"])
                row.pack_start(ic, False, False, 0)
                pop = day.get("pop") or 0
                pl = label(f"{pop}%" if pop >= 20 else "", "pop", ellipsize=False)
                pl.set_size_request(34, -1)
                row.pack_start(pl, False, False, 0)
                lo = label(f"{day['min']:.0f}°", "dim", xalign=1.0, ellipsize=False)
                lo.set_size_request(30, -1)
                row.pack_start(lo, False, False, 0)
                row.pack_start(TempBar(day["min"], day["max"], wlo, whi), True, True, 0)
                hi = label(f"{day['max']:.0f}°", "subtitle", ellipsize=False)
                hi.set_size_request(30, -1)
                row.pack_start(hi, False, False, 0)
                self.we_days.pack_start(row, False, False, 0)
        self.we_days.show_all()

    def _fill_weather_page(self):
        c = self.core
        w = c.weather
        d = w.data
        if d:
            self._fill_weather(w, d)
        status = "Actualizando…" if w.loading else (w.error or
                                                     (f"Actualizado a las {hm(d['updated'])} · Open-Meteo" if d else ""))
        self.we_status.set_text(status)
        set_accent(self.we_status, "red" if w.error and not w.loading else None)

    def _set_city(self):
        text = self.we_entry.get_text().strip()
        self.host.set_focus(None)
        if text:
            self.core.weather.set_city(text)

    def _open_weather(self):
        self.we_entry.set_text("")
        w = self.core.weather
        if not w.data or time.time() - w.data["updated"] > 600:
            w.refresh()

    def typing(self):
        return self.we_entry.has_focus()
