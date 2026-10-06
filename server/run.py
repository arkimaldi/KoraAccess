# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Punt d'entrada de KoraAccess.

Se serveix amb cheroot, que sí que fa TLS (waitress no en fa). Així no cal cap
procés Node ni cap proxy invers: un sol executable Python.
"""

import logging
import os
import sys

from cheroot.wsgi import Server
from cheroot.ssl.builtin import BuiltinSSLAdapter

from app import create_app


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s'
    )
    config_name = os.environ.get('KORAACCESS_CONFIG', 'dev')
    app = create_app(config_name)

    host = app.config['LISTEN_HOST']
    port = app.config['LISTEN_PORT']
    cert = app.config['TLS_CERT_FILE']
    key = app.config['TLS_KEY_FILE']

    server = Server((host, port), app, numthreads=app.config['SERVER_THREADS'])
    if cert and key:
        server.ssl_adapter = BuiltinSSLAdapter(cert, key)
        scheme = 'https'
    else:
        scheme = 'http'
        logging.warning('Sense certificat: se serveix en HTTP pla (només per a desenvolupament)')

    logging.info('KoraAccess escoltant a %s://%s:%d', scheme, host, port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
        sys.exit(0)


if __name__ == '__main__':
    main()
