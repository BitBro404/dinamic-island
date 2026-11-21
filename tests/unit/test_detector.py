"""FaceDetector: sin OpenCV o sin cámara nunca dice «no hay nadie» (devuelve None)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.presence import FaceDetector  # noqa: E402

try:
    import cv2  # noqa: F401
    import numpy as np
    HAVE_CV = os.path.exists(os.path.join(FaceDetector.CASCADES, "haarcascade_frontalface_default.xml"))
except ImportError:
    HAVE_CV = False


class DetectorWithoutModelsTest(unittest.TestCase):
    def test_missing_cascades_unavailable(self):
        d = FaceDetector(cascade_dir="/no/existe")
        self.assertFalse(d.available())
        self.assertIn("python3-opencv", d.error)
        self.assertIsNone(d.detect())


@unittest.skipUnless(HAVE_CV, "OpenCV (python3-opencv + opencv-data) no instalado")
class DetectorWithOpenCVTest(unittest.TestCase):
    def test_available(self):
        self.assertTrue(FaceDetector().available())

    def test_blank_frame_has_no_face(self):
        d = FaceDetector()
        d.available()
        self.assertFalse(d.detect_frame(np.full((240, 320, 3), 128, np.uint8)))

    def test_missing_device_is_none(self):
        d = FaceDetector(device="/dev/video99")
        self.assertIsNone(d.detect())


if __name__ == "__main__":
    unittest.main()
