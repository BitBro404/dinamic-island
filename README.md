# Isla dinámica

Una píldora tipo «Dynamic Island» arriba al centro de la pantalla para escritorios Linux con Wayland.
Muestra la música, las llamadas, el temporizador, las descargas, los despliegues y los avisos.
Al pasar el ratón por encima se expande en un panel con ajustes rápidos y páginas: Wi‑Fi, Bluetooth,
GitHub, Teams y correo, clima, sistema, presencia y más.

Está hecha en Python 3 + GTK3 (PyGObject) con `gtk-layer-shell`, y probada en **Ubuntu 26.10 con Budgie
sobre Wayland (labwc)**.

📖 La documentación de todas las funciones, ordenadas por las dependencias que necesitan, está en
**[docs/DOCUMENTACION.md](docs/DOCUMENTACION.md)**.

---

## 1. Requisitos

### Base (obligatorio)

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 gir1.2-gdkpixbuf-2.0
```

- Necesitas una sesión **Wayland** con un compositor que soporte `wlr-layer-shell`, como labwc, sway o
  Hyprland.
- Las notificaciones (página Avisos, Teams y correo, «No molestar») se leen del servidor de
  notificaciones de **Budgie** (`org.budgie_desktop.Notifications`). En otro escritorio esas funciones
  quedan vacías.

### Por función (opcionales)

Si falta una herramienta, la isla sigue funcionando y la página correspondiente te dice qué instalar.

| Función | Paquetes / herramientas | Instalar |
|---|---|---|
| Volumen, audio en vivo, llamadas | PipeWire + `pactl`, `wpctl`, `parec`, `pw-play` | `sudo apt install pipewire-pulse wireplumber pulseaudio-utils pipewire-bin` |
| Wi‑Fi, red, VPN, modo avión | NetworkManager (`nmcli`), `rfkill`, `ip`, `ss` | `sudo apt install network-manager rfkill iproute2` |
| Bluetooth | BlueZ | `sudo apt install bluez` |
| Copias (portapapeles) | `wl-copy`, `wl-paste` | `sudo apt install wl-clipboard` |
| Recorte y captura de pantalla | `grim`, `slurp` | `sudo apt install grim slurp` |
| Grabar pantalla | `wf-recorder` | `sudo apt install wf-recorder` |
| GitHub y despliegues | `gh` con sesión iniciada | `sudo apt install gh` y luego `gh auth login` |
| Proyectos (git) | `git` | `sudo apt install git` |
| Presencia (cámara) | OpenCV, `swayidle`, `wlopm` | `sudo apt install python3-opencv opencv-data swayidle wlopm` |
| Cuidar batería, ahorro de energía | UPower y power-profiles-daemon (vienen con Ubuntu) | — |
| Abrir ajustes del sistema | `budgie-control-center` | viene con Budgie |

Todo junto:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 gir1.2-gdkpixbuf-2.0 \
  pipewire-pulse wireplumber pulseaudio-utils pipewire-bin network-manager rfkill iproute2 bluez \
  wl-clipboard grim slurp wf-recorder gh git python3-opencv opencv-data swayidle wlopm
```

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
./install.sh
```

`install.sh` hace lo siguiente:

1. Copia el paquete `isla_dinamica/` a `~/.local/share/isla-dinamica/`.
2. Crea el lanzador `~/.local/bin/isla-dinamica`.
3. Cierra la isla que esté corriendo y arranca la nueva.

Vuelve a ejecutarlo cada vez que cambies el código.

### Arrancar al iniciar sesión

```bash
cp isla-dinamica.desktop ~/.config/autostart/
```

Edita la línea `Exec=` si tu usuario no es `luis`: debe apuntar a `~/.local/bin/isla-dinamica` con la ruta
completa.

### Ejecutar sin instalar (desarrollo)

```bash
python3 isla.py
```

| Variable de entorno | Efecto |
|---|---|
| `ISLA_DEBUG=1` | Muestra en la terminal lo que detecta: avisos, consultas, errores |
| `ISLA_NO_WELCOME=1` | No muestra el saludo al arrancar |

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
| **GitHub** | `gh auth login`. Muestra las revisiones pedidas, tus PR abiertas y las fusionadas en 7 días, y avisa del CI. Consulta cada 3 min. |
| **Despliegues en vivo** | Lo mismo que GitHub. Lee los *deployments* que Railway u otras plataformas reportan a GitHub en tus repos con actividad de las últimas 3 semanas. Se ven en la pestaña GitHub. |
| **Teams y correo** | Teams (app o PWA de Chrome) y Outlook web abierto en Chrome, con las notificaciones permitidas. La isla lee esas notificaciones; no usa la API de Microsoft. |
| **Clima** | Nada. Toma la ciudad de tu zona horaria; puedes cambiarla en la página Clima. |
| **Dólar (TRM)** | Internet. |
| **Proyectos (git)** | Las carpetas con repos que vigila. Por defecto es `~/Documentos/WM`; se pueden añadir más desde la página Proyectos. |
| **Presencia (cámara)** | Paquetes OpenCV, `swayidle` y `wlopm`. Viene **apagada**: actívala en Funciones o con su casilla del inicio. Más detalles abajo. |
| **Audio en vivo / Cámara y micrófono** | PipeWire. |
| **Red y VPN / Monitor del sistema / Descargas / Servidores locales / Recordatorios** | Nada más. |
| **Hora en formato 24 h** | Apágala para ver la hora en 12 h. |

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
install.sh                instala en ~/.local y reinicia
isla_dinamica/
  main.py                 arranque
  core.py                 estado central, servicios y eventos
  window.py               ventana, píldora, burbujas y prioridades
  common.py               utilidades, CSS y configuración
  widgets.py              widgets propios
  services/               lógica sin interfaz (un servicio por archivo)
  pages/                  páginas del panel (un mixin por archivo, registradas en pages/__init__.py)
tests/
  unit/                   pruebas unitarias (unittest)
  harness.py              arnés de capturas de pantalla
  fixtures/               datos falsos para el arnés
```

### Pruebas

Pruebas unitarias (usan solo la biblioteca estándar, sin pytest):

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests/unit
```

Comprobar que todo compila:

```bash
python3 -m compileall -q isla_dinamica
```

Capturas de páginas con datos falsos:

```bash
python3 tests/harness.py github ms home --setup tests/fixtures/ms_demo.py --out /tmp/capturas
```

El arnés detiene la isla instalada, abre las páginas pedidas, guarda un PNG por página y vuelve a arrancar
la isla instalada. Las páginas especiales son `pill` (la píldora cerrada) y `bubble`/`bubble2` (las
burbujas).

### Añadir una página o función

1. Crea `isla_dinamica/pages/<nombre>.py` con una clase mixin que defina `PAGES = {...}` y llame a
   `feature()` y, si quieres un acceso en Más → Herramientas, a `tool()`.
2. Regístrala en `isla_dinamica/pages/__init__.py`.
3. Si necesita datos del sistema, crea un servicio en `isla_dinamica/services/` y créalo en `core.py`.

---

## 5. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| La isla no aparece | Comprueba que estás en Wayland (`echo $XDG_SESSION_TYPE`) y que tienes `gir1.2-gtklayershell-0.1`. Ejecuta `ISLA_DEBUG=1 python3 isla.py` para ver los errores. |
| GitHub pide iniciar sesión | `gh auth login` y luego pulsa Actualizar. |
| No llegan los mensajes de Teams o del correo | Deja Teams y Outlook web abiertos en Chrome con las notificaciones permitidas, y desactiva «No molestar». |
| Presencia dice «Sin OpenCV» | `sudo apt install python3-opencv opencv-data` |
| Presencia nunca cuenta | Hay música o vídeo reproduciéndose (inhibe la inactividad), o estás fuera del horario o en pausa. |
| Grabar pantalla no funciona | `sudo apt install wf-recorder` |
