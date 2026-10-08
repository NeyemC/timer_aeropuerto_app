"""
Persistencia local (JSON) y exportación a CSV / Google Sheets.
En Android guarda en el almacenamiento interno de la app
(/data/user/0/<pkg>/files/tiempos_aeropuerto), que no es accesible desde fuera,
y deja una copia de cada JSON/CSV en Documents/TimerAeropuerto (visible en el
explorador de archivos y por USB).
En Windows/Mac/Linux guarda en ~/tiempos_aeropuerto.
"""

import json
import csv
import os
import re as _re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from modelos import Sesion, Pasajero, TIPOS, PREGUNTAS_ES

# En Android el app corre en /data/user/0/<pkg>/ o /data/data/<pkg>/
# Usamos la carpeta interna del app (files/) que siempre es escribible.
_android_match = _re.search(r'^(/data/(?:user/\d+|data)/[^/]+)', str(Path(__file__)))
if _android_match:
    CARPETA_DATOS = Path(_android_match.group(1)) / "files" / "tiempos_aeropuerto"
    CARPETA_PUBLICA: Path | None = Path("/storage/emulated/0/Documents/TimerAeropuerto")
else:
    CARPETA_DATOS = Path.home() / "tiempos_aeropuerto"
    CARPETA_PUBLICA = None
CARPETA_DATOS.mkdir(parents=True, exist_ok=True)


def _copia_publica(ruta: Path):
    """Copia el archivo a la carpeta pública. Si falla (permisos, sin almacenamiento),
    se ignora: la copia interna es la que cuenta."""
    if CARPETA_PUBLICA is None:
        return
    try:
        CARPETA_PUBLICA.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ruta, CARPETA_PUBLICA / ruta.name)
    except Exception:
        pass


def ruta_sesion(sesion_id: str) -> Path:
    return CARPETA_DATOS / f"sesion_{sesion_id}.json"


def guardar(sesion: Sesion):
    """Guarda la sesión completa como JSON (sobreescribe si existe)."""
    ruta = ruta_sesion(sesion.id)
    tmp = ruta.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sesion.to_dict(), f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)   # atómico: un cierre inesperado no deja el JSON a medias
    _copia_publica(ruta)


def cargar(sesion_id: str) -> Sesion | None:
    ruta = ruta_sesion(sesion_id)
    if not ruta.exists():
        return None
    with open(ruta, encoding="utf-8") as f:
        return Sesion.from_dict(json.load(f))


def listar_sesiones() -> list[dict]:
    """Retorna lista de metadatos de sesiones guardadas, ordenadas por fecha desc."""
    sesiones = []
    for archivo in CARPETA_DATOS.glob("sesion_*.json"):
        try:
            with open(archivo, encoding="utf-8") as f:
                d = json.load(f)
            finalizada = d.get("finalizada", False)
            sesiones.append({
                "id": d["id"],
                "aeropuerto": d["aeropuerto"],
                "encuestador": d["encuestador"],
                "fecha": d["fecha"],
                "total": len(d["pasajeros"]),
                "completados": sum(1 for p in d["pasajeros"] if p["estado"] == "completado"),
                "finalizada": finalizada,
                "sincronizada": d.get("sincronizada", finalizada),
            })
        except Exception:
            pass
    return sorted(sesiones, key=lambda s: s["fecha"], reverse=True)


def obtener_sesion_activa() -> Sesion | None:
    """Retorna la sesión no finalizada más reciente de hoy o de ayer
    (una jornada puede cruzar la medianoche), o None."""
    hoy = datetime.now().date()
    fechas_validas = {hoy.isoformat(), (hoy - timedelta(days=1)).isoformat()}
    for meta in listar_sesiones():
        if meta["fecha"] in fechas_validas and not meta["finalizada"]:
            return cargar(meta["id"])
    return None


def sesiones_pendientes() -> list[Sesion]:
    """Sesiones finalizadas cuyo envío a Google Sheets no se pudo confirmar."""
    pendientes = []
    for meta in listar_sesiones():
        if meta["finalizada"] and not meta["sincronizada"]:
            s = cargar(meta["id"])
            if s:
                pendientes.append(s)
    return pendientes


# ---------------------------------------------------------------------------
# Exportación a CSV y Google Sheets
# ---------------------------------------------------------------------------

_GAS_URL = "https://script.google.com/macros/s/AKfycbxq__snenjRmu1gFyZQl3o79MPx9YHcB7vcxE76MlBSI51XWD2IRoSVRhCOaWYGHoI/exec"

COLUMNAS = [
    "sesion_id", "fecha", "aeropuerto", "encuestador",
    "obs_id", "numero", "tipo", "linea_aerea", "vuelo",
    "counter_fila", "counter_proceso",
    "auto_fila", "auto_proceso",
    "avsec_fila", "avsec_proceso",
    "equipaje_primera_maleta", "equipaje_ultima_maleta",
    "equipaje_origen", "equipaje_cinta", "equipaje_carros",
    "intl_poli_llegada_fila", "intl_poli_llegada_proceso",
    "intl_sag_fila", "intl_sag_proceso",
    "intl_poli_salida_fila", "intl_poli_salida_proceso",
    "modulos_servicio", "equipaje_bodega", "personas",
]


def _segundos(t1_iso: str, t2_iso: str) -> float | None:
    try:
        t1 = datetime.fromisoformat(t1_iso)
        t2 = datetime.fromisoformat(t2_iso)
        return (t2 - t1).total_seconds()
    except Exception:
        return None


def _hms(segundos: float | None) -> str:
    if segundos is None:
        return ""
    h, rem = divmod(int(segundos), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _construir_fila(sesion: Sesion, p: Pasajero) -> dict:
    ts = p.timestamps
    fila: dict = {
        "sesion_id":        sesion.id,
        "fecha":            sesion.fecha,
        "aeropuerto":       sesion.aeropuerto,
        "encuestador":      sesion.encuestador,
        "obs_id":           p.id,
        "numero":           p.numero,
        "tipo":             TIPOS[p.tipo][0],
        "linea_aerea":      p.linea,
        "vuelo":            p.vuelo,
        "modulos_servicio": p.extra.get("modulos", ""),
        "equipaje_bodega":  p.extra.get("equipaje_bodega", ""),
        "personas":         p.extra.get("personas", ""),
        "equipaje_origen":  p.extra.get("origen", ""),
        "equipaje_cinta":   p.extra.get("cinta", ""),
        "equipaje_carros":  p.extra.get("carros", ""),
    }
    if p.tipo == "counter":
        fila["counter_fila"]    = _hms(_segundos(ts.get("inicio_fila_counter",""), ts.get("inicio_atencion_counter","")))
        fila["counter_proceso"] = _hms(_segundos(ts.get("inicio_atencion_counter",""), ts.get("fin_counter","")))
    elif p.tipo == "autochequeo":
        fila["auto_fila"]    = _hms(_segundos(ts.get("inicio_fila_auto",""), ts.get("inicio_uso_auto","")))
        fila["auto_proceso"] = _hms(_segundos(ts.get("inicio_uso_auto",""), ts.get("fin_auto","")))
    elif p.tipo == "avsec":
        fila["avsec_fila"]    = _hms(_segundos(ts.get("inicio_fila_avsec",""), ts.get("inicio_atencion_avsec","")))
        fila["avsec_proceso"] = _hms(_segundos(ts.get("inicio_atencion_avsec",""), ts.get("fin_avsec","")))
    elif p.tipo == "equipaje":
        fila["equipaje_primera_maleta"] = _hms(_segundos(ts.get("aterrizaje",""), ts.get("primera_maleta","")))
        fila["equipaje_ultima_maleta"]  = _hms(_segundos(ts.get("aterrizaje",""), ts.get("ultima_maleta","")))
    elif p.tipo == "poli_llegada":
        fila["intl_poli_llegada_fila"]    = _hms(_segundos(ts.get("inicio_fila_poli_llegada",""), ts.get("inicio_atencion_poli_llegada","")))
        fila["intl_poli_llegada_proceso"] = _hms(_segundos(ts.get("inicio_atencion_poli_llegada",""), ts.get("fin_poli_llegada","")))
    elif p.tipo == "sag":
        fila["intl_sag_fila"]             = _hms(_segundos(ts.get("inicio_fila_sag",""), ts.get("inicio_atencion_sag","")))
        fila["intl_sag_proceso"]          = _hms(_segundos(ts.get("inicio_atencion_sag",""), ts.get("fin_sag","")))
    elif p.tipo == "poli_salida":
        fila["intl_poli_salida_fila"]     = _hms(_segundos(ts.get("inicio_fila_poli_salida",""), ts.get("inicio_atencion_poli_salida","")))
        fila["intl_poli_salida_proceso"]  = _hms(_segundos(ts.get("inicio_atencion_poli_salida",""), ts.get("fin_poli_salida","")))
    return fila


def exportar_csv(sesion: Sesion) -> Path:
    aeropuerto_codigo = sesion.aeropuerto.split(" - ")[0]
    nombre_archivo = f"tiempos_{aeropuerto_codigo}_{sesion.fecha}_{sesion.id}.csv"
    ruta = CARPETA_DATOS / nombre_archivo
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS)
        writer.writeheader()
        for p in sesion.completados():
            writer.writerow(_construir_fila(sesion, p))
    _copia_publica(ruta)
    return ruta


def _enviar(payload: dict, intentos: int = 3) -> int:
    """
    POST al Google Apps Script que escribe en Sheets. Usa urllib (stdlib) para evitar
    dependencias nativas en Android. Reintenta errores de red: el script descarta
    filas ya existentes, así que reenviar es seguro.
    Retorna el número de filas nuevas añadidas según responde el script.
    """
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    ultimo_error: Exception | None = None
    for intento in range(intentos):
        if intento:
            time.sleep(2 * intento)
        try:
            req = urllib.request.Request(
                _GAS_URL, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                texto = resp.read().decode("utf-8").strip()
        except Exception as ex:
            ultimo_error = ex
            continue
        if texto.isdigit():
            return int(texto)
        # El script respondió, pero con un error: reintentar no lo arregla
        raise RuntimeError(texto if texto.startswith("ERROR") else
                           f"Respuesta inesperada del servidor: {texto[:120]}")
    raise RuntimeError(f"Sin conexión con Google Sheets ({ultimo_error})")


def sincronizar_sheets(sesion: Sesion) -> int:
    """Envía las observaciones completadas. Retorna filas nuevas añadidas."""
    filas = [
        [str(_construir_fila(sesion, p).get(col, "")) for col in COLUMNAS]
        for p in sesion.completados()
    ]
    if not filas:
        return 0
    return _enviar({"columnas": COLUMNAS, "filas": filas})


def sincronizar(sesion: Sesion) -> int:
    """Envía la sesión según su módulo y, si el servidor confirma, la marca como
    sincronizada. Lanza excepción si no se pudo enviar."""
    if sesion.modulo == "encuestas":
        n = sincronizar_sheets_encuestas(sesion)
    else:
        n = sincronizar_sheets(sesion)
    sesion.sincronizada = True
    guardar(sesion)
    return n


# ---------------------------------------------------------------------------
# Módulo B — Encuestas de satisfacción
# ---------------------------------------------------------------------------

COLUMNAS_ENCUESTA = [
    "sesion_id", "fecha", "aeropuerto", "encuestador", "numero",
    "estacionamiento_disp", "estacionamiento_precio",
    "bancos_cajeros", "aseo",
]


def _filas_encuestas(sesion: Sesion) -> list[dict]:
    filas = []
    for e in sesion.encuestas:
        if not e.completa():
            continue
        fila = {
            "sesion_id":   sesion.id,
            "fecha":       sesion.fecha,
            "aeropuerto":  sesion.aeropuerto,
            "encuestador": sesion.encuestador,
            "numero":      e.numero,
        }
        for clave, _ in PREGUNTAS_ES:
            v = e.respuestas.get(clave)
            fila[clave] = "" if v is None else v
        filas.append(fila)
    return filas


def exportar_csv_encuestas(sesion: Sesion) -> Path:
    aeropuerto_codigo = sesion.aeropuerto.split(" - ")[0]
    nombre_archivo = f"encuestas_{aeropuerto_codigo}_{sesion.fecha}_{sesion.id}.csv"
    ruta = CARPETA_DATOS / nombre_archivo
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS_ENCUESTA)
        writer.writeheader()
        for fila in _filas_encuestas(sesion):
            writer.writerow(fila)
    _copia_publica(ruta)
    return ruta


def sincronizar_sheets_encuestas(sesion: Sesion) -> int:
    filas = [
        [str(fila.get(col, "")) for col in COLUMNAS_ENCUESTA]
        for fila in _filas_encuestas(sesion)
    ]
    if not filas:
        return 0
    return _enviar({
        "hoja": "encuestas",
        "columnas": COLUMNAS_ENCUESTA,
        "filas": filas,
    })
