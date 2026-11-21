"""Formato de fechas, horas, duraciones y textos para mostrar (funciones puras, en español)."""
import calendar
import html
import os
import re
import time


def today_count(stamps, now=None):
    """Cuántas marcas de tiempo (epoch) caen en el día de hoy (desde las 00:00 locales)."""
    t = time.localtime(now if now is not None else time.time())
    midnight = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
    return sum(1 for s in stamps if s and s >= midnight)


def fmt_secs(s):
    s = max(0, int(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def strip_markup(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def nm_split(line):
    parts = re.split(r"(?<!\\):", line)
    return [p.replace("\\:", ":").replace("\\\\", "\\") for p in parts]


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha():
    t = time.localtime()
    return f"{DIAS[t.tm_wday].capitalize()} {t.tm_mday} de {MESES[t.tm_mon - 1]}"


def bat_icon(pct, charging):
    lvl = "full" if pct > 85 else "good" if pct > 50 else "low" if pct > 20 else "caution"
    return f"battery-{lvl}{'-charging' if charging else ''}-symbolic"


CLOCK = {"h24": True}      # Core lo actualiza según la función «clock24» de la página «Más»


def hm(ts=None):
    """Hora corta según la preferencia: «15:58» o «3:58 pm»."""
    t = time.localtime(ts)
    if CLOCK["h24"]:
        return f"{t.tm_hour:02d}:{t.tm_min:02d}"
    return f"{t.tm_hour % 12 or 12}:{t.tm_min:02d} {'am' if t.tm_hour < 12 else 'pm'}"


def ago(ts):
    d = time.time() - ts
    if d < 60:
        return "ahora"
    if d < 3600:
        return f"hace {int(d // 60)} min"
    return hm(ts)


def ago_long(ts):
    """«hace 5 min», «hace 3 h», «ayer», «hace 4 días», «13 nov»."""
    d = time.time() - ts
    if d < 60:
        return "ahora"
    if d < 3600:
        return f"hace {int(d // 60)} min"
    if d < 86400:
        return f"hace {int(d // 3600)} h"
    days = int(d // 86400)
    if days == 1:
        return "ayer"
    if days < 7:
        return f"hace {days} días"
    meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    t = time.localtime(ts)
    return f"{t.tm_mday} {meses[t.tm_mon - 1]}"


def iso_ts(s):
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return time.time()


def tz_city():
    try:
        tz = os.path.realpath("/etc/localtime").split("zoneinfo/")[-1]
        return tz.split("/")[-1].replace("_", " ")
    except OSError:
        return "Bogota"
