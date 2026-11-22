"""`isla-dinamica --doctor`: informe de texto con el escritorio detectado y el método de cada función."""


def report(desktop, tools, features, window):
    """features: [(título, [Method…])]. Devuelve el informe como texto."""
    from .chain import pick
    lines = ["Isla dinámica — diagnóstico", "",
             f"Escritorio: {desktop.label}" + (" (protocolos wlroots)" if desktop.wlr else ""),
             f"Ventana: {window}", ""]
    width = max((len(t) for t, _m in features), default=10) + 3
    for title, methods in features:
        m = pick(methods, tools, desktop)
        if m:
            state = m.name
        else:
            hints = []
            for x in methods:
                if x.hint and x.hint not in hints:
                    hints.append(x.hint)
            state = "no disponible" + (f" — instala uno de: {', '.join(hints[:4])}" if hints else "")
        lines.append(f"  {title.ljust(width, '.')} {state}")
    return "\n".join(lines) + "\n"


def all_features():
    """Las cadenas de todas las funciones dependientes del escritorio (se llenan en platform/*)."""
    from . import features
    return features.ALL
