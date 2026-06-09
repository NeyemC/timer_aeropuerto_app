"""
App de Tiempos de Proceso Aeroportuarios
=========================================
Uso: python main.py
Compilar a APK: flet build apk (requiere Android SDK)

Flujo principal:
  1. Pantalla de configuración de sesión (aeropuerto, encuestador)
  2. Pantalla principal con tarjetas de pasajeros activos
  3. Diálogo "Nuevo pasajero" → seleccionar tipo + datos básicos
  4. Diálogo "Completar" → ingresar datos extra al terminar etapas
  5. Exportar CSV al terminar la jornada
"""

import flet as ft
from datetime import datetime
import threading
import time as time_module

from modelos import (
    Sesion, Pasajero,
    TIPOS, LINEAS_AEREAS, AEROPUERTOS,
)
from almacenamiento import guardar, exportar_csv

# ---------------------------------------------------------------------------
# Paleta de colores por tipo de observación
# ---------------------------------------------------------------------------
COLOR_TIPO = {
    "counter":       ft.Colors.BLUE_700,
    "autochequeo":   ft.Colors.GREEN_700,
    "equipaje":      ft.Colors.ORANGE_700,
    "internacional": ft.Colors.PURPLE_700,
}

COLOR_TIPO_SUAVE = {
    "counter":       ft.Colors.BLUE_50,
    "autochequeo":   ft.Colors.GREEN_50,
    "equipaje":      ft.Colors.ORANGE_50,
    "internacional": ft.Colors.PURPLE_50,
}


# ===========================================================================
# Función principal de la app
# ===========================================================================

def main(page: ft.Page):
    page.title = "Tiempos de Proceso – Aeropuerto"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = ft.Colors.GREY_100

    # Estado de la sesión activa
    sesion: list[Sesion | None] = [None]   # lista de 1 elemento para mutarlo en closures

    # -----------------------------------------------------------------------
    # PANTALLA 1: CONFIGURACIÓN DE SESIÓN
    # -----------------------------------------------------------------------

    def mostrar_setup():
        campo_encuestador = ft.TextField(
            label="Nombre del encuestador",
            hint_text="Ej: Juan Pérez",
            prefix_icon=ft.Icons.PERSON,
            autofocus=True,
            border_radius=12,
        )

        dd_aeropuerto = ft.Dropdown(
            label="Aeropuerto",
            options=[ft.dropdown.Option(a) for a in AEROPUERTOS],
            border_radius=12,
        )

        texto_error = ft.Text("", color=ft.Colors.RED_700, size=13)

        def iniciar_sesion(e):
            if not campo_encuestador.value or not dd_aeropuerto.value:
                texto_error.value = "Completa todos los campos para continuar."
                page.update()
                return
            sesion[0] = Sesion(
                aeropuerto=dd_aeropuerto.value,
                encuestador=campo_encuestador.value.strip(),
            )
            guardar(sesion[0])
            mostrar_principal()

        page.views.clear()
        page.views.append(
            ft.View(
                route="/setup",
                bgcolor=ft.Colors.WHITE,
                padding=0,
                controls=[
                    ft.Container(
                        expand=True,
                        alignment=ft.alignment.center,
                        padding=ft.padding.symmetric(horizontal=40, vertical=60),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=24,
                            controls=[
                                ft.Icon(ft.Icons.FLIGHT, size=72, color=ft.Colors.BLUE_700),
                                ft.Text(
                                    "Tiempos de Proceso\nAeroportuarios",
                                    size=28,
                                    weight=ft.FontWeight.BOLD,
                                    text_align=ft.TextAlign.CENTER,
                                    color=ft.Colors.BLUE_900,
                                ),
                                ft.Text(
                                    "Configura la sesión antes de comenzar",
                                    size=16,
                                    color=ft.Colors.GREY_600,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Divider(height=8),
                                dd_aeropuerto,
                                campo_encuestador,
                                texto_error,
                                ft.ElevatedButton(
                                    "Iniciar Jornada",
                                    icon=ft.Icons.PLAY_ARROW,
                                    on_click=iniciar_sesion,
                                    style=ft.ButtonStyle(
                                        padding=ft.padding.symmetric(horizontal=40, vertical=20),
                                        shape=ft.RoundedRectangleBorder(radius=12),
                                    ),
                                    bgcolor=ft.Colors.BLUE_700,
                                    color=ft.Colors.WHITE,
                                ),
                            ],
                        ),
                    )
                ],
            )
        )
        page.go("/setup")

    # -----------------------------------------------------------------------
    # PANTALLA 2: PRINCIPAL (lista de pasajeros activos)
    # -----------------------------------------------------------------------

    tarjetas_ref: dict[str, ft.Ref] = {}   # id_pasajero → refs para actualizar

    def mostrar_principal():
        s = sesion[0]

        # --- Encabezado ---
        encabezado = ft.Container(
            bgcolor=ft.Colors.BLUE_700,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(s.aeropuerto, color=ft.Colors.WHITE, size=13,
                                    weight=ft.FontWeight.W_500),
                            ft.Text(s.encuestador, color=ft.Colors.BLUE_100, size=12),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.DOWNLOAD,
                                icon_color=ft.Colors.WHITE,
                                tooltip="Exportar CSV",
                                on_click=lambda e: accion_exportar(),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.INFO_OUTLINE,
                                icon_color=ft.Colors.WHITE,
                                tooltip="Resumen de sesión",
                                on_click=lambda e: mostrar_resumen(),
                            ),
                        ],
                    ),
                ],
            ),
        )

        # --- Contenedor de tarjetas ---
        lista_tarjetas = ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        texto_vacio = ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Icon(ft.Icons.PERSON_SEARCH, size=64, color=ft.Colors.GREY_400),
                    ft.Text("Sin pasajeros activos",
                            size=20, color=ft.Colors.GREY_500,
                            weight=ft.FontWeight.W_500),
                    ft.Text("Toca + para agregar una nueva observación",
                            size=14, color=ft.Colors.GREY_400),
                ],
            ),
        )

        def reconstruir_lista():
            activos = s.activos()
            lista_tarjetas.controls.clear()
            if not activos:
                lista_tarjetas.controls.append(texto_vacio)
            else:
                for p in activos:
                    lista_tarjetas.controls.append(construir_tarjeta(p, reconstruir_lista))
            page.update()

        # --- FAB "+" ---
        fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            text="Nuevo",
            bgcolor=ft.Colors.BLUE_700,
            foreground_color=ft.Colors.WHITE,
            on_click=lambda e: mostrar_dialogo_nuevo(reconstruir_lista),
        )

        page.views.clear()
        page.views.append(
            ft.View(
                route="/principal",
                bgcolor=ft.Colors.GREY_100,
                padding=0,
                floating_action_button=fab,
                controls=[
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            encabezado,
                            ft.Container(
                                expand=True,
                                padding=ft.padding.all(12),
                                content=lista_tarjetas,
                            ),
                        ],
                    )
                ],
            )
        )
        page.go("/principal")
        reconstruir_lista()
        iniciar_timer_live(lista_tarjetas, s, reconstruir_lista)

    # -----------------------------------------------------------------------
    # TARJETA de pasajero activo
    # -----------------------------------------------------------------------

    def construir_tarjeta(p: Pasajero, on_change) -> ft.Container:
        s = sesion[0]
        color_principal = COLOR_TIPO[p.tipo]
        etapa = p.etapa_pendiente()
        if etapa is None:
            return ft.Container()

        _clave, texto_etapa = etapa
        tipo_label = TIPOS[p.tipo][0]
        total_etapas = len(p.etapas)

        # Identificador del pasajero
        titulo = ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    bgcolor=color_principal,
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    content=ft.Text(
                        f"#{p.numero}",
                        color=ft.Colors.WHITE,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                ),
                ft.Text(tipo_label, size=15, weight=ft.FontWeight.W_600,
                        color=color_principal),
                ft.Text("·", color=ft.Colors.GREY_400),
                ft.Text(p.linea, size=14, color=ft.Colors.GREY_700),
                ft.Text(p.vuelo, size=14, color=ft.Colors.GREY_500),
            ],
        )

        # Barra de progreso
        progreso_frac = p.etapa_idx / total_etapas
        barra_progreso = ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Progreso", size=12, color=ft.Colors.GREY_500),
                        ft.Text(p.progreso(), size=12, color=ft.Colors.GREY_500),
                    ],
                ),
                ft.ProgressBar(
                    value=progreso_frac,
                    bgcolor=ft.Colors.GREY_200,
                    color=color_principal,
                    height=6,
                    border_radius=3,
                ),
            ],
        )

        # Etapa actual y timer
        ref_timer = ft.Ref[ft.Text]()
        bloque_etapa = ft.Container(
            bgcolor=ft.Colors.GREY_50,
            border_radius=10,
            padding=ft.padding.all(14),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=2,
                        expand=True,
                        controls=[
                            ft.Text("Próximo evento a registrar:",
                                    size=12, color=ft.Colors.GREY_500),
                            ft.Text(
                                texto_etapa,
                                size=17,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.GREY_900,
                            ),
                        ],
                    ),
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        spacing=2,
                        controls=[
                            ft.Text("En esta etapa", size=11, color=ft.Colors.GREY_400),
                            ft.Text(
                                ref=ref_timer,
                                value=p.tiempo_en_etapa_actual(),
                                size=22,
                                weight=ft.FontWeight.BOLD,
                                color=color_principal,
                                font_family="monospace",
                            ),
                        ],
                    ),
                ],
            ),
        )

        # Guardar referencia del timer para actualización en vivo
        tarjetas_ref[p.id] = ref_timer

        # Botón principal de acción
        def on_registrar(e, pasajero=p):
            completado = pasajero.registrar_evento()
            guardar(s)
            if completado:
                del tarjetas_ref[pasajero.id]
                mostrar_dialogo_completar(pasajero, on_change)
            else:
                on_change()

        # Botón cancelar
        def on_cancelar(e, pasajero=p):
            def confirmar_cancelar(e2):
                pasajero.cancelar()
                guardar(s)
                if pasajero.id in tarjetas_ref:
                    del tarjetas_ref[pasajero.id]
                page.dialog.open = False
                on_change()
                page.update()

            page.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("¿Cancelar observación?"),
                content=ft.Text(f"Se perderán los datos del pasajero #{pasajero.numero}."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: cerrar_dialogo()),
                    ft.TextButton("Sí, descartar",
                                  style=ft.ButtonStyle(color=ft.Colors.RED_700),
                                  on_click=confirmar_cancelar),
                ],
            )
            page.dialog.open = True
            page.update()

        tarjeta = ft.Container(
            bgcolor=ft.Colors.WHITE,
            border_radius=16,
            padding=ft.padding.all(16),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            border=ft.border.all(1, ft.Colors.GREY_200),
            content=ft.Column(
                spacing=14,
                controls=[
                    titulo,
                    barra_progreso,
                    bloque_etapa,
                    # Botón principal (grande, toda la anchura)
                    ft.ElevatedButton(
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=20),
                                ft.Text(
                                    f"REGISTRAR: {texto_etapa}",
                                    size=15,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.padding.symmetric(vertical=16),
                        ),
                        bgcolor=color_principal,
                        color=ft.Colors.WHITE,
                        on_click=on_registrar,
                        expand=True,
                    ),
                    # Botón cancelar (pequeño, discreto)
                    ft.TextButton(
                        "Descartar observación",
                        icon=ft.Icons.DELETE_OUTLINE,
                        style=ft.ButtonStyle(color=ft.Colors.RED_400),
                        on_click=on_cancelar,
                    ),
                ],
            ),
        )
        return tarjeta

    # -----------------------------------------------------------------------
    # DIÁLOGO: Nuevo pasajero
    # -----------------------------------------------------------------------

    def mostrar_dialogo_nuevo(on_change):
        tipo_sel: list[str] = ["counter"]

        dd_linea = ft.Dropdown(
            label="Línea aérea",
            options=[ft.dropdown.Option(l) for l in LINEAS_AEREAS],
            border_radius=10,
            value=LINEAS_AEREAS[0],
        )
        campo_vuelo = ft.TextField(
            label="N° de vuelo (opcional)",
            hint_text="Ej: LA-450",
            border_radius=10,
        )

        def chip_tipo(tipo_key, label, icono):
            sel = tipo_sel[0] == tipo_key

            def on_select(e, tk=tipo_key):
                tipo_sel[0] = tk
                # Reconstruir chips
                actualizar_chips()

            return ft.Container(
                on_click=on_select,
                bgcolor=COLOR_TIPO[tipo_key] if tipo_sel[0] == tipo_key else ft.Colors.GREY_100,
                border_radius=10,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                border=ft.border.all(2, COLOR_TIPO[tipo_key] if tipo_sel[0] == tipo_key else ft.Colors.GREY_300),
                content=ft.Row(
                    spacing=6,
                    controls=[
                        ft.Icon(icono, size=18,
                                color=ft.Colors.WHITE if tipo_sel[0] == tipo_key else ft.Colors.GREY_600),
                        ft.Text(label, size=13, weight=ft.FontWeight.W_500,
                                color=ft.Colors.WHITE if tipo_sel[0] == tipo_key else ft.Colors.GREY_700),
                    ],
                ),
            )

        chips_row = ft.Ref[ft.Row]()

        def construir_chips():
            return [
                chip_tipo("counter", "Counter", ft.Icons.AIRLINE_SEAT_RECLINE_NORMAL),
                chip_tipo("autochequeo", "Autochequeo", ft.Icons.COMPUTER),
                chip_tipo("equipaje", "Equipaje", ft.Icons.LUGGAGE),
                chip_tipo("internacional", "Internacional", ft.Icons.PUBLIC),
            ]

        chips_container = ft.Row(wrap=True, spacing=8, run_spacing=8, controls=construir_chips())

        def actualizar_chips():
            chips_container.controls = construir_chips()
            page.update()

        def confirmar(e):
            if not dd_linea.value:
                return
            sesion[0].agregar_pasajero(
                tipo=tipo_sel[0],
                linea=dd_linea.value,
                vuelo=campo_vuelo.value.strip() or "-",
            )
            guardar(sesion[0])
            page.dialog.open = False
            on_change()
            page.update()

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nueva Observación", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    tight=True,
                    spacing=16,
                    controls=[
                        ft.Text("Tipo de proceso:", size=13, weight=ft.FontWeight.W_500,
                                color=ft.Colors.GREY_700),
                        chips_container,
                        ft.Divider(),
                        dd_linea,
                        campo_vuelo,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: cerrar_dialogo()),
                ft.ElevatedButton(
                    "Iniciar",
                    icon=ft.Icons.PLAY_ARROW,
                    bgcolor=ft.Colors.BLUE_700,
                    color=ft.Colors.WHITE,
                    on_click=confirmar,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog.open = True
        page.update()

    # -----------------------------------------------------------------------
    # DIÁLOGO: Datos al completar una observación
    # -----------------------------------------------------------------------

    def mostrar_dialogo_completar(p: Pasajero, on_change):
        """Captura datos extra después de completar todas las etapas."""

        controles_extra = []

        if p.tipo in ("counter", "autochequeo"):
            campo_modulos = ft.TextField(
                label="Módulos en servicio",
                hint_text="Ej: 4",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=10,
            )
            campo_personas = ft.TextField(
                label="Personas en el grupo",
                hint_text="Ej: 2",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=10,
                value="1",
            )
            dd_equip = ft.Dropdown(
                label="Equipaje en bodega",
                options=[ft.dropdown.Option("Sí"), ft.dropdown.Option("No")],
                border_radius=10,
                value="Sí",
            )
            controles_extra = [campo_modulos, campo_personas, dd_equip]

        elif p.tipo == "equipaje":
            campo_origen = ft.TextField(
                label="Origen del vuelo",
                hint_text="Ej: Santiago",
                border_radius=10,
            )
            campo_cinta = ft.TextField(
                label="N° de cinta",
                hint_text="Ej: 1",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=10,
            )
            campo_carros = ft.TextField(
                label="Carros disponibles",
                hint_text="Ej: 30",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=10,
            )
            controles_extra = [campo_origen, campo_cinta, campo_carros]

        def guardar_y_cerrar(e):
            if p.tipo in ("counter", "autochequeo"):
                p.extra["modulos"]          = campo_modulos.value
                p.extra["personas"]         = campo_personas.value
                p.extra["equipaje_bodega"]  = dd_equip.value
            elif p.tipo == "equipaje":
                p.extra["origen"] = campo_origen.value
                p.extra["cinta"]  = campo_cinta.value
                p.extra["carros"] = campo_carros.value
            guardar(sesion[0])
            page.dialog.open = False
            on_change()
            page.update()

        tipo_label = TIPOS[p.tipo][0]
        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_600, size=24),
                    ft.Text(f"#{p.numero} Completado", weight=ft.FontWeight.BOLD),
                ],
            ),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    tight=True,
                    spacing=14,
                    controls=[
                        ft.Text(
                            f"Proceso: {tipo_label}  ·  {p.linea}  {p.vuelo}",
                            size=13,
                            color=ft.Colors.GREY_600,
                        ),
                        ft.Divider(),
                        *controles_extra,
                    ],
                ),
            ),
            actions=[
                ft.ElevatedButton(
                    "Guardar y cerrar",
                    icon=ft.Icons.SAVE,
                    bgcolor=ft.Colors.GREEN_700,
                    color=ft.Colors.WHITE,
                    on_click=guardar_y_cerrar,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog.open = True
        page.update()

    # -----------------------------------------------------------------------
    # DIÁLOGO: Resumen de sesión
    # -----------------------------------------------------------------------

    def mostrar_resumen():
        s = sesion[0]
        activos    = len(s.activos())
        completados = len(s.completados())
        total      = len(s.pasajeros)

        page.dialog = ft.AlertDialog(
            modal=False,
            title=ft.Text("Resumen de sesión"),
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=[
                    ft.Text(f"Aeropuerto:  {s.aeropuerto}", size=14),
                    ft.Text(f"Encuestador: {s.encuestador}", size=14),
                    ft.Text(f"Fecha:       {s.fecha}", size=14),
                    ft.Divider(),
                    ft.Text(f"Observaciones totales:     {total}", size=14),
                    ft.Text(f"En curso:                  {activos}", size=14, color=ft.Colors.ORANGE_700),
                    ft.Text(f"Completadas:               {completados}", size=14, color=ft.Colors.GREEN_700),
                ],
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo()),
            ],
        )
        page.dialog.open = True
        page.update()

    # -----------------------------------------------------------------------
    # ACCIÓN: Exportar CSV
    # -----------------------------------------------------------------------

    def accion_exportar():
        s = sesion[0]
        completados = len(s.completados())
        if completados == 0:
            page.snack_bar = ft.SnackBar(
                ft.Text("No hay observaciones completadas para exportar."),
                bgcolor=ft.Colors.ORANGE_700,
            )
            page.snack_bar.open = True
            page.update()
            return

        ruta = exportar_csv(s)
        page.snack_bar = ft.SnackBar(
            ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.WHITE),
                    ft.Text(f"CSV exportado: {ruta.name}", color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=ft.Colors.GREEN_700,
            duration=5000,
        )
        page.snack_bar.open = True
        page.update()

    # -----------------------------------------------------------------------
    # TIMER EN VIVO: actualiza los cronómetros cada segundo
    # -----------------------------------------------------------------------

    timer_activo = [True]

    def iniciar_timer_live(lista, s, on_change):
        def loop():
            while timer_activo[0]:
                time_module.sleep(1)
                # Actualizar solo los textos de timer (sin reconstruir tarjetas)
                for pid, ref in list(tarjetas_ref.items()):
                    pasajero = next((p for p in s.pasajeros if p.id == pid), None)
                    if pasajero and ref.current:
                        ref.current.value = pasajero.tiempo_en_etapa_actual()
                try:
                    page.update()
                except Exception:
                    break

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    # -----------------------------------------------------------------------
    # Utilidad: cerrar diálogo
    # -----------------------------------------------------------------------

    def cerrar_dialogo():
        if page.dialog:
            page.dialog.open = False
        page.update()

    # -----------------------------------------------------------------------
    # Inicio de la app
    # -----------------------------------------------------------------------

    mostrar_setup()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ft.app(target=main)
