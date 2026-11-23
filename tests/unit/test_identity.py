"""T1–T3: modelos verificados, galería local y bandas de decisión (sin cámara ni red)."""
import hashlib
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services import identity  # noqa: E402

BODY = b"modelo de prueba de tamano conocido"
SHA = hashlib.sha256(BODY).hexdigest()
SPECS = {"mini": ("mini.onnx", len(BODY), SHA, "https://example.test/mini.onnx")}


class FakeFetch:
    def __init__(self, data=BODY, fail=False):
        self.data, self.fail, self.calls = data, fail, 0

    def __call__(self, url, timeout=10):
        self.calls += 1
        if self.fail:
            raise OSError("sin red")
        return self.data


class ModelsTest(unittest.TestCase):
    def test_published_hashes_are_complete_sha256(self):
        for key, (_name, _size, sha, _url) in identity.MODELS.items():
            with self.subTest(model=key):
                self.assertRegex(sha, r"^[0-9a-f]{64}$")

    def test_download_verifies_and_uses_private_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            paths = identity.ensure_models(fetch=FakeFetch(), directory=d, models=SPECS)
            path = paths["mini"]
            self.assertTrue(os.path.isfile(path))
            with open(path, "rb") as f:
                self.assertEqual(f.read(), BODY)
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(d).st_mode), 0o700)

    def test_bad_hash_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(identity.ModelError):
                identity.ensure_models(fetch=FakeFetch(data=b"otro"), directory=d, models=SPECS)
            self.assertEqual(os.listdir(d), [])

    def test_existing_valid_model_is_not_downloaded_again(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mini.onnx")
            with open(path, "wb") as f:
                f.write(BODY)
            fetch = FakeFetch()
            identity.ensure_models(fetch=fetch, directory=d, models=SPECS)
            self.assertEqual(fetch.calls, 0)

    def test_network_error_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(identity.ModelError):
                identity.ensure_models(fetch=FakeFetch(fail=True), directory=d, models=SPECS)
            self.assertEqual(os.listdir(d), [])


class FakeRecognizer:
    """Devuelve el «rasgo» directamente como puntuación; sin OpenCV."""

    def __init__(self, fails=False):
        self.fails, self.matched = fails, []

    def alignCrop(self, frame, face):
        return face

    def feature(self, aligned):
        if self.fails:
            raise RuntimeError("cámara rota")
        return [float(aligned[0])]

    def match(self, a, b, dis_type=0):
        self.matched.append((a, b))
        return float(a[0])


class GalleryTest(unittest.TestCase):
    def make(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return identity.Gallery(os.path.join(d.name, "identity", "gallery.json"))

    def test_empty_gallery_is_not_enrolled(self):
        g = self.make()
        self.assertFalse(g.enrolled)
        self.assertEqual(g.templates, [])

    def test_add_sets_anchor_and_rotates_limiting_samples(self):
        g = self.make()
        g.add([0.1], when=1)
        g.add([0.2], when=2)
        for i in range(3, 10):
            g.add([float(i)], when=i)
        self.assertTrue(g.enrolled)
        self.assertEqual(g.templates[0], [0.1])
        self.assertEqual(len(g.templates), 1 + identity.MAX_ROTATING)
        self.assertEqual(g.templates[1], [5.0])          # descarta las más antiguas
        path = g.path
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode), 0o700)
        with open(path, encoding="utf-8") as f:
            data = f.read()
        self.assertIn("embedding", data)
        self.assertNotIn("image", data)
        self.assertNotIn("frame", data)

    def test_clear_removes_file_and_enrollment(self):
        g = self.make()
        g.add([0.3])
        g.clear()
        self.assertFalse(g.enrolled)
        self.assertFalse(os.path.exists(g.path))

    def test_corrupt_file_is_ignored(self):
        g = self.make()
        os.makedirs(os.path.dirname(g.path), exist_ok=True)
        with open(g.path, "w", encoding="utf-8") as f:
            f.write("{'no es json':")
        self.assertFalse(identity.Gallery(g.path).enrolled)

    def test_corrupt_sample_metadata_is_ignored(self):
        import json
        g = self.make()
        g.add([0.4])
        os.makedirs(os.path.dirname(g.path), exist_ok=True)
        with open(g.path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "anchor": [0.4],
                       "samples": [{"embedding": [0.5], "when": "no-es-fecha"}]}, f)
        loaded = identity.Gallery(g.path)
        self.assertEqual(loaded.samples[0]["when"], 0.0)

    def test_next_sample_at_persists(self):
        g = self.make()
        g.next_sample_at = 1234.0
        self.assertEqual(identity.Gallery(g.path).next_sample_at, 1234.0)


class VerifierTest(unittest.TestCase):
    def make(self, enrolled=True, fails=False):
        g = identity.Gallery(os.path.join(tempfile.mkdtemp(), "gallery.json"))
        if enrolled:
            g.add([0.5])
        self.addCleanup(lambda: g.clear())
        rec = FakeRecognizer(fails=fails)
        return identity.IdentityVerifier(g, recognizer=rec), rec

    def test_threshold_bands(self):
        v, _ = self.make()
        self.assertEqual(v.verify(None, [[0.9, 0, 10, 10]]), "me")
        v, _ = self.make()
        self.assertEqual(v.verify(None, [[0.1, 0, 10, 10]]), "other")
        v, _ = self.make()
        self.assertEqual(v.verify(None, [[0.3, 0, 10, 10]]), "unknown")

    def test_best_of_several_faces_and_enrollment_uses_largest(self):
        v, rec = self.make()
        label, feature = v.inspect(None, [[0.2, 0, 10, 10], [0.95, 0, 40, 40]])
        self.assertEqual((label, feature), ("me", [0.95]))
        self.assertEqual(v.enroll_feature(None, [[0.2, 0, 10, 10], [0.95, 0, 40, 40]]), [0.95])

    def test_no_face_not_enrolled_or_error_is_unknown(self):
        v, _ = self.make()
        self.assertEqual(v.verify(None, []), "unknown")
        v, _ = self.make(enrolled=False)
        self.assertEqual(v.verify(None, [[0.9, 0, 10, 10]]), "unknown")
        v, _ = self.make(fails=True)
        self.assertEqual(v.verify(None, [[0.9, 0, 10, 10]]), "unknown")


class DecideTest(unittest.TestCase):
    def test_mapping_to_presence_logic(self):
        cases = (
            (("me", True, False, True), (True, False)),
            (("other", True, False, True), (False, False)),
            (("unknown", True, False, True), (False, True)),
            (("me", True, True, True), (False, True)),       # llamada o cámara ocupada manda
            (("me", True, False, False), (True, False)),     # sin plantilla: modo actual
            ((None, True, False, False), (True, False)),
            ((None, False, False, False), (False, False)),
            ((None, None, True, False), (False, True)),      # sin datos: no bloquea
        )
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(identity.decide(*args), expected)


class LabelTest(unittest.TestCase):
    def test_new_identity_states_have_labels(self):
        from isla_dinamica.services.presence import presence_label
        self.assertEqual(presence_label("other"), "Otra persona")
        self.assertEqual(presence_label("confirm"), "¿Eras tú?")


class DailySampleTest(unittest.TestCase):
    def test_random_time_inside_schedule_and_after_now(self):
        from datetime import datetime
        now = datetime(2026, 11, 23, 9, 0)         # lunes
        when = identity.next_sample_time(now, "08:00", "18:00", (0, 1, 2, 3, 4), rand=lambda: 0.5)
        self.assertEqual(when.date(), now.date())
        self.assertEqual(when.hour, 13)            # 08:00 + 0.5 × 10 h
        self.assertGreater(when, now)

    def test_finished_window_moves_to_next_allowed_day(self):
        from datetime import datetime
        now = datetime(2026, 11, 23, 17, 59)       # lunes, casi fuera de horario
        when = identity.next_sample_time(now, "08:00", "18:00", (0, 1, 2, 3, 4), rand=lambda: 0.0)
        self.assertEqual(when.date(), datetime(2026, 11, 24).date())
        self.assertEqual((when.hour, when.minute), (8, 0))

    def test_weekend_is_skipped(self):
        from datetime import datetime
        now = datetime(2026, 11, 27, 17, 59)       # viernes
        when = identity.next_sample_time(now, "08:00", "18:00", (0, 1, 2, 3, 4), rand=lambda: 0.0)
        self.assertEqual(when.date(), datetime(2026, 11, 30).date())   # salta sábado y domingo


if __name__ == "__main__":
    unittest.main()
