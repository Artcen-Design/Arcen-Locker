# ArtcenKiosk — Casillero Inteligente de Paquetería

Kiosco de autoservicio para depósito y recogida de paquetes, construido sobre
una Raspberry Pi 5 en modo kiosco, una placa controladora de casilleros
(protocolo serie) y un lector de códigos QR USB.

El servidor (Flask + SQLite) es la única autoridad sobre qué casillero se
abre y qué código de recogida es válido — el frontend nunca decide eso por
su cuenta, solo muestra lo que el servidor confirma.

## Hardware

- **Raspberry Pi 5**, corriendo Chromium en modo kiosco.
- **Placa controladora de casilleros** ("Chinese locker board"), conectada
  por USB-serie. Se le habla con un protocolo binario propio (ver
  [`hardware.py`](hardware.py)).
- **Lector de códigos QR USB**, funciona como teclado ("wedge"): al escanear,
  escribe el contenido del QR donde esté el foco y termina con Enter. No
  necesita driver ni integración especial — el frontend solo mantiene el
  campo de código enfocado.

## Arquitectura

```
Navegador (Chromium kiosco)
   │  fetch /api/...
   ▼
server.py (Flask)  ──lee──►  config.py (.env)
   │
   ├──► db.py ──► kiosk.db (SQLite: casilleros + auditoría)
   │
   ├──► hardware.py ──serie──► Placa de casilleros
   │
   └──► mailer.py ──SMTP──► Bandeja del cliente (código + QR)
```

- **`server.py`** — único punto de entrada HTTP. Sirve el frontend estático
  y expone la API. Traduce casillero lógico → canal físico, valida sesión de
  admin, y es el único lugar donde se decide si un código de recogida es
  válido.
- **`config.py`** — única fuente de configuración por sitio (lee `.env`).
- **`db.py`** — única fuente de estado persistente (SQLite): quién tiene qué
  casillero, y un registro de auditoría de cada depósito/recogida/apertura
  manual.
- **`hardware.py`** — único lugar que toca el puerto serie. No sabe qué es
  un "casillero", solo abre/consulta canales físicos.
- **`mailer.py`** — arma y envía por SMTP el correo de recogida (código +
  QR embebido). El servidor genera el QR (no el navegador), así que un
  fallo de envío queda registrado en los mismos logs que todo lo demás.

### Dependencias de frontend (`vendor/`)

Tailwind, Font Awesome, QRious y simple-keyboard están vendorizados
(copiados localmente) en vez de cargarse desde un CDN — el kiosco renderiza
sin depender de internet, y arranca más rápido al no esperar recursos
externos. Lo único que sigue necesitando conexión es el envío del correo de
recogida.

Tailwind en particular se compila (no es solo una descarga) porque el CDN
sirve un compilador JIT, no un CSS estático. Si se agregan clases de
Tailwind nuevas en `index.html` o cualquier archivo de `js/` y no aparecen
estilizadas, hay que recompilar:
```bash
tailwindcss -i vendor/tailwind.input.css -o vendor/tailwind.css --minify
```
(usa el binario standalone de `tailwindcss` v3.x — no hace falta Node/npm:
https://github.com/tailwindlabs/tailwindcss/releases)

### Frontend (`js/`)

| Archivo | Rol |
|---|---|
| `main.js` | Punto de entrada: carga configuración y estado, conecta los botones principales. |
| `utils/config.js` | URL base de la API; `NUM_LOCKERS` se pide al servidor. |
| `utils/state.js` | Estado en memoria de los casilleros (`GET /api/lockers`), sin lógica propia de validación. |
| `utils/hardware.js` | `waitForDoorClose()` — sondea el estado de la puerta hasta que se cierra. |
| `utils/csv.js` | Exporta un reporte de solo lectura del estado actual. |
| `widgets/modal.js` | Sistema genérico de modales + teclado en pantalla. |
| `widgets/admin.js` | Login, panel de administración, depósito, gestión de casilleros. |
| `widgets/customer.js` | Pantalla de recogida (código manual o escaneado). |

## Configurar un casillero nuevo desde cero

Guía completa, en orden, para dejar un Raspberry Pi nuevo funcionando como
kiosco de punta a punta — pensada para que alguien sin contexto previo del
proyecto la pueda seguir tal cual. Cada bloque se ejecuta en la terminal del
Pi (por SSH o directo).

### 1. Clonar el repositorio

```bash
cd /home/pi
git clone https://github.com/Sepu2002/ArtcenKiosk.git
cd ArtcenKiosk
```

### 2. Entorno de Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

### 3. Dar acceso al puerto serie sin `sudo`

```bash
sudo usermod -aG dialout $USER
sudo reboot
```

El grupo solo aplica en una sesión nueva — por eso el reboot. Después de
reiniciar, confirmar que aplicó:

```bash
groups
```

debe listar `dialout`. Si no aparece, repetir el `usermod` y reiniciar de
nuevo antes de seguir.

### 4. Crear el archivo de configuración

```bash
cd /home/pi/ArtcenKiosk
cp .env.example .env
```

### 5. Clave de sesión y contraseña de administrador

```bash
SECRET_KEY_VALUE=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY_VALUE|" .env

read -s -p "Contraseña de administrador: " ADMIN_PW
echo
ADMIN_HASH=$(echo "$ADMIN_PW" | ./venv/bin/python -c "
import sys
from werkzeug.security import generate_password_hash
print(generate_password_hash(sys.stdin.readline().strip()))
")
sed -i "s|^ADMIN_PASSWORD_HASH=.*|ADMIN_PASSWORD_HASH=$ADMIN_HASH|" .env
unset ADMIN_PW ADMIN_HASH SECRET_KEY_VALUE
```

Confirmar que ambas quedaron con valor (no vacías):

```bash
grep -E '^(SECRET_KEY|ADMIN_PASSWORD_HASH)=' .env
```

### 6. Cantidad y mapeo de casilleros

Cuántas puertas físicas tiene este sitio:

```bash
sed -i "/^NUM_LOCKERS=/d" .env
echo "NUM_LOCKERS=8" >> .env
```

Si algún puerto de la placa está dañado y las puertas se recablearon a otro
canal, mapear casillero lógico → canal físico en orden (ver `LOCKER_CHANNELS`
en la tabla de variables más abajo para el ejemplo completo). Si un
casillero existe pero no se puede usar, excluirlo:

```bash
sed -i "/^LOCKER_CHANNELS=/d" .env
echo "LOCKER_CHANNELS=1,2,3,4,5,6,7,8" >> .env
sed -i "/^DISABLED_LOCKERS=/d" .env
echo "DISABLED_LOCKERS=" >> .env
```

### 7. Puerto serie de la placa controladora

```bash
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Usar lo que aparezca ahí (normalmente `/dev/ttyUSB0`):

```bash
sed -i "/^SERIAL_PORT=/d" .env
echo "SERIAL_PORT=/dev/ttyUSB0" >> .env
```

### 8. Correo de recogida (código + QR)

Ejemplo con Gmail — requiere verificación en 2 pasos activada en esa cuenta
y una [App Password](https://myaccount.google.com/apppasswords) generada
específicamente (no sirve la contraseña normal de la cuenta):

```bash
sed -i "/^SMTP_HOST=/d" .env
echo "SMTP_HOST=smtp.gmail.com" >> .env
sed -i "/^SMTP_PORT=/d" .env
echo "SMTP_PORT=587" >> .env
sed -i "/^SMTP_USERNAME=/d" .env
echo "SMTP_USERNAME=correo@gmail.com" >> .env
sed -i "/^SMTP_PASSWORD=/d" .env
echo "SMTP_PASSWORD=contraseña-de-aplicación-de-16-caracteres" >> .env
```

Sin esto configurado, el depósito sigue funcionando con normalidad, pero el
envío de correo falla silenciosamente (queda en el log) y hay que mostrarle
el código QR en pantalla al cliente como respaldo.

### 9. Marca del cliente (logo, color) — opcional

Copiar el/los archivo(s) de logo a la carpeta `branding/` del proyecto (por
`scp` desde otra máquina, o USB — ver `branding/README.md`), luego:

```bash
sed -i "/^BRAND_LOGO=/d" .env
echo "BRAND_LOGO=branding/logo_a.png" >> .env
sed -i "/^BRAND_LOGO_DARK=/d" .env
echo "BRAND_LOGO_DARK=branding/logo_b.png" >> .env
sed -i "/^BRAND_COLOR=/d" .env
echo "BRAND_COLOR=#111827" >> .env
sed -i "/^BRAND_FOOTER=/d" .env
echo "BRAND_FOOTER=soporte@cliente.com" >> .env
```

`BRAND_LOGO_DARK` es opcional (si se omite, el modo oscuro reutiliza
`BRAND_LOGO`), igual que `BRAND_FOOTER`. Sin nada de esto, el kiosco se ve
con el look por defecto (sin logo, botón azul, sin pie de página).

### 10. Probar el servidor manualmente

```bash
./venv/bin/python server.py
```

Debe arrancar sin errores y mostrar `Frontend + API listos en
http://127.0.0.1:5000/`. En otra terminal, confirmar que responde:

```bash
curl http://127.0.0.1:5000/api/lockers
```

`Ctrl+C` para detenerlo una vez confirmado — el arranque automático (paso
siguiente) es el que lo deja corriendo de verdad.

### 11. Arranque automático al iniciar el Pi

```bash
chmod +x /home/pi/ArtcenKiosk/run_kiosk.sh
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/kiosk.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=ArtcenKiosk
Exec=/home/pi/ArtcenKiosk/run_kiosk.sh
X-GNOME-Autostart-enabled=true
EOF
```

Esto asume que el Pi ya está configurado para iniciar sesión automáticamente
en el escritorio (`raspi-config` → System Options → Boot / Auto Login →
Desktop Autologin) — sin eso, nada dispara `run_kiosk.sh`. Ver "Despliegue
en el kiosco" más abajo para el detalle de qué hace ese script paso a paso.

### 12. Reiniciar y verificar

```bash
sudo reboot
```

Después de reiniciar, Chromium debería abrir solo en pantalla completa
mostrando el kiosco. Si algo falla, el primer lugar donde mirar es:

```bash
tail -50 /home/pi/ArtcenKiosk/kiosk_launch.log
```

Para actualizar el código más adelante (no hace falta repetir nada de lo
anterior, salvo que cambien las dependencias):

```bash
cd /home/pi/ArtcenKiosk
git pull
pkill -f "venv/bin/python server.py"   # el watchdog de run_kiosk.sh lo reinicia solo
```

## Variables de entorno (`.env`)

| Variable | Default | Descripción |
|---|---|---|
| `NUM_LOCKERS` | `8` | Cantidad de casilleros de este sitio. |
| `LOCKER_CHANNELS` | `1..NUM_LOCKERS` | Mapeo casillero → canal físico de la placa, en orden. Se usa cuando un puerto dañado obliga a recablear a otros canales (ej. `2,3,4,5`). |
| `DISABLED_LOCKERS` | *(vacío)* | IDs de casilleros que existen pero están fuera de servicio (ej. `1` o `1,4`). Se excluyen de todo flujo y nunca se sondean por serie. |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Puerto serie de la placa. |
| `BAUD_RATE` | `9600` | Velocidad del puerto serie. |
| `PICKUP_CODE_LENGTH` | `8` | Longitud (caracteres hex) del código de recogida generado. |
| `SECRET_KEY` | *(aleatoria)* | Clave de sesión de Flask — generar una fija en producción o las sesiones de admin no sobreviven un reinicio. |
| `ADMIN_PASSWORD_HASH` | *(admin123 por defecto)* | Hash de la contraseña de administrador — generar con `set_admin_password.py`. |
| `SESSION_LIFETIME_MINUTES` | `30` | Duración de la sesión de admin. |
| `PICKUP_RATE_LIMIT_ATTEMPTS` | `5` | Intentos de código de recogida permitidos por IP... |
| `PICKUP_RATE_LIMIT_WINDOW_SECONDS` | `60` | ...dentro de esta ventana, antes de bloquear temporalmente. |
| `DB_PATH` | `kiosk.db` | Ruta de la base de datos SQLite. |
| `LOG_FILE` | `action_log.log` | Ruta del archivo de log. |
| `SMTP_HOST` | *(vacío)* | Servidor SMTP para el correo de recogida. Vacío = envío deshabilitado (se usa solo el QR de respaldo en pantalla). |
| `SMTP_PORT` | `587` | Puerto SMTP. |
| `SMTP_USERNAME` | *(vacío)* | Usuario SMTP (normalmente el correo completo). |
| `SMTP_PASSWORD` | *(vacío)* | Contraseña o App Password SMTP. |
| `SMTP_FROM_EMAIL` | `SMTP_USERNAME` | Dirección remitente. |
| `SMTP_FROM_NAME` | `Kiosco de Paquetería` | Nombre remitente. |
| `BRAND_NAME` | *(vacío)* | Solo se usa como texto alternativo (accesibilidad) del logo — no se muestra en pantalla. |
| `BRAND_LOGO` | *(vacío)* | Ruta relativa al logo en modo claro dentro de `branding/` (ej. `branding/logo_a.png`). Vacío = sin encabezado de marca. |
| `BRAND_LOGO_DARK` | *(vacío)* | Logo en modo oscuro. Vacío = reutiliza `BRAND_LOGO` en ambos modos. |
| `BRAND_COLOR` | `#2563eb` | Color del botón principal y acentos de marca. |
| `BRAND_FOOTER` | *(vacío)* | Texto de pie de página (contacto, "powered by", etc). Vacío = sin pie de página. |

`config.py` es la única parte del código que lee estas variables — nada más
debería tocar `os.environ` directamente. Con todas las `BRAND_*` vacías el
kiosco se ve exactamente igual que antes de que existiera esta función.

## API

Toda la API vive bajo `/api/`. Las rutas `/api/admin/*` requieren sesión de
administrador (`POST /api/admin/login`); el resto son públicas.

| Ruta | Método | Descripción |
|---|---|---|
| `/api/config` | GET | `{ numLockers }` |
| `/api/lockers` | GET | Estado combinado (hardware + BD) de todos los casilleros. Incluye `pickupCode` solo si hay sesión de admin. |
| `/api/lockers/<id>/status` | GET | Estado físico de un casillero (usado para el sondeo de puerta cerrada). |
| `/api/admin/login` | POST | `{ password }` → inicia sesión. |
| `/api/admin/logout` | POST | Cierra sesión. |
| `/api/admin/session` | GET | `{ isAdmin }` |
| `/api/admin/deposit` | POST | `{ bayId, email }` → abre el casillero y genera el código de recogida. |
| `/api/admin/deposit/confirm` | POST | `{ bayId }` → confirma el depósito una vez cerrada la puerta. |
| `/api/admin/deposit/send-email` | POST | `{ bayId }` → envía el correo de recogida (código + QR) por SMTP. |
| `/api/admin/open` | POST | `{ bayId }` → apertura manual (mantenimiento). |
| `/api/admin/clear` | POST | `{ bayId }` → libera un casillero. |
| `/api/pickup` | POST | `{ code }` → valida el código y abre el casillero (con límite de intentos). |
| `/api/pickup/confirm` | POST | `{ bayId, code }` → confirma la recogida una vez cerrada la puerta. |
| `/api/log` | POST | Registra un evento del frontend en el log del servidor. |

## Seguridad

- La contraseña de admin y los códigos de recogida se validan **solo en el
  servidor** — nunca en el navegador.
- Los códigos de recogida son aleatorios (`secrets.token_hex`), no derivados
  de la hora.
- `/api/pickup` tiene límite de intentos por IP para evitar fuerza bruta.
- La sesión de admin es una cookie firmada por Flask con expiración
  configurable.
- El estado vive en SQLite en el servidor, no en `localStorage` del
  navegador — sobrevive a que se borre la caché y queda un registro de
  auditoría (`events` en `kiosk.db`).

## Despliegue en el kiosco (Raspberry Pi)

`run_kiosk.sh` arranca todo al iniciar el Pi:

1. Lanza `server.py` en un bucle (se reinicia solo si se cae).
2. Espera activamente a que el servidor responda.
3. Espera a que el socket de Wayland del compositor exista (evita pantalla
   en blanco por arrancar Chromium antes de tiempo).
4. Abre Chromium en modo kiosco apuntando a `http://127.0.0.1:5000/`, y lo
   reintenta si se cierra casi de inmediato tras arrancar.

Se dispara vía `~/.config/autostart/kiosk.desktop` (autostart XDG), que
apunta a `/home/pi/ArtcenKiosk/run_kiosk.sh`. Todo lo que imprime queda en
`kiosk_launch.log`, dentro de la carpeta del proyecto.

## Limitaciones conocidas / próximos pasos

- El servidor Flask corre con el servidor de desarrollo integrado (`app.run`)
  — suficiente para un kiosco de un solo sitio, pero no pensado para alta
  concurrencia. Si esto se convierte en algo con más tráfico, pasar a un WSGI
  de producción (gunicorn/waitress) sería el siguiente paso natural.
- El correo se envía por SMTP directo (`smtplib`), sin cola ni reintentos —
  si el proveedor de correo está caído en ese instante, ese envío puntual se
  pierde (queda registrado en el log, y el operador ve el QR de respaldo en
  pantalla). Para volumen alto, un servicio transaccional (SES, Postmark,
  etc.) con reintentos sería más robusto que SMTP directo.
- Gmail limita el envío a ~500 correos/día en una cuenta normal — de sobra
  para un kiosco, pero vale la pena saberlo si el volumen crece mucho.
- Pensado para un único kiosco: todo corre en `127.0.0.1` y el panel de
  administración solo es accesible desde la pantalla del propio kiosco. No
  hay administración remota ni sincronización entre sitios — fue una
  decisión consciente para este despliegue, no una limitación técnica del
  diseño (agregarlo más adelante implicaría sumar autenticación de red y
  HTTPS reales).
