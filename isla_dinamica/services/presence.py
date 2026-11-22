"""Sensor de presencia: si no hay nadie frente a la cámara ni teclado/ratón, bloquear y apagar la pantalla."""
import os
import threading
import time

from gi.repository import GLib, Gio

from ..platform.idle import IdleWatch  # noqa: F401  (se reexporta: tests y Presence la usan desde aquí)
from ..util.proc import dbg

CHECK_EVERY = 10          # segundos entre revisiones de la cámara mientras estás inactivo
_HELD = ("paused", "off_hours")


def _minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def in_schedule(dt, start="08:00", end="18:00", days=(0, 1, 2, 3, 4)):
    """¿Está dt (hora local) dentro de la franja? days: 0 = lunes … 6 = domingo. start == end → todo el día.
    Si la franja cruza la medianoche, la madrugada pertenece al día en que empezó."""
    s, e, now = _minutes(start), _minutes(end), dt.hour * 60 + dt.minute
    wd = dt.weekday()
    if s == e:
        return wd in days
    if s < e:
        return wd in days and s <= now < e
    if now >= s:
        return wd in days
    return now < e and (wd - 1) % 7 in days


_LABELS = {"off": "Apagado", "no_cv": "Sin OpenCV", "off_hours": "Fuera de horario", "paused": "En pausa",
           "active": "Vigilando", "watching": "Vigilando", "present": "Te ve", "warning": "Bloqueando",
           "locked": "Bloqueado", "lock_failed": "No se pudo bloquear"}
LOCK_FAILED = "No se pudo bloquear la sesión: la pantalla sigue encendida"


def presence_label(state):
    """Texto corto del estado (casilla rápida y página)."""
    return _LABELS.get(state, "")


class PresenceLogic:
    """Decide cuándo avisar y bloquear. Sin hilos ni cámara: los tiempos llegan como argumento."""

    def __init__(self, minutes=5, warn=30, check_after=60):
        self.minutes, self.warn, self.check_after = minutes, warn, check_after
        self.idle_since = None        # sin input desde (None = hay input)
        self.ok_at = float("-inf")    # última vez que «todo bien» (pausa, fuera de horario)
        self.last_face = float("-inf")
        self.last_check = float("-inf")
        self.seen = False
        self.paused = 0
        self.locked = False
        self.state = "active"

    # ── eventos ──
    def input_idle(self, now):
        self.idle_since = now - self.check_after

    def input_active(self, now):
        self.idle_since, self.locked, self.seen = None, False, False

    def face(self, now, seen, busy=False):
        self.last_check = now
        self.seen = bool(seen or busy)
        if self.seen:
            self.last_face = now

    def pause_until(self, ts):
        self.paused = ts

    # ── estado ──
    def _absent_from(self):
        return max(self.idle_since, self.ok_at, self.last_face)

    def step(self, now, scheduled=True):
        if self.paused > now or not scheduled:
            self.ok_at = now
            self.state = "paused" if self.paused > now else "off_hours"
            return self.state
        if self.state in _HELD:
            self.ok_at = now
        if self.locked:
            self.state = "locked"
        elif self.idle_since is None:
            self.state = "active"
        else:
            gone = now - self._absent_from()
            if gone >= self.minutes * 60:
                self.locked = True
                self.state = "lock"
            elif gone >= self.minutes * 60 - self.warn:
                self.state = "warning"
            else:
                self.state = "present" if self.seen else "watching"
        return self.state

    def needs_check(self, now):
        return self.state in ("watching", "present", "warning") and now - self.last_check >= CHECK_EVERY

    def seconds_left(self, now):
        if self.idle_since is None or self.locked or self.state in _HELD:
            return None
        return max(0, self.minutes * 60 - (now - self._absent_from()))


class FaceDetector:
    """¿Hay una cara frente a la cámara? Todo en memoria: ninguna imagen se guarda.
    detect() → True / False, o None si no se puede saber (sin OpenCV, cámara ocupada o con error)."""
    CASCADES = "/usr/share/opencv4/haarcascades"
    YUNET = os.path.expanduser("~/.local/share/isla-dinamica/face_detection_yunet.onnx")
    INSTALL = "Instala OpenCV: sudo apt install python3-opencv opencv-data"
    FRAMES, WARMUP = 4, 5

    def __init__(self, device=0, cascade_dir=CASCADES):
        self.device, self.cascade_dir = device, cascade_dir
        self.cv, self.haar, self.yunet, self.error = None, [], None, None

    def available(self):
        if self.cv:
            return True
        try:
            import cv2
        except ImportError:
            self.error = self.INSTALL
            return False
        haar = []
        for name in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
            path = os.path.join(self.cascade_dir, name)
            c = cv2.CascadeClassifier(path) if os.path.exists(path) else None
            if c is not None and not c.empty():
                haar.append(c)
        if not haar:
            self.error = self.INSTALL
            return False
        if os.path.exists(self.YUNET) and hasattr(cv2, "FaceDetectorYN"):
            try:
                self.yunet = cv2.FaceDetectorYN.create(self.YUNET, "", (320, 240), 0.7)
            except cv2.error:
                self.yunet = None
        self.cv, self.haar, self.error = cv2, haar, None
        return True

    def detect_frame(self, frame):
        cv2 = self.cv
        if self.yunet is not None:
            h, w = frame.shape[:2]
            self.yunet.setInputSize((w, h))
            _n, faces = self.yunet.detect(frame)
            if faces is not None and len(faces):
                return True
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        for i, c in enumerate(self.haar):
            imgs = (gray, cv2.flip(gray, 1)) if i else (gray,)     # perfil: los dos lados
            for img in imgs:
                if len(c.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))):
                    return True
        return False

    def detect(self):
        if not self.available():
            return None
        cv2 = self.cv
        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        try:
            if not cap.isOpened():
                return None
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            got = False
            for i in range(self.WARMUP + self.FRAMES):      # los primeros salen oscuros (autoexposición)
                ok, frame = cap.read()
                if not ok:
                    continue
                got = True
                if i >= self.WARMUP and self.detect_frame(frame):
                    return True
            return False if got else None
        except cv2.error:
            return None
        finally:
            cap.release()


def _session_bus():
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def _platform_action(kind):
    """Acción por defecto: la cadena de `platform/` elige el método según el escritorio."""
    from ..platform.lock import Locker
    from ..platform.screen import Screen

    def action():
        bus = _session_bus()
        if kind == "lock":
            return Locker(bus).lock()
        screen = Screen(bus)
        return screen.off() if kind == "screen_off" else screen.on()
    return action


DEFAULT_ACTIONS = {k: _platform_action(k) for k in ("lock", "screen_off", "screen_on")}


class Presence:
    """Sensor de presencia: une inactividad (swayidle), cámara (FaceDetector), horario y pausa.
    Estados: off, no_cv, off_hours, paused, active, watching, present, warning, locked."""

    def __init__(self, config, on_change, on_lock, enabled, in_call=lambda: False, detector=None,
                 actions=None, start=True, clock=time.monotonic, wall=None, epoch=time.time,
                 camera_busy=None, post=None, desktop=None, bus=None):
        from datetime import datetime
        from .privacy import camera_users
        self.cfg, self.on_change, self.on_lock = config, on_change, on_lock
        self.enabled, self.in_call = enabled, in_call
        self.detector = detector or FaceDetector()
        self.actions = actions or DEFAULT_ACTIONS
        self.clock, self.wall, self.epoch = clock, wall or datetime.now, epoch
        self.camera_busy = camera_busy or (lambda: bool(camera_users()))
        self.post = post or (lambda f: GLib.idle_add(lambda: f() and False))
        self.logic = PresenceLogic()
        self.mutex = threading.RLock()
        self.state, self.error, self.last_seen, self.test_result = "off", None, None, None
        self.screen_off, self._shown, self.idle = False, None, None
        self.lock_failed = False      # el último intento de bloqueo falló (se limpia al volver a usar el equipo)
        self._sync()
        if start:
            self.idle = IdleWatch(self.check_after(), self._idle, self._active, desktop=desktop, bus=bus)
            threading.Thread(target=self._loop, daemon=True).start()

    @property
    def conf(self):
        return self.cfg.data["presence"]

    def check_after(self):
        """Segundos sin input antes de empezar a mirar: deja tiempo a varias revisiones antes del aviso."""
        c = self.conf
        return int(min(60, max(10, c["minutes"] * 60 - c["warn"] - 20)))

    def _sync(self):
        c, lg = self.conf, self.logic
        lg.minutes, lg.warn, lg.check_after = c["minutes"], c["warn"], self.check_after()
        if self.idle and self.idle.after != lg.check_after:
            self.idle.set_after(lg.check_after)

    # ── eventos de inactividad (llegan desde el hilo de swayidle) ──
    def _idle(self, now):
        with self.mutex:
            self._sync()
            self.logic.input_idle(now)

    def _active(self, now):
        with self.mutex:
            self.logic.input_active(now)
            was_off, self.screen_off = self.screen_off, False
            self.lock_failed = False
        if was_off:
            self.actions["screen_on"]()
        self._notify()

    # ── bucle ──
    def _loop(self):
        while True:
            try:
                self._tick()
            except Exception as e:       # que un fallo raro no mate el sensor
                dbg("presence", e)
            time.sleep(1)

    def _tick(self):
        now = self.clock()
        with self.mutex:
            self._sync()
            lg = self.logic
            c = self.conf
            if not self.enabled() or not self.detector.available():
                # apagado o sin OpenCV: al volver a funcionar, empezar a contar desde cero
                lg.ok_at = now
                if self.enabled():
                    self.state, self.error = "no_cv", self.detector.error
                else:
                    self.state = "off"
            else:
                self.error = None
                lg.pause_until(now + 1 if self.epoch() < c["paused_until"] else 0)
                st = lg.step(now, in_schedule(self.wall(), c["start"], c["end"], c["days"]))
                if lg.needs_check(now):
                    busy = self.in_call() or self.camera_busy()
                    seen = None if busy else self.detector.detect()
                    # sin datos (llamada, cámara ocupada o con error) = presente: nunca bloquear a ciegas
                    lg.face(now, bool(seen), busy=seen is None)
                    if seen:
                        self.last_seen = self.epoch()
                    st = lg.step(now)
                if st == "lock":
                    st = "locked"
                    if self.actions["lock"]():
                        self.screen_off = True
                        self.actions["screen_off"]()
                    else:
                        # sin bloqueo, apagar la pantalla dejaría la sesión abierta a oscuras: no se apaga
                        self.lock_failed = True
                    self.post(self.on_lock)
                if self.lock_failed and st == "locked":
                    st, self.error = "lock_failed", LOCK_FAILED
                self.state = st
        self._notify()

    def _notify(self):
        left = self.seconds_left()
        key = (self.state, None if left is None else int(left), self.error)
        if key != self._shown:
            self._shown = key
            self.post(self.on_change)

    def seconds_left(self):
        if self.state not in ("watching", "present", "warning"):
            return None
        return self.logic.seconds_left(self.clock())

    # ── acciones de la interfaz ──
    def _set_pause(self, until):
        self.conf["paused_until"] = until
        try:
            self.cfg.save()
        except OSError:
            pass
        self._notify()

    def set_conf(self, key, value):
        """Cambia un ajuste si es válido (mismas reglas que al cargar config.json) y lo guarda."""
        from ..config import _PRESENCE_OK
        if key not in _PRESENCE_OK or not _PRESENCE_OK[key](value):
            return False
        if self.conf.get(key) != value:
            self.conf[key] = value
            try:
                self.cfg.save()
            except OSError:
                pass
            self._shown = None
            self._notify()
        return True

    def pause(self, secs):
        self._set_pause(self.epoch() + secs)

    def pause_tomorrow(self):
        from datetime import datetime, timedelta
        t = datetime.fromtimestamp(self.epoch()) + timedelta(days=1)
        self._set_pause(t.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    def resume(self):
        self._set_pause(0)

    @property
    def paused_until(self):
        return self.conf["paused_until"]

    def check_now(self):
        """Prueba la cámara una vez (botón «Probar ahora»), en otro hilo."""
        def work():
            if self.camera_busy():
                res = "La cámara la está usando otra app"
            else:
                seen = self.detector.detect()
                res = {True: "Te veo", False: "No veo a nadie"}.get(seen, self.detector.error or
                                                                    "No se pudo usar la cámara")
                if seen:
                    self.last_seen = self.epoch()
            self.test_result = res
            self.post(self.on_change)
        self.test_result = "Mirando…"
        threading.Thread(target=work, daemon=True).start()
