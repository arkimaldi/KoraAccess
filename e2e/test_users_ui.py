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


class RowMenuNotClippedTest(E2ETestCase):
    """
    Regressió: el desplegable d'accions quedava retallat dins del contenidor de
    la taula (table-responsive) i calia fer scroll per veure les opcions. Passava
    sobretot amb poques files, quan la taula és baixa.
    """

    USERS = [TEST_USER, OPERATOR]

    def item_is_reachable(self, item):
        """
        Cert si un clic al centre de l'opció hi arribaria de debò. Un element
        retallat per overflow continua sent «visible» per a Playwright, però al
        seu punt hi ha un altre element: per això es comprova amb elementFromPoint.
        """
        box = item.bounding_box()
        if box is None:
            return False
        x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        # Bootstrap posa pointer-events: none a les opcions desactivades, i
        # elementFromPoint les travessa: per a aquestes, n'hi ha prou que el
        # punt caigui dins del menú, que és el que fallaria si estigués retallat.
        return self.page.evaluate(
            '''([x, y, el]) => {
                 const hit = document.elementFromPoint(x, y);
                 if (!hit) { return false; }
                 const target = el.disabled ? el.closest('.dropdown-menu') : el;
                 return target.contains(hit);
               }''',
            [x, y, item.element_handle()])

    def test_every_option_reachable_without_scrolling(self):
        self.page.goto(BASE_URL + '/users')
        self.page.wait_for_selector('table.users-table', timeout=10000)
        for username in (TEST_USER['username'], OPERATOR['username']):
            with self.subTest(username=username):
                row = self.page.locator(f'tr[data-username="{username}"]')
                row.locator('[data-row-actions]').click()
                self.page.wait_for_selector(f'tr[data-username="{username}"] .dropdown-menu.show')
                items = row.locator('.dropdown-menu.show .dropdown-item')
                self.assertGreater(items.count(), 0)
                for i in range(items.count()):
                    self.assertTrue(self.item_is_reachable(items.nth(i)),
                                    f'opció {items.nth(i).inner_text()!r} retallada')
                self.page.keyboard.press('Escape')
                self.page.wait_for_timeout(200)


class CloseOwnSessionsTest(E2ETestCase):
    """
    Sobre la pròpia fila, l'acció tanca les altres sessions i manté l'actual: si
    la tanqués, l'administrador es faria fora a si mateix sense voler.
    """

    USERS = [TEST_USER]

    def own_row(self):
        return self.page.locator(f'tr[data-username="{TEST_USER["username"]}"]')

    def open_own_menu(self):
        self.page.goto(BASE_URL + '/users')
        self.page.wait_for_selector('table.users-table', timeout=10000)
        self.own_row().locator('[data-row-actions]').click()
        return self.own_row().locator('[data-action="close-sessions"]')

    def test_disabled_with_only_the_current_session(self):
        action = self.open_own_menu()
        self.assertEqual(action.inner_text().strip(), 'Close other sessions')
        self.assertTrue(action.is_disabled())

    def test_closes_the_others_and_keeps_the_current_one(self):
        other = self.browser.new_page(locale=self.LOCALE)
        try:
            other.request.post(BASE_URL + '/api/auth/login', headers=CSRF_HEADERS,
                               data={'username': TEST_USER['username'], 'password': TEST_USER['password']})
            self.assertEqual(other.request.get(BASE_URL + '/api/auth/me').status, 200)

            action = self.open_own_menu()
            self.assertFalse(action.is_disabled())
            action.click()
            self.page.wait_for_selector('kora-modal-confirm .modal-content')
            self.assertEqual(self.page.locator('kora-modal-confirm .modal-body').inner_text().strip(),
                             'Close all your other open sessions? The session you are using now will stay open.')
            self.page.click('kora-modal-confirm [data-modal-confirm]')
            self.page.wait_for_timeout(800)

            # L'altra s'ha tancat; la d'aquí continua
            self.assertEqual(other.request.get(BASE_URL + '/api/auth/me').status, 401)
            self.assertEqual(self.page.request.get(BASE_URL + '/api/auth/me').status, 200)
            self.assertEqual(self.page.locator('kora-login').count(), 0)
            self.assertIn('1', self.own_row().locator('td').nth(5).inner_text())
        finally:
            other.close()


class OwnRowLabelCatalanTest(E2ETestCase):
    """La marca de la pròpia fila, en català."""

    LOCALE = 'ca-ES'

    def test_label(self):
        self.page.goto(BASE_URL + '/users')
        self.page.wait_for_selector('table.users-table', timeout=10000)
        self.page.wait_for_timeout(300)
        own = self.page.locator(f'tr[data-username="{TEST_USER["username"]}"] .badge').first
        self.assertEqual(own.inner_text().strip(), 'Vostè')
