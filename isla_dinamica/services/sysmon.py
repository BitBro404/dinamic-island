"""Monitor del sistema: CPU, RAM, temperatura y procesos que más consumen."""
from collections import deque

import os
import threading
import time

from gi.repository import GLib

HISTORY = 40               # muestras (cada 3 s → 2 minutos)
CPU_HOG, HOG_SECS = 90.0, 45     # % de un núcleo sostenido tantos segundos = «se come la CPU»
RAM_LOW, TEMP_HOT = 10.0, 90.0   # % de RAM disponible y °C para avisar
QUIET = 600                # no repetir el mismo aviso en 10 min


def _temp_path():
    base = "/sys/class/hwmon"
    try:
        for h in sorted(os.listdir(base)):
            with open(f"{base}/{h}/name") as f:
                if f.read().strip() in ("coretemp", "k10temp", "zenpower", "cpu_thermal"):
                    if os.path.exists(f"{base}/{h}/temp1_input"):
                        return f"{base}/{h}/temp1_input"
    except OSError:
        pass
    for z in range(20):
        try:
            with open(f"/sys/class/thermal/thermal_zone{z}/type") as f:
                if f.read().strip() in ("x86_pkg_temp", "TCPU", "acpitz"):
                    return f"/sys/class/thermal/thermal_zone{z}/temp"
        except OSError:
            break
    return None


def _cpu_times():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    idle = v[3] + (v[4] if len(v) > 4 else 0)
    return sum(v), idle


def _procs():
    """pid → (nombre, ticks de CPU, RAM en bytes) de los procesos del usuario."""
    out, page = {}, os.sysconf("SC_PAGE_SIZE")
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/stat") as f:
                raw = f.read()
            name = raw[raw.index("(") + 1:raw.rindex(")")]
            rest = raw[raw.rindex(")") + 2:].split()
            out[int(pid)] = (name, int(rest[11]) + int(rest[12]), int(rest[21]) * page)
        except (OSError, ValueError, IndexError):
            pass
    return out


class SysMon:
    """CPU, RAM y temperatura con historial; avisa de procesos que consumen demasiado."""
    def __init__(self, on_change, on_alert, enabled=lambda: True):
        self.on_change, self.on_alert, self.enabled = on_change, on_alert, enabled
        self.cpu = deque(maxlen=HISTORY)
        self.ram = deque(maxlen=HISTORY)
        self.temp = deque(maxlen=HISTORY)
        self.mem_total = self.mem_used = 0
        self.top = []                     # [(nombre, %cpu, bytes)]
        self.ncpu = os.cpu_count() or 1
        self._temp = _temp_path()
        self._hog_since, self._said = {}, {}
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        tick = os.sysconf("SC_CLK_TCK")
        prev_cpu, prev_p, prev_t = _cpu_times(), _procs(), time.monotonic()
        while True:
            time.sleep(3)
            if not self.enabled():
                prev_cpu, prev_p, prev_t = _cpu_times(), _procs(), time.monotonic()
                continue
            now_cpu, now_p, now_t = _cpu_times(), _procs(), time.monotonic()
            total, idle = now_cpu[0] - prev_cpu[0], now_cpu[1] - prev_cpu[1]
            cpu = 100.0 * (1 - idle / total) if total else 0.0
            dt = max(0.1, now_t - prev_t)
            by_name = {}
            for pid, (name, ticks, rss) in now_p.items():
                if pid in prev_p:
                    pct = 100.0 * (ticks - prev_p[pid][1]) / tick / dt
                    n = by_name.setdefault(name, [0.0, 0])
                    n[0] += pct
                    n[1] += rss
            top = sorted(((k, v[0], v[1]) for k, v in by_name.items()), key=lambda x: -x[1])[:6]
            mem = {}
            with open("/proc/meminfo") as f:
                for ln in f:
                    k, v = ln.split(":")
                    mem[k] = int(v.split()[0]) * 1024
            temp = None
            if self._temp:
                try:
                    with open(self._temp) as f:
                        temp = int(f.read()) / 1000
                except (OSError, ValueError):
                    pass
            GLib.idle_add(self._update, cpu, mem["MemTotal"], mem["MemTotal"] - mem["MemAvailable"], temp, top)
            prev_cpu, prev_p, prev_t = now_cpu, now_p, now_t

    def _update(self, cpu, total, used, temp, top):
        self.cpu.append(cpu)
        self.mem_total, self.mem_used = total, used
        self.ram.append(100.0 * used / total if total else 0)
        if temp is not None:
            self.temp.append(temp)
        self.top = top
        self._check(top, total, used, temp)
        self.on_change()
        return False

    def _say(self, key, *args):
        now = time.time()
        if now - self._said.get(key, 0) > QUIET:
            self._said[key] = now
            self.on_alert(*args)

    def _check(self, top, total, used, temp):
        now = time.time()
        hot = {name for name, pct, _ in top if pct >= CPU_HOG}
        for name in list(self._hog_since):
            if name not in hot:
                del self._hog_since[name]
        for name, pct, _ in top:
            if name in hot:
                since = self._hog_since.setdefault(name, now)
                if now - since >= HOG_SECS:
                    self._say(("cpu", name), "cpu", name, pct)
        if total and 100.0 * (total - used) / total < RAM_LOW:
            self._say("ram", "ram", top[0][0] if top else "", 100.0 * (total - used) / total)
        if temp is not None and temp >= TEMP_HOT:
            self._say("temp", "temp", "", temp)
