"""T4–T6: Presence con verificación de identidad, pregunta y calibración (sin cámara real)."""
import copy
import hashlib
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.config import DEFAULTS  # noqa: E402
from isla_dinamica.services import identity  # noqa: E402
from isla_dinamica.services.presence import Presence  # noqa: E402

WORK = datetime(2026, 11, 23, 10, 0)      # lunes, en horario
BODY = b"modelo de prueba"
SPECS = {"mini": ("mini.onnx", len(BODY), hashlib.sha256(BODY).hexdigest(),
                  "https://example.test/mini.onnx")}


class FakeConfig:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULTS)

    def save(self):
        pass


class FakeDetector:
    def __init__(self, faces=None, frame="foto"):
        self.faces, self.frame, self.calls = faces if faces is not None else [], frame, 0

    def available(self):
        return True

    def capture(self):
        self.calls += 1
        return self.frame, self.faces


class FakeIdentity:
    def __init__(self, result, feature=None, enrolled=True):
        self.result, self.feature, self.enrolled = result, feature, enrolled

    def available(self):
        return self.enrolled

    def has_recognizer(self):
        return True

    def inspect(self, frame, faces):
        return self.result, self.feature

    def enroll_feature(self, frame, faces):
        return self.feature


class FakeFetch:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    def __call__(self, url, timeout=10):
        self.calls += 1
        if self.fail:
            raise OSError("sin red")
        return BODY


class IdentityServiceTest(unittest.TestCase):
    def make(self, result="other", faces=None, feature=None, enrolled=True, fetch=None,
             wall=WORK, busy=False, epoch=1000.0, rand=None):
        self.now, self.epoch_now = [0.0], [epoch]
        self.done, self.locks = [], 0
        self.det = FakeDetector(faces)
        self.fetch = fetch or FakeFetch()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.gallery = identity.Gallery(os.path.join(tmp.name, "gallery.json"))
        if enrolled:
            self.gallery.add([0.5])
        self.ident = FakeIdentity(result, feature if feature is not None else [0.5], enrolled)
        acts = {k: (lambda k=k: self.done.append(k)) for k in ("screen_off", "screen_on")}

        def lock():
            self.done.append("lock")
            return True
        acts["lock"] = lock
        def on_lock():
            self.locks += 1
        self.p = Presence(FakeConfig(), on_change=lambda: None, on_lock=on_lock,
                          enabled=lambda: True, detector=self.det, identity=self.ident,
                          gallery=self.gallery, actions=acts, start=False, clock=lambda: self.now[0],
                          wall=lambda: wall, epoch=lambda: self.epoch_now[0], rand=rand,
                          camera_busy=lambda: busy, post=lambda f: f(), models=SPECS,
                          models_dir=os.path.join(tmp.name, "models"), fetch=self.fetch)
        return self.p

    def run_for(self, secs):
        for _ in range(int(secs)):
            self.now[0] += 1
            self.p._tick()

    def test_other_person_locks(self):
        p = self.make(result="other", faces=[[0.1, 0, 20, 20]], feature=[0.1])
        p._idle(0.0)
        self.run_for(300)
        self.assertEqual(self.done, ["lock", "screen_off"])
        self.assertEqual(p.state, "locked")

    def test_me_never_locks(self):
        p = self.make(result="me", faces=[[0.9, 0, 20, 20]])
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual(self.done, [])
        self.assertEqual(p.state, "present")

    def test_unknown_prompts_and_never_locks(self):
        p = self.make(result="unknown", faces=[[0.3, 0, 20, 20]], feature=[0.3])
        p._idle(0.0)
        self.run_for(20)
        self.assertIsNotNone(p.pending_prompt)
        self.assertEqual(p.state, "confirm")
        self.assertEqual(self.done, [])
        p.answer(True)
        self.assertIsNone(p.pending_prompt)
        self.assertEqual(len(self.gallery.samples), 1)
        self.run_for(900)
        self.assertEqual(self.done, [])

    def test_answer_no_does_not_change_gallery(self):
        p = self.make(result="unknown", faces=[[0.3, 0, 20, 20]], feature=[0.3])
        p._idle(0.0)
        self.run_for(20)
        p.answer(False)
        self.assertEqual(len(self.gallery.samples), 0)
        self.assertIsNone(p.pending_prompt)

    def test_without_template_behaves_as_before(self):
        p = self.make(result="me", faces=[], enrolled=False)
        p._idle(0.0)
        self.run_for(300)
        self.assertEqual(self.done, ["lock", "screen_off"])

    def test_no_face_with_template_still_locks(self):
        p = self.make(result="unknown", faces=[], feature=[0.3])
        p._idle(0.0)
        self.run_for(300)
        self.assertEqual(self.done, ["lock", "screen_off"])

    def test_call_is_fail_open(self):
        p = self.make(result="other", faces=[[0.1, 0, 20, 20]], busy=True)
        p._idle(0.0)
        self.run_for(900)
        self.assertEqual(self.done, [])

    def test_enroll_downloads_models_and_saves_template(self):
        p = self.make(result="me", faces=[[0.9, 0, 20, 20]], feature=[0.9], enrolled=False)
        p.enroll()
        self.assertTrue(self.gallery.enrolled)
        self.assertEqual(self.fetch.calls, 1)
        self.assertIn("Registrado", p.test_result)

    def test_enroll_without_network_keeps_current_state(self):
        p = self.make(result="me", fetch=FakeFetch(fail=True), enrolled=False)
        p.enroll()
        self.assertFalse(self.gallery.enrolled)
        self.assertIn("Error", p.test_result)

    def test_clear_identity_restores_current_behavior(self):
        p = self.make(result="me", faces=[[0.9, 0, 20, 20]], feature=[0.9])
        p.enroll()
        self.assertTrue(self.gallery.enrolled)
        p.clear_identity()
        self.assertFalse(self.gallery.enrolled)
        self.assertIsNone(p.pending_prompt)
        self.det.faces = []              # sin plantilla, sin cara → bloquea como siempre
        p._idle(0.0)
        self.run_for(300)
        self.assertEqual(self.done, ["lock", "screen_off"])

    def test_enrolling_skips_camera_checks(self):
        p = self.make(result="other", faces=[[0.1, 0, 20, 20]])
        p._idle(0.0)
        p.enrolling = True
        self.run_for(100)
        self.assertEqual(self.det.calls, 0)
        self.assertEqual(self.done, [])


class DailyCalibrationTest(unittest.TestCase):
    def due(self, p, epoch=1000.0):
        self.t.epoch_now[0] = epoch
        p.gallery.next_sample_at = epoch - 1
        p._active(0.0)                         # actividad reciente
        p.clock = lambda: 1.0                  # un segundo después; sigue siendo actividad reciente

    def make(self, **kw):
        t = IdentityServiceTest()
        t.setUp()
        self.addCleanup(t.doCleanups)
        p = t.make(result="me", faces=[[0.9, 0, 20, 20]], feature=[0.9], rand=lambda: 0.5, **kw)
        self.t = t
        return p

    def test_daily_sample_asks_and_adds_only_embedding(self):
        p = self.make()
        self.due(p)
        p._tick()
        self.assertIsNotNone(p.pending_prompt)
        self.assertEqual(p.pending_prompt["source"], "daily")
        self.assertEqual(p.state, "confirm")
        self.assertGreater(p.gallery.next_sample_at, 1000.0)   # ya programó el del próximo día
        p.answer(True)
        self.assertEqual(len(p.gallery.samples), 1)
        self.assertEqual(p.gallery.anchor, [0.5])              # el ancla no se toca
        self.assertEqual(p.pending_prompt, None)

    def test_no_recent_input_never_asks(self):
        p = self.make()
        p.gallery.next_sample_at = 999.0
        p._tick()
        self.assertIsNone(p.pending_prompt)

    def test_not_due_yet_does_not_ask(self):
        p = self.make()
        p.gallery.next_sample_at = 2000.0
        p._active(0.0)
        p._tick()
        self.assertIsNone(p.pending_prompt)

    def test_out_of_hours_and_pause_do_not_ask(self):
        from datetime import datetime
        p = self.make(wall=datetime(2026, 11, 28, 10, 0))      # sábado
        self.due(p)
        p._tick()
        self.assertIsNone(p.pending_prompt)
        p2 = self.make()
        p2.conf["paused_until"] = 2000.0
        self.due(p2)
        p2._tick()
        self.assertIsNone(p2.pending_prompt)

    def test_timeout_and_no_do_not_change_gallery(self):
        p = self.make()
        self.due(p)
        p._tick()
        for _ in range(identity.PROMPT_TIMEOUT + 1):
            p.clock = lambda n=_: 1.0 + n
            p._tick()
        self.assertIsNone(p.pending_prompt)
        self.assertEqual(p.gallery.samples, [])
        self.due(p, epoch=p.gallery.next_sample_at + 1)
        p._tick()
        self.assertIsNotNone(p.pending_prompt)
        p.answer(False)
        self.assertEqual(p.gallery.samples, [])


if __name__ == "__main__":
    unittest.main()
