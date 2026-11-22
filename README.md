# Isla dinámica

Una píldora tipo «Dynamic Island» arriba al centro de la pantalla para **cualquier escritorio Linux**
(Wayland o X11). Muestra la música, las llamadas, el temporizador, las descargas, los despliegues y los
avisos. Al pasar el ratón por encima de la píldora se expande en un panel con ajustes rápidos y páginas:
Wi‑Fi, Bluetooth, GitHub, Teams y correo, clima, sistema, presencia y más.

Está hecha en Python 3 + GTK3 (PyGObject). Usa `gtk-layer-shell` cuando el compositor lo admite y,
si no, coloca una ventana X11 con el mismo aspecto; en GNOME puede apoyarse en una extensión
provisional. Las funciones que dependen del escritorio eligen entre varios métodos disponibles: si
ninguno funciona, se ocultan o se marca «No disponible», y `isla-dinamica --doctor` lo explica.

📖 Documentación:
**[docs/DOCUMENTACION.md](docs/DOCUMENTACION.md)** (funciones por nivel de dependencias) y
**[docs/ESCRITORIOS.md](docs/ESCRITORIOS.md)** (qué probar en cada escritorio).

---

## 1. Requisitos

### Base (obligatorio)

- Python 3, GTK3 y PyGObject (`python3-gi`, `gir1.2-gtk-3.0`, `gir1.2-gdkpixbuf-2.0`).
- D-Bus de sesión; para batería, bloqueo y energía también el de sistema.
- **Wayland** con `wlr-layer-shell` da la ventana nativa. Sin él, la isla relanza una sola vez con
  `GDK_BACKEND=x11` y usa una ventana X11 (funciona en GNOME, Cinnamon, sesiones X11 y XWayland).
- En GNOME Wayland se puede instalar la extensión provisional para colocar la ventana desde el shell.

`./install.sh --deps` detecta tu distro (apt, dnf, pacman o zypper), muestra los paquetes y la orden, y
solo ejecuta `sudo` si confirmas. Paquetes base por familia:

| Familia | Paquetes |
|---|---|
| Debian/Ubuntu y derivadas (apt) | `python3-gi gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 gir1.2-gdkpixbuf-2.0` |
| Fedora/RHEL (dnf) | `python3-gobject gtk3 gtk-layer-shell` |
| Arch/Manjaro (pacman) | `python-gobject gtk3 gtk-layer-shell` |
| openSUSE (zypper) | `python3-gobject-Gdk gtk3 typelib-1_0-GtkLayerShell-0_1` |

### Por función (opcionales)

Si falta una herramienta, la isla sigue funcionando; la función se oculta o muestra qué instalar.

| Función | Métodos que prueba, en orden |
|---|---|
| Avisos y No molestar | Monitor genérico de `org.freedesktop.Notifications` + el daemon del escritorio (Budgie, GNOME, KDE, XFCE, mako, SwayNC, dunst…). Centro de avisos nativo o de la extensión; si no hay, se oculta |
| Volumen y sonidos | `wpctl` → `pactl`; `pw-play` → `paplay` → `canberra-gtk-play` |
| Wi‑Fi, red, VPN, modo avión | NetworkManager (`nmcli`), `rfkill`, `ip`, `ss` |
| Bluetooth | BlueZ; con la función «Burbuja Bluetooth» (activa por defecto), el primer dispositivo conectado aparece como burbuja con su batería |
| Copias (portapapeles) | `wl-paste --watch` en wlroots; `Gtk.Clipboard` en X11/XWayland. Mismo filtro de secretos |
| Capturas | `grim`+`slurp`, `spectacle`, extensión GNOME, `maim`, `scrot` o portal |
| Grabar pantalla | `wf-recorder`, `ffmpeg` x11grab, extensión GNOME o portal |
| Bloqueo, pantalla e inactividad | Método nativo del escritorio → `loginctl`/`xset`/XScreenSaver → sondeo; verifica que el bloqueo funcionó antes de apagar la pantalla |
| Modo oscuro y luz nocturna | gsettings del escritorio, `gammastep`/`redshift` o portal; la casilla se oculta si no hay método |
| Cerrar sesión y «despierto» | SessionManager del escritorio → `xfce4-session-logout` → `loginctl`; `systemd-inhibit` como último recurso |
| Ajustes rápidos y monitor | Centro de ajustes del escritorio; `top` en terminal como último recurso |
| GitHub y despliegues | `gh` con sesión iniciada (`gh auth login`) |
| Proyectos (git) | `git` |
| Presencia (cámara) | OpenCV + detección de inactividad (`swayidle`, XScreenSaver, reloj del bus…) y `wlopm`/`xset` |

### Servicios en línea (sin claves ni cuentas)

| Uso | Servicio |
|---|---|
| Clima y buscador de ciudades | [Open‑Meteo](https://open-meteo.com) |
| Dólar (TRM oficial) | datos.gov.co; respaldo: open.er-api.com |
| GitHub, PR y despliegues | API de GitHub a través de `gh` (tu propia sesión) |

---

## 2. Instalar y ejecutar

```bash
git clone <este-repo> "dinamic island"
cd "dinamic island"
./install.sh --deps     # opcional: instala las dependencias de tu distro (pregunta antes)
./install.sh
```

| Orden | Qué hace |
|---|---|
| `./install.sh` | Copia `isla_dinamica/` a `~/.local/share/isla-dinamica/`, escribe el lanzador y el autoarranque, y reinicia la isla |
| `./install.sh --deps` | Muestra los paquetes según distro/escritorio y pregunta antes de ejecutar la orden con `sudo` |
| `./install.sh --gnome-extension` | Copia y activa la extensión provisional de GNOME (pregunta antes) |
| `./install.sh --no-restart` | Actualiza los archivos sin reiniciar la isla en marcha |
| `./install.sh --help` | Ayuda |

El lanzador es `~/.local/bin/isla-dinamica` y el autoarranque,
`~/.config/autostart/isla-dinamica.desktop`, con la ruta real de tu usuario (no hay que editar nada).
En sway, Hyprland, river, labwc y otros compositores sin autoarranque estándar, el instalador muestra la
línea `exec` que debes añadir a tu configuración; **no la edita por ti**.

Vuelve a ejecutar `./install.sh` cada vez que cambies el código.

### Diagnóstico

```bash
isla-dinamica --doctor
```

Muestra el escritorio y el tipo de sesión detectados, el backend de la ventana y el método elegido para
cada función (avisos, DND, centro, bloqueo, pantalla, inactividad, portapapeles, captura, grabación,
oscuro, luz nocturna, cerrar sesión, despierto, volumen y sonidos). «No disponible» significa que no hay
ningún método; en ese caso la casilla o la página se oculta. Es la primera cosa que hay que mirar antes de
abrir un issue.

### Ejecutar sin instalar (desarrollo)

```bash
python3 isla.py
```

| Variable de entorno | Efecto |
|---|---|
| `ISLA_DEBUG=1` | Muestra en la terminal lo que detecta: avisos, consultas, errores |
| `ISLA_NO_WELCOME=1` | No muestra el saludo al arrancar |
| `GDK_BACKEND=x11` | Fuerza X11/XWayland (el instalador lo hace automáticamente cuando no hay layer-shell) |

### Detener

```bash
pkill -f isla-dinamica
```

---

## 3. Configurar las opciones

Todo se configura desde la propia isla. Pasa el ratón por la píldora y ve a **⋯ (Más) → Funciones**,
donde puedes activar o desactivar cada función. Los cambios se guardan en
`~/.config/isla-dinamica/config.json`.

| Función | Qué necesita para funcionar |
|---|---|
| **GitHub** | `gh auth login`. Muestra las revisiones pedidas, tus PR abiertas y las fusionadas en 7 días. Consulta cada 3 min y avisa con una alerta, que queda en Notificaciones, de: cada novedad de tu bandeja de GitHub (PR nuevas, comentarios, menciones, issues, releases de los repos que sigues), CI terminado, revisiones aprobadas o con cambios y PR tuyas fusionadas. Al arrancar da un solo resumen de lo que haya sin leer. |
| **Despliegues en vivo** | Lo mismo que GitHub. Lee los *deployments* que Railway u otras plataformas reportan a GitHub en tus repos con actividad de las últimas 3 semanas. Se ven en la pestaña GitHub. |
| **Teams y correo** | Teams (app o PWA de Chrome) y Outlook web abierto en Chrome, con las notificaciones permitidas. La isla lee esas notificaciones; no usa la API de Microsoft. |
| **Clima** | Nada. Toma la ciudad de tu zona horaria; puedes cambiarla en la página Clima. |
| **Dólar (TRM)** | Internet. |
| **Proyectos (git)** | Las carpetas con repos que vigila. Por defecto es `~/Documentos/WM`; se pueden añadir más desde la página Proyectos. Avisa con una alerta cuando llegan commits nuevos al remoto (pull pendiente) y cuando un repo lleva 15 min con commits sin subir (push pendiente). |
| **Presencia (cámara)** | Paquetes OpenCV, `swayidle` y `wlopm`. Viene **apagada**: actívala en Funciones o con su casilla del inicio. Más detalles abajo. |
| **Audio en vivo / Cámara y micrófono** | PipeWire. |
| **Red y VPN / Monitor del sistema / Descargas / Servidores locales / Recordatorios** | Nada más. |
| **Burbuja Bluetooth** | BlueZ. Muestra junto a la píldora una burbuja redonda para el primer dispositivo conectado (por nombre), con su icono y un anillo con el porcentaje de batería; al pasar el ratón se ve `Nombre · NN%`. Si el dispositivo no reporta batería, se ve solo el nombre. Viene activada. |
| **Burbuja de tareas** | Si hay más actividades de las que caben (2 burbujas), muestra una tercera `+N`; al hacer clic abre «Tareas en curso» con todo lo que está en marcha, y cada fila abre su página. Viene activada. |
| **Hora en formato 24 h** | Apágala para ver la hora en 12 h. |

**Burbujas de actividades:** pasar el ratón por una burbuja muestra un tooltip con el nombre de la opción y lo que
está pasando (`Pomodoro · Enfoque · 12:30`, `Música · Canción · Artista`, `Grabación · 00:12`…); en Bluetooth se ve
el nombre del dispositivo y su batería (`BT · 80%`). La isla no se expande con el ratón encima de una burbuja:
**haz clic** en ella para abrir su página. El clic en la píldora sigue abriendo Inicio.
Si no caben todas, la burbuja `+N` abre la lista **Tareas en curso**.

### Presencia (bloquear si no hay nadie)

Funciona así:

1. Cuando llevas un rato sin tocar el teclado ni el ratón, la isla mira por la cámara cada pocos segundos.
2. Si nadie aparece durante **N minutos** (5 por defecto), la píldora muestra una cuenta atrás.
3. Al terminar la cuenta atrás, la isla **bloquea la sesión y apaga la pantalla**.

Hay casos en los que nunca bloquea: si estás en una llamada, si otra app usa la cámara o si hay un error
de cámara.

Para configurarla, ve a la página **Presencia** (inicio → casilla Presencia → ›):

- **Minutos**: de 1 a 60.
- **Horario**: desde/hasta y días de la semana. Por defecto, de lunes a viernes de 08:00 a 18:00. La
  franja puede cruzar la medianoche.
- **Pausa**: 1 hora, hasta mañana o reanudar.
- **Probar cámara**: comprueba si te detecta.

Para detectar mejor de perfil o con poca luz, usa YuNet en lugar del detector Haar. Para ello, guarda
`face_detection_yunet.onnx` en `~/.local/share/isla-dinamica/`.

Limitación: si Chrome reproduce música o vídeo, el sistema no se considera inactivo y la presencia no
empieza a contar.

### Secciones plegables y contador «hoy»

En **GitHub** y en **Teams y correo** puedes plegar o desplegar cada sección haciendo clic en su
encabezado; la isla recuerda cuáles dejaste plegadas. El contador azul **«N hoy»** indica cuántas
novedades hubo en esa sección desde las 00:00, aunque esté plegada.

### Archivo de configuración

`~/.config/isla-dinamica/config.json` (se crea solo). Claves principales:

```jsonc
{
  "city": null,                                 // ciudad del clima (null = según la zona horaria)
  "dock": {"edge": "top", "pos": 0.5},         // borde y posición de la píldora
  "features": {"presence": true},              // funciones activadas o desactivadas
  "collapsed": ["gh_merged"],                  // secciones plegadas
  "git_folders": ["~/Documentos/WM"],          // carpetas que vigila «Proyectos»
  "pomodoro": {"work": 25, "short": 5, "long": 15, "every": 4, "auto": true},
  "presence": {"minutes": 5, "warn": 30, "start": "08:00", "end": "18:00", "days": [0,1,2,3,4]}
}
```

Si una clave falta o no es válida, se usa el valor por defecto. Para volver a la configuración inicial,
borra el archivo y reinicia la isla.

---

## 4. Desarrollo

### Estructura

```
isla.py                   lanzador para desarrollo
install.sh                instala en ~/.local y reinicia (--deps, --gnome-extension, --help)
tools/                    generadores puros de dependencias, autoarranque y lanzador
extras/gnome-shell/       extensión provisional (D-Bus) para GNOME
docs/                     DOCUMENTACION.md y ESCRITORIOS.md
isla_dinamica/
  __init__.py             versiones de GTK/Gdk/LayerShell (gi.require_version), una sola vez
  main.py                 arranque y --doctor
  platform/               ÚNICO sitio con nombres de escritorio: detección, cadenas de métodos y puente D-Bus
  config.py               preferencias (config.json): valores por defecto, validación, guardado 0600
  core.py                 estado central: crea los servicios y guarda el estado
  events.py               EventRouter: evento de un servicio → aviso de la píldora
  capture.py              fachada de capturas; delega en platform/capture.py
  window.py               ventana: une los mixins de ui/ con las páginas
  ui/
    placement.py          implementación de las formas de colocar la ventana (sin elegir por escritorio)
    style.py              tamaños de la píldora y hoja CSS
    gtk.py                fábricas de widgets (label, icon, button…)
    pill.py               PILL_ORDER y pick_pill: qué muestra la píldora (función pura)
    pill_view.py          cómo se dibuja cada estado de la píldora
    bubbles.py            burbujas de actividades (geometría pura + mixin)
    dock.py               acople a los bordes y arrastre (geometría pura + mixin)
    paint.py              fondo, brillo y color de las tarjetas (Cairo)
    widgets/              widgets dibujados: carátula, ecualizador, clima, gráficos, casillas
  util/
    fmt.py                fechas, horas y duraciones en español
    proc.py               lanzar comandos sin bloquear, abrir apps y URIs, sonidos
    safety.py             qué URLs, archivos y apps se pueden abrir
    net.py                fetch_json
    links.py              apps web (Teams, GitHub, Outlook)
  services/               lógica sin interfaz (un servicio por archivo; poller.py = temporizadores comunes)
  pages/                  páginas del panel: una clase Page por archivo, listadas en pages/__init__.py
tests/
  unit/                   pruebas unitarias (unittest; incluye la regla de arquitectura)
  harness.py              arnés de capturas de pantalla
  docker/                 Xvfb + Openbox para probar la ventana X11
  x11_smoke.sh            comprobación X11 automatizada
  fixtures/               datos falsos para el arnés
```

Las dependencias van en un solo sentido: `util` y `config` no importan nada del resto del proyecto;
`platform` conoce los escritorios y no importa `ui`, `pages` ni `services`; `services` usa `util`/`config`/
`platform`; `ui` usa `util`, `platform.placement` y lee el estado de algunos servicios; `pages` usa `ui`,
`util` y `services`; `window` y `core` lo unen todo. Ningún servicio importa nada de `ui` ni de `pages`.
Los nombres de escritorio solo aparecen en `platform/` (lo comprueba `tests/unit/test_architecture.py`).
No hay `import *`: cada archivo dice de dónde sale cada nombre.

### Pruebas

Con `make check` (o, si no tienes `make`, con los dos comandos siguientes) se comprueba que todo compila
y se ejecutan las pruebas unitarias, incluidas las de detección, cada cadena de métodos y la regla de
arquitectura:

```bash
python3 -m compileall -q isla_dinamica tools
python3 -W error::ResourceWarning -m unittest discover -s tests/unit
```

La ventana X11 se comprueba aparte, sin depender del escritorio anfitrión:

```bash
bash tests/x11_smoke.sh     # Xvfb + Openbox en Docker; requiere Docker
```

GNOME, KDE, Cinnamon y el resto se validan en una VM siguiendo
**[docs/ESCRITORIOS.md](docs/ESCRITORIOS.md)**.

Capturas de páginas con datos falsos:

```bash
python3 tests/harness.py github ms home --setup tests/fixtures/ms_demo.py --out /tmp/capturas
```

El arnés detiene la isla instalada, abre las páginas pedidas, guarda un PNG por página y vuelve a arrancar
la isla instalada. Las páginas especiales son `pill` (la píldora cerrada) y `bubble`/`bubble2`/`bubble3` (clic
en la 1.ª/2.ª/3.ª burbuja, que abre su página; la 3.ª es `+N`). Para probar la burbuja `+N` y «Tareas en curso»:
`python3 tests/harness.py pill bubble3 tasks --setup tests/fixtures/tasks_demo.py --out /tmp/capturas-tareas`.
Para probar la burbuja Bluetooth sin dispositivos reales:

```bash
BT_NAME=Auriculares BT_BATTERY=82 python3 tests/harness.py pill \
  --setup tests/fixtures/bluetooth_demo.py --out /tmp/capturas-bt
BT_BATTERY=none python3 tests/harness.py pill --setup tests/fixtures/bluetooth_demo.py \
  --out /tmp/capturas-bt-sin-bateria
```

El fixture acepta `BT_NAME`, `BT_BATTERY` (`none` para probar sin porcentaje), `BT_ICON` y `BT_CONNECTED=0`
(para comparar sin burbuja); con `BT_DEBUG=1` imprime el tooltip calculado.

### Añadir una página o función

1. Crea `isla_dinamica/pages/<nombre>.py` con una clase que herede de `Page` (`pages/base.py`), defina
   `PAGES = {"nombre": page("_build_nombre")}` y, si quieres un acceso en Más → Herramientas,
   `TOOLS = (tool(...),)`. Llama a `feature()` si la función se puede apagar.
2. Añádela a `PAGE_CLASSES` en `isla_dinamica/pages/__init__.py`.
3. Usa solo lo que `Page` ofrece (`self.core`, `self.go()`, `self._page()`, `self._row()`, `self._fold()`…) y,
   si lo necesitas, los ganchos `live()` (cada segundo), `on_collapse()`, `typing()` y `waiting()`.
4. Si necesita datos del sistema, crea un servicio en `isla_dinamica/services/` y créalo en `core.py`.

---

## 5. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| La isla no aparece | Ejecuta `isla-dinamica --doctor`: dice el escritorio detectado y el backend elegido. Faltan paquetes base o hay un error de arranque; prueba `ISLA_DEBUG=1 python3 isla.py`. |
| Tengo un dispositivo Bluetooth conectado pero no veo su burbuja | La isla en marcha usa la copia instalada, no el repo. Ejecuta `./install.sh` (instala y reinicia) y comprueba que la función «Burbuja Bluetooth» está activa en ⋯ → Funciones. El arnés de capturas también reinicia esa copia al terminar. |
| GitHub pide iniciar sesión | `gh auth login` y luego pulsa Actualizar. |
| No llegan los mensajes de Teams o del correo | Deja Teams y Outlook web abiertos en Chrome con las notificaciones permitidas, y desactiva «No molestar». |
| Presencia dice «Sin OpenCV» | `sudo apt install python3-opencv opencv-data` |
| Presencia nunca cuenta | Hay música o vídeo reproduciéndose (inhibe la inactividad), o estás fuera del horario o en pausa. |
| Grabar pantalla no funciona | `sudo apt install wf-recorder` (wlroots) o `ffmpeg` (X11). `--doctor` dice qué método se eligió; el portal es el último recurso |
| Una función no sale en el panel | No hay método en este escritorio. Mira `isla-dinamica --doctor` e instala la herramienta que indica; las casillas sin método se ocultan |
| En GNOME la ventana queda detrás de las maximizadas | Instala la extensión provisional con `./install.sh --gnome-extension` y reinicia la sesión |
