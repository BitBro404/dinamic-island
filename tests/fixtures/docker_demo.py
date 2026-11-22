"""Contenedor de prueba «isla-demo-web» (alpine; Docker publica :18080): la isla lo detiene (■) y luego lo vuelve a
arrancar desde DETENIDOS (▶). No toca otros contenedores ni guarda la configuración. Al terminar:
`docker rm -f isla-demo-web`."""
import subprocess

from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    core.config.data["servers_recent"] = []
    subprocess.run(["docker", "rm", "-f", "isla-demo-web"], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--init", "--name", "isla-demo-web", "-p", "127.0.0.1:18080:8080",
                    "alpine", "sleep", "3600"], capture_output=True)

    def page():
        w = next(iter(core.windows.values()))
        return next(o for o in w.page_objs if type(o).__name__ == "ServersPage")

    def stop():
        page()._sv_docker("docker:isla-demo-web", "stop")
        page()._sv_docker("docker:isla-demo-web", "stop")
        return False

    def start():
        idx = next((i for i, r in core.servers.stopped() if r["name"] == "isla-demo-web"), None)
        if idx is not None:
            page()._sv_relaunch(idx)
        return False
    GLib.timeout_add(7500, stop)
    GLib.timeout_add(14000, start)
