# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Proves e2e del login, el tancament de sessió i el canvi de contrasenya.

La seguretat de debò es prova al servidor (server/tests/test_auth.py). Aquí es
prova que la pantalla reacciona bé a cada situació.
"""

import unittest

from harness import BASE_URL, CSRF_HEADERS, E2ETestCase, TEST_USER

OTHER_PASSWORD = 'una-altra-contrasenya'


class LoginScreenTest(E2ETestCase):

    LOGIN = False

    def open_app(self):
        self.page.goto(BASE_URL + '/')
        self.page.wait_for_selector('kora-login', timeout=10000)

    def fill_and_submit(self, username, password):
        self.page.fill('#login-username', username)
        self.page.fill('#login-password', password)
        self.page.click('kora-login button[type=submit]')

    def test_without_session_shows_login(self):
        self.open_app()
        self.assertEqual(self.page.locator('kora-terminals').count(), 0)
        self.assertEqual(self.page.locator('kora-navbar').count(), 0)
        # Sense sessió prèvia no s'ha d'avisar de cap caducitat
        self.assertEqual(self.page.locator('kora-login .auth-info').count(), 0)

    def test_wrong_password(self):
        self.open_app()
        self.fill_and_submit(TEST_USER['username'], 'contrasenya-dolenta')
        self.page.wait_for_selector('.auth-error', timeout=5000)
        self.assertEqual(self.page.locator('.auth-error').inner_text().strip(),
                         'Incorrect username or password.')
        self.assertEqual(self.page.input_value('#login-password'), '')   # es buida

    def test_login_and_logout(self):
        self.open_app()
        self.fill_and_submit(TEST_USER['username'].upper(), TEST_USER['password'])
        self.page.wait_for_selector('table.grid', timeout=10000)
        # Inicials del nom complet a l'avatar, i el nom sencer dins del menú
        self.assertEqual(self.page.locator('kora-navbar button.avatar').inner_text().strip(), 'PE')
        self.open_avatar_menu()
        self.assertIn(TEST_USER['full_name'], self.page.locator('kora-navbar .dropdown-menu').inner_text())

        self.page.click('kora-navbar [data-logout]')
        self.page.wait_for_selector('kora-login', timeout=5000)
        self.assertEqual(self.page.locator('kora-terminals').count(), 0)
        # I la sessió s'ha tancat de debò al servidor
        self.assertEqual(self.page.request.get(BASE_URL + '/api/terminals').status, 401)


class SessionExpiredTest(E2ETestCase):
    """Si la sessió es perd mentre es fa servir, es torna al login amb un avís."""

    # Un delete_pending fa que la pantalla refresqui cada 5 s
    SEED = [{'eui64': '00000000000000E5', 'description': 'Sortint', 'status': 'delete_pending'}]

    def test_returns_to_login_with_notice(self):
        self.open_terminals()
        # Es tanca la sessió per darrere, com si hagués caducat o l'haguessin revocat
        self.page.request.post(BASE_URL + '/api/auth/logout', headers=CSRF_HEADERS)
        self.page.wait_for_selector('kora-login', timeout=12000)
        self.assertEqual(self.page.locator('kora-login .auth-info').inner_text().strip(),
                         'Your session has expired. Please log in again.')


class ForcedPasswordChangeTest(E2ETestCase):

    LOGIN = False
    USERS = [TEST_USER, {'username': 'temporal', 'password': 'contrasenya-temporal',
                         'role': 'operator', 'must_change_password': True}]

    def test_must_change_before_continuing(self):
        self.login_via_api('temporal', 'contrasenya-temporal')
        self.page.goto(BASE_URL + '/')
        self.page.wait_for_selector('kora-change-password', timeout=10000)
        self.assertEqual(self.page.locator('kora-terminals').count(), 0)
        self.assertEqual(self.page.locator('kora-change-password .auth-info').inner_text().strip(),
                         'You must change your password before continuing.')
        # No es pot cancel·lar, només tancar la sessió
        self.assertEqual(self.page.locator('kora-change-password button:has-text("Cancel")').count(), 0)

        # Les dues contrasenyes noves no coincideixen
        self.page.fill('#cp-current', 'contrasenya-temporal')
        self.page.fill('#cp-new', OTHER_PASSWORD)
        self.page.fill('#cp-confirm', OTHER_PASSWORD + 'x')
        self.page.click('kora-change-password button[type=submit]')
        self.assertEqual(self.page.locator('.auth-error').inner_text().strip(), 'The passwords do not match.')

        self.page.fill('#cp-confirm', OTHER_PASSWORD)
        self.page.click('kora-change-password button[type=submit]')
        self.page.wait_for_selector('table.grid', timeout=10000)


class VoluntaryPasswordChangeTest(E2ETestCase):

    def open_change_password(self):
        self.open_avatar_menu()
        self.page.click('kora-navbar a[href="/password"]')

    def test_cancel_returns_to_terminals(self):
        self.open_terminals()
        self.open_change_password()
        self.page.wait_for_selector('kora-change-password', timeout=5000)
        self.assertEqual(self.page.locator('kora-terminals').count(), 0)
        self.page.click('kora-change-password button:has-text("Cancel")')
        self.page.wait_for_selector('table.grid', timeout=10000)

    def test_server_rejects_wrong_current_password(self):
        self.open_terminals()
        self.open_change_password()
        self.page.fill('#cp-current', 'no-es-la-meva')
        self.page.fill('#cp-new', OTHER_PASSWORD)
        self.page.fill('#cp-confirm', OTHER_PASSWORD)
        self.page.click('kora-change-password button[type=submit]')
        self.page.wait_for_selector('.auth-error', timeout=5000)
        self.assertEqual(self.page.locator('.auth-error').inner_text().strip(),
                         'The current password is incorrect.')


class UserLanguageTest(E2ETestCase):
    """L'idioma desat a l'usuari passa per davant del del navegador."""

    LOGIN = False
    USERS = [TEST_USER, {'username': 'pepa', 'password': 'contrasenya-pepa',
                         'role': 'operator', 'language': 'es'}]

    def test_user_language_applies_after_login(self):
        self.login_via_api('pepa', 'contrasenya-pepa')
        self.page.goto(BASE_URL + '/')
        self.page.wait_for_selector('table.grid', timeout=10000)
        self.page.wait_for_timeout(300)
        self.assertEqual(self.page.locator('thead th').first.inner_text().strip().lower(), 'descripción')


if __name__ == '__main__':
    unittest.main(verbosity=2)


class FreshInstallationTest(E2ETestCase):
    """
    Instal·lació nova: el servidor arrenca sense cap usuari i crea l'administrador
    inicial amb una contrasenya aleatòria, desada a la carpeta de dades.
    """

    LOGIN = False
    USERS = []

    def test_initial_admin_flow(self):
        import os
        path = os.path.join(self.server.data_dir, 'secrets', 'initial-admin-password.txt')
        self.assertTrue(os.path.exists(path), 'el servidor no ha creat el fitxer de la contrasenya inicial')
        with open(path, encoding='utf-8') as f:
            password = f.read().strip()

        # Login per la pantalla, com ho faria l'instal·lador
        self.page.goto(BASE_URL + '/')
        self.page.wait_for_selector('kora-login', timeout=10000)
        self.page.fill('#login-username', 'admin')
        self.page.fill('#login-password', password)
        self.page.click('kora-login button[type=submit]')

        # Ha de canviar la contrasenya abans de res
        self.page.wait_for_selector('kora-change-password', timeout=10000)
        self.page.fill('#cp-current', password)
        self.page.fill('#cp-new', 'la-contrasenya-definitiva')
        self.page.fill('#cp-confirm', 'la-contrasenya-definitiva')
        self.page.click('kora-change-password button[type=submit]')
        self.page.wait_for_selector('table.grid', timeout=10000)

        # El fitxer ja no hi és: la contrasenya inicial ha deixat de ser vàlida
        self.assertFalse(os.path.exists(path))
        # I la contrasenya no apareix al log del servidor
        self.assertNotIn(password, self.server.read_log())
