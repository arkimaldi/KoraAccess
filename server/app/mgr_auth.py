# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Usuaris, contrasenyes i sessions.

Aquí no hi ha res criptogràfic escrit a mà:
  - contrasenyes: argon2id, amb argon2-cffi;
  - identificadors de sessió: secrets.token_urlsafe, 256 bits aleatoris;
  - a la base de dades, només el SHA-256 de l'identificador (hashlib).

Com que l'identificador és aleatori i llarg, n'hi ha prou amb un SHA-256 simple:
no cal sal ni un hash lent, que només calen per a secrets triats per persones.

Cada sessió caduca per inactivitat i, en tot cas, passat un temps màxim des
del login. Es revoquen esborrant-ne la fila.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import current_app

from app.db_models import UserSessions, Users, utcnow
from app.extensions import db
from app.messages import AppError, Msg

ROLES = ('admin', 'operator')
LANGUAGES = ('en', 'ca', 'es')

_hasher = PasswordHasher()

# Hash d'una contrasenya qualsevol, per gastar el mateix temps quan l'usuari no
# existeix. Sense això, el temps de resposta delataria quins usuaris existeixen.
_DUMMY_HASH = _hasher.hash('kora-dummy-password-for-timing')


# ----------------------------------------------------------------------
# Contrasenyes
# ----------------------------------------------------------------------
def hash_password(password):
    return _hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def check_password_policy(password):
    """Mínim i màxim de longitud, sense regles de composició (NIST SP 800-63B)."""
    cfg = current_app.config
    if len(password or '') < cfg['PASSWORD_MIN_LENGTH']:
        raise AppError(Msg.PASSWORD_TOO_SHORT, 400, min=cfg['PASSWORD_MIN_LENGTH'])
    if len(password) > cfg['PASSWORD_MAX_LENGTH']:
        raise AppError(Msg.PASSWORD_TOO_LONG, 400, max=cfg['PASSWORD_MAX_LENGTH'])


def normalize_username(username):
    return (username or '').strip().lower()


# ----------------------------------------------------------------------
# Usuaris
# ----------------------------------------------------------------------
def get_user_by_username(username):
    return Users.query.filter_by(username=normalize_username(username)).first()


def create_user(username, password, role, full_name='', must_change_password=False):
    username = normalize_username(username)
    if not username:
        raise ValueError('El nom d\'usuari no pot ser buit.')
    if role not in ROLES:
        raise ValueError(f'Perfil desconegut: {role}. Valors possibles: {", ".join(ROLES)}.')
    if get_user_by_username(username) is not None:
        raise ValueError(f'Ja existeix l\'usuari {username}.')
    check_password_policy(password)
    user = Users(username=username, full_name=full_name or '', role=role,
                 password_hash=hash_password(password),
                 must_change_password=must_change_password)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate(username, password):
    """
    Retorna l'usuari si les credencials són correctes i el compte és actiu.
    Sempre el mateix error per a usuari inexistent, contrasenya incorrecta o
    compte desactivat: no s'ha de poder esbrinar quins usuaris existeixen.
    """
    user = get_user_by_username(username)
    if user is None:
        verify_password(_DUMMY_HASH, password or '')
        return None
    if not verify_password(user.password_hash, password or ''):
        return None
    if not user.is_active:
        return None
    # Si els paràmetres d'argon2 han canviat des que es va desar, es refà el hash.
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def change_password(user, new_password, keep_session_id=None):
    """
    Canvia la contrasenya i tanca totes les altres sessions de l'usuari: si algú
    la coneixia i tenia una sessió oberta, deixa de tenir-la.
    """
    check_password_policy(new_password)
    if verify_password(user.password_hash, new_password):
        raise AppError(Msg.PASSWORD_SAME_AS_CURRENT, 400)
    user.password_hash = hash_password(new_password)
    user.password_changed_dts = utcnow()
    user.must_change_password = False
    revoke_user_sessions(user, keep_session_id=keep_session_id, commit=False)
    db.session.commit()


def set_active(user, active):
    user.is_active = bool(active)
    if not active:
        revoke_user_sessions(user, commit=False)
    db.session.commit()


# ----------------------------------------------------------------------
# Sessions
# ----------------------------------------------------------------------
def _token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_session(user, ip_address=None, user_agent=None):
    """
    Obre una sessió nova i en retorna el token, que només viatja a la cookie.
    A cada login un token nou: evita la fixació de sessió.
    """
    cfg = current_app.config
    purge_expired_sessions(commit=False)
    token = secrets.token_urlsafe(32)
    now = utcnow()
    db.session.add(UserSessions(
        token_hash=_token_hash(token),
        user_id=user.user_id,
        created_dts=now,
        last_seen_dts=now,
        expires_dts=now + timedelta(seconds=cfg['AUTH_ABSOLUTE_TIMEOUT_S']),
        ip_address=(ip_address or '')[:45] or None,
        user_agent=(user_agent or '')[:255] or None,
    ))
    user.last_login_dts = now
    db.session.commit()
    return token


def load_session(token):
    """
    Retorna la sessió vigent que correspon al token, o None. Una sessió caducada
    s'esborra en el mateix moment.
    """
    if not token:
        return None
    cfg = current_app.config
    session = UserSessions.query.filter_by(token_hash=_token_hash(token)).first()
    if session is None:
        return None

    now = utcnow()
    idle_limit = session.last_seen_dts + timedelta(seconds=cfg['AUTH_IDLE_TIMEOUT_S'])
    if now >= session.expires_dts or now >= idle_limit or not session.user.is_active:
        db.session.delete(session)
        db.session.commit()
        return None

    if (now - session.last_seen_dts).total_seconds() >= cfg['AUTH_LAST_SEEN_UPDATE_S']:
        session.last_seen_dts = now
        db.session.commit()
    return session


def delete_session(session):
    db.session.delete(session)
    db.session.commit()


def revoke_user_sessions(user, keep_session_id=None, commit=True):
    query = UserSessions.query.filter(UserSessions.user_id == user.user_id)
    if keep_session_id:
        query = query.filter(UserSessions.session_id != keep_session_id)
    query.delete(synchronize_session=False)
    if commit:
        db.session.commit()


def purge_expired_sessions(commit=True):
    """Esborra les sessions caducades, per absoluta o per inactivitat."""
    try:
        cfg = current_app.config
        now = utcnow()
        idle_cutoff = now - timedelta(seconds=cfg['AUTH_IDLE_TIMEOUT_S'])
        UserSessions.query.filter(
            (UserSessions.expires_dts <= now) | (UserSessions.last_seen_dts <= idle_cutoff)
        ).delete(synchronize_session=False)
        if commit:
            db.session.commit()
    except Exception as e:
        logging.error('purge_expired_sessions exception: %s', e)
        db.session.rollback()


def user_to_dict(user):
    """El que el frontend necessita saber de l'usuari connectat."""
    return {
        'user_id': user.user_id,
        'username': user.username,
        'full_name': user.full_name,
        'role': user.role,
        'language': user.language,
        'must_change_password': user.must_change_password,
    }
