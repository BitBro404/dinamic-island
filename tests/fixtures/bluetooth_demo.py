"""Dispositivo Bluetooth falso para el arnés: BT_NAME, BT_BATTERY (none o entero) y BT_ICON.

Uso: python3 tests/harness.py pill --setup tests/fixtures/bluetooth_demo.py --out /tmp/opencode/isla-bt
Con BT_DEBUG=1 imprime una vez el tooltip de las burbujas calculadas.
"""
import os

from isla_dinamica.ui.bubbles import bubble_tip


def setup(core):
    core.config.save = lambda: None
    core.config.data["features"]["bt_bubble"] = True

    name = os.environ.get("BT_NAME", "Auriculares")
    raw = os.environ.get("BT_BATTERY", "82")
    battery = None if raw.lower() in ("none", "") else int(raw)
    connected = os.environ.get("BT_CONNECTED", "1") != "0"
    fake = {"/dev/fake": {"path": "/dev/fake", "name": name, "connected": connected,
                          "icon": os.environ.get("BT_ICON", "audio-headphones-symbolic"),
                          "battery": battery}}
    core.bt.devices = fake
    core.bt.powered, core.bt.adapter = True, "/org/bluez/hci0"
    core.bt.refresh = lambda: None          # BlueZ real no sobrescribe el dispositivo falso
    # la primera lectura asíncrona de GetManagedObjects llega después de setup() y asigna self.devices
    original_on_change = core.bt.on_change

    def keep_fake():
        core.bt.devices = fake
        original_on_change()

    core.bt.on_change = keep_fake

    if os.environ.get("BT_DEBUG") == "1":
        original, seen = core.refresh, set()

        def debug_refresh():
            original()
            windows = list(core.windows.values())
            tips = tuple(bubble_tip(a) for a in windows[0].bubbles) if windows else ()
            if tips and tips not in seen:
                seen.add(tips)
                print("BT_BUBBLE_TIPS:", tips, flush=True)
            return False
        core.refresh = debug_refresh
