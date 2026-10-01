# Estación de entrada de paquetes — Simplex

App local (Python + Flask) para el almacén Miami. Cámara + lectura de etiqueta (código de
barras para el tracking, IA/OCR para nombre/casillero/contenido) + balanza PS60 + impresión,
empujando a Simplex por **token de estación**. Funciona **online** (IA en la nube) u **offline** (OCR local).

## Instalar

### Windows (una línea, PowerShell)
```powershell
git clone https://github.com/gregorysantana/simplex-station.git; cd simplex-station; py -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; copy .env.example .env; notepad .env; python app.py
```
Edita `.env` (pon `STATION_TOKEN`, `AI_MODE`, `OPENAI_API_KEY`) cuando se abra el Notepad, guárdalo y cierra. Abre http://localhost:8777. La **cámara se elige en la página** (menú arriba del video) y el navegador pedirá permiso.

### macOS / Linux
```bash
cd simplex-station
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # completa SIMPLEX_URL, STATION_TOKEN, AI_MODE, OPENAI_API_KEY
python app.py           # http://localhost:8777
```

> La cámara la maneja el **navegador** (getUserMedia): se elige en el selector de la página
> y el navegador pide permiso. No depende de permisos del SO al proceso Python.

## Flujo
1. **📸 Capturar**: toma el frame → tracking del **código de barras** + IA/OCR → nombre/casillero/contenido.
   - Busca el cliente por casillero (ej. `25` → `H-000025`) y lo selecciona si hay 1.
2. **⚖️ Pesar**: lee la balanza PS60 (USB HID) y llena el peso.
3. Ajusta campos, elige **contenedor** (opcional), **Agregar paquete** → crea en Simplex e **imprime** la etiqueta.

## Config (.env)
- `SIMPLEX_URL`, `STATION_TOKEN` (token de estación emitido por un admin).
- `AI_MODE`: `gemini` | `openai` | `claude` | `offline` (+ su API key/modelo).
- `CAMERA_INDEX` (0 por defecto). `SCALE_VENDOR_ID`/`SCALE_PRODUCT_ID` (hex; vacío = autodetecta).
- `LABEL_PRINTER` (nombre en el SO; vacío = impresora por defecto; usa `lp` en mac/linux, impresión del SO en Windows).

## Notas
- El **tracking** siempre sale del código de barras (nunca del QR ni OCR).
- El **casillero** no es el ZIP; se valida contra los clientes reales de Simplex.
- Las API keys viven en `.env` de la estación (no en el navegador).
- El token mapea a un usuario con permisos `packages.create`, `clients.view`, `containers.warehouse`.

## Endpoints Simplex usados (token por header `X-Station-Token`)
`/api/station/client-search`, `/api/station/containers`, `/api/station/intake-pending`,
`/api/station/package-create`, `/api/station/container-create`.
