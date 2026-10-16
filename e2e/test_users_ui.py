# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Proves e2e de la pantalla de gestió d'usuaris.

Les regles (permisos, últim administrador...) es proven al servidor, a
server/tests/test_users_api.py. Aquí es prova que la pantalla les reflecteix.
"""

import re
import unittest

from harness import BASE_URL, CSRF_HEADERS, E2ETestCase, TEST_USER

OPERATOR = {'username': 'operari', 'password': 'contrasenya-operari', 'role': 'operator',
            'full_name': 'Operari Prova'}


class UsersScreenTest(E2ETestCase):

    USERS = [TEST_USER, OPERATOR]

    def open_users(self):
        self.page.goto(BASE_URL + '/users')
        self.page.wait_for_selector('table.users-table', timeout=10000)
        self.page.wait_for_timeout(200)

    def user_row(self, username):
        return self.page.locator(f'tr[data-username="{username}"]')

    def row_action(self, username, action):
        self.user_row(username).locator('[data-row-actions]').click()
        self.page.locator(f'tr[data-username="{username}"] [data-action="{action}"]').click()

    def confirm(self):
        self.page.click('kora-modal-confirm [data-modal-confirm]')
        self.page.wait_for_timeout(600)

    def test_reload_on_users_stays_on_users(self):
        """
        Regressió: el router navega en arrencar, abans de saber qui és l'usuari, i
        el guard redirigia a Terminals un administrador que recarregava /users.
        """
        self.open_users()
        self.page.reload()
        self.page.wait_for_selector('table.users-table', timeout=10000)
        self.assertTrue(self.page.url.endswith('/users'))

    def test_admin_sees_users_menu(self):
        self.open_terminals()
        self.assertEqual(self.page.locator('kora-navbar a[href="/users"]').count(), 1)

    def test_list(self):
        self.open_users()
        own = self.user_row(TEST_USER['username'])
        self.assertIn('You', own.inner_text())
        self.assertIn('Administrator', own.inner_text())
        self.assertIn('Operator', self.user_row('operari').inner_text())

    def test_create_user_shows_temporary_password_once(self):
        self.open_users()
        self.page.click('[data-new-user]')
        self.page.wait_for_selector('kora-modal-user-form .modal-content')
        self.page.fill('#uf-username', 'NouOperari')
        self.page.fill('#uf-full-name', 'Nou Operari')
        self.page.click('kora-modal-user-form [data-modal-confirm]')

        self.page.wait_for_selector('kora-modal-temporary-password .modal-content', timeout=5000)
        password = self.page.input_value('kora-modal-temporary-password input.temp-password')
        self.assertRegex(password, r'^[a-z2-9]{4}(-[a-z2-9]{4}){3}$')
        self.page.click('kora-modal-temporary-password [data-modal-confirm]')

        row = self.user_row('nouoperari')
        row.wait_for(timeout=5000)
        self.assertIn('Password change pending', row.inner_text())
        # La contrasenya no torna a aparèixer a la pantalla
        self.assertNotIn(password, self.page.content())

        # I amb ella s'entra, però obliga a canviar-la
        other = self.browser.new_page(locale=self.LOCALE)
        try:
            r = other.request.post(BASE_URL + '/api/auth/login', headers=CSRF_HEADERS,
                                   data={'username': 'nouoperari', 'password': password})
            self.assertTrue(r.ok)
            other.goto(BASE_URL + '/')
            other.wait_for_selector('kora-change-password', timeout=10000)
        finally:
            other.close()

    def test_server_error_shown_in_form(self):
        self.open_users()
        self.page.click('[data-new-user]')
        self.page.fill('#uf-username', 'operari')        # ja existeix
        self.page.click('kora-modal-user-form [data-modal-confirm]')
        self.page.wait_for_selector('kora-modal-user-form .modal-error', timeout=5000)
        self.assertEqual(self.page.locator('kora-modal-user-form .modal-error').inner_text().strip(),
                         'The username operari is already in use.')
        self.page.click('kora-modal-user-form button:has-text("Cancel")')

    def test_edit_full_name(self):
        self.open_users()
        self.row_action('operari', 'edit')
        self.page.wait_for_selector('kora-modal-user-form .modal-content')
        self.assertTrue(self.page.locator('#uf-username').is_disabled())
        self.page.fill('#uf-full-name', 'Nom Canviat')
        self.page.click('kora-modal-user-form [data-modal-confirm]')
        self.page.wait_for_timeout(800)
        self.assertIn('Nom Canviat', self.user_row('operari').inner_text())

    def test_admin_cannot_deactivate_or_demote_self(self):
        self.open_users()
        self.user_row(TEST_USER['username']).locator('[data-row-actions]').click()
        menu = self.user_row(TEST_USER['username']).locator('.dropdown-menu')
        self.assertEqual(menu.locator('[data-action="deactivate"]').count(), 0)
        menu.locator('[data-action="edit"]').click()
        self.page.wait_for_selector('kora-modal-user-form .modal-content')
        self.assertTrue(self.page.locator('#uf-role').is_disabled())
        self.page.click('kora-modal-user-form button:has-text("Cancel")')

    def test_deactivate_and_activate(self):
        self.open_users()
        self.row_action('operari', 'deactivate')
        self.page.wait_for_selector('kora-modal-confirm .modal-content')
        self.assertIn('operari', self.page.locator('kora-modal-confirm .modal-body').inner_text())
        self.confirm()
        self.assertIn('Inactive', self.user_row('operari').inner_text())

        self.row_action('operari', 'activate')
        self.page.wait_for_timeout(600)
        self.assertIn('Active', self.user_row('operari').inner_text())
        self.assertNotIn('Inactive', self.user_row('operari').inner_text())

    def test_reset_password(self):
        self.open_users()
        self.row_action('operari', 'reset')
        self.confirm()
        self.page.wait_for_selector('kora-modal-temporary-password .modal-content', timeout=5000)
        self.assertIn('operari', self.page.locator('kora-modal-temporary-password .modal-body').inner_text())
        self.page.click('kora-modal-temporary-password [data-modal-confirm]')
        self.page.wait_for_timeout(500)
        self.assertIn('Password change pending', self.user_row('operari').inner_text())


class OperatorCannotManageUsersTest(E2ETestCase):

    LOGIN = False
    USERS = [TEST_USER, OPERATOR]

    def test_no_menu_and_redirected(self):
        self.login_via_api(OPERATOR['username'], OPERATOR['password'])
        self.page.goto(BASE_URL + '/users')
        self.page.wait_for_selector('table.grid', timeout=10000)   # ha acabat a Terminals
        self.assertTrue(self.page.url.endswith('/terminals'))
        self.assertEqual(self.page.locator('kora-navbar a[href="/users"]').count(), 0)
        # I el servidor també li tanca la porta
        self.assertEqual(self.page.request.get(BASE_URL + '/api/users').status, 403)


if __name__ == '__main__':
    unittest.main(verbosity=2)
