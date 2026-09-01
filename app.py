import pandas as pd
import requests
import streamlit as st
from db import (
    actualizar_estado_delegacion,
    actualizar_estado_pago,
    obtener_integrantes_delegacion,
    obtener_pagos_pendientes,
    obtener_todas_delegaciones,
    obtener_todas_nominas,
    obtener_todos_pagos,
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
    try:
        requests.post(API_URL, json={"action": action, "data": data}, timeout=5)
    except Exception as e:
        st.warning(
            f"Cambio guardado en Firebase, pero hubo un detalle con la"
            f" notificación por mail: {e}"
        )


def descargar_csv_para_excel(df, nombre_archivo):
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

st.sidebar.markdown("---")

tab_dash, tab_ficha, tab_auditoria, tab_pagos, tab_paises, tab_medicos, tab_acred = (
    st.tabs([
        "📊 Dashboard y KPIs",
        "🏫 Ficha Nominal por Escuela",
        "🔍 Auditoría y Aprobación Final",
        "💰 Gestión de Pagos",
        "🌍 Países y Bancas",
        "🩺 Alertas Médicas",
        "🎫 Control de Acreditación",
    ])
)

# 1. DASHBOARD
with tab_dash:
    st.subheader("📊 Panel General")
    delegaciones = obtener_todas_delegaciones()
    nominas = obtener_todas_nominas()
    pagos_pendientes = obtener_pagos_pendientes()

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
        descargar_csv_para_excel(df_del, "escuelas_preinscriptas")
    else:
        st.info("No hay delegaciones registradas en Firestore.")

# 2. FICHA NOMINAL CON BÚSQUEDA AVANZADA
with tab_ficha:
    st.subheader("🏫 Ficha Integral por Institución")
    delegaciones_ficha = obtener_todas_delegaciones()

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
            st.warning("No se encontraron escuelas que coincidan con el filtro.")
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
            st.markdown("### 📄 Toda la Información Registrada")
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
                    "**👤 Docente Responsable:**"
                    f" {escuela.get('docente_apellido_nombre', '-')}"
                )
                st.markdown(
                    f"**📧 Email Docente:** {escuela.get('docente_email', '-')}"
                )
                st.markdown(
                    "**📱 Teléfono:** {escuela.get('docente_telefono', '-')}"
                )
            with cols_info[2]:
                st.markdown(
                    "**📊 Cupos Solicitados:**"
                    f" {escuela.get('cupos_solicitados', '-')}"
                )
                st.markdown(
                    f"**🔑 Clave Hash:** `{escuela.get('secret_hash', '-')}`"
                )

            with st.expander("🔍 Ver JSON con todos los atributos de Firestore"):
                st.json(escuela)

            st.markdown("---")
            st.markdown("### 👨‍🏫 Docentes Acompañantes Registrados")
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
                        f" (DNI: {doc.get('dni', doc.get('id'))}) —"
                        f" {doc.get('alergias_medicas', 'Sin especificaciones')}"
                    )

            st.markdown("### 👥 Estudiantes Registrados en Nómina")
            if not alumnos_escuela:
                st.info("No hay participantes cargados en la nómina.")
            else:
                df_alumnos = pd.DataFrame(alumnos_escuela).astype(str)
                st.dataframe(df_alumnos, use_container_width=True)
                descargar_csv_para_excel(df_alumnos, f"nomina_{id_del}")

# 3. AUDITORÍA Y NOTIFICACIÓN
with tab_auditoria:
    st.subheader("🔍 Auditoría de Documentación y Aprobación Final")
    delegaciones_aud = obtener_todas_delegaciones()

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
            st.warning(
                "⚠️ Esta escuela todavía no ha cargado participantes en su"
                " nómina."
            )
        else:
            st.markdown(
                "### 📋 Nómina Completa y Enlaces a Documentos en Drive"
            )
            for idx, reg in enumerate(registros_aud):
                st.markdown(
                    f"**{idx+1}. {reg.get('nombre', '')} {reg.get('apellido', '')}**"
                    f" (DNI: {reg.get('dni', reg.get('id'))}) — *Rol/Banca:*"
                    f" {reg.get('rol_mnu', '-')}"
                )

                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    ficha_id = reg.get("ficha_medica_id") or "-"
                    if ficha_id != "-":
                        st.markdown(
                            "📄 [Ver Ficha / Constancia en"
                            f" Drive](https://drive.google.com/open?id={ficha_id})",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.write("📄 Documento 1: No adjunto")
                with col_e2:
                    aut_id = reg.get("autorizacion_id") or "-"
                    if aut_id != "-":
                        st.markdown(
                            "📝 [Ver Autorización en"
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
                    st.success(
                        "¡Legajo aprobado en Firebase y correo enviado!"
                    )
                    st.rerun()

            with col_btn2:
                with st.expander("❌ Rechazar Legajo con Observaciones"):
                    with st.form(key=f"form_rechazo_{id_del_aud}"):
                        motivo_rechazo = st.text_area(
                            "Indique el motivo del rechazo:"
                        )
                        btn_enviar_rechazo = st.form_submit_button(
                            "Confirmar Rechazo y Notificar"
                        )

                        if btn_enviar_rechazo:
                            if not motivo_rechazo.strip():
                                st.error("Debe ingresar un motivo.")
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

# 4. GESTIÓN DE PAGOS
with tab_pagos:
    st.subheader("💰 Gestión de Comprobantes y Recaudación")
    pagos_pendientes = obtener_pagos_pendientes()
    pagos_todos = obtener_todos_pagos()

    sub1, sub2 = st.tabs(
        ["⏳ Pagos Pendientes", "✅ Historial de Pagos y Acumulador"]
    )

    with sub1:
        if not pagos_pendientes:
            st.success("🎉 ¡No hay pagos pendientes de revisión!")
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
            descargar_csv_para_excel(df_pagos, "historial_pagos")
        else:
            st.info("No hay pagos en Firestore.")

# 5. ALERTAS MÉDICAS
with tab_medicos:
    st.subheader("🩺 Reporte General de Salud y Alergias")
    nominas_medicas = obtener_todas_nominas()

    if nominas_medicas:
        alerta_nominas = [
            n
            for n in nominas_medicas
            if n.get("alergias_medicas")
            and str(n.get("alergias_medicas")).strip().lower()
            not in ["ninguna", "-", ""]
        ]
        if not alerta_nominas:
            st.success("✅ No hay alertas médicas registradas.")
        else:
            st.warning(
                f"⚠️ Se encontraron {len(alerta_nominas)} registros con"
                " observaciones médicas:"
            )
            df_alertas = pd.DataFrame(alerta_nominas).astype(str)
            st.dataframe(df_alertas, use_container_width=True)
            descargar_csv_para_excel(df_alertas, "reporte_alertas_medicas")
    else:
        st.info("No hay datos en las nóminas.")

# 6. PAÍSES Y ACREDITACIÓN
with tab_paises:
    st.subheader("🌍 Control de Disponibilidad")
    st.info("Módulo disponible para asignaciones de Firestore.")

with tab_acred:
    st.subheader("🎫 Control de Acreditación")
    st.info("Módulo disponible para validación de acreditados de Firestore.")
