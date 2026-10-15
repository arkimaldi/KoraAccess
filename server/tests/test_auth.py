# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Proves d'autenticació i de sessions.

Cada prova correspon a una propietat de seguretat acordada en el disseny. Si
alguna falla, no és un detall: és una porta oberta.
"""

import os
import sys
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, mgr_auth                       # noqa: E402
from app.db_models import UserSessions, Users, utcnow      # noqa: E402
from app.extensions import db, limiter                     # noqa: E402
from auth_helpers import (CSRF_HEADERS, TEST_PASSWORD,     # noqa: E402
                          client_with_header, relax_rate_limit)

COOKIE = 'koraaccess_session'


class AuthTestCase(unittest.TestCase):

    def setUp(self):
        os.environ['KORAACCESS_DATA_DIR'] = '/tmp'
        self.app = create_app('dev', start_background=False)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        relax_rate_limit(self.app)
        self.user = mgr_auth.create_user('Maria', TEST_PASSWORD, 'operator', 'Maria Puig')
        self.client = client_with_header(self.app)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, client=None, username='maria', password=TEST_PASSWORD):
        return (client or self.client).post('/api/auth/login',
                                            json={'username': username, 'password': password})

    def cookie_value(self, response):
        header = response.headers.get('Set-Cookie', '')
        return header.split(';')[0].split('=', 1)[1] if header.startswith(COOKIE) else None

    # ------------------------------------------------------------------
    # Accés
    # ------------------------------------------------------------------
    def test_api_requires_session(self):
        r = self.client.get('/api/terminals')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()['message_key'], 'MSG_AUTH_REQUIRED')

    def test_new_api_endpoints_are_protected_by_default(self):
        """Qualsevol ruta de /api/ no declarada pública requereix sessió."""
        public = {('POST', '/api/auth/login'), ('POST', '/api/auth/logout')}
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith('/api/'):
                continue
            path = rule.rule.replace('<device_id>', '00000000-0000-0000-0000-000000000000')
            for method in rule.methods - {'HEAD', 'OPTIONS'}:
                if (method, rule.rule) in public:
                    continue
                with self.subTest(method=method, path=rule.rule):
                    r = self.client.open(path, method=method, json={})
                    self.assertEqual(r.status_code, 401)

    def test_device_protocol_and_spa_do_not_require_session(self):
        r = self.client.post('/v1/Cloud/Event',
                             json={'msgType': 'on_cloud_keep_alive', 'msgArg': {'sEUI64': 'X'}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 200)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def test_login_ok(self):
        r = self.login(username='  MARIA ')   # sense distinció de majúscules ni espais
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['user']['username'], 'maria')
        self.assertEqual(self.client.get('/api/terminals').status_code, 200)

    def test_cookie_attributes(self):
        header = self.login().headers['Set-Cookie']
        self.assertIn('HttpOnly', header)
        self.assertIn('SameSite=Strict', header)
        self.assertIn('Path=/', header)

    def test_cookie_is_secure_outside_development(self):
        self.app.config['AUTH_COOKIE_SECURE'] = True
        self.assertIn('Secure', self.login().headers['Set-Cookie'])

    def test_same_error_for_unknown_user_wrong_password_and_inactive(self):
        """No s'ha de poder esbrinar quins usuaris existeixen."""
        unknown = self.login(username='ningu')
        wrong = self.login(password='contrasenya-dolenta')
        mgr_auth.set_active(self.user, False)
        inactive = self.login()
        for r in (unknown, wrong, inactive):
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.get_json(), unknown.get_json())

    def test_password_stored_with_argon2id(self):
        self.assertTrue(self.user.password_hash.startswith('$argon2id$'))
        self.assertNotIn(TEST_PASSWORD, self.user.password_hash)

    def test_new_token_on_each_login(self):
        """Evita la fixació de sessió."""
        first = self.cookie_value(self.login())
        second = self.cookie_value(self.login())
        self.assertNotEqual(first, second)

    def test_rate_limit_on_login(self):
        self.app.config['AUTH_LOGIN_RATE_LIMIT'] = '5 per minute'
        limiter.reset()
        codes = [self.login(password='dolenta').status_code for _ in range(5)]
        self.assertEqual(codes, [401] * 5)
        r = self.login()   # fins i tot amb la contrasenya bona
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.get_json()['message_key'], 'MSG_LOGIN_RATE_LIMITED')

    # ------------------------------------------------------------------
    # CSRF
    # ------------------------------------------------------------------
    def test_state_changing_requests_need_the_header(self):
        self.login()
        plain = self.app.test_client()
        plain.set_cookie(COOKIE, self.cookie_value(self.login()))
        r = plain.post('/api/discovery/scan')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()['message_key'], 'MSG_REQUEST_HEADER_MISSING')
        # Una lectura no ho necessita
        self.assertEqual(plain.get('/api/terminals').status_code, 200)

    # ------------------------------------------------------------------
    # Emmagatzematge de la sessió
    # ------------------------------------------------------------------
    def test_token_is_not_stored_in_clear(self):
        """Una còpia de la base de dades no ha de permetre entrar."""
        token = self.cookie_value(self.login())
        stored = [s.token_hash for s in UserSessions.query.all()]
        self.assertEqual(len(stored), 1)
        self.assertNotIn(token, stored)
        self.assertEqual(len(stored[0]), 64)   # SHA-256 en hexadecimal

    # ------------------------------------------------------------------
    # Caducitat
    # ------------------------------------------------------------------
    def test_idle_timeout(self):
        self.login()
        session = UserSessions.query.one()
        session.last_seen_dts = utcnow() - timedelta(seconds=self.app.config['AUTH_IDLE_TIMEOUT_S'] + 1)
        db.session.commit()
        r = self.client.get('/api/terminals')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(UserSessions.query.count(), 0)   # s'esborra
        self.assertIn(f'{COOKIE}=;', r.headers.get('Set-Cookie', ''))   # i s'esborra la cookie

    def test_absolute_timeout_even_if_active(self):
        self.login()
        session = UserSessions.query.one()
        session.expires_dts = utcnow() - timedelta(seconds=1)
        db.session.commit()
        self.assertEqual(self.client.get('/api/terminals').status_code, 401)

    def test_activity_extends_idle_timeout(self):
        self.login()
        session = UserSessions.query.one()
        old = utcnow() - timedelta(seconds=self.app.config['AUTH_LAST_SEEN_UPDATE_S'] + 5)
        session.last_seen_dts = old
        db.session.commit()
        self.client.get('/api/terminals')
        db.session.refresh(session)
        self.assertGreater(session.last_seen_dts, old)

    def test_purge_removes_only_expired_sessions(self):
        self.login()
        other = client_with_header(self.app)
        self.login(other)
        stale = UserSessions.query.first()
        stale.expires_dts = utcnow() - timedelta(seconds=1)
        db.session.commit()
        mgr_auth.purge_expired_sessions()
        self.assertEqual(UserSessions.query.count(), 1)

    # ------------------------------------------------------------------
    # Logout i revocació
    # ------------------------------------------------------------------
    def test_logout(self):
        self.login()
        r = self.client.post('/api/auth/logout')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(UserSessions.query.count(), 0)
        self.assertEqual(self.client.get('/api/terminals').status_code, 401)

    def test_logout_without_session_is_harmless(self):
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 200)

    def test_deactivating_user_closes_sessions(self):
        self.login()
        mgr_auth.set_active(self.user, False)
        self.assertEqual(self.client.get('/api/terminals').status_code, 401)

    # ------------------------------------------------------------------
    # Canvi de contrasenya
    # ------------------------------------------------------------------
    def change(self, current, new, client=None):
        return (client or self.client).put('/api/auth/password',
                                           json={'current_password': current, 'new_password': new})

    def test_change_password_requires_current(self):
        self.login()
        r = self.change('dolenta', 'una-de-nova-prou-llarga')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()['message_key'], 'MSG_PASSWORD_CURRENT_INVALID')

    def test_password_policy(self):
        self.login()
        short = self.change(TEST_PASSWORD, 'curta')
        self.assertEqual(short.get_json()['message_key'], 'MSG_PASSWORD_TOO_SHORT')
        self.assertEqual(short.get_json()['params'], {'min': 10})
        long_ = self.change(TEST_PASSWORD, 'x' * 129)
        self.assertEqual(long_.get_json()['message_key'], 'MSG_PASSWORD_TOO_LONG')
        same = self.change(TEST_PASSWORD, TEST_PASSWORD)
        self.assertEqual(same.get_json()['message_key'], 'MSG_PASSWORD_SAME_AS_CURRENT')

    def test_change_password_keeps_current_session_and_closes_others(self):
        self.login()
        other = client_with_header(self.app)
        self.login(other)
        self.assertEqual(self.change(TEST_PASSWORD, 'una-de-nova-prou-llarga').status_code, 200)
        self.assertEqual(self.client.get('/api/terminals').status_code, 200)
        self.assertEqual(other.get('/api/terminals').status_code, 401)
        # I la contrasenya nova funciona
        fresh = client_with_header(self.app)
        self.assertEqual(self.login(fresh, password='una-de-nova-prou-llarga').status_code, 200)

    def test_forced_password_change_blocks_everything_else(self):
        self.user.must_change_password = True
        db.session.commit()
        self.login()
        blocked = self.client.get('/api/terminals')
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()['message_key'], 'MSG_PASSWORD_CHANGE_REQUIRED')
        self.assertTrue(self.client.get('/api/auth/me').get_json()['user']['must_change_password'])

        self.assertEqual(self.change(TEST_PASSWORD, 'una-de-nova-prou-llarga').status_code, 200)
        self.assertEqual(self.client.get('/api/terminals').status_code, 200)

    # ------------------------------------------------------------------
    # Idioma de l'usuari
    # ------------------------------------------------------------------
    def test_language_preference(self):
        self.login()
        r = self.client.put('/api/auth/me/language', json={'language': 'ca'})
        self.assertEqual(r.get_json()['user']['language'], 'ca')
        self.assertEqual(self.client.get('/api/auth/me').get_json()['user']['language'], 'ca')
        bad = self.client.put('/api/auth/me/language', json={'language': 'de'})
        self.assertEqual(bad.get_json()['message_key'], 'MSG_LANGUAGE_UNSUPPORTED')


class UsersCliTestCase(unittest.TestCase):
    """Les ordres de gestió d'usuaris, que en aquesta iteració fan de pantalla d'administració."""

    def setUp(self):
        os.environ['KORAACCESS_DATA_DIR'] = '/tmp'
        self.app = create_app('dev', start_background=False)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        relax_rate_limit(self.app)
        self.runner = self.app.test_cli_runner()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def run_cli(self, args, input_text=None):
        return self.runner.invoke(args=['users'] + args, input=input_text)

    def test_create_admin(self):
        r = self.run_cli(['create-admin', '--username', 'Admin', '--full-name', 'Cap'],
                         input_text='contrasenya-admin\ncontrasenya-admin\n')
        self.assertEqual(r.exit_code, 0, r.output)
        user = Users.query.one()
        self.assertEqual((user.username, user.role, user.full_name), ('admin', 'admin', 'Cap'))

    def test_password_is_not_echoed(self):
        r = self.run_cli(['create-admin', '--username', 'admin', '--full-name', ''],
                         input_text='contrasenya-admin\ncontrasenya-admin\n')
        self.assertNotIn('contrasenya-admin', r.output)

    def test_create_rejects_short_password(self):
        r = self.run_cli(['create', '--username', 'op', '--full-name', '', '--role', 'operator'],
                         input_text='curta\ncurta\n')
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn('at least 10', r.output)
        self.assertEqual(Users.query.count(), 0)

    def test_create_rejects_duplicate(self):
        mgr_auth.create_user('op', TEST_PASSWORD, 'operator')
        r = self.run_cli(['create', '--username', 'OP', '--full-name', '', '--role', 'operator'],
                         input_text=f'{TEST_PASSWORD}\n{TEST_PASSWORD}\n')
        self.assertNotEqual(r.exit_code, 0)

    def test_reset_password_forces_change_and_closes_sessions(self):
        user = mgr_auth.create_user('op', TEST_PASSWORD, 'operator')
        client = client_with_header(self.app)
        client.post('/api/auth/login', json={'username': 'op', 'password': TEST_PASSWORD})
        r = self.run_cli(['reset-password', 'op'], input_text='temporal-nova-1\ntemporal-nova-1\n')
        self.assertEqual(r.exit_code, 0, r.output)
        db.session.refresh(user)
        self.assertTrue(user.must_change_password)
        self.assertEqual(UserSessions.query.count(), 0)
        self.assertEqual(client.get('/api/terminals').status_code, 401)

    def test_cannot_deactivate_last_admin(self):
        mgr_auth.create_user('admin', TEST_PASSWORD, 'admin')
        r = self.run_cli(['deactivate', 'admin'])
        self.assertNotEqual(r.exit_code, 0)
        self.assertTrue(Users.query.one().is_active)

    def test_deactivate_and_activate(self):
        mgr_auth.create_user('admin', TEST_PASSWORD, 'admin')
        mgr_auth.create_user('op', TEST_PASSWORD, 'operator')
        self.assertEqual(self.run_cli(['deactivate', 'op']).exit_code, 0)
        self.assertFalse(mgr_auth.get_user_by_username('op').is_active)
        self.assertEqual(self.run_cli(['activate', 'op']).exit_code, 0)
        self.assertTrue(mgr_auth.get_user_by_username('op').is_active)

    def test_list(self):
        mgr_auth.create_user('admin', TEST_PASSWORD, 'admin')
        r = self.run_cli(['list'])
        self.assertIn('admin', r.output)
        self.assertNotIn(TEST_PASSWORD, r.output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
