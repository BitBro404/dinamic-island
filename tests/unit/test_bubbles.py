"""Burbujas de actividades: qué hay en curso y dónde se dibuja cada burbuja (caracterización)."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.ui.bubbles import activities, bubble_rects  # noqa: E402


def core(features=(), **over):
    c = NS(
        feature=lambda name: name in features,
        audio=NS(call=None, call_since=0, audible=False, outputs=[]),
        art=None,
        pomo=NS(active=False, phase="work", left=lambda: 0, length=lambda ph: 1500),
        recorder=NS(active=False, elapsed=lambda: 0),
        reminders=NS(next=lambda: None),
        deploys=NS(active=lambda: []),
        downloads=NS(active=[], main=lambda: None),
        presence=NS(state="off"),
        timer_total=0)
    for k, v in over.items():
        setattr(c, k, v)
    return c


def keys(acts):
    return [a["key"] for a in acts]


class ActivitiesTest(unittest.TestCase):
    def test_nothing(self):
        self.assertEqual(activities(core(), None, False, None, now=0, wall=0), [])

    def test_order_call_music_pomodoro_rest(self):
        c = core(("audio", "reminders", "deploys", "downloads", "presence"),
                 audio=NS(call="Meet", call_since=0, audible=True, outputs=["Chrome"]),
                 pomo=NS(active=True, phase="work", left=lambda: 750, length=lambda ph: 1500),
                 recorder=NS(active=True, elapsed=lambda: 3),
                 reminders=NS(next=lambda: {"text": "daily", "at": 100}),
                 deploys=NS(active=lambda: [{"name": "api", "env": "qa"}]),
                 downloads=NS(active=[1], main=lambda: {"name": "x.zip"}),
                 presence=NS(state="present"), timer_total=60)
        acts = activities(c, {"title": "Canción", "artist": "A"}, True, 30, now=0, wall=0)
        self.assertEqual(keys(acts), ["call", "media", "pomo", "rec", "reminder", "deploy", "download",
                                      "presence", "timer"])
        self.assertAlmostEqual(next(a for a in acts if a["key"] == "pomo")["progress"], 0.5)
        self.assertAlmostEqual(next(a for a in acts if a["key"] == "timer")["progress"], 0.5)

    def test_features_off_hide_activities(self):
        c = core((), audio=NS(call="Meet", call_since=0, audible=True, outputs=["x"]),
                 deploys=NS(active=lambda: [{"name": "api", "env": "qa"}]), presence=NS(state="present"))
        self.assertEqual(activities(c, None, False, None, now=0, wall=0), [])

    def test_reminder_only_in_last_five_minutes(self):
        c = core(("reminders",), reminders=NS(next=lambda: {"text": "x", "at": 1000}))
        self.assertEqual(activities(c, None, False, None, now=0, wall=600), [])
        self.assertEqual(keys(activities(c, None, False, None, now=0, wall=701)), ["reminder"])

    def test_other_audio_only_without_music_or_call(self):
        au = NS(call=None, call_since=0, audible=True, outputs=["Firefox"])
        self.assertEqual(keys(activities(core(("audio",), audio=au), None, False, None, now=0, wall=0)), ["audio"])
        self.assertNotIn("audio", keys(activities(core(("audio",), audio=au), {"title": "t"}, True, None,
                                                  now=0, wall=0)))


class BubbleRectsTest(unittest.TestCase):
    def test_horizontal_at_the_right_end(self):
        self.assertEqual(bubble_rects(2, 300, 40, vertical=False, size=34, gap=6),
                         [(300 - 74, 3.0), (300 - 34, 3.0)])

    def test_vertical_at_the_bottom(self):
        self.assertEqual(bubble_rects(1, 34, 200, vertical=True, size=34, gap=6), [(0.0, 200 - 34)])


if __name__ == "__main__":
    unittest.main()
