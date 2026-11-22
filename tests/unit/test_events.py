"""EventRouter: traduce los eventos de los servicios en avisos de la píldora (sin GTK)."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.events import EventRouter  # noqa: E402


class FakeCore:
    def __init__(self):
        self.shown, self.opened = [], []
        self.charge_limit = NS(enabled=True, end=80, supported=True)
        self.weather = NS(data=None)

    def show_event(self, secs=3.0, **ev):
        self.shown.append(dict(ev, secs=secs))

    def open_github(self, url=None):
        self.opened.append(url)

    def alert(self, app, icon, title, body="", action=None, secs=10.0):
        self.shown.append({"kind": "alert", "app": app, "icon": icon, "title": title, "body": body,
                           "action": action, "secs": secs})

    def feature(self, name):
        return True

    def charge_target(self):
        return 80


class EventRouterTest(unittest.TestCase):
    def setUp(self):
        self.core = FakeCore()
        self.ev = EventRouter(self.core, play=lambda *a: None)

    def last(self):
        return self.core.shown[-1]

    def test_deploy_start_is_orange_pill(self):
        self.ev.deploy("start", {"name": "api", "env": "qa", "state": "IN_PROGRESS"})
        e = self.last()
        self.assertEqual((e["kind"], e["accent"], e["text"]), ("pill", "orange", "Desplegando api · qa"))

    def test_deploy_failure_is_card_with_action(self):
        self.ev.deploy("done", {"name": "api", "env": "qa", "state": "FAILURE", "commit": "fix",
                                "repo": "o/api", "url": "https://x"})
        e = self.last()
        self.assertEqual((e["kind"], e["app"], e["title"]), ("card", "Despliegue fallido", "api · qa"))
        self.assertTrue(callable(e["action"]))

    def test_deploy_success_is_green(self):
        self.ev.deploy("done", {"name": "api", "env": "qa", "state": "SUCCESS"})
        self.assertEqual(self.last()["accent"], "green")

    def test_github_review_opens_pr(self):
        p = {"repo": "o/r", "num": 3, "title": "T", "author": "ana", "url": "https://github.com/o/r/pull/3"}
        self.ev.github("review", p)
        self.last()["action"]()
        self.assertEqual(self.core.opened, ["https://github.com/o/r/pull/3"])

    def test_github_ci(self):
        self.ev.github("ci", {"repo": "o/r", "num": 3, "ci": "FAILURE", "url": "u"})
        self.assertEqual((self.last()["kind"], self.last()["title"]), ("alert", "CI falló · o/r#3"))

    def test_github_inbox_alert_opens_thread(self):
        self.ev.github("inbox", {"kind": "PR", "title": "Nueva PR", "repo": "o/r", "reason": "repo que sigues",
                                 "url": "https://github.com/o/r/pull/9"})
        e = self.last()
        self.assertEqual((e["app"], e["title"], e["body"]), ("GitHub · PR", "Nueva PR", "o/r · repo que sigues"))
        e["action"]()
        self.assertEqual(self.core.opened, ["https://github.com/o/r/pull/9"])

    def test_github_inbox_summary(self):
        items = [{"repo": r} for r in ("a/1", "a/2", "a/3", "a/4", "a/1")]
        self.ev.github("inbox_summary", {"count": 5, "items": items})
        self.assertEqual((self.last()["title"], self.last()["body"]), ("5 novedades sin leer", "a/1, a/2, a/3 y 1 más"))

    def test_github_merged(self):
        self.ev.github("merged", {"repo": "o/r", "num": 4, "title": "Feat", "url": "u"})
        self.assertEqual((self.last()["app"], self.last()["body"]), ("GitHub · PR fusionada", "o/r#4"))

    def test_battery_full_respects_charge_limit(self):
        self.ev.battery("full", 80)
        self.assertIn("80 %", self.last()["title"])

    def test_battery_charging_shows_limit(self):
        self.ev.battery("charging", 50)
        self.assertEqual(self.last()["right"], "50% · hasta 80%")

    def test_net_and_sysmon_and_servers(self):
        self.ev.net("offline", None)
        self.assertEqual(self.last()["text"], "Sin Internet")
        self.ev.sysmon("cpu", "chrome", 99.0)
        self.assertEqual(self.last()["text"], "chrome usa mucha CPU")
        self.ev.server("down", {"name": "vite", "port": 5173})
        self.assertEqual(self.last()["text"], "Se cayó · vite · :5173")

    def test_privacy(self):
        self.ev.privacy("mic", ["Chrome", "Zoom"])
        self.assertEqual((self.last()["accent"], self.last()["text"]),
                         ("orange", "Chrome, Zoom está usando el micrófono"))

    def test_rain_warning_only_once_per_hour(self):
        self.core.weather = NS(data={"soon": {"hour": "15:00", "kind": "rain", "pop": 80}})
        self.ev.weather()
        self.ev.weather()
        self.assertEqual(len(self.core.shown), 1)
        self.assertEqual(self.last()["text"], "Lluvia hacia las 15:00")

    def test_git_plural(self):
        self.ev.git("behind", {"name": "api", "behind": 1, "upstream": "origin/main", "path": "/r"})
        self.assertEqual(self.last()["title"], "1 commit nuevo en origin/main")
        self.ev.git("behind", {"name": "api", "behind": 3, "upstream": "origin/main", "path": "/r"})
        self.assertEqual(self.last()["title"], "3 commits nuevos en origin/main")

    def test_git_ahead(self):
        self.ev.git("ahead", {"name": "api", "ahead": 2, "branch": "main", "upstream": "origin/main", "path": "/r"})
        self.assertEqual((self.last()["app"], self.last()["title"]), ("Git · api", "2 commits sin subir"))


if __name__ == "__main__":
    unittest.main()
