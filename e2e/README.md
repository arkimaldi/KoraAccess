# Proves e2e

Proves de punta a punta de KoraAccess: arrenquen un servidor real, hi sembren
dades, obren la SPA en un navegador i hi interactuen com ho faria un usuari.

Cobreixen el que les proves del servidor (`server/tests/`) no poden veure,
perquè només passa al navegador. Tots tres errors que van motivar aquesta
carpeta eren d'aquest tipus:

- totes les files sense registre entraven en edició alhora;
- en editar, la columna s'eixamplava i la taula es desplaçava;
- la taula es reordenava a cada keep-alive.

## Posada en marxa

Un cop, a més de les dependències del servidor:

```bash
pip install -r e2e/requirements.txt
python -m playwright install chromium
```

I cal tenir `npm install` fet dins de `webapp/`.

## Executar

Des de l'arrel del repositori:

```bash
python e2e/run_e2e.py --build          # compila l'Angular i executa totes les proves
python e2e/run_e2e.py                  # fa servir el build existent de webapp/dist
python e2e/run_e2e.py -k Polling       # només les proves que continguin «Polling»
```

Amb `--build` es prova el codi actual. Sense, es prova l'últim build, que pot
estar desfasat respecte al codi: en cas de dubte, feu servir `--build`.

## Aïllament

Cada classe de proves arrenca el seu propi servidor, i **no interfereix amb el
de desenvolupament**:

| | Desenvolupament | Proves e2e |
|---|---|---|
| Port HTTP | 8080 | 8099 |
| Port de discovery | 60100 | 60199 |
| Base de dades | `server/` o `KORAACCESS_DATA_DIR` | carpeta temporal, s'esborra en acabar |
| SPA | `server/static/` | `webapp/dist/`, directament |

Els ports es poden canviar amb `KORAACCESS_E2E_PORT` i
`KORAACCESS_E2E_DISCOVERY_PORT`.

## Com es simulen els dispositius

No cal cap terminal ni simulador. Les observacions de discovery s'injecten
enviant per UDP respostes `kapri_discovery` al port de discovery del servidor,
exactament com les enviaria un dispositiu real. El servidor les accepta perquè
escolta respostes de qualsevol origen.

Els dispositius amb registre es creen directament a la base de dades abans
d'arrencar el servidor (`seed.py`).

## En cas d'error

Cada prova que falla desa una captura de pantalla a `e2e/artifacts/`, amb el nom
de la prova. Aquesta carpeta no es versiona.

## Escriure proves noves

Subclasseu `E2ETestCase` (a `harness.py`) i definiu l'escenari:

```python
class ElMeuTest(E2ETestCase):
    SEED = [{'eui64': '00000000000000E1', 'description': 'Porta', 'status': 'enrolled'}]
    OBSERVATIONS = [('00000000000000E2', '')]   # un dispositiu FREE

    def test_alguna_cosa(self):
        self.open_terminals()
        self.assertEqual(self.desc_cell('00000000000000E1').inner_text().strip(), 'Porta')
```

Dues regles que ja ens han fet perdre temps:

1. **Busqueu les files per EUI64, mai per posició** (`self.row(eui64)`). L'ordre
   de la taula pot canviar.
2. **Dins del navegador, pauses amb `self.page.wait_for_timeout()`, mai amb
   `time.sleep()`.** Amb l'API síncrona de Playwright, `time.sleep()` bloqueja
   el despatx d'esdeveniments: les peticions i els missatges de consola que
   passen durant la pausa no es registren. Ens va fer creure que el polling
   estava trencat quan funcionava perfectament.

Les classes no comparteixen servidor ni dades, però les proves d'una mateixa
classe sí. Feu servir EUI64 diferents a cada prova si en modifiquen l'estat.
