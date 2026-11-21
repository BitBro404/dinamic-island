"""Acople a los bordes: geometría pura de dónde va la isla (sin GTK)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.ui.dock import dock_xy, drop_position, layer_layout, nearest_edge  # noqa: E402

MW, MH, GAP = 1920, 1080, 6


class DockGeometryTest(unittest.TestCase):
    def test_nearest_edge(self):
        self.assertEqual(nearest_edge(960, 10, MW, MH), "top")
        self.assertEqual(nearest_edge(960, 1070, MW, MH), "bottom")
        self.assertEqual(nearest_edge(5, 540, MW, MH), "left")
        self.assertEqual(nearest_edge(1915, 540, MW, MH), "right")

    def test_top_center(self):
        self.assertEqual(dock_xy("top", 0.5, 200, 34, MW, MH, GAP), (860.0, 6.0))

    def test_bottom_and_sides(self):
        self.assertEqual(dock_xy("bottom", 0.5, 200, 34, MW, MH, GAP), (860.0, MH - 34 - GAP))
        self.assertEqual(dock_xy("left", 0.5, 34, 200, MW, MH, GAP), (6.0, 440.0))
        self.assertEqual(dock_xy("right", 0.5, 34, 200, MW, MH, GAP), (MW - 34 - GAP, 440.0))

    def test_never_leaves_the_screen(self):
        self.assertEqual(dock_xy("top", 0.0, 200, 34, MW, MH, GAP), (6, 6.0))
        self.assertEqual(dock_xy("top", 1.0, 200, 34, MW, MH, GAP), (MW - 200 - GAP, 6.0))

    def test_while_dragging_uses_the_pointer_center(self):
        self.assertEqual(dock_xy(None, None, 100, 34, MW, MH, GAP, center=(500, 300)), (450.0, 283.0))

    def test_drop_position(self):
        self.assertEqual(drop_position(480, 10, MW, MH), ("top", 0.25))
        self.assertEqual(drop_position(10, 270, MW, MH), ("left", 0.25))

    def test_layer_layout_grows_away_from_its_edge(self):
        self.assertEqual(layer_layout("top", 860, 6, 200, 34, MW, MH), (("top", "left"), {"top": 6, "left": 860}))
        self.assertEqual(layer_layout("bottom", 860, 1040, 200, 34, MW, MH),
                         (("bottom", "left"), {"bottom": 6, "left": 860}))
        self.assertEqual(layer_layout("right", 1880, 440, 34, 200, MW, MH),
                         (("top", "right"), {"top": 440, "right": 6}))
        self.assertEqual(layer_layout(None, 10, 20, 34, 200, MW, MH), (("top", "left"), {"top": 20, "left": 10}))


if __name__ == "__main__":
    unittest.main()
