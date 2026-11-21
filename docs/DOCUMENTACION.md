# Documentación completa de la Isla dinámica

Esta guía recorre **todas** las funciones de la isla en el orden en que se van necesitando dependencias.
Cada nivel da por hecho que los niveles anteriores ya están instalados. Puedes quedarte en cualquier nivel:
la isla funciona igual y solo oculta o avisa en lo que le falte.

| Nivel | Qué añade | Dependencias nuevas |
|---|---|---|
| [0](#nivel-0--base-la-isla-misma) | La isla: píldora, panel, reloj, temporizador, pomodoro, recordatorios, sistema, descargas | Python 3, GTK3, gtk-layer-shell, sesión Wayland |
| [1](#nivel-1--servicios-del-escritorio-vienen-con-ubuntu) | Ajustes rápidos, música, batería, energía, USB, Wi‑Fi, Bluetooth, red | D-Bus del sistema: NetworkManager, BlueZ, UPower, logind… |
| [2](#nivel-2--audio-pipewire) | Volumen, audio en vivo, llamadas, micrófono en uso, sonidos | PipeWire + utilidades |
| [3](#nivel-3--notificaciones-de-budgie) | Avisos, No molestar, Teams y correo | Escritorio Budgie |
| [4](#nivel-4--herramientas-wayland) | Portapapeles, capturas, grabar pantalla | wl-clipboard, grim, slurp, wf-recorder |
| [5](#nivel-5--internet) | Clima, dólar (TRM) | Conexión a Internet |
| [6](#nivel-6--git) | Proyectos (estado de tus repos) | git |
| [7](#nivel-7--github-gh) | Pull requests, CI y despliegues en vivo | gh + cuenta de GitHub |
| [8](#nivel-8--cámara-presencia) | Presencia: bloquear si no hay nadie | Cámara, OpenCV, swayidle, wlopm |

Las funciones que se pueden apagar están en **⋯ Más → Funciones**. Todas vienen encendidas salvo
*Presencia*.

---

## Nivel 0 — Base: la isla misma

### Dependencias

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 gir1.2-gdkpixbuf-2.0
```

- Sesión **Wayland** con un compositor que soporte `wlr-layer-shell` (labwc, sway, Hyprland…). Para
  comprobarlo: `echo $XDG_SESSION_TYPE` debe decir `wayland`.
- Instalar y arrancar: `./install.sh` (ver el [README](../README.md#2-instalar-y-ejecutar)).

### La píldora

La píldora es la isla cerrada. Muestra **una sola cosa a la vez**, en este orden de prioridad (gana la
primera que esté activa):

1. Alarma del temporizador al terminar, a pantalla ancha.
2. Una tarjeta de aviso mientras el ratón está encima (se queda abierta).
3. El panel expandido, si el ratón está encima.
4. *Presencia*: «Nadie frente a la pantalla» con la cuenta atrás antes de bloquear.
5. Un evento puntual, como «Copiado», «Desplegado» o una notificación.
6. Una llamada en curso, con su duración.
7. La música que suena, con la carátula y el ecualizador.
8. El pomodoro, con su fase y el tiempo restante.
9. «Grabando», si se está grabando la pantalla.
10. Un recordatorio que vence en menos de 5 min.
11. Un despliegue en curso.
12. Una descarga en curso, con su velocidad.
13. Otra app que reproduce audio.
14. El temporizador.
15. En reposo: la hora, un punto rojo si hay avisos sin leer y la temperatura.

**Burbujas de actividades:** lo que está activo pero no cabe en la píldora aparece como círculos a su lado,
con un anillo de progreso cuando lo hay. Al pasar el ratón por una burbuja se abre su página.

### Interacción

| Gesto | Qué hace |
|---|---|
| Pasar el ratón | Expande el panel (página de inicio) |
| Clic en la píldora | Expande el panel; si es una tarjeta de aviso, ejecuta su acción (abrir el chat, el PR…) |
| Rueda del ratón sobre la píldora | Sube o baja el volumen (requiere nivel 2) |
| Arrastrar la píldora | La mueve. Al soltarla se acopla al borde más cercano (arriba, abajo, izquierda o derecha) y se guarda la posición |

### Funciones del nivel 0

| Función | Dónde | Qué hace |
|---|---|---|
| **Reloj** | Píldora e inicio | Hora en formato 24 h o 12 h (*Más → Funciones → Hora en formato 24 h*) y fecha |
| **Temporizador** | Inicio → Alarma | Cuenta atrás en la píldora; al terminar, alarma a pantalla ancha durante 10 s |
| **Pomodoro** | Inicio → Pomodoro | Enfoque, descanso y descanso largo (por defecto 25/5/15 min, descanso largo cada 4). Pausar, reiniciar y avance automático |
| **Recordatorios** | Más → Recordar | Escribes en español «qué y cuándo»: *«llamar a Ana en 20 min»*, *«daily a las 9:30»*, *«mañana a las 8 pagar luz»*. Se ven en la píldora 5 min antes y avisan a la hora |
| **Monitor del sistema** | Más → Sistema | CPU, RAM y temperatura con gráfica, y los procesos que más consumen. Avisa si un proceso usa más del 90 % de un núcleo durante 45 s, si falta memoria o si el equipo se calienta. Lee `/proc` y `/sys` |
| **Descargas** | Más → Descargas | Vigila la carpeta Descargas: archivos `.crdownload` (Chrome) y `.part` (Firefox). Muestra el progreso y la velocidad en la píldora y avisa al terminar |
| **Más** | Botón ⋯ | Herramientas extra y los interruptores de cada función |

---

## Nivel 1 — Servicios del escritorio (vienen con Ubuntu)

La isla habla por D-Bus con servicios que ya trae un Ubuntu de escritorio. Si alguno falta, su casilla no
hace nada o no aparece.

```bash
sudo apt install network-manager rfkill iproute2 bluez upower power-profiles-daemon udisks2
```

| Función | Servicio que usa | Qué hace |
|---|---|---|
| **Wi‑Fi** (casilla y página) | NetworkManager (`nmcli`) | Encender o apagar el Wi‑Fi, ver las redes y conectarse (pide la contraseña si hace falta) |
| **Bluetooth** (casilla y página) | BlueZ (`org.bluez`) | Encender o apagar, ver los dispositivos con su batería, y conectar o desconectar |
| **Avión** | `rfkill` | Apaga o enciende todas las radios |
| **Red y VPN** (Más → Red) | `nmcli`, `ip`, `/sys/class/net` | Velocidad de bajada y subida en vivo, interfaz, IP local y VPN activa. Avisa si se cae Internet o la VPN |
| **Servidores locales** (Más → Servidores) | `ss` (iproute2) | Servidores de desarrollo escuchando en los puertos 3000–9999 (Vite, Next, Nest, Django, Spring…): abrirlos en el navegador, detenerlos y aviso si se caen |
| **Música** | MPRIS (`org.mpris.MediaPlayer2.*`) | Canción, artista y carátula de Spotify, Chrome, etc., con botones de reproducir, anterior y siguiente. El color del ecualizador sale de la carátula |
| **Batería** | UPower | Porcentaje y estado en el inicio; avisos al conectar o desconectar el cargador |
| **Cuidar batería** | UPower `EnableChargeThreshold` | Limita la carga (normalmente al 80 %) si el portátil lo soporta. Puede pedir contraseña |
| **Ahorro** | power-profiles-daemon | Cambia al perfil de bajo consumo |
| **Oscuro** | GSettings `org.gnome.desktop.interface` | Tema claro u oscuro |
| **Luz nocturna** | GSettings de color | Activa o desactiva la luz nocturna |
| **Despierto** | `org.gnome.SessionManager.Inhibit` | Impide que la pantalla se apague o el equipo se suspenda |
| **USB** (Inicio → USB) | GIO / udisks2 | Medios extraíbles: abrirlos y expulsarlos |
| **Energía** (Inicio → Energía) | logind (`org.freedesktop.login1`) | Bloquear, suspender, reiniciar y apagar, con confirmación |
| **Ajustes del sistema** | `budgie-control-center` | Algunas páginas tienen un acceso directo a su panel de configuración |
| **Cámara en uso** | `/proc` | Punto verde en la píldora mientras una app usa la cámara (*Más → Funciones → Cámara y micrófono*) |

---

## Nivel 2 — Audio (PipeWire)

```bash
sudo apt install pipewire-pulse wireplumber pulseaudio-utils pipewire-bin
```

| Función | Herramienta | Qué hace |
|---|---|---|
| **Volumen** | `wpctl` | Barra de volumen en el inicio y rueda del ratón sobre la píldora. Muestra el nivel al cambiarlo |
| **Audio en vivo** | `parec`, `pactl` | Las barras del ecualizador siguen el sonido real y el borde brilla al ritmo |
| **Llamadas** | `pactl` | Detecta llamadas (Teams, Meet, Zoom…) y muestra «En llamada» con su duración |
| **Otras apps con audio** | `pactl` | Si suena algo que no es música (un vídeo, por ejemplo), lo indica |
| **Micrófono en uso** | `pactl` | Punto naranja en la píldora y nombre de la app que lo usa |
| **Sonidos** | `pw-play` | Sonido de la alarma y de los avisos |

Para apagar el audio en vivo: *Más → Funciones → Audio en vivo*.

---

## Nivel 3 — Notificaciones de Budgie

La isla escucha al servidor de notificaciones de Budgie (`org.budgie_desktop.Notifications`). En otro
escritorio, las funciones de este nivel quedan vacías.

| Función | Dónde | Qué hace |
|---|---|---|
| **Avisos** | Píldora, Inicio → Avisos | Cada notificación aparece como tarjeta en la píldora. El historial guarda hasta 60, con un contador de no leídas |
| **No molestar** | Casilla del inicio | Silencia las tarjetas, salvo las urgentes |
| **Teams y correo** | Inicio → botón *Teams y correo* | Separa las notificaciones de Microsoft Teams y de Outlook web en dos secciones, con un contador de no leídos. Clic en un mensaje: abre Teams u Outlook |

**Requisitos para Teams y correo:**
- Teams (app o PWA de Chrome) y Outlook web abiertos en Chrome, con las notificaciones permitidas.
- No usa la API de Microsoft: lo que no notifica Chrome, la isla no lo ve.

Las secciones **TEAMS** y **CORREO · OUTLOOK** se pliegan con un clic en el encabezado. El contador azul
«N hoy» indica cuántos avisos llegaron desde las 00:00.

---

## Nivel 4 — Herramientas Wayland

```bash
sudo apt install wl-clipboard grim slurp wf-recorder
```

| Función | Herramienta | Qué hace |
|---|---|---|
| **Copias** (Inicio → Copias) | `wl-paste --watch`, `wl-copy` | Historial del portapapeles: clic para volver a copiar y botón para borrar todo. Ignora lo que marcan los gestores de contraseñas |
| **Recorte** (Inicio) | `grim` + `slurp` | Arrastras un rectángulo y se guarda en `~/Imágenes/Capturas/` |
| **Pantalla** (Inicio) | `grim` | Captura la pantalla completa en la misma carpeta |
| **Grabar** (Más → Grabar) | `wf-recorder` | Graba la pantalla completa o un área, con o sin audio, en `~/Vídeos/`. Mientras graba, la píldora muestra «Grabando» en rojo |

---

## Nivel 5 — Internet

No necesita cuentas ni claves.

| Función | Servicio | Qué hace |
|---|---|---|
| **Clima** | Open‑Meteo | Temperatura en la píldora y página con el pronóstico por horas y días, la sensación térmica, el viento, la humedad, el índice UV y la hora del amanecer y el atardecer. Avisa si va a llover. La ciudad sale de tu zona horaria; puedes cambiarla en la página Clima |
| **Dólar (TRM)** (Más → Dólar) | datos.gov.co (respaldo: open.er-api.com) | TRM oficial de hoy, su variación, los últimos 30 días y un conversor USD ⇄ COP |

---

## Nivel 6 — git

```bash
sudo apt install git
```

| Función | Dónde | Qué hace |
|---|---|---|
| **Proyectos** | Más → Proyectos | Para cada repo dentro de las carpetas vigiladas: rama, cambios sin commit, commits por subir o bajar, stashes y conflictos |

**Configuración:** por defecto vigila `~/Documentos/WM`. Puedes añadir o quitar carpetas desde la página
o con la clave `git_folders` en `config.json`.

---

## Nivel 7 — GitHub (`gh`)

```bash
sudo apt install gh
gh auth login
```

Si falta `gh` o la sesión, la página GitHub muestra estos mismos comandos con un botón *Copiar*.

| Función | Dónde | Qué hace |
|---|---|---|
| **GitHub** | Inicio → botón *GitHub* | Tres secciones: **Revisión pedida**, **Mis PR abiertas** y **Fusionadas en los últimos 7 días**. Avisa cuando te piden una revisión o cuando el CI de tus PR pasa o falla. Consulta cada 3 min. El contador rojo del botón son las revisiones pendientes |
| **Despliegues en vivo** | Pestaña GitHub, píldora y burbuja | Lee los *deployments* que Railway u otra plataforma reporta a GitHub en tus repos con actividad en las últimas 3 semanas. **Desplegando** aparece arriba (solo si hay alguno en curso) y **Despliegues recientes** abajo. Avisa al empezar, al terminar bien y al fallar. Consulta cada 30 s si hay alguno en curso y cada 90 s si no |

Los despliegues dependen de la sesión de GitHub: se pueden apagar por separado (*Más → Funciones →
Despliegues en vivo*), pero no funcionan sin `gh`.

Cada sección se pliega con un clic en su encabezado. El contador azul «N hoy» indica las novedades del
día:
- en Revisión pedida y Mis PR, las PR actualizadas hoy;
- en Fusionadas, las fusionadas hoy;
- en Despliegues recientes, los que terminaron hoy.

---

## Nivel 8 — Cámara (presencia)

```bash
sudo apt install python3-opencv opencv-data swayidle wlopm
```

Necesita una webcam en `/dev/video0`. Viene **apagada**: actívala con la casilla *Presencia* del inicio o en
*Más → Funciones*.

**Para qué sirve:** bloquea la sesión y apaga la pantalla si no hay nadie frente al equipo.

**Cómo decide:**
1. `swayidle` avisa cuando no hay teclado ni ratón durante un rato (hasta 1 min).
2. Desde ese momento, cada 10 s la isla abre la cámara, busca una cara (OpenCV) y la vuelve a cerrar.
3. Si nadie aparece durante **N minutos** (5 por defecto), la píldora muestra *«Nadie frente a la
   pantalla»* con una cuenta atrás de 30 s. Mover el ratón la cancela.
4. Al terminar la cuenta atrás, bloquea con el bloqueo de Budgie (o `loginctl lock-session`) y apaga la
   pantalla con `wlopm --off`. Al volver a usar el teclado o el ratón, la pantalla se enciende.

**Nunca bloquea:**
- durante una llamada (requiere el nivel 2);
- si otra app está usando la cámara;
- si la cámara da error;
- fuera del horario o en pausa.

**Página Presencia:**
- **Minutos**: de 1 a 60.
- **Horario**: desde/hasta y días de la semana. Por defecto, de lunes a viernes de 08:00 a 18:00; la franja
  puede cruzar la medianoche.
- **Pausa**: 1 hora, hasta mañana o reanudar.
- **Probar cámara**: comprueba si te detecta.
- **Estado**: Vigilando, Te ve, Bloqueando, Fuera de horario, En pausa o Sin OpenCV. También se ve en la
  casilla del inicio y en una burbuja con un ojo.

**Mejor detección (opcional):** guarda el modelo YuNet `face_detection_yunet.onnx` en
`~/.local/share/isla-dinamica/`. Detecta mejor caras de perfil y con poca luz que el detector Haar que se
usa por defecto.

**Limitación:** si Chrome reproduce música o vídeo, el sistema no se considera inactivo y la presencia no
empieza a contar.

---

## Configuración guardada

Todo lo que cambias desde la isla se guarda en `~/.config/isla-dinamica/config.json`. Si una clave falta o
no es válida, se usa el valor por defecto.

| Clave | Por defecto | Para qué |
|---|---|---|
| `city` | `null` (según la zona horaria) | Ciudad del clima |
| `dock` | `{"edge": "top", "pos": 0.5}` | Borde y posición de la píldora |
| `features` | `{}` (todo encendido salvo `presence`) | Funciones encendidas o apagadas: `ms`, `github`, `deploys`, `weather`, `fx`, `git`, `netmon`, `sysmon`, `reminders`, `servers`, `downloads`, `audio`, `privacy`, `clock24`, `presence` |
| `collapsed` | `[]` | Secciones plegadas: `gh_review`, `gh_mine`, `gh_merged`, `dp_active`, `dp_recent`, `ms_teams`, `ms_outlook` |
| `git_folders` | `["~/Documentos/WM"]` | Carpetas que vigila *Proyectos* |
| `pomodoro` | `work 25, short 5, long 15, every 4, auto true` | Minutos de cada fase, cada cuántos enfoques toca el descanso largo y si avanza solo |
| `presence` | `minutes 5, warn 30, start 08:00, end 18:00, days [0..4]` | Presencia (los días van de 0 = lunes a 6 = domingo) |

Para depurar, ejecuta `ISLA_DEBUG=1 python3 isla.py`: muestra en la terminal lo que detecta cada servicio.

---

## Para desarrolladores

La estructura del código (qué hace cada carpeta y en qué sentido van las dependencias), las pruebas y cómo
añadir una página están en la sección «4. Desarrollo» del [README](../README.md).
