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


def _battery_pct(value):
    """Porcentaje de batería válido (0–100), o None si el dispositivo no lo reporta."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        return None
    return value


def bluetooth_activity(devices):
    """Burbuja del primer dispositivo Bluetooth conectado (por nombre), o None si no hay ninguno."""
    connected = [d for d in (devices or {}).values() if d and d.get("connected")]
    if not connected:
        return None
    d = sorted(connected, key=lambda x: str(x.get("name") or "").lower())[0]
    name = d.get("name") or "Dispositivo"
    pct = _battery_pct(d.get("battery"))
    tip = f"{name} · {pct:.0f}%" if pct is not None else name
    return {"key": "bt", "icon": d.get("icon") or "bluetooth-active-symbolic", "accent": "blue",
            "page": "bt", "progress": pct / 100 if pct is not None else None, "tip": tip}


def bubble_rects(n, w, h, vertical, size=H, gap=BUB_GAP):
    """(x, y) de la esquina de cada una de las `n` burbujas, alineadas al final de una ventana de w×h:
    a la derecha de la píldora en horizontal y debajo en vertical."""
    ext = n * (size + gap)
    out = []
    for i in range(n):
        off = ext - gap - i * (size + gap)
        out.append((w / 2 - size / 2, h - off) if vertical else (w - off, h / 2 - size / 2))
    return out


MORE_KEY = "more"


def bubble_slots(acts, shown, limit, more):
    """Burbujas que se ven: las actividades que no están en la píldora (`shown`), como mucho `limit`, y si
    sobran y `more` está activo, una extra «+N» que abre la página «Tareas en curso»."""
    rest = [a for a in acts if a["key"] not in shown]
    slots = rest[:limit]
    hidden = len(rest) - len(slots)
    if more and hidden > 0:
        slots.append({"key": MORE_KEY, "label": "Tareas en curso", "icon": None, "accent": None,
                      "page": "tasks", "count": hidden, "tip": f"{hidden} más"})
    return slots


def bubble_tip(act):
    """Texto del tooltip: «Opción · estado»; Bluetooth ya trae «dispositivo · batería» y no lleva prefijo."""
    label, tip = act.get("label"), act.get("tip") or ""
    return f"{label} · {tip}" if label and tip else label or tip


def activities(c, m, playing, timer_left, now=None, wall=None):
    """Actividades en curso, de más a menos importante: llamada, música, pomodoro, Bluetooth y el resto.
    Cada una es un dict {key, label, icon, accent, page, tip, [art], [progress]}. La primera que gana la
    píldora (ui.pill) se ve allí; las demás, como burbujas al lado. `now`/`wall` (monotónico/epoch) se inyectan
    en las pruebas."""
    now = time.monotonic() if now is None else now
    wall = time.time() if wall is None else wall
    acts = []
    au = c.audio if c.feature("audio") else None
    if au and au.call:
        acts.append({"key": "call", "label": "Llamada", "icon": "call-start-symbolic", "accent": "green",
                     "page": "home", "tip": f"{au.call} · {fmt_secs(now - au.call_since)}"})
    if playing:
        acts.append({"key": "media", "label": "Música", "icon": "audio-x-generic-symbolic", "accent": "green",
                     "page": "home", "art": c.art,
                     "tip": f"{m['title']} · {m.get('artist') or ''}".rstrip(" ·")})
    p = c.pomo
    if p.active:
        acts.append({"key": "pomo", "label": "Pomodoro", "icon": "timer-symbolic",
                     "accent": "red" if p.phase == "work" else "green",
                     "page": "pomo", "progress": 1 - p.left() / p.length(p.phase),
                     "tip": f"{Pomodoro.LABEL[p.phase]} · {fmt_secs(p.left())}"})
    if c.feature("bt_bubble") and getattr(c, "bt", None):
        bt = bluetooth_activity(c.bt.devices)
        if bt:
            acts.append(bt)
    if c.recorder.active:
        acts.append({"key": "rec", "label": "Grabación", "icon": "media-record-symbolic", "accent": "red",
                     "page": "record", "tip": fmt_secs(c.recorder.elapsed())})
    r = c.reminders.next() if c.feature("reminders") else None
    if r and r["at"] - wall < 300:
        acts.append({"key": "reminder", "label": "Recordatorio", "icon": "alarm-symbolic", "accent": "blue",
                     "page": "reminders", "tip": r["text"]})
    if c.feature("deploys") and c.deploys.active():
        d = c.deploys.active()[0]
        acts.append({"key": "deploy", "label": "Despliegues", "icon": "emblem-synchronizing-symbolic",
                     "accent": "orange", "page": "github", "tip": f"{d['name']} · {d['env']}"})
    if c.feature("downloads") and c.downloads.active:
        acts.append({"key": "download", "label": "Descargas", "icon": "folder-download-symbolic", "accent": "blue",
                     "page": "downloads", "tip": c.downloads.main()["name"]})
    if au and not playing and not au.call and au.audible and au.outputs:
        acts.append({"key": "audio", "label": "Audio", "icon": "audio-speakers-symbolic", "accent": "green",
                     "page": "home", "tip": ", ".join(au.outputs)})
    pr = c.presence
    if c.feature("presence") and pr.state in ("watching", "present"):
        acts.append({"key": "presence", "label": "Presencia", "icon": "view-reveal-symbolic",
                     "accent": "green" if pr.state == "present" else "blue", "page": "presence",
                     "tip": "te ve" if pr.state == "present" else "mirando si hay alguien"})
    if timer_left is not None:
        acts.append({"key": "timer", "label": "Temporizador", "icon": "alarm-symbolic", "accent": "orange",
                     "page": "timer", "progress": 1 - timer_left / max(1, c.timer_total),
                     "tip": fmt_secs(timer_left)})
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
        for i, (st, img, art, count) in enumerate(self.bub_widgets):
            if i < len(acts):
                a = acts[i]
                if a.get("count"):
                    count.set_text(f"+{a['count']}")
                    st.set_visible_child_name("count")
                elif a.get("art") is not None:
                    art.set_pixbuf(a["art"])
                    st.set_visible_child_name("art")
                else:
                    img.set_from_icon_name(icon_name(a["icon"]), Gtk.IconSize.MENU)
                    set_accent(img, a.get("accent"))
                    st.set_visible_child_name("icon")
                st.set_tooltip_text(bubble_tip(a))
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
