"""Servidores de desarrollo locales: abrir en el navegador, detenerlos, relanzarlos y volver a arrancar los
detenidos (la isla recuerda su carpeta y su comando)."""
import os
import shlex

from gi.repository import GLib, Gtk

from ..ui.gtk import button, clear, icon, label
from ..util.fmt import ago, hm
from ..util.safety import open_web
from .base import Page
from .registry import feature, page, tool

feature("servers", "Servidores locales",
        "Servidores de desarrollo en este equipo: abrirlos, detenerlos, relanzarlos y aviso si se caen")


class ServersPage(Page):
    """Servidores: servidores de desarrollo locales y sus puertos."""
    PAGES = {
        "servers": page("_build_servers", "_fill_servers", ("servers",), "_open_servers"),
    }
    TOOLS = (tool("network-server-symbolic", "Servidores", "Servidores locales", "servers", feature="servers"),)

    def _build_servers(self):
        self.sv_scan = button("ctrl", icon("view-refresh-symbolic"), self._sv_scan,
                              "Escanear puertos ahora (servidores y Docker)")
        box = self._page("Servidores locales", self.sv_scan)
        self.sv_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.sv_list, 380), False, False, 0)
        self.sv_hint = label("", "dim small", xalign=0.5)
        box.pack_start(self.sv_hint, False, False, 0)
        self._sv_confirm = None
        return box

    def _open_servers(self):
        self._sv_confirm = None
        self.core.servers.refresh()

    def _sv_scan(self):
        self._sv_confirm = None
        self.sv_scan.set_sensitive(False)
        self.sv_hint.set_text("Escaneando puertos…")
        self.core.servers.scan(self._sv_scanned)

    def _sv_scanned(self, found):
        self.sv_scan.set_sensitive(True)
        if found is None:
            self.sv_hint.set_text("⚠ No se pudo escanear (falta «ss»)")
        else:
            self.sv_hint.set_text("Escaneo hecho · " + ("nada escuchando" if not found else
                                                       f"{found} servidor{'es' if found != 1 else ''}"))
        GLib.timeout_add(4000, self._sv_clear_hint, self.sv_hint.get_text())

    def _sv_clear_hint(self, text):
        if self.sv_hint.get_text() == text:
            self.sv_hint.set_text("")
        return False

    def _sv_ask(self, key, text):
        """Primer clic: pide confirmación (6 s). → True si ya estaba confirmada (segundo clic)."""
        if self._sv_confirm != key:
            self._sv_confirm = key
            self.sv_hint.set_text(text)
            GLib.timeout_add(6000, self._sv_reset, key)
            return False
        self._sv_confirm = None
        self.sv_hint.set_text("")
        return True

    def _sv_stop(self, port):
        if self._sv_ask(("stop", port), f"Vuelve a pulsar ■ para detener el servidor del puerto {port}"):
            self.core.servers.stop(port)

    def _sv_restart(self, port):
        if self._sv_ask(("restart", port), f"Vuelve a pulsar ↻ para reiniciar el servidor del puerto {port}"):
            if not self.core.servers.restart(port):
                self.sv_hint.set_text("No sé cómo se arrancó este servidor")

    def _sv_docker(self, key, verb):
        name = key.split(":", 1)[1]
        if verb == "stop" and self._sv_ask(("dstop", key), f"Vuelve a pulsar ■ para detener {name} (docker stop)"):
            self.core.servers.docker_stop(key)
        elif verb == "restart" and self._sv_ask(("drestart", key),
                                                f"Vuelve a pulsar ↻ para reiniciar {name} (docker restart)"):
            self.core.servers.docker_restart(key)

    def _sv_relaunch(self, index):
        ok, msg = self.core.servers.relaunch(index)
        self.sv_hint.set_text(msg if ok else f"⚠ {msg}")

    def _sv_forget(self, index):
        self._sv_confirm = None
        self.sv_hint.set_text("")
        self.core.servers.forget(index)

    def _sv_reset(self, port):
        if self._sv_confirm == port:
            self._sv_confirm = None
            self.sv_hint.set_text("")
        return False

    def _fill_servers(self):
        sv = self.core.servers
        clear(self.sv_list)
        stopped = sv.stopped()
        rows = sv.all()
        if rows and stopped:
            self.sv_list.pack_start(label(f"CORRIENDO · {len(rows)}", "section"), False, False, 0)
        for s in rows:
            if s.get("docker"):
                self.sv_list.pack_start(self._sv_docker_row(s), False, False, 0)
                continue
            sub = f":{s['port']} · {s['kind']}"
            if s["started"]:
                sub += f" · desde las {hm(s['started'])}"
            extra = [button("ctrl", icon("web-browser-symbolic"), lambda u=s["url"]: self._collapse_then(
                lambda: open_web(u)), "Abrir en el navegador")]
            if s["mine"]:
                if s.get("launch"):
                    extra.append(button("ctrl", icon("view-refresh-symbolic"), lambda p=s["port"]: self._sv_restart(p),
                                        "Reiniciar: detener y volver a lanzar " + shlex.join(s["launch"])))
                extra.append(button("ctrl", icon("process-stop-symbolic"), lambda p=s["port"]: self._sv_stop(p),
                                    "Detener (pide confirmación); la isla recuerda el comando"))
            row = self._row("network-server-symbolic", s["name"], sub, None, extra,
                            sub_accent="green" if s["mine"] else None)
            if s.get("launch"):
                row.set_tooltip_text(f"{shlex.join(s['launch'])}\nen {s['cwd']}")
            self.sv_list.pack_start(row, False, False, 0)
        if not rows:
            self._empty(self.sv_list, "No hay servidores de desarrollo corriendo")
        if stopped:
            self.sv_list.pack_start(label(f"DETENIDOS · {len(stopped)}", "section"), False, False, 0)
        for i, r in stopped:
            if r.get("docker"):
                self.sv_list.pack_start(self._sv_docker_stopped(i, r), False, False, 0)
                continue
            folder = os.path.basename(r["cwd"].rstrip("/")) or r["cwd"]
            sub = " · ".join(x for x in (f":{r['port']}" if r.get("port") else "", folder,
                                         ago(r["when"]) if r.get("when") else "") if x)
            extra = [button("ctrl", icon("media-playback-start-symbolic"), lambda i=i: self._sv_relaunch(i),
                            "Relanzar " + shlex.join(r["argv"])),
                     button("ctrl", icon("window-close-symbolic"), lambda i=i: self._sv_forget(i), "Olvidar")]
            row = self._row("network-server-symbolic", r.get("name") or folder, sub, None, extra)
            row.set_tooltip_text(f"{shlex.join(r['argv'])}\nen {r['cwd']}")
            self.sv_list.pack_start(row, False, False, 0)
        self.sv_list.show_all()

    def _sv_docker_row(self, g):
        n = len(g["containers"])
        parts = [f":{g['port']}" if g["port"] else "", g["kind"],
                 ", ".join(g["services"]) if n <= 3 else f"{n} contenedores"]
        extra = []
        if g["url"]:
            extra.append(button("ctrl", icon("web-browser-symbolic"), lambda u=g["url"]: self._collapse_then(
                lambda: open_web(u)), "Abrir en el navegador"))
        extra.append(button("ctrl", icon("view-refresh-symbolic"), lambda k=g["key"]: self._sv_docker(k, "restart"),
                            "Reiniciar (docker restart)"))
        extra.append(button("ctrl", icon("process-stop-symbolic"), lambda k=g["key"]: self._sv_docker(k, "stop"),
                            "Detener (docker stop); la isla lo recuerda para volver a arrancarlo"))
        row = self._row("application-x-addon-symbolic", g["name"], " · ".join(p for p in parts if p), None, extra,
                        sub_accent="green")
        row.set_tooltip_text("Contenedores: " + ", ".join(g["containers"]) +
                             (f"\nPuertos: {', '.join(map(str, g['ports']))}" if g["ports"] else ""))
        return row

    def _sv_docker_stopped(self, i, r):
        n = len(r["docker"])
        sub = " · ".join(x for x in (f":{r['port']}" if r.get("port") else "", (r.get("kind") or "Docker").replace("Docker Compose", "Compose"),
                                     f"{n} contenedor{'es' if n != 1 else ''}",
                                     ago(r["when"]) if r.get("when") else "") if x)
        extra = [button("ctrl", icon("media-playback-start-symbolic"), lambda i=i: self._sv_relaunch(i),
                        "Arrancar (docker start)"),
                 button("ctrl", icon("window-close-symbolic"), lambda i=i: self._sv_forget(i), "Olvidar")]
        row = self._row("application-x-addon-symbolic", r["name"], sub, None, extra)
        row.set_tooltip_text("docker start " + " ".join(r["docker"]))
        return row
