# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Proves de la creació del primer administrador i de la protecció de la carpeta
de dades.

Els permisos de Windows (icacls) no es poden provar en Linux: aquí es comprova
quina ordre s'executaria. La verificació real s'ha de fer en un servidor Windows
(vegeu docs/autenticacio.md).
"""

import logging
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, mgr_auth, mgr_bootstrap      # noqa: E402
from app.db_models import Users                           # noqa: E402
from app.extensions import db                             # noqa: E402
from auth_helpers import TEST_PASSWORD, client_with_header, relax_rate_limit   # noqa: E402


class BootstrapTestCase(unittest.TestCase):

    def setUp(self):
        os.environ['KORAACCESS_DATA_DIR'] = '/tmp'
        self.app = create_app('dev', start_background=False)
        self.data_dir = tempfile.mkdtemp(prefix='kora_boot_')
        self.app.config['DATA_DIR'] = self.data_dir
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        relax_rate_limit(self.app)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def read_password(self):
        with open(mgr_bootstrap.initial_password_path(), encoding='utf-8') as f:
            return f.read().strip()

    # ------------------------------------------------------------------
    # Creació
    # ------------------------------------------------------------------
    def test_creates_admin_with_random_temporary_password(self):
        path = mgr_bootstrap.ensure_initial_admin()
        self.assertEqual(path, os.path.join(self.data_dir, 'secrets', 'initial-admin-password.txt'))
        user = Users.query.one()
        self.assertEqual((user.username, user.role, user.must_change_password), ('admin', 'admin', True))
        password = self.read_password()
        self.assertRegex(password, r'^[a-z2-9]{4}(-[a-z2-9]{4}){3}$')
        self.assertTrue(mgr_auth.verify_password(user.password_hash, password))

    def test_password_differs_between_installations(self):
        """Cap contrasenya fixa: cada instal·lació en té una de diferent."""
        mgr_bootstrap.ensure_initial_admin()
        first = self.read_password()
        db.drop_all()
        db.create_all()
        os.remove(mgr_bootstrap.initial_password_path())
        mgr_bootstrap.ensure_initial_admin()
        self.assertNotEqual(first, self.read_password())

    def test_does_nothing_if_users_exist(self):
        mgr_auth.create_user('maria', TEST_PASSWORD, 'admin')
        self.assertIsNone(mgr_bootstrap.ensure_initial_admin())
        self.assertFalse(os.path.exists(mgr_bootstrap.initial_password_path()))
        self.assertEqual(Users.query.count(), 1)

    def test_second_start_does_not_overwrite(self):
        mgr_bootstrap.ensure_initial_admin()
        first = self.read_password()
        self.assertIsNone(mgr_bootstrap.ensure_initial_admin())
        self.assertEqual(self.read_password(), first)

    def test_password_never_logged(self):
        with self.assertLogs(level='INFO') as logs:
            mgr_bootstrap.ensure_initial_admin()
        password = self.read_password()
        self.assertFalse(any(password in line for line in logs.output))
        self.assertTrue(any('initial-admin-password.txt' in line for line in logs.output))

    def test_not_created_by_manage_or_tests(self):
        """Amb start_background=False (manage.py, proves) no es crea cap administrador."""
        self.assertEqual(Users.query.count(), 0)

    # ------------------------------------------------------------------
    # Permisos (fora de Windows)
    # ------------------------------------------------------------------
    @unittest.skipIf(os.name == 'nt', 'permisos POSIX')
    def test_posix_permissions(self):
        mgr_bootstrap.ensure_initial_admin()
        dir_mode = stat.S_IMODE(os.stat(mgr_bootstrap.secrets_dir()).st_mode)
        file_mode = stat.S_IMODE(os.stat(mgr_bootstrap.initial_password_path()).st_mode)
        self.assertEqual(dir_mode, 0o700)
        self.assertEqual(file_mode, 0o600)

    # ------------------------------------------------------------------
    # Permisos (Windows, simulat)
    # ------------------------------------------------------------------
    def test_windows_icacls_command(self):
        """Es treu l'herència i es dona accés per SID, mai per nom de grup."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            result = mock.Mock()
            result.stdout = '"servidor\\\\kora","S-1-5-21-111-222-333-1001"\n'
            return result

        with mock.patch.object(mgr_bootstrap.os, 'name', 'nt'), \
             mock.patch.object(mgr_bootstrap.subprocess, 'run', side_effect=fake_run):
            self.assertTrue(mgr_bootstrap.restrict_directory(os.path.join(self.data_dir, 'x')))

        icacls = next(c for c in calls if c[0] == 'icacls')
        self.assertIn('/inheritance:r', icacls)
        grants = [icacls[i + 1] for i, a in enumerate(icacls) if a == '/grant:r']
        self.assertEqual(sorted(grants), sorted([
            '*S-1-5-18:(OI)(CI)F',                    # SYSTEM
            '*S-1-5-32-544:(OI)(CI)F',                # Administradors
            '*S-1-5-21-111-222-333-1001:(OI)(CI)F',   # el compte del servei
        ]))
        self.assertFalse(any('Administrators' in a or 'Administradores' in a for a in icacls))

    def test_no_admin_if_permissions_cannot_be_secured(self):
        """Més val crear l'administrador amb manage.py que deixar la contrasenya llegible."""
        with mock.patch.object(mgr_bootstrap, 'restrict_directory', return_value=False):
            self.assertIsNone(mgr_bootstrap.ensure_initial_admin())
        self.assertEqual(Users.query.count(), 0)
        self.assertFalse(os.path.exists(mgr_bootstrap.initial_password_path()))

    def test_secure_data_dir_only_when_configured(self):
        with mock.patch.object(mgr_bootstrap, 'restrict_directory') as restrict:
            self.app.config['SECURE_DATA_DIR'] = False
            mgr_bootstrap.secure_data_dir()
            restrict.assert_not_called()
            self.app.config['SECURE_DATA_DIR'] = True
            mgr_bootstrap.secure_data_dir()
            restrict.assert_called_once_with(self.data_dir)

    # ------------------------------------------------------------------
    # Primer login i esborrat del fitxer
    # ------------------------------------------------------------------
    def test_first_login_forces_change_and_removes_file(self):
        mgr_bootstrap.ensure_initial_admin()
        password = self.read_password()
        client = client_with_header(self.app)
        r = client.post('/api/auth/login', json={'username': 'admin', 'password': password})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()['user']['must_change_password'])
        self.assertEqual(client.get('/api/terminals').status_code, 403)

        r = client.put('/api/auth/password', json={'current_password': password,
                                                   'new_password': 'una-contrasenya-nova'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(os.path.exists(mgr_bootstrap.initial_password_path()))
        self.assertEqual(client.get('/api/terminals').status_code, 200)

    def test_reset_by_another_admin_removes_file(self):
        mgr_bootstrap.ensure_initial_admin()
        mgr_auth.set_temporary_password(mgr_auth.get_user_by_username('admin'))
        self.assertFalse(os.path.exists(mgr_bootstrap.initial_password_path()))

    def test_reset_from_command_line_removes_file(self):
        mgr_bootstrap.ensure_initial_admin()
        r = self.app.test_cli_runner().invoke(
            args=['users', 'reset-password', 'admin'], input='temporal-nova-1\ntemporal-nova-1\n')
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertFalse(os.path.exists(mgr_bootstrap.initial_password_path()))

    def test_other_users_do_not_remove_file(self):
        mgr_bootstrap.ensure_initial_admin()
        other = mgr_auth.create_user('maria', TEST_PASSWORD, 'operator')
        mgr_auth.change_password(other, 'una-contrasenya-nova')
        self.assertTrue(os.path.exists(mgr_bootstrap.initial_password_path()))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main(verbosity=2)
