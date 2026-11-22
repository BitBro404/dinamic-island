"""U6.1: generador puro de paquetes por distro y escritorio para `install.sh --deps`."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.deps import detect_manager, install_command, packages  # noqa: E402


class DepsTest(unittest.TestCase):
    def test_manager_by_distro(self):
        self.assertEqual(detect_manager("ID=ubuntu\nID_LIKE=debian\n"), "apt")
        self.assertEqual(detect_manager("ID=fedora\n"), "dnf")
        self.assertEqual(detect_manager("ID=arch\n"), "pacman")
        self.assertEqual(detect_manager("ID=opensuse-tumbleweed\n"), "zypper")

    def test_common_and_family_packages(self):
        apt = packages("apt", "budgie", "wayland")
        self.assertIn("gir1.2-gtk-3.0", apt)
        self.assertIn("gir1.2-gtklayershell-0.1", apt)
        self.assertIn("wl-clipboard", apt)
        self.assertIn("grim", apt)
        self.assertTrue(all(isinstance(p, str) for p in apt))
        self.assertEqual(len(apt), len(set(apt)))

        dnf = packages("dnf", "kde", "wayland")
        self.assertIn("gtk3", dnf)
        self.assertIn("wl-clipboard", dnf)
        self.assertIn("plasma-workspace", dnf)

        pacman = packages("pacman", "sway", "wayland")
        self.assertIn("gtk3", pacman)
        self.assertIn("swayidle", pacman)

        zypper = packages("zypper", "xfce", "x11")
        self.assertIn("typelib-1_0-GtkLayerShell-0_1", zypper)
        self.assertIn("xset", zypper or [])

    def test_install_command(self):
        self.assertEqual(install_command("apt", ["a", "b"]), ["sudo", "apt", "install", "-y", "a", "b"])
        self.assertEqual(install_command("dnf", ["a"]), ["sudo", "dnf", "install", "-y", "a"])
        self.assertEqual(install_command("pacman", ["a"]), ["sudo", "pacman", "-S", "--noconfirm", "a"])
        self.assertEqual(install_command("zypper", ["a"]), ["sudo", "zypper", "install", "-y", "a"])


if __name__ == "__main__":
    unittest.main()
