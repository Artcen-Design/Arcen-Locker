"""Envío del correo de recogida (código + QR) por SMTP.

Reemplaza el envío anterior desde el navegador (EmailJS): ahora el servidor
genera el QR y manda el correo, así que un fallo queda en los mismos logs
que todo lo demás en vez de desaparecer en la consola del kiosco.
"""
import io
import smtplib
import socket
import ssl
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import qrcode

import config


def _build_qr_png(pickup_code):
    img = qrcode.make(pickup_code)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _config_faltante():
    """Nombres de las variables SMTP_* obligatorias que están vacías."""
    requeridas = {
        "SMTP_HOST": config.SMTP_HOST,
        "SMTP_USERNAME": config.SMTP_USERNAME,
        "SMTP_PASSWORD": config.SMTP_PASSWORD,
    }
    return [nombre for nombre, valor in requeridas.items() if not valor]


def _explicar_fallo(etapa, error, destinatario):
    """Traduce una excepción de smtplib o de red a un mensaje accionable.

    Gmail, en particular, no siempre responde un 535 claro cuando rechaza la
    cuenta o la contraseña: a veces solo corta la conexión al autenticar, y
    smtplib lo reporta como "Connection unexpectedly closed", que por sí solo
    no dice nada útil. Por eso se tiene en cuenta en qué etapa ocurrió.
    """
    servidor = f"{config.SMTP_HOST}:{config.SMTP_PORT}"
    credenciales = (
        "Revisa que SMTP_USERNAME sea la dirección completa y que SMTP_PASSWORD "
        "sea una App Password vigente de esa misma cuenta, sin espacios."
    )

    if isinstance(error, smtplib.SMTPAuthenticationError):
        causa = f"el servidor rechazó las credenciales. {credenciales}"
    elif isinstance(error, smtplib.SMTPNotSupportedError):
        causa = (
            f"el servidor {servidor} no soporta esta operación (esta app usa "
            "STARTTLS con usuario y contraseña; el puerto debe ser el 587)."
        )
    elif isinstance(error, smtplib.SMTPRecipientsRefused):
        causa = f"el servidor rechazó al destinatario {destinatario}; revisa que el correo exista."
    elif isinstance(error, smtplib.SMTPSenderRefused):
        causa = (
            f"el servidor rechazó al remitente {config.SMTP_FROM_EMAIL}; SMTP_FROM_EMAIL "
            "debe ser la cuenta autenticada o un alias permitido."
        )
    elif isinstance(error, smtplib.SMTPServerDisconnected) and "timed out" in str(error):
        # smtplib reporta una espera agotada de lectura como "Connection
        # unexpectedly closed: timed out": la conexión SÍ se abrió, pero el
        # servidor dejó de contestar. No es lo mismo que un corte inmediato.
        if etapa == "conexión":
            causa = (
                f"se abrió la conexión con {servidor} pero el saludo del servidor SMTP no llegó "
                "a tiempo. Suele ser una red inestable, o una que bloquea o intercepta el correo "
                "saliente (firewall, red de una institución, portal cautivo). Para confirmarlo, "
                "prueba el Pi desde otra red (por ejemplo, el hotspot de un teléfono)."
            )
        else:
            causa = (
                f"el servidor {servidor} dejó de responder a tiempo durante la etapa de {etapa}; "
                "suele ser una red inestable o que interfiere con el correo saliente."
            )
    elif isinstance(error, smtplib.SMTPServerDisconnected):
        if etapa == "autenticación":
            causa = (
                "el servidor cortó la conexión al autenticar. Gmail hace esto cuando "
                f"rechaza la cuenta o la contraseña. {credenciales}"
            )
        elif etapa == "TLS":
            causa = "el servidor cortó la conexión al negociar STARTTLS; revisa que SMTP_PORT sea 587."
        elif etapa == "conexión":
            causa = (
                f"el servidor {servidor} cortó la conexión apenas se abrió; revisa SMTP_HOST y "
                "SMTP_PORT (587, no 465), o si la red bloquea el correo saliente."
            )
        else:
            causa = "el servidor cortó la conexión mientras se enviaba el mensaje."
    elif isinstance(error, socket.gaierror):
        causa = f"no se pudo resolver el nombre {config.SMTP_HOST}; revisa SMTP_HOST y la conexión a internet del Pi."
    elif isinstance(error, (TimeoutError, socket.timeout)):
        causa = (
            f"{servidor} tardó demasiado en responder; la red del Pi puede estar bloqueando "
            "el puerto SMTP, o SMTP_HOST/SMTP_PORT son incorrectos."
        )
    elif isinstance(error, ConnectionRefusedError):
        causa = f"{servidor} rechazó la conexión; revisa SMTP_HOST y SMTP_PORT (Gmail: smtp.gmail.com y 587)."
    elif isinstance(error, ssl.SSLError):
        causa = f"falló el cifrado TLS con {config.SMTP_HOST}."
    elif isinstance(error, smtplib.SMTPException):
        causa = "el servidor rechazó la operación."
    else:
        causa = "error inesperado."

    return f"Falló en la etapa de {etapa}: {causa} (detalle técnico: {type(error).__name__}: {error})"


def send_pickup_email(to_email, pickup_code, bay_id):
    """Devuelve (enviado: bool, error: str|None)."""
    faltantes = _config_faltante()
    if faltantes:
        return False, f"SMTP no configurado: falta {', '.join(faltantes)} (revisa .env)"

    msg = MIMEMultipart('related')
    msg['Subject'] = 'Tu código de recogida de paquete'
    msg['From'] = f"{config.SMTP_FROM_NAME} <{config.SMTP_FROM_EMAIL}>"
    msg['To'] = to_email

    alt = MIMEMultipart('alternative')
    msg.attach(alt)

    text = (
        f"Tu paquete está listo para recoger en el Casillero {bay_id}.\n"
        f"Código de recogida: {pickup_code}\n\n"
        "Escanea el código QR adjunto en el kiosco, o introduce el código manualmente."
    )
    alt.attach(MIMEText(text, 'plain'))

    html = f"""
    <div style="font-family: sans-serif; text-align: center;">
        <h2>Tu paquete está listo</h2>
        <p>Casillero <strong>{bay_id}</strong></p>
        <img src="cid:qrcode" alt="Código QR" width="200" height="200">
        <p style="font-size: 24px; font-family: monospace; letter-spacing: 2px;">{pickup_code}</p>
        <p>Escanea el código QR en el kiosco, o introduce el código manualmente.</p>
    </div>
    """
    alt.attach(MIMEText(html, 'html'))

    image = MIMEImage(_build_qr_png(pickup_code), name='qrcode.png')
    image.add_header('Content-ID', '<qrcode>')
    image.add_header('Content-Disposition', 'inline', filename='qrcode.png')
    msg.attach(image)

    etapa = "conexión"
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            etapa = "TLS"
            server.starttls()
            etapa = "autenticación"
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            etapa = "envío"
            server.sendmail(config.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        return True, None
    except Exception as e:
        return False, _explicar_fallo(etapa, e, to_email)
