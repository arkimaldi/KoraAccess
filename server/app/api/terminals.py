# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
API REST de la pantalla de Terminals.

Les etiquetes són una funció de presentació calculada a partir del registre a
Devices, la presència a PortalDevices i la darrera observació de discovery.
No són una màquina d'estats.
"""

import logging
from datetime import timezone

from flask import Blueprint, jsonify, request, current_app

from app.db_models import Devices
from app.global_consts import DeviceStatus
from app.mgr_devices import MgrDevices

terminals_bp = Blueprint('terminals', __name__)


def _discovery():
    return current_app.extensions['kora_discovery']


def _server_url():
    return current_app.config['SERVER_PUBLIC_URL']


# ----------------------------------------------------------------------
# Etiquetes i diagnòstics
# ----------------------------------------------------------------------
def _label_for_device(device, obs, server_url):
    if device.status == DeviceStatus.DELETE_PENDING:
        return 'DELETE_PENDING'
    if device.status == DeviceStatus.ENROLL_PENDING:
        return 'LINKED'
    return 'ASSIGNED' if device.is_assigned else 'ENROLLED'


def _is_stale(device, obs):
    """
    Una observació és obsoleta si és anterior a l'últim canvi que coneixem
    del dispositiu: la darrera vinculació o, sobretot, l'últim contacte seu.

    Si el dispositiu ens ha trucat amb un token vàlid després d'una
    observació, aquella observació ja no descriu el present: sabem del cert
    que té la nostra URL configurada. Comparar només amb linked_dts no basta,
    perquè entre la vinculació i el primer contacte poden passar minuts (per
    exemple si la URL es configura a mà) i els scans d'aquest interval encara
    veuen el dispositiu verge.
    """
    if obs is None:
        return False
    marks = [d for d in (device.linked_dts, device.link_kick_dts) if d is not None]
    if not marks:
        return False
    newest = max(d.replace(tzinfo=timezone.utc).timestamp() for d in marks)
    return obs.seen_dts < newest


def _warnings_for_device(device, obs, server_url):
    """
    Contradiccions entre el que creu el programa i el que informa el
    dispositiu. Només es poden detectar quan el discovery hi arriba i quan
    l'observació és posterior a la darrera vinculació.
    """
    warnings = []
    if _is_stale(device, obs):
        return warnings
    if device.status == DeviceStatus.ENROLLED and obs is not None:
        if obs.is_virgin():
            warnings.append('El dispositiu s\'ha resetejat per fora: cal esborrar-ne el registre.')
        elif not obs.belongs_to(server_url):
            warnings.append('El dispositiu apunta ara a un altre servidor: cal un reset físic.')

    # Vinculat correctament però que no arriba mai a enrolar-se
    if (device.status == DeviceStatus.ENROLL_PENDING
            and device.link_kick_dts is None
            and obs is not None and obs.belongs_to(server_url)):
        warnings.append('El dispositiu apunta al servidor però no hi arriba: '
                        'comproveu que resol el domini pel DNS de la instal·lació.')
    return warnings


def _device_to_dict(device, obs, server_url):
    return {
        'device_id': device.device_id,
        'eui64': device.eui64,
        'description': device.description,
        'status': device.status,
        'label': _label_for_device(device, obs, server_url),
        'link': device.link,
        'link_kick_dts': device.link_kick_dts.isoformat() if device.link_kick_dts else None,
        'knet_id': device.knet_id,
        'image_version': device.image_version,
        'ip_address': obs.ip_address if (obs and not _is_stale(device, obs)) else device.ip_address,
        'web_securized': device.web_securized,
        'portal_name': device.portal_device.portal_name if device.is_assigned else None,
        'is_assigned': device.is_assigned,
        'seen_in_discovery': obs is not None and not _is_stale(device, obs),
        'warnings': _warnings_for_device(device, obs, server_url),
        'can_assign': (device.status == DeviceStatus.ENROLLED
                       and not device.is_assigned
                       and MgrDevices.license_available()),
        'can_release': device.status == DeviceStatus.ENROLLED and not device.is_assigned,
        'can_delete': MgrDevices.can_delete_manually(device)[0],
    }


# ----------------------------------------------------------------------
# Llistat
# ----------------------------------------------------------------------
@terminals_bp.route('/api/terminals', methods=['GET'])
def list_terminals():
    try:
        server_url = _server_url()
        discovery = _discovery()
        observations = {o.eui64: o for o in discovery.get_observations()}

        rows = []
        known = set()
        for device in Devices.query.order_by(Devices.datetimestamp.desc()).all():
            known.add(device.eui64)
            rows.append(_device_to_dict(device, observations.get(device.eui64), server_url))

        # Dispositius vistos pel discovery que no tenen registre:
        # verges (FREE) o vinculats a un altre servidor (FOREIGN).
        for eui64, obs in observations.items():
            if eui64 in known:
                continue
            rows.append({
                'device_id': None,
                'eui64': eui64,
                'description': '',
                'status': None,
                'label': 'FREE' if obs.is_virgin() else (
                    'LINKED' if obs.belongs_to(server_url) else 'FOREIGN'),
                'link': None,
                'link_kick_dts': None,
                'knet_id': None,
                'image_version': obs.image_version,
                'ip_address': obs.ip_address,
                'web_securized': None,
                'portal_name': None,
                'is_assigned': False,
                'seen_in_discovery': True,
                'warnings': ([] if obs.is_virgin() or not obs.belongs_to(server_url) else
                             ['El dispositiu apunta a aquest servidor però no hi consta: '
                              'cal un reset físic per recuperar-lo.']),
                'can_assign': False,
                'can_release': False,
                'can_delete': False,
                'can_link': obs.is_virgin(),
            })

        return jsonify({
            'terminals': rows,
            'license': {
                'assigned': MgrDevices.count_assigned(),
                'limit': MgrDevices.license_limit(),
            },
            'server_url': server_url,
        })
    except Exception as e:
        logging.error('list_terminals exception: %s', e)
        return jsonify({'error': str(e)}), 500


@terminals_bp.route('/api/discovery/scan', methods=['POST'])
def discovery_scan():
    sent = _discovery().send_discovery()
    return jsonify({'sent_to': sent})


# ----------------------------------------------------------------------
# Accions
# ----------------------------------------------------------------------
@terminals_bp.route('/api/terminals/link', methods=['POST'])
def link_terminal():
    """Vincula un dispositiu verge: crea el registre i li envia la URL per UDP."""
    body = request.get_json(force=True, silent=True) or {}
    eui64 = body.get('eui64')
    description = body.get('description', '')

    obs = _discovery().get_observation(eui64) if eui64 else None
    if obs is None:
        return jsonify({'error': 'El dispositiu no apareix al discovery.'}), 400
    if not obs.is_virgin():
        return jsonify({'error': 'El dispositiu ja està vinculat a un servidor.'}), 400

    device, err = MgrDevices.create_pending(eui64, description)
    if device is None:
        return jsonify({'error': err}), 400

    # L'observació que tenim és d'abans de configurar el dispositiu: queda
    # obsoleta en el mateix moment de vincular-lo.
    _discovery().invalidate(eui64)

    ok, err = _discovery().send_link(obs.ip_address, _server_url())
    if not ok:
        return jsonify({'error': f'Registre creat, però la vinculació UDP ha fallat: {err}'}), 502
    return jsonify({'device_id': device.device_id, 'eui64': device.eui64})


@terminals_bp.route('/api/terminals/<device_id>/assign', methods=['POST'])
def assign_terminal(device_id):
    body = request.get_json(force=True, silent=True) or {}
    device = MgrDevices.get_by_id(device_id)
    if device is None:
        return jsonify({'error': 'Dispositiu desconegut.'}), 404
    ok, err = MgrDevices.assign_to_portal(device, body.get('portal_name', ''))
    return (jsonify({'ok': True}) if ok else (jsonify({'error': err}), 400))


@terminals_bp.route('/api/terminals/<device_id>/unassign', methods=['POST'])
def unassign_terminal(device_id):
    device = MgrDevices.get_by_id(device_id)
    if device is None:
        return jsonify({'error': 'Dispositiu desconegut.'}), 404
    ok, err = MgrDevices.unassign(device)
    return (jsonify({'ok': True}) if ok else (jsonify({'error': err}), 400))


@terminals_bp.route('/api/terminals/<device_id>/release', methods=['POST'])
def release_terminal(device_id):
    """Ordena l'alliberament: el registre passa a delete_pending."""
    device = MgrDevices.get_by_id(device_id)
    if device is None:
        return jsonify({'error': 'Dispositiu desconegut.'}), 404
    ok, err = MgrDevices.request_delete(device)
    return (jsonify({'ok': True}) if ok else (jsonify({'error': err}), 400))


@terminals_bp.route('/api/terminals/<device_id>', methods=['DELETE'])
def delete_terminal(device_id):
    """Esborrat manual del registre, sense instrucció al dispositiu."""
    device = MgrDevices.get_by_id(device_id)
    if device is None:
        return jsonify({'error': 'Dispositiu desconegut.'}), 404
    ok, err = MgrDevices.can_delete_manually(device)
    if not ok:
        return jsonify({'error': err}), 400
    MgrDevices.delete(device, reason='esborrat manual')
    return jsonify({'ok': True})
