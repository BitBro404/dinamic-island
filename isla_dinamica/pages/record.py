"""Grabar la pantalla (wf-recorder)."""
from ..common import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import page, tool


class RecordPage:
    PAGES = {
        "record": page("_build_record", "_fill_record", ("rec",)),
    }
    TOOLS = (tool("media-record-symbolic", "Grabar", "Grabar la pantalla en video", "record"),)

    def _build_record(self):
        box = self._page("Grabar pantalla")
        self.rc_state = label("", "dim")
        box.pack_start(self.rc_state, False, False, 0)

        self.rc_opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.rc_opts.pack_start(label("AUDIO", "section"), False, False, 0)
        row = Gtk.Box(spacing=6, homogeneous=True)
        self.rc_audio = {}
        for key, text in Recorder.AUDIO:
            b = button("chip", cb=lambda k=key: self._rc_audio(k), text=text)
            self.rc_audio[key] = b
            row.pack_start(b, True, True, 0)
        self.rc_opts.pack_start(row, False, False, 0)

        self.rc_opts.pack_start(label("QUÉ GRABAR", "section"), False, False, 0)
        acts = Gtk.Box(spacing=6, homogeneous=True)

        def big(ic, title, sub, cb):
            inner = Gtk.Box(spacing=10)
            inner.pack_start(icon(ic, px=24), False, False, 0)
            t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            t.pack_start(label(title, "subtitle"), False, False, 0)
            t.pack_start(label(sub, "dim small"), False, False, 0)
            inner.pack_start(t, True, True, 0)
            return button("act", inner, cb)
        acts.pack_start(big("view-fullscreen-symbolic", "Esta pantalla", "Toda la pantalla",
                            lambda: self._collapse_then(lambda: self.core.record(self.monitor))), True, True, 0)
        acts.pack_start(big("applets-screenshooter-symbolic", "Un área", "Arrastra un rectángulo",
                            lambda: self._collapse_then(lambda: self.core.record(None))), True, True, 0)
        self.rc_opts.pack_start(acts, False, False, 0)
        box.pack_start(self.rc_opts, False, False, 0)

        self.rc_stop = button("chip danger", cb=self.core.recorder.stop, text="Detener y guardar")
        box.pack_start(self.rc_stop, False, False, 0)

        foot = Gtk.Box(spacing=6)
        self.rc_hint = label("Para detener: pasa el ratón por la isla", "dim small")
        foot.pack_start(self.rc_hint, True, True, 0)
        foot.pack_end(button("chip", cb=lambda: self._collapse_then(lambda: open_uri(
            Gio.File.new_for_path(self._rc_folder()).get_uri())), text="Abrir carpeta"), False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    @staticmethod
    def _rc_folder():
        d = videos_dir()
        os.makedirs(d, exist_ok=True)
        return d

    def _rc_audio(self, key):
        self.core.recorder.audio = key
        self.core.changed("rec")

    def _fill_record(self):
        rec = self.core.recorder
        for key, b in self.rc_audio.items():
            set_class(b, "on", key == rec.audio)
        self.rc_opts.set_visible(rec.available and not rec.active)
        self.rc_stop.set_visible(rec.active)
        if not rec.available:
            self.rc_state.set_text("Falta wf-recorder: sudo apt install wf-recorder")
            set_accent(self.rc_state, "orange")
        elif rec.active:
            self.rc_state.set_text(f"Grabando · {fmt_secs(rec.elapsed())}")
            set_accent(self.rc_state, "red")
        elif rec.error:
            self.rc_state.set_text(f"No se pudo grabar: {rec.error}")
            set_accent(self.rc_state, "red")
        else:
            self.rc_state.set_text("Se guarda en Vídeos/Grabaciones (MP4)")
            set_accent(self.rc_state, None)
