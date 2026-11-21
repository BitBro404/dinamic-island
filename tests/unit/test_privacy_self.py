"""Los puntos de privacidad no deben contar a la propia isla cuando revisa la cámara."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.privacy import camera_users  # noqa: E402


def fake_proc(root, pid, comm, target):
    os.makedirs(os.path.join(root, str(pid), "fd"))
    os.symlink(target, os.path.join(root, str(pid), "fd", "3"))
    with open(os.path.join(root, str(pid), "comm"), "w") as f:
        f.write(comm + "\n")


class PrivacySelfTest(unittest.TestCase):
    def test_own_process_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            fake_proc(root, os.getpid(), "python3", "/dev/video0")
            fake_proc(root, 999999, "chrome", "/dev/video0")
            fake_proc(root, 999998, "bash", "/dev/null")
            self.assertEqual(camera_users(proc=root), ["Chrome"])

    def test_only_self_means_nobody(self):
        with tempfile.TemporaryDirectory() as root:
            fake_proc(root, os.getpid(), "python3", "/dev/video0")
            self.assertEqual(camera_users(proc=root), [])


if __name__ == "__main__":
    unittest.main()
