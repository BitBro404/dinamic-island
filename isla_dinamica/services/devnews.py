"""Novedades de desarrollo sin ver (commits por bajar, PR nuevas): encienden un punto azul en la píldora hasta
que abres GitHub o Proyectos, o hasta que haces pull. Lógica pura, sin GTK."""


class DevNews:
    KINDS = ("behind", "pr")

    def __init__(self, on_change=lambda: None):
        self.on_change = on_change
        self.items = set()            # {(tipo, clave)}: («behind», ruta del repo) o («pr», id de la PR)

    @property
    def pending(self):
        return bool(self.items)

    def count(self, kind=None):
        return sum(1 for k, _ in self.items if kind in (None, k))

    def mark(self, kind, key):
        if (kind, key) not in self.items:
            self.items.add((kind, key))
            self.on_change()

    def seen(self, kind=None):
        """Las ya vistas se apagan (todas, o solo las de un tipo)."""
        left = {i for i in self.items if kind is not None and i[0] != kind}
        if left != self.items:
            self.items = left
            self.on_change()

    def still_behind(self, paths):
        """Tras revisar los repos: los que ya no tienen commits por bajar se apagan solos."""
        left = {i for i in self.items if i[0] != "behind" or i[1] in paths}
        if left != self.items:
            self.items = left
            self.on_change()
