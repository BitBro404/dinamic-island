"""U8.1: los nombres de escritorio solo pueden aparecer en isla_dinamica/platform/.

Se analiza el AST (no texto): los comentarios y docstrings explican el comportamiento y están permitidos;
lo prohibido es que la lógica (cadenas, variables, funciones, clases) ramifique por nombre de escritorio
fuera de `platform/`.
"""
import ast
import os
import pathlib
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.desktop import _TOKENS  # noqa: E402

FAMILIES = {name for token, name in _TOKENS} | {token for token, _ in _TOKENS}
FAMILIES.discard("other")
WORDS = re.compile(r"[a-z]+")
PARTS = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def _identifier_parts(name):
    return {p.lower() for p in PARTS.findall(name)}


def violations(source):
    """Lista de (línea, tipo, valor) con nombres de escritorio usados como código."""
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                for child in ast.walk(node):
                    if isinstance(child, ast.Constant) and child.value == doc:
                        docstrings.add(id(child))
                        break
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            bad = set(WORDS.findall(node.value.lower())) & FAMILIES
            if bad:
                found.append((node.lineno, "cadena", node.value.strip()[:70]))
        elif isinstance(node, (ast.Name, ast.Attribute, ast.arg, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef, ast.alias)):
            name = (getattr(node, "id", None) or getattr(node, "attr", None) or getattr(node, "arg", None)
                    or getattr(node, "name", None) or getattr(node, "asname", None))
            if name and _identifier_parts(name) & FAMILIES:
                found.append((getattr(node, "lineno", 0), "identificador", name))
    return found


class ArchitectureTest(unittest.TestCase):
    def test_el_analizador_detecta_violaciones_pero_no_docstrings(self):
        self.assertTrue(violations('panel = "gnome"\n'))
        self.assertTrue(violations('def gnome_settings(): pass\n'))
        self.assertEqual(violations('"""GNOME, KDE y sway se explican aquí."""\nx = 1\n'), [])

    def test_sin_nombres_de_escritorio_fuera_de_platform(self):
        root = pathlib.Path(__file__).resolve().parents[2] / "isla_dinamica"
        found = []
        for path in sorted(root.rglob("*.py")):
            if "platform" in path.relative_to(root).parts:
                continue
            for line, kind, value in violations(path.read_text(encoding="utf-8")):
                found.append(f"{path.relative_to(root)}:{line} {kind} {value!r}")
        self.assertEqual(found, [], "Los nombres de escritorio van en platform/:\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
