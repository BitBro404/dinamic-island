"""Servidores: detener, recordar el comando que los arrancó y relanzarlos."""
import json
import os
import socket
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services import servers as sv  # noqa: E402

HOME = os.path.expanduser("~")


def table(rows):
    """Lector de procesos falso: pid → {ppid, cwd, argv, path}."""
    def info(pid):
        return rows.get(pid)
    return info


class LaunchSpecTest(unittest.TestCase):
    def test_npm_run_dev_is_remembered_not_the_inner_node(self):
        info = table({
            10: {"ppid": 1, "cwd": HOME, "argv": ["-zsh"], "path": "/usr/bin"},
            20: {"ppid": 10, "cwd": "/p/web", "argv": ["npm run dev"], "path": "/n/bin:/usr/bin"},
            30: {"ppid": 20, "cwd": "/p/web", "argv": ["sh", "-c", "vite"], "path": "/n/bin"},
            40: {"ppid": 30, "cwd": "/p/web", "argv": ["node", "/p/web/node_modules/.bin/vite"], "path": "/n/bin"},
        })
        spec = sv.launch_spec(40, info)
        self.assertEqual(spec["top"], 20)
        self.assertEqual(spec["argv"], ["npm", "run", "dev"])
        self.assertEqual(spec["cwd"], "/p/web")
        self.assertEqual(spec["path"], "/n/bin:/usr/bin")

    def test_does_not_climb_into_an_unrelated_python_parent(self):
        info = table({
            30: {"ppid": 1, "cwd": "/p/api", "argv": ["python3", "-m", "unittest"], "path": "/usr/bin"},
            40: {"ppid": 30, "cwd": "/p/api", "argv": ["python3", "-m", "http.server", "8000"], "path": "/usr/bin"},
        })
        spec = sv.launch_spec(40, info)
        self.assertEqual((spec["top"], spec["argv"]), (40, ["python3", "-m", "http.server", "8000"]))

    def test_climbs_through_nodemon_but_not_into_another_folder(self):
        info = table({
            15: {"ppid": 1, "cwd": "/otro", "argv": ["npm", "start"], "path": "/usr/bin"},
            20: {"ppid": 15, "cwd": "/p/api", "argv": ["node", "/p/api/node_modules/.bin/nodemon", "server.js"],
                 "path": "/usr/bin"},
            30: {"ppid": 20, "cwd": "/p/api", "argv": ["node", "server.js"], "path": "/usr/bin"},
        })
        spec = sv.launch_spec(30, info)
        self.assertEqual(spec["top"], 20)
        self.assertEqual(spec["argv"], ["node", "/p/api/node_modules/.bin/nodemon", "server.js"])

    def test_interactive_shell_is_not_a_launcher(self):
        info = table({
            10: {"ppid": 1, "cwd": "/p", "argv": ["bash"], "path": "/usr/bin"},
            20: {"ppid": 10, "cwd": "/p", "argv": ["php", "artisan", "serve"], "path": "/usr/bin"},
        })
        self.assertEqual(sv.launch_spec(20, info)["top"], 20)

    def test_unknown_process_gives_none(self):
        self.assertIsNone(sv.launch_spec(99, table({})))


class RuntimeTest(unittest.TestCase):
    """Node 24 llama «MainThread» a su hilo principal y Python puede salir como «python3.12»: se mira el
    ejecutable real del proceso, no solo el nombre que muestra `ss`."""
    LINES = "\n".join([
        'LISTEN 0 511 *:3000 *:* users:(("MainThread",pid=101,fd=24))',
        'LISTEN 0 5 127.0.0.1:8001 0.0.0.0:* users:(("python3.12",pid=102,fd=3))',
        'LISTEN 0 511 127.0.0.1:35459 0.0.0.0:* users:(("code",pid=103,fd=72))',
        'LISTEN 0 511 127.0.0.1:5000 0.0.0.0:* users:(("MainThread",pid=104,fd=7))',
    ])
    EXE = {101: "/home/u/.nvm/versions/node/v24.22.3/bin/node", 102: "/usr/bin/python3.12",
           103: "/snap/code/281/usr/share/code/code", 104: "/opt/chrome/chrome"}

    def test_runtime(self):
        self.assertEqual(sv.runtime("MainThread", self.EXE[101]), "node")
        self.assertEqual(sv.runtime("python3.12", self.EXE[102]), "python")
        self.assertEqual(sv.runtime("uvicorn", "/usr/bin/python3.13"), "uvicorn")
        self.assertIsNone(sv.runtime("code", self.EXE[103]))
        self.assertIsNone(sv.runtime("MainThread", self.EXE[104]))

    def test_node_and_python_ports_are_listed(self):
        with mock.patch.object(sv, "_exe", lambda pid: self.EXE.get(pid, "")), \
                mock.patch.object(sv, "_proc", lambda pid: ("/p/wmservice-backend", "node index.js")), \
                mock.patch.object(sv, "launch_spec", lambda pid: None), \
                mock.patch.object(sv, "_started", lambda pid: None):
            found = sv.parse_ss(self.LINES)
        self.assertEqual(sorted(found), [3000, 8001])
        self.assertEqual((found[3000]["name"], found[3000]["kind"], found[3000]["comm"]),
                         ("wmservice-backend", "Node", "node"))
        self.assertEqual(found[8001]["kind"], "Python")


class RememberTest(unittest.TestCase):
    def spec(self, port, argv, cwd="/p"):
        return {"name": "web", "port": port, "kind": "Vite", "cwd": cwd, "argv": argv, "path": "/usr/bin"}

    def test_newest_first_without_duplicates_and_limited(self):
        recent = []
        recent = sv.remember(recent, self.spec(5173, ["npm", "run", "dev"]), now=1)
        recent = sv.remember(recent, self.spec(8000, ["python3", "app.py"]), now=2)
        recent = sv.remember(recent, self.spec(5174, ["npm", "run", "dev"]), now=3)
        self.assertEqual([(r["port"], r["when"]) for r in recent], [(5174, 3), (8000, 2)])
        for i in range(20):
            recent = sv.remember(recent, self.spec(9000 + i, ["x", str(i)]), now=10 + i)
        self.assertEqual(len(recent), sv.RECENT_MAX)

    def test_running_ones_are_hidden_from_the_stopped_list(self):
        recent = [self.spec(5173, ["npm", "run", "dev"]), self.spec(8000, ["python3", "app.py"], cwd="/q")]
        running = {5173: {"cwd": "/p", "launch": ["npm", "run", "dev"]}}
        self.assertEqual([r["port"] for r in sv.stopped(recent, running)], [8000])


class ConfigTest(unittest.TestCase):
    def test_recent_servers_are_loaded_and_validated(self):
        from isla_dinamica import config as cfgmod
        good = {"name": "web", "port": 5173, "kind": "Vite", "cwd": "/p", "argv": ["npm", "run", "dev"],
                "path": "/usr/bin", "when": 5}
        bad = [{"argv": [], "cwd": "/p"}, {"argv": "npm run dev", "cwd": "/p"}, {"argv": ["x"], "cwd": 3}, "x"]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w") as f:
                json.dump({"servers_recent": [good] + bad}, f)
            with mock.patch.object(cfgmod, "CONFIG_PATH", path):
                c = cfgmod.Config()
        self.assertEqual(c.data["servers_recent"], [good])


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def listening(port, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


class LaunchTest(unittest.TestCase):
    def test_launch_runs_in_its_folder_in_background_with_a_log(self):
        port = free_port()
        with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as logs:
            spec = {"name": "demo", "port": port, "cwd": cwd, "path": os.environ.get("PATH", ""),
                    "argv": [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"]}
            ok, msg, pid = sv.launch(spec, logs)
            try:
                self.assertTrue(ok, msg)
                self.assertTrue(listening(port))
                self.assertEqual(os.readlink(f"/proc/{pid}/cwd"), os.path.realpath(cwd))
                self.assertEqual(os.getpgid(pid), pid)          # sesión propia: sobrevive a la isla
                self.assertTrue(os.path.exists(sv.log_path(spec, logs)))
                live = sv.proc_info(pid)
                self.assertEqual(live["argv"][1:3], ["-m", "http.server"])
                sv.terminate({"top": pid, "pid": pid})
                end = time.time() + 5
                while listening(port, timeout=0.1) and time.time() < end:
                    time.sleep(0.1)
                self.assertFalse(listening(port, timeout=0.1))
            finally:
                try:
                    os.kill(pid, 9)
                except (OSError, TypeError):
                    pass

    def test_launch_refuses_a_missing_folder_or_program(self):
        ok, msg, _ = sv.launch({"name": "x", "port": 1, "cwd": "/no/existe", "argv": ["ls"], "path": "/usr/bin"},
                               tempfile.gettempdir())
        self.assertFalse(ok)
        self.assertIn("carpeta", msg)
        with tempfile.TemporaryDirectory() as cwd:
            ok, msg, _ = sv.launch({"name": "x", "port": 1, "cwd": cwd, "argv": ["no-existe-xyz"], "path": "/usr/bin"},
                                   tempfile.gettempdir())
        self.assertFalse(ok)
        self.assertIn("no-existe-xyz", msg)


class LaunchSafetyTest(unittest.TestCase):
    def test_relative_path_entries_are_dropped(self):
        """S13: «.» o entradas vacías en el PATH guardado harían ejecutar un programa plantado en el proyecto."""
        self.assertEqual(sv.clean_path(".:/usr/bin::bin:/opt/x/bin:~/bin"), "/usr/bin:/opt/x/bin")

    def test_program_planted_in_the_project_is_not_run(self):
        with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as logs:
            planted = os.path.join(cwd, "node")
            with open(planted, "w") as f:
                f.write("#!/bin/sh\ntouch pwned\n")
            os.chmod(planted, 0o755)
            ok, msg, _ = sv.launch({"name": "x", "port": 1, "cwd": cwd, "argv": ["node", "server.js"],
                                    "path": ".:" + cwd + "/no-existe"}, logs)
            self.assertFalse(ok)
            self.assertIn("node", msg)
            self.assertFalse(os.path.exists(os.path.join(cwd, "pwned")))

    def test_logs_are_private(self):
        """S15: la salida de un servidor puede llevar secretos: carpeta 0700 y archivo 0600."""
        port = free_port()
        with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as base:
            logs = os.path.join(base, "servers")
            ok, msg, pid = sv.launch({"name": "demo", "port": port, "cwd": cwd, "path": os.environ["PATH"],
                                      "argv": [sys.executable, "-c", "print('hola')"]}, logs)
            self.assertTrue(ok, msg)
            time.sleep(0.3)
            self.assertEqual(os.stat(logs).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(sv.log_path({"name": "demo", "port": port}, logs)).st_mode & 0o777, 0o600)

    def test_a_reused_pid_is_not_signalled(self):
        """S14: si el PID guardado ya es de otro proceso (arrancó a otra hora), no se le manda la señal."""
        import subprocess
        p = subprocess.Popen(["sleep", "30"])
        self.addCleanup(lambda: (p.kill(), p.wait()))
        real = sv._started(p.pid)
        sv.terminate({"top": p.pid, "pid": p.pid, "top_started": real - 100, "pid_started": real - 100})
        time.sleep(0.2)
        self.assertIsNone(p.poll())                    # sigue vivo
        sv.terminate({"top": p.pid, "pid": p.pid, "top_started": real, "pid_started": real})
        self.assertEqual(p.wait(timeout=3), -15)

    def test_launch_spec_records_start_times(self):
        import subprocess
        p = subprocess.Popen(["sleep", "30"])
        self.addCleanup(lambda: (p.kill(), p.wait()))
        spec = sv.launch_spec(p.pid)
        self.assertEqual(spec["pid_started"], sv._started(p.pid))
        self.assertIsNotNone(spec["top_started"])


class ServersFlowTest(unittest.TestCase):
    def make(self):
        self.events, self.saved, self.launched = [], [], []
        with mock.patch.object(sv, "run"), mock.patch.object(sv.GLib, "timeout_add_seconds"):
            s = sv.Servers(lambda: None, lambda k, x: self.events.append((k, x["port"])),
                           recent=lambda: self.saved[-1] if self.saved else [],
                           save_recent=self.saved.append, logs=tempfile.gettempdir())
        s.apply({})
        spec = {"top": 20, "pid": 40, "argv": ["npm", "run", "dev"], "cwd": "/p/web", "path": "/usr/bin"}
        s.apply({5173: {"port": 5173, "pid": 40, "name": "web", "kind": "Vite", "cwd": "/p/web", "mine": True,
                        "spec": spec, "launch": spec["argv"]}})
        self.events.clear()
        return s

    def test_stop_remembers_the_command(self):
        s = self.make()
        with mock.patch.object(sv, "terminate") as term:
            s.stop(5173)
        term.assert_called_once()
        self.assertEqual(self.saved[-1][0]["argv"], ["npm", "run", "dev"])
        s.apply({})
        self.assertEqual(self.events, [("stopped", 5173)])

    def test_a_server_that_falls_is_also_remembered(self):
        s = self.make()
        s.apply({})
        self.assertEqual(self.events, [("down", 5173)])
        self.assertEqual(self.saved[-1][0]["port"], 5173)

    def test_restart_stops_then_launches_the_same_command_when_the_port_frees(self):
        s = self.make()
        with mock.patch.object(sv, "terminate"), \
                mock.patch.object(sv, "launch", side_effect=lambda spec, logs: (True, "", 77)) as launch:
            s.restart(5173)
            launch.assert_not_called()          # aún escucha: espera a que se libere el puerto
            s.apply({})
            launch.assert_called_once()
        self.assertEqual(launch.call_args[0][0]["argv"], ["npm", "run", "dev"])
        self.assertEqual(self.events, [("restarting", 5173)])

    def test_relaunch_a_stopped_one(self):
        s = self.make()
        with mock.patch.object(sv, "terminate"):
            s.stop(5173)
        s.apply({})
        with mock.patch.object(sv, "launch", return_value=(True, "", 77)) as launch:
            ok, _ = s.relaunch(0)
        self.assertTrue(ok)
        self.assertEqual(launch.call_args[0][0]["cwd"], "/p/web")

    def test_forget(self):
        s = self.make()
        with mock.patch.object(sv, "terminate"):
            s.stop(5173)
        s.forget(0)
        self.assertEqual(self.saved[-1], [])


if __name__ == "__main__":
    unittest.main()
