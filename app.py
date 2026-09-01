import pandas as pd
import requests
import streamlit as st
from db import (
    actualizar_estado_delegacion,
    actualizar_estado_pago,
    guardar_esquema_formulario,
    obtener_delegaciones_por_modelo,
    obtener_esquema_formulario,
    obtener_integrantes_delegacion,
    obtener_modelos_activos,
    obtener_nominas_por_modelo,
    obtener_pagos_pendientes,
    obtener_todos_pagos,
    procesar_acreditacion_forms,
)

st.set_page_config(
    page_title="Panel de Secretaría - Modelos ONU", page_icon="👑", layout="wide"
)

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

API_URL = st.secrets["API_URL"]


def notificar_apps_script(action, data):
    """Envia eventos de notificación a Google Apps Script."""
    try:
        requests.post(API_URL, json={"action": action, "data": data}, timeout=5)
    except Exception as e:
        st.warning(
            f"Operación guardada en Firestore, pero hubo un detalle en la"
            f" notificación: {e}"
        )


def descargar_csv_para_excel(df, nombre_archivo):
    """Genera botón de descarga compatible con Excel."""
    df_clean = df.astype(str)
    csv = df_clean.to_csv(index=False).encode("utf-8-sig")
    return st.download_button(
        label=f"📥 Descargar {nombre_archivo} (Compatible con Excel)",
        data=csv,
        file_name=f"{nombre_archivo}.csv",
        mime="text/csv",
        key=f"btn_{nombre_archivo}",
    )


st.title("👑 Panel de Control - Secretaría / Administración")

# Control de Acceso
if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False

if not st.session_state["admin_logueado"]:
    st.markdown("### 🔒 Acceso Restringido al Secretariado")
    with st.form("form_login_admin"):
        pass_ingresada = st.text_input(
            "Contraseña de Administración:", type="password"
        )
        btn_ingresar = st.form_submit_button("Ingresar al Panel")

        if btn_ingresar:
            if pass_ingresada.strip() == st.secrets["admin_logueado"]:
                st.session_state["admin_logueado"] = True
                st.success("¡Acceso concedido!")
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()

if st.sidebar.button("Cerrar Sesión Admin"):
    st.session_state["admin_logueado"] = False
    st.rerun()

# Selector de Modelo Activo
modelos = obtener_modelos_activos()
dict_modelos = {m["nombre_visible"]: m["id_modelo"] for m in modelos}

modelo_seleccionado = st.sidebar.selectbox(
    "📌 Seleccionar Modelo a Gestionar:", list(dict_modelos.keys())
)
id_modelo_actual = dict_modelos[modelo_seleccionado]

st.sidebar.markdown(f"**ID Modelo Activo:** `{id_modelo_actual}`")
st.sidebar.markdown("---")

# Estructura de Pestañas
(
    tab_dash,
    tab_ficha,
    tab_auditoria,
    tab_pagos,
    tab_medicos,
    tab_acred,
    tab_config,
) = st.tabs([
    "📊 Dashboard y KPIs",
    "🏫 Ficha Nominal por Escuela",
    "🔍 Auditoría de Legajos",
    "💰 Gestión de Pagos",
    "🩺 Alertas Médicas",
    "🎫 Control de Acreditación",
    "⚙️ Configuración de Formulario",
])

# 1. DASHBOARD
with tab_dash:
    st.subheader(f"📊 Panel General — {modelo_seleccionado}")
    delegaciones = obtener_delegaciones_por_modelo(id_modelo_actual)
    nominas = obtener_nominas_por_modelo(id_modelo_actual)
    pagos_pendientes = obtener_pagos_pendientes(id_modelo_actual)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Escuelas Registradas", len(delegaciones))
    with col2:
        docs_completas = sum(
            1
            for d in delegaciones
            if str(d.get("estado")).upper()
            in ["DOCUMENTACION_COMPLETA", "APROBADO_FINAL"]
        )
        st.metric("Doc. Completa / Aprobada", docs_completas)
    with col3:
        st.metric("Participantes en Nómina", len(nominas))
    with col4:
        st.metric("Pagos Pendientes", len(pagos_pendientes))

    st.markdown("---")
    st.markdown("### 📋 Listado Rápido de Instituciones")
    if delegaciones:
        df_del = pd.DataFrame(delegaciones).astype(str)
        st.dataframe(df_del, use_container_width=True)
        descargar_csv_para_excel(
            df_del, f"escuelas_preinscriptas_{id_modelo_actual}"
        )
    else:
        st.info("No hay delegaciones registradas para este modelo.")

# 2. FICHA NOMINAL CON BÚSQUEDA AVANZADA
with tab_ficha:
    st.subheader(f"🏫 Ficha Integral por Institución — {modelo_seleccionado}")
    delegaciones_ficha = obtener_delegaciones_por_modelo(id_modelo_actual)

    if not delegaciones_ficha:
        st.info("No hay escuelas registradas.")
    else:
        busqueda = st.text_input(
            "🔍 Buscar por Nombre de Escuela o Código de Delegación:", ""
        ).strip()

        escuelas_filtradas = [
            d
            for d in delegaciones_ficha
            if busqueda.lower() in str(d.get("nombre_colegio", "")).lower()
            or busqueda.lower() in str(d.get("id", "")).lower()
        ]

        if not escuelas_filtradas:
            st.warning("No se encontraron coincidencias.")
        else:
            opciones_escuelas = {
                f"[{d.get('id')}] {d.get('nombre_colegio', 'Sin Nombre')}": d
                for d in escuelas_filtradas
            }
            escuela_label = st.selectbox(
                "Seleccionar Institución:",
                list(opciones_escuelas.keys()),
                key="select_escuela_ficha",
            )
            escuela = opciones_escuelas[escuela_label]
            id_del = escuela.get("id")

            st.markdown("---")
            st.markdown("### 📄 Información Registrada en Firestore")
            cols_info = st.columns(3)
            with cols_info[0]:
                st.markdown(
                    f"**🏛️ Institución:** {escuela.get('nombre_colegio', '-')}"
                )
                st.markdown(
                    f"**📍 Dirección:** {escuela.get('direccion_escuela', '-')}"
                )
                st.markdown(f"**🆔 ID Delegación:** `{id_del}`")
                st.markdown(
                    f"**📌 Estado:** `{escuela.get('estado', 'REGISTRADO')}`"
                )
            with cols_info[1]:
                st.markdown(
                    "**👤 Responsable:**"
                    f" {escuela.get('docente_apellido_nombre', '-')}"
                )
                st.markdown(
                    f"**📧 Email:** {escuela.get('docente_email', '-')}"
                )
                st.markdown(
                    f"**📱 Teléfono:** {escuela.get('docente_telefono', '-')}"
                )
            with cols_info[2]:
                st.markdown(
                    "**📊 Cupos Solicitados:**"
                    f" {escuela.get('cupos_solicitados', '-')}"
                )
                st.markdown(
                    f"**🔑 Clave Hash:** `{escuela.get('secret_hash', '-')}`"
                )

            with st.expander("🔍 Ver todos los atributos (JSON)"):
                st.json(escuela)

            st.markdown("---")
            st.markdown("### 👨‍🏫 Docentes Acompañantes")
            registros_escuela = obtener_integrantes_delegacion(id_del)

            docentes_escuela = [
                r
                for r in registros_escuela
                if r.get("rol_mnu") == "Docente Acompañante"
            ]
            alumnos_escuela = [
                r
                for r in registros_escuela
                if r.get("rol_mnu") != "Docente Acompañante"
            ]

            if not docentes_escuela:
                st.info("No hay docentes acompañantes registrados.")
            else:
                for doc in docentes_escuela:
                    st.write(
                        f"- **{doc.get('nombre', '')} {doc.get('apellido', '')}**"
                        f" (DNI: {doc.get('dni', doc.get('id'))})"
                    )

            st.markdown("### 👥 Estudiantes en Nómina")
            if not alumnos_escuela:
                st.info("No hay participantes en la nómina.")
            else:
                df_alumnos = pd.DataFrame(alumnos_escuela).astype(str)
                st.dataframe(df_alumnos, use_container_width=True)
                descargar_csv_para_excel(df_alumnos, f"nomina_{id_del}")

# 3. AUDITORÍA
with tab_auditoria:
    st.subheader(f"🔍 Auditoría y Aprobaciones — {modelo_seleccionado}")
    delegaciones_aud = obtener_delegaciones_por_modelo(id_modelo_actual)

    if not delegaciones_aud:
        st.info("No hay escuelas registradas.")
    else:
        opc_aud = {
            f"[{d.get('id')}] {d.get('nombre_colegio')} (Estado: {d.get('estado')})": d
            for d in delegaciones_aud
        }
        sel_aud_label = st.selectbox(
            "Seleccionar Institución a Auditar:",
            list(opc_aud.keys()),
            key="select_auditoria",
        )
        escuela_aud = opc_aud[sel_aud_label]
        id_del_aud = escuela_aud.get("id")

        st.markdown("---")
        st.write(
            f"**Institución:** {escuela_aud.get('nombre_colegio')} | **Docente:** {escuela_aud.get('docente_apellido_nombre')} ({escuela_aud.get('docente_email')})"
        )
        st.write(
            f"**Estado actual:** `{escuela_aud.get('estado', 'REGISTRADO')}`"
        )

        registros_aud = obtener_integrantes_delegacion(id_del_aud)

        if not registros_aud:
            st.warning("⚠️ Sin participantes en nómina.")
        else:
            st.markdown("### 📋 Documentación Presentada")
            for idx, reg in enumerate(registros_aud):
                st.markdown(
                    f"**{idx+1}. {reg.get('nombre', '')} {reg.get('apellido', '')}**"
                    f" (DNI: {reg.get('dni', reg.get('id'))})"
                )
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    ficha_id = reg.get("ficha_medica_id") or "-"
                    if ficha_id != "-":
                        st.markdown(
                            "📄 [Ver Ficha Medica"
                            f" Drive](https://drive.google.com/open?id={ficha_id})",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.write("📄 Documento 1: No adjunto")
                with col_e2:
                    aut_id = reg.get("autorizacion_id") or "-"
                    if aut_id != "-":
                        st.markdown(
                            "📝 [Ver Autorización"
                            f" Drive](https://drive.google.com/open?id={aut_id})",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.write("📝 Documento 2: No adjunto")
                st.markdown("---")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button(
                    "✅ Aprobar Legajo Completo",
                    key=f"btn_aprobar_{id_del_aud}",
                    use_container_width=True,
                ):
                    actualizar_estado_delegacion(
                        id_del_aud, "DOCUMENTACION_COMPLETA"
                    )
                    notificar_apps_script(
                        "APROBAR_LEGAJO_ESCUELA", {"id_delegacion": id_del_aud}
                    )
                    st.success("Legajo aprobado y notificado.")
                    st.rerun()

            with col_btn2:
                with st.expander("❌ Rechazar Legajo"):
                    with st.form(key=f"form_rechazo_{id_del_aud}"):
                        motivo_rechazo = st.text_area(
                            "Indique el motivo del rechazo:"
                        )
                        btn_enviar_rechazo = st.form_submit_button(
                            "Confirmar Rechazo"
                        )
                        if btn_enviar_rechazo:
                            if not motivo_rechazo.strip():
                                st.error("Ingrese un motivo.")
                            else:
                                actualizar_estado_delegacion(
                                    id_del_aud, "RECHAZADO", motivo_rechazo
                                )
                                notificar_apps_script(
                                    "RECHAZAR_LEGAJO_ESCUELA",
                                    {
                                        "id_delegacion": id_del_aud,
                                        "motivo": motivo_rechazo,
                                    },
                                )
                                st.warning("Legajo rechazado y notificado.")
                                st.rerun()

# 4. PAGOS
with tab_pagos:
    st.subheader(f"💰 Gestión de Comprobantes — {modelo_seleccionado}")
    pagos_pendientes = obtener_pagos_pendientes(id_modelo_actual)
    pagos_todos = obtener_todos_pagos(id_modelo_actual)

    sub1, sub2 = st.tabs(["⏳ Pendientes", "✅ Historial"])
    with sub1:
        if not pagos_pendientes:
            st.success("🎉 ¡No hay pagos pendientes!")
        else:
            for p in pagos_pendientes:
                id_pago = p.get("id_pago")
                with st.container():
                    col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                    with col_p1:
                        st.write(f"**ID Pago:** `{id_pago}`")
                        st.write(
                            "**🏛️ Delegación:**"
                            f" `{p.get('id_delegacion', '-')}`"
                        )
                        st.write(f"**💵 Monto:** **${p.get('monto', 0)}**")
                    with col_p2:
                        url_comp = p.get("drive_file_url")
                        if url_comp:
                            st.markdown(
                                f"🔗 [Ver Comprobante]({url_comp})",
                                unsafe_allow_html=True,
                            )
                        st.write(
                            f"**Estado:** `{p.get('estado_pago', 'PENDIENTE')}`"
                        )
                    with col_p3:
                        if st.button("Aprobar", key=f"ap_{id_pago}"):
                            actualizar_estado_pago(id_pago, "APROBADO")
                            notificar_apps_script(
                                "CAMBIAR_ESTADO_PAGO",
                                {"id_pago": id_pago, "nuevo_estado": "APROBADO"},
                            )
                            st.success("Pago aprobado.")
                            st.rerun()
                        if st.button("Rechazar", key=f"rec_{id_pago}"):
                            actualizar_estado_pago(id_pago, "RECHAZADO")
                            notificar_apps_script(
                                "CAMBIAR_ESTADO_PAGO",
                                {
                                    "id_pago": id_pago,
                                    "nuevo_estado": "RECHAZADO",
                                },
                            )
                            st.warning("Pago rechazado.")
                            st.rerun()
                    st.markdown("---")

    with sub2:
        if pagos_todos:
            df_pagos = pd.DataFrame(pagos_todos).astype(str)
            pagos_aprobados = df_pagos[
                df_pagos["estado_pago"].str.upper() == "APROBADO"
            ]
            total_recaudado = (
                pagos_aprobados["monto"].astype(float).sum()
                if not pagos_aprobados.empty
                else 0
            )
            st.metric("Total Recaudado", f"${total_recaudado:,.2f}")
            st.dataframe(df_pagos, use_container_width=True)
            descargar_csv_para_excel(
                df_pagos, f"historial_pagos_{id_modelo_actual}"
            )

# 5. ALERTAS MÉDICAS
with tab_medicos:
    st.subheader(f"🩺 Reporte de Salud — {modelo_seleccionado}")
    nominas_medicas = obtener_nominas_por_modelo(id_modelo_actual)

    if nominas_medicas:
        alerta_nominas = [
            n
            for n in nominas_medicas
            if n.get("alergias_medicas")
            and str(n.get("alergias_medicas")).strip().lower()
            not in ["ninguna", "-", ""]
        ]
        if not alerta_nominas:
            st.success("✅ Sin alertas médicas.")
        else:
            st.warning(
                f"⚠️ Se encontraron {len(alerta_nominas)} observaciones"
                " médicas:"
            )
            df_alertas = pd.DataFrame(alerta_nominas).astype(str)
            st.dataframe(df_alertas, use_container_width=True)
            descargar_csv_para_excel(
                df_alertas, f"reporte_alertas_medicas_{id_modelo_actual}"
            )

# 6. ACREDITACIÓN VIA GOOGLE FORMS
with tab_acred:
    st.subheader(f"🎫 Acreditaciones Google Forms — {modelo_seleccionado}")
    file_forms = st.file_uploader(
        "Cargar Excel/CSV con asistencias de Google Forms", type=["xlsx", "csv"]
    )

    if file_forms:
        df_f = (
            pd.read_csv(file_forms)
            if file_forms.name.endswith(".csv")
            else pd.read_excel(file_forms)
        )
        if "DNI" not in df_f.columns:
            st.error("El archivo debe contener la columna 'DNI'.")
        else:
            if st.button("🔍 Procesar y Auditar Acreditaciones"):
                res = procesar_acreditacion_forms(df_f, id_modelo_actual)
                col_a1, col_a2, col_a3 = st.columns(3)
                with col_a1:
                    st.metric("Total en Nómina", res["total_nominados"])
                with col_a2:
                    st.metric("Acreditados Correctos", res["total_acreditados"])
                with col_a3:
                    st.metric(
                        "% Acreditación del Modelo", f"{res['porcentaje']}%"
                    )

                st.markdown("---")
                no_reg = res["no_registrados"]
                if no_reg:
                    st.warning(
                        f"⚠️ {len(no_reg)} DNI acreditados NO figuran en la"
                        " nómina oficial:"
                    )
                    st.write(no_reg)
                    if st.button("📧 Enviar Correo a DNI No Registrados"):
                        for dni_nr in no_reg:
                            notificar_apps_script(
                                "NOTIFICAR_ACREDITADO_NO_REGISTRADO",
                                {"dni": dni_nr, "modelo": modelo_seleccionado},
                            )
                        st.info("Notificaciones enviadas.")
                else:
                    st.success("🎉 ¡Todos los asistidos figuran en la nómina!")

# 7. CONFIGURACIÓN DINÁMICA DE FORMULARIO
with tab_config:
    st.subheader(
        f"⚙️ Diseñador de Campos de Formulario — {modelo_seleccionado}"
    )
    st.write(
        "Agrega o elimina los campos requeridos para las inscripciones de este"
        " modelo."
    )

    campos_actuales = obtener_esquema_formulario(id_modelo_actual)
    df_campos = (
        pd.DataFrame(campos_actuales)
        if campos_actuales
        else pd.DataFrame(
            columns=[
                "nombre_campo",
                "tipo_dato",
                "opciones_separadas_por_coma",
                "es_requerido",
            ]
        )
    )

    df_editado = st.data_editor(
        df_campos,
        num_rows="dynamic",
        column_config={
            "nombre_campo": st.column_config.TextColumn("Nombre del Campo"),
            "tipo_dato": st.column_config.SelectboxColumn(
                "Tipo de Entrada",
                options=["texto", "numero", "seleccion", "booleano"],
            ),
            "opciones_separadas_por_coma": st.column_config.TextColumn(
                "Opciones (solo si es Selección)"
            ),
            "es_requerido": st.column_config.CheckboxColumn(
                "¿Obligatorio?", default=False
            ),
        },
        key="editor_esquema_formulario",
    )

    if st.button("💾 Publicar Cambios en el Formulario"):
        lista_nuevos_campos = df_editado.to_dict(orient="records")
        if guardar_esquema_formulario(id_modelo_actual, lista_nuevos_campos):
            st.success(
                "¡Estructura de formulario actualizada correctamente!"
            )
            st.rerun()
