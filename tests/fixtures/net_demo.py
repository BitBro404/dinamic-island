"""Genera tráfico (descarga de prueba a /dev/null) y simula que se cae la VPN."""
import subprocess

from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    GLib.timeout_add(4000, lambda: subprocess.Popen(
        ["curl", "-s", "-o", "/dev/null", "https://speed.cloudflare.com/__down?bytes=30000000"]) and False)
    GLib.timeout_add(14000, lambda: core.netmon._got_vpns(True, "802-11-wireless:XIAOMI\n", "") or False)
