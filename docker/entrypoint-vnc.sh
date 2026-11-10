#!/bin/bash
# Virtual display + VNC + noVNC (http://localhost:6080/vnc.html)
set -e
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

Xvfb :99 -screen 0 "${VNC_RESOLUTION:-1920x1080x24}" +extension GLX +render -noreset &
for _ in $(seq 1 50); do
    xdpyinfo -display :99 >/dev/null 2>&1 && break
    sleep 0.1
done

openbox &
x11vnc -display :99 -forever -shared -nopw -localhost -rfbport 5900 -quiet &
websockify --web /usr/share/novnc 6080 localhost:5900 &

exec /entrypoint.sh "$@"
