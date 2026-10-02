"""Envío del correo de recogida (código + QR) por SMTP.

Reemplaza el envío anterior desde el navegador (EmailJS): ahora el servidor
genera el QR y manda el correo, así que un fallo queda en los mismos logs
que todo lo demás en vez de desaparecer en la consola del kiosco.
"""
import io
import smtplib
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


def send_pickup_email(to_email, pickup_code, bay_id):
    """Devuelve (enviado: bool, error: str|None)."""
    if not config.SMTP_HOST or not config.SMTP_USERNAME or not config.SMTP_PASSWORD:
        return False, "SMTP no configurado (revisa SMTP_* en .env)"

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

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)
