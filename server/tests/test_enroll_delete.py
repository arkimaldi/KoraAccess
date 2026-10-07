# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Prova del cicle complet: vinculació, enrolament, assignació i alliberament,
simulant les respostes d'un dispositiu real.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.db_models import Devices
from app.global_consts import DeviceStatus, LinkState, MsgType, MsgId
from app.mgr_discovery import DiscoveryObservation
import time

EUI64 = '001824FFFD000094'
SERVER_URL = 'https://kora.exemple.com'


class FakeDiscovery:
    """Substitueix el discovery real: no hi ha xarxa en el test."""

    def __init__(self):
        self.obs = {}
        self.links_sent = []

    def put_virgin(self, eui64, ip='10.0.0.144'):
        self.obs[eui64] = DiscoveryObservation(eui64, ip, 'KapriOn_1.5.7', '', time.time())

    def put_linked(self, eui64, url, ip='10.0.0.144'):
        self.obs[eui64] = DiscoveryObservation(eui64, ip, 'KapriOn_1.5.7', url, time.time())

    def clear(self):
        self.obs = {}

    def invalidate(self, eui64):
        self.obs.pop(eui64, None)

    def get_observations(self):
        return list(self.obs.values())

    def get_observation(self, eui64):
        return self.obs.get(eui64)

    def send_link(self, ip, url, keep_alive_tmo):
        self.links_sent.append((ip, url, keep_alive_tmo))
        return True, None

    def send_discovery(self):
        return ['255.255.255.255']


class EnrollDeleteTestCase(unittest.TestCase):

    def setUp(self):
        os.environ['KORAACCESS_DATA_DIR'] = '/tmp'
        self.app = create_app('dev', start_background=False)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        self.app.config['SERVER_PUBLIC_URL'] = SERVER_URL
        self.app.config['LICENSE_MAX_ASSIGNED_DEVICES'] = 2
        self.discovery = FakeDiscovery()
        self.app.extensions['kora_discovery'] = self.discovery
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # -- utilitats que simulen el dispositiu ---------------------------
    def keep_alive(self, token=''):
        return self.client.post('/v1/Cloud/Event', json={
            'msgType': MsgType.ON_CLOUD_KEEP_ALIVE,
            'msgArg': {'sEUI64': EUI64, 'sToken': token}
        }).get_json()

    def ans_enroll(self, token='', securize_ret=0):
        return self.client.post('/v1/Cloud/Event', json={
            'msgType': MsgType.ANS_CLOUD_BATCH,
            'msgArg': {
                'sEUI64': EUI64, 'sToken': token,
                'msgId': {'name': MsgId.ENROLL_DEVICE_STEP_2},
                'ucRet': 0,
                'listBatch': [
                    {'msgType': 'ans_cpu_get_device_info',
                     'msgArg': {'msgId': MsgId.GET_INFO, 'ucRet': 0, 'ucModelNo': 42,
                                'sImageVersion': 'KapriOn_1.5.7',
                                'sMAC_Address': '00:18:24:00:00:94'}},
                    {'msgType': 'ans_web_credentials_set',
                     'msgArg': {'msgId': MsgId.SECURIZE, 'ucRet': securize_ret}},
                    {'msgType': 'ans_cfg_write',
                     'msgArg': {'msgId': MsgId.SET_TOKEN, 'ucRet': 0}},
                    {'msgType': 'ans_cfg_apply',
                     'msgArg': {'msgId': MsgId.APPLY, 'ucRet': 0}},
                ]
            }
        }).get_json()

    def ans_delete(self, token, desecurize_ret=0):
        return self.client.post('/v1/Cloud/Event', json={
            'msgType': MsgType.ANS_CLOUD_BATCH,
            'msgArg': {
                'sEUI64': EUI64, 'sToken': token,
                'msgId': {'name': MsgId.DELETE_DEVICE_STEP_2},
                'ucRet': 0,
                'listBatch': [
                    {'msgType': 'ans_web_credentials_set',
                     'msgArg': {'msgId': MsgId.DESECURIZE, 'ucRet': desecurize_ret}},
                    {'msgType': 'ans_cfg_write',
                     'msgArg': {'msgId': MsgId.CLEAR_TOKEN, 'ucRet': 0}},
                    {'msgType': 'ans_cfg_apply',
                     'msgArg': {'msgId': MsgId.APPLY, 'ucRet': 0}},
                ]
            }
        }).get_json()

    def enroll_device(self, securize_ret=0):
        """Porta el dispositiu de verge a enrolat."""
        self.discovery.put_virgin(EUI64)
        self.client.post('/api/terminals/link', json={'eui64': EUI64})
        self.keep_alive(token='')
        self.ans_enroll(token='', securize_ret=securize_ret)
        return Devices.query.filter_by(eui64=EUI64).first()

    # -- proves --------------------------------------------------------
    def test_unknown_eui64_is_rejected(self):
        r = self.keep_alive()
        self.assertIsNone(r)
        self.assertIsNone(Devices.query.filter_by(eui64=EUI64).first())

    def test_full_cycle(self):
        # 1. El discovery veu un dispositiu verge
        self.discovery.put_virgin(EUI64)
        rows = self.client.get('/api/terminals').get_json()['terminals']
        self.assertEqual(rows[0]['label'], 'FREE')
        self.assertTrue(rows[0]['can_link'])

        # 2. Vinculació
        r = self.client.post('/api/terminals/link', json={'eui64': EUI64, 'description': 'Porta 1'})
        self.assertEqual(r.status_code, 200)
        device = Devices.query.filter_by(eui64=EUI64).first()
        self.assertEqual(device.status, DeviceStatus.ENROLL_PENDING)
        # La URL enviada per UDP ha de ser el domini, no la IP
        self.assertEqual(self.discovery.links_sent[-1][1], SERVER_URL)
        token = device.cloud_remote_server_token

        # 3. El dispositiu truca amb token buit: rep el lot d'enrolament
        ins = self.keep_alive(token='')
        self.assertEqual(ins['msgType'], MsgType.INS_CLOUD_BATCH)
        self.assertEqual(ins['msgArg']['msgId']['name'], MsgId.ENROLL_DEVICE_STEP_2)
        ins_types = [i['msgType'] for i in ins['msgArg']['listBatch']]
        self.assertEqual(ins_types, [MsgType.INS_CPU_GET_DEVICE_INFO,
                                     MsgType.INS_WEB_CREDENTIALS_SET,
                                     MsgType.INS_CFG_WRITE, MsgType.INS_CFG_APPLY])
        # El token que s'escriu al dispositiu és el del registre
        self.assertEqual(ins['msgArg']['listBatch'][2]['msgArg']['cloud_remote_server_token'], token)

        # 4. El dispositiu confirma: queda enrolat
        self.ans_enroll(token='')
        device = Devices.query.filter_by(eui64=EUI64).first()
        self.assertEqual(device.status, DeviceStatus.ENROLLED)
        self.assertEqual(device.knet_id, 42)
        self.assertTrue(device.web_securized)
        self.assertEqual(device.link, LinkState.ONLINE)

        # 5. Un cop enrolat, el token buit ja no s'accepta
        self.discovery.put_linked(EUI64, SERVER_URL)
        before = device.link_kick_dts
        self.keep_alive(token='')
        db.session.refresh(device)
        self.assertEqual(device.link_kick_dts, before)   # cap crida vàlida

        # 6. Assignació a porta
        r = self.client.post(f'/api/terminals/{device.device_id}/assign',
                             json={'portal_name': 'Porta principal'})
        self.assertEqual(r.status_code, 200)
        rows = self.client.get('/api/terminals').get_json()['terminals']
        self.assertEqual(rows[0]['label'], 'ASSIGNED')

        # 7. No es pot alliberar mentre està assignat
        r = self.client.post(f'/api/terminals/{device.device_id}/release')
        self.assertEqual(r.status_code, 400)

        # 8. Es desassigna i s'allibera
        self.client.post(f'/api/terminals/{device.device_id}/unassign')
        r = self.client.post(f'/api/terminals/{device.device_id}/release')
        self.assertEqual(r.status_code, 200)
        db.session.refresh(device)
        self.assertEqual(device.status, DeviceStatus.DELETE_PENDING)

        # 9. El dispositiu rep el lot d'esborrat i el confirma
        ins = self.keep_alive(token=token)
        self.assertEqual(ins['msgArg']['msgId']['name'], MsgId.DELETE_DEVICE_STEP_2)
        self.ans_delete(token=token)
        self.assertIsNone(Devices.query.filter_by(eui64=EUI64).first())

    def test_enroll_continues_if_only_web_fails(self):
        self.discovery.put_virgin(EUI64)
        self.client.post('/api/terminals/link', json={'eui64': EUI64})
        self.keep_alive(token='')
        self.ans_enroll(token='', securize_ret=1)
        device = Devices.query.filter_by(eui64=EUI64).first()
        self.assertEqual(device.status, DeviceStatus.ENROLLED)
        self.assertFalse(device.web_securized)

    def test_manual_delete_requires_severe_lost(self):
        self.discovery.put_virgin(EUI64)
        self.client.post('/api/terminals/link', json={'eui64': EUI64})
        self.keep_alive(token='')
        self.ans_enroll(token='')
        device = Devices.query.filter_by(eui64=EUI64).first()
        self.client.post(f'/api/terminals/{device.device_id}/release')

        r = self.client.delete(f'/api/terminals/{device.device_id}')
        self.assertEqual(r.status_code, 400)       # encara online

        device.link = LinkState.SEVERE_LOST
        db.session.commit()
        r = self.client.delete(f'/api/terminals/{device.device_id}')
        self.assertEqual(r.status_code, 200)

    def test_license_limit_blocks_assignment(self):
        self.app.config['LICENSE_MAX_ASSIGNED_DEVICES'] = 0
        self.discovery.put_virgin(EUI64)
        self.client.post('/api/terminals/link', json={'eui64': EUI64})
        self.keep_alive(token='')
        self.ans_enroll(token='')
        device = Devices.query.filter_by(eui64=EUI64).first()
        r = self.client.post(f'/api/terminals/{device.device_id}/assign',
                             json={'portal_name': 'X'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('llicència', r.get_json()['error'])

    def test_foreign_and_reset_warnings(self):
        # Dispositiu vinculat a un altre servidor i sense registre: FOREIGN
        self.discovery.put_linked(EUI64, 'https://altre.exemple.com')
        rows = self.client.get('/api/terminals').get_json()['terminals']
        self.assertEqual(rows[0]['label'], 'FOREIGN')

        # Enrolat que el discovery veu verge: avís de reset per fora
        self.discovery.clear()
        self.discovery.put_virgin(EUI64)
        self.client.post('/api/terminals/link', json={'eui64': EUI64})
        self.keep_alive(token='')
        self.ans_enroll(token='')

        # Una observació ANTERIOR a la vinculació és obsoleta: cap avís
        rows = self.client.get('/api/terminals').get_json()['terminals']
        self.assertEqual(rows[0]['warnings'], [])

        # Una observació POSTERIOR que el veu verge sí que és un reset per fora
        import time as _t
        _t.sleep(1.1)
        self.discovery.put_virgin(EUI64)
        rows = self.client.get('/api/terminals').get_json()['terminals']
        self.assertTrue(any('resetejat' in w for w in rows[0]['warnings']))


    # -- casos detectats en proves amb maquinari real ----------------
    def test_delete_confirmed_with_empty_token(self):
        """
        El lot d'esborrat esborra el token del dispositiu i l'aplica abans
        que respongui, de manera que la confirmació arriba amb sToken buit.
        S'ha d'acceptar igualment; si no, el registre queda en delete_pending
        per sempre.
        """
        device = self.enroll_device()
        device_id = device.device_id
        self.client.post(f'/api/terminals/{device_id}/release')

        self.keep_alive(token=device.cloud_remote_server_token)
        self.ans_delete(token='')          # el dispositiu ja no té token
        self.assertIsNone(Devices.query.filter_by(eui64=EUI64).first())

    def test_delete_succeeds_if_only_web_fails(self):
        """
        Si el web no es va arribar a protegir, la desprotecció fallarà. No ha
        de bloquejar l'esborrat, igual que a l'enrolament la protecció no
        bloqueja res.
        """
        device = self.enroll_device(securize_ret=1)
        self.assertFalse(device.web_securized)
        self.client.post(f'/api/terminals/{device.device_id}/release')

        self.keep_alive(token=device.cloud_remote_server_token)
        self.ans_delete(token='', desecurize_ret=4)
        self.assertIsNone(Devices.query.filter_by(eui64=EUI64).first())

    def test_link_is_refreshed_in_any_status(self):
        """
        L'estat de connexió es refresca a cada crida vàlida, també en
        delete_pending: la pantalla ha de mostrar si el dispositiu és viu
        mentre s'està alliberant.
        """
        device = self.enroll_device()
        self.client.post(f'/api/terminals/{device.device_id}/release')
        db.session.refresh(device)
        before = device.link_kick_dts

        import time as _t
        _t.sleep(1.1)
        self.keep_alive(token=device.cloud_remote_server_token)
        db.session.refresh(device)
        self.assertGreater(device.link_kick_dts, before)

    def test_delete_batch_leaves_device_as_factory(self):
        """
        El lot d'alliberament ha de deixar el dispositiu com de fàbrica: sense
        token, sense URL i amb el cloud apagat. Esborrar la URL és
        imprescindible perquè el discovery el torni a reportar com a verge.
        """
        device = self.enroll_device()
        self.client.post(f'/api/terminals/{device.device_id}/release')
        ins = self.keep_alive(token=device.cloud_remote_server_token)

        cfg = next(i['msgArg'] for i in ins['msgArg']['listBatch']
                   if i['msgArg'].get('msgId') == MsgId.CLEAR_TOKEN)
        self.assertEqual(cfg['cloud_remote_server_token'], '')
        self.assertEqual(cfg['cloud_remote_server_url'], '')
        self.assertFalse(cfg['cloud_interface'])

    def test_link_frame_enables_cloud(self):
        """
        La trama UDP de vinculació ha de deixar el dispositiu en condicions de
        trucar: cloud actiu, URL i cadència de keep-alive. I res més.
        """
        self.discovery.put_virgin(EUI64)
        self.client.post('/api/terminals/link', json={'eui64': EUI64})

        frame = self.discovery.links_sent[-1]
        self.assertEqual(frame[1], SERVER_URL)
        self.assertEqual(frame[2], self.app.config['DEVICES_KEEP_ALIVE_TMO'])

    def test_delete_blocked_if_securized_web_cannot_be_restored(self):
        """
        Si vam canviar la contrasenya del web i no la podem restaurar, no es
        pot esborrar el registre: el dispositiu quedaria amb una contrasenya
        que ja no sap ningú.
        """
        device = self.enroll_device(securize_ret=0)
        self.assertTrue(device.web_securized)
        self.client.post(f'/api/terminals/{device.device_id}/release')

        self.keep_alive(token=device.cloud_remote_server_token)
        self.ans_delete(token='', desecurize_ret=4)
        self.assertIsNotNone(Devices.query.filter_by(eui64=EUI64).first())

        # Amb la desprotecció correcta, sí que s'esborra
        self.ans_delete(token='', desecurize_ret=0)
        self.assertIsNone(Devices.query.filter_by(eui64=EUI64).first())

    def test_enroll_reply_ignored_while_delete_pending(self):
        """
        Una resposta d'enrolament endarrerida no ha de ressuscitar un
        dispositiu que s'està alliberant.
        """
        device = self.enroll_device()
        self.client.post(f'/api/terminals/{device.device_id}/release')

        self.ans_enroll(token=device.cloud_remote_server_token)
        db.session.refresh(device)
        self.assertEqual(device.status, DeviceStatus.DELETE_PENDING)

    def test_nothing_to_do_returns_null(self):
        """
        Quan no hi ha instruccions es retorna null, no un msgType inventat: el
        firmware ho interpretaria com un error i reintentaria en bucle.
        """
        device = self.enroll_device()
        ans = self.keep_alive(token=device.cloud_remote_server_token)
        self.assertIsNone(ans)

    def test_failed_batch_is_not_processed(self):
        """Si el lot sencer ha fallat, no se'n miren les instruccions."""
        device = self.enroll_device()
        self.client.post(f'/api/terminals/{device.device_id}/release')
        self.client.post('/v1/Cloud/Event', json={
            'msgType': MsgType.ANS_CLOUD_BATCH,
            'msgArg': {
                'sEUI64': EUI64, 'sToken': '',
                'msgId': {'name': MsgId.DELETE_DEVICE_STEP_2},
                'ucRet': 7,
                'listBatch': [
                    {'msgArg': {'msgId': MsgId.CLEAR_TOKEN, 'ucRet': 0}},
                    {'msgArg': {'msgId': MsgId.APPLY, 'ucRet': 0}},
                ]
            }
        })
        self.assertIsNotNone(Devices.query.filter_by(eui64=EUI64).first())

    def test_no_false_reset_warning_after_manual_url_setup(self):
        """
        Entre la vinculació i el primer contacte poden passar minuts (URL
        configurada a mà). Els scans d'aquest interval veuen el dispositiu
        encara verge, però són anteriors a l'últim contacte: no han de
        disparar l'avís de reset per fora.
        """
        self.discovery.put_virgin(EUI64)
        self.client.post('/api/terminals/link', json={'eui64': EUI64})

        # Scan posterior a la vinculació: el dispositiu encara no està configurat
        import time as _t
        _t.sleep(1.1)
        self.discovery.put_virgin(EUI64)

        # Ara sí, el dispositiu es configura i s'enrola
        _t.sleep(1.1)
        self.keep_alive(token='')
        self.ans_enroll(token='')

        rows = self.client.get('/api/terminals').get_json()['terminals']
        self.assertEqual(rows[0]['label'], 'ENROLLED')
        self.assertEqual(rows[0]['warnings'], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
