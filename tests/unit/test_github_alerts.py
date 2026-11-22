"""Alertas de GitHub y git: bandeja de notificaciones, PR fusionadas y commits sin subir (sin red ni GTK)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services import gitwatch  # noqa: E402
from isla_dinamica.services.github import GitHub, html_url, inbox_item  # noqa: E402


def raw(i, updated="2026-11-22T10:00:00Z", kind="PullRequest", path="pulls/4", reason="subscribed"):
    return {"id": str(i), "updated_at": updated, "reason": reason, "unread": True,
            "repository": {"full_name": "o/r"},
            "subject": {"title": f"T{i}", "type": kind, "url": f"https://api.github.com/repos/o/r/{path}"}}


def bare_github():
    g = GitHub.__new__(GitHub)          # sin __init__: no lanza gh ni temporizadores
    g.events = []
    g.on_event = lambda kind, p: g.events.append((kind, p))
    g._seen, g._merged, g._known, g._prev = None, None, None, {}
    g.mine, g.review, g.merged, g.inbox = [], [], [], []
    return g


class HtmlUrlTest(unittest.TestCase):
    def test_pull_commit_issue_release(self):
        base = "https://api.github.com/repos/o/r/"
        self.assertEqual(html_url(base + "pulls/4", "o/r"), "https://github.com/o/r/pull/4")
        self.assertEqual(html_url(base + "commits/abc", "o/r"), "https://github.com/o/r/commit/abc")
        self.assertEqual(html_url(base + "issues/7", "o/r"), "https://github.com/o/r/issues/7")
        self.assertEqual(html_url(base + "releases/99", "o/r"), "https://github.com/o/r/releases")

    def test_without_url_falls_back_to_repo(self):
        self.assertEqual(html_url(None, "o/r"), "https://github.com/o/r")

    def test_item(self):
        i = inbox_item(raw(1))
        self.assertEqual((i["kind"], i["reason"], i["url"]), ("PR", "repo que sigues", "https://github.com/o/r/pull/4"))


class InboxTest(unittest.TestCase):
    def test_first_load_is_one_summary_then_only_new_ones(self):
        g = bare_github()
        g.inbox = [inbox_item(raw(1)), inbox_item(raw(2))]
        g._notify_inbox()
        self.assertEqual([k for k, _ in g.events], ["inbox_summary"])
        g.events.clear()
        g.inbox = [inbox_item(raw(3)), inbox_item(raw(1)), inbox_item(raw(2))]
        g._notify_inbox()
        self.assertEqual([(k, p["title"]) for k, p in g.events], [("inbox", "T3")])

    def test_same_thread_updated_again_alerts_again(self):
        g = bare_github()
        g.inbox = [inbox_item(raw(1))]
        g._notify_inbox()
        g.events.clear()
        g.inbox = [inbox_item(raw(1, updated="2026-11-22T11:00:00Z"))]
        g._notify_inbox()
        self.assertEqual(len(g.events), 1)

    def test_many_new_at_once_is_a_summary(self):
        g = bare_github()
        g.inbox = []
        g._notify_inbox()
        g.inbox = [inbox_item(raw(i)) for i in range(7)]
        g._notify_inbox()
        self.assertEqual([k for k, _ in g.events], ["inbox_summary"])

    def test_merged_pr_alerts_after_first_load(self):
        g = bare_github()
        g.merged = [{"id": "a"}]
        g._notify_changes()
        g.merged = [{"id": "b"}, {"id": "a"}]
        g._notify_changes()
        self.assertEqual(g.events, [("merged", {"id": "b"})])


class AheadTest(unittest.TestCase):
    def setUp(self):
        self.w = gitwatch.GitWatch.__new__(gitwatch.GitWatch)
        self.events = []
        self.w.on_event = lambda kind, s: self.events.append(kind)
        self.w._ahead_since, self.w._ahead_warned = {}, set()
        self.s = {"path": "/r", "ahead": 2, "upstream": "origin/main"}

    def test_alerts_once_after_grace_and_rearms_after_push(self):
        self.w._check_ahead(self.s, now=0)
        self.w._check_ahead(self.s, now=gitwatch.AHEAD_GRACE - 1)
        self.assertEqual(self.events, [])
        self.w._check_ahead(self.s, now=gitwatch.AHEAD_GRACE)
        self.w._check_ahead(self.s, now=gitwatch.AHEAD_GRACE * 3)
        self.assertEqual(self.events, ["ahead"])
        self.w._check_ahead(dict(self.s, ahead=0), now=gitwatch.AHEAD_GRACE * 4)
        self.w._check_ahead(self.s, now=gitwatch.AHEAD_GRACE * 5)
        self.w._check_ahead(self.s, now=gitwatch.AHEAD_GRACE * 6)
        self.assertEqual(self.events, ["ahead", "ahead"])

    def test_branch_without_remote_never_alerts(self):
        self.w._check_ahead(dict(self.s, upstream=None), now=0)
        self.w._check_ahead(dict(self.s, upstream=None), now=gitwatch.AHEAD_GRACE * 2)
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
