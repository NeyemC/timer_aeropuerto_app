"""
Modelos de datos para la app de tiempos de proceso aeroportuarios.
Cada pasajero tiene un tipo que determina sus etapas secuenciales.
Al registrar cada evento se guarda el timestamp absoluto; las duraciones
se calculan al exportar.
"""

from datetime import datetime
import uuid

# ---------------------------------------------------------------------------
# Configuración de etapas por tipo de observación
# Cada etapa es (clave_interna, texto_para_encuestador)
# ---------------------------------------------------------------------------

ETAPAS_COUNTER = [
    ("inicio_fila_counter",      "Inicio Fila Counter"),
    ("inicio_atencion_counter",  "Inicio Atención Counter"),
    ("fin_counter",              "Fin Counter"),
]

ETAPAS_AUTOCHEQUEO = [
    ("inicio_fila_auto",         "Inicio Fila Autochequeo"),
    ("inicio_uso_auto",          "Inicio Uso Kiosko"),
    ("fin_auto",                 "Fin Autochequeo"),
]

ETAPAS_AVSEC = [
    ("inicio_fila_avsec",        "Inicio Fila AVSEC"),
    ("inicio_atencion_avsec",    "Inicio Atención AVSEC"),
    ("fin_avsec",                "Fin AVSEC"),
]

ETAPAS_EQUIPAJE = [
    ("aterrizaje",               "Aterrizaje del Vuelo"),
    ("primera_maleta",           "1ª Maleta en Cinta"),
    ("ultima_maleta",            "Última Maleta en Cinta"),
]

ETAPAS_POLI_LLEGADA = [
    ("inicio_fila_poli_llegada",     "Inicio Fila Policía Internacional Llegadas"),
    ("inicio_atencion_poli_llegada", "Inicio Atención Policía Internacional Llegadas"),
    ("fin_poli_llegada",             "Fin Policía Internacional Llegadas"),
]

ETAPAS_SAG = [
    ("inicio_fila_sag",              "Inicio Fila SAG / Aduana"),
    ("inicio_atencion_sag",          "Inicio Atención SAG / Aduana"),
    ("fin_sag",                      "Fin SAG / Aduana"),
]

ETAPAS_POLI_SALIDA = [
    ("inicio_fila_poli_salida",      "Inicio Fila Policía Internacional Salidas"),
    ("inicio_atencion_poli_salida",  "Inicio Atención Policía Internacional Salidas"),
    ("fin_poli_salida",              "Fin Policía Internacional Salidas"),
]

TIPOS = {
    "counter":       ("Counter",                        ETAPAS_COUNTER),
    "autochequeo":   ("Autochequeo",                   ETAPAS_AUTOCHEQUEO),
    "avsec":         ("AVSEC",                          ETAPAS_AVSEC),
    "equipaje":      ("Equipaje Llegada",               ETAPAS_EQUIPAJE),
    "poli_llegada":  ("Policía Int. Llegadas",          ETAPAS_POLI_LLEGADA),
    "sag":           ("SAG / Aduana",                   ETAPAS_SAG),
    "poli_salida":   ("Policía Int. Salidas",           ETAPAS_POLI_SALIDA),
}

LINEAS_AEREAS = ["LATAM", "Sky Airline", "JetSmart", "DAP"]

AEROPUERTOS = [
    "ANF - Antofagasta",
    "ARI - Arica",
    "BBA - Balmaceda",
    "CPO - Copiapó",
    "LSC - La Serena",
    "PUQ - Punta Arenas",
]


# ---------------------------------------------------------------------------
# Clase Pasajero
# ---------------------------------------------------------------------------

class Pasajero:
    """
    Representa una observación en curso (un pasajero o un vuelo de llegada).
    estado: 'activo' | 'completado' | 'cancelado'
    """

    def __init__(self, tipo: str, linea: str, vuelo: str, numero: int, extra: dict | None = None):
        self.id = str(uuid.uuid4())[:6].upper()
        self.tipo = tipo
        self.linea = linea
        self.vuelo = vuelo
        self.numero = numero          # número correlativo en la sesión
        self.extra = extra or {}      # datos adicionales (módulos, personas, etc.)
        self.etapas = TIPOS[tipo][1]
        self.etapa_idx = 0            # índice de la próxima etapa a registrar
        self.timestamps: dict[str, str] = {}   # clave → ISO datetime
        self.estado = "activo"
        self.creado_en = datetime.now().isoformat()

    # --- Consulta --------------------------------------------------------

    def etapa_pendiente(self) -> tuple[str, str] | None:
        """Retorna la etapa que se va a registrar al próximo tap, o None si terminó."""
        if self.etapa_idx < len(self.etapas):
            return self.etapas[self.etapa_idx]
        return None

    def progreso(self) -> str:
        """Ej: '3 / 6'"""
        return f"{self.etapa_idx} / {len(self.etapas)}"

    def tiempo_en_etapa_actual(self) -> str:
        """Tiempo transcurrido desde el último evento registrado (MM:SS).
        Devuelve '--:--' antes del primer evento."""
        if self.etapa_idx == 0:
            return "--:--"
        ultima_clave = self.etapas[self.etapa_idx - 1][0]
        if ultima_clave not in self.timestamps:
            return "--:--"
        prev = datetime.fromisoformat(self.timestamps[ultima_clave])
        delta = datetime.now() - prev
        minutos, segs = divmod(int(delta.total_seconds()), 60)
        return f"{minutos:02d}:{segs:02d}"

    # --- Mutación --------------------------------------------------------

    def registrar_evento(self) -> bool:
        """Registra timestamp para la etapa actual y avanza. Retorna True si completó."""
        if self.etapa_idx >= len(self.etapas):
            return False
        clave = self.etapas[self.etapa_idx][0]
        self.timestamps[clave] = datetime.now().isoformat()
        self.etapa_idx += 1
        if self.etapa_idx >= len(self.etapas):
            self.estado = "completado"
            return True
        return False

    def cancelar(self):
        self.estado = "cancelado"

    # --- Serialización ---------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "linea": self.linea,
            "vuelo": self.vuelo,
            "numero": self.numero,
            "extra": self.extra,
            "etapa_idx": self.etapa_idx,
            "timestamps": self.timestamps,
            "estado": self.estado,
            "creado_en": self.creado_en,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pasajero":
        p = cls(d["tipo"], d["linea"], d["vuelo"], d["numero"], d.get("extra", {}))
        p.id = d["id"]
        p.etapa_idx = d["etapa_idx"]
        p.timestamps = d["timestamps"]
        p.estado = d["estado"]
        p.creado_en = d["creado_en"]
        return p


# ---------------------------------------------------------------------------
# Clase Sesión
# ---------------------------------------------------------------------------

class Sesion:
    """
    Agrupa todas las observaciones de una jornada de trabajo.
    """

    def __init__(self, aeropuerto: str, encuestador: str, fecha: str | None = None):
        self.id = str(uuid.uuid4())[:8].upper()
        self.aeropuerto = aeropuerto
        self.encuestador = encuestador
        self.fecha = fecha or datetime.now().strftime("%Y-%m-%d")
        self.pasajeros: list[Pasajero] = []
        self._contador = 0

    def agregar_pasajero(self, tipo: str, linea: str, vuelo: str, extra: dict | None = None) -> Pasajero:
        self._contador += 1
        p = Pasajero(tipo, linea, vuelo, self._contador, extra)
        self.pasajeros.append(p)
        return p

    def activos(self) -> list[Pasajero]:
        return [p for p in self.pasajeros if p.estado == "activo"]

    def completados(self) -> list[Pasajero]:
        return [p for p in self.pasajeros if p.estado == "completado"]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "aeropuerto": self.aeropuerto,
            "encuestador": self.encuestador,
            "fecha": self.fecha,
            "contador": self._contador,
            "pasajeros": [p.to_dict() for p in self.pasajeros],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Sesion":
        s = cls(d["aeropuerto"], d["encuestador"], d["fecha"])
        s.id = d["id"]
        s._contador = d["contador"]
        s.pasajeros = [Pasajero.from_dict(p) for p in d["pasajeros"]]
        return s
