"""Lógica del sensor de presencia: reloj falso, sin cámara ni GTK."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.presence import CHECK_EVERY, PresenceLogic  # noqa: E402


def run_until(lg, start, end, scheduled=True):
    """Avanza segundo a segundo y devuelve {estado: primer instante en que apareció}."""
    first = {}
    for t in range(start, end + 1):
        first.setdefault(lg.step(t, scheduled), t)
    return first


class LogicTest(unittest.TestCase):
    def setUp(self):
        self.lg = PresenceLogic(minutes=5, warn=30, check_after=60)

    def test_active_while_input(self):
        self.assertEqual(self.lg.step(10), "active")
        self.assertFalse(self.lg.needs_check(10))
        self.assertIsNone(self.lg.seconds_left(10))

    def test_no_face_goes_watching_warning_lock(self):
        self.lg.input_idle(100)           # sin input desde t=40
        first = run_until(self.lg, 100, 400)
        self.assertEqual(first["watching"], 100)
        self.assertEqual(first["warning"], 310)
        self.assertEqual(first["lock"], 340)
        self.assertEqual(self.lg.step(500), "locked")

    def test_lock_fires_once(self):
        self.lg.input_idle(100)
        states = [self.lg.step(t) for t in range(100, 600)]
        self.assertEqual(states.count("lock"), 1)

    def test_face_restarts_countdown(self):
        self.lg.input_idle(100)
        self.lg.face(200, True)
        first = run_until(self.lg, 200, 600)
        self.assertEqual(first["present"], 200)
        self.assertEqual(first["warning"], 470)
        self.assertEqual(first["lock"], 500)

    def test_busy_camera_counts_as_present(self):
        self.lg.input_idle(100)
        self.lg.face(300, False, busy=True)
        self.assertEqual(self.lg.step(320), "present")
        self.assertEqual(self.lg.step(339), "present")

    def test_input_cancels_warning_and_unlocks(self):
        self.lg.input_idle(100)
        self.assertEqual(self.lg.step(320), "warning")
        self.lg.input_active(321)
        self.assertEqual(self.lg.step(321), "active")
        self.lg.input_idle(400)
        self.assertEqual(self.lg.step(400), "watching")

    def test_after_lock_input_rearms(self):
        self.lg.input_idle(100)
        run_until(self.lg, 100, 400)
        self.lg.input_active(401)
        self.lg.input_idle(500)
        first = run_until(self.lg, 500, 800)
        self.assertEqual(first["lock"], 740)

    def test_pause(self):
        self.lg.input_idle(100)
        self.lg.pause_until(1000)
        self.assertEqual(self.lg.step(500), "paused")
        self.assertFalse(self.lg.needs_check(500))
        # al reanudar empieza de cero (no bloquea al instante)
        self.assertEqual(self.lg.step(1000), "watching")
        self.assertEqual(run_until(self.lg, 1000, 1400)["lock"], 1300)

    def test_resume_early(self):
        self.lg.pause_until(1000)
        self.lg.pause_until(0)
        self.assertEqual(self.lg.step(10), "active")

    def test_needs_check_every_interval(self):
        self.lg.input_idle(100)
        self.lg.step(100)
        self.assertTrue(self.lg.needs_check(100))
        self.lg.face(100, False)
        self.assertFalse(self.lg.needs_check(100 + CHECK_EVERY - 1))
        self.assertTrue(self.lg.needs_check(100 + CHECK_EVERY))

    def test_seconds_left(self):
        self.lg.input_idle(100)
        self.lg.step(310)
        self.assertEqual(self.lg.seconds_left(310), 30)
        self.assertEqual(self.lg.seconds_left(330), 10)

    def test_off_hours(self):
        self.lg.input_idle(100)
        self.assertEqual(self.lg.step(500, scheduled=False), "off_hours")
        self.assertFalse(self.lg.needs_check(500))
        # al entrar en horario, aunque lleve 10 min sin input, empieza de cero
        self.assertEqual(self.lg.step(700, scheduled=True), "watching")
        self.assertEqual(run_until(self.lg, 700, 1100)["warning"], 970)


if __name__ == "__main__":
    unittest.main()
