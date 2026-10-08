# Timer Aeropuerto

App Android para medir tiempos de procesos en estudios en aeropuertos. Los encuestadores
registran con un toque cada etapa de un proceso (inicio de fila, inicio de atención, fin) y
la app calcula las duraciones. Incluye además un módulo de encuestas de satisfacción.

Hecha en Python con [Flet](https://flet.dev) 0.85.3 (Flutter por debajo) y compilada como APK.

## Funcionamiento

1. **Inicio:** el encuestador elige aeropuerto y escribe su nombre.
2. **Módulo:**
   - **Tiempos de Procesos:** cada observación sigue 3 etapas según el tipo: Counter,
     Autochequeo, AVSEC, Equipaje de llegada, Policía Internacional (llegadas/salidas) y
     SAG/Aduana. Se pueden llevar varias observaciones en paralelo.
   - **Preguntas Adicionales:** encuesta de satisfacción de 4 preguntas, en español o inglés.
3. **Finalizar sesión:** exporta un CSV y envía los datos a Google Sheets.

Funciona sin conexión: solo necesita internet al finalizar la sesión. Si la app se cierra,
al abrirla de nuevo retoma la sesión en curso (de hoy o de ayer).

## Datos

**En el teléfono.** Cada acción se guarda de inmediato en un JSON por sesión, en el
almacenamiento interno de la app. Al finalizar se genera además un CSV. Se deja una copia
de ambos en `Documents/TimerAeropuerto`, visible desde el explorador de archivos o por USB.

**En Google Sheets.** Al finalizar, la app envía las filas a un Google Apps Script
(`_GAS_URL` en `almacenamiento.py`) que las agrega a la planilla:

- `Observaciones`: una fila por observación completada, con la clave `obs_id`.
- `encuestas`: una fila por encuesta, con la clave `sesion_id` + `numero`.

El script descarta las filas que ya existen, así que reenviar una sesión es seguro. Si el
envío falla, la sesión queda pendiente y la pantalla de inicio la reintenta automáticamente
(o con el botón **Enviar ahora**).

El código del Apps Script no está en este repo: se administra con
[clasp](https://github.com/google/clasp). Al publicar cambios, hay que actualizar
**el mismo despliegue** (`clasp deploy -i <id>`) para que la URL no cambie.

## Estructura

| Archivo | Contenido |
|---|---|
| `main.py` | Interfaz: pantallas, diálogos y flujo de la app |
| `modelos.py` | `Sesion`, `Pasajero` (observación) y `Encuesta`; tipos de proceso y etapas |
| `almacenamiento.py` | Guardado JSON, exportación CSV y envío a Google Sheets |
| `build_apk.sh` | Compila el APK firmado desde el commit actual |
| `assets/` | Ícono y logo |

## Desarrollo

Requiere Python 3.12 o superior.

```bash
python3 -m venv ~/.venvs/timer_aeropuerto
~/.venvs/timer_aeropuerto/bin/pip install "flet[all]==0.85.3"
~/.venvs/timer_aeropuerto/bin/flet run main.py
```

En el escritorio los datos se guardan en `~/tiempos_aeropuerto`.

## Compilar el APK

```bash
./build_apk.sh
```

El script:

- Se niega a compilar si hay cambios sin commitear: cada APK corresponde a un commit exacto.
- Compila desde una copia limpia del commit (`git archive`), así el APK nunca incluye `.git`
  ni archivos locales.
- Agrega `build_info.txt` con versión, commit y fecha. La app muestra la versión en el pie
  de la pantalla de inicio, por ejemplo `v1.1.0 (abc1234)`.

La primera vez, Flet descarga Flutter, el JDK y el Android SDK (unos 20–40 minutos).

**Antes de cada versión nueva**, sube en `pyproject.toml`:

- `[project] version`: la versión visible (`1.1.0` → `1.2.0`).
- `[tool.flet] build_number`: el `versionCode` de Android. Tiene que aumentar siempre.

No cambies `[project] name`: define el paquete Android (`cl.indata.timer_aeropuerto_app`).
Si cambia, el APK se instala como otra app.

### Firma

El APK se firma con una clave que **no está en este repo** y nunca debe subirse. Por
defecto el script la busca en `~/In-data/timer_aeropuerto_firma/`; otra ruta se indica con
`FIRMA_DIR`. Esa carpeta contiene:

- `timer_aeropuerto_release.jks` (alias `upload`)
- `password.txt`

Para que una versión nueva se instale encima de la anterior sin perder datos, tiene que
firmarse **con la misma clave**. Si la clave se pierde, hay que desinstalar la app en cada
teléfono, y eso borra las sesiones guardadas. Mantén un respaldo fuera del PC.

### Instalar en un teléfono

Con la depuración USB activada:

```bash
adb install -r timer_aeropuerto_v1.1.0_<commit>.apk
```

## Historial de versiones

### 1.1.0

- **Duplicados en Google Sheets.** Los `obs_id` eran 6 caracteres hexadecimales; cuando
  parecían números (`372654`, `94E099`), Sheets los convertía y el control de duplicados
  dejaba de reconocerlos. Ahora los IDs tienen prefijo y 12 caracteres (`OBS-109E7767E10C`)
  y no pueden confundirse con números. El riesgo de que dos observaciones reciban el mismo
  ID baja de 3% a prácticamente cero.
- **Reintento de envío.** Si el envío a Sheets falla, la sesión queda pendiente y se
  reintenta desde la pantalla de inicio. Antes los datos quedaban atrapados en el teléfono.
  Cada envío además reintenta solo los errores de red.
- **La app ya no se congela** mientras envía los datos.
- **Doble toque.** Ya no registra dos etapas en "REGISTRAR", no envía dos veces al
  finalizar y no guarda dos veces la misma encuesta.
- **Copia visible de los datos** en `Documents/TimerAeropuerto`.
- **Sesiones que cruzan la medianoche** se retoman al reabrir la app.
- **Encuestas:** cambiar ES/EN ya no borra las respuestas marcadas, y el botón de idioma
  muestra su texto correctamente.
- **Mensajes de error claros** cuando el servidor rechaza un envío.
- **Versión visible** en el pie de la pantalla de inicio.
- **Nueva clave de firma:** para instalar 1.1.0 hay que desinstalar antes la 1.0.0.
  Antes de desinstalar, finaliza y envía todas las sesiones del teléfono.

### 1.0.0

Versión inicial: módulos de tiempos y encuestas, retomar sesión activa, modo oscuro,
exportación CSV y envío a Google Sheets.
