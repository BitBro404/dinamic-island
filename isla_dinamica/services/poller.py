"""Poller: los temporizadores de consulta que comparten los servicios (GitHub, despliegues, clima, dólar, git).

Antes cada servicio repetía su propio `_schedule`/`_tick` con GLib. Ahora todos usan las mismas tres formas:
  every(s)  consultar cada `s` segundos, para siempre;
  soon(s)   consultar una vez dentro de `s` segundos (reemplaza la vuelta «pronto» pendiente);
  retry(s)  reintentar tras un fallo (como mucho un reintento en cola).
`timeout_add`/`source_remove` se inyectan para probarlo sin bucle de GLib (inversión de dependencias).
"""
from gi.repository import GLib


class Poller:
    """Temporizadores de consulta: every / soon / retry / stop."""
    def __init__(self, fetch, timeout_add=GLib.timeout_add_seconds, source_remove=GLib.source_remove):
        self.fetch = fetch
        self._add, self._remove = timeout_add, source_remove
        self._every = self._soon = self._retry = None

    def every(self, secs):
        """Llama a `fetch` cada `secs` segundos."""
        if self._every:
            self._remove(self._every)
        self._every = self._add(secs, self._on_every)
        return self

    def soon(self, secs):
        """Llama a `fetch` una sola vez dentro de `secs` segundos; cancela la vuelta «pronto» anterior."""
        if self._soon:
            self._remove(self._soon)
        self._soon = self._add(secs, self._on_soon)
        return self

    def retry(self, secs):
        """Reintento tras un error: si ya hay uno en cola, no se agrega otro."""
        if not self._retry:
            self._retry = self._add(secs, self._on_retry)
        return self

    def stop(self):
        for attr in ("_every", "_soon", "_retry"):
            tid = getattr(self, attr)
            if tid:
                self._remove(tid)
                setattr(self, attr, None)

    def _on_every(self):
        self.fetch()
        return True

    def _on_soon(self):
        self._soon = None
        self.fetch()
        return False

    def _on_retry(self):
        self._retry = None
        self.fetch()
        return False
