"""Texto de estado de la casilla rápida «Presencia»."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.presence import presence_label  # noqa: E402


class LabelTest(unittest.TestCase):
    def test_labels(self):
        cases = {"off": "Apagado", "no_cv": "Sin OpenCV", "off_hours": "Fuera de horario", "paused": "En pausa",
                 "active": "Vigilando", "watching": "Vigilando", "present": "Te ve", "warning": "Bloqueando",
                 "locked": "Bloqueado"}
        for state, text in cases.items():
            self.assertEqual(presence_label(state), text, state)

    def test_unknown(self):
        self.assertEqual(presence_label("raro"), "")


if __name__ == "__main__":
    unittest.main()
