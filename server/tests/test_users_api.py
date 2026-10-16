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
    # Esborrat (anonimització)
    # ------------------------------------------------------------------
    def create_and_deactivate(self, username='op', full_name='Maria Puig'):
        body = self.create(username=username, full_name=full_name).get_json()
        user_id = body['user']['user_id']
        self.admin.post(f'/api/users/{user_id}/deactivate')
        return user_id, body['temporary_password']

    def test_only_deactivated_users_can_be_deleted(self):
        user_id = self.create().get_json()['user']['user_id']
        r = self.admin.delete(f'/api/users/{user_id}')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()['message_key'], 'MSG_DELETE_ACTIVE_USER')
        self.assertIsNone(Users.query.filter_by(user_id=user_id).one().deleted_dts)

    def test_delete_anonymizes_and_keeps_the_row(self):
        user_id, _ = self.create_and_deactivate(username='maria', full_name='Maria Puig')
        self.admin.put(f'/api/users/{user_id}', json={'full_name': 'Maria Puig', 'role': 'operator'})
        Users.query.filter_by(user_id=user_id).one().language = 'ca'
        db.session.commit()

        r = self.admin.delete(f'/api/users/{user_id}')
        self.assertEqual(r.status_code, 200)

        row = Users.query.filter_by(user_id=user_id).one()   # la fila es conserva
        self.assertEqual(row.username, 'deleted-' + user_id.replace('-', ''))
        self.assertEqual(row.full_name, '')
        self.assertIsNone(row.language)
        self.assertEqual(row.password_hash, '!')
        self.assertEqual(row.role, 'operator')               # es manté per a l'auditoria
        self.assertFalse(row.is_active)
        self.assertIsNotNone(row.deleted_dts)
        self.assertIsNotNone(row.created_dts)

    def test_no_personal_data_left_in_the_row(self):
        """Ni el nom d'usuari ni el nom complet originals queden en cap columna."""
        user_id, _ = self.create_and_deactivate(username='jordimas', full_name='Jordi Mas')
        self.admin.delete(f'/api/users/{user_id}')
        row = Users.query.filter_by(user_id=user_id).one()
        values = ' '.join(str(getattr(row, c.name)) for c in Users.__table__.columns).lower()
        self.assertNotIn('jordimas', values)
        self.assertNotIn('jordi', values)

    def test_new_username_does_not_derive_from_the_old_one(self):
        """Dos usuaris amb el mateix nom esborrats en moments diferents no es poden relacionar."""
        first, _ = self.create_and_deactivate(username='repetit')
        self.admin.delete(f'/api/users/{first}')
        second, _ = self.create_and_deactivate(username='repetit')
        self.admin.delete(f'/api/users/{second}')
        a = Users.query.filter_by(user_id=first).one().username
        b = Users.query.filter_by(user_id=second).one().username
        self.assertNotEqual(a, b)
        self.assertNotIn('repetit', a + b)

    def test_deleted_user_disappears_from_list(self):
        user_id, _ = self.create_and_deactivate()
        self.admin.delete(f'/api/users/{user_id}')
        ids = [u['user_id'] for u in self.admin.get('/api/users').get_json()['users']]
        self.assertNotIn(user_id, ids)

    def test_deleted_user_does_not_exist_for_any_operation(self):
        """No es pot reactivar, editar ni restablir: seria ressuscitar un compte anònim."""
        user_id, _ = self.create_and_deactivate()
        self.admin.delete(f'/api/users/{user_id}')
        calls = [('PUT', f'/api/users/{user_id}', {'full_name': 'X', 'role': 'operator'}),
                 ('POST', f'/api/users/{user_id}/activate', {}),
                 ('POST', f'/api/users/{user_id}/deactivate', {}),
                 ('POST', f'/api/users/{user_id}/reset-password', {}),
                 ('POST', f'/api/users/{user_id}/close-sessions', {}),
                 ('DELETE', f'/api/users/{user_id}', {})]
        for method, path, body in calls:
            with self.subTest(method=method, path=path):
                r = self.admin.open(path, method=method, json=body)
                self.assertEqual(r.status_code, 404)
                self.assertEqual(r.get_json()['message_key'], 'MSG_USER_UNKNOWN')
        self.assertFalse(Users.query.filter_by(user_id=user_id).one().is_active)

    def test_deleted_user_cannot_log_in(self):
        user_id, password = self.create_and_deactivate(username='op')
        self.admin.delete(f'/api/users/{user_id}')
        deleted_name = Users.query.filter_by(user_id=user_id).one().username
        for username in ('op', deleted_name):
            with self.subTest(username=username):
                self.assertEqual(self.login_as(username, password)[1].status_code, 401)
                self.assertEqual(self.login_as(username, '!')[1].status_code, 401)

    def test_username_can_be_reused(self):
        user_id, _ = self.create_and_deactivate(username='op')
        self.admin.delete(f'/api/users/{user_id}')
        r = self.create(username='op')
        self.assertEqual(r.status_code, 201)
        self.assertNotEqual(r.get_json()['user']['user_id'], user_id)

    def test_cannot_delete_self(self):
        r = self.admin.delete(f'/api/users/{self.boss.user_id}')
        self.assertEqual(r.get_json()['message_key'], 'MSG_CANNOT_MODIFY_SELF')
        self.assertIsNone(Users.query.filter_by(user_id=self.boss.user_id).one().deleted_dts)

    def test_reserved_prefix(self):
        r = self.create(username='deleted-abc')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()['message_key'], 'MSG_USERNAME_RESERVED')
        self.assertEqual(r.get_json()['params'], {'prefix': 'deleted-'})

    def test_cli_does_not_see_deleted_users(self):
        user_id, _ = self.create_and_deactivate(username='op')
        self.admin.delete(f'/api/users/{user_id}')
        runner = self.app.test_cli_runner()
        self.assertNotIn('deleted-', runner.invoke(args=['users', 'list']).output)
        r = runner.invoke(args=['users', 'activate', 'deleted-' + user_id.replace('-', '')])
        self.assertNotEqual(r.exit_code, 0)

    def test_no_direct_user_queries_in_code(self):
        """
        Tota consulta d'usuaris ha de partir de mgr_auth.live_users(). Una
        consulta directa a Users.query inclouria els esborrats, i podria fer
        reaparèixer un compte anònim.
        """
        import re
        app_dir = os.path.join(os.path.dirname(__file__), '..', 'app')
        offenders = []
        for base, _, files in os.walk(app_dir):
            for name in files:
                if not name.endswith('.py'):
                    continue
                with open(os.path.join(base, name), encoding='utf-8') as f:
                    for n, line in enumerate(f, 1):
                        if re.search(r'\bUsers\.query\b', line) and 'def live_users' not in line \
                                and 'return Users.query.filter(Users.deleted_dts.is_(None))' not in line:
                            offenders.append(f'{name}:{n}: {line.strip()}')
        self.assertEqual(offenders, [], 'Feu servir mgr_auth.live_users()')

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
