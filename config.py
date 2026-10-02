"""Site configuration, loaded from environment variables / a local .env file.

Copy .env.example to .env and adjust per deployment instead of editing code
here — this keeps per-site settings (locker count, serial port, secrets) out
of version control and out of the codebase itself.
"""
import os
import secrets
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent

NUM_LOCKERS = int(os.environ.get('NUM_LOCKERS', 8))


def _parse_id_list(value):
    return {int(x.strip()) for x in value.split(',') if x.strip()}


# Casilleros que existen físicamente pero están fuera de servicio (p.ej. un
# puerto dañado en la placa sin recablear). Se excluyen de todo flujo de
# depósito/apertura y se muestran como "Fuera de Servicio" en vez de
# sondearlos por serial.
DISABLED_LOCKERS = _parse_id_list(os.environ.get('DISABLED_LOCKERS', ''))

# Mapeo de casillero lógico (1..NUM_LOCKERS, lo que ve el admin/cliente) a
# canal físico real en la placa. Por defecto es 1:1 (casillero 1 = canal 1),
# pero si un puerto de la placa se daña y las puertas se recablean a otros
# canales, esto se ajusta en .env sin tocar código. Ejemplo: si el puerto 1
# de la placa está frito y todo se recableó un canal más adelante,
# LOCKER_CHANNELS=2,3,4,5 hace que el casillero 1 hable con el canal 2, etc.
def _parse_channel_list(value, default_length):
    if not value:
        return list(range(1, default_length + 1))
    return [int(x.strip()) for x in value.split(',') if x.strip()]


LOCKER_CHANNELS = _parse_channel_list(os.environ.get('LOCKER_CHANNELS', ''), NUM_LOCKERS)
if len(LOCKER_CHANNELS) != NUM_LOCKERS:
    print(
        f"WARNING: LOCKER_CHANNELS tiene {len(LOCKER_CHANNELS)} canal(es) pero "
        f"NUM_LOCKERS={NUM_LOCKERS}; revisa tu .env, el mapeo puede quedar incompleto."
    )

BAY_TO_CHANNEL = {bay_id: channel for bay_id, channel in enumerate(LOCKER_CHANNELS, start=1)}


def channel_for(bay_id):
    return BAY_TO_CHANNEL.get(bay_id, bay_id)

SERIAL_PORT = os.environ.get('SERIAL_PORT', '/dev/ttyUSB0')
BAUD_RATE = int(os.environ.get('BAUD_RATE', 9600))

PICKUP_CODE_LENGTH = int(os.environ.get('PICKUP_CODE_LENGTH', 8))

SESSION_LIFETIME_MINUTES = int(os.environ.get('SESSION_LIFETIME_MINUTES', 30))

PICKUP_RATE_LIMIT_ATTEMPTS = int(os.environ.get('PICKUP_RATE_LIMIT_ATTEMPTS', 5))
PICKUP_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('PICKUP_RATE_LIMIT_WINDOW_SECONDS', 60))

DB_PATH = os.environ.get('DB_PATH', str(BASE_DIR / 'kiosk.db'))
LOG_FILE = os.environ.get('LOG_FILE', str(BASE_DIR / 'action_log.log'))

# Identidad de marca por sitio. Todo vacío por defecto = el kiosco se ve
# exactamente como hoy (sin encabezado de logo, botón azul de siempre, sin
# pie de página). Un cliente se personaliza completando estos valores en
# .env, sin tocar código — mismo patrón que NUM_LOCKERS/LOCKER_CHANNELS.
# Usado solo como texto alternativo (accesibilidad) del logo — el nombre ya
# no se muestra como texto en pantalla, se asume que el logo lo incluye.
BRAND_NAME = os.environ.get('BRAND_NAME', '')
# Rutas relativas a archivos dentro de branding/, p.ej. "branding/logo_a.png".
# BRAND_LOGO se usa en modo claro. BRAND_LOGO_DARK se usa en modo oscuro; si
# se deja vacío, el modo oscuro simplemente reutiliza BRAND_LOGO.
BRAND_LOGO = os.environ.get('BRAND_LOGO', '')
BRAND_LOGO_DARK = os.environ.get('BRAND_LOGO_DARK', '')
BRAND_COLOR = os.environ.get('BRAND_COLOR', '#2563eb')
BRAND_FOOTER = os.environ.get('BRAND_FOOTER', '')

# Correo de recogida (código + QR), enviado desde el servidor por SMTP.
SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SMTP_FROM_EMAIL = os.environ.get('SMTP_FROM_EMAIL', SMTP_USERNAME)
SMTP_FROM_NAME = os.environ.get('SMTP_FROM_NAME', 'Kiosco de Paquetería')

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print(
        "WARNING: SECRET_KEY no está configurada en el entorno; usando una "
        "clave aleatoria temporal (las sesiones de admin no sobrevivirán un "
        "reinicio). Define SECRET_KEY en .env para producción."
    )

ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH')
if not ADMIN_PASSWORD_HASH:
    from werkzeug.security import generate_password_hash
    ADMIN_PASSWORD_HASH = generate_password_hash('admin123')
    print(
        "WARNING: ADMIN_PASSWORD_HASH no está configurada en el entorno; "
        "usando la contraseña por defecto 'admin123'. Genera una real con "
        "'python set_admin_password.py' y agrégala a .env antes de salir a producción."
    )
