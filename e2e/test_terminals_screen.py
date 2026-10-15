# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Proves e2e de la pantalla de Terminals.

Cobreixen errors que les proves del servidor no podien veure, perquè només
apareixen al navegador:
  - totes les files sense registre entraven en edició alhora;
  - en editar, la columna s'eixamplava i la taula es desplaçava;
  - la taula es reordenava a cada keep-alive.
"""

import unittest

from harness import BASE_URL, E2ETestCase

ENROLLED = 'enrolled'
ENROLL_PENDING = 'enroll_pending'
DELETE_PENDING = 'delete_pending'

FOREIGN_URL = 'https://altre.exemple.com/v1/Cloud/Event'


class DescriptionDisplayTest(E2ETestCase):
    """Què es mostra a la columna de descripció en cada cas."""

    SEED = [
        {'eui64': '00000000000000A1', 'description': 'Porta principal', 'status': ENROLLED},
        {'eui64': '00000000000000A2', 'description': '', 'status': ENROLLED},
        {'eui64': '00000000000000A3', 'description': '', 'status': ENROLL_PENDING},
        {'eui64': '00000000000000A4', 'description': '', 'status': DELETE_PENDING},
    ]
    OBSERVATIONS = [
        ('00000000000000F1', ''),            # FREE
        ('00000000000000F2', ''),            # FREE
        ('00000000000000F3', FOREIGN_URL),   # FOREIGN
    ]

    EXPECTED = {
        '00000000000000A1': ('Porta principal', True),
        '00000000000000A2': ('Afegir descripció', True),
        '00000000000000A3': ('Afegir descripció', True),
        '00000000000000A4': ('—', False),
        '00000000000000F1': ('—', False),
        '00000000000000F2': ('—', False),
        '00000000000000F3': ('—', False),
    }

    def test_each_row_shows_the_right_text(self):
        self.open_terminals()
        for eui64, (text, is_link) in self.EXPECTED.items():
            with self.subTest(eui64=eui64):
                cell = self.desc_cell(eui64)
                self.assertEqual(cell.inner_text().strip(), text)
                self.assertEqual(cell.locator('.desc-link').count() > 0, is_link)

    def test_no_row_is_in_edit_mode_on_load(self):
        """
        Regressió: les files sense registre tenen device_id null, igual que
        editingId fora d'edició, i entraven totes en edició alhora.
        """
        self.open_terminals()
        self.assertEqual(self.page.locator('.desc-input').count(), 0)

    def test_rows_without_editable_description_do_not_open_editor(self):
        self.open_terminals()
        for eui64 in ('00000000000000A4', '00000000000000F1', '00000000000000F3'):
            with self.subTest(eui64=eui64):
                self.desc_cell(eui64).click()
                self.page.wait_for_timeout(200)
                self.assertEqual(self.page.locator('.desc-input').count(), 0)

    def test_only_the_clicked_row_opens_and_text_does_not_leak(self):
        self.open_terminals()
        self.desc_cell('00000000000000A2').click()
        self.page.wait_for_timeout(300)
        self.assertEqual(self.page.locator('.desc-input').count(), 1)
        self.page.keyboard.type('Text de prova')
        for eui64 in self.EXPECTED:
            if eui64 == '00000000000000A2':
                continue
            with self.subTest(eui64=eui64):
                self.assertNotIn('Text de prova', self.desc_cell(eui64).inner_text())
        self.page.keyboard.press('Escape')


class DescriptionEditTest(E2ETestCase):
    """Edició de la descripció: desar, cancel·lar i buidar."""

    SEED = [
        {'eui64': '00000000000000B1', 'description': 'Porta principal', 'status': ENROLLED},
        {'eui64': '00000000000000B2', 'description': 'Magatzem', 'status': ENROLLED},
        {'eui64': '00000000000000B3', 'description': 'Moll', 'status': ENROLLED},
        {'eui64': '00000000000000B4', 'description': 'Recepció', 'status': ENROLLED},
    ]

    def edit(self, eui64):
        self.desc_cell(eui64).click()
        self.page.wait_for_timeout(300)
        self.assertEqual(self.page.locator('.desc-input:focus').count(), 1)

    def test_escape_cancels(self):
        self.open_terminals()
        self.edit('00000000000000B1')
        self.page.keyboard.type('canviat')
        self.page.keyboard.press('Escape')
        self.page.wait_for_timeout(300)
        self.assertEqual(self.desc_cell('00000000000000B1').inner_text().strip(), 'Porta principal')

    def test_losing_focus_cancels(self):
        self.open_terminals()
        self.edit('00000000000000B2')
        self.page.keyboard.type('canviat')
        self.page.locator('h2').click()
        self.page.wait_for_timeout(300)
        self.assertEqual(self.desc_cell('00000000000000B2').inner_text().strip(), 'Magatzem')

    def test_enter_saves(self):
        self.open_terminals()
        self.edit('00000000000000B3')
        self.page.keyboard.press('Control+a')
        self.page.keyboard.type('Moll de càrrega')
        self.page.keyboard.press('Enter')
        self.page.wait_for_timeout(1200)
        self.assertEqual(self.desc_cell('00000000000000B3').inner_text().strip(), 'Moll de càrrega')

    def test_description_can_be_emptied(self):
        self.open_terminals()
        self.edit('00000000000000B4')
        self.page.keyboard.press('Control+a')
        self.page.keyboard.press('Delete')
        self.page.keyboard.press('Enter')
        self.page.wait_for_timeout(1200)
        self.assertEqual(self.desc_cell('00000000000000B4').inner_text().strip(), 'Afegir descripció')

    def test_column_does_not_shift_when_editing(self):
        """Regressió: en entrar en edició, la columna s'eixamplava."""
        self.open_terminals()
        eui_cell = self.row('00000000000000B1').locator('td.mono').first
        x_before = eui_cell.bounding_box()['x']
        self.edit('00000000000000B1')
        x_after = eui_cell.bounding_box()['x']
        self.page.keyboard.press('Escape')
        self.assertAlmostEqual(x_before, x_after, delta=1)


class PollingTest(E2ETestCase):
    """Ritme del refresc i pausa durant l'edició."""

    SEED = [
        {'eui64': '00000000000000C1', 'description': 'Porta', 'status': ENROLLED},
        # Amb un delete_pending el polling va al ritme ràpid, de 5 s.
        {'eui64': '00000000000000C2', 'description': 'Sortint', 'status': DELETE_PENDING},
    ]

    def count_list_requests(self, ms):
        requests = []
        handler = (lambda r: requests.append(1)
                   if r.url.endswith('/api/terminals') and r.method == 'GET' else None)
        self.page.on('request', handler)
        self.page.wait_for_timeout(ms)
        self.page.remove_listener('request', handler)
        return len(requests)

    def test_initial_load_shows_spinner_then_table(self):
        self.page.goto(BASE_URL + '/')
        self.page.wait_for_timeout(300)
        self.assertTrue(self.page.locator('.initial-loading').is_visible())
        self.assertEqual(self.page.locator('table.grid').count(), 0)
        self.page.wait_for_selector('table.grid', timeout=10000)
        self.assertEqual(self.page.locator('.initial-loading').count(), 0)

    def test_fast_polling_while_operation_pending(self):
        self.open_terminals()
        self.assertGreaterEqual(self.count_list_requests(11000), 2)

    def test_polling_paused_while_editing(self):
        self.open_terminals()
        self.desc_cell('00000000000000C1').click()
        self.page.wait_for_timeout(300)
        self.page.keyboard.type(' a mig escriure')

        self.assertEqual(self.count_list_requests(11000), 0)
        self.assertTrue(self.page.locator('.desc-input').input_value().endswith('a mig escriure'))

        self.page.keyboard.press('Escape')
        self.assertGreaterEqual(self.count_list_requests(6000), 1)


class OrderingTest(E2ETestCase):
    """Ordre estable: per descripció, després per EUI64, i els no gestionats al final."""

    SEED = [
        {'eui64': '00000000000000D3', 'description': 'Zona de càrrega', 'status': ENROLLED},
        {'eui64': '00000000000000D1', 'description': 'àrea de descans', 'status': ENROLLED},
        {'eui64': '00000000000000D2', 'description': 'Bústies', 'status': ENROLLED},
        {'eui64': '00000000000000D9', 'description': '', 'status': ENROLLED},
    ]
    OBSERVATIONS = [('00000000000000D0', '')]   # FREE

    def visible_order(self):
        return [self.page.locator('tbody tr').nth(i).locator('td.mono').first.inner_text().strip()
                for i in range(self.page.locator('tbody tr').count())]

    def test_table_order(self):
        self.open_terminals()
        self.assertEqual(self.visible_order(), [
            '00000000000000D1',   # àrea de descans
            '00000000000000D2',   # Bústies
            '00000000000000D3',   # Zona de càrrega
            '00000000000000D9',   # sense descripció
            '00000000000000D0',   # no gestionat, al final
        ])


if __name__ == '__main__':
    unittest.main(verbosity=2)
