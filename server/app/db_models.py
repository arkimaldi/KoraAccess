# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Model de dades de KoraAccess."""

import uuid
from datetime import datetime, timezone

from app.extensions import db
from app.global_consts import DeviceStatus, LinkState


def _uuid4():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Devices(db.Model):
    """
    Dispositius que gestiona el programa: enrolats, pendents d'enrolar
    i pendents d'esborrar.
    """
    __tablename__ = 'devices'

    device_id = db.Column(db.String(36), primary_key=True, default=_uuid4)

    # Identificador del dispositiu Kimaldi: 16 caràcters hexadecimals en
    # majúscules, sense separadors (p.ex. 001824FFFD000094).
    # Es desa i es compara literalment, sense normalitzar.
    eui64 = db.Column(db.String(16), unique=True, nullable=False, index=True)

    status = db.Column(db.String(20), nullable=False, default=DeviceStatus.ENROLL_PENDING)
    description = db.Column(db.String(120), nullable=False, default='')

    # Generats pel servidor en crear el registre. L'escriu al dispositiu la
    # seqüència d'enrolament, que ja circula per HTTPS: el token no viatja
    # mai per UDP.
    cloud_remote_server_token = db.Column(db.String(36), nullable=False, default=_uuid4)
    web_admin_password = db.Column(db.String(64), nullable=False, default='')
    web_securized = db.Column(db.Boolean, nullable=False, default=False)

    # Reportats pel dispositiu durant l'enrolament
    knet_id = db.Column(db.Integer, nullable=True)
    image_version = db.Column(db.String(64), nullable=True)
    mac_address = db.Column(db.String(32), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    link = db.Column(db.String(20), nullable=False, default=LinkState.OFFLINE)
    link_kick_dts = db.Column(db.DateTime, nullable=True)

    # Moment en què es va ordenar l'alliberament
    delete_requested_dts = db.Column(db.DateTime, nullable=True)

    datetimestamp = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    portal_device = db.relationship('PortalDevices', backref='device',
                                    uselist=False, cascade='all, delete-orphan')
    logs = db.relationship('DeviceLogs', backref='device',
                           cascade='all, delete-orphan', passive_deletes=True)

    @property
    def is_assigned(self):
        return self.portal_device is not None


class PortalDevices(db.Model):
    """Vincula un terminal amb una porta. Un terminal per porta."""
    __tablename__ = 'portal_devices'

    portal_device_id = db.Column(db.String(36), primary_key=True, default=_uuid4)
    device_id = db.Column(db.String(36), db.ForeignKey('devices.device_id', ondelete='CASCADE'),
                          unique=True, nullable=False)
    # El mòdul de Portes encara no està especificat: de moment només el nom.
    portal_name = db.Column(db.String(120), nullable=False, default='')
    datetimestamp = db.Column(db.DateTime, nullable=False, default=utcnow)


class DeviceLogs(db.Model):
    """
    Històric d'esdeveniments per dispositiu: enrolament, errors, rebuigs,
    pèrdues de connexió. Substitueix qualsevol camp d'últim error.
    """
    __tablename__ = 'device_logs'

    device_log_id = db.Column(db.String(36), primary_key=True, default=_uuid4)
    device_id = db.Column(db.String(36), db.ForeignKey('devices.device_id', ondelete='CASCADE'),
                          nullable=True, index=True)
    eui64 = db.Column(db.String(16), nullable=True, index=True)
    event = db.Column(db.String(60), nullable=False)
    detail = db.Column(db.Text, nullable=False, default='')
    datetimestamp = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
