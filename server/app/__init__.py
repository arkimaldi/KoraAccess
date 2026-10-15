# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Fàbrica de l'aplicació KoraAccess."""

import logging
import os
import threading
import time

from flask import Flask, send_from_directory
from flask_migrate import upgrade

from config import CONFIG_BY_NAME
from app.extensions import db, limiter, login_manager, migrate
from app.mgr_discovery import MgrDiscovery
from app.mgr_link import MgrLink

# Carpeta amb el build de l'Angular. Es pot sobreescriure per entorn, cosa que
# fan servir les proves e2e per servir webapp/dist directament.
STATIC_DIR = os.environ.get(
    'KORAACCESS_STATIC_DIR',
    os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), 'static'))


def create_app(config_name='dev', start_background=True):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(CONFIG_BY_NAME[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    _init_auth(app)

    from app.api.auth import auth_bp
    from app.api.cloud_event import cloud_event_bp
    from app.api.terminals import terminals_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(cloud_event_bp)
    app.register_blueprint(terminals_bp)
    _register_error_handlers(app)

    from app.cli import users_cli
    app.cli.add_command(users_cli)

    discovery = MgrDiscovery(
        port=app.config['DISCOVERY_PORT'],
        token=app.config['DISCOVERY_TOKEN'],
        result_ttl=app.config['DISCOVERY_RESULT_TTL']
    )
    app.extensions['kora_discovery'] = discovery

    with app.app_context():
        _upgrade_database(app)

    # --- SPA d'Angular: build copiat a static/ ---
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_spa(path):
        full = os.path.join(STATIC_DIR, path)
        if path and os.path.isfile(full):
            return send_from_directory(STATIC_DIR, path)
        index = os.path.join(STATIC_DIR, 'index.html')
        if os.path.isfile(index):
            return send_from_directory(STATIC_DIR, 'index.html')
        return ('KoraAccess: el frontend no està compilat. '
                'Compileu l\'Angular i copieu el build a static/.', 200)

    if start_background:
        _start_background_tasks(app, discovery)

    return app


def _upgrade_database(app):
    """
    Porta l'esquema a l'última revisió a l'arrencada.

    El programa s'instal·la com a servei a casa del client, on no hi ha ningú
    per executar «flask db upgrade» a mà i on la base de dades conté els
    terminals ja enrolats: no es pot recrear.

    En els tests, que usen una base de dades en memòria i no tenen l'historial
    de migracions, es crea l'esquema directament.
    """
    if app.config.get('TESTING') or app.config['SQLALCHEMY_DATABASE_URI'].endswith(':memory:'):
        db.create_all()
        return
    try:
        upgrade()
    except Exception as e:
        logging.error('No s\'ha pogut actualitzar l\'esquema: %s', e)
        raise


# Endpoints de /api/ accessibles sense sessió. Tota la resta en requereix: un
# endpoint nou queda protegit per defecte, encara que algú s'oblidi de marcar-lo.
PUBLIC_API_ENDPOINTS = {
    ('POST', '/api/auth/login'),
    ('POST', '/api/auth/logout'),
}

# Mentre l'usuari ha de canviar la contrasenya, només pot fer això.
PASSWORD_CHANGE_ENDPOINTS = {
    ('GET', '/api/auth/me'),
    ('PUT', '/api/auth/password'),
    ('POST', '/api/auth/logout'),
}

# Capçalera que el frontend afegeix a totes les peticions. Un formulari d'una
# altra web no la pot posar sense permís CORS, que el servidor no dona: és una
# segona defensa contra CSRF, a més de la cookie SameSite=Strict.
CSRF_HEADER = 'X-Requested-With'
CSRF_HEADER_VALUE = 'KoraAccess'
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


def _init_auth(app):
    """
    Autenticació amb Flask-Login. La sessió no viu a la cookie de Flask sinó a la
    taula user_sessions: request_loader la carrega a cada petició a partir de la
    cookie pròpia.
    """
    from flask import g, request
    from flask_login import current_user
    from app import mgr_auth
    from app.messages import AppError, Msg

    login_manager.init_app(app)
    # No fem servir la sessió de Flask: la protecció de Flask-Login sobre ella
    # no aplica.
    login_manager.session_protection = None

    @login_manager.request_loader
    def _load_user_from_request(req):
        token = req.cookies.get(app.config['AUTH_COOKIE_NAME'])
        session = mgr_auth.load_session(token)
        g.kora_session = session
        return session.user if session is not None else None

    @app.before_request
    def _guard_api():
        # L'usuari es carrega de nou a cada petició. Flask-Login el desa a g, i g
        # pertany al context d'aplicació, que es pot reutilitzar entre peticions
        # si ja n'hi havia un d'obert (ho fan les proves). Sense això, una
        # petició podria heretar l'usuari, o l'anonimat, de l'anterior.
        g.pop('_login_user', None)
        g.pop('kora_session', None)

        if not request.path.startswith('/api/'):
            return None   # la SPA i el protocol dels terminals no hi entren
        if request.method not in SAFE_METHODS and \
                request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
            raise AppError(Msg.REQUEST_HEADER_MISSING, 403)

        key = (request.method, request.path)
        if key in PUBLIC_API_ENDPOINTS:
            current_user._get_current_object()   # carrega la sessió, si n'hi ha
            return None
        if not current_user.is_authenticated:
            raise AppError(Msg.AUTH_REQUIRED, 401)
        if current_user.must_change_password and key not in PASSWORD_CHANGE_ENDPOINTS:
            raise AppError(Msg.PASSWORD_CHANGE_REQUIRED, 403)
        return None

    @app.after_request
    def _clear_stale_cookie(response):
        """Si el navegador porta una cookie que ja no val, se li esborra."""
        if request.path.startswith('/api/') and response.status_code == 401 \
                and request.cookies.get(app.config['AUTH_COOKIE_NAME']):
            from app.api.auth import clear_session_cookie
            clear_session_cookie(response)
        return response


def _register_error_handlers(app):
    """
    Tota resposta d'error de /api/ té la forma comuna de messages.py, també la
    d'un error inesperat. /v1/Cloud/Event no hi entra: és el protocol dels
    terminals i té el seu propi contracte.
    """
    from flask import request
    from werkzeug.exceptions import HTTPException
    from app.messages import AppError, Msg

    @app.errorhandler(AppError)
    def _app_error(e):
        return e.response()

    @app.errorhandler(429)
    def _rate_limited(e):
        if request.path.startswith('/api/'):
            return AppError(Msg.LOGIN_RATE_LIMITED, 429).response()
        return e

    @app.errorhandler(Exception)
    def _unexpected(e):
        if isinstance(e, HTTPException) or not request.path.startswith('/api/'):
            return e
        logging.exception('Unexpected error on %s', request.path)
        return AppError(Msg.INTERNAL_ERROR, 500).response()


def _start_background_tasks(app, discovery):
    try:
        discovery.start_listener()
    except Exception as e:
        logging.error('No s\'ha pogut iniciar el listener de discovery: %s', e)

    def link_refresher():
        while True:
            time.sleep(app.config['DEVICES_KEEP_ALIVE_TMO'])
            with app.app_context():
                MgrLink.refresh_all()

    threading.Thread(target=link_refresher, name='KoraLinkRefresh', daemon=True).start()

    def session_purger():
        from app import mgr_auth
        while True:
            time.sleep(3600)
            with app.app_context():
                mgr_auth.purge_expired_sessions()

    threading.Thread(target=session_purger, name='KoraSessionPurge', daemon=True).start()
