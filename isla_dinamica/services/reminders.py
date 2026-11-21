"""Recordatorios: «llamar a Ana en 20 min», «daily a las 9:30», «mañana a las 8 pagar luz»."""
import re

import json
import os
import time

from gi.repository import GLib

from ..util.fmt import DIAS, hm

REMINDERS_PATH = os.path.join(GLib.get_user_config_dir(), "isla-dinamica", "reminders.json")
DEFAULT_MIN = 30

_UNITS = {"s": 1, "seg": 1, "segundo": 1, "segundos": 1,
          "m": 60, "min": 60, "mins": 60, "minuto": 60, "minutos": 60,
          "h": 3600, "hr": 3600, "hrs": 3600, "hora": 3600, "horas": 3600}
_IN = re.compile(r"\b(?:en|dentro de)\s+(\d+(?:[.,]\d+)?|una?|media)\s*(" + "|".join(
    sorted(_UNITS, key=len, reverse=True)) + r")\b\.?", re.I)
_HALF = re.compile(r"\b(?:en|dentro de)\s+media\s+hora\b", re.I)
_AT = re.compile(r"\b(?:a\s+las?|a\s+la|@)\s*(\d{1,2})(?:[:.h](\d{2}))?\s*(am|pm|a\.\s?m\.|p\.\s?m\.)?", re.I)
_TOMORROW = re.compile(r"\bmañana\b", re.I)


def parse(text, now=None):
    """Devuelve (texto limpio, epoch o None) a partir de una frase en español."""
    now = now or time.time()
    t, at = text.strip(), None
    m = _HALF.search(t)
    if m:
        at = now + 1800
        t = t[:m.start()] + t[m.end():]
    m = None if at else _IN.search(t)
    if m:
        n = m.group(1).lower()
        n = 1.0 if n in ("un", "una") else 0.5 if n == "media" else float(n.replace(",", "."))
        at = now + n * _UNITS[m.group(2).lower()]
        t = t[:m.start()] + t[m.end():]
    tomorrow = _TOMORROW.search(t)
    m = None if at else _AT.search(t)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower().replace(".", "").replace(" ", "")
        if ampm == "pm" and hh < 12:
            hh += 12
        elif ampm == "am" and hh == 12:
            hh = 0
        if hh < 24 and mm < 60:
            lt = time.localtime(now)
            base = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))
            if tomorrow:
                base = _plus_days(base, 1)
            elif base <= now:
                # «a las 3» dicho después de las 3 a. m. → 15:00; otras horas ya pasadas → mañana
                if not ampm and 1 <= hh <= 6 and base + 12 * 3600 > now:
                    base += 12 * 3600
                else:
                    base = _plus_days(base, 1)
            at = base
            t = t[:m.start()] + t[m.end():]
    if tomorrow:
        if at is None:
            lt = time.localtime(now)
            at = _plus_days(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 9, 0, 0, 0, 0, -1)), 1)
        t = _TOMORROW.sub("", t, count=1)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.-·")
    return t, at


def _plus_days(ts, n):
    lt = time.localtime(ts)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + n, lt.tm_hour, lt.tm_min, 0, 0, 0, -1))


def when(ts):
    """«en 12 min · 15:30», «mañana 09:00», «lun 24 · 09:00»."""
    d = ts - time.time()
    hm_ = hm(ts)
    if d < 60:
        return f"ahora · {hm_}"
    if d < 3600:
        return f"en {int(d // 60) + (1 if d % 60 else 0)} min · {hm_}"
    today = time.localtime()
    lt = time.localtime(ts)
    days = (time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) -
            time.mktime((today.tm_year, today.tm_mon, today.tm_mday, 0, 0, 0, 0, 0, -1))) / 86400
    if round(days) == 0:
        h, m = int(d // 3600), int(d % 3600 // 60)
        return f"en {h} h {m:02d} min · {hm_}" if m else f"en {h} h · {hm_}"
    if round(days) == 1:
        return f"mañana · {hm_}"
    return f"{DIAS[lt.tm_wday][:3]} {lt.tm_mday} · {hm_}"


class Reminders:
    """Recordatorios guardados en disco que disparan un aviso a su hora."""
    def __init__(self, on_change, on_due):
        self.on_change, self.on_due = on_change, on_due
        self.items = []                 # [{id, text, at}] ordenados por hora
        try:
            with open(REMINDERS_PATH, encoding="utf-8") as f:
                self.items = [r for r in json.load(f) if r.get("text") and r.get("at")]
        except (OSError, ValueError):
            pass
        self.items.sort(key=lambda r: r["at"])
        self.missed = [r for r in self.items if r["at"] < time.time() - 60]

    def _save(self):
        os.makedirs(os.path.dirname(REMINDERS_PATH), exist_ok=True)
        tmp = REMINDERS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, REMINDERS_PATH)
        self.on_change()

    def add(self, text, at=None):
        """Agrega desde una frase; at fuerza la hora. Devuelve el recordatorio o None."""
        clean, parsed = parse(text)
        at = at or parsed or time.time() + DEFAULT_MIN * 60
        clean = clean or text.strip()
        if not clean:
            return None
        r = {"id": f"{time.time():.6f}", "text": clean[:200], "at": float(at)}
        self.items.append(r)
        self.items.sort(key=lambda x: x["at"])
        self._save()
        return r

    def remove(self, rid):
        self.items = [r for r in self.items if r["id"] != rid]
        self._save()

    def snooze(self, r, mins=10):
        self.add(r["text"], time.time() + mins * 60)

    def next(self):
        return self.items[0] if self.items else None

    def tick(self):
        now = time.time()
        due = [r for r in self.items if r["at"] <= now]
        if not due:
            return
        self.items = [r for r in self.items if r["at"] > now]
        self._save()
        for r in due:
            self.on_due(r, late=now - r["at"] > 90)
