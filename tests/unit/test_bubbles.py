"""Burbujas de actividades: qué hay en curso y dónde se dibuja cada burbuja (caracterización)."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.ui.bubbles import (activities, bluetooth_activity, bubble_rects, bubble_slots,  # noqa: E402
                                      bubble_tip)


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
        bt=NS(devices={}),
        timer_total=0)
    for k, v in over.items():
        setattr(c, k, v)
    return c


def keys(acts):
    return [a["key"] for a in acts]


def bt_device(name="Auriculares", connected=True, battery=82, icon="audio-headphones-symbolic"):
    return {"path": "/dev/" + name, "name": name, "connected": connected, "icon": icon, "battery": battery}


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


class BluetoothBubbleTest(unittest.TestCase):
    def test_no_connected_device(self):
        self.assertIsNone(bluetooth_activity({}))
        self.assertIsNone(bluetooth_activity({"a": bt_device(connected=False)}))

    def test_first_connected_by_name(self):
        devs = {"z": bt_device("Ratón"), "a": bt_device("Auriculares", battery=41, icon="audio-headphones-symbolic")}
        act = bluetooth_activity(devs)
        self.assertEqual(act["key"], "bt")
        self.assertEqual(act["icon"], "audio-headphones-symbolic")
        self.assertEqual(act["accent"], "blue")
        self.assertEqual(act["page"], "bt")
        self.assertEqual(act["tip"], "Auriculares · 41%")
        self.assertAlmostEqual(act["progress"], 0.41)

    def test_battery_limits(self):
        for battery, pct, progress in ((0, "0%", 0.0), (100, "100%", 1.0)):
            act = bluetooth_activity({"a": bt_device(battery=battery)})
            self.assertEqual(act["tip"], f"Auriculares · {pct}")
            self.assertAlmostEqual(act["progress"], progress)

    def test_unknown_battery_shows_only_name(self):
        for battery in (None, True, "82", -1, 101):
            with self.subTest(battery=battery):
                act = bluetooth_activity({"a": bt_device(battery=battery)})
                self.assertEqual(act["tip"], "Auriculares")
                self.assertIsNone(act["progress"])
        self.assertIsNone(bluetooth_activity({"a": {"path": "/dev/a", "name": "Auriculares",
                                                    "connected": True, "icon": "bluetooth-active"}})["progress"])

    def test_missing_name_falls_back(self):
        dev = bt_device()
        del dev["name"]
        self.assertEqual(bluetooth_activity({"a": dev})["tip"], "Dispositivo · 82%")

    def test_activities_respects_feature_and_order(self):
        c = core(("bt_bubble",), bt=NS(devices={"a": bt_device()}),
                 pomo=NS(active=True, phase="work", left=lambda: 750, length=lambda ph: 1500))
        acts = activities(c, None, False, None, now=0, wall=0)
        self.assertEqual(keys(acts), ["pomo", "bt"])
        self.assertEqual(acts[1]["page"], "bt")
        self.assertEqual(keys(activities(core((), bt=NS(devices={"a": bt_device()})), None, False, None,
                                       now=0, wall=0)), [])
        self.assertEqual(activities(core(("bt_bubble",)), None, False, None, now=0, wall=0), [])
        no_bt = core(("bt_bubble",))
        del no_bt.bt
        self.assertEqual(activities(no_bt, None, False, None, now=0, wall=0), [])


class BubbleTipTest(unittest.TestCase):
    def test_bluetooth_keeps_device_and_battery(self):
        self.assertEqual(bubble_tip({"tip": "BT · 80%"}), "BT · 80%")

    def test_other_activities_prefix_the_option_name(self):
        self.assertEqual(bubble_tip({"label": "Pomodoro", "tip": "Enfoque · 12:30"}),
                         "Pomodoro · Enfoque · 12:30")
        self.assertEqual(bubble_tip({"label": "Música", "tip": "Canción · Artista"}),
                         "Música · Canción · Artista")

    def test_missing_parts(self):
        self.assertEqual(bubble_tip({}), "")
        self.assertEqual(bubble_tip({"label": "Presencia"}), "Presencia")

    def test_activities_label_every_activity_except_bluetooth(self):
        c = core(("audio", "reminders", "deploys", "downloads", "presence", "bt_bubble"),
                 audio=NS(call="Meet", call_since=0, audible=True, outputs=["Chrome"]),
                 pomo=NS(active=True, phase="work", left=lambda: 750, length=lambda ph: 1500),
                 recorder=NS(active=True, elapsed=lambda: 3),
                 reminders=NS(next=lambda: {"text": "daily", "at": 100}),
                 deploys=NS(active=lambda: [{"name": "api", "env": "qa"}]),
                 downloads=NS(active=[1], main=lambda: {"name": "x.zip"}),
                 presence=NS(state="present"),
                 bt=NS(devices={"a": bt_device("BT", battery=80)}), timer_total=60)
        acts = activities(c, {"title": "Canción", "artist": "Artista"}, True, 30, now=0, wall=0)
        expected = {"call": "Llamada", "media": "Música", "pomo": "Pomodoro", "bt": None,
                    "rec": "Grabación", "reminder": "Recordatorio", "deploy": "Despliegues",
                    "download": "Descargas", "presence": "Presencia", "timer": "Temporizador"}
        self.assertEqual({a["key"]: a.get("label") for a in acts}, expected)
        self.assertEqual(bubble_tip(next(a for a in acts if a["key"] == "pomo")), "Pomodoro · Enfoque · 12:30")
        self.assertEqual(bubble_tip(next(a for a in acts if a["key"] == "rec")), "Grabación · 0:03")
        self.assertEqual(bubble_tip(next(a for a in acts if a["key"] == "bt")), "BT · 80%")
        self.assertEqual(bubble_tip(next(a for a in acts if a["key"] == "download")), "Descargas · x.zip")

    def test_every_bubble_opens_a_registered_page_and_has_a_tooltip(self):
        # hover = tooltip y clic = abrir página valen para todas las burbujas, no solo Bluetooth
        from isla_dinamica.pages import PAGE_CLASSES
        pages = {n for cls in PAGE_CLASSES for n in cls.PAGES}
        busy = dict(audio=NS(call="Meet", call_since=0, audible=True, outputs=["Chrome"]),
                    pomo=NS(active=True, phase="work", left=lambda: 750, length=lambda ph: 1500),
                    recorder=NS(active=True, elapsed=lambda: 3),
                    reminders=NS(next=lambda: {"text": "daily", "at": 100}),
                    deploys=NS(active=lambda: [{"name": "api", "env": "qa"}]),
                    downloads=NS(active=[1], main=lambda: {"name": "x.zip"}),
                    presence=NS(state="present"),
                    bt=NS(devices={"a": bt_device("BT", battery=80)}), timer_total=60)
        feats = ("audio", "reminders", "deploys", "downloads", "presence", "bt_bubble")
        acts = activities(core(feats, **busy), {"title": "Canción", "artist": "A"}, True, 30, now=0, wall=0)
        busy["audio"] = NS(call=None, call_since=0, audible=True, outputs=["Chrome"])
        acts += activities(core(feats, **busy), None, False, None, now=0, wall=0)   # «audio» sin música
        self.assertEqual({a["key"] for a in acts}, {"call", "media", "pomo", "bt", "rec", "reminder", "deploy",
                                                     "download", "audio", "presence", "timer"})
        for a in acts:
            self.assertIn(a["page"], pages, a["key"])
            self.assertTrue(bubble_tip(a), a["key"])


def _acts(*keys):
    return [{"key": k, "label": k.title(), "page": k, "tip": "x"} for k in keys]


class BubbleSlotsTest(unittest.TestCase):
    """Burbuja «+N»: 2 burbujas reales y, si sobran, una extra con cuántas quedan ocultas (B7)."""

    def test_two_fit_without_more(self):
        self.assertEqual([a["key"] for a in bubble_slots(_acts("pomo", "bt"), set(), 2, True)], ["pomo", "bt"])

    def test_overflow_adds_more_with_hidden_count(self):
        slots = bubble_slots(_acts("pomo", "bt", "rec", "download"), set(), 2, True)
        self.assertEqual([a["key"] for a in slots], ["pomo", "bt", "more"])
        more = slots[-1]
        self.assertEqual((more["count"], more["page"], more["label"]), (2, "tasks", "Tareas en curso"))
        self.assertEqual(bubble_tip(more), "Tareas en curso · 2 más")
        self.assertIsNone(more.get("progress"))

    def test_disabled_keeps_current_behaviour(self):
        self.assertEqual([a["key"] for a in bubble_slots(_acts("pomo", "bt", "rec"), set(), 2, False)],
                         ["pomo", "bt"])

    def test_activity_in_the_pill_is_not_counted(self):
        slots = bubble_slots(_acts("call", "pomo", "bt", "rec"), {"call"}, 2, True)
        self.assertEqual([a["key"] for a in slots], ["pomo", "bt", "more"])
        self.assertEqual(slots[-1]["count"], 1)
        self.assertEqual([a["key"] for a in bubble_slots(_acts("call", "pomo", "bt"), {"call"}, 2, True)],
                         ["pomo", "bt"])

    def test_empty(self):
        self.assertEqual(bubble_slots([], set(), 2, True), [])


class BubbleRectsTest(unittest.TestCase):
    def test_horizontal_at_the_right_end(self):
        self.assertEqual(bubble_rects(2, 300, 40, vertical=False, size=34, gap=6),
                         [(300 - 74, 3.0), (300 - 34, 3.0)])

    def test_vertical_at_the_bottom(self):
        self.assertEqual(bubble_rects(1, 34, 200, vertical=True, size=34, gap=6), [(0.0, 200 - 34)])


if __name__ == "__main__":
    unittest.main()
