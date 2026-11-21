"""Estado compartido por las islas de todas las pantallas."""
from .common import *  # noqa: F401,F403
from .services import *  # noqa: F401,F403
from .window import IslandWindow


# ───────────────────────────── núcleo compartido ─────────────────────────────
class Core:
    """Estado y servicios compartidos por las islas de todas las pantallas."""

    def __init__(self, app):
        self.app = app
        self.windows = {}
        self.ver = {}
        self.media = None
        self.event = None
        self.timer_end, self.timer_total, self.alert_until = None, 0, None
        self.notifs = []
        self.unread = 0
        self._art_url, self._art_cache, self.art = None, {}, None

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sysbus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.mpris = Media(bus)
        self.volume = Volume(self._on_volume)
        self.charge_limit = ChargeLimit(sysbus, lambda: self.changed("modes"))
        self.battery = Battery(self._on_battery, self._charge_target)
        self.notif = Notifications(bus, self._on_notify, lambda: self.changed("modes"))
        self.clip = Clipboard(lambda: self.changed("clip"))
        self.bt = Bluetooth(sysbus, lambda: self.changed("bt"), self._on_bt_connect)
        self.wifi = Wifi(sysbus, lambda: self.changed("wifi"))
        self.radios = Radios(lambda: self.changed("modes"))
        self.modes = Modes(sysbus, bus, lambda: self.changed("modes"))
        self.drives = Drives(lambda: self.changed("usb"), self._on_drive)
        self.power = Power(sysbus, bus)
        self.config = Config()
        self.feature("clock24")
        self._rain_warned = None
        self.weather = Weather(self.config, self._on_weather)
        self.pomo = Pomodoro(self.config, self._on_pomo_end, lambda: self.changed("pomo"))
        self.ms_unread = {"teams": 0, "outlook": 0}
        self.git = GitWatch(self.config, lambda: self.changed("git"), self._on_git, lambda: self.feature("git"))
        self.recorder = Recorder(lambda: self._on_rec_change(), self._on_rec_done)
        self.reminders = Reminders(lambda: self.changed("reminders"), self._on_reminder)
        self._rm_minute = None
        self.fx = Fx(lambda: self.changed("fx"), self._on_fx_day, lambda: self.feature("fx"))
        self.audio = AudioWatch(lambda: self.changed("audio"), lambda: self.feature("audio"))
        self.privacy = Privacy(lambda: self.changed("privacy"), self._on_privacy, lambda: self.feature("privacy"))
        self.presence = Presence(self.config, lambda: self.changed("presence"), lambda: self.changed("presence"),
                                 lambda: self.feature("presence"),
                                 in_call=lambda: bool(self.feature("audio") and self.audio.call))
        self.downloads = Downloads(lambda: self.changed("downloads"), self._on_download,
                                   lambda: self.feature("downloads"))
        self.netmon = NetMon(lambda: self.changed("netmon"), self._on_net, lambda: self.feature("netmon"))
        self.sysmon = SysMon(lambda: self.changed("sysmon"), self._on_sysmon, lambda: self.feature("sysmon"))
        self.servers = Servers(lambda: self.changed("servers"), self._on_server, lambda: self.feature("servers"))
        self.deploys = Deploys(lambda: self.changed("deploys"), self._on_deploy, lambda: self.feature("deploys"))
        self.github = GitHub(lambda: self.changed("github"), self._on_github, lambda: self.feature("github"))

        # bienvenida al despertar / desbloquear
        sysbus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep",
                                "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, self._on_sleep)
        sysbus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Session", "Unlock",
                                None, None, Gio.DBusSignalFlags.NONE, lambda *_: self.welcome(True))

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
        for w in self.windows.values():
            (w.hide if hidden else w.show)()

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

    def _on_weather(self):
        self.changed("weather")
        w = getattr(self, "weather", None)     # el primer aviso llega antes de asignarlo
        d = w and w.data
        soon = d and d.get("soon")
        if soon:
            key = time.strftime("%Y-%m-%d ") + soon["hour"]
            if key != self._rain_warned:
                self._rain_warned = key
                storm = soon["kind"] == "storm"
                self.show_event(4.0, kind="pill",
                                icon="weather-storm-symbolic" if storm else "weather-showers-symbolic",
                                accent="blue", text=f"{'Tormenta' if storm else 'Lluvia'} hacia las {soon['hour']}",
                                right=f"{soon['pop']}%", right_accent="blue")

    def _on_volume(self, v, muted):
        self.show_event(1.8, kind="volume", value=v, muted=muted)

    def _charge_target(self):
        cl = getattr(self, "charge_limit", None)
        return cl.end if cl and cl.supported and cl.enabled else 100

    def _on_battery(self, kind, pct):
        if kind == "low":
            play_sound("dialog-warning.oga", "bell.oga")
            self.show_event(12.0, kind="card", icon="battery-caution-symbolic", app="Batería",
                            title=f"Batería baja · {pct:.0f} %",
                            body="Conecta el cargador para no perder tu trabajo.", action=None)
            return
        if kind == "full":
            play_sound("complete.oga")
            target = self._charge_target()
            if target < 100:
                title = f"Batería al {target} % · tope de cuidado"
                body = (f"Se detuvo la carga en {target} % para cuidar la batería. "
                        "Si necesitas el 100 %, apaga «Cuidar batería».")
            else:
                title = "Carga completa · 100 %"
                body = "Ya puedes desconectar el cargador."
            self.show_event(10.0, kind="card", icon="battery-full-charged-symbolic", app="Batería",
                            title=title, body=body, action=None)
            return
        txt, acc, ic = {
            "charging": ("Cargando", "green", bat_icon(pct, True)),
            "unplugged": ("Con batería", None, bat_icon(pct, False)),
            "low": ("Batería baja", "red", "battery-caution-symbolic"),
        }[kind]
        right = f"{pct:.0f}%"
        if kind == "charging" and self.charge_limit.enabled:
            right += f" · hasta {self.charge_limit.end}%"
        self.show_event(4.5, kind="pill", icon=ic, accent=acc, text=txt, right=right, right_accent=acc)

    def _on_notify(self, n):
        n["ms"] = ms_kind(n)
        dbg("aviso:", n["app"], "|", n["desktop"], "|", n["summary"], "->", n["ms"])
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
        elif not launch_desktop(n.get("desktop") or "") and not launch_desktop(n["app"]):
            self.notif.open_center()

    def open_teams(self):
        if not launch_desktop(TEAMS_APP):
            open_uri("https://teams.microsoft.com/")

    def open_github(self, url=None):
        if url:
            open_uri(url)
        elif not launch_desktop(GITHUB_APP):
            open_uri("https://github.com/pulls")

    def _on_privacy(self, kind, apps):
        who = ", ".join(apps)
        if kind == "cam":
            self.show_event(3.5, kind="pill", icon="camera-web-symbolic", accent="green",
                            text=f"{who} está usando la cámara")
        else:
            self.show_event(3.5, kind="pill", icon="audio-input-microphone-symbolic", accent="orange",
                            text=f"{who} está usando el micrófono")

    def _on_git(self, kind, s):
        n = s["behind"]
        self.show_event(5.0, kind="pill", icon="emblem-synchronizing-symbolic", accent="blue",
                        text=f"{s['name']}: {n} commit{'s' if n != 1 else ''} nuevo{'s' if n != 1 else ''} en {s['upstream']}")

    # ── grabación ──
    def record(self, monitor=None):
        """Con monitor: graba esa pantalla. Sin monitor: eliges un área con slurp."""
        def go(geom):
            if self.recorder.start(geom):
                for w in self.windows.values():
                    w.page = "record"
            else:
                self.show_event(4.0, kind="pill", icon="dialog-error-symbolic", accent="red",
                                text="No se pudo empezar a grabar")

        def start():
            if monitor is not None:
                g = monitor.get_geometry()
                go(f"{g.x},{g.y} {g.width}x{g.height}")
            else:
                self.set_hidden(True)

                def picked(ok, out, _e):
                    self.set_hidden(False)
                    if ok and out.strip():
                        go(out.strip())
                run(["slurp", "-d", "-b", "00000099", "-c", "ff453aff", "-s", "00000000", "-w", "2"], picked)
            return False
        GLib.timeout_add(250, start)

    def _on_rec_change(self):
        self.changed("rec")

    def _on_rec_done(self, path, secs):
        for w in self.windows.values():
            if w.page == "record" and not w.hover:
                w.page = "home"
        if not path:
            self.show_event(6.0, kind="pill", icon="dialog-error-symbolic", accent="red",
                            text=f"La grabación falló · {self.recorder.error or ''}".rstrip(" ·"))
            return
        size = os.path.getsize(path)
        self.show_event(8.0, kind="card", icon="media-record-symbolic", app="Grabación guardada",
                        title=os.path.basename(path), body=f"{fmt_secs(secs)} · {fmt_size(size)} · clic para abrir",
                        action=lambda: open_uri(Gio.File.new_for_path(path).get_uri()))

    def _on_reminder(self, r, late=False):
        if not self.feature("reminders"):
            return
        play_sound("alarm-clock-elapsed.oga", "complete.oga")
        hm_ = hm(r["at"])
        self.show_event(20.0, kind="card", icon="alarm-symbolic",
                        app=f"Recordatorio · pendiente desde las {hm_}" if late else f"Recordatorio · {hm_}",
                        title=r["text"], body="Clic para posponer 10 min",
                        action=lambda: (self.reminders.snooze(r, 10),
                                        self.show_event(2.0, kind="pill", icon="alarm-symbolic", accent="blue",
                                                        text="Pospuesto 10 min")))

    def _on_fx_day(self):
        ch = self.fx.change()
        right = None if ch is None else f"{'▲' if ch > 0 else '▼'} {abs(ch):.1f}%".replace(".", ",")
        self.show_event(5.0, kind="pill", icon="money-symbolic", text=f"TRM hoy {cop(self.fx.trm)}",
                        right=right, right_accent=None if ch is None else "red" if ch > 0 else "green")

    def _on_download(self, kind, d):
        if kind == "done":
            path = d["path"]
            self.show_event(7.0, kind="card", icon="folder-download-symbolic", app="Descarga terminada",
                            title=d["name"], body=f"{fmt_size(d['size'])} · clic para abrir",
                            action=lambda: open_uri(Gio.File.new_for_path(path).get_uri()))
        elif kind == "cancelled":
            self.show_event(3.0, kind="pill", icon="folder-download-symbolic", text=f"Descarga cancelada · {d['name']}")

    def _on_net(self, kind, name):
        if kind == "vpn_on":
            self.show_event(3.0, kind="pill", icon="network-vpn-symbolic", accent="blue", text=f"VPN conectada · {name}")
        elif kind == "vpn_off":
            self.show_event(4.0, kind="pill", icon="network-vpn-symbolic", accent="orange",
                            text=f"VPN desconectada · {name}")
        elif kind == "offline":
            self.show_event(6.0, kind="pill", icon="network-offline-symbolic", accent="red", text="Sin Internet")
        else:
            self.show_event(3.0, kind="pill", icon="network-transmit-receive-symbolic", accent="green",
                            text="Internet de vuelta")

    def _on_sysmon(self, kind, name, value):
        if kind == "cpu":
            self.show_event(6.0, kind="pill", icon="utilities-system-monitor-symbolic", accent="orange",
                            text=f"{name} usa mucha CPU", right=f"{value:.0f}%", right_accent="orange")
        elif kind == "ram":
            self.show_event(6.0, kind="pill", icon="dialog-warning-symbolic", accent="red",
                            text="Queda poca memoria" + (f" · {name}" if name else ""),
                            right=f"{value:.0f}% libre", right_accent="red")
        else:
            self.show_event(6.0, kind="pill", icon="dialog-warning-symbolic", accent="red",
                            text="La CPU está muy caliente", right=f"{value:.0f}°", right_accent="red")

    def _on_server(self, kind, s):
        where = f"{s['name']} · :{s['port']}"
        if kind == "up":
            self.show_event(3.0, kind="pill", icon="network-server-symbolic", accent="green", text=f"Listo · {where}")
        elif kind == "stopped":
            self.show_event(2.5, kind="pill", icon="process-stop-symbolic", text=f"Detenido · {where}")
        else:
            self.show_event(6.0, kind="pill", icon="dialog-error-symbolic", accent="red", text=f"Se cayó · {where}")

    def _on_deploy(self, kind, d):
        where = f"{d['name']} · {d['env']}"
        if kind == "start":
            self.show_event(3.0, kind="pill", icon="emblem-synchronizing-symbolic", accent="orange",
                            text=f"Desplegando {where}")
        elif d["state"] == "SUCCESS":
            self.show_event(5.0, kind="pill", icon="emblem-ok-symbolic", accent="green", text=f"Desplegado · {where}")
        else:
            self.show_event(12.0, kind="card", icon="dialog-error-symbolic", app="Despliegue fallido",
                            title=where, body=d["commit"] or d["repo"], action=lambda: open_uri(d["url"]))

    def _on_github(self, kind, p):
        ref = f"{p['repo']}#{p['num']}"
        if kind == "review":
            self.show_event(9.0, kind="card", icon=GITHUB_APP, app="GitHub · Revisión pedida",
                            title=p["title"], body=f"{ref} · {p['author']}",
                            action=lambda: self.open_github(p["url"]))
        elif kind == "ci":
            good = p["ci"] == "SUCCESS"
            self.show_event(4.0, kind="pill", icon="emblem-ok-symbolic" if good else "dialog-error-symbolic",
                            accent="green" if good else "red", text=f"CI {'pasó' if good else 'falló'} · {ref}")
        elif kind == "decision":
            good = p["review"] == "APPROVED"
            self.show_event(4.0, kind="pill", icon="emblem-ok-symbolic" if good else "document-edit-symbolic",
                            accent="green" if good else "orange",
                            text=f"{'Aprobada' if good else 'Piden cambios'} · {ref}")

    def _on_bt_connect(self, name, connected, ic):
        self.show_event(4.0, kind="pill", icon=ic, accent="blue" if connected else None,
                        text=name, right="Conectado" if connected else "Desconectado",
                        right_accent="blue" if connected else None)

    def _on_drive(self, kind, name, vol):
        if kind == "usb":
            self.show_event(7.0, kind="card", icon="media-removable-symbolic", app="Medio extraíble",
                            title=name, body="Haz clic para abrirlo", action=lambda: self.drives.open(vol))
        elif kind == "ejected":
            self.show_event(3.0, kind="pill", icon="media-eject-symbolic", accent="green",
                            text=f"Ya puedes retirar {name}")
        else:
            self.show_event(3.5, kind="pill", icon="dialog-warning-symbolic", accent="red", text=name)

    # ── temporizador ──
    def _on_pomo_end(self, prev, nxt):
        for snd in ("/usr/share/sounds/freedesktop/stereo/complete.oga",
                    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"):
            if os.path.exists(snd):
                subprocess.Popen(["pw-play", snd], stderr=subprocess.DEVNULL)
                break
        mins = self.pomo.conf[nxt]
        title = "¡Buen trabajo! Toca descansar" if prev == "work" else "¡Fin del descanso! A enfocarse"
        auto = self.pomo.running
        body = f"Siguiente: {Pomodoro.LABEL[nxt].lower()} de {mins} min" + \
            ("" if auto else " · haz clic para empezar")
        self.show_event(10.0, kind="card", icon="timer-symbolic", app="Pomodoro", title=title, body=body,
                        action=None if auto else self.pomo.start)

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
    def screenshot(self, monitor=None):
        """Sin monitor: eliges un área con un rectángulo sobre la pantalla sombreada.
        Con monitor: captura esa pantalla completa."""
        folder = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
                              or os.path.expanduser("~/Imágenes"), "Capturas")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, time.strftime("Captura %Y-%m-%d %H-%M-%S.png"))
        self.set_hidden(True)

        def grab(geom):
            def saved(ok, _o, _err):
                self.set_hidden(False)
                if not ok:
                    self.show_event(3, kind="pill", icon="dialog-warning-symbolic", accent="red",
                                    text="No se pudo capturar")
                    return
                run(["sh", "-c", 'wl-copy -t image/png < "$1"', "sh", path])
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 160, 160)
                except GLib.Error:
                    pb = None
                self.show_event(7.0, kind="card", pixbuf=pb, icon="camera-photo-symbolic", app="Captura",
                                title="Guardada y copiada al portapapeles", body=os.path.basename(path),
                                action=lambda: open_uri(GLib.filename_to_uri(path, None)))
            run(["grim", "-g", geom, path], saved)

        def start():
            if monitor is not None:
                g = monitor.get_geometry()
                grab(f"{g.x},{g.y} {g.width}x{g.height}")
            else:
                def picked(ok, out, _e):
                    if ok and out.strip():
                        grab(out.strip())
                    else:
                        self.set_hidden(False)
                run(["slurp", "-d", "-b", "00000099", "-c", "ffffffff", "-s", "00000000", "-w", "2",
                     "-B", "ffffff22"], picked)
            return False
        GLib.timeout_add(250, start)

    # ── tic de 1 s ──
    def tick(self):
        now = time.monotonic()
        if self.timer_end and now >= self.timer_end:
            self.timer_end = None
            self.alert_until = now + 10
            for snd in ("/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
                        "/usr/share/sounds/freedesktop/stereo/complete.oga"):
                if os.path.exists(snd):
                    subprocess.Popen(["pw-play", snd], stderr=subprocess.DEVNULL)
                    break
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
