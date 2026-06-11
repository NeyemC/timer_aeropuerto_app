"""
App de Tiempos de Proceso Aeroportuarios
"""

import asyncio
import flet as ft

from modelos import Sesion, Pasajero, TIPOS, LINEAS_AEREAS, AEROPUERTOS
from almacenamiento import guardar, exportar_csv, sincronizar_sheets

COLOR_TIPO = {
    "counter":       ft.Colors.BLUE_700,
    "autochequeo":   ft.Colors.GREEN_700,
    "avsec":         ft.Colors.TEAL_700,
    "equipaje":      ft.Colors.ORANGE_700,
    "internacional": ft.Colors.PURPLE_700,
}


def _borde(w, color):
    s = ft.BorderSide(w, color)
    return ft.Border(left=s, top=s, right=s, bottom=s)


async def main(page: ft.Page):
    page.title = "Tiempos Aeropuerto"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    sesion:       list[Sesion | None] = [None]
    tarjetas_ref: dict[str, ft.Text]  = {}
    timer_id = [0]

    # ── diálogos ──────────────────────────────────────────────────────────
    def abrir_dialogo(dlg): page.show_dialog(dlg)
    def cerrar_dialogo():   page.pop_dialog()

    # ── pantalla de setup ──────────────────────────────────────────────────
    def mostrar_setup():
        campo = ft.TextField(
            label="Nombre del encuestador", hint_text="Ej: Juan Pérez",
            prefix_icon=ft.Icons.PERSON, autofocus=True, border_radius=12)
        dd = ft.Dropdown(
            label="Aeropuerto",
            options=[ft.dropdown.Option(a) for a in AEROPUERTOS],
            border_radius=12)
        error = ft.Text("", color=ft.Colors.RED_700, size=13)

        async def iniciar(e):
            if not campo.value or not dd.value:
                error.value = "Completa todos los campos."
                page.update()
                return
            sesion[0] = Sesion(aeropuerto=dd.value,
                               encuestador=campo.value.strip())
            guardar(sesion[0])
            mostrar_principal()

        page.floating_action_button = None
        page.bgcolor = ft.Colors.WHITE
        page.controls.clear()
        page.controls.append(
            ft.Container(
                expand=True, alignment=ft.Alignment(0, 0),
                padding=ft.Padding(40, 60, 40, 60),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=24,
                    controls=[
                        ft.Icon(ft.Icons.FLIGHT, size=72,
                                color=ft.Colors.BLUE_700),
                        ft.Text("Tiempos de Proceso\nAeroportuarios",
                                size=28, weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.BLUE_900),
                        ft.Text("Configura la sesión antes de comenzar",
                                size=16, color=ft.Colors.GREY_600,
                                text_align=ft.TextAlign.CENTER),
                        ft.Divider(height=8),
                        dd, campo, error,
                        ft.FilledButton(
                            "Iniciar Jornada", icon=ft.Icons.PLAY_ARROW,
                            on_click=iniciar,
                            style=ft.ButtonStyle(
                                padding=ft.Padding(40, 20, 40, 20),
                                shape=ft.RoundedRectangleBorder(radius=12),
                                bgcolor=ft.Colors.BLUE_700,
                                color=ft.Colors.WHITE,
                            ),
                        ),
                    ],
                ),
            )
        )
        page.update()

    # ── pantalla principal ─────────────────────────────────────────────────
    def mostrar_principal():
        s = sesion[0]
        timer_id[0] += 1
        tarjetas_ref.clear()

        # columna persistente: se actualizan sus controls en place
        lista_col = ft.Column(
            spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

        encabezado = ft.Container(
            bgcolor=ft.Colors.BLUE_700,
            padding=ft.Padding(20, 14, 20, 14),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(spacing=2, controls=[
                        ft.Text(s.aeropuerto, color=ft.Colors.WHITE,
                                size=13, weight=ft.FontWeight.W_500),
                        ft.Text(s.encuestador,
                                color=ft.Colors.BLUE_100, size=12),
                    ]),
                    ft.Row(spacing=4, controls=[
                        ft.IconButton(icon=ft.Icons.DOWNLOAD,
                                      icon_color=ft.Colors.WHITE,
                                      tooltip="Exportar CSV",
                                      on_click=accion_exportar),
                        ft.IconButton(icon=ft.Icons.INFO_OUTLINE,
                                      icon_color=ft.Colors.WHITE,
                                      tooltip="Resumen",
                                      on_click=mostrar_resumen),
                    ]),
                ],
            ),
        )

        # FAB como propiedad de página (evita Stack que puede absorber toques)
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            bgcolor=ft.Colors.BLUE_700,
            foreground_color=ft.Colors.WHITE,
            tooltip="Nueva observación",
            on_click=lambda e: mostrar_dialogo_nuevo(reconstruir_lista),
        )

        page.bgcolor = ft.Colors.GREY_100
        page.controls.clear()
        page.controls.append(
            ft.Column(expand=True, spacing=0, controls=[
                encabezado,
                ft.Container(
                    expand=True,
                    padding=ft.Padding(12, 12, 12, 80),
                    content=lista_col,
                ),
            ])
        )
        page.update()

        # reconstruir_lista_async corre como tarea asyncio independiente,
        # igual que el timer, para no modificar la UI desde dentro del handler
        async def reconstruir_lista_async():
            activos = s.activos()
            tarjetas_ref.clear()
            if activos:
                nuevas = [construir_tarjeta(p, reconstruir_lista)
                          for p in activos]
            else:
                nuevas = [
                    ft.Container(
                        expand=True, alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                            controls=[
                                ft.Icon(ft.Icons.PERSON_SEARCH, size=64,
                                        color=ft.Colors.GREY_400),
                                ft.Text("Sin pasajeros activos", size=20,
                                        color=ft.Colors.GREY_500,
                                        weight=ft.FontWeight.W_500),
                                ft.Text(
                                    "Toca + para agregar una observación",
                                    size=14, color=ft.Colors.GREY_400),
                            ],
                        ),
                    )
                ]
            lista_col.controls.clear()
            lista_col.controls.extend(nuevas)
            page.update()

        def reconstruir_lista():
            asyncio.create_task(reconstruir_lista_async())

        reconstruir_lista()
        iniciar_timer_live(s)

    # ── timer ──────────────────────────────────────────────────────────────
    def iniciar_timer_live(s: Sesion):
        my_id = timer_id[0]

        async def _run():
            while True:
                await asyncio.sleep(1)
                if timer_id[0] != my_id:
                    break
                for pid, tw in list(tarjetas_ref.items()):
                    pas = next((p for p in s.pasajeros if p.id == pid), None)
                    if pas:
                        tw.value = pas.tiempo_en_etapa_actual()
                if tarjetas_ref:
                    page.update()

        asyncio.create_task(_run())

    # ── tarjeta ────────────────────────────────────────────────────────────
    def construir_tarjeta(p: Pasajero, on_change) -> ft.Container:
        s     = sesion[0]
        color = COLOR_TIPO[p.tipo]
        label = TIPOS[p.tipo][0]
        total = len(p.etapas)

        etapa = p.etapa_pendiente()
        if etapa is None:
            return ft.Container()
        _, nombre = etapa

        w_etapa   = ft.Text(nombre, size=17, weight=ft.FontWeight.W_600,
                            color=ft.Colors.GREY_900)
        w_btn_txt = ft.Text(f"REGISTRAR: {nombre}", size=15,
                            weight=ft.FontWeight.BOLD)
        w_barra   = ft.ProgressBar(value=p.etapa_idx / total,
                                   bgcolor=ft.Colors.GREY_200, color=color,
                                   height=6, border_radius=3)
        w_prog    = ft.Text(p.progreso(), size=12, color=ft.Colors.GREY_500)
        w_timer   = ft.Text(p.tiempo_en_etapa_actual(), size=22,
                            weight=ft.FontWeight.BOLD, color=color,
                            font_family="monospace")
        tarjetas_ref[p.id] = w_timer

        # handlers ASYNC para correr en el event loop (no en thread pool)
        # y poder usar asyncio.create_task() dentro de on_change()
        async def on_registrar(e):
            completado = p.registrar_evento()
            guardar(s)
            if completado:
                tarjetas_ref.pop(p.id, None)
                mostrar_dialogo_completar(p, on_change)
            else:
                on_change()

        async def on_cancelar(e):
            async def confirmar(e2):
                p.cancelar()
                guardar(s)
                tarjetas_ref.pop(p.id, None)
                cerrar_dialogo()
                on_change()

            abrir_dialogo(ft.AlertDialog(
                modal=True,
                title=ft.Text("¿Cancelar observación?"),
                content=ft.Text(
                    f"Se perderán los datos del pasajero #{p.numero}."),
                actions=[
                    ft.TextButton("Volver",
                                  on_click=lambda e: cerrar_dialogo()),
                    ft.TextButton("Sí, descartar",
                                  style=ft.ButtonStyle(
                                      color=ft.Colors.RED_700),
                                  on_click=confirmar),
                ],
            ))

        return ft.Container(
            bgcolor=ft.Colors.WHITE, border_radius=16,
            padding=ft.Padding(16, 16, 16, 16),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 2)),
            border=_borde(1, ft.Colors.GREY_200),
            content=ft.Column(spacing=14, controls=[
                ft.Row(spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER,
                       controls=[
                           ft.Container(
                               bgcolor=color, border_radius=8,
                               padding=ft.Padding(10, 4, 10, 4),
                               content=ft.Text(f"#{p.numero}",
                                               color=ft.Colors.WHITE,
                                               size=16,
                                               weight=ft.FontWeight.BOLD)),
                           ft.Text(label, size=15,
                                   weight=ft.FontWeight.W_600, color=color),
                           ft.Text("·", color=ft.Colors.GREY_400),
                           ft.Text(p.linea, size=14, color=ft.Colors.GREY_700),
                           ft.Text(p.vuelo,  size=14, color=ft.Colors.GREY_500),
                       ]),
                ft.Column(spacing=4, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                           controls=[ft.Text("Progreso", size=12,
                                             color=ft.Colors.GREY_500),
                                     w_prog]),
                    w_barra,
                ]),
                ft.Container(
                    bgcolor=ft.Colors.GREY_50, border_radius=10,
                    padding=ft.Padding(14, 14, 14, 14),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(spacing=2, expand=True, controls=[
                                ft.Text("Próximo evento:",
                                        size=12, color=ft.Colors.GREY_500),
                                w_etapa,
                            ]),
                            ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                spacing=2,
                                controls=[
                                    ft.Text("En esta etapa", size=11,
                                            color=ft.Colors.GREY_400),
                                    w_timer,
                                ]),
                        ])),
                ft.FilledButton(
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=20),
                            w_btn_txt,
                        ]),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=ft.Padding(0, 16, 0, 16),
                        bgcolor=color,
                        color=ft.Colors.WHITE,
                    ),
                    on_click=on_registrar, expand=True,
                ),
                ft.TextButton(
                    "Descartar observación",
                    icon=ft.Icons.DELETE_OUTLINE,
                    style=ft.ButtonStyle(color=ft.Colors.RED_400),
                    on_click=on_cancelar),
            ]),
        )

    # ── diálogos ──────────────────────────────────────────────────────────
    def mostrar_dialogo_nuevo(on_change):
        tipo_sel = ["counter"]
        chips_data = [
            ("counter",       "Counter",       ft.Icons.AIRLINE_SEAT_RECLINE_NORMAL),
            ("autochequeo",   "Autochequeo",   ft.Icons.COMPUTER),
            ("avsec",         "AVSEC",         ft.Icons.SECURITY),
            ("equipaje",      "Equipaje",      ft.Icons.LUGGAGE),
            ("internacional", "Internacional", ft.Icons.PUBLIC),
        ]

        def hacer_chip(key, lbl, icon):
            sel = tipo_sel[0] == key
            def click(e, k=key):
                tipo_sel[0] = k
                chips_row.controls = [hacer_chip(*d) for d in chips_data]
                page.update()
            return ft.Container(
                on_click=click,
                bgcolor=COLOR_TIPO[key] if sel else ft.Colors.GREY_100,
                border_radius=10,
                padding=ft.Padding(14, 10, 14, 10),
                border=_borde(2, COLOR_TIPO[key] if sel else ft.Colors.GREY_300),
                content=ft.Row(spacing=6, controls=[
                    ft.Icon(icon, size=18,
                            color=ft.Colors.WHITE if sel else ft.Colors.GREY_600),
                    ft.Text(lbl, size=13, weight=ft.FontWeight.W_500,
                            color=ft.Colors.WHITE if sel else ft.Colors.GREY_700),
                ]),
            )

        chips_row   = ft.Row(wrap=True, spacing=8, run_spacing=8,
                             controls=[hacer_chip(*d) for d in chips_data])
        dd_linea    = ft.Dropdown(
            label="Línea aérea",
            options=[ft.dropdown.Option(l) for l in LINEAS_AEREAS],
            border_radius=10, value=LINEAS_AEREAS[0])
        campo_vuelo = ft.TextField(
            label="N° de vuelo (opcional)", hint_text="Ej: LA-450",
            border_radius=10)

        async def confirmar(e):
            if not dd_linea.value:
                return
            sesion[0].agregar_pasajero(
                tipo_sel[0], dd_linea.value,
                campo_vuelo.value.strip() or "-")
            guardar(sesion[0])
            cerrar_dialogo()
            on_change()

        abrir_dialogo(ft.AlertDialog(
            modal=True,
            title=ft.Text("Nueva Observación", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=420, content=ft.Column(
                tight=True, spacing=16,
                controls=[
                    ft.Text("Tipo de proceso:", size=13,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.GREY_700),
                    chips_row, ft.Divider(), dd_linea, campo_vuelo,
                ],
            )),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: cerrar_dialogo()),
                ft.FilledButton(
                    "Iniciar", icon=ft.Icons.PLAY_ARROW,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                    on_click=confirmar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    def mostrar_dialogo_completar(p: Pasajero, on_change):
        c_mod = c_per = c_eq = c_ori = c_cin = c_car = None
        extras = []

        if p.tipo in ("counter", "autochequeo"):
            c_mod = ft.TextField(label="Módulos en servicio", hint_text="Ej: 4",
                                 keyboard_type=ft.KeyboardType.NUMBER,
                                 border_radius=10)
            c_per = ft.TextField(label="Personas en el grupo", hint_text="Ej: 2",
                                 keyboard_type=ft.KeyboardType.NUMBER,
                                 border_radius=10, value="1")
            c_eq  = ft.Dropdown(label="Equipaje en bodega",
                                options=[ft.dropdown.Option("Sí"),
                                         ft.dropdown.Option("No")],
                                border_radius=10, value="Sí")
            extras = [c_mod, c_per, c_eq]
        elif p.tipo == "equipaje":
            c_ori = ft.TextField(label="Origen del vuelo",
                                 hint_text="Ej: Santiago", border_radius=10)
            c_cin = ft.TextField(label="N° de cinta", hint_text="Ej: 1",
                                 keyboard_type=ft.KeyboardType.NUMBER,
                                 border_radius=10)
            c_car = ft.TextField(label="Carros disponibles",
                                 hint_text="Ej: 30",
                                 keyboard_type=ft.KeyboardType.NUMBER,
                                 border_radius=10)
            extras = [c_ori, c_cin, c_car]

        async def guardar_y_cerrar(e):
            if p.tipo in ("counter", "autochequeo"):
                p.extra.update({"modulos": c_mod.value,
                                "personas": c_per.value,
                                "equipaje_bodega": c_eq.value})
            elif p.tipo == "equipaje":
                p.extra.update({"origen": c_ori.value,
                                "cinta": c_cin.value,
                                "carros": c_car.value})
            guardar(sesion[0])
            cerrar_dialogo()
            on_change()

        abrir_dialogo(ft.AlertDialog(
            modal=True,
            title=ft.Row(spacing=8, controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_600, size=24),
                ft.Text(f"#{p.numero} Completado", weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Container(width=420, content=ft.Column(
                tight=True, spacing=14,
                controls=[
                    ft.Text(f"{TIPOS[p.tipo][0]}  ·  {p.linea}  {p.vuelo}",
                            size=13, color=ft.Colors.GREY_600),
                    ft.Divider(), *extras,
                ],
            )),
            actions=[
                ft.FilledButton("Guardar y cerrar", icon=ft.Icons.SAVE,
                               style=ft.ButtonStyle(
                                   bgcolor=ft.Colors.GREEN_700,
                                   color=ft.Colors.WHITE),
                               on_click=guardar_y_cerrar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    async def mostrar_resumen(_e):
        s = sesion[0]
        abrir_dialogo(ft.AlertDialog(
            modal=False, title=ft.Text("Resumen de sesión"),
            content=ft.Column(tight=True, spacing=10, controls=[
                ft.Text(f"Aeropuerto:  {s.aeropuerto}", size=14),
                ft.Text(f"Encuestador: {s.encuestador}", size=14),
                ft.Text(f"Fecha:       {s.fecha}", size=14),
                ft.Divider(),
                ft.Text(f"Total:       {len(s.pasajeros)}", size=14),
                ft.Text(f"En curso:    {len(s.activos())}", size=14,
                        color=ft.Colors.ORANGE_700),
                ft.Text(f"Completadas: {len(s.completados())}", size=14,
                        color=ft.Colors.GREEN_700),
            ]),
            actions=[ft.TextButton("Cerrar",
                                   on_click=lambda e: cerrar_dialogo())],
        ))

    async def accion_exportar(_e):
        s = sesion[0]
        if not s.completados():
            abrir_dialogo(ft.AlertDialog(
                modal=False,
                title=ft.Text("Sin datos para exportar"),
                content=ft.Text("Aún no hay observaciones completadas."),
                actions=[ft.TextButton("OK", on_click=lambda e: cerrar_dialogo())],
            ))
            return
        try:
            ruta = exportar_csv(s)
            msg = f"CSV guardado en:\n{ruta}"
            try:
                n = sincronizar_sheets(s)
                msg += f"\n\n✓ {n} fila(s) nuevas enviadas a Google Sheets."
            except Exception as ex_sheets:
                msg += f"\n\n⚠ No se pudo sincronizar con Sheets:\n{ex_sheets}"
            abrir_dialogo(ft.AlertDialog(
                modal=False,
                title=ft.Text("Exportado"),
                content=ft.Text(msg),
                actions=[ft.TextButton("OK", on_click=lambda e: cerrar_dialogo())],
            ))
        except Exception as ex:
            abrir_dialogo(ft.AlertDialog(
                modal=False,
                title=ft.Text("Error al exportar"),
                content=ft.Text(str(ex)),
                actions=[ft.TextButton("OK", on_click=lambda e: cerrar_dialogo())],
            ))

    mostrar_setup()


if __name__ == "__main__":
    ft.run(main)
