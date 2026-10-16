# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Proves de la gestió d'usuaris des de la webapp."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, mgr_auth                    # noqa: E402
from app.db_models import UserSessions, Users           # noqa: E402
from app.extensions import db                           # noqa: E402
from auth_helpers import (TEST_PASSWORD, client_with_header,   # noqa: E402
                          logged_in_client, relax_rate_limit)


class UsersApiTestCase(unittest.TestCase):

    def setUp(self):
        os.environ['KORAACCESS_DATA_DIR'] = '/tmp'
        self.app = create_app('dev', start_background=False)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        relax_rate_limit(self.app)
        self.admin = logged_in_client(self.app, username='boss', role='admin')
        self.boss = mgr_auth.get_user_by_username('boss')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def create(self, username='op', role='operator', full_name='Operari'):
        return self.admin.post('/api/users', json={'username': username, 'role': role,
                                                   'full_name': full_name})

    def login_as(self, username, password):
        client = client_with_header(self.app)
        r = client.post('/api/auth/login', json={'username': username, 'password': password})
        return client, r

    # ------------------------------------------------------------------
    # Permisos
    # ------------------------------------------------------------------
    def test_operator_cannot_use_any_users_endpoint(self):
        user_id = self.boss.user_id
        operator = logged_in_client(self.app, username='op', role='operator')
        calls = [('GET', '/api/users'), ('POST', '/api/users'),
                 ('PUT', f'/api/users/{user_id}'),
                 ('POST', f'/api/users/{user_id}/reset-password'),
                 ('POST', f'/api/users/{user_id}/deactivate'),
                 ('POST', f'/api/users/{user_id}/activate'),
                 ('POST', f'/api/users/{user_id}/close-sessions')]
        for method, path in calls:
            with self.subTest(method=method, path=path):
                r = operator.open(path, method=method, json={})
                self.assertEqual(r.status_code, 403)
                self.assertEqual(r.get_json()['message_key'], 'MSG_FORBIDDEN')

    def test_every_users_route_requires_admin(self):
        """Una ruta nova d'usuaris sense @admin_required no passaria aquesta prova."""
        operator = logged_in_client(self.app, username='op', role='operator')
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith('/api/users'):
                continue
            path = rule.rule.replace('<user_id>', self.boss.user_id)
            for method in rule.methods - {'HEAD', 'OPTIONS'}:
                with self.subTest(method=method, path=rule.rule):
                    self.assertEqual(operator.open(path, method=method, json={}).status_code, 403)

    def test_role_change_takes_effect_on_next_request(self):
        """El perfil no viatja al token: treure'l té efecte sense tancar la sessió."""
        self.create(username='second', role='admin')
        second = mgr_auth.get_user_by_username('second')
        password = mgr_auth.set_temporary_password(second)
        second.must_change_password = False
        db.session.commit()
        client, _ = self.login_as('second', password)
        self.assertEqual(client.get('/api/users').status_code, 200)

        self.admin.put(f'/api/users/{second.user_id}', json={'role': 'operator'})
        self.assertEqual(client.get('/api/users').status_code, 403)

    # ------------------------------------------------------------------
    # Crear
    # ------------------------------------------------------------------
    def test_create_returns_temporary_password_once(self):
        r = self.create(username='  Op.Nou ')
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertEqual(body['user']['username'], 'op.nou')
        self.assertTrue(body['user']['must_change_password'])
        password = body['temporary_password']
        self.assertRegex(password, r'^[a-z2-9]{4}(-[a-z2-9]{4}){3}$')
        # No es torna a veure enlloc
        listing = self.admin.get('/api/users').get_data(as_text=True)
        self.assertNotIn(password, listing)
        self.assertNotIn(password, Users.query.filter_by(username='op.nou').one().password_hash)

        # I serveix per entrar, però obliga a canviar-la
        client, r = self.login_as('op.nou', password)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(client.get('/api/terminals').status_code, 403)

    def test_temporary_passwords_are_different(self):
        a = self.create(username='aaa').get_json()['temporary_password']
        b = self.create(username='bbb').get_json()['temporary_password']
        self.assertNotEqual(a, b)

    def test_create_validation(self):
        cases = [
            ({'username': 'x', 'role': 'operator'}, 'MSG_USERNAME_INVALID'),
            ({'username': 'amb espai', 'role': 'operator'}, 'MSG_USERNAME_INVALID'),
            ({'username': 'àlex', 'role': 'operator'}, 'MSG_USERNAME_INVALID'),
            ({'username': 'boss', 'role': 'operator'}, 'MSG_USERNAME_TAKEN'),
            ({'username': 'nou', 'role': 'root'}, 'MSG_ROLE_INVALID'),
            ({'username': 'nou', 'role': 'operator', 'full_name': 'x' * 121}, 'MSG_FULL_NAME_TOO_LONG'),
        ]
        for body, key in cases:
            with self.subTest(body=body):
                r = self.admin.post('/api/users', json=body)
                self.assertEqual(r.get_json()['message_key'], key)
        self.assertEqual(Users.query.count(), 1)

    # ------------------------------------------------------------------
    # Llistar
    # ------------------------------------------------------------------
    def test_list_shows_active_sessions_and_no_secrets(self):
        self.create(username='op')
        users = {u['username']: u for u in self.admin.get('/api/users').get_json()['users']}
        self.assertEqual(users['boss']['active_sessions'], 1)
        self.assertEqual(users['op']['active_sessions'], 0)
        self.assertTrue(users['boss']['last_login_dts'].endswith('Z'))
        for u in users.values():
            self.assertNotIn('password_hash', u)

    # ------------------------------------------------------------------
    # Editar
    # ------------------------------------------------------------------
    def test_update_name_and_role(self):
        user_id = self.create().get_json()['user']['user_id']
        r = self.admin.put(f'/api/users/{user_id}', json={'full_name': 'Nom Nou', 'role': 'admin'})
        self.assertEqual(r.get_json()['user']['full_name'], 'Nom Nou')
        self.assertEqual(r.get_json()['user']['role'], 'admin')

    def test_username_cannot_be_changed(self):
        user_id = self.create().get_json()['user']['user_id']
        self.admin.put(f'/api/users/{user_id}', json={'username': 'altre', 'full_name': 'X',
                                                      'role': 'operator'})
        self.assertEqual(Users.query.filter_by(user_id=user_id).one().username, 'op')

    def test_unknown_user(self):
        r = self.admin.put('/api/users/00000000-0000-0000-0000-000000000000', json={})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()['message_key'], 'MSG_USER_UNKNOWN')

    # ------------------------------------------------------------------
    # Protecció dels administradors
    # ------------------------------------------------------------------
    def test_admin_cannot_demote_or_deactivate_self(self):
        uid = self.boss.user_id
        self.create(username='other', role='admin')   # perquè no sigui l'últim
        for method, path, body in [('PUT', f'/api/users/{uid}', {'role': 'operator'}),
                                   ('POST', f'/api/users/{uid}/deactivate', {})]:
            with self.subTest(path=path):
                r = self.admin.open(path, method=method, json=body)
                self.assertEqual(r.get_json()['message_key'], 'MSG_CANNOT_MODIFY_SELF')
        db.session.refresh(self.boss)
        self.assertEqual((self.boss.role, self.boss.is_active), ('admin', True))

    def test_admin_can_edit_own_name(self):
        r = self.admin.put(f'/api/users/{self.boss.user_id}', json={'full_name': 'Cap', 'role': 'admin'})
        self.assertEqual(r.status_code, 200)

    def test_last_active_admin_is_protected(self):
        """Un altre administrador, desactivat, no compta: només en queda un d'actiu."""
        other = self.create(username='other', role='admin').get_json()['user']['user_id']
        self.admin.post(f'/api/users/{other}/deactivate')
        # Des d'un segon administrador actiu que es crea ara
        third_id = self.create(username='third', role='admin').get_json()['user']['user_id']
        third = Users.query.filter_by(user_id=third_id).one()
        pw = mgr_auth.set_temporary_password(third)
        third.must_change_password = False
        db.session.commit()
        client, _ = self.login_as('third', pw)
        # third desactiva boss: queda third com a únic administrador actiu
        self.assertEqual(client.post(f'/api/users/{self.boss.user_id}/deactivate').status_code, 200)
        # i ara ningú pot treure third (ell mateix tampoc)
        self.assertEqual(client.post(f'/api/users/{third_id}/deactivate').get_json()['message_key'],
                         'MSG_CANNOT_MODIFY_SELF')
        self.assertEqual(mgr_auth._other_active_admins(self.boss), 1)

    # ------------------------------------------------------------------
    # Contrasenya i sessions
    # ------------------------------------------------------------------
    def test_reset_password_closes_sessions(self):
        body = self.create().get_json()
        user_id = body['user']['user_id']
        client, _ = self.login_as('op', body['temporary_password'])
        r = self.admin.post(f'/api/users/{user_id}/reset-password')
        new_password = r.get_json()['temporary_password']
        self.assertNotEqual(new_password, body['temporary_password'])
        self.assertEqual(client.get('/api/auth/me').status_code, 401)
        _, r = self.login_as('op', new_password)
        self.assertEqual(r.status_code, 200)

    def test_deactivate_closes_sessions_and_activate_restores_access(self):
        body = self.create().get_json()
        user_id = body['user']['user_id']
        client, _ = self.login_as('op', body['temporary_password'])
        self.admin.post(f'/api/users/{user_id}/deactivate')
        self.assertEqual(client.get('/api/auth/me').status_code, 401)
        self.assertEqual(self.login_as('op', body['temporary_password'])[1].status_code, 401)
        self.admin.post(f'/api/users/{user_id}/activate')
        self.assertEqual(self.login_as('op', body['temporary_password'])[1].status_code, 200)

    def test_close_sessions_of_another_user(self):
        body = self.create().get_json()
        client, _ = self.login_as('op', body['temporary_password'])
        r = self.admin.post(f'/api/users/{body["user"]["user_id"]}/close-sessions')
        self.assertEqual(r.get_json()['user']['active_sessions'], 0)
        self.assertEqual(client.get('/api/auth/me').status_code, 401)

    def test_close_own_sessions_keeps_current(self):
        other, _ = self.login_as('boss', TEST_PASSWORD)
        self.admin.post(f'/api/users/{self.boss.user_id}/close-sessions')
        self.assertEqual(self.admin.get('/api/users').status_code, 200)
        self.assertEqual(other.get('/api/users').status_code, 401)
        self.assertEqual(UserSessions.query.filter_by(user_id=self.boss.user_id).count(), 1)

    # ------------------------------------------------------------------
    # Rutes inexistents
    # ------------------------------------------------------------------
    def test_unknown_api_route_is_json_404(self):
        """Abans requeia a la SPA i responia index.html amb un 200."""
        r = self.admin.get('/api/no-existeix')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()['message_key'], 'MSG_NOT_FOUND')


if __name__ == '__main__':
    unittest.main(verbosity=2)
