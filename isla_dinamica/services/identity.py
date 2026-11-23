"""Identidad facial para el sensor de presencia: modelos, galería local y decisión.

Solo se guardan vectores de rasgos (embeddings) en un archivo privado; nunca imágenes.
Los modelos vienen de OpenCV Zoo (Apache-2.0) y se verifican por tamaño y SHA-256.
"""
import hashlib
import json
import math
import os
import random
import time
import urllib.request
from datetime import datetime, timedelta

MODEL_DIR = os.path.expanduser("~/.local/share/isla-dinamica/models")
TEMPLATE_DIR = os.path.expanduser("~/.config/isla-dinamica/identity")
ME = 0.363             # similitud cosine a partir de la cual es «yo» (referencia OpenCV Zoo)
DOUBT = 0.25           # por debajo de esto es «otra persona»; entre medias se pregunta
MAX_ROTATING = 5       # muestras nuevas además de la plantilla ancla
RECENT_INPUT = 60      # segundos de actividad reciente para preguntar
PROMPT_TIMEOUT = 20    # segundos que espera la respuesta «¿eras tú?»
MODELS = {
    "yunet": ("face_detection_yunet_2023mar.onnx", 232589,
              "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
              "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
              "face_detection_yunet/face_detection_yunet_2023mar.onnx"),
    "sface": ("face_recognition_sface_2021dec.onnx", 38696353,
              "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
              "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
              "face_recognition_sface/face_recognition_sface_2021dec.onnx"),
}


class ModelError(Exception):
    """Un modelo no se pudo descargar o no coincide con lo esperado."""


def _hhmm(text):
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def next_sample_time(now, start="08:00", end="18:00", days=(0, 1, 2, 3, 4), rand=None):
    """Próxima hora aleatoria (datetime) dentro del horario, posterior a `now` y en día laborable."""
    rand = rand or random.random
    s, e = _hhmm(start), _hhmm(end)
    for delta in range(8):                       # una semana vista basta aunque no haya días válidos
        day = now.date() + timedelta(days=delta)
        if day.weekday() not in days:
            continue
        lo, hi = (0, 1440) if s == e else ((s, e) if s < e else (s, 1440 + e))
        when = datetime(day.year, day.month, day.day) + timedelta(minutes=lo + rand() * (hi - lo))
        if when > now:
            return when
    return now + timedelta(days=1)               # configuración sin días válidos: no preguntar muy a menudo


def _fetch(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def _valid(path, size, sha):
    try:
        if os.path.getsize(path) != size:
            return False
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest() == sha
    except OSError:
        return False


def _write_private(path, data):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, path)


def ensure_models(fetch=None, directory=None, models=None):
    """Descarga los modelos que falten y devuelve {clave: ruta}. Inyectable para pruebas."""
    fetch, directory, models = fetch or _fetch, directory or MODEL_DIR, models or MODELS
    os.makedirs(directory, mode=0o700, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    paths = {}
    for key, (name, size, sha, url) in models.items():
        path = os.path.join(directory, name)
        if _valid(path, size, sha):
            paths[key] = path
            continue
        try:
            data = fetch(url)
        except Exception as e:
            raise ModelError(f"No se pudo descargar {name}: {e}") from e
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
            raise ModelError(f"{name} no pasó la verificación")
        _write_private(path, data)
        paths[key] = path
    return paths


def _vector(value):
    """Lista de floats finitos, o None. Acepta listas y arrays de NumPy."""
    try:
        v = [float(x) for x in value]
    except (TypeError, ValueError):
        return None
    return v if v and all(math.isfinite(x) for x in v) else None


class Gallery:
    """Plantilla ancla + muestras rotativas. Solo vectores, nunca imágenes."""

    def __init__(self, path=None):
        self.path = path or os.path.join(TEMPLATE_DIR, "gallery.json")
        self.anchor, self.samples, self._next = None, [], 0.0
        self._load()

    @property
    def enrolled(self):
        return self.anchor is not None

    @property
    def templates(self):
        return [self.anchor] + [s["embedding"] for s in self.samples] if self.enrolled else []

    @property
    def next_sample_at(self):
        return self._next

    @next_sample_at.setter
    def next_sample_at(self, ts):
        self._next = float(ts)
        self._save()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(data, dict) or data.get("version") != 1:
            return
        try:
            self._next = float(data.get("next_sample_at", 0) or 0)
        except (TypeError, ValueError):
            self._next = 0.0
        anchor = _vector(data.get("anchor"))
        if not anchor:
            return
        samples = []
        raw = data.get("samples")
        for s in raw if isinstance(raw, list) else []:
            if not isinstance(s, dict):
                continue
            v = _vector(s.get("embedding"))
            if not v:
                continue
            try:
                when = float(s.get("when", 0))
            except (TypeError, ValueError):
                when = 0.0
            samples.append({"embedding": v, "when": when})
        self.anchor, self.samples = anchor, samples[-MAX_ROTATING:]

    def _save(self):
        directory = os.path.dirname(self.path)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass
        data = {"version": 1, "anchor": self.anchor, "samples": self.samples,
                "next_sample_at": self._next}
        _write_private(self.path, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def add(self, feature, when=None):
        """Añade una muestra. La primera es el ancla; el resto rota con límite."""
        v = _vector(feature)
        if not v:
            return False
        if self.enrolled:
            self.samples.append({"embedding": v, "when": float(when or time.time())})
            self.samples = self.samples[-MAX_ROTATING:]
        else:
            self.anchor = v
        self._save()
        return True

    def clear(self):
        self.anchor, self.samples, self._next = None, [], 0.0
        try:
            os.unlink(self.path)
        except OSError:
            pass


class IdentityVerifier:
    """Compara embeddings con la galería. `unknown` equivale a duda: nunca bloquea."""

    def __init__(self, gallery, recognizer=None, me=ME, doubt=DOUBT):
        self.gallery, self._recognizer = gallery, recognizer
        self.me, self.doubt, self.error = me, doubt, None

    @property
    def recognizer(self):
        if self._recognizer is None:
            path = os.path.join(MODEL_DIR, MODELS["sface"][0])
            if not _valid(path, MODELS["sface"][1], MODELS["sface"][2]):
                self.error = "Faltan los modelos: registra tu rostro para descargarlos"
                return None
            try:
                import cv2
                self._recognizer = cv2.FaceRecognizerSF.create(path, "", backend_id=0, target_id=0)
            except Exception as e:
                self.error = str(e)
        return self._recognizer

    def available(self):
        return self.recognizer is not None and self.gallery.enrolled

    def has_recognizer(self):
        return self._recognizer is not None

    def inspect(self, frame, faces):
        """Devuelve (etiqueta, mejor embedding). Sin datos o con error → unknown."""
        rec = self.recognizer
        if not self.available() or not faces:
            return "unknown", None
        try:
            templates = self.gallery.templates
            best_score, best_feature = -1.0, None
            for face in faces:
                feature = rec.feature(rec.alignCrop(frame, face))
                score = max(float(rec.match(feature, t, 0)) for t in templates)
                if score > best_score:
                    best_score, best_feature = score, feature
            if best_feature is None:
                return "unknown", None
            label = "me" if best_score >= self.me else (
                "other" if best_score < self.doubt else "unknown")
            return label, best_feature
        except Exception as e:
            self.error = str(e)
            return "unknown", None

    def verify(self, frame, faces):
        return self.inspect(frame, faces)[0]

    def enroll_feature(self, frame, faces):
        """Embedding de la cara más grande, para registrar una muestra."""
        rec = self.recognizer
        if rec is None or not faces:
            return None
        try:
            face = max(faces, key=lambda f: float(f[2]) * float(f[3]))
            return rec.feature(rec.alignCrop(frame, face))
        except Exception as e:
            self.error = str(e)
            return None


def decide(identity, detected, busy=False, enrolled=False):
    """Traduce el resultado a (seen, busy) para PresenceLogic.face.

    Con duda o sin datos, `busy=True`: la isla se comporta como si hubiera alguien.
    """
    if busy:
        return False, True
    if not enrolled:
        return bool(detected), False
    if identity == "me":
        return True, False
    if identity == "other":
        return False, False
    if identity == "unknown":
        return False, True
    return bool(detected), False
