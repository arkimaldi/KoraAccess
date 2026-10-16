# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Permisos per perfil.

La guarda de app/__init__.py ja exigeix sessió a tota ruta de /api/. Aquests
decoradors hi afegeixen el perfil. Són la protecció de debò: el frontend només
amaga les opcions que l'usuari no pot fer servir.
"""

from functools import wraps

from flask_login import current_user

from app.messages import AppError, Msg


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            raise AppError(Msg.FORBIDDEN, 403)
        return view(*args, **kwargs)
    return wrapper
