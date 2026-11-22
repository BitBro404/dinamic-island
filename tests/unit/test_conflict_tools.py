"""Herramientas para resolver un conflicto: Claude Code u OpenCode en una terminal, o VS Code."""
import os
import shlex
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform import terminal  # noqa: E402

REPO = "/home/u/mi repo"


def finder(*present):
    paths = {name: f"/usr/bin/{name}" for name in present}
    return lambda name: paths.get(name)


class TerminalTest(unittest.TestCase):
    def test_xfce4_terminal(self):
        argv = terminal.terminal_argv(REPO, ["claude", "hola"], which=finder("xfce4-terminal"))
        self.assertEqual(argv, ["/usr/bin/xfce4-terminal", f"--working-directory={REPO}", "-x", "claude", "hola"])

    def test_gnome_terminal(self):
        argv = terminal.terminal_argv(REPO, ["claude", "hola"], which=finder("gnome-terminal"))
        self.assertEqual(argv, ["/usr/bin/gnome-terminal", f"--working-directory={REPO}", "--", "claude", "hola"])

    def test_generic_fallback_quotes_everything(self):
        argv = terminal.terminal_argv(REPO, ["claude", "it's; rm -rf ~"], which=finder("x-terminal-emulator"))
        self.assertEqual(argv[:2], ["/usr/bin/x-terminal-emulator", "-e"])
        sh, flag, inner = shlex.split(argv[2])
        self.assertEqual((sh, flag), ("sh", "-c"))
        self.assertEqual(shlex.split(inner), ["cd", REPO, "&&", "exec", "claude", "it's; rm -rf ~"])

    def test_no_terminal(self):
        self.assertIsNone(terminal.terminal_argv(REPO, ["claude"], which=finder()))


class ResolverTest(unittest.TestCase):
    def test_available(self):
        home = os.path.expanduser("~/.opencode/bin/opencode")
        which = finder("claude", "code")
        self.assertEqual(terminal.resolvers(which=which, exists=lambda p: p == home),
                         {"claude": "/usr/bin/claude", "opencode": home, "code": "/usr/bin/code"})
        self.assertEqual(terminal.resolvers(which=finder(), exists=lambda p: False), {})

    def test_prompt_mentions_files_and_forbids_commit(self):
        p = terminal.conflict_prompt(["a.txt", "src/b.py"], "feat", "main")
        self.assertIn("a.txt, src/b.py", p)
        self.assertIn("feat", p)
        self.assertIn("git add", p)
        self.assertIn("no hagas commit", p.lower())

    def test_commands(self):
        tools = {"claude": "/c/claude", "opencode": "/o/opencode", "code": "/v/code"}
        self.assertEqual(terminal.resolver_command("claude", tools, REPO, ["a.txt"], "P"), ["/c/claude", "P"])
        self.assertEqual(terminal.resolver_command("opencode", tools, REPO, ["a.txt"], "P"),
                         ["/o/opencode", "--prompt", "P", REPO])
        self.assertEqual(terminal.resolver_command("code", tools, REPO, ["a.txt", "b/c.py"], "P"),
                         ["/v/code", REPO, os.path.join(REPO, "a.txt"), os.path.join(REPO, "b/c.py")])


if __name__ == "__main__":
    unittest.main()
