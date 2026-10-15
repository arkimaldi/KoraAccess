# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Ajudants per a les proves que necessiten una sessió iniciada."""

TEST_PASSWORD = 'contrasenya-de-proves'
CSRF_HEADERS = {'X-Requested-With': 'KoraAccess'}


def relax_rate_limit(app):
    """
    El límit d'intents viu en memòria i es comparteix entre proves del mateix
    procés: s'apuja i es buida perquè una prova no consumeixi el marge d'una altra.
    """
    from app.extensions import limiter
    app.config['AUTH_LOGIN_RATE_LIMIT'] = '1000 per minute'
    limiter.reset()


def client_with_header(app):
    """Client de proves que envia la capçalera anti-CSRF a totes les peticions."""
    client = app.test_client()
    client.environ_base['HTTP_X_REQUESTED_WITH'] = CSRF_HEADERS['X-Requested-With']
    return client


def logged_in_client(app, username='tester', role='admin'):
    from app import mgr_auth
    relax_rate_limit(app)
    if mgr_auth.get_user_by_username(username) is None:
        mgr_auth.create_user(username, TEST_PASSWORD, role)
    client = client_with_header(app)
    r = client.post('/api/auth/login', json={'username': username, 'password': TEST_PASSWORD})
    assert r.status_code == 200, r.get_json()
    return client
