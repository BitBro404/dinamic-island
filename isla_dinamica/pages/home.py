"""Página de inicio: reloj, música, volumen, ajustes rápidos, accesos, sección DEV y «Más opciones».
En los monitores que no son el principal, los ajustes rápidos y los accesos quedan tras el botón «Opciones»."""
from gi.repository import Gtk

from ..services.media import Volume
from ..services.presence import presence_label
from ..ui.gtk import button, icon, label, set_accent
from ..ui.widgets.art import Art
from ..ui.widgets.audio import Spectrum
from ..ui.widgets.tile import Tile
from ..ui.widgets.weather_icon import WeatherIcon
from ..util.fmt import bat_icon, fecha, fmt_secs, hm
from ..util.screens import primary_index
from ..util.links import GITHUB_APP, TEAMS_APP
from .base import Page
from .registry import feature, page

feature("clock24", "Hora en formato 24 h", "Apágalo para ver la hora en 12 h (3:58 pm)")
feature("audio", "Audio en vivo", "Barras que siguen el sonido real, brillo al ritmo y aviso de llamadas o de "
        "apps que reproducen audio")
feature("privacy", "Cámara y micrófono",
        "Punto verde (cámara) o naranja (micrófono) en la píldora mientras una app los usa")


class HomePage(Page):
    """Inicio: reloj, fecha, batería, volumen, ajustes rápidos y accesos a las demás páginas."""
    PAGES = {
        "home": page("_build_home", open="_open_home"),
    }

    def _build_home(self):
        c = self.core
        self._vol_lock = False     # mientras se arrastra la barra, no la mueve el volumen real
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
        self.m_spec = Spectrum(38)
        self.m_spec.levels_fn = lambda: c.audio.levels if c.feature("audio") else None
        spec_btn = button("spec", self.m_spec, lambda: c.media_cmd("PlayPause"), "Clic para pausar o reanudar")
        self.h_media.pack_start(spec_btn, False, False, 0)
        self.h_media.set_no_show_all(True)
        for ch in (row, prog, spec_btn):
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
        self.t_presence = Tile("view-reveal-symbolic", "Presencia",
                               lambda: c.set_feature("presence", not c.feature("presence")),
                               lambda: self.go("presence"))
        tiles = [self.t_wifi, self.t_bt, self.t_air]
        if c.notif.supported:                 # sin servidor de avisos conocido, el tile no tiene sentido
            tiles.append(self.t_dnd)
        tiles += [t for t, ok in ((self.t_dark, m.dark_available), (self.t_night, m.night_available),
                                  (self.t_saver, True), (self.t_awake, m.awake_available),
                                  (self.t_presence, True)) if ok]
        if c.charge_limit.supported:
            tiles.append(self.t_care)
        cols = 5 if len(tiles) > 8 else 4
        for i, t in enumerate(tiles):
            grid.attach(t, i % cols, i // cols, 1, 1)
        # en el monitor secundario: ajustes rápidos y accesos ocultos tras «Opciones» (los rellena el bloque de abajo)
        self.h_opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.h_opts.pack_start(grid, False, False, 0)
        self.h_secondary = not self._on_primary()
        if self.h_secondary:
            inner = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
            self.h_opts_icon = icon("pan-down-symbolic")
            inner.pack_start(self.h_opts_icon, False, False, 0)
            self.h_opts_lbl = label("Opciones", "small", ellipsize=False)
            inner.pack_start(self.h_opts_lbl, False, False, 0)
            box.pack_start(button("work", inner, self._toggle_opts, "Ajustes rápidos y accesos"), False, False, 0)
            self.h_opts.set_no_show_all(True)
        box.pack_start(self.h_opts, False, False, 0)

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
        self.h_opts.pack_start(acts, False, False, 0)
        if not self.h_secondary:
            self.h_opts.show_all()

        # DEV: GitHub, servidores, proyectos y Teams/correo a un clic
        self.h_dev = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.h_dev.pack_start(label("DEV", "section"), False, False, 0)
        dev = Gtk.Box(spacing=5, homogeneous=True)
        self.work_labels, self.work_buttons = {}, {}
        for key, ics, txt, tip, target in (
                ("github", (GITHUB_APP,), "GitHub", "Pull requests, commits por sincronizar y despliegues", "github"),
                ("servers", ("network-server-symbolic",), "Servidores", "Servidores locales y Docker", "servers"),
                ("git", ("folder-symbolic",), "Proyectos", "Repos que vigilas: ramas, pull y push", "projects"),
                ("ms", (TEAMS_APP, "mail-unread-symbolic"), "Teams y correo",
                 "Mensajes de Teams y correo de Outlook", "ms")):
            ov = Gtk.Overlay()
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
            ics_box = Gtk.Box(spacing=3, halign=Gtk.Align.CENTER)
            for ic in ics:
                ics_box.pack_start(icon(ic, px=18), False, False, 0)
            inner.pack_start(ics_box, False, False, 0)
            inner.pack_start(label(txt, "time-small", xalign=0.5, ellipsize=False), False, False, 0)
            btn = button("act", inner, lambda pg=target: self.go(pg), tip)
            ov.add(btn)
            cnt = label("", "badge", xalign=0.5, ellipsize=False)
            cnt.set_halign(Gtk.Align.END)
            cnt.set_valign(Gtk.Align.START)
            cnt.set_no_show_all(True)
            ov.add_overlay(cnt)
            self.work_labels[key] = cnt
            self.work_buttons[key] = ov
            dev.pack_start(ov, True, True, 0)
        self.h_dev.pack_start(dev, False, False, 0)
        box.pack_start(self.h_dev, False, False, 0)

        more = Gtk.Box(spacing=7, halign=Gtk.Align.CENTER)
        more.pack_start(icon("view-more-symbolic", px=18), False, False, 0)
        more.pack_start(label("Más opciones", "small", ellipsize=False), False, False, 0)
        box.pack_start(button("work", more, lambda: self.go("more"), "Herramientas, funciones y ajustes"),
                       False, False, 0)
        return box

    def _on_primary(self):
        """¿Esta isla está en el monitor principal? (el que declara el sistema o, si no, el de arriba a la izquierda)"""
        try:
            d = self.monitor.get_display()
            mons = [d.get_monitor(i) for i in range(d.get_n_monitors())]
            origins = [(m.get_geometry().x, m.get_geometry().y) for m in mons]
            prim = d.get_primary_monitor()
            idx = primary_index(origins, mons.index(prim) if prim in mons else None)
            return idx is None or mons[idx] == self.monitor
        except (AttributeError, TypeError, ValueError):
            return True

    def _toggle_opts(self, show=None):
        show = not self.h_opts.get_visible() if show is None else show
        if show:                              # no_show_all: show_all() sobre la caja no hace nada
            for ch in self.h_opts.get_children():
                ch.show_all()
            self.h_opts.show()
        else:
            self.h_opts.hide()
        self.h_opts_icon.set_from_icon_name("pan-up-symbolic" if show else "pan-down-symbolic", Gtk.IconSize.MENU)
        self.h_opts_lbl.set_text("Ocultar opciones" if show else "Opciones")
        self.refresh()

    def on_collapse(self):
        super().on_collapse()
        if self.h_secondary and self.h_opts.get_visible():
            self._toggle_opts(False)          # al cerrarse vuelve a quedar compacta

    def _set_count(self, key, n):
        lb = self.work_labels[key]
        lb.set_text(str(min(n, 99)))
        lb.set_visible(n > 0)

    def _on_vol_scale(self, scale):
        if not self._vol_lock:
            Volume.set(scale.get_value() / 100)

    def live(self, c, m, playing, timer_left):
        """Refresco de cada segundo: reloj, batería, música, clima y accesos."""
        self.h_clock.set_text(hm())
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
        self.m_art.set_pixbuf(c.art)
        self.m_spec.color = self.host._art_color
        self.m_spec.set_playing(playing and self.hover and self.host.page == "home")
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
        if self.t_dark.get_parent():
            self.t_dark.set(md.dark, "Activado" if md.dark else "")
        if self.t_night.get_parent():
            self.t_night.set(md.night, "Activada" if md.night else "")
        self.t_saver.set(md.profile == "power-saver",
                         {"power-saver": "Activado", "performance": "Rendimiento"}.get(md.profile, ""))
        self.t_awake.set(md.awake, "Activado" if md.awake else "")
        lim = c.charge_limit
        self.t_care.set(lim.enabled, f"Hasta {lim.end}%" if lim.enabled else "Hasta 100%")
        pres_on = c.feature("presence")
        pst = c.presence.state if pres_on else "off"
        self.t_presence.set(pres_on, presence_label("active" if pres_on and pst == "off" else pst),
                            "view-reveal-symbolic" if pres_on else "view-conceal-symbolic")

        if c.unread:
            self.badge.set_text(str(min(c.unread, 99)))
            self.badge.show()
        else:
            self.badge.hide()
        self._set_count("github", len(c.github.review) + c.dev.count("pr"))
        self._set_count("servers", len(c.servers.items) + len(c.servers.docker))
        self._set_count("git", sum(1 for s in c.git.repos if s.get("behind") or s.get("ahead")))
        self._set_count("ms", c.ms_unread["teams"] + c.ms_unread["outlook"])

        p = c.privacy
        self.h_priv.set_text(p.summary())
        self.h_priv.set_visible(bool(p.cam or p.mic))
        set_accent(self.h_priv, "green" if p.cam else "orange")
        self.h_w_btn.set_visible(c.feature("weather"))
        for key in self.work_buttons:
            self.work_buttons[key].set_visible(c.feature(key))
        self.h_dev.set_visible(any(c.feature(k) for k in self.work_buttons))
        wd = c.weather.data
        if wd:
            self.h_w.set_text(f"{wd['temp']:.0f}° · {wd['desc']}")
            self.h_w_icon.set_kind(wd.get("kind", "cloudy"))
        else:
            self.h_w.set_text("Cargando clima…" if c.weather.loading else "Clima")

    def _open_home(self):
        self.core.radios.refresh()
