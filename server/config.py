# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Configuració de KoraAccess."""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# A Windows, en producció, la base de dades ha de viure a ProgramData,
# mai dins de Program Files, on el compte del servei pot no tenir escriptura.
DEFAULT_DATA_DIR = os.environ.get('KORAACCESS_DATA_DIR', BASE_DIR)


class BaseConfig:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(DEFAULT_DATA_DIR, 'koraaccess.sqlite')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Servidor ---
    LISTEN_HOST = '0.0.0.0'
    LISTEN_PORT = 8443
    SERVER_THREADS = 8
    # Certificat públic real emès per al domini del servei. El DNS de la
    # instal·lació resol aquest domini cap a la IP privada del servidor.
    TLS_CERT_FILE = os.environ.get('KORAACCESS_TLS_CERT', '')
    TLS_KEY_FILE = os.environ.get('KORAACCESS_TLS_KEY', '')

    # URL que es configura als terminals en vincular-los.
    # Ha de portar el DOMINI, mai la IP: amb una IP el certificat no validaria.
    SERVER_PUBLIC_URL = os.environ.get('KORAACCESS_PUBLIC_URL', 'https://kora.exemple.com')

    # --- Discovery UDP ---
    DISCOVERY_PORT = 60100
    DISCOVERY_TOKEN = b'KAPRI_DISCOVERY'
    DISCOVERY_PERIOD = 30          # s; només mentre la pantalla és oberta
    DISCOVERY_RESULT_TTL = 90      # s; antiguitat màxima d'una observació

    # --- Keep-alive i estat de connexió (valors de KapriCloudMainAPI) ---
    DEVICES_KEEP_ALIVE_TMO = 10
    DEVICES_LOST_TMO = 150
    DEVICES_SEVERE_LOST_TMO = 300

    # --- Llicència ---
    # Provisional: fins que s'integri el mòdul compartit amb KoraPresence.
    LICENSE_MAX_ASSIGNED_DEVICES = 20


class DevConfig(BaseConfig):
    DEBUG = True
    LISTEN_PORT = 8080
    TLS_CERT_FILE = ''   # en desenvolupament, HTTP pla


CONFIG_BY_NAME = {'dev': DevConfig, 'prod': BaseConfig}
