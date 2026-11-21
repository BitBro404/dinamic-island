"""Pestaña GitHub con «Fusionadas» plegada y despliegues falsos (uno de hoy). No toca ~/.config."""
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))


def setup(core):
    runpy.run_path(os.path.join(HERE, "deploys_fake.py"))["setup"](core)
    core.config.data["collapsed"] = ["gh_merged"]
