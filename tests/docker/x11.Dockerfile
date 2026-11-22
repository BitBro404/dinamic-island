# Entorno X11 mínimo para probar la isla sin layer-shell ni compositor (como LXDE/Openbox).
# Uso: tests/x11_smoke.sh
FROM debian:trixie-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 \
        xvfb openbox xdotool x11-utils imagemagick dbus dbus-x11 fonts-dejavu-core \
        adwaita-icon-theme librsvg2-common x11-xserver-utils upower network-manager \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m isla && mkdir -p /run/dbus
COPY tests/docker/x11_run.sh /usr/local/bin/x11_run.sh
# el bus del sistema (lo tiene toda distro real) necesita root; la isla corre como usuario normal
ENTRYPOINT ["sh", "-c", "dbus-daemon --system --fork && exec runuser -u isla -- /usr/local/bin/x11_run.sh"]
