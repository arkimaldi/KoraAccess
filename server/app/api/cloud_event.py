# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Endpoint /v1/Cloud/Event: protocol CloudKimaldi.

Es manté idèntic al del cloud perquè el mateix firmware serveixi per als dos
productes sense cap canvi.

Flux:
  - El dispositiu envia on_cloud_keep_alive amb sEUI64 i sToken.
  - El servidor respon amb un ins_cloud_batch etiquetat amb msgId.name.
  - El dispositiu executa el lot i respon amb ans_cloud_batch i els ucRet.
"""

import logging

from flask import Blueprint, request, jsonify, current_app

from app.extensions import db
from app.global_consts import (DeviceStatus, MsgType, MsgId, UC_RET_OK,
                               WEB_DEFAULT_USER, WEB_DEFAULT_PASSWORD)
from app.mgr_devices import MgrDevices
from app.mgr_link import MgrLink
from app.mgr_logs import MgrLogs

cloud_event_bp = Blueprint('cloud_event', __name__)


def _empty_reply():
    """
    Res a fer.

    Es retorna null, igual que a KapriCloudMainAPI, que és el que el firmware
    espera quan el servidor no té instruccions. Inventar-se un msgType que el
    protocol no coneix fa que el dispositiu ho tracti com un error i reintenti
    immediatament, i es crea un bucle de crides.
    """
    return jsonify(None)


@cloud_event_bp.route('/v1/Cloud/Event', methods=['POST'])
def cloud_event():
    try:
        body = request.get_json(force=True, silent=True) or {}
        msg_type = body.get('msgType')
        msg_arg = body.get('msgArg') or {}
        eui64 = msg_arg.get('sEUI64')
        token = msg_arg.get('sToken', '')

        if not eui64:
            return _empty_reply()

        device = MgrDevices.get_by_eui64(eui64)

        # Una crida amb un EUI64 que no consta a Devices es rebutja: el
        # programa només atén dispositius que ell mateix ha vinculat.
        if device is None:
            MgrLogs.add('rejected_unknown_eui64', f'msgType={msg_type}', eui64=eui64)
            return _empty_reply()

        if not MgrDevices.token_accepted(device, token):
            MgrLogs.add('rejected_bad_token', f'msgType={msg_type}', device=device)
            return _empty_reply()

        # L'estat de connexió només es refresca amb el dispositiu enrolat,
        # com a KapriCloudMainAPI. Si es refresqués també en delete_pending, un
        # registre encallat no arribaria mai a severe_lost i la pantalla no
        # permetria esborrar-lo manualment.
        if device.status == DeviceStatus.ENROLLED:
            MgrLink.on_device_call(device)
        if request.remote_addr:
            device.ip_address = request.remote_addr
        db.session.commit()

        if msg_type == MsgType.ON_CLOUD_KEEP_ALIVE:
            return _on_keep_alive(device)
        if msg_type == MsgType.ANS_CLOUD_BATCH:
            return _on_ans_cloud_batch(device, msg_arg)

        return _empty_reply()
    except Exception as e:
        logging.error('cloud_event exception: %s', e)
        db.session.rollback()
        return _empty_reply()


# ----------------------------------------------------------------------
# Keep-alive: segons el status, es llança la seqüència corresponent
# ----------------------------------------------------------------------
def _on_keep_alive(device):
    if device.status == DeviceStatus.ENROLL_PENDING:
        return _enroll_device_launch(device)
    if device.status == DeviceStatus.DELETE_PENDING:
        return _delete_device_launch(device)
    return _empty_reply()   # enrolled: la sincronització és d'un altre mòdul


def _enroll_device_launch(device):
    """
    Lot d'enrolament: llegir informació, protegir el web, escriure el token i
    aplicar la configuració.
    """
    cfg = current_app.config
    batch = [
        {
            'msgType': MsgType.INS_CPU_GET_DEVICE_INFO,
            'msgArg': {'msgId': MsgId.GET_INFO}
        },
        {
            'msgType': MsgType.INS_WEB_CREDENTIALS_SET,
            'msgArg': {
                'msgId': MsgId.SECURIZE,
                'user_name': WEB_DEFAULT_USER,
                'password_old': WEB_DEFAULT_PASSWORD,
                'password_new': device.web_admin_password
            }
        },
        {
            'msgType': MsgType.INS_CFG_WRITE,
            'msgArg': {
                'msgId': MsgId.SET_TOKEN,
                'cloud_remote_server_token': device.cloud_remote_server_token,
                'cloud_interface': True,
                'cloud_allowed_events': MsgType.ON_CLOUD_KEEP_ALIVE,
                'cloud_keep_alive_timeout': cfg['DEVICES_KEEP_ALIVE_TMO'],
                'http_interface': False,
                'jso_interface': False
            }
        },
        {
            'msgType': MsgType.INS_CFG_APPLY,
            'msgArg': {'msgId': MsgId.APPLY}
        },
    ]
    return _ins_cloud_batch(MsgId.ENROLL_DEVICE_STEP_2, batch)


def _delete_device_launch(device):
    """
    Lot d'alliberament: restaurar la contrasenya del web, escriure la
    configuració amb el token buit i aplicar-la.
    """
    batch = [
        {
            'msgType': MsgType.INS_WEB_CREDENTIALS_SET,
            'msgArg': {
                'msgId': MsgId.DESECURIZE,
                'user_name': WEB_DEFAULT_USER,
                'password_old': device.web_admin_password,
                'password_new': WEB_DEFAULT_PASSWORD
            }
        },
        {
            'msgType': MsgType.INS_CFG_WRITE,
            'msgArg': {
                'msgId': MsgId.CLEAR_TOKEN,
                'cloud_remote_server_token': '',
                'cloud_interface': False,
                'cloud_allowed_events': '',
                'http_interface': False,
                'jso_interface': False
            }
        },
        {
            'msgType': MsgType.INS_CFG_APPLY,
            'msgArg': {'msgId': MsgId.APPLY}
        },
    ]
    return _ins_cloud_batch(MsgId.DELETE_DEVICE_STEP_2, batch)


def _ins_cloud_batch(msg_id_name, batch):
    return jsonify({
        'msgType': MsgType.INS_CLOUD_BATCH,
        'msgArg': {
            'bReply': True,
            'msgId': {'name': msg_id_name},
            'listBatch': batch
        }
    })


# ----------------------------------------------------------------------
# Resposta del dispositiu al lot
# ----------------------------------------------------------------------
def _batch_results(msg_arg):
    """Retorna {msgId: msgArg} de cada instrucció resposta."""
    results = {}
    for item in msg_arg.get('listBatch') or []:
        arg = item.get('msgArg') or {}
        if 'msgId' in arg:
            results[arg['msgId']] = arg
    return results


def _on_ans_cloud_batch(device, msg_arg):
    # El lot sencer ha d'haver anat bé abans de mirar-ne les instruccions,
    # com a KapriCloudMainAPI.
    if msg_arg.get('ucRet') != UC_RET_OK:
        MgrLogs.add('batch_failed', f"ucRet={msg_arg.get('ucRet')}", device=device)
        return _empty_reply()

    name = (msg_arg.get('msgId') or {}).get('name')
    if name == MsgId.ENROLL_DEVICE_STEP_2:
        return _enroll_device_step_2(device, msg_arg)
    if name == MsgId.DELETE_DEVICE_STEP_2:
        return _delete_device_step_2(device, msg_arg)
    return _empty_reply()


def _enroll_device_step_2(device, msg_arg):
    """
    Si la lectura d'informació, l'escriptura del token o l'aplicació han
    fallat, no s'enrola i es reintentarà al següent keep-alive. Si només ha
    fallat la contrasenya del web, l'enrolament continua i es desa
    web_securized a fals.
    """
    results = _batch_results(msg_arg)

    info = results.get(MsgId.GET_INFO) or {}
    set_token = results.get(MsgId.SET_TOKEN) or {}
    apply_res = results.get(MsgId.APPLY) or {}

    critical_ok = (info.get('ucRet') == UC_RET_OK
                   and set_token.get('ucRet') == UC_RET_OK
                   and apply_res.get('ucRet') == UC_RET_OK)

    if not critical_ok:
        MgrLogs.add('enroll_failed',
                    f"get_info={info.get('ucRet')} set_token={set_token.get('ucRet')} "
                    f"apply={apply_res.get('ucRet')}",
                    device=device)
        return _empty_reply()

    securize = results.get(MsgId.SECURIZE) or {}
    device.web_securized = (securize.get('ucRet') == UC_RET_OK)
    if not device.web_securized:
        MgrLogs.add('web_not_securized', f"ucRet={securize.get('ucRet')}",
                    device=device, commit=False)

    MgrDevices.enroll(device, info)
    return _empty_reply()


def _delete_device_step_2(device, msg_arg):
    """
    S'esborra el registre si el dispositiu ha quedat lliure, és a dir si ha
    pogut esborrar el token i aplicar la configuració. La confirmació la dona
    el propi dispositiu, no el discovery.
    """
    results = _batch_results(msg_arg)
    clear_token = results.get(MsgId.CLEAR_TOKEN) or {}
    apply_res = results.get(MsgId.APPLY) or {}

    # Només són crítiques les instruccions que deixen el dispositiu lliure.
    # La desprotecció del web no ho és: si mai es va arribar a protegir no té
    # sentit exigir que es desprotegeixi, igual que a l'enrolament la
    # protecció no bloqueja res.
    critical_ok = (clear_token.get('ucRet') == UC_RET_OK
                   and apply_res.get('ucRet') == UC_RET_OK)

    if not critical_ok:
        MgrLogs.add('delete_failed',
                    ', '.join(f"{k}={v.get('ucRet')}" for k, v in results.items()),
                    device=device)
        return _empty_reply()

    desecurize = results.get(MsgId.DESECURIZE) or {}
    if desecurize.get('ucRet') != UC_RET_OK:
        MgrLogs.add('web_not_desecurized', f"ucRet={desecurize.get('ucRet')}",
                    device=device)

    MgrDevices.delete(device, reason='confirmat pel dispositiu')
    return _empty_reply()
