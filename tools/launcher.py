"""Contenido del lanzador ~/.local/bin/isla-dinamica (reenvía --doctor y cualquier otro argumento)."""
from pathlib import Path


def launcher_script(dest):
    """`dest`: directorio donde install.sh copió `isla_dinamica`."""
    return (f"#!/usr/bin/env python3\n"
            f'"""Isla dinámica (instalada con install.sh). Usa --doctor para diagnosticar."""\n'
            f"import os\nimport sys\n\n"
            f"sys.path.insert(0, {str(Path(dest))!r})\n"
            f"from isla_dinamica.main import main  # noqa: E402\n\n"
            f"main()\n")
