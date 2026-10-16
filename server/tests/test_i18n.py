# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Coherència de les traduccions entre el servidor i el frontend.

El servidor envia claus (server/app/messages.py) i el frontend les tradueix
(webapp/src/assets/i18n/*.json). Són dos llocs diferents que han de quadrar, i
cap compilador no ho comprova: una clau que falta només es veu quan l'usuari
rep l'error, i en l'idioma en què no l'havíeu provat.

Aquesta prova és possible perquè servidor i frontend són al mateix repositori.
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

from app.messages import MESSAGES   # noqa: E402

I18N_DIR = os.path.join(ROOT, 'webapp', 'src', 'assets', 'i18n')
APP_DIR = os.path.join(ROOT, 'webapp', 'src', 'app')
LANGUAGES = ('en', 'ca', 'es')

# La mateixa expressió que fa servir ngx-extract.js per trobar les claus.
EXTRACT_RE = re.compile(r"""{{\s*['"`]([^'"`]+)['"`]?\s*\| translate\s*}}""")
SYS_RE = re.compile(r"""['"`](_sys_\w+)""")
# Claus passades des del codi als modals: titleKey: '...', textKey: '...', etc.
CODE_KEY_RE = re.compile(r"""\b\w*Key\s*:\s*['"`]([^'"`]+)['"`]""")
# Claus _sys_ construïdes a partir d'un prefix: '_sys_link_' + estat, '_sys_role_' + perfil.
DYNAMIC_SYS_KEYS = {
    '_sys_link_': ('online', 'lost', 'severe_lost', 'offline'),
    '_sys_role_': ('admin', 'operator'),
}
PY_PARAM_RE = re.compile(r'(?<!\{)\{(\w+)\}(?!\})')
NGX_PARAM_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def load(lang):
    with open(os.path.join(I18N_DIR, f'{lang}.json'), encoding='utf8') as f:
        return json.load(f)


def source_files():
    for base, _, files in os.walk(APP_DIR):
        for name in files:
            if name.endswith(('.ts', '.html')):
                with open(os.path.join(base, name), encoding='utf8') as f:
                    yield name, f.read()


class I18nTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dicts = {lang: load(lang) for lang in LANGUAGES}

    def test_all_languages_have_the_same_keys(self):
        en = set(self.dicts['en'])
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                self.assertEqual(set(self.dicts[lang]) - en, set(), 'claus que no són a en.json')
                self.assertEqual(en - set(self.dicts[lang]), set(), f'claus que falten a {lang}.json')

    def test_no_empty_or_pending_translations(self):
        for lang, d in self.dicts.items():
            for key, value in d.items():
                with self.subTest(lang=lang, key=key):
                    self.assertTrue(value.strip(), 'traducció buida')
                    self.assertNotIn('TODO', value)

    def test_every_server_message_is_translated(self):
        for key in MESSAGES:
            for lang in LANGUAGES:
                with self.subTest(key=key, lang=lang):
                    self.assertIn(key, self.dicts[lang])

    def test_server_message_params_match_translations(self):
        """
        Si el servidor envia {limit} i una traducció escriu {{limt}}, l'usuari
        veuria el marcador sense substituir.
        """
        for key, text in MESSAGES.items():
            expected = set(PY_PARAM_RE.findall(text))
            for lang in LANGUAGES:
                with self.subTest(key=key, lang=lang):
                    got = set(NGX_PARAM_RE.findall(self.dicts[lang].get(key, '')))
                    self.assertEqual(got, expected)

    def test_english_matches_server_fallback(self):
        """L'anglès del frontend ha de dir el mateix que el text de reserva del servidor."""
        for key, text in MESSAGES.items():
            with self.subTest(key=key):
                self.assertEqual(self.dicts['en'][key], PY_PARAM_RE.sub(r'{{\1}}', text))

    def test_template_texts_are_translated(self):
        """
        Tot text marcat amb | translate a les plantilles ha de ser al diccionari.
        Detecta un en.json que no s'ha tornat a extreure després de canviar una
        plantilla.
        """
        for name, content in source_files():
            for key in EXTRACT_RE.findall(content):
                with self.subTest(file=name, key=key):
                    for lang in LANGUAGES:
                        self.assertIn(key, self.dicts[lang])

    def test_sys_keys_used_in_code_are_translated(self):
        """
        Les claus _sys_ es construeixen al codi i ngx-extract no les troba: s'han
        de mantenir a mà, i és fàcil oblidar-ne alguna.
        """
        for name, content in source_files():
            for key in SYS_RE.findall(content):
                if key in DYNAMIC_SYS_KEYS:   # prefix d'una clau dinàmica, vegeu sota
                    continue
                with self.subTest(file=name, key=key):
                    for lang in LANGUAGES:
                        self.assertIn(key, self.dicts[lang])

    def test_dynamic_sys_keys_are_translated(self):
        """'_sys_link_' + estat i '_sys_role_' + perfil: cal una clau per a cada valor."""
        for prefix, values in DYNAMIC_SYS_KEYS.items():
            for value in values:
                for lang in LANGUAGES:
                    with self.subTest(key=prefix + value, lang=lang):
                        self.assertIn(prefix + value, self.dicts[lang])

    def test_keys_passed_from_code_are_sys_or_msg(self):
        """
        Una clau que es passa des del codi (titleKey, textKey...) no la troba
        ngx-extract. Si no és _sys_ ni MSG_, el procediment de la casa no la
        restaura després d'extreure, i desapareixeria d'en.json en silenci.
        """
        for name, content in source_files():
            if not name.endswith('.ts'):
                continue
            for key in CODE_KEY_RE.findall(content):
                with self.subTest(file=name, key=key):
                    self.assertTrue(key.startswith(('_sys_', 'MSG_')),
                                    f'{key!r} es passa des del codi: ha de ser una clau _sys_')
                    for lang in LANGUAGES:
                        self.assertIn(key, self.dicts[lang])

    def test_master_dictionary_matches_language_files(self):
        """ngx_tool_dict.json ha de quadrar amb els fitxers d'idioma."""
        with open(os.path.join(I18N_DIR, 'ngx_tool_dict.json'), encoding='utf8') as f:
            master = json.load(f)
        self.assertEqual(set(master), set(self.dicts['en']))
        for key, entry in master.items():
            for lang in LANGUAGES:
                with self.subTest(key=key, lang=lang):
                    self.assertEqual(entry[f'{lang}.json'], self.dicts[lang][key])


if __name__ == '__main__':
    unittest.main(verbosity=2)
