"""Saludo de inicio/desbloqueo: la hora ya va fija en la isla, el saludo no la repite."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.core import Core  # noqa: E402


class FakeCore:
    def __init__(self, battery):
        self.battery = battery
        self.events = []

    def show_event(self, secs=3.0, **ev):
        self.events.append(ev)


class WelcomeTest(unittest.TestCase):
    def test_hello_has_no_time_on_the_right(self):
        core = FakeCore(NS(present=True, percent=80))
        Core.welcome(core)
        self.assertTrue(core.events[0]["text"].startswith("Hola, "))
        self.assertNotIn("right", core.events[0])

    def test_welcome_back_shows_battery_not_time(self):
        core = FakeCore(NS(present=True, percent=64.4))
        Core.welcome(core, back=True)
        self.assertEqual(core.events[0]["right"], "64%")

    def test_welcome_back_without_battery_has_nothing_on_the_right(self):
        core = FakeCore(NS(present=False, percent=0))
        Core.welcome(core, back=True)
        self.assertNotIn("right", core.events[0])


if __name__ == "__main__":
    unittest.main()
