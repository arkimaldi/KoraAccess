# Usuaris, autenticació i sessions

Document de referència del mòdul d'usuaris. Explica què es protegeix, com i,
sobretot, per què, perquè diverses decisions no s'entenen només llegint el codi.

---

## 1. Principi

**No escriure cap peça criptogràfica ni de protocol.** El codi propi es limita a
lligar llibreries provades, i ha de ser prou petit per revisar-lo sencer
(`server/app/mgr_auth.py`).

| Peça | Què fem servir |
|---|---|
| Contrasenyes | argon2id, amb `argon2-cffi` |
| Usuari actual, `current_user` | Flask-Login |
| Límit d'intents | Flask-Limiter |
| Identificador de sessió | `secrets.token_urlsafe(32)`, 256 bits |
| Hash de l'identificador | SHA-256, `hashlib` |

---

## 2. Com funciona una sessió

1. `POST /api/auth/login` comprova usuari i contrasenya.
2. El servidor genera un identificador aleatori, en desa **només el hash** a la
   taula `user_sessions` i l'envia al navegador en una cookie.
3. A cada petició, el servidor fa el hash de la cookie, busca la sessió i
   comprova que no hagi caducat.
4. `POST /api/auth/logout` esborra la fila. També es pot revocar esborrant-la des
   del servidor.

El frontend **no veu mai el token**. Sap qui és l'usuari preguntant-ho a
`GET /api/auth/me`.

---

## 3. Per què cada decisió

### Cookie i no token a `localStorage`

La cookie és `HttpOnly`: JavaScript no la pot llegir. Si algun dia la webapp té
una vulnerabilitat XSS, l'atacant podrà actuar dins de la pàgina, però no podrà
endur-se la sessió. Amb un token a `localStorage`, com fa KapriCloudWebManager,
sí que podria.

### Només el hash a la base de dades

A on-premises, la base de dades és un fitxer SQLite que algú copia per fer una
còpia de seguretat. Si s'hi desés l'identificador tal qual, qui tingués la còpia
podria entrar amb qualsevol sessió activa. Amb el hash, no.

N'hi ha prou amb un SHA-256 simple, sense sal ni hash lent: aquests només calen
per a secrets triats per persones, que són previsibles. Un identificador de 256
bits aleatoris no es pot endevinar.

### El token és opac: no porta el perfil ni l'idioma

Si el token portés dades de l'usuari, o el servidor se'n refiaria (i l'usuari se
les podria modificar) o les tornaria a llegir de la base de dades (i llavors no
caldria que hi fossin). El perfil i l'idioma surten de `GET /api/auth/me`.

### Doble caducitat

| | Valor | Configuració |
|---|---|---|
| Per inactivitat | 8 hores | `AUTH_IDLE_TIMEOUT_S` |
| Absoluta, des del login | 30 dies | `AUTH_ABSOLUTE_TIMEOUT_S` |

L'activitat no s'escriu a cada petició, sinó com a molt un cop per minut
(`AUTH_LAST_SEEN_UPDATE_S`): la pantalla de Terminals fa polling cada pocs
segons. Les sessions caducades s'esborren en accedir-hi, en cada login i cada
hora.

### Un token nou a cada login

Evita la fixació de sessió: un atacant no pot fer servir un identificador que
hagi aconseguit abans que l'usuari entrés.

### Protecció contra CSRF

Dues capes:

1. La cookie és `SameSite=Strict`: el navegador no l'envia en peticions que
   vinguin d'una altra web.
2. Les peticions que modifiquen dades han de portar la capçalera
   `X-Requested-With: KoraAccess`, que afegeix l'interceptor del frontend. Una
   altra web no la pot posar sense permís CORS, que el servidor no dona.

### Sense bloqueig de comptes

Hi ha un límit de 5 intents de login per minut i per IP. No es bloqueja el compte
després de X intents fallits: llavors qualsevol podria bloquejar el compte d'un
altre a propòsit. El canvi de contrasenya té el mateix límit, perquè si no
serviria per endevinar la contrasenya actual.

### No es pot saber quins usuaris existeixen

Usuari inexistent, contrasenya incorrecta i compte desactivat donen exactament
el mateix error. Quan l'usuari no existeix, igualment es calcula un hash, perquè
el temps de resposta no ho delati.

### Contrasenyes

Mínim de 10 caràcters, màxim de 128, sense regles de composició. És el que
recomana avui NIST (SP 800-63B): les regles de composició porten a contrasenyes
previsibles com `Contrasenya1!`.

---

## 4. Protegit per defecte

**Totes les rutes de `/api/` requereixen sessió**, tret de les declarades a
`PUBLIC_API_ENDPOINTS` a `server/app/__init__.py`, que avui són el login i el
logout. Un endpoint nou queda protegit encara que algú s'oblidi de marcar-lo.
La prova `test_new_api_endpoints_are_protected_by_default` recorre totes les
rutes i ho comprova.

Queden fora:
- **La SPA**: ha de poder carregar la pantalla de login.
- **`/v1/Cloud/Event`**: és el protocol dels terminals, que s'autentiquen amb el
  seu propi token.

---

## 5. Perfils

| Perfil | Pot |
|---|---|
| `admin` | Tot, inclosa la gestió d'usuaris |
| `operator` | Tot, excepte la gestió d'usuaris |

Els permisos es comproven **al servidor**, amb el decorador `admin_required`
(`server/app/api/permissions.py`), a totes les rutes de `/api/users`. La prova
`test_every_users_route_requires_admin` recorre-les totes: una ruta nova sense el
decorador la fa fallar. Al frontend el perfil només serveix per amagar el menú
d'usuaris; si un operador hi entra escrivint l'URL, el servidor li respon 403.

El perfil es llegeix de la base de dades a cada petició, no viatja en el token.
Si es treu el perfil d'administrador a algú, té efecte a la petició següent,
sense haver de tancar-li la sessió.

## 5b. Gestió d'usuaris des de la webapp

Pantalla **Usuaris**, només per a administradors.

- **Contrasenyes generades pel servidor.** En crear un usuari o restablir-li la
  contrasenya, el servidor en genera una de temporal (16 caràcters en grups de
  quatre, sense caràcters que es confonguin) i la retorna **una sola vegada**.
  L'usuari l'haurà de canviar en entrar. Els administradors que les trien a mà
  acostumen a posar-ne de febles, i així ningú més no la coneix després del
  primer login. El modal que la mostra no es tanca fent clic a fora, perquè no
  es perdi per accident.
- **El nom d'usuari no es pot canviar**: és amb el que s'entra.
- **No s'esborren usuaris, es desactiven.** Es conserva la traça per als
  registres d'auditoria. Desactivar tanca totes les sessions.
- **Ningú es pot desactivar ni treure el perfil d'administrador a si mateix**,
  per evitar tancar-se la porta per accident.
- **Sempre hi ha d'haver almenys un administrador actiu.**
- **Tancar les sessions** d'un usuari sense desactivar-lo, per exemple si ha
  perdut el portàtil. Si un administrador tanca les seves, es manté la que està
  fent servir.

Aquestes regles són a `mgr_auth.py` i les comparteixen la pantalla i les ordres
de línia de comandes, de manera que no es poden desincronitzar.

---

## 6. Ordres de gestió

```bash
cd server
python manage.py users create-admin
python manage.py users create --role operator
python manage.py users list
python manage.py users reset-password <usuari>
python manage.py users deactivate <usuari>
python manage.py users activate <usuari>
```

- **El primer administrador es crea així, en instal·lar.** No hi ha pantalla web
  de primera configuració: el primer que hi arribés es convertiria en
  administrador. Tampoc hi ha cap contrasenya per defecte al codi.
- **L'accés al servidor és la font de confiança.** També és el camí per
  recuperar l'accés si s'oblida la contrasenya de l'últim administrador.
- `reset-password` deixa la contrasenya com a temporal: l'usuari l'haurà de
  canviar en entrar, i mentrestant el servidor rebutja qualsevol altra petició.
  També tanca totes les sessions de l'usuari.
- `deactivate` tanca totes les sessions, i no deixa desactivar l'últim
  administrador actiu.
- Les contrasenyes es demanen sempre de manera interactiva i sense mostrar-les,
  mai com a argument: quedarien a l'historial de l'intèrpret d'ordres.

---

## 7. Desenvolupament

La cookie porta `Secure`, i el navegador només l'envia per HTTPS. En
desenvolupament, que va en HTTP pla, `DevConfig` la desactiva
(`AUTH_COOKIE_SECURE = False`). **No s'ha de copiar a producció.**
