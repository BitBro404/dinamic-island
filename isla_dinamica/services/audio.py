"""Lo que suena: qué apps reproducen audio, si hay una llamada y el nivel real por bandas.

El nivel se mide escuchando el «monitor» de la salida por defecto con parec (8 kHz, mono),
solo mientras alguna app esté reproduciendo. Se nombra «isla peak detect» para que el
detector de micrófono no lo confunda con una grabación."""
import array
import math
import threading

from ..common import *  # noqa: F401,F403
from .privacy import _pretty

__all__ = ["AudioWatch"]

RATE = 8000
CHUNK = 400                      # 50 ms → 20 lecturas por segundo
WIN = 128                        # muestras analizadas por banda: bandas anchas (~62 Hz) y poco cálculo
BANDS = (125, 375, 1250, 3250)   # Hz: graves, medios bajos, medios, agudos (píldora)
WIN_D = 200                      # espectro detallado (reproductor desplegado): 10 bandas de ~40 Hz
BANDS_D = (80, 130, 200, 300, 450, 700, 1050, 1600, 2400, 3400)
CLIENT = "isla-dinamica-meter"
_IGNORE_BIN = {"pw-play", "paplay", "aplay", "canberra-gtk-play", "speech-dispatcher", "parec", "pw-record", "pw-cat"}


def _goertzel_coeffs(win, bands):
    return [2 * math.cos(2 * math.pi * round(win * f / RATE) / win) for f in bands]


def _streams(kind):
    try:
        out = subprocess.run(["pactl", "-f", "json", "list", kind], capture_output=True, text=True,
                             timeout=3).stdout
        return json.loads(out or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def _app(p):
    return _pretty(p.get("application.name") or p.get("application.process.binary"))


def _ours(p):
    return (p.get("application.name") == CLIENT or "peak detect" in (p.get("media.name") or "").lower()
            or p.get("application.process.binary") in _IGNORE_BIN or p.get("media.role") == "event")


class AudioWatch:
    def __init__(self, on_change, enabled=lambda: True):
        self.on_change, self.enabled = on_change, enabled
        self.outputs = []          # apps reproduciendo (sin pausar)
        self.mic = []              # apps grabando del micrófono
        self.call = None           # app en llamada (micrófono + altavoz)
        self.call_since = None
        self.levels = None         # [0..1] por banda, o None si no se está midiendo
        self.level = 0.0           # nivel general 0..1
        self.loud_at = 0.0         # última vez que sonó algo audible
        self._proc = None
        self._peak = 0.02
        self._bpeak = {}
        self._coef = _goertzel_coeffs(WIN, BANDS)
        self._coef_d = _goertzel_coeffs(WIN_D, BANDS_D)
        self.detail_until = 0.0    # hasta cuándo calcular el espectro detallado
        self._lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    @property
    def audible(self):
        """Suena algo de verdad (no solo un flujo abierto en silencio)."""
        return bool(self.outputs) and time.monotonic() - self.loud_at < 1.5

    # ── qué apps suenan (cada 1,5 s) ──
    def _loop(self):
        while True:
            if self.enabled():
                outs = sorted({_app(s.get("properties", {})) for s in _streams("sink-inputs")
                               if not s.get("corked") and not _ours(s.get("properties", {}))})
                mic = []
                for s in _streams("source-outputs"):
                    p = s.get("properties", {})
                    if s.get("corked") or _ours(p) or p.get("stream.capture.sink") == "true" or \
                            str(p.get("target.object", "")).endswith(".monitor"):
                        continue
                    mic.append(_app(p))
                mic = sorted(set(mic))
                both = [a for a in mic if a in outs]
                call = both[0] if both else None
            else:
                outs, mic, call = [], [], None
            GLib.idle_add(self._apply, outs, mic, call)
            with self._lock:
                want = bool(outs)
                if want and self._proc is None:
                    self._start_meter()
                elif not want and self._proc is not None:
                    self._stop_meter()
            time.sleep(1.5)

    def _apply(self, outs, mic, call):
        if call != self.call:
            self.call_since = time.monotonic() if call else None
        changed = (outs, mic, call) != (self.outputs, self.mic, self.call)
        self.outputs, self.mic, self.call = outs, mic, call
        if changed:
            self.on_change()
        return False

    # ── medidor ──
    def _start_meter(self):
        try:
            sink = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True,
                                  timeout=3).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            sink = ""
        if not sink or not GLib.find_program_in_path("parec"):
            return
        argv = tied(["parec", "-d", sink + ".monitor", "--rate", str(RATE), "--channels", "1",
                     "--format", "s16le", "--latency-msec", "50", "--client-name", CLIENT,
                     "--stream-name", "isla peak detect"])
        try:
            self._proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            self._proc = None
            return
        threading.Thread(target=self._read, args=(self._proc,), daemon=True).start()

    def _stop_meter(self):
        p, self._proc = self._proc, None
        if p:
            p.terminate()
        self.levels, self.level = None, 0.0

    def _read(self, proc):
        size = CHUNK * 2
        while proc is self._proc:
            data = proc.stdout.read(size)
            if not data or len(data) < size:
                break
            x = array.array("h", data)
            self._analyze(x)
        if proc is self._proc:          # parec murió solo: se reintentará en la próxima vuelta
            with self._lock:
                self._proc = None
            self.levels, self.level = None, 0.0

    def _analyze(self, x):
        n = len(x)
        rms = math.sqrt(sum(v * v for v in x) / n) / 32768
        detail = time.monotonic() < self.detail_until
        win, coefs = (WIN_D, self._coef_d) if detail else (WIN, self._coef)
        w = x[-win:]
        mags = []
        for c in coefs:
            s1 = s2 = 0.0
            for v in w:
                s0 = v + c * s1 - s2
                s2, s1 = s1, s0
            mags.append(math.sqrt(max(0.0, s1 * s1 + s2 * s2 - c * s1 * s2)) / (win * 32768))
        # ganancia automática por banda (cada barra usa su propio techo, que decae despacio)
        # y una general, para que una canción suave no se vea igual de alta que una fuerte
        self._peak = max(rms, self._peak * 0.995, 0.01)
        loud = min(1.0, rms / self._peak * 1.15)
        out = []
        peaks = self._bpeak.setdefault(len(mags), [0.01] * len(mags))
        for i, m in enumerate(mags):
            peaks[i] = max(m, peaks[i] * 0.985, 0.002)
            out.append(min(1.0, (m / peaks[i]) ** 0.8 * (0.35 + 0.65 * loud)) if rms > 0.002 else 0.0)
        self.levels = out
        self.level = loud if rms > 0.002 else 0.0
        if rms > 0.004:
            self.loud_at = time.monotonic()
