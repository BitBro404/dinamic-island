"""Servidores de desarrollo locales: abrir en el navegador o detenerlos."""
from ..common import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import feature, page, tool

feature("servers", "Servidores locales",
        "Servidores de desarrollo en este equipo: abrirlos, detenerlos y aviso si se caen")


class ServersPage:
    PAGES = {
        "servers": page("_build_servers", "_fill_servers", ("servers",), "_open_servers"),
    }
    TOOLS = (tool("network-server-symbolic", "Servidores", "Servidores locales", "servers", feature="servers"),)

    def _build_servers(self):
        box = self._page("Servidores locales")
        self.sv_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.sv_list, 380), False, False, 0)
        self.sv_hint = label("", "dim small", xalign=0.5)
        box.pack_start(self.sv_hint, False, False, 0)
        self._sv_confirm = None
        return box

    def _open_servers(self):
        self._sv_confirm = None
        self.core.servers.refresh()

    def _sv_stop(self, port):
        if self._sv_confirm != port:
            self._sv_confirm = port
            self.sv_hint.set_text(f"Vuelve a pulsar ■ para detener el servidor del puerto {port}")
            GLib.timeout_add(6000, self._sv_reset, port)
            return
        self._sv_confirm = None
        self.sv_hint.set_text("")
        self.core.servers.stop(port)

    def _sv_reset(self, port):
        if self._sv_confirm == port:
            self._sv_confirm = None
            self.sv_hint.set_text("")
        return False

    def _fill_servers(self):
        sv = self.core.servers
        clear(self.sv_list)
        for s in sv.sorted():
            sub = f":{s['port']} · {s['kind']}"
            if s["started"]:
                sub += f" · desde las {hm(s['started'])}"
            extra = [button("ctrl", icon("web-browser-symbolic"), lambda u=s["url"]: self._collapse_then(
                lambda: open_uri(u)), "Abrir en el navegador")]
            if s["mine"]:
                extra.append(button("ctrl", icon("process-stop-symbolic"), lambda p=s["port"]: self._sv_stop(p),
                                    "Detener (pide confirmación)"))
            self.sv_list.pack_start(self._row("network-server-symbolic", s["name"], sub, None, extra,
                                              sub_accent="green" if s["mine"] else None), False, False, 0)
        if not sv.items:
            self._empty(self.sv_list, "No hay servidores de desarrollo corriendo")
        self.sv_list.show_all()
