"""Desactiva clima, GitHub y Teams/correo sin tocar ~/.config (para probar los interruptores)."""


def setup(core):
    core.config.save = lambda: None
    for name in ("weather", "github", "ms"):
        core.set_feature(name, False)
