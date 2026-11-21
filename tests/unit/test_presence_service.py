"""Servicio Presence con detector, reloj, horario y acciones falsos (sin hilos, sin cámara)."""
import copy
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.config import DEFAULTS  # noqa: E402
from isla_dinamica.services.presence import Presence  # noqa: E402

WORK = datetime(2026, 11, 20, 10, 0)      # viernes 10:00 (en horario)
NIGHT = datetime(2026, 11, 20, 22, 0)     # viernes 22:00 (fuera de horario)


class FakeConfig:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULTS)
        self.saved = 0

    def save(self):
        self.saved += 1


class FakeDetector:
    def __init__(self, result=False, ok=True):
        self.result, self.ok, self.calls = result, ok, 0
        self.error = None if ok else "Instala OpenCV"

    def available(self):
        return self.ok

    def detect(self):
        self.calls += 1
        return self.result


class ServiceTest(unittest.TestCase):
    def make(self, result=False, ok=True, enabled=True, in_call=False, busy=False, wall=WORK, epoch=1000.0,
             lock_ok=True):
        self.now = [0.0]
        self.done = []
        self.locks = 0
        self.det = FakeDetector(result, ok)
        self.cfg = FakeConfig()
        acts = {k: (lambda k=k: self.done.append(k)) for k in ("screen_off", "screen_on")}

        def lock():
            self.done.append("lock")
            return lock_ok
        acts["lock"] = lock

        def on_lock():
            self.locks += 1
        self.p = Presence(self.cfg, on_change=lambda: None, on_lock=on_lock, enabled=lambda: enabled,
                          in_call=lambda: in_call, detector=self.det, actions=acts, start=False,
                          clock=lambda: self.now[0], wall=lambda: wall, epoch=lambda: epoch,
                          camera_busy=lambda: busy, post=lambda f: f())
        return self.p

    def run_for(self, secs):
        for _ in range(int(secs)):
            self.now[0] += 1
            self.p._tick()

    def test_nobody_locks_once_and_screen_back_on_input(self):
        p = self.make(result=False)
        p._idle(0.0)                  # sin input desde -60: aviso a los 210 s, bloqueo a los 240 s
        self.run_for(200)
        self.assertEqual(p.state, "watching")
        self.run_for(15)
        self.assertEqual(p.state, "warning")
        self.assertEqual(p.seconds_left(), 25)
        self.assertGreater(self.det.calls, 0)
        self.run_for(200)
        self.assertEqual(self.locks, 1)
        self.assertEqual(self.done, ["lock", "screen_off"])
        p._active(self.now[0])
        self.assertEqual(self.done, ["lock", "screen_off", "screen_on"])

    def test_failed_lock_never_turns_screen_off(self):
        """S2: si no se pudo bloquear, apagar la pantalla dejaría la sesión abierta a oscuras."""
        p = self.make(result=False, lock_ok=False)
        p._idle(0.0)
        self.run_for(400)
        self.assertEqual(self.done, ["lock"])            # lo intentó una vez y NO apagó la pantalla
        self.assertEqual(p.state, "lock_failed")
        self.assertIn("bloquear", p.error)
        p._active(self.now[0])
        self.assertNotIn("screen_on", self.done)         # no la había apagado: nada que encender
        self.run_for(1)
        self.assertEqual(p.state, "active")

    def test_face_prevents_lock(self):
        p = self.make(result=True)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual(self.locks, 0)
        self.assertEqual(p.state, "present")
        self.assertIsNotNone(p.last_seen)

    def test_call_never_locks_nor_opens_camera(self):
        p = self.make(in_call=True)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual(self.locks, 0)
        self.assertEqual(self.det.calls, 0)

    def test_camera_busy_never_locks(self):
        p = self.make(busy=True)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual(self.locks, 0)
        self.assertEqual(self.det.calls, 0)

    def test_camera_error_never_locks(self):
        p = self.make(result=None)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual(self.locks, 0)

    def test_disabled(self):
        p = self.make(enabled=False)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual((p.state, self.locks, self.det.calls), ("off", 0, 0))

    def test_enable_after_long_idle_starts_from_zero(self):
        flag = [False]
        p = self.make()
        p.enabled = lambda: flag[0]
        p._idle(0.0)
        self.run_for(900)                 # 15 min apagado y sin input
        flag[0] = True
        self.run_for(1)
        self.assertEqual(p.state, "watching")
        self.run_for(200)
        self.assertEqual(self.locks, 0)

    def test_without_opencv(self):
        p = self.make(ok=False)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual((p.state, self.locks, self.det.calls), ("no_cv", 0, 0))
        self.assertIn("OpenCV", p.error)

    def test_off_hours(self):
        p = self.make(wall=NIGHT)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual((p.state, self.locks, self.det.calls), ("off_hours", 0, 0))

    def test_paused_and_saved(self):
        p = self.make(epoch=1000.0)
        p.pause(3600)
        self.assertEqual(self.cfg.data["presence"]["paused_until"], 4600.0)
        self.assertGreater(self.cfg.saved, 0)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual((p.state, self.locks), ("paused", 0))
        p.resume()
        self.assertEqual(self.cfg.data["presence"]["paused_until"], 0)
        self.run_for(2)
        self.assertEqual(p.state, "watching")

    def test_minutes_from_config(self):
        p = self.make()
        self.cfg.data["presence"]["minutes"] = 1
        self.assertEqual(p.check_after(), 10)     # con 1 min la cámara empieza a mirar a los 10 s
        p._idle(0.0)                  # sin input desde -10: aviso a los 20 s, bloqueo a los 50 s
        self.run_for(19)
        self.assertEqual(p.state, "watching")
        self.run_for(1)
        self.assertEqual(p.state, "warning")
        self.run_for(30)
        self.assertEqual(self.locks, 1)

    def test_set_conf_validates_and_saves(self):
        p = self.make()
        self.assertTrue(p.set_conf("minutes", 7))
        self.assertTrue(p.set_conf("start", "09:30"))
        self.assertTrue(p.set_conf("days", [0, 2]))
        self.assertFalse(p.set_conf("start", "9:3"))
        self.assertFalse(p.set_conf("minutes", 0))
        self.assertFalse(p.set_conf("otra", 1))
        c = self.cfg.data["presence"]
        self.assertEqual((c["minutes"], c["start"], c["days"]), (7, "09:30", [0, 2]))
        self.assertEqual(self.cfg.saved, 3)

    def test_check_after_default(self):
        self.assertEqual(self.make().check_after(), 60)


if __name__ == "__main__":
    unittest.main()
