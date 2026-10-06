# KoraAccess — Backend (Python)

Servidor on-premises de control d'accessos. Obriu aquesta carpeta amb PyCharm.

## Posada en marxa

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python run.py
```

Per defecte arrenca en mode `dev`: HTTP pla al port 8080. Amb
`KORAACCESS_CONFIG=prod` i les variables del certificat, serveix HTTPS al 8443.

## Variables d'entorn

| Variable | Per a què serveix |
|---|---|
| `KORAACCESS_CONFIG` | `dev` o `prod` |
| `KORAACCESS_DATA_DIR` | On viu el fitxer SQLite. A Windows, `ProgramData`, mai `Program Files` |
| `KORAACCESS_PUBLIC_URL` | URL que es configura als terminals. **Ha de ser el domini, mai la IP** |
| `KORAACCESS_TLS_CERT` / `KORAACCESS_TLS_KEY` | Certificat públic del domini |

## Per què cheroot i no waitress

Waitress no serveix TLS. Cheroot sí, és Python pur i WSGI, de manera que no
cal cap procés Node ni cap proxy invers: un sol executable.

## Estructura

```
run.py                  Punt d'entrada (cheroot)
config.py               Configuració i temps de link
app/db_models.py        Devices, PortalDevices, DeviceLogs
app/mgr_devices.py      Cicle de vida: enroll_pending -> enrolled -> delete_pending
app/mgr_discovery.py    Discovery UDP multi-NIC i vinculació
app/mgr_link.py         Estat de connexió (online/lost/severe_lost/offline)
app/api/cloud_event.py  /v1/Cloud/Event — protocol CloudKimaldi
app/api/terminals.py    API REST de la pantalla de Terminals
static/                 Build de l'Angular
```

## Proves

```bash
python tests/test_enroll_delete.py
```

Simulen un dispositiu real: cicle complet, límit de llicència, esborrat manual
i avisos de contradicció.

## Pendent

- **Instrucció UDP de vinculació**: el firmware encara no la implementa.
  `MgrDiscovery.send_link()` envia `{"type":"kapri_link","sRemoteUrl":...}`;
  cal acordar-ne el format real amb l'equip de firmware.
- **Mòdul de Portes**: `PortalDevices` només desa un nom de porta.
- **Llicència**: `LICENSE_MAX_ASSIGNED_DEVICES` és un valor fix fins que
  s'integri el mòdul compartit amb KoraPresence.
- **Windows**: NSSM, PyInstaller, hardware-id i regla de firewall per al port
  UDP 60100 no s'han pogut provar aquí.
