# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Sembra un escenari a la base de dades de proves.

S'executa com a subprocés, i no importat, perquè config.py llegeix
KORAACCESS_DATA_DIR en el moment d'importar-se: si el procés de proves ja
l'hagués importat, apuntaria a la base de dades equivocada.

Ús: python seed.py '<json amb la llista de dispositius>'
Cada dispositiu: {"eui64": ..., "description": ..., "status": ...}
"""

import json
import os
import sys

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'server'))
sys.path.insert(0, SERVER_DIR)
os.chdir(SERVER_DIR)

from app import create_app                       # noqa: E402
from app.extensions import db                    # noqa: E402
from app.mgr_devices import MgrDevices           # noqa: E402
from app.global_consts import DeviceStatus, LinkState   # noqa: E402
from app.db_models import utcnow                 # noqa: E402


def main():
    devices = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    app = create_app('dev', start_background=False)
    with app.app_context():
        for d in devices:
            device, err = MgrDevices.create_pending(d['eui64'], d.get('description', ''))
            if device is None:
                raise SystemExit(f"No s'ha pogut crear {d['eui64']}: {err}")
            device.status = d.get('status', DeviceStatus.ENROLLED)
            if device.status == DeviceStatus.ENROLLED:
                device.link = LinkState.ONLINE
                device.link_kick_dts = utcnow()
        db.session.commit()


if __name__ == '__main__':
    main()
