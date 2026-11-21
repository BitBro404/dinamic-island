"""Registro de páginas de la isla.

Cada página es una clase «mixin» con un diccionario PAGES:
    PAGES = {"nombre": page("_build_x", "_fill_x", ("datos",), "_open_x")}
  build  método que construye y devuelve el widget de la página
  fill   (opcional) método que la rellena cuando cambian los datos vigilados
  watch  claves de Core.ver que, al cambiar, vuelven a llamar a fill
  open   (opcional) método que se llama al entrar en la página
Para agregar una página nueva basta con crear su archivo en pages/ y sumarla a pages/__init__.py.
"""


def page(build, fill=None, watch=(), open=None):
    return {"build": build, "fill": fill, "watch": tuple(watch), "open": open}


# Funciones que se pueden activar o desactivar desde la página «Más» (en orden de registro).
FEATURES = []


def feature(key, title, desc):
    """Registra una función activable. Core.feature(key) dice si está activada."""
    FEATURES.append({"key": key, "title": title, "desc": desc})


def tool(icon_name, text, tip, target, feature=None):
    """Un acceso en la cuadrícula «Herramientas» de la página «Más».
    Se declara en la clase de la página: TOOLS = (tool(...),)"""
    return {"icon": icon_name, "text": text, "tip": tip, "page": target, "feature": feature}
