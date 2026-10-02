# Arcen Locker — Casillero Inteligente de Paquetería

Kiosco de autoservicio para depósito y recogida de paquetes, construido sobre
una Raspberry Pi 5 en modo kiosco, una placa controladora de casilleros
(protocolo serie) y un lector de códigos QR USB.

El servidor (Flask + SQLite) es la única autoridad sobre qué casillero se
abre y qué código de recogida es válido — el frontend nunca decide eso por
su cuenta, solo muestra lo que el servidor confirma.

- **Repositorio:** https://github.com/Artcen-Design/Arcen-Locker
- **Nombre anterior:** el proyecto se llamó *ArtcenKiosk* y vivía en un
  repositorio personal (`Sepu2002/ArtcenKiosk`) que ya no es la fuente
  oficial. El nombre viejo sobrevive en un solo lugar: la carpeta de
  instalación en el Pi (`/home/pi/ArtcenKiosk`), porque `run_kiosk.sh` y
  `kiosk.service` la tienen escrita a mano. Ver
  [Rutas y nombre de carpeta](#rutas-y-nombre-de-carpeta).

## Índice

1. [Traspaso: lo primero que hay que saber](#traspaso-lo-primero-que-hay-que-saber)
2. [Hardware](#hardware)
3. [Arquitectura](#arquitectura)
4. [Configurar un casillero nuevo desde cero](#configurar-un-casillero-nuevo-desde-cero)
5. [Configuración del sitio actual](#configuración-del-sitio-actual)
6. [Variables de entorno](#variables-de-entorno)
7. [API y flujos](#api-y-flujos)
8. [Seguridad y privacidad](#seguridad-y-privacidad)
9. [Despliegue en el kiosco](#despliegue-en-el-kiosco)
10. [Operación diaria](#operación-diaria)
11. [Solución de problemas](#solución-de-problemas)
12. [Desarrollo local sin hardware](#desarrollo-local-sin-hardware)
13. [Checklist de verificación](#checklist-de-verificación)
14. [Limitaciones conocidas y próximos pasos](#limitaciones-conocidas-y-próximos-pasos)

---

## Traspaso: lo primero que hay que saber

Esta sección es para quien herede el proyecto. El resto del documento explica
cómo funciona y cómo se opera; aquí está lo que **no** vive en el repositorio
y por lo tanto no se descubre leyendo el código.

### Qué vive fuera del repositorio

| Qué | Dónde | Si se pierde |
|---|---|---|
| Configuración del sitio y secretos (`.env`) | Solo en el Pi: `/home/pi/ArtcenKiosk/.env`. Git lo ignora a propósito. | Recuperable, salvo la contraseña de admin actual (se guarda como hash, no se puede leer): hay que definir una nueva. Los valores no secretos están en [Configuración del sitio actual](#configuración-del-sitio-actual). |
| Base de datos (`kiosk.db`): paquetes depositados con su código de recogida, e historial de eventos | Solo en el Pi: `/home/pi/ArtcenKiosk/kiosk.db`. Git la ignora. | **No recuperable.** Los paquetes que estén dentro en ese momento pierden su código; habría que abrir los casilleros a mano y volver a registrarlos. Ver [Respaldos](#respaldos). |
| Usuario y contraseña del Pi (SSH y escritorio) | No están en el repositorio ni deben estarlo. | Guardarlos en el gestor de contraseñas de la empresa. |
| Cuenta de Gmail que envía los correos | `SMTP_USERNAME` del `.env` (`artcendesignkio@gmail.com`). | Sin ella no salen correos (el kiosco sigue funcionando y muestra el QR en pantalla). |

### Cuentas y accesos a transferir

- [ ] **GitHub.** El repositorio vive en la organización `Artcen-Design`.
  Confirmar que al menos dos personas tengan rol de administrador. El
  repositorio personal anterior (`Sepu2002/ArtcenKiosk`) hay que archivarlo o
  borrarlo cuando el Pi ya apunte al nuevo, para que nadie siga haciendo
  `git pull` desde ahí.
- [ ] **Gmail remitente** (`artcendesignkio@gmail.com`). Pasar la propiedad a
  la empresa: correo y teléfono de recuperación, verificación en dos pasos. Al
  traspasar, **rotar la App Password**: generar una nueva en
  https://myaccount.google.com/apppasswords, actualizar `SMTP_PASSWORD` en el
  `.env`, reiniciar el servidor y borrar la anterior. Así quedan sin efecto
  todas las copias viejas.
- [ ] **Contraseña de administrador del kiosco.** Definir una nueva (ver
  [Operación diaria](#operación-diaria)) y guardarla en el gestor de
  contraseñas.
- [ ] **Acceso al Pi.** Usuario `pi`, nombre de host `raspberrypi`. Si la
  contraseña se compartió durante el desarrollo, cambiarla con `passwd`.
- [ ] **Respaldo inicial** de `.env` y `kiosk.db` (ver [Respaldos](#respaldos)).
- [ ] **EmailJS.** Era el servicio de correo del prototipo original. Ya no se
  usa: el código se eliminó y el envío es por SMTP desde el servidor. La cuenta
  vieja se puede ignorar.

### Migrar el Pi existente al repositorio de la organización

El Pi que está en producción sigue apuntando al repositorio personal anterior.
El repositorio nuevo se creó con un `Initial commit` (no es un push del
historial viejo), así que un `git pull` normal fallaría con *refusing to merge
unrelated histories*. Lo que funciona es repuntar el remoto y alinear los
archivos versionados con `git reset --hard`, que **no** toca lo que git ignora
(`.env`, `kiosk.db`, `venv/`, logs).

**Paso 1 — en un PC, verificar que `run_kiosk.sh` es ejecutable en el repo
nuevo:**

```bash
git ls-files --stage run_kiosk.sh
```

Debe empezar con `100755`. Si dice `100644`, corregirlo antes de migrar. El bit
se pierde al crear repositorios desde Windows, y sin él el kiosco no arranca
tras el siguiente reinicio (el autostart no puede ejecutar el script):

```bash
git update-index --chmod=+x run_kiosk.sh
git commit -m "run_kiosk.sh ejecutable"
git push
```

**Paso 2 — solo si el repositorio es privado:** el Pi necesita credenciales de
solo lectura. Lo más limpio es una *deploy key*:

```bash
ssh-keygen -t ed25519 -C "arcen-locker-pi" -f ~/.ssh/arcen_locker_deploy -N ""
cat ~/.ssh/arcen_locker_deploy.pub
```

Pegar la clave pública en GitHub → repositorio → Settings → Deploy keys (sin
marcar *Allow write access*) y crear `~/.ssh/config`:

```
Host github-arcen-locker
    HostName github.com
    User git
    IdentityFile ~/.ssh/arcen_locker_deploy
    IdentitiesOnly yes
```

Probar con `ssh -T git@github-arcen-locker` (la primera vez pide aceptar la
huella de github.com: responder `yes`). En el paso 3 se usa entonces la URL
`git@github-arcen-locker:Artcen-Design/Arcen-Locker.git` en lugar de la https.

**Paso 3 — en el Pi:**

```bash
cd /home/pi/ArtcenKiosk
git status --short
```

Debe salir vacío o solo con archivos sin seguimiento (`??`, por ejemplo
`kiosk_launch.log`, que el `.gitignore` anterior no ignoraba; el
`reset --hard` no los toca). Si aparecen archivos modificados (`M`),
revisarlos con `git diff`: el siguiente comando los descarta.

```bash
git remote set-url origin https://github.com/Artcen-Design/Arcen-Locker.git
git fetch origin
git reset --hard origin/main
ls -l run_kiosk.sh
git pull
```

`ls -l` debe mostrar `-rwxr-xr-x` (si no, `chmod +x run_kiosk.sh`) y `git pull`
debe responder `Already up to date.` Para cerrar, reiniciar (`sudo reboot`) y
comprobar que el kiosco levanta solo: a partir de ahí el Pi ya no depende del
repositorio personal.

### Respaldos

El Pi es la única copia de `.env` y `kiosk.db`. Una tarjeta SD corrupta se los
lleva. Copiar ambos fuera del Pi cuando cambie algo importante, y la base de
datos periódicamente.

En el Pi, copia consistente de la base de datos (no copiar el archivo "a mano"
mientras el servidor escribe):

```bash
cd /home/pi/ArtcenKiosk
./venv/bin/python - <<'EOF'
import sqlite3
origen = sqlite3.connect('kiosk.db')
destino = sqlite3.connect('kiosk_respaldo.db')
origen.backup(destino)
destino.close(); origen.close()
EOF
```

Desde otro equipo. El `.env` contiene secretos: guardarlo solo en el gestor de
contraseñas de la empresa, nunca en el repositorio ni por correo.

```bash
scp pi@raspberrypi:/home/pi/ArtcenKiosk/kiosk_respaldo.db .
scp pi@raspberrypi:/home/pi/ArtcenKiosk/.env ./env-respaldo
```

`*.db` está en `.gitignore`, así que `kiosk_respaldo.db` no se sube por
accidente. La copia más completa es clonar la tarjeta SD entera desde un PC una
vez que el kiosco esté estable: se recupera todo (sistema, `.env`, base de
datos) en minutos.

---

## Hardware

- **Raspberry Pi 5** con Raspberry Pi OS (Debian 13 "trixie") y escritorio
  Wayland (labwc), corriendo Chromium en modo kiosco. Alimentarla con la
  **fuente oficial de 27 W (5 V / 5 A)**: con fuentes menores el Pi limita la
  corriente de los puertos USB y los periféricos USB (táctil, lector,
  adaptador serie) fallan de forma intermitente.
- **Placa controladora de casilleros** ("Chinese locker board"), conectada por
  USB-serie (normalmente `/dev/ttyUSB0`, 9600 baudios). Se le habla con un
  protocolo binario propio (ver abajo y [`hardware.py`](hardware.py)).
- **Lector de códigos QR USB**, funciona como teclado ("wedge"): al escanear,
  escribe el contenido del QR donde esté el foco. No necesita driver ni
  integración especial — el frontend solo mantiene el campo de código
  enfocado. El lector debe enviar **Enter** al final del escaneo (así se envía
  solo); si el suyo no lo hace, reconfigurarlo o el cliente tendrá que tocar
  "Enviar Código".
- **Pantalla táctil.** Toda la interfaz está pensada para toque; el teclado en
  pantalla (simple-keyboard) aparece en los campos de texto.

En la placa del sitio actual el **puerto 1 está dañado**: las 4 puertas se
recablearon a los canales 2 a 5 y se compensa por configuración
(`LOCKER_CHANNELS=2,3,4,5`), sin tocar código.

### Protocolo serie de la placa

Referencia para depurar o reemplazar la placa. Toda la lógica está en
[`hardware.py`](hardware.py) y no la usa nada más.

| Campo del paquete enviado | Bytes | Valor |
|---|---|---|
| Cabecera | 4 | `57 4B 4C 59` ("WKLY") |
| Longitud | 1 | Largo total del paquete (cabecera + longitud + payload + checksum) |
| Dirección de placa | 1 | `01` |
| Comando | 1 | `82` abrir, `83` consultar estado |
| Canal | 1 | Número de canal físico de la placa |
| Checksum | 1 | XOR de los tres bytes del payload (dirección, comando, canal) |

- **Consulta de estado (`83`):** la placa responde unos 11 bytes. Se validan la
  cabecera, el byte 6 (`83`), el byte 8 (el canal) y se lee el estado en el
  byte 9 (posiciones desde 0): `01` = cerrada (`LOCKED`), `00` = abierta
  (`UNLOCKED`). Los demás bytes no se interpretan.
- **Abrir (`82`):** la placa **no responde**; el código solo comprueba que la
  escritura al puerto no falló.
- **Tiempos:** cada comando abre y cierra la conexión serie (`timeout` de 1 s).
  Consultar un casillero toma ≈0,25 s; abrir toma ≈1 s porque se espera el
  timeout de una respuesta que nunca llega. El panel de admin consulta todos
  los casilleros en serie, así que su tiempo de carga crece linealmente con el
  número de puertas (≈1 s con 4).

---

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

El navegador y Python se comunican solo por HTTP y JSON, siempre en el mismo
origen (`http://127.0.0.1:5000`): el navegador pide, el servidor responde, y el
servidor nunca empuja nada por su cuenta. Para saber cuándo se cerró una puerta
el frontend **sondea** cada 2 s (`GET /api/lockers/<id>/status`); no hay
WebSockets.

### Estructura del repositorio

```
Arcen-Locker/
├── server.py              Flask: API y servidor del frontend
├── config.py              Lectura de .env (único lugar que toca os.environ)
├── db.py                  SQLite: casilleros y eventos
├── hardware.py            Protocolo serie de la placa
├── mailer.py              Correo de recogida por SMTP
├── set_admin_password.py  Utilidad: genera ADMIN_PASSWORD_HASH
├── run_kiosk.sh           Arranque en el Pi: servidor + Chromium
├── kiosk.service          Unidad systemd alternativa (no es la que se usa)
├── index.html             Único HTML
├── js/  css/              Frontend propio
├── vendor/                Tailwind compilado, Font Awesome, QRious, simple-keyboard
├── branding/              Logos del cliente (ver branding/README.md)
├── images/                Fondo de pantalla
├── tailwind.config.js     Configuración para recompilar vendor/tailwind.css
├── requirements.txt       Dependencias de Python
└── .env.example           Plantilla de configuración
```

Se generan en el Pi y git los ignora: `.env`, `kiosk.db`, `action_log.log*`,
`kiosk_launch.log*`, `venv/`.

### Dependencias de frontend (`vendor/`)

Tailwind, Font Awesome, QRious y simple-keyboard están vendorizados
(copiados localmente) en vez de cargarse desde un CDN — el kiosco renderiza
sin depender de internet, y arranca más rápido al no esperar recursos
externos. Lo único que sigue necesitando conexión es el envío del correo de
recogida.

Tailwind en particular se compila (no es solo una descarga) porque el CDN
sirve un compilador JIT, no un CSS estático. `vendor/tailwind.css` está
versionado, así que el Pi no necesita compilar nada. Solo en un equipo de
desarrollo, si se agregan clases de Tailwind nuevas en `index.html` o
cualquier archivo de `js/` y no aparecen estilizadas, hay que recompilar:

```bash
tailwindcss -i vendor/tailwind.input.css -o vendor/tailwind.css --minify
```

(usa el binario standalone de `tailwindcss` v3.x — no hace falta Node/npm:
https://github.com/tailwindlabs/tailwindcss/releases)

### Frontend (`js/`)

| Archivo | Rol |
|---|---|
| `main.js` | Punto de entrada: carga configuración y estado, aplica la marca (logo, color, pie), conecta los botones principales y el modo claro/oscuro. |
| `utils/config.js` | URL base de la API y configuración del sitio que pide el servidor (`/api/config`): número de casilleros y marca. |
| `utils/state.js` | Estado en memoria de los casilleros (`GET /api/lockers`), sin lógica propia de validación. |
| `utils/hardware.js` | `waitForDoorClose()` — sondea el estado de la puerta hasta que se cierra. |
| `utils/csv.js` | Exporta un reporte de solo lectura del estado actual. |
| `widgets/modal.js` | Sistema genérico de modales + teclado en pantalla. |
| `widgets/admin.js` | Login, panel de administración, depósito, gestión de casilleros. |
| `widgets/customer.js` | Pantalla de recogida (código manual o escaneado). |

---

## Configurar un casillero nuevo desde cero

Guía completa, en orden, para dejar un Raspberry Pi nuevo funcionando como
kiosco de punta a punta — pensada para que alguien sin contexto previo del
proyecto la pueda seguir tal cual. Cada bloque se ejecuta en la terminal del
Pi (por SSH o directo).

Requisitos previos: Raspberry Pi OS con escritorio, inicio de sesión
automático en el escritorio (`raspi-config` → System Options → Boot / Auto
Login → Desktop Autologin), internet para instalar y para el correo, y acceso
al repositorio.

### 1. Clonar el repositorio

```bash
cd /home/pi
git clone https://github.com/Artcen-Design/Arcen-Locker.git ArtcenKiosk
cd ArtcenKiosk
```

La carpeta se llama `ArtcenKiosk` a propósito (ver
[Rutas y nombre de carpeta](#rutas-y-nombre-de-carpeta)). Si el repositorio es
privado, clonar con la URL SSH y la deploy key descrita en
[Migrar el Pi existente](#migrar-el-pi-existente-al-repositorio-de-la-organización).

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
nuevo antes de seguir. **Nunca** correr el servidor con `sudo` como atajo (ver
[Solución de problemas](#solución-de-problemas)).

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

Importante: si `ADMIN_PASSWORD_HASH` queda vacío, el servidor arranca igual
pero el panel de administrador queda con la contraseña por defecto `admin123`.

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

Aviso sobre estos comandos: se usa "borrar la línea y agregarla" en vez de un
simple `sed s///` porque este último **no hace nada** si la línea no existe en
el `.env` (por ejemplo, si se copió de una versión vieja de `.env.example`), y
el cambio se pierde en silencio.

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
envío de correo falla (queda en el log) y hay que mostrarle el código QR en
pantalla al cliente como respaldo.

### 9. Marca del cliente (logo, color) — opcional

Los logos viven en `branding/`, que **está versionada** y compartida por todos
los sitios. Para no pisar el logo de otro sitio, usar nombres de archivo
distintos por cliente (por ejemplo `branding/torres-del-parque_claro.png` y
`branding/torres-del-parque_oscuro.png`): el `.env` de cada Pi decide cuál se
usa. Subirlos por git (y `git pull` en el Pi) o copiarlos con `scp`. Luego:

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
con el look por defecto (sin logo, botón azul, sin pie de página). Detalles de
los logos en [`branding/README.md`](branding/README.md).

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

Esto asume el inicio de sesión automático en el escritorio de los requisitos
previos — sin eso, nada dispara `run_kiosk.sh`. **No habilitar a la vez
`kiosk.service`**: ambos lanzarían el servidor y chocarían en el puerto 5000
(ver [Despliegue en el kiosco](#despliegue-en-el-kiosco)).

### 12. Reiniciar y verificar

```bash
sudo reboot
```

Después de reiniciar, Chromium debería abrir solo en pantalla completa
mostrando el kiosco. Si algo falla, el primer lugar donde mirar es:

```bash
tail -50 /home/pi/ArtcenKiosk/kiosk_launch.log
```

Con el kiosco arriba, recorrer el [Checklist de verificación](#checklist-de-verificación)
(sobre todo abrir cada puerta una por una para confirmar que el casillero N
abre la puerta física N).

---

## Configuración del sitio actual

Último estado conocido del kiosco en producción (valores **no** secretos). La
fuente de verdad es siempre el `.env` del Pi.

| Variable | Valor | Nota |
|---|---|---|
| `NUM_LOCKERS` | `4` | La instalación tiene 4 puertas. |
| `LOCKER_CHANNELS` | `2,3,4,5` | El puerto 1 de la placa está dañado; las puertas se recablearon un canal más allá. |
| `DISABLED_LOCKERS` | *(vacío)* | Las 4 puertas funcionan. |
| `SERIAL_PORT` | `/dev/ttyUSB0` | |
| `BRAND_LOGO` / `BRAND_LOGO_DARK` | `branding/logo_a.png` / `branding/logo_b.png` | Logo de Artcen Design para modo claro / oscuro. |
| `BRAND_COLOR` | `#111827` | Casi negro, a juego con el logo. |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com` / `587` | |
| `SMTP_USERNAME` | `artcendesignkio@gmail.com` | Cuenta de Gmail con App Password. |

Para ver el `.env` real del Pi sin exponer los secretos:

```bash
grep -E '^[A-Z_]+=' /home/pi/ArtcenKiosk/.env | grep -vE '^(SECRET_KEY|ADMIN_PASSWORD_HASH|SMTP_PASSWORD)='
```

---

## Variables de entorno

Todas se definen en el archivo `.env` (copia de `.env.example`). Cualquier
cambio requiere reiniciar el servidor (ver [Operación diaria](#operación-diaria)):
el `.env` se lee una sola vez al arrancar.

| Variable | Default | Descripción |
|---|---|---|
| `NUM_LOCKERS` | `8` | Cantidad de casilleros de este sitio. |
| `LOCKER_CHANNELS` | `1..NUM_LOCKERS` | Mapeo casillero → canal físico de la placa, en orden. Se usa cuando un puerto dañado obliga a recablear a otros canales (ej. `2,3,4,5`: el casillero 1 habla con el canal 2, el 2 con el 3, etc.). Debe tener tantos valores como `NUM_LOCKERS`; si no, el servidor imprime una advertencia. |
| `DISABLED_LOCKERS` | *(vacío)* | IDs de casilleros que existen pero están fuera de servicio (ej. `1` o `1,4`). Se excluyen de todo flujo y nunca se sondean por serie. |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Puerto serie de la placa. |
| `BAUD_RATE` | `9600` | Velocidad del puerto serie. |
| `PICKUP_CODE_LENGTH` | `8` | Longitud (caracteres hex) del código de recogida generado. Se redondea hacia abajo al número par más cercano; mínimo 4. |
| `SECRET_KEY` | *(aleatoria)* | Clave de sesión de Flask — generar una fija en producción o las sesiones de admin no sobreviven un reinicio. |
| `ADMIN_PASSWORD_HASH` | *(admin123 por defecto)* | Hash de la contraseña de administrador — generar con `set_admin_password.py`. **Si queda vacío, la contraseña del panel de admin es `admin123`.** |
| `SESSION_LIFETIME_MINUTES` | `30` | Duración de la sesión de admin. |
| `PICKUP_RATE_LIMIT_ATTEMPTS` | `5` | Intentos de código de recogida permitidos por IP... |
| `PICKUP_RATE_LIMIT_WINDOW_SECONDS` | `60` | ...dentro de esta ventana, antes de bloquear temporalmente. |
| `DB_PATH` | `kiosk.db` | Ruta de la base de datos SQLite. |
| `LOG_FILE` | `action_log.log` | Ruta del archivo de log del servidor (rota solo: 1 MB × 5 archivos). |
| `SMTP_HOST` | *(vacío)* | Servidor SMTP para el correo de recogida. Vacío = envío deshabilitado (se usa solo el QR de respaldo en pantalla). |
| `SMTP_PORT` | `587` | Puerto SMTP (con STARTTLS). |
| `SMTP_USERNAME` | *(vacío)* | Usuario SMTP (normalmente el correo completo). |
| `SMTP_PASSWORD` | *(vacío)* | Contraseña o App Password SMTP. |
| `SMTP_FROM_EMAIL` | `SMTP_USERNAME` | Dirección remitente. |
| `SMTP_FROM_NAME` | `Kiosco de Paquetería` | Nombre remitente. |
| `BRAND_NAME` | *(vacío)* | Solo se usa como texto alternativo (accesibilidad) del logo — no se muestra en pantalla. |
| `BRAND_LOGO` | *(vacío)* | Ruta relativa al logo en modo claro dentro de `branding/` (ej. `branding/logo_a.png`). Vacío = sin encabezado de marca. |
| `BRAND_LOGO_DARK` | *(vacío)* | Logo en modo oscuro. Vacío = reutiliza `BRAND_LOGO` en ambos modos. |
| `BRAND_COLOR` | `#2563eb` | Color del botón principal de la pantalla de inicio. |
| `BRAND_FOOTER` | *(vacío)* | Texto de pie de página (contacto, "powered by", etc). Vacío = sin pie de página. |

`config.py` es la única parte del código que lee estas variables — nada más
debería tocar `os.environ` directamente. Con todas las `BRAND_*` vacías el
kiosco usa el look por defecto.

---

## API y flujos

Toda la API vive bajo `/api/`. Las rutas `/api/admin/*` requieren sesión de
administrador (`POST /api/admin/login`); el resto son públicas. Las
respuestas son JSON con `success` y, si falló, `error`. Códigos usados: `400`
datos inválidos, `401` sin sesión de admin, `404` no existe / código inválido,
`409` casillero ocupado o fuera de servicio, `429` demasiados intentos, `500`
fallo de comunicación con la placa.

| Ruta | Método | Descripción |
|---|---|---|
| `/api/config` | GET | Configuración del sitio para el frontend: `numLockers`, `brandName`, `brandLogo`, `brandLogoDark`, `brandColor`, `brandFooter`. |
| `/api/lockers` | GET | Estado combinado (hardware + BD) de todos los casilleros. Incluye `pickupCode` solo si hay sesión de admin. |
| `/api/lockers/<id>/status` | GET | Estado físico de un casillero (usado para el sondeo de puerta cerrada). |
| `/api/admin/login` | POST | `{ password }` → inicia sesión. |
| `/api/admin/logout` | POST | Cierra sesión. |
| `/api/admin/session` | GET | `{ isAdmin }` |
| `/api/admin/deposit` | POST | `{ bayId, email }` → abre el casillero y genera el código de recogida. |
| `/api/admin/deposit/confirm` | POST | `{ bayId }` → confirma el depósito una vez cerrada la puerta. |
| `/api/admin/deposit/send-email` | POST | `{ bayId }` → envía el correo de recogida (código + QR) por SMTP. |
| `/api/admin/open` | POST | `{ bayId }` → apertura manual (mantenimiento). |
| `/api/admin/clear` | POST | `{ bayId }` → libera un casillero (borra correo y código; no abre la puerta). |
| `/api/pickup` | POST | `{ code }` → valida el código y abre el casillero (con límite de intentos). |
| `/api/pickup/confirm` | POST | `{ bayId, code }` → confirma la recogida una vez cerrada la puerta. |
| `/api/log` | POST | Registra un evento del frontend en el log del servidor. Hoy el frontend no lo usa. |

### Flujo de depósito (administrador)

1. `POST /api/admin/deposit`: valida que el casillero exista, esté libre y no
   esté deshabilitado; abre la puerta; genera el código; guarda el depósito
   como **pendiente** (correo y código guardados, `occupied = 0`).
2. El frontend sondea `GET /api/lockers/<id>/status` cada 2 s hasta `LOCKED`.
3. `POST /api/admin/deposit/confirm`: marca `occupied = 1` y registra el
   evento.
4. `POST /api/admin/deposit/send-email`: manda el correo. Si falla, el admin ve
   el código y el QR en pantalla para dárselos al cliente.

### Flujo de recogida (cliente)

1. `POST /api/pickup` con el código (escaneado o escrito): busca un casillero
   `occupied = 1` con ese código y abre la puerta.
2. El frontend sondea hasta `LOCKED`.
3. `POST /api/pickup/confirm`: limpia el casillero y registra el evento.

### Casos límite conocidos

- Si el navegador se cierra o recarga **entre abrir y confirmar un depósito**,
  queda un registro con código pero `occupied = 0`: el casillero aparece libre
  y el siguiente depósito lo sobrescribe.
- Si se abre un casillero para recogida y **no se confirma** (la puerta nunca
  se cierra o se recarga la página), el casillero sigue ocupado y el código
  sigue siendo válido: el cliente puede volver a ingresarlo. El admin puede
  usar "Liberar".

---

## Seguridad y privacidad

- La contraseña de admin y los códigos de recogida se validan **solo en el
  servidor** — nunca en el navegador.
- Los códigos de recogida son aleatorios (`secrets.token_hex`), no derivados
  de la hora.
- `/api/pickup` tiene límite de intentos por IP para evitar fuerza bruta. El
  contador vive en memoria (se reinicia con el servidor) y, como el navegador
  siempre conecta desde `127.0.0.1`, **es global**: cinco intentos seguidos de
  cualquier persona bloquean la recogida durante un minuto para todos.
- La sesión de admin es una cookie firmada por Flask con expiración
  configurable.
- El estado vive en SQLite en el servidor, no en `localStorage` del
  navegador — sobrevive a que se borre la caché y queda un registro de
  auditoría (`events` en `kiosk.db`).
- El servidor escucha **solo en `127.0.0.1`**. No cambiar el `host` de
  `server.py` ni exponer el puerto 5000 a la red sin antes agregar
  autenticación de red y HTTPS: el panel de admin y `/api/log` no están
  pensados para eso.
- `server.py` solo sirve archivos de `css/`, `js/`, `images/`, `vendor/` y
  `branding/` (lista blanca en `static_files`). Por eso `.env` y `kiosk.db` no
  son accesibles por HTTP. Al agregar una carpeta de estáticos nueva hay que
  sumarla a esa lista.
- **Datos sensibles:** `kiosk.db`, `action_log.log` y `kiosk_launch.log`
  contienen correos de clientes y códigos de recogida en claro (incluidos los
  intentos con códigos inválidos). Tratarlos como confidenciales: no
  adjuntarlos a tickets, no subirlos a git (ya están ignorados) y borrarlos o
  truncarlos antes de desechar o prestar una tarjeta SD.
- Con `ADMIN_PASSWORD_HASH` vacío la contraseña de admin es `admin123`. Nunca
  poner un kiosco en producción así.

---

## Despliegue en el kiosco

`run_kiosk.sh` arranca todo al iniciar el Pi:

1. Lanza `server.py` en un bucle (se reinicia solo si se cae).
2. Espera activamente a que el servidor responda.
3. Espera a que el socket de Wayland del compositor exista (evita pantalla
   en blanco por arrancar Chromium antes de tiempo).
4. Abre Chromium en modo kiosco (`--kiosk --app=http://127.0.0.1:5000/`,
   sin barras ni diálogos de error, con gestos de pellizco y deslizar-atrás
   desactivados), y lo reintenta si se cierra casi de inmediato tras arrancar.

Todo lo que imprime (servidor, reinicios, Chromium) queda en
`kiosk_launch.log`, dentro de la carpeta del proyecto. Las líneas de Chromium
sobre `DEPRECATED_ENDPOINT` / `gcm` son ruido inofensivo.

El script usa `--ozone-platform=wayland` y `/bin/chromium`: asume el escritorio
Wayland (labwc) de Raspberry Pi OS. En X11 hay que cambiar esa bandera.

### Cómo se dispara al encender

El mecanismo **confirmado y en uso** es el autostart XDG:
`~/.config/autostart/kiosk.desktop`, que ejecuta `run_kiosk.sh` cuando arranca
la sesión de escritorio (se crea en el paso 11 de la guía de instalación).

El repositorio incluye además `kiosk.service`, una unidad systemd que depende de
`graphical-session.target` (por eso está pensada para el gestor de usuario,
`systemctl --user`) y que **no se ha probado ni verificado** en el Pi.
Mientras no se pruebe, tratarla como una alternativa pendiente. Lo importante:
**solo uno de los dos mecanismos puede estar activo**; si ambos
lanzan `run_kiosk.sh`, el segundo servidor falla con "Address already in use"
y el comportamiento se vuelve errático. Para ver qué hay activo:

```bash
ls ~/.config/autostart/
systemctl --user is-enabled kiosk.service
systemctl is-enabled kiosk.service
```

### Rutas y nombre de carpeta

La carpeta de instalación `/home/pi/ArtcenKiosk` está escrita a mano en:

- `run_kiosk.sh` (línea `APP_DIR="/home/pi/ArtcenKiosk"`),
- `kiosk.service` (`ExecStart=`),
- `~/.config/autostart/kiosk.desktop` (`Exec=`), que se crea según esta guía.

Por eso el repositorio se clona en una carpeta llamada `ArtcenKiosk` aunque el
repositorio se llame `Arcen-Locker` (`git clone <url> ArtcenKiosk`). Para usar
otro nombre hay que cambiar esas tres rutas a la vez; si no, el kiosco no
arranca (`run_kiosk.sh` termina con "No se encontró ...").

### Mantenimiento del sistema operativo

Se desarrolló y probó con Raspberry Pi OS basado en Debian 13 (trixie),
escritorio Wayland (labwc) y Python 3.13. Una actualización completa
(`apt upgrade`) cambia muchas piezas a la vez (kernel, compositor, Chromium) y
es la operación de mantenimiento más riesgosa para este kiosco, porque
`run_kiosk.sh` está ajustado a los tiempos de arranque del compositor. En el
último intento documentado (≈440 paquetes: kernel nuevo, Chromium 141 → 151,
wlroots 0.18 → 0.19) `apt` abortó por falta de espacio y no se forzó.

- **Espacio primero.** La tarjeta SD es de ≈8 GB (7,2 GB visibles) y estaba al
  ~91 %. Antes de actualizar: `df -h /`. Una actualización grande necesita
  ~850 MB de descarga más espacio para instalar. Quitar lo que un kiosco no
  usa libera mucho (la imagen de escritorio trae Firefox, el sistema de
  impresión CUPS y VLC): `sudo apt purge firefox rpi-firefox-mods`, luego
  `cups cups-browsed hplip` y `vlc vlc-plugin-qt`, y por último
  `sudo apt autoremove`. **Leer la lista "Removing" de `apt` antes de
  confirmar**; si aparece `labwc`, `wf-panel-pi`, `pi-greeter` o cualquier cosa
  de Wayland, cancelar. A mediano plazo lo correcto es una tarjeta de 16 GB o
  más.
- **Previsualizar:** `sudo apt update && apt list --upgradable`. Prestar
  atención a `chromium`, `labwc`/`wlroots` y `python3`.
- Preferir `apt upgrade` a `apt full-upgrade`: no elimina ni reemplaza
  paquetes para resolver dependencias.
- El `venv` solo se rompe si Python cambia de versión *menor* (3.13 → 3.14),
  no con revisiones de Debian (`3.13.5-2` → `3.13.5-2+deb13u4`). Si pasa,
  recrearlo:

  ```bash
  rm -rf /home/pi/ArtcenKiosk/venv
  cd /home/pi/ArtcenKiosk
  python3 -m venv venv
  ./venv/bin/pip install -r requirements.txt
  ```
- Hacerlo con tiempo y acceso físico al Pi, reiniciar y recorrer el
  [Checklist de verificación](#checklist-de-verificación) completo.

---

## Operación diaria

Todos los comandos, en el Pi.

**Estado general**

```bash
tail -50 /home/pi/ArtcenKiosk/kiosk_launch.log
df -h /
vcgencmd get_throttled
```

**Reiniciar solo el servidor** (Chromium sigue abierto; el bucle de
`run_kiosk.sh` lo relanza en ~2 s y recarga el `.env`):

```bash
pkill -f "venv/bin/python server.py"
```

**Actualizar el código:**

```bash
cd /home/pi/ArtcenKiosk
git pull
./venv/bin/pip install -r requirements.txt   # solo si cambió requirements.txt
pkill -f "venv/bin/python server.py"
```

Si solo cambió el frontend (`js/`, `css/`, `index.html`), basta tocar el botón
de recargar de la pantalla (esquina inferior derecha).

**Cambiar un valor del `.env`** (patrón "borrar y agregar"; ejemplo con el
color de marca) y reiniciar el servidor:

```bash
cd /home/pi/ArtcenKiosk
sed -i "/^BRAND_COLOR=/d" .env
echo "BRAND_COLOR=#111827" >> .env
pkill -f "venv/bin/python server.py"
```

**Cambiar la contraseña de administrador:**

```bash
cd /home/pi/ArtcenKiosk
read -s -p "Nueva contraseña de administrador: " ADMIN_PW
echo
ADMIN_HASH=$(echo "$ADMIN_PW" | ./venv/bin/python -c "
import sys
from werkzeug.security import generate_password_hash
print(generate_password_hash(sys.stdin.readline().strip()))
")
sed -i "/^ADMIN_PASSWORD_HASH=/d" .env
echo "ADMIN_PASSWORD_HASH=$ADMIN_HASH" >> .env
unset ADMIN_PW ADMIN_HASH
pkill -f "venv/bin/python server.py"
```

**Ver el historial de eventos** (depósitos, recogidas, aperturas manuales,
errores, intentos fallidos). La tabla `events` es la auditoría; incluye
códigos y correos, ver [Seguridad y privacidad](#seguridad-y-privacidad):

```bash
cd /home/pi/ArtcenKiosk
./venv/bin/python - <<'EOF'
import sqlite3
for fila in sqlite3.connect('kiosk.db').execute("SELECT ts, level, message FROM events ORDER BY id DESC LIMIT 20"):
    print(*fila)
EOF
```

**Casilleros desde el panel de admin** (botón *Admin*): ver estado real de
cada puerta, *Depositar Paquete*, y en *Gestionar Casilleros*: *Abrir Puerta*
(mantenimiento) y *Liberar* (borra correo y código sin abrir la puerta; útil
si quedó un depósito a medias).

**Cambiar logo, color o pie de página:** ver paso 9 de la guía de instalación y
[`branding/README.md`](branding/README.md), y reiniciar el servidor. Si se
reemplazó un logo conservando el nombre del archivo, Chromium puede seguir
mostrando el viejo por la caché: reiniciar el kiosco.

**Cambiar el fondo de pantalla:** hoy no es configurable por `.env`. Reemplazar
`images/wallpaper-allianz.jpg` (el nombre viene del prototipo original) o
editar la regla `body { background-image: ... }` de `css/styles.css`.

**Apagar de forma segura** (no cortar la corriente a ciegas: puede corromper la
tarjeta SD o la base de datos):

```bash
sudo shutdown -h now
```

---

## Solución de problemas

**La pantalla dice "127.0.0.1 refused to connect" o se queda en blanco**

El servidor no está corriendo. Leer `tail -50 /home/pi/ArtcenKiosk/kiosk_launch.log`
y buscar el error. Causas típicas:

- `ModuleNotFoundError` tras una actualización: llegó una dependencia nueva →
  `./venv/bin/pip install -r requirements.txt` y reiniciar el servidor.
- Un error en el `.env` (línea mal escrita, `LOCKER_CHANNELS` con otro tamaño que
  `NUM_LOCKERS`).
- Los permisos de la base de datos o el puerto ocupado (siguientes puntos).

**`Address already in use` (puerto 5000)**

Hay otra copia del servidor corriendo, casi siempre porque dos mecanismos de
arranque lanzan `run_kiosk.sh` (por ejemplo `kiosk.desktop` y `kiosk.service`, o
una copia vieja del script). Ver quién usa el puerto y dejar un solo mecanismo:

```bash
sudo ss -tlnp | grep 5000
ls ~/.config/autostart/
```

**`attempt to write a readonly database`**

`kiosk.db` (u otros archivos) quedaron a nombre de `root` porque alguna vez se
corrió el servidor con `sudo`. Verlo y corregirlo (sin perder datos):

```bash
find /home/pi/ArtcenKiosk -not -user pi
sudo chown -R pi:pi /home/pi/ArtcenKiosk
```

No volver a usar `sudo` para correr el servidor: el acceso al puerto serie se
resuelve con el grupo `dialout`.

**`SERIAL ERROR` / `Permission denied` en `/dev/ttyUSB0`**

El usuario no está en el grupo `dialout` (o falta reiniciar tras agregarlo):

```bash
groups
ls -l /dev/ttyUSB*
sudo usermod -aG dialout pi
sudo reboot
```

Si el puerto no aparece en `ls`, revisar el cable/alimentación de la placa o si
cambió de nombre (`ttyUSB1`, `ttyACM0`) y actualizar `SERIAL_PORT`.

**Todos los casilleros salen "DESCONOCIDO" en el panel de admin**

La placa no responde: cable, alimentación, `SERIAL_PORT` equivocado. Si solo
**uno** sale desconocido, revisar el cableado de esa puerta y que
`LOCKER_CHANNELS` apunte al canal correcto. Mientras el servidor no logre hablar
con la placa, depositar y abrir devuelven error a propósito: el sistema falla
cerrado en vez de aparentar que abrió.

**El táctil deja de responder pero la pantalla se sigue viendo**

Sospechar de un corte de corriente por USB (sobrecorriente): el Pi desactiva
los puertos USB, el táctil se apaga y la imagen (HDMI) no.

```bash
vcgencmd get_throttled
dmesg | grep -i -E "over-current|overcurrent"
```

Un valor distinto de `0x0` en `get_throttled` indica límites o subtensión
(actuales o pasadas). Soluciones: la fuente oficial de 27 W, un **hub USB con
alimentación propia** para táctil, lector y adaptador serie, y revisar cables y
conectores por si hay un cortocircuito.

**El correo de recogida no llega**

Buscar en `kiosk_launch.log` la línea del envío:

- `Correo de recogida enviado ...`: el servidor lo entregó a Gmail. Si no está
  en la bandeja, **revisar spam**: un remitente nuevo, sin historial, cae ahí
  con facilidad (le pasó a un destinatario de prueba). Marcar los primeros
  como "No es spam" ayuda.
- `SMTP no configurado (revisa SMTP_* en .env)`: faltan `SMTP_HOST`,
  `SMTP_USERNAME` o `SMTP_PASSWORD`. Si se agregaron con `sed s///` y no
  surtieron efecto, es porque esas líneas no existían: usar el patrón "borrar y
  agregar" y reiniciar el servidor.
- `535 Username and Password not accepted`: Gmail rechaza las credenciales. La
  App Password debe generarse **en la misma cuenta** que `SMTP_USERNAME`, con
  verificación en dos pasos activa. Generar una nueva, actualizar
  `SMTP_PASSWORD`, reiniciar.

**En lugar del logo aparece texto**

Se ve el texto alternativo porque la imagen no cargó: la ruta de `BRAND_LOGO` o
`BRAND_LOGO_DARK` está mal. Linux distingue mayúsculas de minúsculas (en Windows
`Logo_A.png` y `logo_a.png` son lo mismo, en el Pi no):

```bash
ls /home/pi/ArtcenKiosk/branding/
grep '^BRAND_LOGO' /home/pi/ArtcenKiosk/.env
```

**El panel de admin tarda en abrir**

Es normal que tarde ≈0,25 s por casillero (ver
[Protocolo serie](#protocolo-serie-de-la-placa)). Si tarda mucho más, hay canales
que no responden y cada uno espera 1 s de timeout: revisar errores `SERIAL ERROR`
en el log y los casilleros en estado "DESCONOCIDO".

**A veces arranca bien y a veces queda en blanco**

Es una carrera entre Chromium y el compositor. `run_kiosk.sh` ya espera el
socket de Wayland y relanza Chromium si cierra al instante; en el log aparecen
`ADVERTENCIA: no se detectó el socket de Wayland` y `Chromium se cerró muy
rápido`. Si ocurre seguido, revisar que el inicio de sesión automático al
escritorio esté activo y que no haya dos mecanismos de arranque.

**`git pull` se queja de cambios locales o de permisos**

```bash
cd /home/pi/ArtcenKiosk
git status
git diff
```

Si los cambios locales no hacen falta, descartarlos con
`git checkout -- <archivo>`. (El bit ejecutable de `run_kiosk.sh` está
versionado como `100755`; si git lo marca como modificado, hay que revisar el
modo del archivo.)

---

## Desarrollo local sin hardware

Funciona en Windows, macOS o Linux. Sin la placa conectada el servidor arranca
igual: todos los casilleros salen `UNKNOWN` y abrir/depositar devuelve error de
hardware (a propósito).

```bash
git clone https://github.com/Artcen-Design/Arcen-Locker.git
cd Arcen-Locker
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Abrir http://127.0.0.1:5000/. Sin `.env`, la contraseña de admin es
`admin123` y se imprimen advertencias; es lo esperado en desarrollo.

No hay pruebas automatizadas en el repositorio. Para ejercitar el flujo
completo (depósito → recogida) sin placa, este script sustituye la capa de
hardware y usa una base de datos temporal. Guardarlo como `prueba_flujo.py` en
la raíz del repositorio (no versionar) y correrlo con `python prueba_flujo.py`;
debe terminar imprimiendo `OK`:

```python
import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "kiosk.db")

import hardware

hardware.open_locker = lambda canal: True
hardware.get_lock_status = lambda canal: {"channel": canal, "status": "LOCKED"}
hardware.get_all_statuses = lambda canales: [{"channel": c, "status": "LOCKED"} for c in canales]

import server

admin = server.app.test_client()
assert admin.post('/api/admin/login', json={"password": "admin123"}).status_code == 200

r = admin.post('/api/admin/deposit', json={"bayId": 1, "email": "cliente@example.com"})
codigo = r.get_json()["pickupCode"]
assert admin.post('/api/admin/deposit/confirm', json={"bayId": 1}).status_code == 200

cliente = server.app.test_client()
r = cliente.post('/api/pickup', json={"code": codigo})
assert r.status_code == 200 and r.get_json()["bayId"] == 1
assert cliente.post('/api/pickup/confirm', json={"bayId": 1, "code": codigo}).status_code == 200
print("OK")
```

(Si hay un `.env` con `ADMIN_PASSWORD_HASH`, el login con `admin123` falla:
usar esa contraseña o probar sin `.env`.)

### Convenciones al modificar el código

- **Todo lo que cambia por sitio va en `.env`, no en el código.** Para agregar
  una opción: leerla en `config.py`, documentarla en `.env.example` y en la
  tabla de [Variables de entorno](#variables-de-entorno), y si el frontend la
  necesita, exponerla en `/api/config` (`server.py`) y leerla en
  `js/utils/config.js`.
- **El servidor decide, el frontend muestra.** Cualquier regla de negocio
  (validar códigos, permisos, abrir puertas) va en `server.py`, nunca en JS.
- **El hardware solo se toca desde `hardware.py`**, y los números de canal
  físico solo se manejan allí y en `config.channel_for()`; el resto del código
  habla de casilleros lógicos.
- **Clases de Tailwind nuevas** exigen recompilar `vendor/tailwind.css` (ver
  [Dependencias de frontend](#dependencias-de-frontend-vendor)) y commitear el
  resultado.
- **Rutas nuevas de archivos estáticos:** agregar la carpeta a la lista blanca
  de `static_files` en `server.py`.
- Texto de la interfaz, mensajes y comentarios del proyecto están en español.

---

## Checklist de verificación

Recorrer después de una instalación nueva, de un cambio de configuración o de
cualquier actualización (código o sistema operativo).

1. **Arranque.** Reiniciar: Chromium abre solo, en pantalla completa y sin
   barras. `kiosk_launch.log` sin `ADVERTENCIA` ni reinicios repetidos.
2. **Panel de admin.** El login funciona y todos los casilleros muestran estado
   real (`Disponible`), ninguno `DESCONOCIDO`.
3. **Cada puerta.** *Gestionar Casilleros → Abrir Puerta*, una por una: el
   casillero N abre la puerta física N (así se valida `LOCKER_CHANNELS`).
4. **Depósito completo.** Elegir un casillero, poner un correo real, cerrar la
   puerta, ver la confirmación y recibir el correo (revisar spam).
5. **Recogida.** Escanear el QR del correo con el lector (o escribir el
   código): abre la puerta; al cerrarla, el casillero vuelve a `Disponible`.
6. **Errores.** Un código inválido muestra el error; cinco intentos seguidos
   bloquean temporalmente.
7. **Táctil.** Los botones de la pantalla de inicio y de todos los modales
   responden al toque; el teclado en pantalla funciona.
8. **Modo claro y oscuro.** El logo correcto en cada modo y textos legibles en
   los modales (liberar casillero, QR de depósito).
9. **Cerrar sesión** del panel de admin.

---

## Limitaciones conocidas y próximos pasos

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
  para un kiosco, pero vale la pena saberlo si el volumen crece mucho. Un
  remitente nuevo además puede caer en spam al principio.
- Pensado para un único kiosco: todo corre en `127.0.0.1` y el panel de
  administración solo es accesible desde la pantalla del propio kiosco. No
  hay administración remota ni sincronización entre sitios — fue una
  decisión consciente para este despliegue, no una limitación técnica del
  diseño (agregarlo más adelante implicaría sumar autenticación de red y
  HTTPS reales).
- **Ruta de instalación fija.** `run_kiosk.sh` y `kiosk.service` tienen
  `/home/pi/ArtcenKiosk` escrito a mano. Mejora pendiente: que `run_kiosk.sh`
  la deduzca de su propia ubicación
  (`APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`) para que el nombre
  de la carpeta deje de importar. Hay que desplegarlo con cuidado: un error aquí
  deja el kiosco sin arrancar.
- **Sin rotación ni purga.** `kiosk_launch.log` no rota y la tabla `events` nunca
  se purga. En una tarjeta SD de ≈8 GB conviene vigilar el espacio
  (`df -h /`); si el log crece, vaciarlo con `truncate -s 0 kiosk_launch.log`
  (el servidor sigue escribiendo sin problema).
- **Una conexión serie por comando.** Cada consulta abre y cierra el puerto. Con
  decenas de casilleros el panel de admin tardaría varios segundos; mantener una
  conexión abierta (con un candado para serializar el acceso) lo reduciría.
- **La marca no llega a los modales.** `BRAND_COLOR` solo tiñe el botón
  principal de la pantalla de inicio; los botones de los modales de admin y
  recogida usan colores de Tailwind fijos en `js/widgets/`.
- **Fondo no configurable.** El fondo (`images/wallpaper-allianz.jpg`, nombre
  heredado del prototipo original) no se cambia por `.env`; conviene
  sustituirlo por una imagen propia o con derechos claros.
- **Una sola "voz" de log.** `/api/log` existe pero el frontend no lo usa; si
  nunca se va a usar, eliminarlo reduce superficie (es público y escribe en el
  log y en la base de datos).
- **Sin pruebas automatizadas** (ver [Desarrollo local](#desarrollo-local-sin-hardware)).
- **Cosmético, sin investigar a fondo:** en pruebas de escritorio, el fondo
  translúcido del panel principal (`.main-screen`) no cambiaba de color al pasar
  a modo oscuro (textos e iconos sí). No se verificó en el kiosco real.
