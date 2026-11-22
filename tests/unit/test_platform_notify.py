"""U2: avisos de cualquier servidor de notificaciones y «No molestar» por escritorio."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gi.repository import GLib  # noqa: E402

from isla_dinamica.platform import dnd  # noqa: E402
from isla_dinamica.platform.chain import Method, Tools, pick  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.platform.notify import SOURCES, parse_notify  # noqa: E402
from isla_dinamica.services.notifications import Notifications  # noqa: E402

KDE = detect({"XDG_CURRENT_DESKTOP": "KDE", "XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w"})


def tools(cmds=(), names=(), schemas=(), server=""):
    return Tools(which=lambda c: c if c in cmds else None, has_name=lambda n: n in names,
                 has_schema=lambda s: s in schemas, notif_server=lambda: server)


class ParseNotifyTest(unittest.TestCase):
    def test_fields(self):
        n = parse_notify("Microsoft Teams", 7, "", "<b>Ana</b>", "¿Subiste el fix?",
                         {"desktop-entry": "chrome-teams", "urgency": 2}, now=100.0)
        self.assertEqual((n["id"], n["app"], n["summary"], n["body"], n["desktop"], n["urgent"], n["time"]),
                         (7, "Microsoft Teams", "Ana", "¿Subiste el fix?", "chrome-teams", True, 100.0))

    def test_defaults(self):
        n = parse_notify("", 0, "", "Hola", "", {}, now=1.0)
        self.assertEqual(n["app"], "Sistema")
        self.assertEqual(n["icon"], "preferences-system-notifications-symbolic")
        self.assertFalse(n["urgent"])

    def test_file_icon_becomes_image_path(self):
        seen = []
        parse_notify("App", 1, "file:///tmp/x.png", "s", "b", {}, now=1.0,
                     load_file=lambda p: seen.append(p))
        self.assertEqual(seen, ["/tmp/x.png"])


class SourceChainTest(unittest.TestCase):
    def test_budgie_dispatcher_when_present(self):
        self.assertEqual(pick(SOURCES, tools(names={"org.budgie_desktop.Notifications"}), KDE).name,
                         "Budgie (Dispatcher)")

    def test_generic_monitor_everywhere_else(self):
        self.assertEqual(pick(SOURCES, tools(), KDE).name, "D-Bus (cualquier servidor)")


class DndChainTest(unittest.TestCase):
    def name(self, **kw):
        m = pick(dnd.METHODS, tools(**kw), KDE)
        return m.name if m else None

    def test_by_server(self):
        self.assertEqual(self.name(names={"org.budgie_desktop.Notifications"}), "Budgie")
        self.assertEqual(self.name(server="gnome-shell", schemas={"org.gnome.desktop.notifications"}), "GNOME")
        self.assertEqual(self.name(server="plasma"), "KDE Plasma")
        self.assertEqual(self.name(server="cinnamon", schemas={"org.cinnamon.desktop.notifications"}), "Cinnamon")
        self.assertEqual(self.name(server="xfce4-notifyd", cmds={"xfconf-query"}), "XFCE")
        self.assertEqual(self.name(server="mako", cmds={"makoctl"}), "mako")
        self.assertEqual(self.name(server="swaync", cmds={"swaync-client"}), "SwayNC")
        self.assertEqual(self.name(server="dunst", cmds={"dunstctl"}), "dunst")

    def test_none_for_unknown_server(self):
        self.assertIsNone(self.name(server="lxqt-notificationd"))

    def test_command_outputs(self):
        self.assertTrue(dnd.parse_mako("default\ndo-not-disturb\n"))
        self.assertFalse(dnd.parse_mako("default\n"))
        self.assertTrue(dnd.parse_bool("true\n"))
        self.assertFalse(dnd.parse_bool("false"))

    def test_command_backend(self):
        calls = []
        b = dnd.CommandDnd(["dunstctl", "is-paused"], ["dunstctl", "set-paused", "toggle"], dnd.parse_bool,
                           run=lambda argv: calls.append(argv) or "true")
        self.assertTrue(b.get())
        b.toggle()
        self.assertEqual(calls[-1], ["dunstctl", "set-paused", "toggle"])

    def test_gsettings_backend_inverts_show_banners(self):
        store = {"show-banners": True}
        b = dnd.SettingsDnd("org.gnome.desktop.notifications", "show-banners", invert=True,
                            settings=FakeSettings(store))
        self.assertFalse(b.get())
        b.toggle()
        self.assertEqual(store["show-banners"], False)
        self.assertTrue(b.get())


class FakeSettings:
    def __init__(self, store):
        self.store = store

    def get_boolean(self, k):
        return self.store[k]

    def set_boolean(self, k, v):
        self.store[k] = v

    def connect(self, *_a):
        pass


class FakeBus:
    """Sólo lo que el servicio y los métodos de Budgie usan del bus."""

    def __init__(self, dnd_value=False):
        self.dnd_value, self.subscriptions, self.calls = dnd_value, [], []

    def signal_subscribe(self, *args):
        self.subscriptions.append(args)

    def call(self, *args):
        self.calls.append(args)

    def call_sync(self, dest, path, iface, method, params, reply_type, *_args):
        self.calls.append((dest, path, iface, method, params))
        return GLib.Variant("(b)", (self.dnd_value,))


class FakeDnd:
    polls = False

    def __init__(self, bus):
        self.bus, self.value, self.calls, self.watcher = bus, False, [], None

    def get(self):
        return self.value

    def toggle(self):
        self.calls.append("toggle")

    def watch(self, cb):
        self.watcher = cb


class NotificationServiceTest(unittest.TestCase):
    def test_budgie_behaviour_is_preserved(self):
        bus = FakeBus(dnd_value=True)
        n = Notifications(bus, lambda _: None, lambda: None, tools=tools(names={
            "org.budgie_desktop.Notifications", "org.budgie_desktop.Raven"}), desktop=KDE,
            sources=SOURCES, dnd_methods=dnd.METHODS, centers=dnd.CENTER)
        self.assertTrue(any("NotificationAdded" in str(sub) for sub in bus.subscriptions))
        self.assertIsInstance(n.dnd_backend, dnd.BudgieDnd)
        self.assertTrue(n.dnd)
        self.assertTrue(n.has_center)
        n.toggle_dnd()
        self.assertTrue(any(call[3] == "ToggleDoNotDisturb" for call in bus.calls))
        n.open_center()
        self.assertTrue(any(call[0] == "org.budgie_desktop.Raven" for call in bus.calls))

    def test_uses_the_chosen_source_dnd_and_center(self):
        bus, got, changed, centers, timers = FakeBus(), [], [], [], []
        backend = FakeDnd(bus)
        backend.polls = True
        source = lambda b, cb: type("S", (), {"cb": cb})()
        n = Notifications(bus, got.append, lambda: changed.append(1), tools=tools(), desktop=KDE,
                          sources=[Method("fake", lambda t, d: True, source)],
                          dnd_methods=[Method("fake dnd", lambda t, d: True, lambda b: backend)],
                          centers=[Method("fake center", lambda t, d: True, lambda b: centers.append(b))],
                          timeout_add=lambda secs, cb: timers.append((secs, cb)) or 7)
        n.source.cb({"summary": "hola"})
        self.assertEqual(got, [{"summary": "hola"}])
        n.toggle_dnd()
        self.assertEqual(backend.calls, ["toggle"])
        n.open_center()
        self.assertEqual(centers, [bus])
        self.assertEqual(timers[0][0], 3)
        backend.value = True
        self.assertTrue(timers[0][1]())
        self.assertTrue(n.dnd)
        self.assertEqual(len(changed), 1)
        backend.value = False
        timers[0][1]()
        self.assertEqual(len(changed), 2)          # avisa también al volver a no molestar

    def test_without_methods_nothing_breaks(self):
        bus = FakeBus()
        n = Notifications(bus, lambda _: None, lambda: None, tools=tools(), desktop=KDE,
                          sources=[], dnd_methods=[], centers=[], timeout_add=lambda *_: 7)
        self.assertIsNone(n.source)
        self.assertFalse(n.supported)
        self.assertFalse(n.has_center)
        n.toggle_dnd()
        n.open_center()
        self.assertEqual(bus.calls, [])


if __name__ == "__main__":
    unittest.main()
