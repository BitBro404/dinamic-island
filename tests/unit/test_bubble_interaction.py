"""Interacción de las burbujas: hover = tooltip (sin expandir), clic = abrir la página.

Usa los métodos reales de IslandWindow con un objeto falso, sin construir GTK.
"""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.window import IslandWindow  # noqa: E402


class FakeWindow:
    """Solo lo que _set_hover/_on_click necesitan de la ventana."""
    _on_click = IslandWindow._on_click
    _set_hover = IslandWindow._set_hover
    _bubble_clicked = IslandWindow._bubble_clicked
    _on_drag_end = IslandWindow._on_drag_end
    _tap = IslandWindow._tap
    _tapped = IslandWindow._tapped

    def __init__(self, view="compact", bubble=0, page="home"):
        self.view, self.bubble, self.page = view, bubble, page
        self.bubbles = [{"key": "bt", "page": "bt"}]
        self.hover, self._hover_src = False, None
        self.drag, self._drag_end = None, 0
        self.drops, self._tap_t = 0, 0.0
        self.card_hold, self._nav_t = False, 0
        self.opened, self.refreshes = [], 0
        self.core = NS(event=None, radios=NS(refresh=lambda: None), recorder=NS(active=False))
        self.page_objs = []

    def _bubble_at(self):
        return self.bubble

    def _opened(self, page):
        self.opened.append(page)

    def refresh(self):
        self.refreshes += 1
        return False

    def _drop(self):
        self.drops += 1


class BubbleInteractionTest(unittest.TestCase):
    def test_hover_over_bubble_does_not_expand_or_open(self):
        w = FakeWindow(bubble=0)
        self.assertFalse(w._set_hover(True))
        self.assertFalse(w.hover)
        self.assertEqual(w.opened, [])
        self.assertEqual(w.page, "home")

    def test_click_on_bubble_opens_its_page(self):
        w = FakeWindow(bubble=0)
        w._on_click(NS(), NS(button=1))
        self.assertTrue(w.hover)
        self.assertEqual(w.page, "bt")
        self.assertEqual(w.opened, ["bt"])

    def test_click_on_pill_just_expands_home(self):
        w = FakeWindow(bubble=None)
        w._on_click(NS(), NS(button=1))
        self.assertTrue(w.hover)
        self.assertEqual(w.page, "home")
        self.assertEqual(w.opened, [])

    def test_click_outside_compact_does_nothing(self):
        w = FakeWindow(view="card", bubble=0)
        self.assertFalse(w._on_click(NS(), NS(button=1)))
        self.assertFalse(w.hover)

    def test_direct_widget_click_opens_page_even_if_pointer_detection_fails(self):
        # el ratón real a veces no cae dentro del rectángulo calculado: el widget sabe qué burbuja es
        w = FakeWindow(bubble=None)
        self.assertTrue(w._bubble_clicked(0, NS(button=1)))
        self.assertTrue(w.hover)
        self.assertEqual(w.page, "bt")
        self.assertEqual(w.opened, ["bt"])

    def test_direct_widget_click_second_bubble(self):
        # el usuario tiene pomodoro + Bluetooth: clic en la segunda abre Bluetooth, no la primera
        w = FakeWindow(bubble=None)
        w.bubbles = [{"page": "pomo"}, {"page": "bt"}]
        self.assertTrue(w._bubble_clicked(1, NS(button=1)))
        self.assertEqual(w.page, "bt")
        self.assertEqual(w.opened, ["bt"])

    def test_direct_widget_click_ignores_other_buttons(self):
        w = FakeWindow(bubble=0)
        self.assertFalse(w._bubble_clicked(0, NS(button=3)))
        self.assertFalse(w.hover)
        self.assertEqual(w.opened, [])



class RealPointerClickTest(unittest.TestCase):
    """En el escritorio real el gesto de arrastre (fase CAPTURE) se queda con el clic: solo llega drag-end,
    nunca el button-release del EventBox ni de la burbuja (log real 2026-11-21). El clic sale del gesto."""

    def test_drag_end_without_movement_on_bubble_opens_its_page(self):
        w = FakeWindow(bubble=0)
        w.drag = {"start": (400, 20), "moving": False}
        w._on_drag_end(NS(), 0.0, 0.0)
        self.assertTrue(w.hover)
        self.assertEqual(w.page, "bt")
        self.assertEqual(w.opened, ["bt"])

    def test_drag_end_when_poll_already_cleared_drag_still_clicks(self):
        # _drag_poll puede ver el botón suelto antes que drag-end y poner drag=None
        w = FakeWindow(bubble=0)
        w._on_drag_end(NS(), 0.0, 0.0)
        self.assertEqual(w.page, "bt")

    def test_drag_end_without_movement_on_pill_expands_home(self):
        w = FakeWindow(bubble=None)
        w._on_drag_end(NS(), 0.0, 0.0)
        self.assertTrue(w.hover)
        self.assertEqual(w.page, "home")

    def test_real_drag_drops_and_does_not_open(self):
        w = FakeWindow(bubble=0)
        w.drag = {"start": (400, 20), "moving": True}
        w._on_drag_end(NS(), 80.0, 0.0)
        self.assertEqual(w.drops, 1)
        self.assertFalse(w.hover)
        self.assertEqual(w.opened, [])

    def test_offset_beyond_threshold_is_not_a_click(self):
        w = FakeWindow(bubble=0)
        w._on_drag_end(NS(), 40.0, 0.0)
        self.assertFalse(w.hover)
        self.assertEqual(w.opened, [])

    def test_drag_end_outside_compact_does_nothing(self):
        # en páginas abiertas el clic es de sus botones, no de la isla
        w = FakeWindow(view="bt", bubble=None)
        w._on_drag_end(NS(), 0.0, 0.0)
        self.assertFalse(w.hover)

    def test_real_click_opens_the_page_of_any_bubble(self):
        # mismo comportamiento para todas las opciones con burbuja (pomodoro, grabación, descargas…)
        for page in ("home", "pomo", "bt", "record", "reminders", "github", "downloads", "presence", "timer"):
            with self.subTest(page=page):
                w = FakeWindow(bubble=1)
                w.bubbles = [{"page": "bt"}, {"page": page}]
                w._on_drag_end(NS(), 0.0, 0.0)
                self.assertTrue(w.hover)
                self.assertEqual(w.page, page)
                self.assertEqual(w.opened, [page])

    def test_click_on_more_bubble_opens_tasks_page(self):
        w = FakeWindow(bubble=2)
        w.bubbles = [{"page": "pomo"}, {"page": "bt"}, {"key": "more", "page": "tasks", "count": 2}]
        w._on_drag_end(NS(), 0.0, 0.0)
        self.assertEqual((w.hover, w.page, w.opened), (True, "tasks", ["tasks"]))

    def test_release_after_gesture_click_is_not_handled_twice(self):
        # donde el button-release sí llega (p. ej. X11), no debe repetir la acción
        w = FakeWindow(bubble=0)
        w._on_drag_end(NS(), 0.0, 0.0)
        self.assertTrue(w._bubble_clicked(0, NS(button=1)))
        self.assertTrue(w._on_click(NS(), NS(button=1)))
        self.assertEqual(w.opened, ["bt"])


if __name__ == "__main__":
    unittest.main()
