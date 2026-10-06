# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Estat de connexió dels dispositius (Devices.link).

Independent del cicle de vida. Els temps són els de KapriCloudMainAPI:
keep-alive cada 10 s, pas a lost als 150 s, pas a severe_lost als 300 s.
"""

import logging

from flask import current_app

from app.extensions import db
from app.db_models import Devices, utcnow
from app.global_consts import DeviceStatus, LinkState
from app.mgr_logs import MgrLogs


class MgrLink:

    @staticmethod
    def on_device_call(device):
        """
        Qualsevol crida d'un dispositiu el torna a online.
        La recuperació només es registra si venia de severe_lost, per no
        generar sorolls amb talls breus.
        """
        was = device.link
        device.link = LinkState.ONLINE
        device.link_kick_dts = utcnow()
        if was == LinkState.SEVERE_LOST:
            MgrLogs.add('link_recovered', f'des de {was}', device=device, commit=False)

    @staticmethod
    def refresh_all():
        """
        Recalcula l'estat de connexió segons el temps transcorregut des del
        darrer keep-alive. Pensat per ser cridat periòdicament.
        """
        try:
            lost_tmo = current_app.config['DEVICES_LOST_TMO']
            severe_tmo = current_app.config['DEVICES_SEVERE_LOST_TMO']
            now = utcnow()
            changed = 0

            for device in Devices.query.all():
                if device.status == DeviceStatus.ENROLL_PENDING and device.link_kick_dts is None:
                    continue  # acabat de vincular, encara no ha trucat mai

                if device.link_kick_dts is None:
                    continue

                elapsed = (now - device.link_kick_dts).total_seconds()
                if elapsed >= severe_tmo:
                    new_link = LinkState.SEVERE_LOST
                elif elapsed >= lost_tmo:
                    new_link = LinkState.LOST
                else:
                    new_link = LinkState.ONLINE

                if new_link != device.link:
                    MgrLogs.add('link_changed', f'{device.link} -> {new_link}',
                                device=device, commit=False)
                    device.link = new_link
                    changed += 1

            if changed:
                db.session.commit()
            return changed
        except Exception as e:
            logging.error('MgrLink.refresh_all exception: %s', e)
            db.session.rollback()
            return 0
