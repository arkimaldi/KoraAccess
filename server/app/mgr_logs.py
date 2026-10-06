# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Registre d'esdeveniments per dispositiu."""

import logging

from app.extensions import db
from app.db_models import DeviceLogs


class MgrLogs:

    @staticmethod
    def add(event, detail='', device=None, eui64=None, commit=True):
        try:
            row = DeviceLogs(
                device_id=device.device_id if device is not None else None,
                eui64=eui64 if eui64 is not None else (device.eui64 if device is not None else None),
                event=event,
                detail=detail or ''
            )
            db.session.add(row)
            if commit:
                db.session.commit()
        except Exception as e:
            logging.error('MgrLogs.add exception: %s', e)
            db.session.rollback()
