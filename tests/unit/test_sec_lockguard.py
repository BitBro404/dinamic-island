"""S5: con la sesión bloqueada la isla se oculta (no debe verse ni usarse encima del bloqueo)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.lockguard import LockGuard  # noqa: E402


class LockGuardTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.g = LockGuard(set_visible=lambda v: self.calls.append(("visible", v)),
                           on_lock=lambda: self.calls.append(("wipe",)))

    def test_lock_hides_and_wipes_once(self):
        self.g.set_locked(True)
        self.g.set_locked(True)
        self.assertTrue(self.g.locked)
        self.assertEqual(self.calls, [("visible", False), ("wipe",)])

    def test_unlock_shows_again(self):
        self.g.set_locked(True)
        self.g.set_locked(False)
        self.assertEqual(self.calls[-1], ("visible", True))
        self.assertFalse(self.g.locked)

    def test_unlock_without_lock_does_nothing(self):
        self.g.set_locked(False)
        self.assertEqual(self.calls, [])

    def test_temporary_hide_does_not_reveal_while_locked(self):
        """Capturas y grabación ocultan la isla un momento; al terminar no deben mostrarla si hay bloqueo."""
        self.g.set_locked(True)
        self.calls.clear()
        self.g.request_visible(True)
        self.assertEqual(self.calls, [])
        self.g.request_visible(False)
        self.assertEqual(self.calls, [("visible", False)])

    def test_temporary_hide_works_when_unlocked(self):
        self.g.request_visible(False)
        self.g.request_visible(True)
        self.assertEqual(self.calls, [("visible", False), ("visible", True)])


if __name__ == "__main__":
    unittest.main()
