"""
Persistencia local (JSON) y exportación a CSV.
Los archivos se guardan en ~/tiempos_aeropuerto/ para que sean accesibles
en la tablet sin instalar nada extra.
"""

import json
import csv
import os
from datetime import datetime
from pathlib import Path
from modelos import Sesion, Pasajero, TIPOS

# Carpeta base de datos
CARPETA_DATOS = Path.home() / "tiempos_aeropuerto"
CARPETA_DATOS.mkdir(exist_ok=True)


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
# Exportación a CSV
# ---------------------------------------------------------------------------

def _segundos(t1_iso: str, t2_iso: str) -> float | None:
    """Diferencia en segundos entre dos timestamps ISO."""
    try:
        t1 = datetime.fromisoformat(t1_iso)
        t2 = datetime.fromisoformat(t2_iso)
        return (t2 - t1).total_seconds()
    except Exception:
        return None


def _hms(segundos: float | None) -> str:
    """Formatea segundos como HH:MM:SS para compatibilidad con Excel."""
    if segundos is None:
        return ""
    h, rem = divmod(int(segundos), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def exportar_csv(sesion: Sesion) -> Path:
    """
    Genera un CSV con una fila por pasajero completado.
    Las duraciones se calculan como diferencias de timestamps.
    Retorna la ruta del archivo generado.
    """
    aeropuerto_codigo = sesion.aeropuerto.split(" - ")[0]
    nombre_archivo = f"tiempos_{aeropuerto_codigo}_{sesion.fecha}_{sesion.id}.csv"
    ruta = CARPETA_DATOS / nombre_archivo

    # Columnas del CSV (compatibles con la estructura del Excel original)
    columnas = [
        "sesion_id", "fecha", "aeropuerto", "encuestador",
        "obs_id", "numero", "tipo", "linea_aerea", "vuelo",
        # Counter
        "counter_fila", "counter_proceso",
        # Autochequeo
        "auto_fila", "auto_proceso",
        # AVSEC
        "avsec_fila", "avsec_proceso",
        # Equipaje llegada
        "equipaje_primera_maleta", "equipaje_ultima_maleta",
        "equipaje_origen", "equipaje_cinta", "equipaje_carros",
        # Internacional
        "intl_poli_llegada_fila", "intl_poli_llegada_proceso",
        "intl_sag_fila", "intl_sag_proceso",
        "intl_poli_salida_fila", "intl_poli_salida_proceso",
        # Datos extra por pasajero
        "modulos_servicio", "equipaje_bodega", "personas",
    ]

    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()

        for p in sesion.completados():
            ts = p.timestamps
            fila: dict = {
                "sesion_id":    sesion.id,
                "fecha":        sesion.fecha,
                "aeropuerto":   sesion.aeropuerto,
                "encuestador":  sesion.encuestador,
                "obs_id":       p.id,
                "numero":       p.numero,
                "tipo":         TIPOS[p.tipo][0],
                "linea_aerea":  p.linea,
                "vuelo":        p.vuelo,
                # Datos extra
                "modulos_servicio": p.extra.get("modulos", ""),
                "equipaje_bodega":  p.extra.get("equipaje_bodega", ""),
                "personas":         p.extra.get("personas", ""),
                # Equipaje llegada
                "equipaje_origen":  p.extra.get("origen", ""),
                "equipaje_cinta":   p.extra.get("cinta", ""),
                "equipaje_carros":  p.extra.get("carros", ""),
            }

            if p.tipo == "counter":
                fila["counter_fila"]    = _hms(_segundos(ts.get("inicio_fila_counter",""), ts.get("inicio_atencion_counter","")))
                fila["counter_proceso"] = _hms(_segundos(ts.get("inicio_atencion_counter",""), ts.get("fin_counter","")))
                fila["avsec_fila"]      = _hms(_segundos(ts.get("inicio_fila_avsec",""), ts.get("inicio_atencion_avsec","")))
                fila["avsec_proceso"]   = _hms(_segundos(ts.get("inicio_atencion_avsec",""), ts.get("fin_avsec","")))

            elif p.tipo == "autochequeo":
                fila["auto_fila"]       = _hms(_segundos(ts.get("inicio_fila_auto",""), ts.get("inicio_uso_auto","")))
                fila["auto_proceso"]    = _hms(_segundos(ts.get("inicio_uso_auto",""), ts.get("fin_auto","")))
                fila["avsec_fila"]      = _hms(_segundos(ts.get("inicio_fila_avsec",""), ts.get("inicio_atencion_avsec","")))
                fila["avsec_proceso"]   = _hms(_segundos(ts.get("inicio_atencion_avsec",""), ts.get("fin_avsec","")))

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

            writer.writerow(fila)

    return ruta
