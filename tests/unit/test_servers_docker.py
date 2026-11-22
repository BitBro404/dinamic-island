"""Servidores en Docker: agrupar contenedores por proyecto de compose, detener, reiniciar y volver a arrancar."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services import servers as sv  # noqa: E402

PS = "\n".join([
    "a26e58b39c75\topengym-web-1\trunning\t8080/tcp, 0.0.0.0:8080->80/tcp, [::]:8080->80/tcp\topengym\tweb\tnginx",
    "536cc060c620\topengym-api-1\trunning\t3000/tcp\topengym\tapi\topengym-api",
    "77aa00bb11cc\tredis\trunning\t127.0.0.1:6379->6379/tcp\t\t\tredis:7",
    "88aa00bb11cc\tviejo\texited\t\t\t\tbusybox",
])

SS = "\n".join([
    'LISTEN 0 4096 0.0.0.0:8080 0.0.0.0:*',
    'LISTEN 0 4096 [::]:8080 [::]:*',
    'LISTEN 0 4096 127.0.0.1:6379 0.0.0.0:*',
    'LISTEN 0 4096 0.0.0.0:9000 0.0.0.0:*',
])


class ParseTest(unittest.TestCase):
    def test_host_ports(self):
        self.assertEqual(sv.host_ports("8080/tcp, 0.0.0.0:8080->80/tcp, [::]:8080->80/tcp"), [8080])
        self.assertEqual(sv.host_ports("3000/tcp"), [])
        self.assertEqual(sv.host_ports("0.0.0.0:5432-5433->5432-5433/tcp"), [5432, 5433])
        self.assertEqual(sv.host_ports(""), [])

    def test_running_containers_grouped_by_compose_project(self):
        groups = sv.docker_groups(sv.parse_docker_ps(PS))
        self.assertEqual(set(groups), {"docker:opengym", "docker:redis"})
        og = groups["docker:opengym"]
        self.assertEqual(og["name"], "opengym")
        self.assertEqual(og["containers"], ["opengym-api-1", "opengym-web-1"])
        self.assertEqual(og["services"], ["api", "web"])
        self.assertEqual((og["ports"], og["port"], og["url"]), ([8080], 8080, "http://localhost:8080"))
        self.assertEqual(og["kind"], "Docker Compose")
        rd = groups["docker:redis"]
        self.assertEqual((rd["name"], rd["kind"], rd["port"]), ("redis", "Docker", 6379))

    def test_docker_ports_leave_the_unknown_list(self):
        groups = sv.docker_groups(sv.parse_docker_ps(PS))
        items = sv.without_docker(sv.parse_ss(SS), groups)
        self.assertEqual(sorted(items), [9000])


class ConfigTest(unittest.TestCase):
    def test_docker_entries_are_kept(self):
        from isla_dinamica import config as cfgmod
        entry = {"name": "opengym", "port": 8080, "kind": "Docker Compose",
                 "docker": ["opengym-api-1", "opengym-web-1"], "when": 3}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w") as f:
                json.dump({"servers_recent": [entry, {"docker": [], "name": "x"}, {"docker": "x"}]}, f)
            with mock.patch.object(cfgmod, "CONFIG_PATH", path):
                c = cfgmod.Config()
        self.assertEqual(len(c.data["servers_recent"]), 1)
        got = c.data["servers_recent"][0]
        self.assertEqual((got["name"], got["docker"], got["port"]), ("opengym", ["opengym-api-1", "opengym-web-1"], 8080))


class FirstScanTest(unittest.TestCase):
    def test_docker_found_on_the_first_scan_refreshes_the_page(self):
        changes, events = [], []
        with mock.patch.object(sv, "run"), mock.patch.object(sv.GLib, "timeout_add_seconds"):
            s = sv.Servers(lambda: changes.append(1), lambda k, x: events.append(k))
        s.apply({}, sv.docker_groups(sv.parse_docker_ps(PS)))
        self.assertTrue(changes)            # la página se vuelve a pintar con opengym y redis
        self.assertEqual(events, [])        # pero sin avisos de «Listo» al arrancar la isla


class OneEntryPerProjectTest(unittest.TestCase):
    """Compose para los contenedores de uno en uno: el proyecto se recuerda una sola vez, con todos."""
    def test_same_project_is_merged(self):
        rec = sv.remember([], {"name": "opengym", "port": 8080, "kind": "Docker Compose",
                               "docker": ["opengym-api-1", "opengym-web-1"]}, now=1)
        rec = sv.remember(rec, {"name": "opengym", "port": None, "kind": "Docker Compose",
                                "docker": ["opengym-api-1"]}, now=2)
        self.assertEqual(len(rec), 1)
        self.assertEqual((rec[0]["docker"], rec[0]["port"], rec[0]["when"]),
                         (["opengym-api-1", "opengym-web-1"], 8080, 2))

    def test_config_merges_old_duplicates(self):
        from isla_dinamica import config as cfgmod
        dup = [{"name": "opengym", "port": None, "kind": "Docker Compose", "docker": ["opengym-api-1"], "when": 2},
               {"name": "opengym", "port": 8080, "kind": "Docker Compose",
                "docker": ["opengym-api-1", "opengym-web-1"], "when": 1}]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w") as f:
                json.dump({"servers_recent": dup}, f)
            with mock.patch.object(cfgmod, "CONFIG_PATH", path):
                c = cfgmod.Config()
        self.assertEqual([(r["docker"], r["port"]) for r in c.data["servers_recent"]],
                         [(["opengym-api-1", "opengym-web-1"], 8080)])


class DockerNameTest(unittest.TestCase):
    """S16: un nombre de contenedor no puede convertirse en una opción de `docker`."""
    def test_config_drops_option_like_names(self):
        from isla_dinamica import config as cfgmod
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w") as f:
                json.dump({"servers_recent": [{"name": "x", "docker": ["--privileged", "ok-1"]},
                                              {"name": "y", "docker": ["web_1", "api.2"]}]}, f)
            with mock.patch.object(cfgmod, "CONFIG_PATH", path):
                c = cfgmod.Config()
        self.assertEqual([r["docker"] for r in c.data["servers_recent"]], [["web_1", "api.2"]])

    def test_relaunch_refuses_bad_names_and_ends_options(self):
        calls = []
        with mock.patch.object(sv, "run"), mock.patch.object(sv.GLib, "timeout_add_seconds"):
            s = sv.Servers(lambda: None, lambda k, x: None,
                           recent=lambda: [{"name": "x", "docker": ["-v"]}, {"name": "y", "docker": ["web"]}])
        with mock.patch.object(sv, "run", lambda argv, cb=None, **_k: calls.append(argv)):
            ok, _ = s.relaunch(0)
            self.assertFalse(ok)
            s.relaunch(1)
        self.assertEqual(calls, [["docker", "start", "--", "web"]])


class ManualScanTest(unittest.TestCase):
    def test_scan_runs_ss_and_docker_and_reports_how_many_it_found(self):
        calls, got = [], []

        def run(argv, cb=None, **_kw):
            calls.append(argv[:2])
            cb(True, SS if argv[0] == "ss" else PS, "")
        with mock.patch.object(sv, "run"), mock.patch.object(sv.GLib, "timeout_add_seconds"):
            s = sv.Servers(lambda: None, lambda k, x: None)
        s._has_docker = True
        with mock.patch.object(sv, "run", run):
            s.scan(got.append)
        self.assertEqual(calls, [["ss", "-ltnpH"], ["docker", "ps"]])
        self.assertEqual(got, [3])          # :9000 suelto + opengym + redis

    def test_scan_still_answers_if_ss_fails(self):
        got = []
        with mock.patch.object(sv, "run"), mock.patch.object(sv.GLib, "timeout_add_seconds"):
            s = sv.Servers(lambda: None, lambda k, x: None)
        with mock.patch.object(sv, "run", lambda argv, cb=None, **_k: cb(False, "", "ss: error")):
            s.scan(got.append)
        self.assertEqual(got, [None])


class DockerFlowTest(unittest.TestCase):
    def make(self):
        self.events, self.saved, self.calls = [], [], []
        with mock.patch.object(sv, "run"), mock.patch.object(sv.GLib, "timeout_add_seconds"):
            s = sv.Servers(lambda: None, lambda k, x: self.events.append((k, x["name"])),
                           recent=lambda: self.saved[-1] if self.saved else [],
                           save_recent=self.saved.append, logs=tempfile.gettempdir())
        s.apply({}, {})
        s.apply({}, sv.docker_groups(sv.parse_docker_ps(PS)))
        self.events.clear()
        return s

    def fake_run(self, ok=True):
        def run(argv, cb=None, **_kw):
            self.calls.append(argv)
            if cb:
                cb(ok, "", "" if ok else "Error: No such container")
        return run

    def test_stop_project_stops_all_its_containers_and_remembers_them(self):
        s = self.make()
        with mock.patch.object(sv, "run", self.fake_run()):
            s.docker_stop("docker:opengym")
        self.assertEqual(self.calls[-1], ["docker", "stop", "--", "opengym-api-1", "opengym-web-1"])
        self.assertEqual(self.saved[-1][0]["docker"], ["opengym-api-1", "opengym-web-1"])
        s.apply({}, {k: v for k, v in sv.docker_groups(sv.parse_docker_ps(PS)).items() if k != "docker:opengym"})
        self.assertEqual(self.events, [("stopped", "opengym")])

    def test_restart_uses_docker_restart(self):
        s = self.make()
        with mock.patch.object(sv, "run", self.fake_run()):
            s.docker_restart("docker:redis")
        self.assertEqual(self.calls[-1], ["docker", "restart", "--", "redis"])
        self.assertEqual(self.events, [("restarting", "redis")])

    def test_a_project_that_falls_is_remembered(self):
        s = self.make()
        s.apply({}, {})
        self.assertIn(("down", "opengym"), self.events)
        self.assertEqual({tuple(r["docker"]) for r in self.saved[-1]},
                         {("opengym-api-1", "opengym-web-1"), ("redis",)})

    def test_relaunch_a_stopped_project_with_docker_start(self):
        s = self.make()
        with mock.patch.object(sv, "run", self.fake_run()):
            s.docker_stop("docker:opengym")
        s.apply({}, {k: v for k, v in sv.docker_groups(sv.parse_docker_ps(PS)).items() if k == "docker:redis"})
        self.events.clear()
        with mock.patch.object(sv, "run", self.fake_run()):
            ok, _ = s.relaunch(0)
        self.assertTrue(ok)
        self.assertEqual(self.calls[-1], ["docker", "start", "--", "opengym-api-1", "opengym-web-1"])

    def test_failed_docker_start_is_reported(self):
        s = self.make()
        with mock.patch.object(sv, "run", self.fake_run()):
            s.docker_stop("docker:redis")
        with mock.patch.object(sv, "run", self.fake_run(ok=False)):
            s.relaunch(0)
        self.assertIn(("failed", "redis"), self.events)

    def test_running_docker_groups_are_hidden_from_stopped(self):
        s = self.make()
        with mock.patch.object(sv, "run", self.fake_run()):
            s.docker_stop("docker:redis")
        self.assertEqual(s.stopped(), [])          # aún corre: no sale en DETENIDOS
        s.apply({}, {})
        self.assertEqual([r["name"] for _i, r in s.stopped()], ["opengym", "redis"])


if __name__ == "__main__":
    unittest.main()
