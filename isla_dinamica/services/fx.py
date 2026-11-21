"""Dólar en Colombia: TRM oficial (datos.gov.co) con historial; respaldo en open.er-api.com."""
import threading

import time

from gi.repository import GLib

from ..util.net import fetch_json
from ..util.proc import dbg
from .poller import Poller

TRM_URL = ("https://www.datos.gov.co/resource/32sa-8pi3.json"
           "?$select=valor,vigenciadesde&$order=vigenciadesde%20DESC&$limit=45")
SPOT_URL = "https://open.er-api.com/v6/latest/USD"
EVERY = 3 * 3600


def cop(v, decimals=2):
    """3461.92 → «$3.461,92» (formato colombiano)."""
    s = f"{v:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return "$" + s


class Fx:
    """Cotización del dólar (TRM): la consulta cada cierto tiempo y avisa del cambio del día."""
    def __init__(self, on_change, on_new_day, enabled=lambda: True):
        self.on_change, self.on_new_day, self.enabled = on_change, on_new_day, enabled
        self.trm = None          # valor de hoy
        self.prev = None         # día hábil anterior
        self.day = None          # «2026-11-21»
        self.history = []        # [(fecha, valor)] del más viejo al más nuevo
        self.source = None
        self.error = None
        self.updated = None
        self._busy = False
        self.poll = Poller(self._kick).soon(5).every(EVERY)

    def change(self):
        if self.trm and self.prev:
            return (self.trm - self.prev) / self.prev * 100
        return None

    def refresh(self):
        self._kick()

    def _kick(self):
        if self.enabled() and not self._busy:
            self._busy = True
            threading.Thread(target=self._fetch, daemon=True).start()
        return True

    def _fetch(self):
        res, err = None, None
        try:
            rows = fetch_json(TRM_URL)
            hist = {}
            for r in rows:
                hist.setdefault(r["vigenciadesde"][:10], float(r["valor"]))
            days = sorted(hist.items())
            res = {"history": days, "source": "TRM · Banco de la República"}
        except Exception as e:  # noqa: BLE001
            err = str(e)
            try:
                d = fetch_json(SPOT_URL)
                res = {"history": [(time.strftime("%Y-%m-%d"), float(d["rates"]["COP"]))],
                       "source": "open.er-api.com"}
            except Exception as e2:  # noqa: BLE001
                err = f"{err} / {e2}"
        GLib.idle_add(self._apply, res, err)

    def _apply(self, res, err):
        self._busy = False
        if not res:
            self.error = err
            dbg("fx:", err)
            self.on_change()
            self.poll.retry(120)
            return False
        self.error = None
        old_day = self.day
        self.history = res["history"][-30:]
        self.source = res["source"]
        self.day, self.trm = self.history[-1]
        self.prev = self.history[-2][1] if len(self.history) > 1 else None
        self.updated = time.time()
        self.on_change()
        if old_day and old_day != self.day:
            self.on_new_day()
        return False
