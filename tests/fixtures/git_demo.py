"""Proyectos: usa las carpetas reales (no guarda la config) y agrega una carpeta extra en memoria."""
import os


def setup(core):
    core.config.save = lambda: None
    core.config.data["git_folders"] = ["~/Documentos/WM", os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))]
    core.git.refresh()
