# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Arnès de les proves e2e.

Cada classe de proves arrenca el seu propi servidor KoraAccess, aïllat del de
desenvolupament:
  - port HTTP i port de discovery propis, per no xocar amb un servidor que
    tinguis corrent al 8080 i al 60100;
  - base de dades en una carpeta temporal, que s'esborra en acabar;
  - serveix directament webapp/dist, sense copiar-lo a server/static.

Les observacions de discovery s'injecten enviant per UDP respostes
«kapri_discovery» al port de discovery del servidor, exactament com ho faria un
dispositiu real. El servidor les accepta perquè escolta respostes de qualsevol
origen (vegeu docs/pantalla-terminals.md, «El listener escolta sempre»).
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SERVER_DIR = os.path.join(ROOT, 'server')
WEBAPP_DIST = os.path.join(ROOT, 'webapp', 'dist')
SEED_SCRIPT = os.path.join(os.path.dirname(__file__), 'seed.py')
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), 'artifacts')

HTTP_PORT = int(os.environ.get('KORAACCESS_E2E_PORT', 8099))
DISCOVERY_PORT = int(os.environ.get('KORAACCESS_E2E_DISCOVERY_PORT', 60199))
BASE_URL = f'http://127.0.0.1:{HTTP_PORT}'

# Ha de coincidir amb la URL de desenvolupament: és la que fa servir el
# servidor per decidir si una observació apunta a ell o a un altre.
SERVER_URL = 'http://10.0.0.144:8080/v1/Cloud/Event'

SERVER_START_TIMEOUT_S = 30

# Usuari amb què les proves inicien sessió si no en declaren cap altre.
TEST_USER = {'username': 'e2e', 'password': 'contrasenya-e2e', 'role': 'admin', 'full_name': 'Proves E2E'}
CSRF_HEADERS = {'X-Requested-With': 'KoraAccess'}


def check_build():
    if not os.path.isfile(os.path.join(WEBAPP_DIST, 'index.html')):
        raise RuntimeError(
            "No hi ha build de l'Angular a webapp/dist. "
            "Executeu 'python e2e/run_e2e.py --build' o 'npm run build' dins de webapp/.")


class ServerUnderTest:
    """Un servidor KoraAccess de proves, amb dades i ports propis."""

    def __init__(self):
        self.data_dir = tempfile.mkdtemp(prefix='kora_e2e_')
        self.process = None
        self.env = dict(os.environ)
        self.env.update({
            'KORAACCESS_CONFIG': 'dev',
            'KORAACCESS_DATA_DIR': self.data_dir,
            'KORAACCESS_PORT': str(HTTP_PORT),
            'KORAACCESS_DISCOVERY_PORT': str(DISCOVERY_PORT),
            'KORAACCESS_STATIC_DIR': WEBAPP_DIST,
            'KORAACCESS_PUBLIC_URL': SERVER_URL,
            # Cada prova inicia sessió: amb el límit real de 5 per minut, la
            # suite es bloquejaria a si mateixa.
            'KORAACCESS_LOGIN_RATE_LIMIT': '1000 per minute',
        })

    def seed(self, devices, users=()):
        """Sembra dispositius i usuaris. S'ha de cridar abans de start()."""
        result = subprocess.run(
            [sys.executable, SEED_SCRIPT, json.dumps({'devices': list(devices), 'users': list(users)})],
            cwd=SERVER_DIR, env=self.env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError('Error sembrant les dades:\n' + result.stderr[-2000:])

    def start(self):
        self.log = open(os.path.join(self.data_dir, 'server.log'), 'w')
        self.process = subprocess.Popen(
            [sys.executable, 'run.py'], cwd=SERVER_DIR, env=self.env,
            stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + SERVER_START_TIMEOUT_S
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('El servidor s\'ha aturat en arrencar. Log:\n' + self.read_log())
            try:
                urllib.request.urlopen(BASE_URL + '/', timeout=1)
                return
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.3)
        raise RuntimeError('El servidor no ha respost a temps. Log:\n' + self.read_log())

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if getattr(self, 'log', None):
            self.log.close()
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def read_log(self):
        try:
            with open(os.path.join(self.data_dir, 'server.log')) as f:
                return f.read()[-3000:]
        except OSError:
            return ''

    @staticmethod
    def inject_observation(eui64, remote_url='', image_version='KapriOn_1.5.7'):
        """Envia una resposta de discovery com si vingués d'un dispositiu."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(json.dumps({
                'type': 'kapri_discovery',
                'sEUI64': eui64,
                'sImageVersion': image_version,
                'sRemoteUrl': remote_url,
            }).encode('ascii'), ('127.0.0.1', DISCOVERY_PORT))
        finally:
            sock.close()

    @staticmethod
    def api(path):
        with urllib.request.urlopen(BASE_URL + path, timeout=5) as r:
            return json.loads(r.read().decode())


class E2ETestCase(unittest.TestCase):
    """
    Base de les proves e2e. Cada subclasse defineix el seu escenari a SEED i
    OBSERVATIONS, i té el seu propi servidor i navegador.

    Les pauses s'han de fer amb page.wait_for_timeout() i mai amb time.sleep():
    amb l'API síncrona de Playwright, time.sleep() bloqueja el despatx
    d'esdeveniments, i les peticions o missatges de consola que passen durant
    la pausa no es registren. Ens va fer creure que el polling estava trencat.
    """

    SEED = []
    OBSERVATIONS = []        # [(eui64, remote_url), ...]
    USERS = [TEST_USER]
    # Si és cert, cada prova comença amb la sessió de TEST_USER ja iniciada.
    LOGIN = True
    VIEWPORT = {'width': 1300, 'height': 700}
    # Idioma del navegador. La interfície el fa servir si no se n'ha triat cap
    # amb el selector. Cada prova obre un context nou, sense idioma desat.
    LOCALE = 'en-US'

    @classmethod
    def setUpClass(cls):
        check_build()
        from playwright.sync_api import sync_playwright
        cls.server = ServerUnderTest()
        cls.server.seed(cls.SEED, cls.USERS)
        cls.server.start()
        cls.inject_observations()
        cls._pw = sync_playwright().start()
        cls.browser = cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
            cls._pw.stop()
        finally:
            cls.server.stop()

    @classmethod
    def inject_observations(cls):
        for eui64, url in cls.OBSERVATIONS:
            cls.server.inject_observation(eui64, url)
        time.sleep(0.5)   # fora del navegador: aquí sí que és correcte

    def setUp(self):
        self.page = self.browser.new_page(viewport=self.VIEWPORT, locale=self.LOCALE)
        if self.LOGIN:
            self.login_via_api(TEST_USER['username'], TEST_USER['password'])

    def tearDown(self):
        # En cas d'error, desa una captura per poder veure què hi havia.
        outcome = getattr(self, '_outcome', None)
        failed = False
        if outcome is not None and getattr(outcome, 'result', None) is not None:
            result = outcome.result
            failed = any(t is self for t, _ in result.failures + result.errors)
        if failed:
            os.makedirs(ARTIFACTS_DIR, exist_ok=True)
            self.page.screenshot(path=os.path.join(ARTIFACTS_DIR, f'{self.id()}.png'))
        self.page.close()

    # --- utilitats -----------------------------------------------------
    def login_via_api(self, username, password):
        """
        Inicia sessió sense passar per la pantalla. page.request comparteix les
        cookies amb el navegador, de manera que la pàgina ja hi entra amb sessió.
        """
        r = self.page.request.post(BASE_URL + '/api/auth/login', headers=CSRF_HEADERS,
                                   data={'username': username, 'password': password})
        assert r.ok, f'Login de proves fallit: {r.status} {r.text()}'

    def open_terminals(self):
        """Obre la pantalla i espera que acabi la càrrega inicial."""
        self.page.goto(BASE_URL + '/')
        self.page.wait_for_selector('table.grid', timeout=10000)
        self.page.wait_for_timeout(300)

    def open_avatar_menu(self):
        """Obre el desplegable de l'avatar (Bootstrap) i espera que es vegi."""
        self.page.click('kora-navbar button.avatar')
        self.page.wait_for_selector('kora-navbar .dropdown-menu.show', timeout=3000)

    def row(self, eui64):
        """
        La fila d'un dispositiu, buscada per EUI64 cada vegada: mai per posició,
        perquè l'ordre de la taula pot canviar.
        """
        return self.page.locator('tbody tr', has=self.page.locator('td.mono', has_text=eui64))

    def desc_cell(self, eui64):
        return self.row(eui64).locator('td.col-desc')
