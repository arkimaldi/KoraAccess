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

    def get_observations(self):
        return list(self.obs.values())

    def get_observation(self, eui64):
        return self.obs.get(eui64)

    def send_link(self, ip, url):
        self.links_sent.append((ip, url))
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

    def ans_delete(self, token):
        return self.client.post('/v1/Cloud/Event', json={
            'msgType': MsgType.ANS_CLOUD_BATCH,
            'msgArg': {
                'sEUI64': EUI64, 'sToken': token,
                'msgId': {'name': MsgId.DELETE_DEVICE_STEP_2},
                'ucRet': 0,
                'listBatch': [
                    {'msgType': 'ans_web_credentials_set',
                     'msgArg': {'msgId': MsgId.DESECURIZE, 'ucRet': 0}},
                    {'msgType': 'ans_cfg_write',
                     'msgArg': {'msgId': MsgId.CLEAR_TOKEN, 'ucRet': 0}},
                    {'msgType': 'ans_cfg_apply',
                     'msgArg': {'msgId': MsgId.APPLY, 'ucRet': 0}},
                ]
            }
        }).get_json()

    # -- proves --------------------------------------------------------
    def test_unknown_eui64_is_rejected(self):
        r = self.keep_alive()
        self.assertEqual(r['msgType'], 'ins_none')
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
        rows = self.client.get('/api/terminals').get_json()['terminals']
        self.assertTrue(any('resetejat' in w for w in rows[0]['warnings']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
