"""U3.3: inactividad por proceso (swayidle) o por sondeo, con la misma interfaz on_idle/on_active."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.chain import Method, Tools  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.platform.idle import IdleWatch, METHODS, poll_step  # noqa: E402

X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"})
WLR = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "sway"})

POLL = [Method("sondeo", lambda t, d: True, "poll")]


class IdleTest(unittest.TestCase):
    def test_swayidle_is_first_on_wlroots(self):
        t = Tools(which=lambda c: c if c == "swayidle" else None)
        self.assertEqual([m.name for m in METHODS if m.ok(t, WLR)][0], "swayidle")

    def test_x11_uses_polling(self):
        t = Tools(which=lambda c: None)
        self.assertIn("XScreenSaver", [m.name for m in METHODS if m.ok(t, X11)])

    def test_poll_step_is_pure(self):
        self.assertEqual(poll_step(60, False, 59_000), False)
        self.assertEqual(poll_step(60, False, 60_000), True)
        self.assertEqual(poll_step(60, True, 59_000), False)

    def test_polling_watch_uses_injected_clock_and_idle_ms(self):
        events = []
        ms = [0]
        w = IdleWatch(60, lambda t: events.append(("idle", t)), lambda t: events.append(("active", t)),
                      methods=POLL, idle_ms=lambda: ms[0], clock=lambda: 100.0, start=False)
        self.assertTrue(w.supported)
        w.poll_step()
        ms[0] = 60_000
        w.poll_step()
        w.poll_step()                       # no repite el aviso
        ms[0] = 1_000
        w.poll_step()
        self.assertEqual(events, [("idle", 100.0), ("active", 100.0)])

    def test_no_method_does_not_break(self):
        events = []
        w = IdleWatch(60, lambda t: events.append("idle"), lambda t: events.append("active"),
                      methods=[], start=False)
        self.assertFalse(w.supported)
        self.assertIsNotNone(w.error)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
