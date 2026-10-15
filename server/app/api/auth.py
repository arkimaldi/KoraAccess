# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Login, logout i dades de l'usuari connectat.

La sessió viatja en una cookie HttpOnly, Secure i SameSite=Strict: JavaScript no
la pot llegir, així que una vulnerabilitat XSS no la pot robar.
"""

from flask import Blueprint, current_app, g, jsonify, request
from flask_login import current_user

from app import mgr_auth
from app.extensions import db, limiter
from app.messages import AppError, Msg

auth_bp = Blueprint('auth', __name__)


def _login_rate_limit():
    return current_app.config['AUTH_LOGIN_RATE_LIMIT']


def set_session_cookie(response, token):
    cfg = current_app.config
    response.set_cookie(
        cfg['AUTH_COOKIE_NAME'], token,
        max_age=cfg['AUTH_ABSOLUTE_TIMEOUT_S'],
        httponly=True,
        secure=cfg['AUTH_COOKIE_SECURE'],
        samesite='Strict',
        path='/',
    )


def clear_session_cookie(response):
    cfg = current_app.config
    response.delete_cookie(cfg['AUTH_COOKIE_NAME'], path='/',
                           secure=cfg['AUTH_COOKIE_SECURE'], httponly=True, samesite='Strict')


@auth_bp.route('/api/auth/login', methods=['POST'])
@limiter.limit(_login_rate_limit)
def login():
    body = request.get_json(force=True, silent=True) or {}
    user = mgr_auth.authenticate(body.get('username'), body.get('password'))
    if user is None:
        raise AppError(Msg.LOGIN_INVALID, 401)
    token = mgr_auth.create_session(user, request.remote_addr, request.headers.get('User-Agent'))
    response = jsonify({'user': mgr_auth.user_to_dict(user)})
    set_session_cookie(response, token)
    return response


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """Pública: ha de poder netejar la cookie encara que la sessió hagi caducat."""
    session = getattr(g, 'kora_session', None)
    if session is not None:
        mgr_auth.delete_session(session)
    response = jsonify({'ok': True})
    clear_session_cookie(response)
    return response


@auth_bp.route('/api/auth/me', methods=['GET'])
def me():
    return jsonify({'user': mgr_auth.user_to_dict(current_user)})


@auth_bp.route('/api/auth/me/language', methods=['PUT'])
def set_language():
    language = (request.get_json(force=True, silent=True) or {}).get('language')
    if language not in mgr_auth.LANGUAGES:
        raise AppError(Msg.LANGUAGE_UNSUPPORTED, 400)
    current_user.language = language
    db.session.commit()
    return jsonify({'user': mgr_auth.user_to_dict(current_user)})


@auth_bp.route('/api/auth/password', methods=['PUT'])
@limiter.limit(_login_rate_limit)
def change_password():
    """Limitat com el login: si no, serviria per endevinar la contrasenya actual."""
    body = request.get_json(force=True, silent=True) or {}
    if not mgr_auth.verify_password(current_user.password_hash, body.get('current_password') or ''):
        raise AppError(Msg.PASSWORD_CURRENT_INVALID, 400)
    # Es manté la sessió des d'on es fa el canvi; es tanquen totes les altres.
    mgr_auth.change_password(current_user, body.get('new_password') or '',
                             keep_session_id=g.kora_session.session_id)
    return jsonify({'user': mgr_auth.user_to_dict(current_user)})
