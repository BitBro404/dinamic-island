"""Avisos: traduce los eventos de los servicios en lo que muestra la píldora (principio de responsabilidad única).

Cada servicio avisa con un callback (`deploy("start", d)`, `battery("low", 12)`…) y `EventRouter` decide
el texto, el icono, el color y la acción. No conoce GTK: solo llama a `core.show_event(**aviso)`, por eso se
prueba con un núcleo falso (tests/unit/test_events.py).
"""
import os
import time

from gi.repository import Gio

from .services.downloads import fmt_size
from .services.fx import cop
from .services.pomodoro import Pomodoro
from .util.fmt import bat_icon, hm
from .util.links import GITHUB_APP
from .util.proc import open_uri, play_sound
from .util.safety import open_web, safe_to_open


class EventRouter:
    """Traduce cada evento de un servicio (batería, despliegue, CI…) en un aviso de la píldora (una sola responsabilidad)."""
    def __init__(self, core, play=None):
        self.core = core
        self.show = core.show_event
        self.play = play or play_sound
        self._rain_warned = None      # última lluvia avisada («AAAA-MM-DD HH:MM»): no repetir

    def volume(self, v, muted):
        self.show(1.8, kind="volume", value=v, muted=muted)

    def battery(self, kind, pct):
        if kind == "low":
            self.play("dialog-warning.oga", "bell.oga")
            self.show(12.0, kind="card", icon="battery-caution-symbolic", app="Batería",
                      title=f"Batería baja · {pct:.0f} %",
                      body="Conecta el cargador para no perder tu trabajo.", action=None)
            return
        if kind == "full":
            self.play("complete.oga")
            target = self.core.charge_target()
            if target < 100:
                title = f"Batería al {target} % · tope de cuidado"
                body = (f"Se detuvo la carga en {target} % para cuidar la batería. "
                        "Si necesitas el 100 %, apaga «Cuidar batería».")
            else:
                title = "Carga completa · 100 %"
                body = "Ya puedes desconectar el cargador."
            self.show(10.0, kind="card", icon="battery-full-charged-symbolic", app="Batería",
                      title=title, body=body, action=None)
            return
        txt, acc, ic = {
            "charging": ("Cargando", "green", bat_icon(pct, True)),
            "unplugged": ("Con batería", None, bat_icon(pct, False)),
            "low": ("Batería baja", "red", "battery-caution-symbolic"),
        }[kind]
        right = f"{pct:.0f}%"
        if kind == "charging" and self.core.charge_limit.enabled:
            right += f" · hasta {self.core.charge_limit.end}%"
        self.show(4.5, kind="pill", icon=ic, accent=acc, text=txt, right=right, right_accent=acc)

    def weather(self):
        w = getattr(self.core, "weather", None)    # el primer aviso llega antes de que exista core.weather
        d = w and w.data
        soon = d and d.get("soon")
        if soon:
            key = time.strftime("%Y-%m-%d ") + soon["hour"]
            if key != self._rain_warned:
                self._rain_warned = key
                storm = soon["kind"] == "storm"
                self.show(4.0, kind="pill",
                          icon="weather-storm-symbolic" if storm else "weather-showers-symbolic",
                          accent="blue", text=f"{'Tormenta' if storm else 'Lluvia'} hacia las {soon['hour']}",
                          right=f"{soon['pop']}%", right_accent="blue")

    def privacy(self, kind, apps):
        who = ", ".join(apps)
        if kind == "cam":
            self.show(3.5, kind="pill", icon="camera-web-symbolic", accent="green",
                      text=f"{who} está usando la cámara")
        else:
            self.show(3.5, kind="pill", icon="audio-input-microphone-symbolic", accent="orange",
                      text=f"{who} está usando el micrófono")

    def git(self, kind, s):
        n = s["behind"]
        self.show(5.0, kind="pill", icon="emblem-synchronizing-symbolic", accent="blue",
                  text=f"{s['name']}: {n} commit{'s' if n != 1 else ''} nuevo{'s' if n != 1 else ''} en {s['upstream']}")

    def reminder(self, r, late=False):
        if not self.core.feature("reminders"):
            return
        self.play("alarm-clock-elapsed.oga", "complete.oga")
        hm_ = hm(r["at"])
        self.show(20.0, kind="card", icon="alarm-symbolic",
                  app=f"Recordatorio · pendiente desde las {hm_}" if late else f"Recordatorio · {hm_}",
                  title=r["text"], body="Clic para posponer 10 min",
                  action=lambda: (self.core.reminders.snooze(r, 10),
                                  self.show(2.0, kind="pill", icon="alarm-symbolic", accent="blue",
                                                  text="Pospuesto 10 min")))

    def fx_day(self):
        ch = self.core.fx.change()
        right = None if ch is None else f"{'▲' if ch > 0 else '▼'} {abs(ch):.1f}%".replace(".", ",")
        self.show(5.0, kind="pill", icon="money-symbolic", text=f"TRM hoy {cop(self.core.fx.trm)}",
                  right=right, right_accent=None if ch is None else "red" if ch > 0 else "green")

    def download(self, kind, d):
        if kind == "done":
            path = d["path"]
            # lo ejecutable o desconocido no se abre con un clic: se abre su carpeta (S6)
            target = path if safe_to_open(d["name"]) else os.path.dirname(path)
            self.show(7.0, kind="card", icon="folder-download-symbolic", app="Descarga terminada",
                      title=d["name"], body=f"{fmt_size(d['size'])} · clic para "
                                            f"{'abrir' if target == path else 'ver en la carpeta'}",
                      action=lambda: open_uri(Gio.File.new_for_path(target).get_uri()))
        elif kind == "cancelled":
            self.show(3.0, kind="pill", icon="folder-download-symbolic", text=f"Descarga cancelada · {d['name']}")

    def net(self, kind, name):
        if kind == "vpn_on":
            self.show(3.0, kind="pill", icon="network-vpn-symbolic", accent="blue", text=f"VPN conectada · {name}")
        elif kind == "vpn_off":
            self.show(4.0, kind="pill", icon="network-vpn-symbolic", accent="orange",
                      text=f"VPN desconectada · {name}")
        elif kind == "offline":
            self.show(6.0, kind="pill", icon="network-offline-symbolic", accent="red", text="Sin Internet")
        else:
            self.show(3.0, kind="pill", icon="network-transmit-receive-symbolic", accent="green",
                      text="Internet de vuelta")

    def sysmon(self, kind, name, value):
        if kind == "cpu":
            self.show(6.0, kind="pill", icon="utilities-system-monitor-symbolic", accent="orange",
                      text=f"{name} usa mucha CPU", right=f"{value:.0f}%", right_accent="orange")
        elif kind == "ram":
            self.show(6.0, kind="pill", icon="dialog-warning-symbolic", accent="red",
                      text="Queda poca memoria" + (f" · {name}" if name else ""),
                      right=f"{value:.0f}% libre", right_accent="red")
        else:
            self.show(6.0, kind="pill", icon="dialog-warning-symbolic", accent="red",
                      text="La CPU está muy caliente", right=f"{value:.0f}°", right_accent="red")

    def server(self, kind, s):
        where = f"{s['name']} · :{s['port']}"
        if kind == "up":
            self.show(3.0, kind="pill", icon="network-server-symbolic", accent="green", text=f"Listo · {where}")
        elif kind == "stopped":
            self.show(2.5, kind="pill", icon="process-stop-symbolic", text=f"Detenido · {where}")
        else:
            self.show(6.0, kind="pill", icon="dialog-error-symbolic", accent="red", text=f"Se cayó · {where}")

    def deploy(self, kind, d):
        where = f"{d['name']} · {d['env']}"
        if kind == "start":
            self.show(3.0, kind="pill", icon="emblem-synchronizing-symbolic", accent="orange",
                      text=f"Desplegando {where}")
        elif d["state"] == "SUCCESS":
            self.show(5.0, kind="pill", icon="emblem-ok-symbolic", accent="green", text=f"Desplegado · {where}")
        else:
            self.show(12.0, kind="card", icon="dialog-error-symbolic", app="Despliegue fallido",
                      title=where, body=d["commit"] or d["repo"], action=lambda: open_web(d["url"]))

    def github(self, kind, p):
        ref = f"{p['repo']}#{p['num']}"
        if kind == "review":
            self.show(9.0, kind="card", icon=GITHUB_APP, app="GitHub · Revisión pedida",
                      title=p["title"], body=f"{ref} · {p['author']}",
                      action=lambda: self.core.open_github(p["url"]))
        elif kind == "ci":
            good = p["ci"] == "SUCCESS"
            self.show(4.0, kind="pill", icon="emblem-ok-symbolic" if good else "dialog-error-symbolic",
                      accent="green" if good else "red", text=f"CI {'pasó' if good else 'falló'} · {ref}")
        elif kind == "decision":
            good = p["review"] == "APPROVED"
            self.show(4.0, kind="pill", icon="emblem-ok-symbolic" if good else "document-edit-symbolic",
                      accent="green" if good else "orange",
                      text=f"{'Aprobada' if good else 'Piden cambios'} · {ref}")

    def bt_connect(self, name, connected, ic):
        self.show(4.0, kind="pill", icon=ic, accent="blue" if connected else None,
                  text=name, right="Conectado" if connected else "Desconectado",
                  right_accent="blue" if connected else None)

    def drive(self, kind, name, vol):
        if kind == "usb":
            self.show(7.0, kind="card", icon="media-removable-symbolic", app="Medio extraíble",
                      title=name, body="Haz clic para abrirlo", action=lambda: self.core.drives.open(vol))
        elif kind == "ejected":
            self.show(3.0, kind="pill", icon="media-eject-symbolic", accent="green",
                      text=f"Ya puedes retirar {name}")
        else:
            self.show(3.5, kind="pill", icon="dialog-warning-symbolic", accent="red", text=name)

    def pomo_end(self, prev, nxt):
        self.play("complete.oga", "alarm-clock-elapsed.oga")
        mins = self.core.pomo.conf[nxt]
        title = "¡Buen trabajo! Toca descansar" if prev == "work" else "¡Fin del descanso! A enfocarse"
        auto = self.core.pomo.running
        body = f"Siguiente: {Pomodoro.LABEL[nxt].lower()} de {mins} min" + \
            ("" if auto else " · haz clic para empezar")
        self.show(10.0, kind="card", icon="timer-symbolic", app="Pomodoro", title=title, body=body,
                  action=None if auto else self.core.pomo.start)
