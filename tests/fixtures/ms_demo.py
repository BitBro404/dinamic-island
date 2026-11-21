"""Teams y correo con avisos falsos (2 de hoy, 1 de ayer) y «Correo» plegado. No toca ~/.config."""
import time

from isla_dinamica.util.links import TEAMS_APP


def setup(core):
    core.config.save = lambda: None
    core.config.data["collapsed"] = ["ms_outlook"]
    now = time.time()

    def n(kind, summary, body, ago):
        return {"id": 0, "ms": kind, "app": "Microsoft Teams" if kind == "teams" else "Outlook",
                "icon": TEAMS_APP if kind == "teams" else "mail-unread-symbolic", "pixbuf": None,
                "summary": summary, "body": body, "desktop": "", "time": now - ago, "urgent": False}
    core.notifs[:0] = [n("teams", "Ana (QA)", "¿Subiste el fix a qa?", 300),
                       n("outlook", "Railway", "Deploy failed: wmservice-backend", 3600),
                       n("teams", "Equipo WM", "Reunión movida a las 4", 30 * 3600)]
    core.ms_unread = {"teams": 2, "outlook": 1}
    core.changed("notifs")
