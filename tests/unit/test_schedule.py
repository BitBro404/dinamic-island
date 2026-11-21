"""Horario del sensor de presencia según la hora local."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.presence import in_schedule  # noqa: E402

WEEK = (0, 1, 2, 3, 4)
# 2026-11-20 es viernes, 2026-11-21 sábado, 2026-11-16 lunes, 2026-11-17 martes
FRI, SAT, MON, TUE, THU = 20, 21, 16, 17, 19


def at(day, h, m=0):
    return datetime(2026, 11, day, h, m)


class ScheduleTest(unittest.TestCase):
    def test_inside(self):
        self.assertTrue(in_schedule(at(FRI, 17, 59), "08:00", "18:00", WEEK))
        self.assertTrue(in_schedule(at(MON, 8, 0), "08:00", "18:00", WEEK))

    def test_end_exclusive(self):
        self.assertFalse(in_schedule(at(FRI, 18, 0), "08:00", "18:00", WEEK))

    def test_before_start(self):
        self.assertFalse(in_schedule(at(MON, 7, 59), "08:00", "18:00", WEEK))

    def test_weekend(self):
        self.assertFalse(in_schedule(at(SAT, 10, 0), "08:00", "18:00", WEEK))

    def test_overnight_belongs_to_start_day(self):
        self.assertTrue(in_schedule(at(FRI, 23, 0), "22:00", "02:00", (4,)))
        self.assertTrue(in_schedule(at(SAT, 1, 0), "22:00", "02:00", (4,)))
        self.assertFalse(in_schedule(at(FRI, 1, 0), "22:00", "02:00", (4,)))
        self.assertFalse(in_schedule(at(SAT, 2, 0), "22:00", "02:00", (4,)))
        self.assertTrue(in_schedule(at(FRI, 1, 0), "22:00", "02:00", (3,)))

    def test_same_start_end_is_all_day(self):
        self.assertTrue(in_schedule(at(TUE, 3, 0), "00:00", "00:00", WEEK))
        self.assertFalse(in_schedule(at(SAT, 3, 0), "00:00", "00:00", WEEK))

    def test_no_days(self):
        self.assertFalse(in_schedule(at(MON, 10, 0), "08:00", "18:00", ()))


if __name__ == "__main__":
    unittest.main()
