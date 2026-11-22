"""Qué monitor es el principal (función pura: recibe las esquinas de los monitores)."""


def primary_index(origins, primary=None):
    """Índice del monitor principal entre `origins` [(x, y)…]: el que declara el sistema (`primary`), y si no
    declara ninguno (labwc), el de más arriba a la izquierda. None si no hay monitores."""
    if not origins:
        return None
    if primary is not None and 0 <= primary < len(origins):
        return primary
    return min(range(len(origins)), key=lambda i: (origins[i][0] + origins[i][1], origins[i][1]))
