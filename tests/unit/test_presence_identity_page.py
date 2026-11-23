"""T5: textos y ayuda de la interfaz de identidad en la página «Presencia»."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.pages import presence as page  # noqa: E402


class IdentityPageTest(unittest.TestCase):
    def test_identity_text_without_template(self):
        text, can_clear = page._identity_text(False, 0)
        self.assertIn("Sin rostro registrado", text)
        self.assertFalse(can_clear)

    def test_identity_text_with_template_and_samples(self):
        text, can_clear = page._identity_text(True, 3)
        self.assertIn("3 muestras", text)
        self.assertTrue(can_clear)

    def test_photo_is_never_written_and_bad_frame_is_ignored(self):
        self.assertIsNone(page._frame_pixbuf(None))
        self.assertIsNone(page._frame_pixbuf(object()))

    def test_prompt_states_explained(self):
        self.assertIn("otra persona", page._identity_hint("other").lower())
        self.assertIn("no se bloquea", page._identity_hint("confirm").lower())


if __name__ == "__main__":
    unittest.main()
