"""Página de inicio: reloj, música, volumen, ajustes rápidos y accesos."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import feature, page

feature("privacy", "Cámara y micrófono",
        "Punto verde (cámara) o naranja (micrófono) en la píldora mientras una app los usa")


class HomePage:
    PAGES = {
        "home": page("_build_home", open="_open_home"),
    }

    def _build_home(self):
        c = self.core
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_start=14, margin_end=14, margin_top=12, margin_bottom=14)
        top = Gtk.Box(spacing=12)
        self.h_clock = label("", "bigclock", ellipsize=False)
        top.pack_start(self.h_clock, False, False, 0)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=2)
        self.h_date = label("", "artist", xalign=1.0)
        bat = Gtk.Box(spacing=5, halign=Gtk.Align.END)
        self.h_bat_icon = Gtk.Image()
        self.h_bat = label("", "dim", xalign=1.0, ellipsize=False)
        bat.pack_start(self.h_bat_icon, False, False, 0)
        bat.pack_start(self.h_bat, False, False, 0)
        side.pack_start(self.h_date, False, False, 0)
        side.pack_start(bat, False, False, 0)
        self.h_priv = label("", "small", xalign=1.0, ellipsize=False)
        self.h_priv.set_no_show_all(True)
        side.pack_start(self.h_priv, False, False, 0)
        wbox = Gtk.Box(spacing=5)
        self.h_w_icon = WeatherIcon(18)
        self.h_w = label("Clima", "dim", ellipsize=False)
        wbox.pack_start(self.h_w_icon, False, False, 0)
        wbox.pack_start(self.h_w, False, False, 0)
        wbtn = self.h_w_btn = button("wlink", wbox, lambda: self.go("weather"), "Ver el clima")
        wbtn.set_halign(Gtk.Align.END)
        side.pack_start(wbtn, False, False, 0)
        top.pack_end(side, True, True, 0)
        box.pack_start(top, False, False, 0)

        # reproductor
        self.h_media = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        row = Gtk.Box(spacing=10)
        self.m_art = Art(44, 10)
        row.pack_start(self.m_art, False, False, 0)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=1)
        self.m_title = label("", "subtitle")
        self.m_artist = label("", "artist")
        txt.pack_start(self.m_title, False, False, 0)
        txt.pack_start(self.m_artist, False, False, 0)
        row.pack_start(txt, True, True, 0)
        row.pack_start(button("ctrl", icon("media-skip-backward-symbolic"), lambda: c.media_cmd("Previous")),
                       False, False, 0)
        self.m_play_img = icon("media-playback-pause-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        row.pack_start(button("ctrl", self.m_play_img, lambda: c.media_cmd("PlayPause")), False, False, 0)
        row.pack_start(button("ctrl", icon("media-skip-forward-symbolic"), lambda: c.media_cmd("Next")),
                       False, False, 0)
        self.h_media.pack_start(row, False, False, 0)
        prog = Gtk.Box(spacing=8)
        self.m_pos = label("0:00", "time-small", ellipsize=False)
        self.m_len = label("0:00", "time-small", ellipsize=False)
        self.m_bar = Gtk.LevelBar(valign=Gtk.Align.CENTER, hexpand=True, min_value=0, max_value=1)
        for off in ("low", "high", "full"):
            self.m_bar.remove_offset_value(off)
        prog.pack_start(self.m_pos, False, False, 0)
        prog.pack_start(self.m_bar, True, True, 0)
        prog.pack_start(self.m_len, False, False, 0)
        self.h_media.pack_start(prog, False, False, 0)
        self.h_media.set_no_show_all(True)
        for ch in (row, prog):
            ch.show_all()
        box.pack_start(self.h_media, False, False, 0)

        # volumen
        vol = Gtk.Box(spacing=8)
        self.v_img = icon("audio-volume-high-symbolic")
        vol.pack_start(button("ctrl", self.v_img, Volume.toggle_mute, "Silenciar"), False, False, 0)
        self.v_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.v_scale.set_draw_value(False)
        self.v_scale.set_hexpand(True)
        self.v_scale.connect("value-changed", self._on_vol_scale)
        vol.pack_start(self.v_scale, True, True, 0)
        self.v_pct = label("", "time-small", ellipsize=False)
        self.v_pct.set_width_chars(4)
        vol.pack_start(self.v_pct, False, False, 0)
        box.pack_start(vol, False, False, 0)

        # ajustes rápidos
        grid = Gtk.Grid(column_homogeneous=True, row_spacing=8, column_spacing=4)
        m = c.modes
        self.t_wifi = Tile("network-wireless-symbolic", "Wi-Fi",
                           lambda: c.wifi.set_enabled(not c.wifi.enabled), lambda: self.go("wifi"))
        self.t_bt = Tile("bluetooth-active-symbolic", "Bluetooth",
                         lambda: c.bt.set_powered(not c.bt.powered), lambda: self.go("bt"))
        self.t_air = Tile("airplane-mode-symbolic", "Avión", c.radios.toggle)
        self.t_dnd = Tile("notifications-disabled-symbolic", "No molestar", c.notif.toggle_dnd)
        self.t_dark = Tile("dark-mode-symbolic", "Oscuro", m.toggle_dark)
        self.t_night = Tile("night-light-symbolic", "Luz nocturna", m.toggle_night)
        self.t_saver = Tile("power-profile-power-saver-symbolic", "Ahorro", m.toggle_saver)
        self.t_awake = Tile("caffeine-cup-full-symbolic", "Despierto", m.toggle_awake)
        self.t_care = Tile("battery-level-80-symbolic", "Cuidar batería", c.charge_limit.toggle)
        tiles = [self.t_wifi, self.t_bt, self.t_air, self.t_dnd, self.t_dark,
                 self.t_night, self.t_saver, self.t_awake]
        if c.charge_limit.supported:
            tiles.append(self.t_care)
        cols = 5 if len(tiles) > 8 else 4
        for i, t in enumerate(tiles):
            grid.attach(t, i % cols, i // cols, 1, 1)
        box.pack_start(grid, False, False, 0)

        # accesos
        acts = Gtk.Box(spacing=5, halign=Gtk.Align.CENTER)

        def act_btn(ic, txt, tip, cb):
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
            inner.pack_start(icon(ic, px=18), False, False, 0)
            inner.pack_start(label(txt, "time-small", xalign=0.5, ellipsize=False), False, False, 0)
            return button("act", inner, cb, tip)

        def act(ic, txt, tip, cb):
            acts.pack_start(act_btn(ic, txt, tip, cb), False, False, 0)
        act("applets-screenshooter-symbolic", "Recorte", "Capturar un área (arrastra un rectángulo)",
            lambda: self._collapse_then(c.screenshot))
        act("view-fullscreen-symbolic", "Pantalla", "Capturar esta pantalla completa",
            lambda: self._collapse_then(lambda: c.screenshot(self.monitor)))
        act("edit-paste-symbolic", "Copias", "Historial del portapapeles", lambda: self.go("clip"))
        ov = Gtk.Overlay()
        ov.add(act_btn("preferences-system-notifications-symbolic", "Avisos", "Notificaciones",
                       lambda: self.go("notifs")))
        self.badge = label("", "badge", xalign=0.5, ellipsize=False)
        self.badge.set_halign(Gtk.Align.END)
        self.badge.set_valign(Gtk.Align.START)
        self.badge.set_no_show_all(True)
        ov.add_overlay(self.badge)
        acts.pack_start(ov, False, False, 0)
        act("media-removable-symbolic", "USB", "Medios extraíbles", lambda: self.go("usb"))
        act("timer-symbolic", "Pomodoro", "Pomodoro", lambda: self.go("pomo"))
        act("alarm-symbolic", "Alarma", "Temporizador", lambda: self.go("timer"))
        act("system-shutdown-symbolic", "Energía", "Bloquear, suspender, reiniciar, apagar", lambda: self.go("power"))
        box.pack_start(acts, False, False, 0)

        # trabajo: GitHub, Teams y correo
        work = Gtk.Box(spacing=6)
        self.work_labels, self.work_buttons = {}, {}
        for key, ic, txt, tip, target in (("github", GITHUB_APP, "GitHub", "Pull requests", "github"),
                                        ("teams", TEAMS_APP, "Teams", "Mensajes de Teams", "ms"),
                                        ("outlook", "mail-unread-symbolic", "Correo", "Correo de Outlook", "ms")):
            inner = Gtk.Box(spacing=7)
            inner.pack_start(icon(ic, px=18), False, False, 0)
            inner.pack_start(label(txt, "small", ellipsize=False), False, False, 0)
            cnt = label("", "badge", xalign=0.5, ellipsize=False)
            cnt.set_valign(Gtk.Align.CENTER)
            cnt.set_no_show_all(True)
            inner.pack_end(cnt, False, False, 0)
            self.work_labels[key] = cnt
            btn = self.work_buttons[key] = button("work", inner, lambda pg=target: self.go(pg), tip)
            work.pack_start(btn, True, True, 0)
        work.pack_end(button("work", icon("view-more-symbolic", px=18), lambda: self.go("more"),
                             "Más herramientas y ajustes"), False, False, 0)
        box.pack_start(work, False, False, 0)
        return box

    def _set_count(self, key, n):
        lb = self.work_labels[key]
        lb.set_text(str(min(n, 99)))
        lb.set_visible(n > 0)

    def _on_vol_scale(self, scale):
        if not self._vol_lock:
            Volume.set(scale.get_value() / 100)

    def _update_home(self, c, m, playing, timer_left):
        self.h_clock.set_text(time.strftime("%H:%M"))
        self.h_date.set_text(fecha())
        b = c.battery
        if b.present:
            lim = c.charge_limit
            self.h_bat.set_text(f"{b.percent:.0f}%" + (" · cargando" if b.charging else "") +
                                (f" · límite {lim.end}%" if lim.enabled else ""))
            self.h_bat_icon.set_from_icon_name(bat_icon(b.percent, b.charging), Gtk.IconSize.MENU)
            set_accent(self.h_bat_icon, "green" if b.charging else ("red" if b.percent <= 15 else None))
        self.h_bat.set_visible(b.present)
        self.h_bat_icon.set_visible(b.present)

        self.h_media.set_visible(m is not None)
        self.c_art.set_pixbuf(c.art)
        self.m_art.set_pixbuf(c.art)
        if m:
            self.m_title.set_text(m["title"])
            self.m_artist.set_text(m["artist"] or m["album"])
            self.m_play_img.set_from_icon_name(
                "media-playback-pause-symbolic" if playing else "media-playback-start-symbolic",
                Gtk.IconSize.LARGE_TOOLBAR)
            self.m_pos.set_text(fmt_secs(m["position"]))
            self.m_len.set_text(fmt_secs(m["length"]) if m["length"] else "--:--")
            self.m_bar.set_value(min(1.0, m["position"] / m["length"]) if m["length"] else 0)

        v, muted = c.volume.value, c.volume.muted
        if not self.v_scale.has_grab():
            self._vol_lock = True
            self.v_scale.set_value(round(v * 100))
            self._vol_lock = False
        self.v_pct.set_text("—" if muted else f"{round(v * 100)}%")
        self.v_img.set_from_icon_name("audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic",
                                      Gtk.IconSize.MENU)

        w = c.wifi
        self.t_wifi.set(w.enabled, (w.active or ("Cable" if w.wired else "Sin red")) if w.enabled else "Apagado",
                        "network-wireless-symbolic" if w.enabled else "network-wireless-disabled-symbolic")
        connected = [d["name"] for d in c.bt.devices.values() if d["connected"]]
        self.t_bt.set(c.bt.powered, (connected[0] if connected else "Encendido") if c.bt.powered else "Apagado",
                      "bluetooth-active-symbolic" if c.bt.powered else "bluetooth-disabled-symbolic")
        self.t_air.set(c.radios.airplane, "Activado" if c.radios.airplane else "")
        self.t_dnd.set(c.notif.dnd, "Activado" if c.notif.dnd else "")
        md = c.modes
        self.t_dark.set(md.dark, "Activado" if md.dark else "")
        self.t_night.set(md.night, "Activada" if md.night else "")
        self.t_saver.set(md.profile == "power-saver",
                         {"power-saver": "Activado", "performance": "Rendimiento"}.get(md.profile, ""))
        self.t_awake.set(md.awake, "Activado" if md.awake else "")
        lim = c.charge_limit
        self.t_care.set(lim.enabled, f"Hasta {lim.end}%" if lim.enabled else "Hasta 100%")

        if c.unread:
            self.badge.set_text(str(min(c.unread, 99)))
            self.badge.show()
        else:
            self.badge.hide()
        self._set_count("github", len(c.github.review))
        self._set_count("teams", c.ms_unread["teams"])
        self._set_count("outlook", c.ms_unread["outlook"])

        p = c.privacy
        self.h_priv.set_text(p.summary())
        self.h_priv.set_visible(bool(p.cam or p.mic))
        set_accent(self.h_priv, "green" if p.cam else "orange")
        self.h_w_btn.set_visible(c.feature("weather"))
        self.work_buttons["github"].set_visible(c.feature("github"))
        self.work_buttons["teams"].set_visible(c.feature("ms"))
        self.work_buttons["outlook"].set_visible(c.feature("ms"))
        wd = c.weather.data
        if wd:
            self.h_w.set_text(f"{wd['temp']:.0f}° · {wd['desc']}")
            self.h_w_icon.set_kind(wd.get("kind", "cloudy"))
        else:
            self.h_w.set_text("Cargando clima…" if c.weather.loading else "Clima")

        p = c.pomo
        acc = "red" if p.phase == "work" else "green"
        self.po_phase.set_text(Pomodoro.LABEL[p.phase] + ("" if p.running or not p.active else " · en pausa"))
        set_accent(self.po_phase, acc)
        self.po_time.set_text(fmt_secs(p.left()))
        set_accent(self.po_time, acc if p.active else None)
        self.po_cycle.set_text(p.cycle_text())
        self.po_play.set_from_icon_name("media-playback-pause-symbolic" if p.running else
                                        "media-playback-start-symbolic", Gtk.IconSize.LARGE_TOOLBAR)

        self.t_big.set_text(fmt_secs(timer_left) if timer_left is not None else "—")
        set_accent(self.t_big, "orange" if timer_left is not None else None)
        self.t_stop.set_visible(timer_left is not None)

        for key, (btn, lb, txt) in self.pw_buttons.items():
            confirming = self._confirm == key
            set_class(btn, "confirm", confirming)
            lb.set_text("¿Seguro?" if confirming else txt)
        if not self._confirm:
            self.pw_hint.set_text("")

    def _open_home(self):
        self.core.radios.refresh()
