# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Ordres d'administració de KoraAccess. Vegeu app/cli.py.

    python manage.py users create-admin

Fa servir la mateixa configuració que run.py (KORAACCESS_CONFIG,
KORAACCESS_DATA_DIR) i no arrenca el servidor ni el discovery, de manera que es
pot executar amb el servei en marxa.
"""

import os

from flask.cli import FlaskGroup

from app import create_app


def _create_app():
    return create_app(os.environ.get('KORAACCESS_CONFIG', 'dev'), start_background=False)


cli = FlaskGroup(create_app=_create_app)

if __name__ == '__main__':
    cli()
