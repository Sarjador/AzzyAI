# AzzyAI Config X — E2E tests

Suite Playwright que cubre la webui de `USER_AI/azzyai-configx.py`:
carga, edición con persistencia real en `.lua`, guard anti-NaN, sticky de headers
de tactics, conservación de scroll, validación de keys de tactics/PVP, pestaña
Extra y dropdowns de enum.

> ⚠️ La suite **muta archivos .lua**: ejecútala siempre contra un sandbox
> (copia desechable de `USER_AI`), nunca contra tu instalación del juego.
> El workflow de CI ya lo hace así.

## Ejecutar localmente

```bash
cd tests && npm install && npx playwright install chromium

# preparar sandbox desechable (desde la raíz del repo)
mkdir -p ../sandbox/USER_AI
cp ../USER_AI/*.lua ../USER_AI/azzyai-configx.py ../sandbox/USER_AI/
mkdir -p ../sandbox/USER_AI/data && touch ../sandbox/USER_AI/data/dummy.txt

# arrancar la app contra el sandbox
(cd ../sandbox/USER_AI && python3 azzyai-configx.py --no-browser --port 7399 &)

# correr la suite
URL=http://127.0.0.1:7399 CFG=../sandbox/USER_AI/H_Config.lua node e2e.cjs
```

Las capturas de pantalla se guardan en `tests/artifacts/`.
