"""Estado compartido por las islas de todas las pantallas."""
import os
import time

from gi.repository import GLib, Gdk, GdkPixbuf, Gio

from .config import Config, FEATURE_DEFAULTS
from .platform.session import Session
from .services.audio import AudioWatch
from .services.clipboard import Clipboard
from .services.deploys import Deploys
from .services.downloads import Downloads
from .services.fx import Fx
from .services.github import GitHub
from .services.gitwatch import GitWatch
from .services.lockguard import LockGuard, watch_session_lock
from .services.media import Media, Volume
from .services.microsoft import clean_body, ms_kind
from .services.netmon import NetMon
from .services.network import Bluetooth, Radios, Wifi
from .services.notifications import Notifications
from .services.pomodoro import Pomodoro
from .services.power import Battery, ChargeLimit, Power
from .services.presence import Presence
from .services.privacy import Privacy
from .services.recorder import Recorder
from .services.reminders import Reminders
from .services.servers import Servers
from .services.sysmon import SysMon
from .services.system import Drives, Modes
from .services.weather import Weather
from .util.fmt import CLOCK, hm
from .util.links import GITHUB_APP, OUTLOOK_URL, TEAMS_APP
from .util.proc import dbg, launch_desktop, open_uri, play_sound
from .util.safety import desktop_matches_app, notif_debug_line, open_web
from .window import IslandWindow
from .events import EventRouter
from .capture import Capture


# ───────────────────────────── núcleo compartido ─────────────────────────────
class Core:
    """Estado y servicios compartidos por las islas de todas las pantallas."""

    def __init__(self, app, desktop=None, window_backend="layer-shell"):
        self.app = app
        self.desktop = desktop                 # platform.desktop.Desktop (familia y sesión)
        self.window_backend = window_backend   # cómo se colocan las ventanas (ui/placement.py)
        self.windows = {}
        self.ver = {}
        self.media = None
        self.event = None
        self.timer_end, self.timer_total, self.alert_until = None, 0, None
        self.notifs = []
        self.unread = 0
        self._art_url, self._art_cache, self.art = None, {}, None

        self.events = EventRouter(self)       # traduce los eventos de los servicios en avisos
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sysbus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.mpris = Media(bus)
        self.volume = Volume(self.events.volume)
        self.charge_limit = ChargeLimit(sysbus, lambda: self.changed("modes"))
        self.battery = Battery(self.events.battery, self.charge_target)
        self.notif = Notifications(bus, self._on_notify, lambda: self.changed("modes"))
        self.clip = Clipboard(lambda: self.changed("clip"), desktop=desktop)
        self.bt = Bluetooth(sysbus, lambda: self.changed("bt"), self.events.bt_connect)
        self.wifi = Wifi(sysbus, lambda: self.changed("wifi"))
        self.radios = Radios(lambda: self.changed("modes"))
        self.session = Session(bus, lambda: self.changed("modes"), desktop=desktop)
        self.modes = Modes(sysbus, bus, lambda: self.changed("modes"), desktop=desktop, session=self.session)
        self.drives = Drives(lambda: self.changed("usb"), self.events.drive)
        self.power = Power(sysbus, bus, desktop, session=self.session)
        self.config = Config()
        self.feature("clock24")
        self.weather = Weather(self.config, self._on_weather)
        self.pomo = Pomodoro(self.config, self.events.pomo_end, lambda: self.changed("pomo"))
        self.ms_unread = {"teams": 0, "outlook": 0}
        self.git = GitWatch(self.config, lambda: self.changed("git"), self.events.git, lambda: self.feature("git"))
        self.capture = Capture(self)
        self.recorder = Recorder(lambda: self.changed("rec"), self.capture.recording_done, desktop=desktop)
        self.reminders = Reminders(lambda: self.changed("reminders"), self.events.reminder)
        self._rm_minute = None
        self.fx = Fx(lambda: self.changed("fx"), self.events.fx_day, lambda: self.feature("fx"))
        self.audio = AudioWatch(lambda: self.changed("audio"), lambda: self.feature("audio"))
        self.privacy = Privacy(lambda: self.changed("privacy"), self.events.privacy, lambda: self.feature("privacy"))
        self.presence = Presence(self.config, lambda: self.changed("presence"), lambda: self.changed("presence"),
                                 lambda: self.feature("presence"),
                                 in_call=lambda: bool(self.feature("audio") and self.audio.call),
                                 desktop=desktop, bus=bus)
        self.downloads = Downloads(lambda: self.changed("downloads"), self.events.download,
                                   lambda: self.feature("downloads"))
        self.netmon = NetMon(lambda: self.changed("netmon"), self.events.net, lambda: self.feature("netmon"))
        self.sysmon = SysMon(lambda: self.changed("sysmon"), self.events.sysmon, lambda: self.feature("sysmon"))
        self.servers = Servers(lambda: self.changed("servers"), self.events.server, lambda: self.feature("servers"))
        self.deploys = Deploys(lambda: self.changed("deploys"), self.events.deploy, lambda: self.feature("deploys"))
        self.github = GitHub(lambda: self.changed("github"), self.events.github, lambda: self.feature("github"))

        # bienvenida al despertar / desbloquear
        sysbus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep",
                                "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, self._on_sleep)
        # sesión bloqueada → isla oculta y portapapeles vacío; al desbloquear vuelve con un saludo
        self.lock = LockGuard(self._set_visible, self.clip.clear)
        watch_session_lock(sysbus, self.lock, on_unlock=lambda: self.welcome(True))

        display = Gdk.Display.get_default()
        display.connect("monitor-added", lambda d, m: self._add_window(m))
        display.connect("monitor-removed", self._remove_window)
        for i in range(display.get_n_monitors()):
            self._add_window(display.get_monitor(i))

        self.tick()
        GLib.timeout_add(1000, self.tick)
        if os.environ.get("ISLA_NO_WELCOME") != "1":
            GLib.timeout_add(900, self.welcome)

    # ── ventanas por pantalla ──
    def _add_window(self, monitor):
        if monitor not in self.windows:
            self.windows[monitor] = IslandWindow(self, monitor)
            if self.lock.locked:                    # pantalla conectada con la sesión bloqueada
                self.windows[monitor].hide()

    def _remove_window(self, _d, monitor):
        w = self.windows.pop(monitor, None)
        if w:
            w.destroy()

    @property
    def dock(self):
        return self.config.data["dock"]

    def set_dock(self, edge, pos):
        self.config.data["dock"] = {"edge": edge, "pos": min(1.0, max(0.0, pos))}
        try:
            self.config.save()
        except OSError:
            pass
        for w in list(self.windows.values()):
            w.dock_changed()

    # ── funciones activables (página «Más») ──
    def feature(self, name):
        on = self.config.data["features"].get(name, FEATURE_DEFAULTS.get(name, True))
        if name == "clock24":
            CLOCK["h24"] = on
        return on

    def set_feature(self, name, on):
        self.config.data["features"][name] = bool(on)
        self.feature(name)
        try:
            self.config.save()
        except OSError:
            pass
        if on and name == "weather":
            self.weather.refresh()
        elif on and name == "github":
            self.github.refresh()
        elif on and name == "deploys":
            self.deploys.refresh()
        elif on and name in ("git", "fx"):
            getattr(self, name).refresh()
        self.changed("features")

    def changed(self, kind=None):
        if kind:
            self.ver[kind] = self.ver.get(kind, 0) + 1
        self.refresh()

    def refresh(self):
        for w in list(self.windows.values()):
            w.refresh()
        return False

    def set_hidden(self, hidden):
        """Ocultar un momento (capturas, grabación). Nunca vuelve a mostrar la isla con la sesión bloqueada."""
        self.lock.request_visible(not hidden)

    def _set_visible(self, visible):
        for w in self.windows.values():
            (w.show if visible else w.hide)()

    # ── avisos ──
    def show_event(self, secs=3.0, **ev):
        ev["until"] = time.monotonic() + secs
        self.event = ev
        self.refresh()
        GLib.timeout_add(int(secs * 1000) + 60, self.refresh)

    def welcome(self, back=False):
        name = (GLib.get_real_name() or "").split(" ")[0]
        if not name or name == "Unknown":
            name = GLib.get_user_name()
        if back:
            right = f"{self.battery.percent:.0f}%" if self.battery.present else hm()
            self.show_event(3.5, kind="pill", icon="weather-clear-symbolic", text=f"Bienvenido de vuelta, {name}",
                            right=right)
        else:
            self.show_event(3.5, kind="pill", icon="face-smile-symbolic", text=f"Hola, {name}",
                            right=hm())
        return False

    def _on_sleep(self, _c, _s, _p, _i, _sig, params):
        if not params.unpack()[0]:          # al despertar
            self.wifi.refresh()
            self.bt.refresh()
            GLib.timeout_add(1200, lambda: self.welcome(True))

    def charge_target(self):
        """Tope de carga de la batería (80 si «Cuidar batería» está activo, si no 100)."""
        cl = getattr(self, "charge_limit", None)
        return cl.end if cl and cl.supported and cl.enabled else 100

    def _on_notify(self, n):
        n["ms"] = ms_kind(n)
        dbg(notif_debug_line(n, n["ms"]))
        if n["ms"]:
            n["body"] = clean_body(n["body"])
            n["app"] = "Microsoft Teams" if n["ms"] == "teams" else "Outlook"
            n["icon"] = TEAMS_APP if n["ms"] == "teams" else "mail-unread-symbolic"
            self.ms_unread[n["ms"]] += 1
            self.ver["ms"] = self.ver.get("ms", 0) + 1
        self.notifs.insert(0, n)
        del self.notifs[60:]
        self.unread += 1
        self.changed("notifs")
        if not self.notif.dnd or n["urgent"]:
            self.show_event(9.0, kind="card", pixbuf=n["pixbuf"], icon=n["icon"], app=n["app"],
                            title=n["summary"], body=n["body"], action=lambda n=n: self.open_notif(n))

    def open_notif(self, n):
        if n.get("ms") == "teams":
            self.open_teams()
        elif n.get("ms") == "outlook":
            open_uri(OUTLOOK_URL)
        else:
            # solo se lanza la app que envió el aviso (el hint desktop-entry lo puede falsear cualquiera)
            desk = n.get("desktop") or ""
            if not (desktop_matches_app(desk, n["app"]) and launch_desktop(desk)) and not launch_desktop(n["app"]):
                self.notif.open_center()

    def open_teams(self):
        if not launch_desktop(TEAMS_APP):
            open_uri("https://teams.microsoft.com/")

    def open_github(self, url=None):
        if url:
            open_web(url)
        elif not launch_desktop(GITHUB_APP):
            open_uri("https://github.com/pulls")

    # capturas y grabación (las piden las páginas Inicio y Grabar)
    def screenshot(self, monitor=None):
        self.capture.screenshot(monitor)

    def record(self, monitor=None):
        self.capture.record(monitor)

    def _on_weather(self):
        self.changed("weather")
        self.events.weather()


    # ── temporizador ──
    def start_timer(self, secs):
        self.timer_total, self.timer_end = secs, time.monotonic() + secs
        self.refresh()

    def stop_timer(self):
        self.timer_end = None
        self.refresh()

    def dismiss_alert(self):
        self.alert_until = None
        self.refresh()

    # ── captura ──
    # ── tic de 1 s ──
    def tick(self):
        now = time.monotonic()
        if self.timer_end and now >= self.timer_end:
            self.timer_end = None
            self.alert_until = now + 10
            play_sound("alarm-clock-elapsed.oga", "complete.oga")
        self.pomo.tick()
        self.reminders.tick()
        if self.recorder.active:
            self.changed("rec")
        minute = int(time.time() // 60)
        if minute != self._rm_minute:          # «en 12 min» se actualiza cada minuto
            self._rm_minute = minute
            if self.reminders.items:
                self.changed("reminders")
        self.media = self.mpris.poll()
        self._load_art()
        self.refresh()
        return True

    def media_cmd(self, method):
        if self.media:
            self.mpris.command(self.media["name"], method)
            GLib.timeout_add(180, lambda: (setattr(self, "media", self.mpris.poll()), self.refresh())[1])

    def _load_art(self):
        url = self.media["art"] if self.media else None
        if url == self._art_url:
            return
        self._art_url = url
        if not url:
            self.art = None
            return
        if url in self._art_cache:
            self.art = self._art_cache[url]
            return

        def done(f, res):
            pb = None
            try:
                _ok, data, _etag = f.load_contents_finish(res)
                loader = GdkPixbuf.PixbufLoader()
                loader.write(data)
                loader.close()
                pb = loader.get_pixbuf()
            except (GLib.Error, AttributeError):
                pb = None
            self._art_cache[url] = pb
            if self._art_url == url:
                self.art = pb
                self.refresh()
        Gio.File.new_for_uri(url).load_contents_async(None, done)
