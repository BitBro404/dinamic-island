"""Burbujas de actividades: lo que está en curso y no cabe en la píldora se ve como círculos a su lado.

`activities` decide qué hay en curso (lógica pura sobre el núcleo) y `bubble_rects` dónde se dibuja cada
burbuja. El dibujo con Cairo y los widgets viven en la ventana.
"""
import time

import math

from gi.repository import Gtk

from ..util.fmt import fmt_secs
from .gtk import icon_name, set_accent
from .style import BUB_GAP, H
from ..services.pomodoro import Pomodoro


def bubble_rects(n, w, h, vertical, size=H, gap=BUB_GAP):
    """(x, y) de la esquina de cada una de las `n` burbujas, alineadas al final de una ventana de w×h:
    a la derecha de la píldora en horizontal y debajo en vertical."""
    ext = n * (size + gap)
    out = []
    for i in range(n):
        off = ext - gap - i * (size + gap)
        out.append((w / 2 - size / 2, h - off) if vertical else (w - off, h / 2 - size / 2))
    return out


def activities(c, m, playing, timer_left, now=None, wall=None):
    """Actividades en curso, de más a menos importante: llamada, música, pomodoro y el resto.
    Cada una es un dict {key, icon, accent, page, tip, [art], [progress]}. La primera que gana la píldora
    (ui.pill) se ve allí; las demás, como burbujas al lado. `now`/`wall` (monotónico/epoch) se inyectan
    en las pruebas."""
    now = time.monotonic() if now is None else now
    wall = time.time() if wall is None else wall
    acts = []
    au = c.audio if c.feature("audio") else None
    if au and au.call:
        acts.append({"key": "call", "icon": "call-start-symbolic", "accent": "green", "page": "home",
                     "tip": f"En llamada · {au.call} · {fmt_secs(now - au.call_since)}"})
    if playing:
        acts.append({"key": "media", "icon": "audio-x-generic-symbolic", "accent": "green", "page": "home",
                     "art": c.art, "tip": f"{m['title']} · {m.get('artist') or ''}".rstrip(" ·")})
    p = c.pomo
    if p.active:
        acts.append({"key": "pomo", "icon": "timer-symbolic", "accent": "red" if p.phase == "work" else "green",
                     "page": "pomo", "progress": 1 - p.left() / p.length(p.phase),
                     "tip": f"{Pomodoro.LABEL[p.phase]} · {fmt_secs(p.left())}"})
    if c.recorder.active:
        acts.append({"key": "rec", "icon": "media-record-symbolic", "accent": "red", "page": "record",
                     "tip": f"Grabando · {fmt_secs(c.recorder.elapsed())}"})
    r = c.reminders.next() if c.feature("reminders") else None
    if r and r["at"] - wall < 300:
        acts.append({"key": "reminder", "icon": "alarm-symbolic", "accent": "blue", "page": "reminders",
                     "tip": r["text"]})
    if c.feature("deploys") and c.deploys.active():
        d = c.deploys.active()[0]
        acts.append({"key": "deploy", "icon": "emblem-synchronizing-symbolic", "accent": "orange",
                     "page": "github", "tip": f"Desplegando {d['name']} · {d['env']}"})
    if c.feature("downloads") and c.downloads.active:
        acts.append({"key": "download", "icon": "folder-download-symbolic", "accent": "blue",
                     "page": "downloads", "tip": f"Descargando {c.downloads.main()['name']}"})
    if au and not playing and not au.call and au.audible and au.outputs:
        acts.append({"key": "audio", "icon": "audio-speakers-symbolic", "accent": "green", "page": "home",
                     "tip": "Sonando: " + ", ".join(au.outputs)})
    pr = c.presence
    if c.feature("presence") and pr.state in ("watching", "present"):
        acts.append({"key": "presence", "icon": "view-reveal-symbolic",
                     "accent": "green" if pr.state == "present" else "blue", "page": "presence",
                     "tip": "Presencia · " + ("te ve" if pr.state == "present" else "mirando si hay alguien")})
    if timer_left is not None:
        acts.append({"key": "timer", "icon": "alarm-symbolic", "accent": "orange", "page": "timer",
                     "progress": 1 - timer_left / max(1, c.timer_total),
                     "tip": f"Temporizador · {fmt_secs(timer_left)}"})
    return acts


class BubblesMixin:
    """Widgets y dibujo de las burbujas de actividades al lado de la píldora (los usa IslandWindow)."""
    # color del anillo de progreso según el acento de la actividad
    RING = {"orange": (1.0, 0.62, 0.04), "green": (0.19, 0.82, 0.35), "red": (1.0, 0.27, 0.23),
            "blue": (0.04, 0.52, 1.0), None: (1.0, 1.0, 1.0)}

    def _bubble_rects(self, w, h):
        """(x, y) de la esquina de cada burbuja, alineadas al final de la ventana."""
        return bubble_rects(len(self.bubbles), w, h, self.vertical)

    def _draw_bubbles(self, cr, w, h):
        for (x, y), act in zip(self._bubble_rects(w, h), self.bubbles):
            cx, cy, r = x + H / 2, y + H / 2, H / 2
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.set_source_rgb(0, 0, 0)
            cr.fill_preserve()
            cr.set_source_rgba(1, 1, 1, 0.07)
            cr.set_line_width(1)
            cr.stroke()
            prog = act.get("progress")
            if prog is not None:
                cr.set_line_width(2.5)
                cr.set_source_rgba(1, 1, 1, 0.12)
                cr.arc(cx, cy, r - 3, 0, 2 * math.pi)
                cr.stroke()
                cr.set_source_rgb(*self.RING.get(act.get("accent"), self.RING[None]))
                cr.arc(cx, cy, r - 3, -math.pi / 2, -math.pi / 2 + 2 * math.pi * min(1.0, max(0.0, prog)))
                cr.stroke()

    def _set_bubbles(self, acts):
        self.bubbles = acts
        for i, (st, img, art) in enumerate(self.bub_widgets):
            if i < len(acts):
                a = acts[i]
                if a.get("art") is not None:
                    art.set_pixbuf(a["art"])
                    st.set_visible_child_name("art")
                else:
                    img.set_from_icon_name(icon_name(a["icon"]), Gtk.IconSize.MENU)
                    set_accent(img, a.get("accent"))
                    st.set_visible_child_name("icon")
                st.set_tooltip_text(a.get("tip"))
                st.show()
            else:
                st.hide()
        self.bub_box.set_visible(bool(acts))
        if self.vertical:
            self.bub_box.set_margin_top(BUB_GAP if acts else 0)
            self.bub_box.set_margin_start(0)
        else:
            self.bub_box.set_margin_start(BUB_GAP if acts else 0)
            self.bub_box.set_margin_top(0)
        self._bub_ext = len(acts) * (H + BUB_GAP)
        self.queue_draw()

    def _bubble_at(self):
        """Índice de la burbuja bajo el ratón, o None (sobre la píldora)."""
        if not self.bubbles or self.view != "compact":
            return None
        try:
            x, y = self._pointer()
        except (AttributeError, TypeError):
            return None
        w, h = self.cur
        for i, (bx, by) in enumerate(self._bubble_rects(w, h)):
            if bx - BUB_GAP / 2 <= x <= bx + H + BUB_GAP / 2 and by - BUB_GAP / 2 <= y <= by + H + BUB_GAP / 2:
                return i
        return None
