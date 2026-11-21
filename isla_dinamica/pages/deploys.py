"""Despliegues en vivo (Railway u otras plataformas que reportan a GitHub)."""
from ..common import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import feature, page, tool

feature("deploys", "Despliegues en vivo",
        "Despliegues de tus repos (Railway): progreso en la píldora y aviso al terminar")

STATE_TXT = {"SUCCESS": ("Desplegado", "green", "emblem-ok-symbolic"),
             "FAILURE": ("Falló", "red", "dialog-error-symbolic"),
             "ERROR": ("Error", "red", "dialog-error-symbolic"),
             "INACTIVE": ("Reemplazado", None, "emblem-ok-symbolic")}


class DeploysPage:
    PAGES = {
        "deploys": page("_build_deploys", "_fill_deploys", ("deploys",), "_open_deploys"),
    }
    TOOLS = (tool("emblem-synchronizing-symbolic", "Deploys", "Despliegues en vivo", "deploys", feature="deploys"),)

    def _build_deploys(self):
        dp = self.core.deploys
        box = self._page("Despliegues", button("ctrl", icon("view-refresh-symbolic"), dp.refresh, "Actualizar"))
        self.dp_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.dp_list, 400), False, False, 0)
        self.dp_status = label("", "dim small")
        box.pack_start(self.dp_status, False, False, 0)
        return box

    def _open_deploys(self):
        if time.time() - self.core.deploys.updated > 30:
            self.core.deploys.refresh()

    def _fill_deploys(self):
        dp, c = self.core.deploys, self.core
        clear(self.dp_list)
        act = dp.active()
        head = label(f"EN CURSO · {len(act)}", "section")
        self.dp_list.pack_start(head, False, False, 0)
        for d in act:
            sub = f"{d['env']} · {d['commit']} · desde hace {fmt_secs(time.time() - d['created'])}"
            self.dp_list.pack_start(self._row("emblem-synchronizing-symbolic", d["name"], sub,
                                              lambda d=d: self._collapse_then(lambda: open_uri(d["url"])),
                                              sub_accent="orange"), False, False, 0)
        if not act:
            self._empty(self.dp_list, "No hay despliegues en curso")
        head = label("RECIENTES", "section")
        head.set_margin_top(6)
        self.dp_list.pack_start(head, False, False, 0)
        for d in dp.recent():
            txt, acc, ic = STATE_TXT.get(d["state"], (d["state"].capitalize(), None, "emblem-ok-symbolic"))
            if dp.stuck(d):
                txt, acc, ic = "Sin terminar (la plataforma no avisó el final)", None, "dialog-question-symbolic"
            sub = f"{d['env']} · {txt} {ago_long(d['changed'])} · {d['commit']}"
            self.dp_list.pack_start(self._row(ic, d["name"], sub,
                                              lambda d=d: self._collapse_then(lambda: open_uri(d["url"])),
                                              sub_accent=acc), False, False, 0)
        if not dp.items:
            self._empty(self.dp_list, "Sin despliegues recientes en tus repos")
        self.dp_list.show_all()
        self.dp_status.set_text("Actualizando…" if dp.loading else dp.error or
                                (f"{len(dp.repos)} repos vigilados · {time.strftime('%H:%M', time.localtime(dp.updated))}"
                                 if dp.updated else ""))
