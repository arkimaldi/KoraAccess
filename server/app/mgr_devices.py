# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Cicle de vida dels dispositius.

enroll_pending -> enrolled -> delete_pending -> (esborrat)

Un keep-alive d'un EUI64 que no consta a Devices es rebutja sempre: el
programa només atén dispositius que ell mateix ha vinculat.
"""

import logging
import secrets
import uuid

from flask import current_app

from app.extensions import db
from app.db_models import Devices, PortalDevices, utcnow
from app.global_consts import DeviceStatus, LinkState
from app.mgr_logs import MgrLogs


class MgrDevices:

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------
    @staticmethod
    def get_by_eui64(eui64):
        if not eui64:
            return None
        return Devices.query.filter_by(eui64=eui64).first()

    @staticmethod
    def get_by_id(device_id):
        return Devices.query.filter_by(device_id=device_id).first()

    @staticmethod
    def count_assigned():
        return PortalDevices.query.count()

    @staticmethod
    def license_limit():
        return current_app.config['LICENSE_MAX_ASSIGNED_DEVICES']

    @staticmethod
    def license_available():
        """
        El límit es comptabilitza sobre terminals assignats, no sobre
        enrolats: un terminal enrolat sense ús no ocupa plaça.
        """
        return MgrDevices.count_assigned() < MgrDevices.license_limit()

    # ------------------------------------------------------------------
    # Vinculació
    # ------------------------------------------------------------------
    @staticmethod
    def create_pending(eui64, description=''):
        """
        Crea el registre en vincular. Si ja existia un enroll_pending del
        mateix EUI64, se sobreescriu amb un token nou.

        Retorna (device, error).
        """
        try:
            existing = MgrDevices.get_by_eui64(eui64)
            if existing is not None:
                if existing.status != DeviceStatus.ENROLL_PENDING:
                    return None, f'El dispositiu {eui64} ja consta com a {existing.status}.'
                existing.cloud_remote_server_token = str(uuid.uuid4())
                existing.web_admin_password = secrets.token_urlsafe(16)
                existing.link = LinkState.OFFLINE
                existing.link_kick_dts = None
                existing.linked_dts = utcnow()
                if description:
                    existing.description = description
                MgrLogs.add('relink', 'token regenerat', device=existing, commit=False)
                db.session.commit()
                return existing, None

            device = Devices(
                eui64=eui64,
                status=DeviceStatus.ENROLL_PENDING,
                description=description or '',
                cloud_remote_server_token=str(uuid.uuid4()),
                web_admin_password=secrets.token_urlsafe(16),
                link=LinkState.OFFLINE,
                linked_dts=utcnow()
            )
            db.session.add(device)
            MgrLogs.add('link', 'registre creat en vincular', device=device, commit=False)
            db.session.commit()
            return device, None
        except Exception as e:
            logging.error('create_pending exception: %s', e)
            db.session.rollback()
            return None, str(e)

    # ------------------------------------------------------------------
    # Validació del token
    # ------------------------------------------------------------------
    @staticmethod
    def token_accepted(device, token):
        """
        Mentre el registre és enroll_pending s'accepta el token buit, perquè
        el dispositiu encara no en té. Un cop enrolled, només el token propi.
        """
        token = token or ''
        if device.status == DeviceStatus.ENROLL_PENDING:
            return token in ('', device.cloud_remote_server_token)
        return token == device.cloud_remote_server_token

    # ------------------------------------------------------------------
    # Enrolament
    # ------------------------------------------------------------------
    @staticmethod
    def enroll(device, info_arg):
        """Completa el registre amb la informació reportada pel dispositiu."""
        try:
            device.knet_id = info_arg.get('ucModelNo')
            device.image_version = info_arg.get('sImageVersion')
            device.mac_address = info_arg.get('sMAC_Address')
            device.status = DeviceStatus.ENROLLED
            MgrLogs.add('enrolled', f"model={device.knet_id} fw={device.image_version}",
                        device=device, commit=False)
            db.session.commit()
            return True
        except Exception as e:
            logging.error('enroll exception: %s', e)
            db.session.rollback()
            return False

    # ------------------------------------------------------------------
    # Alliberament
    # ------------------------------------------------------------------
    @staticmethod
    def request_delete(device):
        """
        Marca el registre com a delete_pending. Només permès sobre dispositius
        enrolats que no tinguin porta assignada.
        """
        try:
            if device.status != DeviceStatus.ENROLLED:
                return False, 'Només es pot alliberar un dispositiu enrolat.'
            if device.is_assigned:
                return False, 'Cal substituir primer el terminal de la porta.'
            device.status = DeviceStatus.DELETE_PENDING
            device.delete_requested_dts = utcnow()
            MgrLogs.add('delete_requested', '', device=device, commit=False)
            db.session.commit()
            return True, None
        except Exception as e:
            logging.error('request_delete exception: %s', e)
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def delete(device, reason=''):
        """Esborra el registre i les files dependents."""
        try:
            MgrLogs.add('deleted', reason, eui64=device.eui64, commit=False)
            db.session.delete(device)
            db.session.commit()
            return True
        except Exception as e:
            logging.error('delete exception: %s', e)
            db.session.rollback()
            return False

    @staticmethod
    def can_delete_manually(device):
        """
        L'esborrat manual d'un enroll_pending és sempre possible: no cal cap
        instrucció al dispositiu.

        El d'un delete_pending només quan el dispositiu està en severe_lost,
        perquè un terminal simplement desconnectat una estona ha de tenir
        ocasió de confirmar l'esborrat.
        """
        if device.status == DeviceStatus.ENROLL_PENDING:
            return True, None
        if device.status == DeviceStatus.DELETE_PENDING:
            if device.link == LinkState.SEVERE_LOST:
                return True, None
            return False, 'Només es pot esborrar manualment quan el dispositiu està en severe_lost.'
        return False, 'Un dispositiu enrolat s\'ha d\'alliberar, no esborrar.'

    # ------------------------------------------------------------------
    # Assignació a porta
    # ------------------------------------------------------------------
    @staticmethod
    def assign_to_portal(device, portal_name):
        try:
            if device.status != DeviceStatus.ENROLLED:
                return False, 'Només es pot assignar un dispositiu enrolat.'
            if device.is_assigned:
                return False, 'El dispositiu ja està assignat a una porta.'
            if not MgrDevices.license_available():
                return False, ('Límit de llicència assolit '
                               f'({MgrDevices.count_assigned()}/{MgrDevices.license_limit()}).')
            db.session.add(PortalDevices(device_id=device.device_id, portal_name=portal_name or ''))
            MgrLogs.add('assigned', portal_name or '', device=device, commit=False)
            db.session.commit()
            return True, None
        except Exception as e:
            logging.error('assign_to_portal exception: %s', e)
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def unassign(device):
        try:
            if not device.is_assigned:
                return False, 'El dispositiu no està assignat.'
            db.session.delete(device.portal_device)
            MgrLogs.add('unassigned', '', device=device, commit=False)
            db.session.commit()
            return True, None
        except Exception as e:
            logging.error('unassign exception: %s', e)
            db.session.rollback()
            return False, str(e)
