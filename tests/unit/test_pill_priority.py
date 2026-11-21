"""Qué muestra la píldora: una sola cosa, la primera activa en el orden de prioridad (caracterización)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.ui.pill import PILL_ORDER, PillState, pick_pill  # noqa: E402

ALL_ON = PillState(alert=True, card_hold=True, hover=True, presence_warning=True, event=True,
                   activities={"call", "reminder", "deploy", "download", "audio"}, playing=True,
                   pomodoro=True, recording=True, timer=True)


class PillPriorityTest(unittest.TestCase):
    def test_full_order(self):
        """Quitando cada vez lo que gana, sale el orden completo documentado."""
        expected = ["alert", "card_hold", "expanded", "presence", "event", "call", "media", "pomodoro",
                    "recording", "reminder", "deploy", "download", "audio", "timer", "idle"]
        self.assertEqual([k for k, _ in PILL_ORDER], expected)
        off = {"alert": dict(alert=False), "card_hold": dict(card_hold=False), "expanded": dict(hover=False),
               "presence": dict(presence_warning=False), "event": dict(event=False), "media": dict(playing=False),
               "pomodoro": dict(pomodoro=False), "recording": dict(recording=False), "timer": dict(timer=False)}
        st, seen = ALL_ON, []
        while True:
            k = pick_pill(st)
            seen.append(k)
            if k == "idle":
                break
            if k in off:
                st = st._replace(**off[k])
            else:
                st = st._replace(activities=st.activities - {k})
        self.assertEqual(seen, expected)

    def test_nothing_active_is_idle(self):
        self.assertEqual(pick_pill(PillState()), "idle")

    def test_call_beats_music(self):
        self.assertEqual(pick_pill(PillState(playing=True, activities={"call"})), "call")

    def test_presence_countdown_beats_events(self):
        self.assertEqual(pick_pill(PillState(event=True, presence_warning=True, playing=True)), "presence")

    def test_hover_beats_everything_but_alerts_and_held_cards(self):
        self.assertEqual(pick_pill(PillState(hover=True, presence_warning=True)), "expanded")
        self.assertEqual(pick_pill(PillState(hover=True, card_hold=True)), "card_hold")


if __name__ == "__main__":
    unittest.main()
