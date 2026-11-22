/* Extensión provisional: expone a la isla las piezas de GNOME Shell que no ofrece otro medio.
 * La ventana de la isla es un GTK independiente y se coloca con ui/placement.py; aquí solo hay un
 * puente D-Bus. Los métodos son best-effort: si GNOME cambia la API, la isla sigue funcionando con
 * gsettings, portal, swayidle/xset... y `--doctor` lo indica.
 */
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {Extension, gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const BUS_NAME = 'io.github.bitbro404.IslaDinamica.Shell';
const OBJECT_PATH = '/io/github/bitbro404/IslaDinamica/Shell';
const XML = `
<node>
  <interface name="${BUS_NAME}">
    <method name="GetIdletime"><arg type="x" direction="out"/></method>
    <method name="Screenshot">
      <arg name="area" type="s" direction="in"/>
      <arg type="b" direction="out"/>
    </method>
    <method name="Screencast">
      <arg name="path" type="s" direction="in"/>
      <arg name="geometry" type="s" direction="in"/>
      <arg type="b" direction="out"/>
    </method>
    <method name="StopScreencast"/>
    <method name="SetPowerSave"><arg name="on" type="b" direction="in"/></method>
    <method name="ToggleNotificationCenter"/>
  </interface>
</node>`;

export default class IslaDinamicaExtension extends Extension {
    enable() {
        const ext = this;
        this._recorder = null;
        this._impl = {
            GetIdletime() {
                try {
                    return Math.max(0, Math.round(global.get_current_time() - global.get_last_input_time()));
                } catch (e) {
                    return 0;
                }
            },

            Screenshot(area) {
                const picture = GLib.build_filenamev([GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) || GLib.get_home_dir(),
                    `Captura ${new Date().toISOString().replace(/[:.]/g, '-')}.png`]);
                try {
                    return GLib.spawn_command_line_async(`gnome-screenshot -f ${GLib.shell_quote(picture)}`);
                } catch (e) {
                    Main.screenshotUI?.open?.();
                    return false;
                }
            },

            Screencast(path, geometry) {
                try {
                    ext._recorder = Gio.Subprocess.new(
                        ['ffmpeg', '-y', '-f', 'pipewire', '-i', 'default', '-c:v', 'libx264', '-preset', 'veryfast', path],
                        Gio.SubprocessFlags.NONE);
                    return ext._recorder !== null;
                } catch (e) {
                    Main.notify(_('Isla dinámica: no se pudo iniciar la grabación'));
                    return false;
                }
            },

            StopScreencast() {
                if (ext._recorder) {
                    try {
                        ext._recorder.force_exit();
                    } catch (e) {
                        /* ya terminó */
                    }
                    ext._recorder = null;
                }
            },

            SetPowerSave(on) {
                try {
                    const proxy = new Gio.DBusProxy({
                        g_connection: Gio.bus_get_sync(Gio.BusType.SESSION, null),
                        g_name: 'org.gnome.SettingsDaemon.Power',
                        g_object_path: '/org/gnome/SettingsDaemon/Power',
                        g_interface_name: 'org.gnome.SettingsDaemon.Power.Screen',
                        g_flags: Gio.DBusProxyFlags.NONE,
                    });
                    proxy.call_sync('SetPowerSave', new GLib.Variant('(b)', [on]),
                        Gio.DBusCallFlags.NONE, 2000, null);
                } catch (e) {
                    try {
                        GLib.spawn_command_line_async(`xset dpms force ${on ? 'on' : 'off'}`);
                    } catch (ignored) {
                        /* sin forma de apagar la pantalla */
                    }
                }
            },

            ToggleNotificationCenter() {
                if (Main.messageTray?.toggle)
                    Main.messageTray.toggle();
                else
                    Main.panel.statusArea.dateMenu?._indicator?.toggle?.();
            },
        };

        this._exported = Gio.DBusExportedObject.wrapJSObject(XML, this._impl);
        this._owner = Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
            connection => this._exported.export(connection, OBJECT_PATH), null, () => {
                Main.notify(_('Isla dinámica: otro proceso tomó el nombre D-Bus'));
            });
    }

    disable() {
        if (this._owner) {
            Gio.bus_unown_name(this._owner);
            this._owner = null;
        }
        if (this._exported) {
            this._exported.unexport();
            this._exported = null;
        }
        this._impl = null;
        this._recorder = null;
    }
}
