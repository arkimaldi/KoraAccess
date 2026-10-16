# KoraAccess — Frontend (Angular)

SPA d'una sola pàgina amb la pantalla de Terminals. Obriu aquesta carpeta amb
Visual Studio Code.

## Posada en marxa

```bash
npm install
npm start          # http://localhost:4200, amb proxy cap al Python del 8080
```

`proxy.conf.json` redirigeix `/api` i `/v1` al backend, de manera que durant el
desenvolupament els dos projectes corren per separat.

## Build per a producció

```bash
npm run build
```

El resultat queda a `dist/`. **Copieu-ne el contingut a `static/` del projecte
Python**, que és qui el serveix en producció: el desplegament és un sol
executable, no dos processos.

```bash
xcopy /E /Y dist\* ..\server\static\     # Windows
cp -r dist/* ../server/static/           # Linux/macOS
```

## Estructura

```
src/app/models/terminal.model.ts      Tipus de l'API
src/app/services/terminals.service.ts Crides HTTP
src/app/terminals/                    Pantalla de Terminals
```

## Notes

- El discovery s'emet cada 30 s **només mentre la pantalla és oberta**
  (`ngOnDestroy` atura el temporitzador).
- Les etiquetes (FREE, LINKED, ENROLLED, ASSIGNED, FOREIGN, DELETE_PENDING) les
  calcula el servidor. El frontend no les dedueix.
- Els diàlegs fan servir `window.prompt` de moment: és la peça a substituir
  quan es decideixi el disseny visual.

## Interfície

Seguim el patró de KapriCloudWebManager:

- **Bootstrap 5.3**, CSS i JavaScript, empaquetat amb l'aplicació des de
  `node_modules` (vegeu `angular.json`). **Mai des d'un CDN**: molts servidors de
  client no tenen sortida a Internet. El mateix per a qualsevol tipus de lletra o
  joc d'icones que s'afegeixi.
- **Angular Router.** Rutes a `src/app/app.routes.ts`. El login i el canvi de
  contrasenya obligatori no són rutes: els mostra `AppComponent` segons l'estat
  de la sessió.
- **Modals amb el `ModalService` del Manager**, copiat sense canvis a
  `src/app/services/modal.service.ts`. Els modals genèrics (confirmar, demanar un
  valor) són a `src/app/shared/modals`. Ja no es fa servir `window.confirm` ni
  `window.prompt`.
- Els desplegables (menú de l'avatar, accions de cada usuari) fan servir el
  `data-bs-toggle="dropdown"` de Bootstrap.

Bootstrap genera un avís en compilar (`.form-floating>~label`): és un defecte
conegut del seu CSS i és inofensiu.

## Traduccions (i18n)

Tota la traducció es fa aquí, amb **ngx-translate**, igual que a
KapriCloudWebManager. El servidor no rep l'idioma: envia claus.

Idiomes: `en` (per defecte i idioma de referència), `ca` i `es`. Fitxers a
`src/assets/i18n/`.

### Tres tipus de claus

| Tipus | Exemple | D'on surt | Com es manté |
|---|---|---|---|
| Text de plantilla | `Add description` | `{{ 'Add description' \| translate }}` | `npm run ngx-extract` |
| `_sys_...` | `_sys_confirmRelease` | Codi TypeScript, o noms construïts a la plantilla | A mà |
| `MSG_...` | `MSG_LICENSE_LIMIT_REACHED` | Missatges del servidor (`server/app/messages.py`) | A mà |

Les plantilles s'escriuen **en anglès**, i la clau és el mateix text. L'extractor
només detecta la forma `{{ 'text' | translate }}`, també dins d'atributs
(`placeholder="{{ 'text' | translate }}"`). No ha de contenir cometes.

**Tota clau que es passa des del codi ha de ser `_sys_`**, també els títols i
textos dels modals (`titleKey: '_sys_actionRelease'`). L'extractor no les troba,
i el procediment només restaura les `_sys_` i les `MSG_`: una clau normal
passada des del codi desapareixeria d'`en.json` sense avisar. La prova
`test_keys_passed_from_code_are_sys_or_msg` ho fa complir.

### Procediment

És el mateix que a KapriCloudWebManager:

1. Canvieu els textos només a les plantilles i al codi.
2. `npm run ngx-extract`. **Sobreescriu `en.json` sencer** i hi deixa només les
   claus de plantilla: restaureu-hi les `_sys_` i les `MSG_` (per exemple amb
   `git diff` i desfent les línies esborrades).
3. Feu servir `ngx_tool` amb `ngx_tool_dict.json` per completar `ca.json` i
   `es.json`.
4. Executeu `python tests/test_i18n.py` des de `server/`.

### Missatges del servidor

Arriben amb aquesta forma, tant els errors com els avisos de la pantalla:

```json
{"message_key": "MSG_LICENSE_LIMIT_REACHED",
 "params": {"assigned": 20, "limit": 20},
 "message": "License limit reached (20/20)."}
```

`MessageService.text()` tradueix `message_key` amb els `params`. Si la clau no
té traducció, mostra `message`, el text anglès de reserva. Per afegir-ne un de
nou: la clau i el text anglès a `server/app/messages.py`, i la traducció als tres
fitxers d'idioma, amb els paràmetres en la sintaxi `{{param}}`.

### La prova que ho lliga tot

`server/tests/test_i18n.py` comprova, entre altres coses, que tots els idiomes
tenen les mateixes claus, que cada clau del servidor és traduïda amb els mateixos
paràmetres, que cada text de plantilla i cada `_sys_` del codi és al diccionari,
i que `ngx_tool_dict.json` quadra amb els fitxers. Si oblideu un dels passos
anteriors, falla.

### Idioma de l'usuari

`LanguageService` el tria així: el desat amb el selector, si no el del navegador,
i si no l'anglès. Quan hi hagi el mòdul d'usuaris, la seva preferència s'haurà
d'afegir allà, per davant de les altres.
