"""Pieza de install.sh que calcula planes de paquetes, autoarranque y lanzador.

No instala nada por sí sola: `install.sh --deps` muestra el plan y pide confirmación (regla D3).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isla_dinamica.platform.desktop import detect  # noqa: E402
from tools.autostart import autostart_entry, compositor_hint  # noqa: E402
from tools.deps import detect_manager, install_command, packages  # noqa: E402
from tools.launcher import launcher_script  # noqa: E402


def _plan():
    release = Path("/etc/os-release")
    text = release.read_text(errors="replace") if release.exists() else ""
    manager = detect_manager(text)
    desktop = detect(os.environ)
    return manager, packages(manager, desktop.family, desktop.session), desktop


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "deps-plan"
    if cmd == "deps-plan":
        manager, pkgs, desktop = _plan()
        print(f"Gestor: {manager} · Escritorio: {desktop.label}")
        print("Paquetes: " + " ".join(pkgs))
        print("Orden: " + " ".join(install_command(manager, pkgs)))
    elif cmd == "deps-command":
        manager, pkgs, _desktop = _plan()
        print("\n".join(install_command(manager, pkgs)))
    elif cmd == "autostart":
        print(autostart_entry(os.path.join(Path.home(), ".local", "bin", "isla-dinamica")), end="")
    elif cmd == "hint":
        line = compositor_hint(detect(os.environ).family)
        if line:
            print(line)
    elif cmd == "launcher":
        print(launcher_script(argv[2]), end="")
    else:
        print(f"Comando desconocido: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
