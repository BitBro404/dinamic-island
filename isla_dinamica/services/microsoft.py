"""Clasificación de avisos de Teams y Outlook."""
from ..common import *  # noqa: F401,F403


_ORIGIN_LINE = re.compile(r"^\s*[\w.-]+\.(?:com|net|org|io|us)\s*$", re.I)


def ms_kind(n):
    """¿Esta notificación viene de Teams o de Outlook? (llegan desde Chrome / sus PWA)."""
    text = " ".join((n.get("app", ""), n.get("desktop", ""), n.get("summary", ""), n.get("body", ""))).lower()
    if "ompifgpmddkgmclendfeacglnodjjndh" in text or "teams" in text:
        return "teams"
    if "outlook" in text or "office.com" in text or "office365" in text:
        return "outlook"
    return None


def clean_body(body):
    """Quita la línea con el dominio (p. ej. «teams.microsoft.com») que Chrome agrega al texto."""
    lines = [ln for ln in (body or "").splitlines() if ln.strip() and not _ORIGIN_LINE.match(ln)]
    return "\n".join(lines)
