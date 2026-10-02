# Save this as server.py
import logging
import secrets
import time
from datetime import timedelta
from functools import wraps
from logging.handlers import RotatingFileHandler

from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import check_password_hash

import config
import db
import hardware
import mailer

app = Flask(__name__, static_folder=None)
app.secret_key = config.SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=config.SESSION_LIFETIME_MINUTES)

db.init_db()

# --- Logging: file (for tailing on the Pi) + DB (queryable audit trail) ---
log_handler = RotatingFileHandler(config.LOG_FILE, maxBytes=1024 * 1024, backupCount=5)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
app.logger.addHandler(log_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('--- Kiosk Lock Server INICIADO ---')


def log(level, message):
    getattr(app.logger, level)(message)
    db.log_event(level.upper(), message)


# --- Simple in-memory rate limit for pickup-code attempts ---
_pickup_attempts = {}


def _is_rate_limited(ip):
    now = time.time()
    window = config.PICKUP_RATE_LIMIT_WINDOW_SECONDS
    attempts = [t for t in _pickup_attempts.get(ip, []) if now - t < window]
    if len(attempts) >= config.PICKUP_RATE_LIMIT_ATTEMPTS:
        _pickup_attempts[ip] = attempts
        return True
    attempts.append(now)
    _pickup_attempts[ip] = attempts
    return False


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            return jsonify({"success": False, "error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return wrapper


# --- Static frontend (single entrypoint: http://127.0.0.1:5000/) ---
@app.route('/')
def index():
    return send_from_directory(config.BASE_DIR, 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    if filename.split('/')[0] not in ('css', 'js', 'images', 'vendor', 'branding'):
        return jsonify({"success": False, "error": "No encontrado"}), 404
    return send_from_directory(config.BASE_DIR, filename)


# --- Config ---
@app.route('/api/config')
def api_config():
    return jsonify({
        "numLockers": config.NUM_LOCKERS,
        "brandName": config.BRAND_NAME,
        "brandLogo": config.BRAND_LOGO,
        "brandLogoDark": config.BRAND_LOGO_DARK,
        "brandColor": config.BRAND_COLOR,
        "brandFooter": config.BRAND_FOOTER,
    })


# --- Locker status (hardware + DB merged) ---
def _merged_bays(include_pickup_code=False):
    enabled_bay_ids = [i for i in range(1, config.NUM_LOCKERS + 1) if i not in config.DISABLED_LOCKERS]
    channels_to_poll = [config.channel_for(bay_id) for bay_id in enabled_bay_ids]
    hw_statuses = {s['channel']: s['status'] for s in hardware.get_all_statuses(channels_to_poll)}
    # Solo se muestran casilleros dentro del rango físico actual (NUM_LOCKERS)
    # — filas más allá de eso son de una configuración anterior con más
    # casilleros y ya no aplican a este sitio.
    bays = [b for b in db.get_all_bays() if b['id'] <= config.NUM_LOCKERS]
    result = []
    for bay in bays:
        if bay['id'] in config.DISABLED_LOCKERS:
            hardware_status = "DISABLED"
        else:
            hardware_status = hw_statuses.get(config.channel_for(bay['id']), "UNKNOWN")
        entry = {
            "id": bay['id'],
            "occupied": bool(bay['occupied']),
            "customerEmail": bay['customer_email'],
            "hardwareStatus": hardware_status,
        }
        # El código de recogida solo se expone a un admin autenticado: es la
        # credencial del cliente, no debe ser legible desde un GET público.
        if include_pickup_code:
            entry["pickupCode"] = bay['pickup_code']
        result.append(entry)
    return result


@app.route('/api/lockers')
def api_lockers():
    is_admin = bool(session.get('is_admin'))
    return jsonify({"success": True, "bays": _merged_bays(include_pickup_code=is_admin)})


@app.route('/api/lockers/<int:bay_id>/status')
def api_locker_status(bay_id):
    status = hardware.get_lock_status(config.channel_for(bay_id))
    return jsonify({"success": True, "status": status["status"], "channel": bay_id})


# --- Admin auth ---
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json(silent=True) or {}
    password = data.get('password', '')
    if check_password_hash(config.ADMIN_PASSWORD_HASH, password):
        session.permanent = True
        session['is_admin'] = True
        return jsonify({"success": True})
    log('warning', "Intento fallido de login de administrador")
    return jsonify({"success": False, "error": "Contraseña incorrecta"}), 401


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({"success": True})


@app.route('/api/admin/session')
def admin_session():
    return jsonify({"isAdmin": bool(session.get('is_admin'))})


# --- Deposit flow (admin) ---
@app.route('/api/admin/deposit', methods=['POST'])
@admin_required
def admin_deposit():
    data = request.get_json(silent=True) or {}
    try:
        bay_id = int(data.get('bayId'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Casillero inválido"}), 400
    email = (data.get('email') or '').strip()
    if not email or '@' not in email:
        return jsonify({"success": False, "error": "Correo inválido"}), 400

    if bay_id in config.DISABLED_LOCKERS:
        return jsonify({"success": False, "error": "Casillero fuera de servicio"}), 409

    bay = db.get_bay(bay_id)
    if not bay:
        return jsonify({"success": False, "error": "Casillero no existe"}), 404
    if bay['occupied']:
        return jsonify({"success": False, "error": "Casillero ocupado"}), 409

    if not hardware.open_locker(config.channel_for(bay_id)):
        log('error', f"Fallo al abrir casillero {bay_id} para depósito")
        return jsonify({"success": False, "error": "Fallo al comunicar con el hardware"}), 500

    pickup_code = secrets.token_hex(max(config.PICKUP_CODE_LENGTH, 4) // 2).upper()
    db.stage_deposit(bay_id, email, pickup_code)
    log('info', f"Comando de apertura enviado para depósito en casillero {bay_id}")
    return jsonify({"success": True, "pickupCode": pickup_code})


@app.route('/api/admin/deposit/confirm', methods=['POST'])
@admin_required
def admin_deposit_confirm():
    data = request.get_json(silent=True) or {}
    try:
        bay_id = int(data.get('bayId'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Casillero inválido"}), 400

    bay = db.get_bay(bay_id)
    if not bay or not bay['pickup_code'] or bay['occupied']:
        return jsonify({"success": False, "error": "No hay un depósito pendiente para este casillero"}), 400

    db.confirm_deposit(bay_id)
    log('info', f"PAQUETE DEPOSITADO en casillero {bay_id} para {bay['customer_email']} (Código: {bay['pickup_code']})")
    return jsonify({"success": True})


@app.route('/api/admin/deposit/send-email', methods=['POST'])
@admin_required
def admin_send_pickup_email():
    data = request.get_json(silent=True) or {}
    try:
        bay_id = int(data.get('bayId'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Casillero inválido"}), 400

    bay = db.get_bay(bay_id)
    if not bay or not bay['pickup_code'] or not bay['customer_email']:
        return jsonify({"success": False, "error": "No hay un depósito para este casillero"}), 400

    sent, error = mailer.send_pickup_email(bay['customer_email'], bay['pickup_code'], bay_id)
    if sent:
        log('info', f"Correo de recogida enviado para casillero {bay_id} a {bay['customer_email']}")
    else:
        log('error', f"Fallo al enviar correo de recogida para casillero {bay_id}: {error}")
    return jsonify({"success": sent, "error": error})


# --- Manual maintenance (admin) ---
@app.route('/api/admin/open', methods=['POST'])
@admin_required
def admin_open():
    data = request.get_json(silent=True) or {}
    try:
        bay_id = int(data.get('bayId'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Casillero inválido"}), 400

    if bay_id in config.DISABLED_LOCKERS:
        return jsonify({"success": False, "error": "Casillero fuera de servicio"}), 409

    if not hardware.open_locker(config.channel_for(bay_id)):
        log('error', f"Fallo al abrir casillero {bay_id} manualmente")
        return jsonify({"success": False, "error": "Fallo al comunicar con el hardware"}), 500

    log('info', f"Apertura manual (admin) del casillero {bay_id}")
    return jsonify({"success": True})


@app.route('/api/admin/clear', methods=['POST'])
@admin_required
def admin_clear():
    data = request.get_json(silent=True) or {}
    try:
        bay_id = int(data.get('bayId'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Casillero inválido"}), 400

    db.clear_bay(bay_id)
    log('info', f"Casillero {bay_id} liberado manualmente (admin)")
    return jsonify({"success": True})


# --- Pickup flow (customer, public but rate-limited + server-validated code) ---
@app.route('/api/pickup', methods=['POST'])
def pickup():
    ip = request.remote_addr or 'unknown'
    if _is_rate_limited(ip):
        return jsonify({"success": False, "error": "Demasiados intentos. Espera un momento e intenta de nuevo."}), 429

    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip().upper()
    if not code:
        return jsonify({"success": False, "error": "Código requerido"}), 400

    bay = db.get_bay_by_code(code)
    if not bay:
        log('warning', f"Intento de recogida con código inválido: {code}")
        return jsonify({"success": False, "error": "El código no es válido o ya fue usado"}), 404

    if not hardware.open_locker(config.channel_for(bay['id'])):
        log('error', f"Fallo al abrir casillero {bay['id']} para recogida")
        return jsonify({"success": False, "error": "Fallo al comunicar con el hardware"}), 500

    log('info', f"Casillero {bay['id']} abierto para recogida (Código: {code})")
    return jsonify({"success": True, "bayId": bay['id']})


@app.route('/api/pickup/confirm', methods=['POST'])
def pickup_confirm():
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip().upper()
    try:
        bay_id = int(data.get('bayId'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Casillero inválido"}), 400

    bay = db.get_bay(bay_id)
    if not bay or bay['pickup_code'] != code:
        return jsonify({"success": False, "error": "El código no coincide con el depósito pendiente"}), 400

    log('info', f"PAQUETE RECOGIDO del casillero {bay_id} (Código: {code})")
    db.clear_bay(bay_id)
    return jsonify({"success": True})


# --- Frontend event logging (kept for client-side errors worth recording) ---
@app.route('/api/log', methods=['POST'])
def handle_log_event():
    data = request.get_json(silent=True) or {}
    message = data.get('message')
    level = (data.get('level') or 'info').lower()
    if not message:
        return jsonify({"success": False, "error": "Missing message"}), 400
    if level not in ('info', 'warning', 'error'):
        level = 'info'
    log(level, f"FRONTEND: {message}")
    return jsonify({"success": True})


if __name__ == '__main__':
    print("--- Starting Kiosk Lock Server ---")
    print(f"Frontend + API listos en http://127.0.0.1:5000/  ({config.NUM_LOCKERS} casilleros)")
    app.run(host='127.0.0.1', port=5000)
