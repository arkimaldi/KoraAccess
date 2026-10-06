# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Fàbrica de l'aplicació KoraAccess."""

import logging
import os
import threading
import time

from flask import Flask, send_from_directory
from flask_migrate import upgrade

from config import CONFIG_BY_NAME
from app.extensions import db, migrate
from app.mgr_discovery import MgrDiscovery
from app.mgr_link import MgrLink

STATIC_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), 'static')


def create_app(config_name='dev', start_background=True):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(CONFIG_BY_NAME[config_name])

    db.init_app(app)
    migrate.init_app(app, db)

    from app.api.cloud_event import cloud_event_bp
    from app.api.terminals import terminals_bp
    app.register_blueprint(cloud_event_bp)
    app.register_blueprint(terminals_bp)

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
