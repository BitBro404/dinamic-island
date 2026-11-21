"""Poller: temporizadores de consulta compartidos por los servicios (cada N s, «pronto» y reintentos)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.poller import Poller  # noqa: E402


class FakeLoop:
    """Imita GLib.timeout_add_seconds / source_remove: guarda los temporizadores y los dispara a mano."""

    def __init__(self):
        self.timers, self.next_id = {}, 1

    def add(self, secs, fn):
        tid, self.next_id = self.next_id, self.next_id + 1
        self.timers[tid] = (secs, fn)
        return tid

    def remove(self, tid):
        self.timers.pop(tid)

    def fire(self, secs):
        """Dispara los temporizadores de `secs` segundos; los que devuelven False se quitan."""
        for tid, (s, fn) in list(self.timers.items()):
            if s == secs and tid in self.timers and not fn():
                self.timers.pop(tid, None)


class PollerTest(unittest.TestCase):
    def setUp(self):
        self.loop, self.calls = FakeLoop(), []
        self.p = Poller(lambda: self.calls.append(1), timeout_add=self.loop.add, source_remove=self.loop.remove)

    def test_every_repeats(self):
        self.p.every(180)
        self.loop.fire(180)
        self.loop.fire(180)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.loop.timers), 1)

    def test_soon_runs_once(self):
        self.p.soon(6)
        self.loop.fire(6)
        self.loop.fire(6)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.loop.timers, {})

    def test_soon_replaces_the_pending_one(self):
        """Pedir otra vuelta cancela la anterior: nunca hay dos consultas «pronto» en cola."""
        self.p.soon(90)
        self.p.soon(30)
        self.assertEqual([s for s, _ in self.loop.timers.values()], [30])
        self.loop.fire(30)
        self.assertEqual(len(self.calls), 1)

    def test_retry_only_once_until_it_fires(self):
        self.p.retry(60)
        self.p.retry(60)
        self.assertEqual(len(self.loop.timers), 1)
        self.loop.fire(60)
        self.p.retry(60)
        self.assertEqual(len(self.loop.timers), 1)

    def test_stop(self):
        self.p.every(10)
        self.p.soon(5)
        self.p.stop()
        self.assertEqual(self.loop.timers, {})


if __name__ == "__main__":
    unittest.main()
