# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Proves e2e de l'idioma de la interfície.

La traducció la fa tota el frontend: tant els textos de la pantalla com els
missatges que envia el servidor, que arriben com a claus.
"""

import unittest

from harness import BASE_URL, CSRF_HEADERS, E2ETestCase

FOREIGN_URL = 'https://altre.exemple.com/v1/Cloud/Event'


def header(page):
    return page.locator('thead th').first.inner_text().strip()


class BrowserLanguageTest(E2ETestCase):
    """Sense idioma desat, es fa servir el del navegador."""

    LOCALE = 'ca-ES'
    SEED = [{'eui64': '00000000000000E1', 'description': '', 'status': 'enrolled'}]

    def test_uses_browser_language(self):
        self.open_terminals()
        self.assertEqual(header(self.page).lower(), 'descripció')
        self.assertEqual(self.desc_cell('00000000000000E1').inner_text().strip(), 'Afegir descripció')
        self.assertEqual(self.page.locator('html').get_attribute('lang'), 'ca')


class UnsupportedBrowserLanguageTest(E2ETestCase):
    """Un idioma no suportat cau a l'anglès."""

    LOCALE = 'de-DE'

    def test_falls_back_to_english(self):
        self.open_terminals()
        self.assertEqual(header(self.page).lower(), 'description')


class LanguageSelectorTest(E2ETestCase):
    """El selector canvia l'idioma a l'instant i el recorda en recarregar."""

    SEED = [{'eui64': '00000000000000E2', 'description': '', 'status': 'enrolled'}]

    def test_selector_changes_and_persists(self):
        """Amb la sessió iniciada, l'idioma es tria al menú de l'avatar i es desa a l'usuari."""
        self.open_terminals()
        self.assertEqual(header(self.page).lower(), 'description')

        self.open_avatar_menu()
        self.page.click('kora-navbar [data-lang=es]')
        self.page.wait_for_timeout(500)
        self.assertEqual(header(self.page).lower(), 'descripción')
        self.assertEqual(self.desc_cell('00000000000000E2').inner_text().strip(), 'Añadir descripción')

        self.page.reload()
        self.page.wait_for_selector('table.grid', timeout=10000)
        self.page.wait_for_timeout(300)
        self.assertEqual(header(self.page).lower(), 'descripción')
        self.open_avatar_menu()
        self.assertEqual(self.page.locator('kora-navbar [data-lang].active').get_attribute('data-lang'), 'es')


class ServerMessagesTranslationTest(E2ETestCase):
    """
    Els missatges del servidor arriben com a claus i es tradueixen aquí. És la
    prova de punta a punta que la clau, els paràmetres i la traducció quadren.
    """

    LOCALE = 'ca-ES'
    SEED = [
        {'eui64': '00000000000000E3', 'description': 'Porta', 'status': 'enrolled'},
        {'eui64': '00000000000000E4', 'description': 'Pendent', 'status': 'enroll_pending'},
    ]
    # El dispositiu enrolat apareix al discovery apuntant a un altre servidor.
    OBSERVATIONS = [('00000000000000E3', FOREIGN_URL)]

    def test_warning_is_translated(self):
        self.open_terminals()
        warning = self.row('00000000000000E3').locator('.warn').first.inner_text().strip()
        self.assertEqual(warning, 'El dispositiu apunta ara a un altre servidor: cal un reset físic.')

    def test_error_and_dialog_are_translated(self):
        """
        Es fa desaparèixer el registre per darrere i després es demana esborrar-lo
        des de la pantalla: el servidor respon 404 amb MSG_DEVICE_UNKNOWN.
        """
        self.open_terminals()
        # page.request comparteix la sessió del navegador
        terminals = self.page.request.get(BASE_URL + '/api/terminals').json()['terminals']
        device_id = next(t['device_id'] for t in terminals if t['eui64'] == '00000000000000E4')
        self.page.request.delete(f'{BASE_URL}/api/terminals/{device_id}', headers=CSRF_HEADERS)

        self.row('00000000000000E4').locator('[data-action=delete]').click()
        self.page.wait_for_selector('kora-modal-confirm .modal-content', timeout=3000)

        # La confirmació, traduïda i amb el paràmetre interpolat
        self.assertEqual(self.page.locator('kora-modal-confirm .modal-body').inner_text().strip(),
                         'Esborrar el registre de 00000000000000E4?')
        self.page.click('kora-modal-confirm [data-modal-confirm]')
        self.page.wait_for_timeout(1000)
        # L'error del servidor, traduït
        self.assertEqual(self.page.locator('.page-error').inner_text().strip(), 'Dispositiu desconegut.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
