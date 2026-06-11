"""
Persistencia local (JSON) y exportación a CSV.
En Android guarda en /storage/emulated/0/Android/data/<pkg>/files/tiempos_aeropuerto
(visible en explorador de archivos, sin necesidad de permisos en Android 10+).
En Windows/Mac guarda en ~/tiempos_aeropuerto.
"""

import json
import csv
import os
import re as _re
from datetime import datetime
from pathlib import Path
from modelos import Sesion, Pasajero, TIPOS

# En Android el app corre en /data/user/0/<pkg>/ o /data/data/<pkg>/
# Usamos la carpeta interna del app (files/) que siempre es escribible.
# En Windows/Mac usamos ~/tiempos_aeropuerto.
_android_match = _re.search(r'^(/data/(?:user/\d+|data)/[^/]+)', str(Path(__file__)))
if _android_match:
    CARPETA_DATOS = Path(_android_match.group(1)) / "files" / "tiempos_aeropuerto"
else:
    CARPETA_DATOS = Path.home() / "tiempos_aeropuerto"
CARPETA_DATOS.mkdir(parents=True, exist_ok=True)


def ruta_sesion(sesion_id: str) -> Path:
    return CARPETA_DATOS / f"sesion_{sesion_id}.json"


def guardar(sesion: Sesion):
    """Guarda la sesión completa como JSON (sobreescribe si existe)."""
    with open(ruta_sesion(sesion.id), "w", encoding="utf-8") as f:
        json.dump(sesion.to_dict(), f, ensure_ascii=False, indent=2)


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
            sesiones.append({
                "id": d["id"],
                "aeropuerto": d["aeropuerto"],
                "encuestador": d["encuestador"],
                "fecha": d["fecha"],
                "total": len(d["pasajeros"]),
                "completados": sum(1 for p in d["pasajeros"] if p["estado"] == "completado"),
            })
        except Exception:
            pass
    return sorted(sesiones, key=lambda s: s["fecha"], reverse=True)


# ---------------------------------------------------------------------------
# Exportación a CSV y Google Sheets
# ---------------------------------------------------------------------------

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
    elif p.tipo == "internacional":
        fila["intl_poli_llegada_fila"]    = _hms(_segundos(ts.get("inicio_fila_poli_llegada",""), ts.get("inicio_atencion_poli_llegada","")))
        fila["intl_poli_llegada_proceso"] = _hms(_segundos(ts.get("inicio_atencion_poli_llegada",""), ts.get("fin_poli_llegada","")))
        fila["intl_sag_fila"]             = _hms(_segundos(ts.get("inicio_fila_sag",""), ts.get("inicio_atencion_sag","")))
        fila["intl_sag_proceso"]          = _hms(_segundos(ts.get("inicio_atencion_sag",""), ts.get("fin_sag","")))
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
    return ruta


_GAS_URL = "https://script.google.com/macros/s/AKfycby0J5Fe9HLlDfjjKhiKqcTgmDeRvUZ2dJLIhNCwljoIdrLYtQCza3SYF8JweYbN9l8c/exec"


def sincronizar_sheets(sesion: Sesion) -> int:
    """
    Envía las observaciones completadas al Google Apps Script que las escribe en Sheets.
    Usa urllib (stdlib) para evitar dependencias nativas en Android.
    Retorna el número de filas nuevas añadidas según responde el script.
    """
    import urllib.request

    filas = [
        [str(_construir_fila(sesion, p).get(col, "")) for col in COLUMNAS]
        for p in sesion.completados()
    ]
    if not filas:
        return 0

    payload = json.dumps({"columnas": COLUMNAS, "filas": filas}).encode("utf-8")
    req = urllib.request.Request(
        _GAS_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        n = int(resp.read().decode("utf-8").strip())
    return n
