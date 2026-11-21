"""Monitor del sistema: CPU, RAM y temperatura con gráfica, y procesos que más consumen."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from .registry import feature, page, tool

feature("sysmon", "Monitor del sistema",
        "CPU, RAM y temperatura; aviso si un proceso se come la CPU, falta memoria o se calienta")


def _gb(b):
    return f"{b / 1024 ** 3:.1f} GB"


class SystemPage:
    PAGES = {
        "system": page("_build_system", "_fill_system", ("sysmon",)),
    }
    TOOLS = (tool("utilities-system-monitor-symbolic", "Sistema", "CPU, RAM y temperatura", "system",
                  feature="sysmon"),)

    def _build_system(self):
        box = self._page("Sistema")
        grid = Gtk.Grid(column_spacing=6, column_homogeneous=True)
        self.sy = {}
        for i, (key, title, color) in enumerate((("cpu", "CPU", (0.04, 0.52, 1.0)),
                                                 ("ram", "Memoria", (0.75, 0.35, 0.95)),
                                                 ("temp", "Temperatura", (1.0, 0.62, 0.04)))):
            t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            t.get_style_context().add_class("wtile")
            t.pack_start(label(title, "dim small"), False, False, 0)
            v = label("—", "title")
            t.pack_start(v, False, False, 0)
            sub = label("", "dim small")
            t.pack_start(sub, False, False, 0)
            sp = Spark(color)
            t.pack_start(sp, False, False, 0)
            self.sy[key] = (v, sub, sp)
            grid.attach(t, i, 0, 1, 1)
        box.pack_start(grid, False, False, 0)
        box.pack_start(label("LO QUE MÁS CONSUME", "section"), False, False, 0)
        self.sy_top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.pack_start(self.sy_top, False, False, 0)
        foot = Gtk.Box()
        foot.pack_end(button("chip", cb=lambda: self._collapse_then(self._open_monitor), text="Monitor del sistema"),
                      False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _open_monitor(self):
        for app in ("gnome-system-monitor", "org.gnome.SystemMonitor", "mate-system-monitor", "plasma-systemmonitor"):
            if launch_desktop(app):
                return
        subprocess.Popen(["x-terminal-emulator", "-e", "top"], stderr=subprocess.DEVNULL)

    def _fill_system(self):
        m = self.core.sysmon
        if m.cpu:
            v, sub, sp = self.sy["cpu"]
            v.set_text(f"{m.cpu[-1]:.0f}%")
            sub.set_text(f"{m.ncpu} núcleos")
            sp.set_values(m.cpu, 0, 100)
            set_accent(v, "red" if m.cpu[-1] > 90 else None)
        if m.mem_total:
            v, sub, sp = self.sy["ram"]
            v.set_text(f"{100 * m.mem_used / m.mem_total:.0f}%")
            sub.set_text(f"{_gb(m.mem_used)} de {_gb(m.mem_total)}")
            sp.set_values(m.ram, 0, 100)
        v, sub, sp = self.sy["temp"]
        if m.temp:
            v.set_text(f"{m.temp[-1]:.0f}°")
            sub.set_text("CPU")
            sp.set_values(m.temp, 30, 100)
            set_accent(v, "red" if m.temp[-1] >= 90 else "orange" if m.temp[-1] >= 80 else None)
        else:
            v.set_text("—")
            sub.set_text("Sin sensor")
        clear(self.sy_top)
        for name, pct, rss in m.top[:5]:
            row = Gtk.Box(spacing=8)
            row.pack_start(label(name, "subtitle"), True, True, 0)
            row.pack_start(label(_gb(rss), "dim", ellipsize=False), False, False, 0)
            p = label(f"{pct:.0f}%", "subtitle", xalign=1.0, ellipsize=False)
            p.set_size_request(48, -1)
            set_accent(p, "orange" if pct >= 50 else None)
            row.pack_start(p, False, False, 0)
            self.sy_top.pack_start(row, False, False, 0)
        self.sy_top.show_all()
