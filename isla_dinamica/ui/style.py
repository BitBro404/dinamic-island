"""Estilo de la isla: tamaños de la píldora y la hoja CSS (colores, tipos de letra, botones)."""


H = 34            # alto de la píldora compacta


W_EXP = 460       # ancho de la isla expandida


W_CARD = 420      # ancho de las tarjetas de aviso


GAP = 6           # separación con el borde de la pantalla


BUB_GAP = 6       # separación entre la píldora y las burbujas de actividades


BUB_MAX = 2       # burbujas como máximo


DRAG_MIN = 8      # píxeles que hay que mover el ratón para empezar a arrastrar


CSS = b"""
window { background: transparent; }
* { color: #f5f5f7; font-family: "Inter", "Cantarell", sans-serif; }
.c-text { font-weight: 600; font-size: 13px; }
.c-time { font-weight: 600; font-size: 13px; color: rgba(255,255,255,0.55); }
.dim { color: #8e8e93; font-size: 12px; }
.bub-count { font-weight: 700; font-size: 12px; color: #ffffff; }
.small { font-size: 11px; }
.title { font-weight: 700; font-size: 15px; }
.subtitle { font-weight: 600; font-size: 13px; }
.artist { color: #a1a1a6; font-size: 13px; }
.bigclock { font-weight: 700; font-size: 30px; }
.huge { font-weight: 700; font-size: 36px; font-feature-settings: "tnum"; }
.time-small { color: #8e8e93; font-size: 11px; }
.orange { color: #ff9f0a; }
.green { color: #30d158; }
.red { color: #ff453a; }
.blue { color: #0a84ff; }

button { background: none; background-image: none; border: none; box-shadow: none;
         text-shadow: none; outline: none; }
button.ctrl { min-width: 36px; min-height: 36px; padding: 0; border-radius: 18px; }
button.ctrl:hover, button.act:hover, button.row:hover, button.link:hover { background: rgba(255,255,255,0.10); }
button.chip { background: rgba(255,255,255,0.10); border-radius: 14px; padding: 3px 12px; min-height: 0; }
button.chip:hover { background: rgba(255,255,255,0.22); }
button.chip label { font-weight: 600; font-size: 12px; }
button.chip.danger label { color: #ff453a; }
button.chip.on { background: #0a84ff; }
button.spec { background: transparent; border: none; box-shadow: none; padding: 0; min-height: 0; }
button.spec:hover { background: rgba(255,255,255,0.04); }
button.chip.on label { color: white; }
button.tile { min-width: 44px; min-height: 44px; padding: 0; border-radius: 22px;
              background: rgba(255,255,255,0.12); }
button.tile:hover { background: rgba(255,255,255,0.22); }
button.tile.on { background: #0a84ff; }
button.tile.on:hover { background: #3d9bff; }
button.link { padding: 1px 6px; border-radius: 8px; min-height: 0; }
button.link label { font-size: 11px; font-weight: 600; }
button.act { min-width: 49px; min-height: 46px; padding: 2px 0; border-radius: 12px;
             background: rgba(255,255,255,0.07); }
button.sechead { padding: 2px 4px; border-radius: 8px; min-height: 0; }
button.sechead:hover { background: rgba(255,255,255,0.08); }
.badge.new { background: #0a84ff; color: white; padding: 0 6px; }
button.row { padding: 6px 8px; border-radius: 10px; }
button.big { min-width: 70px; min-height: 64px; border-radius: 16px; background: rgba(255,255,255,0.08); padding: 4px; }
button.big:hover { background: rgba(255,255,255,0.18); }
button.big.confirm { background: #ff453a; }
.badge { background: #ff453a; border-radius: 8px; min-width: 16px; min-height: 16px;
         font-size: 10px; font-weight: 700; padding: 0 3px; }
levelbar trough { min-height: 4px; border: none; border-radius: 2px; background: rgba(255,255,255,0.18); padding: 0; }
levelbar block.filled { border: none; border-radius: 2px; background: #f5f5f7; }
levelbar block.empty { border: none; background: transparent; }
scale trough { min-height: 6px; border-radius: 3px; background: rgba(255,255,255,0.18); border: none; }
scale highlight { background: #f5f5f7; border-radius: 3px; border: none; }
scale slider { min-width: 14px; min-height: 14px; border-radius: 7px; background: #f5f5f7; border: none; box-shadow: none; }
entry { background: rgba(255,255,255,0.10); border: none; border-radius: 10px; padding: 4px 10px; box-shadow: none; }
scrolledwindow, viewport { background: transparent; border: none; }
spinbutton { background: rgba(255,255,255,0.10); border: none; border-radius: 10px; box-shadow: none; min-height: 0; }
spinbutton entry { background: transparent; min-width: 30px; min-height: 0; padding: 2px 6px; }
spinbutton button { border-radius: 10px; min-width: 20px; min-height: 20px; padding: 0 3px; }
spinbutton button:hover { background: rgba(255,255,255,0.15); }
button.wlink { padding: 0 4px; border-radius: 8px; min-height: 0; }
button.wlink:hover { background: rgba(255,255,255,0.10); }
button.close { min-width: 24px; min-height: 24px; padding: 0; border-radius: 12px; background: rgba(255,255,255,0.10); }
button.close:hover { background: rgba(255,255,255,0.25); }
.hour { font-size: 11px; color: #a1a1a6; }
.wtile { background: rgba(255,255,255,0.07); border-radius: 12px; padding: 6px 10px; }
.wtile-v { font-weight: 600; font-size: 13px; }
.pop { color: #64d2ff; font-size: 11px; font-weight: 600; }
.section { color: #8e8e93; font-size: 11px; font-weight: 700; }
button.work { background: rgba(255,255,255,0.07); border-radius: 12px; padding: 5px 10px; min-height: 0; }
button.work:hover { background: rgba(255,255,255,0.16); }
.cmd { font-family: monospace; font-size: 12px; background: rgba(255,255,255,0.08); border-radius: 8px;
       padding: 4px 8px; }
"""


ACCENTS = ("orange", "green", "red", "blue")
