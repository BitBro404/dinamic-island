"""S4: el historial del portapapeles no guarda lo que parece un secreto y olvida lo viejo."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.clipboard import History, looks_secret  # noqa: E402


def fake(prefix, body):
    """Token falso armado en tiempo de ejecución: así el archivo no contiene nada con forma de token real
    (los escáneres de secretos, como la protección de GitHub, bloquearían el push)."""
    return prefix + body


GH = fake("gh" + "p_", "16C7e42F292c6912E7710c838347Ae178B4a")
SECRETS = [
    GH,
    fake("github" + "_pat_", "11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz"),
    fake("sk" + "-proj-", "Abc123Def456Ghi789Jkl012Mno345"),
    fake("AK" + "IA", "IOSFODNN7EXAMPLE"),
    fake("xo" + "xb-", "123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"),
    fake("gl" + "pat-", "xxxxXXXX1234yyyyZZZZ"),
    fake("ey" + "JhbGciOiJIUzI1NiJ9.", "eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"),
    fake("-----BEGIN OPENSSH " + "PRIVATE KEY-----\n", "b3BlbnNzaC1rZXktdjEAAAAA\n-----END OPENSSH PRIVATE KEY-----"),
    "Xk9#mP2$vL7qR4wZ8nB3tY6",              # contraseña aleatoria
    "  " + GH + "\n",
]
NORMAL = [
    "hola mundo", "git status --short", "https://github.com/BitBro404/dinamic-island/pull/12",
    "/home/luis/Documentos/WM/backend", "da2f9e5", "96ca746b1c3e9f0d2a4b5c6d7e8f9a0b1c2d3e4f",
    "550e8400-e29b-41d4-a716-446655440000", "persona@example.com", "camelCaseIdentifier",
    "Paso a producción 21-11-2026 (qa → main)", "def fetch_json(url):\n    return 1",
]


class LooksSecretTest(unittest.TestCase):
    def test_secrets(self):
        for s in SECRETS:
            self.assertTrue(looks_secret(s), repr(s))

    def test_normal_text(self):
        for s in NORMAL:
            self.assertFalse(looks_secret(s), repr(s))


class HistoryTest(unittest.TestCase):
    def test_skips_secrets_and_keeps_order(self):
        h = History(clock=lambda: 0)
        self.assertTrue(h.add("uno"))
        self.assertFalse(h.add(SECRETS[0]))
        self.assertTrue(h.add("dos"))
        self.assertTrue(h.add("uno"))                  # repetido: sube arriba sin duplicarse
        self.assertEqual(h.items, ["uno", "dos"])

    def test_old_entries_expire(self):
        now = [0.0]
        h = History(clock=lambda: now[0], max_age=1800)
        h.add("viejo")
        now[0] = 1000
        h.add("nuevo")
        now[0] = 1900
        self.assertTrue(h.prune())
        self.assertEqual(h.items, ["nuevo"])
        self.assertFalse(h.prune())                    # nada más que quitar

    def test_limit_and_clear(self):
        h = History(clock=lambda: 0, limit=3)
        for t in "abcd":
            h.add(t)
        self.assertEqual(h.items, ["d", "c", "b"])
        h.clear()
        self.assertEqual(h.items, [])


if __name__ == "__main__":
    unittest.main()
