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
