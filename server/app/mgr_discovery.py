# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Client de discovery UDP i vinculació.

Mecànica, igual que l'eina de diagnòstic existent:
  - La petició s'envia al broadcast dirigit de cada interfície activa
    (adreça | ~màscara) i també al broadcast global.
  - El dispositiu respon per BROADCAST al port 60100, no en unicast a qui ha
    preguntat. Cal lligar aquest port amb SO_REUSEADDR per rebre-les i per
    conviure amb altres eines a la mateixa màquina.
  - Per tant es reben també respostes provocades per peticions d'altri. Cada
    resposta es tracta com una observació amb data, no com el resultat d'una
    petició concreta.
  - Es dedupliquen per sEUI64, mai per IP: la IP pot canviar per DHCP.
  - Els ecos de les pròpies peticions es descarten pel contingut de la trama
    (camp type), no comparant el text enviat, perquè la petició porta el
    paràmetre de filtratge i no és una cadena fixa.
"""

import json
import logging
import socket
import struct
import threading
import time

from app.global_consts import MsgType

DISCOVERY_TYPE = 'kapri_discovery'


class DiscoveryObservation:
    """El que s'ha vist d'un dispositiu en un moment donat."""

    def __init__(self, eui64, ip_address, image_version, remote_url, seen_dts):
        self.eui64 = eui64
        self.ip_address = ip_address
        self.image_version = image_version
        self.remote_url = remote_url or ''
        self.seen_dts = seen_dts

    def is_virgin(self):
        """Sense remote_url: disponible per vincular."""
        return self.remote_url == ''

    def belongs_to(self, server_url):
        return bool(self.remote_url) and self._norm(self.remote_url) == self._norm(server_url)

    @staticmethod
    def _norm(url):
        return (url or '').strip().rstrip('/').lower()

    def to_dict(self):
        return {
            'eui64': self.eui64,
            'ip_address': self.ip_address,
            'image_version': self.image_version,
            'remote_url': self.remote_url,
            'seen_dts': self.seen_dts,
        }


class MgrDiscovery:

    def __init__(self, port, token, result_ttl):
        self.port = port
        self.token = token
        self.result_ttl = result_ttl
        self._lock = threading.Lock()
        self._observations = {}   # eui64 -> DiscoveryObservation
        self._sock = None

    # ------------------------------------------------------------------
    # Socket compartit
    # ------------------------------------------------------------------
    def _get_socket(self):
        if self._sock is not None:
            return self._sock
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(('0.0.0.0', self.port))
        except OSError as e:
            logging.error('No s\'ha pogut lligar el port %d: %s', self.port, e)
            sock.close()
            raise
        sock.settimeout(1.0)
        self._sock = sock
        return sock

    def start_listener(self):
        """
        Escolta permanentment el port de discovery. Així es recullen també les
        respostes provocades per peticions d'altri.
        """
        thread = threading.Thread(target=self._listen_loop, name='KoraDiscoveryRx', daemon=True)
        thread.start()
        return thread

    def _listen_loop(self):
        try:
            sock = self._get_socket()
        except OSError:
            return
        logging.info('Discovery escoltant el port %d', self.port)
        while True:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except Exception:
                logging.exception('Error rebent datagrama de discovery')
                continue
            self._handle_datagram(data, addr)

    def _handle_datagram(self, data, addr):
        try:
            payload = json.loads(data.decode('ascii', errors='replace'))
        except Exception:
            return  # no és JSON: probablement l'eco d'una petició
        if not isinstance(payload, dict) or payload.get('type') != DISCOVERY_TYPE:
            return  # eco de la nostra pròpia petició, o trama aliena
        eui64 = payload.get('sEUI64')
        if not eui64:
            return
        obs = DiscoveryObservation(
            eui64=eui64,
            ip_address=addr[0],
            image_version=payload.get('sImageVersion', ''),
            remote_url=payload.get('sRemoteUrl', ''),
            seen_dts=time.time()
        )
        with self._lock:
            self._observations[eui64] = obs   # deduplicació per EUI64

    # ------------------------------------------------------------------
    # Emissió
    # ------------------------------------------------------------------
    @staticmethod
    def list_broadcast_addresses():
        """
        Broadcast dirigit de cada interfície activa, més el global. Un servidor
        amb diverses NIC que només emetés per una no veuria els terminals de
        les altres xarxes.
        """
        addresses = set()
        try:
            import psutil  # opcional
            for _, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET and a.address and a.netmask:
                        addresses.add(MgrDiscovery._directed_broadcast(a.address, a.netmask))
        except ImportError:
            # Sense psutil s'usa només el broadcast global. A Windows, on el
            # servidor pot tenir diverses NIC, convé instal·lar-lo.
            logging.warning('psutil no disponible: discovery només per broadcast global')
        except Exception as e:
            logging.error('Error enumerant interfícies: %s', e)
        addresses.add('255.255.255.255')
        addresses.discard(None)
        return sorted(addresses)

    @staticmethod
    def _directed_broadcast(ip, netmask):
        try:
            ip_i = struct.unpack('>I', socket.inet_aton(ip))[0]
            mask_i = struct.unpack('>I', socket.inet_aton(netmask))[0]
            bc = ip_i | (~mask_i & 0xFFFFFFFF)
            return socket.inet_ntoa(struct.pack('>I', bc))
        except Exception:
            return None

    def send_discovery(self):
        """Emet la petició de discovery. Les respostes les recull el listener."""
        try:
            sock = self._get_socket()
        except OSError:
            return []
        sent = []
        for bc in self.list_broadcast_addresses():
            try:
                sock.sendto(self.token, (bc, self.port))
                sent.append(bc)
            except Exception as e:
                logging.debug('No s\'ha pogut emetre a %s: %s', bc, e)
        logging.debug('Discovery emès a %s', sent)
        return sent

    def send_link(self, ip_address, server_url, keep_alive_tmo):
        """
        Vinculació: instrucció UDP unicast que deixa el dispositiu en
        condicions de trucar al servidor. Configura quatre coses i cap més:
        activa la interfície cloud, hi escriu la URL, declara el keep-alive
        com a esdeveniment permès i en fixa la cadència.

        Són els mateixos paràmetres crítics que KapriCloudMainAPI força en
        tota configuració que envia (add_critical_cfg_to_hardware_cfg). Sense
        cloud_allowed_events, el dispositiu tindria el cloud encès però no
        emetria cap keep-alive, i la vinculació no garantiria res.

        Els quatre camps porten el nom natiu de configuració del terminal, de
        manera que la trama mapeja un a un amb ins_cfg_write. La resposta de
        discovery, en canvi, manté sRemoteUrl, que és la seva convenció
        pròpia.

        Només aquests tres camps: qualsevol altra configuració viatjaria per
        UDP sense autenticar i sobreescriuria ajustos de l'instal·lador.

        La URL és l'endpoint sencer al qual el terminal farà el POST. En
        producció ha de portar el DOMINI, mai la IP: el certificat és un
        certificat públic real emès per a aquest domini i amb una IP no
        validaria. El token NO viatja per UDP; l'escriu la seqüència
        d'enrolament, que ja circula per HTTPS.

        La cadència s'envia com a paràmetre, no fixa al firmware, perquè ha
        de coincidir amb la que escriu l'enrolament: totes dues surten de
        DEVICES_KEEP_ALIVE_TMO.
        """
        payload = json.dumps({
            'type': 'kapri_link',
            'cloud_interface': True,
            'cloud_remote_server_url': server_url,
            'cloud_allowed_events': MsgType.ON_CLOUD_KEEP_ALIVE,
            'cloud_keep_alive_timeout': keep_alive_tmo,
        }).encode('ascii')
        try:
            sock = self._get_socket()
            sock.sendto(payload, (ip_address, self.port))
            logging.info('Instrucció de vinculació enviada a %s', ip_address)
            return True, None
        except Exception as e:
            logging.error('Error enviant la vinculació a %s: %s', ip_address, e)
            return False, str(e)

    # ------------------------------------------------------------------
    # Resultats
    # ------------------------------------------------------------------
    def get_observations(self):
        """Observacions vigents, descartant les massa antigues."""
        now = time.time()
        with self._lock:
            return [o for o in self._observations.values()
                    if now - o.seen_dts <= self.result_ttl]

    def invalidate(self, eui64):
        """
        Descarta l'observació d'un EUI64 perquè sabem que ha quedat obsoleta,
        típicament just després de vincular-lo: el que el discovery havia vist
        és anterior al canvi i no s'ha d'usar per treure conclusions.
        """
        with self._lock:
            self._observations.pop(eui64, None)

    def get_observation(self, eui64):
        now = time.time()
        with self._lock:
            obs = self._observations.get(eui64)
        if obs is None or now - obs.seen_dts > self.result_ttl:
            return None
        return obs
