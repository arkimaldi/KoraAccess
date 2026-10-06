# KoraAccess

Programa de control d'accessos **on premises** per a terminals Kimaldi
KapriLiteOffline.

El repositori conté els dos components. En desenvolupament corren per separat;
en producció es desplega **un sol executable Python** que també serveix la SPA
ja compilada.

```
server/    Backend Python  (obriu aquesta carpeta amb PyCharm)
webapp/    Frontend Angular (obriu aquesta carpeta amb Visual Studio Code)
```

> Obriu la subcarpeta amb cada IDE, no l'arrel: PyCharm indexaria
> `webapp/node_modules` i es ralentiria molt. Tots dos IDE troben el `.git` de
> l'arrel igualment i poden fer commits sense cap configuració especial.

## Estat actual

Primera iteració: **gestió de terminals**. Inclou descoberta, vinculació,
enrolament, assignació a porta i alliberament, amb la pantalla de Terminals.

Fora d'aquesta iteració: mòdul de Portes, sincronització d'usuaris, calendaris
i logs d'accés, i el mòdul de llicència compartit amb KoraPresence.

## Posada en marxa

**Backend**

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python run.py                    # http://localhost:8080
```

**Frontend**

```bash
cd webapp
npm install
npm start                        # http://localhost:4200, amb proxy cap al 8080
```

**Desplegament**

```bash
cd webapp && npm run build
cp -r dist/* ../server/static/   # xcopy /E /Y dist\* ..\server\static\  a Windows
cd ../server && python run.py
```

## Arquitectura

- **Un sol executable.** El servidor és Python amb **cheroot**, que sí que
  serveix TLS (waitress no en fa). No cal cap procés Node ni cap proxy invers.
- **SQLite**, no un servei de base de dades: en on-premises, la còpia de
  seguretat és copiar un fitxer i no hi ha cap dimoni a mantenir.
- **Servei de Windows amb NSSM.** La base de dades ha de viure a `ProgramData`,
  mai dins de `Program Files`.
- **Certificat públic real** emès per al domini del servei; el DNS de la
  instal·lació el resol cap a la IP privada del servidor. Per això la URL que
  es configura als terminals porta el **domini, mai la IP**.

## Protocol amb els terminals

Es manté idèntic al de KapriCloudMainAPI perquè el mateix firmware serveixi per
als dos productes sense cap canvi.

- **Descoberta**: UDP al port 60100. La petició s'emet al broadcast dirigit de
  cada interfície i al global; el dispositiu respon **per broadcast**, de manera
  que cal lligar el port amb `SO_REUSEADDR`. Les respostes es dedupliquen per
  `sEUI64`, mai per IP.
- **Vinculació**: instrucció UDP unicast que configura només la URL. El token
  **no viatja mai per UDP**: l'escriu la seqüència d'enrolament, ja per HTTPS.
- **Keep-alive i instruccions**: `POST /v1/Cloud/Event`. El dispositiu envia
  `on_cloud_keep_alive`; el servidor respon amb un `ins_cloud_batch`; el
  dispositiu confirma amb `ans_cloud_batch` i els `ucRet`.

### Cicle de vida (`Devices.status`)

| Valor | Significat |
|---|---|
| `enroll_pending` | Registre creat en vincular; encara no enrolat. S'accepta el token buit. |
| `enrolled` | Règim normal. Només s'accepta el token propi. |
| `delete_pending` | Alliberament ordenat; s'espera la confirmació del dispositiu. |

L'assignació a porta és un fet independent (taula `PortalDevices`), i l'estat
de connexió (`online` / `lost` / `severe_lost` / `offline`) també.

Un keep-alive d'un EUI64 que no consta a `Devices` es rebutja sempre: el
programa només atén dispositius que ell mateix ha vinculat.

## Proves

```bash
cd server && python tests/test_enroll_delete.py
```

## Pendent

- **Instrucció UDP de vinculació**: el firmware encara no la implementa. El
  format actual (`MgrDiscovery.send_link`) és provisional i cal acordar-lo.
- **Mòdul de Portes**: `PortalDevices` només desa un nom de porta.
- **Llicència**: `LICENSE_MAX_ASSIGNED_DEVICES` és un valor fix.
- **Windows**: NSSM, PyInstaller, hardware-id i la regla de firewall per al
  port UDP 60100 estan sense provar.
- **Diàlegs del frontend**: fan servir `window.prompt`, provisional fins
  decidir el disseny visual.
