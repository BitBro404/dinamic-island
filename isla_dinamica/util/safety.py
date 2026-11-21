"""Comprobaciones de seguridad: qué URLs, archivos y apps se pueden abrir, y qué se puede registrar.

Ver la fase S de plan.md (S3, S6, S7 y S8)."""
import os
import re
import urllib.parse

from .proc import dbg, open_uri


_LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]", "::1")


def is_safe_web_url(url):
    """¿Se puede abrir `url` en el navegador sin riesgo? Solo https:// (y http:// hacia este equipo).
    Descarta file://, javascript:, esquemas de otras apps y URLs con usuario:contraseña@, porque
    algunas URLs (las de despliegues, por ejemplo) las escriben terceros."""
    if not isinstance(url, str) or url != url.strip():
        return False
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if not u.hostname or u.username or u.password:
        return False
    return u.scheme == "https" or (u.scheme == "http" and u.hostname in _LOCAL_HOSTS)


def open_web(url):
    """Abre una URL web solo si es segura (ver is_safe_web_url). Devuelve si la abrió."""
    if not is_safe_web_url(url):
        dbg("URL descartada por insegura:", repr(url)[:120])
        return False
    open_uri(url)
    return True


# Extensiones que se pueden abrir con un clic: documentos y multimedia sin código ejecutable ni macros.
_SAFE_OPEN_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "heic", "avif",
                  "mp4", "mkv", "webm", "mov", "avi", "mp3", "ogg", "oga", "flac", "wav", "m4a", "opus",
                  "pdf", "txt", "md", "csv", "json", "log",
                  "odt", "ods", "odp", "docx", "xlsx", "pptx", "doc", "xls", "ppt",
                  "zip", "tar", "gz", "xz", "7z", "rar"}


def safe_to_open(name):
    """¿Se puede abrir esta descarga directamente? Lo ejecutable (scripts, .desktop, .exe, AppImage, .deb),
    los documentos con macros y lo desconocido se muestran en la carpeta en lugar de abrirse."""
    ext = os.path.splitext(name or "")[1].lower().lstrip(".")
    return ext in _SAFE_OPEN_EXT


def _norm_app(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def desktop_matches_app(desktop, app):
    """¿El `desktop-entry` de un aviso corresponde a la app que lo envió? El hint lo pone quien envía el
    aviso; sin esta comprobación, cualquier programa podría hacer que un clic lance otra app instalada."""
    entry = _norm_app((desktop or "").removesuffix(".desktop").split(".")[-1])
    name = _norm_app(app)
    return bool(entry and name) and (entry in name or name in entry)


def notif_debug_line(n, kind):
    """Línea de depuración de un aviso SIN su contenido (los mensajes pueden ser privados)."""
    return f"aviso: app={n.get('app')!r} desktop={n.get('desktop')!r} tipo={kind}"
