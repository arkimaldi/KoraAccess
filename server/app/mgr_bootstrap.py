# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Primer administrador i protecció de la carpeta de dades.

En la primera arrencada del servei, si no existeix cap usuari, es crea «admin»
amb una contrasenya aleatòria pròpia d'aquella instal·lació, temporal, i es desa
a <carpeta de dades>/secrets/initial-admin-password.txt. L'instal·lador la pot
llegir i mostrar; en el primer login s'ha de canviar, i llavors el fitxer
s'esborra.

No hi ha cap contrasenya fixa al codi: seria la mateixa a totes les
instal·lacions, la coneixeria tothom qui ha tocat el producte i moltes no es
canviarien mai. A més, el Cyber Resilience Act exigeix configuracions segures
per defecte. Per conèixer la contrasenya inicial cal accés al servidor, que és
la mateixa font de confiança que les ordres de manage.py.

Permisos. A Windows, les subcarpetes de ProgramData les poden llegir tots els
usuaris locals: cal treure l'herència i deixar-hi només SYSTEM, els
administradors i el compte amb què corre el servei. S'hi fan servir els SID i no
els noms dels grups, perquè els noms canvien segons l'idioma del Windows
(«Administradores» en castellà).
"""

import logging
import os
import subprocess

from flask import current_app

from app import mgr_auth
from app.db_models import Users

INITIAL_ADMIN_USERNAME = 'admin'
SECRETS_DIRNAME = 'secrets'
INITIAL_PASSWORD_FILENAME = 'initial-admin-password.txt'

SID_SYSTEM = 'S-1-5-18'
SID_ADMINISTRATORS = 'S-1-5-32-544'


# ----------------------------------------------------------------------
# Rutes
# ----------------------------------------------------------------------
def secrets_dir():
    return os.path.join(current_app.config['DATA_DIR'], SECRETS_DIRNAME)


def initial_password_path():
    return os.path.join(secrets_dir(), INITIAL_PASSWORD_FILENAME)


# ----------------------------------------------------------------------
# Permisos
# ----------------------------------------------------------------------
def _current_user_sid():
    """SID del compte que executa el procés, per no perdre'n l'accés."""
    out = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                         capture_output=True, text=True, check=True).stdout
    # "domini\\usuari","S-1-5-21-..."
    return out.strip().split(',')[-1].strip().strip('"')


def restrict_directory(path):
    """
    Deixa una carpeta accessible només per als administradors i el compte del
    servei. Retorna True si ho ha aconseguit.

    A Windows treu l'herència i hi dona control total a SYSTEM, als
    administradors i al compte actual, amb herència cap als fitxers i
    subcarpetes. Als altres sistemes, permisos 700.
    """
    os.makedirs(path, exist_ok=True)
    try:
        if os.name == 'nt':
            sids = {SID_SYSTEM, SID_ADMINISTRATORS, _current_user_sid()}
            grants = []
            for sid in sorted(sids):
                grants += ['/grant:r', f'*{sid}:(OI)(CI)F']
            subprocess.run(['icacls', path, '/inheritance:r', *grants],
                           capture_output=True, text=True, check=True)
        else:
            os.chmod(path, 0o700)
        return True
    except Exception as e:
        logging.error('No s\'han pogut restringir els permisos de %s: %s', path, e)
        return False


def secure_data_dir():
    """
    Protegeix la carpeta de dades sencera, si la configuració ho demana. Es fa
    a cada arrencada: si algú l'esborra i el servidor la torna a crear, queda
    protegida igualment.
    """
    if current_app.config.get('SECURE_DATA_DIR'):
        restrict_directory(current_app.config['DATA_DIR'])


# ----------------------------------------------------------------------
# Primer administrador
# ----------------------------------------------------------------------
def _write_secret(path, content):
    """Escriu el fitxer amb permisos 600 des del primer moment, no després."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(content + '\n')


def ensure_initial_admin():
    """
    Si no hi ha cap usuari, crea l'administrador inicial i desa la contrasenya.
    Retorna la ruta del fitxer, o None si no ha calgut fer res.

    Si no es poden protegir els permisos de la carpeta, no es crea res: més val
    haver de crear l'administrador amb manage.py que deixar la contrasenya
    llegible per qualsevol usuari del servidor.
    """
    if mgr_auth.live_users().count() > 0:
        return None

    path = initial_password_path()
    if not restrict_directory(secrets_dir()):
        logging.error(
            'No s\'ha creat l\'administrador inicial perquè no s\'han pogut protegir '
            'els permisos de %s. Creeu-lo amb: manage.py users create-admin', secrets_dir())
        return None

    password = mgr_auth.generate_temporary_password()
    mgr_auth.create_user(INITIAL_ADMIN_USERNAME, password, 'admin', must_change_password=True)
    _write_secret(path, password)

    # La contrasenya no s'escriu mai al log: només on és.
    logging.warning(
        'Creat l\'administrador inicial «%s». La contrasenya temporal és a %s. '
        'S\'haurà de canviar en el primer inici de sessió.', INITIAL_ADMIN_USERNAME, path)
    return path


def remove_initial_password_file(user):
    """
    Esborra el fitxer quan la contrasenya inicial deixa de ser vàlida: en
    canviar-la o en restablir-la.
    """
    if user.username != INITIAL_ADMIN_USERNAME:
        return
    try:
        path = initial_password_path()
        if os.path.exists(path):
            os.remove(path)
            logging.info('Esborrat el fitxer de la contrasenya inicial: %s', path)
    except Exception as e:
        logging.error('No s\'ha pogut esborrar el fitxer de la contrasenya inicial: %s', e)
