# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Gestió d'usuaris. Només per a administradors.

Les contrasenyes inicials i les restablertes les genera el servidor i es
retornen una sola vegada: l'administrador les dona a l'usuari, que les haurà de
canviar en entrar. Així ningú més no les coneix després del primer login.

Esborrar un usuari no n'elimina la fila: l'anonimitza (mgr_auth.delete_user),
perquè l'auditoria continuï quadrant. Només es poden esborrar usuaris
desactivats.
"""

from flask import Blueprint, g, jsonify, request
from flask_login import current_user

from app import mgr_auth
from app.api.permissions import admin_required
from app.db_models import Users
from app.messages import AppError, Msg

users_bp = Blueprint('users', __name__)


def _get_user_or_404(user_id):
    """Un usuari esborrat respon com si no existís: no es pot reactivar ni editar."""
    user = mgr_auth.get_user_by_id(user_id)
    if user is None:
        raise AppError(Msg.USER_UNKNOWN, 404)
    return user


def _admin_dict(user):
    sessions = mgr_auth.active_sessions_by_user().get(user.user_id, 0)
    return mgr_auth.user_to_admin_dict(user, sessions)


@users_bp.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    sessions = mgr_auth.active_sessions_by_user()
    users = mgr_auth.live_users().order_by(Users.username).all()
    return jsonify({'users': [mgr_auth.user_to_admin_dict(u, sessions.get(u.user_id, 0)) for u in users]})


@users_bp.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    body = request.get_json(force=True, silent=True) or {}
    password = mgr_auth.generate_temporary_password()
    user = mgr_auth.create_user(body.get('username'), password, body.get('role'),
                                full_name=body.get('full_name', ''), must_change_password=True)
    return jsonify({'user': _admin_dict(user), 'temporary_password': password}), 201


@users_bp.route('/api/users/<user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    user = _get_user_or_404(user_id)
    body = request.get_json(force=True, silent=True) or {}
    mgr_auth.update_user(user, body.get('full_name', user.full_name), body.get('role', user.role),
                         acting_user=current_user)
    return jsonify({'user': _admin_dict(user)})


@users_bp.route('/api/users/<user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = _get_user_or_404(user_id)
    password = mgr_auth.set_temporary_password(user)
    return jsonify({'user': _admin_dict(user), 'temporary_password': password})


@users_bp.route('/api/users/<user_id>/deactivate', methods=['POST'])
@admin_required
def deactivate(user_id):
    user = _get_user_or_404(user_id)
    mgr_auth.set_active(user, False, acting_user=current_user)
    return jsonify({'user': _admin_dict(user)})


@users_bp.route('/api/users/<user_id>/activate', methods=['POST'])
@admin_required
def activate(user_id):
    user = _get_user_or_404(user_id)
    mgr_auth.set_active(user, True, acting_user=current_user)
    return jsonify({'user': _admin_dict(user)})


@users_bp.route('/api/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Esborra (anonimitza) un usuari desactivat. No es pot desfer."""
    user = _get_user_or_404(user_id)
    mgr_auth.delete_user(user, acting_user=current_user)
    return jsonify({'ok': True})


@users_bp.route('/api/users/<user_id>/close-sessions', methods=['POST'])
@admin_required
def close_sessions(user_id):
    """Si l'administrador tanca les seves pròpies sessions, es manté la que fa servir ara."""
    user = _get_user_or_404(user_id)
    keep = g.kora_session.session_id if user.user_id == current_user.user_id else None
    mgr_auth.revoke_user_sessions(user, keep_session_id=keep)
    return jsonify({'user': _admin_dict(user)})
