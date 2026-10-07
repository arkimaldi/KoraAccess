# Pantalla de Terminals: com funciona

Document de referència sobre com es construeix la pantalla de Terminals, quines
fonts d'informació hi intervenen i per què es tracten de manera diferent. És la
part del programa on és més fàcil mostrar informació falsa, perquè combina dues
fonts que es desfasen entre elles.

---

## 1. Les dues fonts d'informació

La pantalla combina dues coses que **no** són equivalents i que no s'han de
barrejar:

| | Base de dades (`Devices`) | Observacions de discovery |
|---|---|---|
| On viu | SQLite, persistent | RAM de `MgrDiscovery`, es perd en reiniciar |
| Qui l'alimenta | Les crides del terminal a `/v1/Cloud/Event` | Les respostes UDP al port 60100 |
| Caducitat | Cap | 90 s (`DISCOVERY_RESULT_TTL`) |
| Abast | Només dispositius que el programa ha vinculat | Qualsevol dispositiu de la xarxa |
| Fiabilitat | Sempre coneguda | Pot faltar sense que això indiqui res |

La diferència d'abast és la clau: **un dispositiu pot funcionar perfectament i
no sortir mai al discovery**. El broadcast UDP no travessa subxarxes ni VLANs, i
un terminal darrere d'una VPN parla amb el servidor per HTTPS sense que cap
datagrama arribi mai fins a ell.

Per això la regla de fons del disseny és:

> **Cap decisió del cicle de vida depèn del discovery.**
> El discovery és observació, no estat.

---

## 2. Les tres capes

La situació d'un dispositiu es descriu amb tres capes independents. Es mantenen
separades perquè barrejar-les en una sola llista d'estats produeix combinacions
superposades i obliga a regles de prioritat artificials.

### 2.1 Cicle de vida (`Devices.status`)

Persistent, sempre conegut, i determina què fa el servidor quan el dispositiu
truca.

| Valor | Significat | Què fa el servidor |
|---|---|---|
| `enroll_pending` | Registre creat en vincular; encara no enrolat | Llança la seqüència d'enrolament. Accepta el token buit |
| `enrolled` | Règim normal | Sincronitza. Només accepta el token propi |
| `delete_pending` | Alliberament ordenat | Llança la seqüència d'esborrat. No sincronitza |

Un valor només pertany a aquesta capa si sobreviu a un reinici, canvia el
comportament del servidor i no es pot calcular a partir d'altres dades.

### 2.2 Assignació (`PortalDevices`)

Presència o absència de fila. És un fet independent del cicle de vida: un
dispositiu `enrolled` pot tenir porta o no tenir-ne. El límit de llicència es
compta sobre aquesta taula, no sobre els enrolats.

### 2.3 Observació

Dades transitòries, que poden ser desconegudes sense que això signifiqui res:

- `last_seen` / `Devices.link` — deriva dels keep-alives, no del discovery
- Resultat del darrer discovery — verge, apunta a nosaltres, apunta a un altre, o no vist
- `DeviceLogs` — històric d'esdeveniments i errors

---

## 3. Etiquetes de la pantalla

L'etiqueta que es mostra és una **funció de presentació**, no una màquina
d'estats. Es calcula al servidor, a `_label_for_device()`. El frontend no la
dedueix mai.

| Etiqueta | Es calcula quan | Font |
|---|---|---|
| `FREE` | Observació verge i sense registre | Discovery |
| `LINKED` | Registre `enroll_pending` | BBDD |
| `ENROLLED` | Registre `enrolled` sense fila a `PortalDevices` | BBDD |
| `ASSIGNED` | Registre `enrolled` amb fila a `PortalDevices` | BBDD |
| `FOREIGN` | Observació que apunta a un altre servidor, sense registre | Discovery |
| `DELETE_PENDING` | Registre `delete_pending` | BBDD |

Les quatre etiquetes centrals surten **només** de la base de dades. El discovery
només aporta files de dispositius que el programa encara no coneix.

Conseqüència pràctica: un terminal enrolat darrere d'una VPN es mostra
correctament com a `ENROLLED` encara que no aparegui mai al discovery. Només
perd la columna d'IP actual i `seen_in_discovery` queda fals.

---

## 4. Diagnòstics

Els avisos són **contradiccions entre les dues fonts**. No són etiquetes: es
mostren sobre la fila corresponent sense substituir-la, i només es poden
detectar quan el discovery arriba al dispositiu.

| Diagnòstic | Condició |
|---|---|
| Resetejat per fora | Registre `enrolled` i el discovery el veu verge |
| Reassignat a un altre servidor | Registre `enrolled` i el discovery el veu apuntant a una altra URL |
| Desconegut que ens apunta | Observació amb la nostra URL i cap registre a `Devices` |

En els dos primers casos el dispositiu ja no respondrà a cap instrucció: cal un
reset físic o esborrar-ne el registre. En el tercer, els keep-alives es
rebutgen, perquè el programa només atén dispositius que ell mateix ha vinculat.

---

## 5. El problema de l'avís fals

Aquest és el punt que va costar més d'encertar i el motiu principal d'aquest
document.

### Què passava

Just després de vincular i enrolar un terminal, la pantalla el mostrava com a
`ENROLLED` **amb l'avís «s'ha resetejat per fora»**.

La seqüència era aquesta:

1. El discovery observa el dispositiu verge i el desa a RAM.
2. L'usuari prem Vincular. Es crea el registre i s'envia la URL per UDP.
3. El dispositiu es configura i comença a trucar. En segons, passa a `enrolled`.
4. La pantalla compara l'estat actual (`enrolled`) amb **l'observació del pas 1**,
   que encara diu «verge», i conclou que algú l'ha resetejat.

L'observació no era incorrecta: era **anterior al canvi**. El codi la tractava
com si descrivís el present.

Amb el polling de 30 s gairebé no es veia. En baixar a 5 s es veuria gairebé
sempre que es vinculés un terminal, i és un avís que convida l'usuari a fer
justament el que no ha de fer.

### Com està resolt

Dues proteccions, que cobreixen casos diferents:

1. **Invalidació immediata.** En vincular, `MgrDiscovery.invalidate(eui64)`
   descarta l'observació d'aquell dispositiu, perquè sabem del cert que ha
   quedat obsoleta.
2. **Marca de temps.** `Devices.linked_dts` guarda el moment de la darrera
   vinculació. `_is_stale()` descarta qualsevol observació anterior a aquest
   instant, cosa que cobreix la cursa on arriba una resposta de discovery
   antiga poc després d'haver invalidat.

Una observació obsoleta no genera avisos i tampoc compta per a
`seen_in_discovery` ni per a la columna d'IP.

### La regla general

> Abans de comparar una observació amb l'estat de la base de dades, comprova
> que l'observació és **posterior** a l'últim canvi que hi hem fet nosaltres.

---

## 6. Endpoints

### `GET /api/terminals`

Construeix tota la pantalla. Fa quatre passos:

1. Llegeix totes les files de `Devices`.
2. Llegeix les observacions vigents (`get_observations()` ja descarta les
   caducades).
3. Per a cada dispositiu conegut hi associa la seva observació per EUI64, si
   existeix i no és obsoleta.
4. Afegeix les observacions **sense** registre com a files `FREE` o `FOREIGN`.

Retorna també `license` (assignats i límit) i `server_url`.

### `POST /api/discovery/scan`

Emet la petició de discovery al broadcast dirigit de cada interfície i al
global. **Retorna immediatament, sense esperar cap resposta.**

### Accions

| Endpoint | Efecte |
|---|---|
| `POST /api/terminals/link` | Crea el registre `enroll_pending` i envia la URL per UDP |
| `POST /api/terminals/<id>/assign` | Crea la fila a `PortalDevices`, si la llicència ho permet |
| `POST /api/terminals/<id>/unassign` | Esborra la fila de `PortalDevices` |
| `POST /api/terminals/<id>/release` | Passa el registre a `delete_pending` |
| `DELETE /api/terminals/<id>` | Esborra el registre sense instrucció al dispositiu |

---

## 7. Temps i asincronia

Hi ha tres rellotges independents, i convé tenir-los presents perquè expliquen
la majoria de comportaments que semblen estranys:

| Què | Valor | On es configura |
|---|---|---|
| Període de discovery | 30 s | `DISCOVERY_PERIOD` / frontend |
| Caducitat d'una observació | 90 s | `DISCOVERY_RESULT_TTL` |
| Refresc del llistat | 30 s, o 5 s si hi ha feina pendent | `REFRESH_PERIOD_MS` / `FAST_REFRESH_PERIOD_MS` |

### L'scan i el llistat no estan sincronitzats

`POST /scan` només emet i torna. Les respostes arriben després, de manera
asíncrona, al listener. Per tant **el `GET /terminals` que ve just darrere encara
no veu les respostes d'aquell scan, sinó les de l'anterior**.

A la pràctica funciona perquè el TTL (90 s) triplica el període (30 s): sempre
hi ha observacions vigents de dues o tres rondes. Però vol dir que un dispositiu
acabat d'endollar pot trigar fins a dos cicles a aparèixer.

### Polling adaptatiu

Mentre hi ha alguna fila en `enroll_pending` o `delete_pending`, el llistat es
refresca cada 5 s en lloc de 30. **L'scan manté el seu ritme de 30 s**, perquè:

- El canvi que s'espera (passar a `enrolled`) ve de la base de dades, no del
  discovery.
- L'scan és broadcast a tota la xarxa del client i no té sentit multiplicar-lo
  per sis.

El ritme es lliga a l'estat i no a una finestra de temps fixa, de manera que
cobreix també els enrolaments lents i l'alliberament.

### El listener escolta sempre

L'emissió només es produeix quan el frontend ho demana, però el listener del
port 60100 està actiu permanentment. Com que les respostes dels dispositius van
per **broadcast**, el servidor recull també les provocades per peticions
d'altri: per exemple, un tècnic executant l'eina de diagnòstic a la mateixa
xarxa. És informació gratuïta, i per això cada resposta es tracta com una
observació amb data i no com el resultat d'una petició concreta.

Per la mateixa raó, les respostes es dedupliquen per **`sEUI64`, mai per IP**:
el mateix dispositiu respon a cada broadcast dirigit, i la IP pot canviar per
DHCP.

---

## 8. Resum de regles

1. El cicle de vida no depèn mai del discovery.
2. Que un dispositiu no surti al discovery no indica res.
3. Una observació anterior a l'últim canvi nostre és obsoleta.
4. Les etiquetes es calculen al servidor; el frontend no les dedueix.
5. Els avisos són contradiccions, no estats.
6. Deduplicació per EUI64, mai per IP.
7. El discovery només s'emet mentre la pantalla és oberta.
