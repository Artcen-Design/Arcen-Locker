#!/bin/bash
# Lanza el backend del kiosco (Flask) y luego Chromium en modo kiosco
# apuntando a él. Pensado para ejecutarse al arrancar el Pi.

set -uo pipefail

APP_DIR="/home/pi/ArtcenKiosk"
LOG_FILE="$APP_DIR/kiosk_launch.log"
SERVER_URL="http://127.0.0.1:5000"

log() {
    echo "$(date '+%F %T') $1" | tee -a "$LOG_FILE"
}

cd "$APP_DIR" || { echo "No se encontró $APP_DIR" >> "$LOG_FILE"; exit 1; }

log "=== run_kiosk.sh iniciado (WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-<vacío>} XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-<vacío>}) ==="

# --- Servidor Flask ---
# Corre en un bucle: si server.py se cae (error de puerto serie, excepción
# no manejada, etc.) se reinicia solo en vez de dejar al kiosco sin backend.
(
  while true; do
    ./venv/bin/python server.py >> "$LOG_FILE" 2>&1
    log "server.py terminó (código $?), reiniciando en 2s..."
    sleep 2
  done
) &
SERVER_WATCHDOG_PID=$!

# --- Espera activa a que el servidor responda, en vez de un sleep fijo ---
log "Esperando a que el servidor responda en $SERVER_URL..."
READY=0
for i in $(seq 1 30); do
    if curl -sf "$SERVER_URL/api/config" > /dev/null 2>&1; then
        log "Servidor listo (intento $i)."
        READY=1
        break
    fi
    sleep 1
done
if [ "$READY" -ne 1 ]; then
    log "El servidor no respondió tras 30s, continuando de todos modos."
fi

# --- Espera a que el compositor Wayland esté realmente listo ---
# Lanzar Chromium antes de que exista el socket del compositor produce una
# pantalla en blanco silenciosa — Chromium en modo --app no muestra ningún
# error visible, simplemente no pinta nada. Esto es lo más probable detrás
# del comportamiento "a veces sí, a veces no".
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
log "Esperando al socket de Wayland (${WAYLAND_DISPLAY:-wayland-0}) en $RUNTIME_DIR..."
SOCKET_READY=0
for i in $(seq 1 20); do
    if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "$RUNTIME_DIR/${WAYLAND_DISPLAY}" ]; then
        log "Socket de Wayland listo (intento $i)."
        SOCKET_READY=1
        break
    fi
    sleep 0.5
done
if [ "$SOCKET_READY" -ne 1 ]; then
    log "ADVERTENCIA: no se detectó el socket de Wayland tras 10s, se intentará abrir Chromium igual."
fi
# Margen extra para que el compositor termine de inicializar justo después
# de crear el socket (a veces acepta conexiones un instante antes de poder
# componer frames de verdad).
sleep 1

# --- Navegador en modo Kiosco, con reintento si crashea al arrancar ---
while true; do
    log "Iniciando Chromium en modo Kiosco."
    /bin/chromium \
      --kiosk \
      --ozone-platform=wayland \
      --start-fullscreen \
      --noerrdialogs \
      --disable-infobars \
      --disable-session-crashed-bubble \
      --disable-pinch \
      --overscroll-history-navigation=0 \
      --app="$SERVER_URL/" >> "$LOG_FILE" 2>&1 &
    CHROMIUM_PID=$!
    CHROMIUM_START=$(date +%s)

    wait "$CHROMIUM_PID"
    CHROMIUM_EXIT=$?
    CHROMIUM_RUNTIME=$(( $(date +%s) - CHROMIUM_START ))
    log "Chromium terminó (código $CHROMIUM_EXIT) tras ${CHROMIUM_RUNTIME}s."

    # Si Chromium se cerró casi de inmediato, probablemente crasheó al
    # arrancar (p.ej. el compositor todavía no estaba listo del todo) en vez
    # de haber sido cerrado a propósito — reintenta unas veces en lugar de
    # dejar el kiosco colgado en pantalla en blanco hasta que alguien lo note.
    if [ "$CHROMIUM_RUNTIME" -lt 5 ]; then
        log "Chromium se cerró muy rápido tras iniciar, reintentando en 2s..."
        sleep 2
        continue
    fi
    break
done

kill "$SERVER_WATCHDOG_PID" 2>/dev/null
