"""Página «Tareas en curso» y burbuja «+N» (B7): interruptor, filas y registro de la página."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica import config  # noqa: E402
from isla_dinamica.pages import PAGE_CLASSES  # noqa: E402
from isla_dinamica.pages.registry import FEATURES  # noqa: E402
from isla_dinamica.pages.tasks import task_rows  # noqa: E402


class TasksFeatureTest(unittest.TestCase):
    def test_registered_in_more(self):
        entries = [f for f in FEATURES if f["key"] == "bub_more"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Burbuja de tareas")
        self.assertTrue(entries[0]["desc"])

    def test_enabled_by_default(self):
        self.assertTrue(config.FEATURE_DEFAULTS.get("bub_more", True))


class TaskRowsTest(unittest.TestCase):
    def test_rows_keep_priority_order_with_label_and_state(self):
        acts = [{"key": "call", "label": "Llamada", "icon": "call-start-symbolic", "page": "home",
                 "tip": "Meet · 0:12"},
                {"key": "pomo", "label": "Pomodoro", "icon": "timer-symbolic", "page": "pomo",
                 "tip": "Enfoque · 12:30"}]
        self.assertEqual(task_rows(acts), [
            ("call", "call-start-symbolic", "Llamada", "Meet · 0:12", "home"),
            ("pomo", "timer-symbolic", "Pomodoro", "Enfoque · 12:30", "pomo")])

    def test_bluetooth_uses_device_name_as_title(self):
        acts = [{"key": "bt", "icon": "audio-headphones-symbolic", "page": "bt", "tip": "BT · 80%"}]
        self.assertEqual(task_rows(acts), [("bt", "audio-headphones-symbolic", "BT", "BT · 80%", "bt")])

    def test_media_row_without_icon_falls_back(self):
        acts = [{"key": "media", "label": "Música", "icon": None, "page": "home", "tip": ""}]
        self.assertEqual(task_rows(acts), [("media", "audio-x-generic-symbolic", "Música", "", "home")])

    def test_empty(self):
        self.assertEqual(task_rows([]), [])


class TasksPageRegisteredTest(unittest.TestCase):
    def test_tasks_page_exists(self):
        pages = {n for cls in PAGE_CLASSES for n in cls.PAGES}
        self.assertIn("tasks", pages)


if __name__ == "__main__":
    unittest.main()
