# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Configuració de KoraAccess."""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# A Windows, en producció, la base de dades ha de viure a ProgramData,
# mai dins de Program Files, on el compte del servei pot no tenir escriptura.
DEFAULT_DATA_DIR = os.environ.get('KORAACCESS_DATA_DIR', BASE_DIR)


class BaseConfig:
    DATA_DIR = DEFAULT_DATA_DIR
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(DEFAULT_DATA_DIR, 'koraaccess.sqlite')

    # Restringir els permisos de tota la carpeta de dades als administradors i
    # al compte del servei. Conté la base de dades, amb els hashes de les
    # contrasenyes i de les sessions, i la contrasenya inicial de l'administrador.
    # La subcarpeta secrets/ es restringeix sempre, també en desenvolupament.
    SECURE_DATA_DIR = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Servidor ---
    LISTEN_HOST = '0.0.0.0'
    LISTEN_PORT = int(os.environ.get('KORAACCESS_PORT', 8443))
    SERVER_THREADS = 8
    # Certificat públic real emès per al domini del servei. El DNS de la
    # instal·lació resol aquest domini cap a la IP privada del servidor.
    TLS_CERT_FILE = os.environ.get('KORAACCESS_TLS_CERT', '')
    TLS_KEY_FILE = os.environ.get('KORAACCESS_TLS_KEY', '')

    # URL que es configura als terminals en vincular-los i a la qual faran el
    # POST. És l'endpoint sencer, amb el camí, no només el host.
    #
    # En producció ha de portar el DOMINI, mai la IP: el certificat és un
    # certificat públic real emès per a aquest domini i amb una IP no
    # validaria. El DNS de la instal·lació el resol cap a la IP privada.
    SERVER_PUBLIC_URL = os.environ.get('KORAACCESS_PUBLIC_URL',
                                       'https://kora.exemple.com/v1/Cloud/Event')

    # --- Discovery UDP ---
    DISCOVERY_PORT = int(os.environ.get('KORAACCESS_DISCOVERY_PORT', 60100))
    DISCOVERY_TOKEN = b'KAPRI_DISCOVERY'
    DISCOVERY_PERIOD = 30          # s; només mentre la pantalla és oberta
    DISCOVERY_RESULT_TTL = 90      # s; antiguitat màxima d'una observació
    # Retard de l'scan que s'emet just després d'esborrar un registre. Dona
    # temps al dispositiu a aplicar el segon lot d'alliberament, que és el que
    # li buida la URL; si s'emetés a l'instant, encara respondria amb la URL
    # posada i es mostraria com a vinculat.
    DISCOVERY_RESCAN_DELAY = 3

    # --- Keep-alive i estat de connexió (valors de KapriCloudMainAPI) ---
    DEVICES_KEEP_ALIVE_TMO = 10
    DEVICES_LOST_TMO = 150
    DEVICES_SEVERE_LOST_TMO = 300

    # --- Autenticació ---
    AUTH_COOKIE_NAME = 'koraaccess_session'
    # Secure: el navegador només envia la cookie per HTTPS. En desenvolupament,
    # que va en HTTP pla, s'ha de desactivar o no s'enviaria mai.
    AUTH_COOKIE_SECURE = True
    # Sessions semi-permanents: caduquen per inactivitat i, en tot cas, passat un
    # temps màxim des del login.
    AUTH_IDLE_TIMEOUT_S = int(os.environ.get('KORAACCESS_AUTH_IDLE_TIMEOUT_S', 8 * 3600))
    AUTH_ABSOLUTE_TIMEOUT_S = int(os.environ.get('KORAACCESS_AUTH_ABSOLUTE_TIMEOUT_S', 30 * 24 * 3600))
    # La darrera activitat no s'escriu a cada petició, sinó com a molt amb
    # aquesta freqüència: la pantalla fa polling cada pocs segons.
    AUTH_LAST_SEEN_UPDATE_S = 60
    # Límit d'intents de login per IP. Sense bloqueig de comptes: permetria
    # bloquejar el compte d'un altre a propòsit.
    AUTH_LOGIN_RATE_LIMIT = os.environ.get('KORAACCESS_LOGIN_RATE_LIMIT', '5 per minute')
    PASSWORD_MIN_LENGTH = 10
    PASSWORD_MAX_LENGTH = 128

    # --- Llicència ---
    # Provisional: fins que s'integri el mòdul compartit amb KoraPresence.
    LICENSE_MAX_ASSIGNED_DEVICES = 20


class DevConfig(BaseConfig):
    DEBUG = True
    LISTEN_PORT = int(os.environ.get('KORAACCESS_PORT', 8080))
    TLS_CERT_FILE = ''   # en desenvolupament, HTTP pla
    AUTH_COOKIE_SECURE = False
    # En desenvolupament la carpeta de dades pot ser la del codi font: no se'n
    # canvien els permisos, o el desenvolupador podria perdre-hi l'accés.
    SECURE_DATA_DIR = False

    # En desenvolupament s'hi va per IP i HTTP pla: no hi ha certificat a
    # validar ni DNS que resolgui el domini. Ha de coincidir exactament amb el
    # que té configurat el terminal, o el discovery el classificaria com a
    # FOREIGN en lloc de LINKED.
    SERVER_PUBLIC_URL = os.environ.get('KORAACCESS_PUBLIC_URL',
                                       'http://10.0.0.144:8080/v1/Cloud/Event')


CONFIG_BY_NAME = {'dev': DevConfig, 'prod': BaseConfig}
