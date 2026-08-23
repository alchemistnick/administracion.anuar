import streamlit as st
import requests
import pandas as pd
import base64

st.set_page_config(
    page_title="Panel de Secretaría - Modelos ONU",
    page_icon="👑",
    layout="wide"
)

# URL DE LA API DE APPS SCRIPT
API_URL = "https://script.google.com/macros/s/AKfycbzetBeBzqAeJLzcLoU6mqbRmwi26JRqC0iAGR9KjoxnhHfvuL47RsLx1CL9axo1lvPgWg/exec"

def api_get(action, params=""):
    try:
        url = f"{API_URL}?action={action}{params}"
        res = requests.get(url).json()
        if res.get("status") == "SUCCESS":
            return res.get("data", [])
        return []
    except Exception:
        return []

import io

def descargar_excel_real(df, nombre_archivo):
    output = io.BytesIO()
    # Usamos pandas con el motor openpyxl para generar un Excel real y limpio
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    processed_data = output.getvalue()
    
    return st.download_button(
        label=f"📥 Descargar {nombre_archivo} en Excel (.xlsx)",
        data=processed_data,
        file_name=f"{nombre_archivo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.title("👑 Panel de Control - Secretaría / Administración")

# ---------------------------------------------------------
# AUTENTICACIÓN ADMINISTRATIVA
# ---------------------------------------------------------
if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False

if not st.session_state["admin_logueado"]:
    st.markdown("### 🔒 Acceso Restringido al Secretariado")
    with st.form("form_login_admin"):
        pass_ingresada = st.text_input("Contraseña de Administración:", type="password")
        btn_ingresar = st.form_submit_button("Ingresar al Panel")
        
        if btn_ingresar:
            if pass_ingresada.strip() == "secreta2026":
                st.session_state["admin_logueado"] = True
                st.success("¡Acceso concedido!")
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()

if st.sidebar.button("Cerrar Sesión Admin"):
    st.session_state["admin_logueado"] = False
    st.rerun()

# Selección de Modelo
modelos = api_get("GET_MODELOS_ACTIVOS")
if not modelos:
    st.warning("⚠️ No hay modelos activos configurados.")
    st.stop()

dict_modelos = {m["nombre_visible"]: m["id_modelo"] for m in modelos}
modelo_seleccionado = st.sidebar.selectbox("Seleccionar Modelo:", list(dict_modelos.keys()))
id_modelo_actual = dict_modelos[modelo_seleccionado]

st.sidebar.markdown("---")

# ---------------------------------------------------------
# NAVEGACIÓN POR PESTAÑAS (TABS)
# ---------------------------------------------------------
tab_dash, tab_ficha, tab_pagos, tab_paises, tab_medicos = st.tabs([
    "📊 Dashboard y KPIs", 
    "🏫 Ficha Nominal por Escuela", 
    "💰 Gestión de Pagos", 
    "🌍 Países y Bancas", 
    "🩺 Alertas Médicas"
])

# ---------------------------------------------------------
# 1. DASHBOARD Y KPIS
# ---------------------------------------------------------
with tab_dash:
    st.subheader(f"📊 Panel General - {modelo_seleccionado}")
    
    delegaciones = api_get("GET_TODAS_DELEGACIONES", f"&id_modelo={id_modelo_actual}")
    nominas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
    pagos = api_get("GET_PAGOS_PENDIENTES")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Escuelas Registradas", len(delegaciones))
    with col2:
        docs_completas = sum(1 for d in delegaciones if str(d.get("estado")).upper() == "DOCUMENTACION_COMPLETA")
        st.metric("Documentación Completa", docs_completas)
    with col3:
        st.metric("Estudiantes en Nómina", len(nominas))
    with col4:
        st.metric("Pagos Pendientes", len(pagos))

    st.markdown("---")
    st.markdown("### 📋 Listado Rápido de Instituciones")
    if delegaciones:
        df_del = pd.DataFrame(delegaciones)
        st.dataframe(df_del, use_container_width=True)
        st.markdown(descargar_excel_html(df_del, "escuelas_preinscriptas"), unsafe_allow_html=True)
    else:
        st.info("No hay delegaciones registradas todavía.")

# ---------------------------------------------------------
# 2. FICHA NOMINAL POR ESCUELA
# ---------------------------------------------------------
with tab_ficha:
    st.subheader("🏫 Ficha Integral por Institución")
    
    delegaciones_ficha = api_get("GET_TODAS_DELEGACIONES", f"&id_modelo={id_modelo_actual}")
    
    if not delegaciones_ficha:
        st.info("No hay escuelas registradas.")
    else:
        opciones_escuelas = {f"[{d.get('id_delegacion')}] {d.get('nombre_colegio')}": d for d in delegaciones_ficha}
        escuela_label = st.selectbox("Seleccionar Institución:", list(opciones_escuelas.keys()), key="select_escuela_ficha")
        escuela = opciones_escuelas[escuela_label]

        id_del = escuela.get("id_delegacion")
        st.markdown("---")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            st.markdown(f"**🏛️ Institución:** {escuela.get('nombre_colegio')}")
            st.markdown(f"**📍 Dirección:** {escuela.get('direccion_escuela')}")
            st.markdown(f"**🆔 Código Delegación:** `{id_del}`")
        with col_f2:
            st.markdown(f"**👤 Responsable:** {escuela.get('docente_apellido_nombre')}")
            st.markdown(f"**📧 Email Docente:** {escuela.get('docente_email')}")
            st.markdown(f"**📱 Teléfono Celular:** {escuela.get('docente_telefono')}")
        with col_f3:
            st.markdown(f"**📊 Cupos Solicitados:** {escuela.get('cupos_solicitados')}")
            st.markdown(f"**🔑 Clave de Acceso:** `{escuela.get('secret_hash')}`")
            st.markdown(f"**📌 Estado Documentación:** `{escuela.get('estado', 'REGISTRADO')}`")

        st.markdown("---")
        st.markdown("### 📌 Bancas y Países Asignados")
        res_asig = requests.get(f"{API_URL}?action=GET_ASIGNACIONES_DELEGACION&id_delegacion={id_del}").json()
        bancas_escuela = res_asig.get("data", [])

        if not bancas_escuela:
            st.warning("⚠️ Esta institución aún no tiene bancas o países asignados.")
        else:
            for b in bancas_escuela:
                st.write(f"- **{b.get('organo')}** — País: **{b.get('pais')}** (ID Asignación: `{b.get('id_asignacion')}`)")

        st.markdown("---")
        st.markdown("### 👥 Estudiantes Registrados en Nómina")
        nominas_todas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
        alumnos_escuela = [n for n in nominas_todas if str(n.get("id_delegacion")).strip().upper() == str(id_del).strip().upper()]
        
        if not alumnos_escuela:
            st.info("La escuela aún no ha cargado participantes en su nómina.")
        else:
            df_alumnos = pd.DataFrame(alumnos_escuela)
            st.dataframe(df_alumnos[["id_asignacion", "rol_mnu", "nombre", "apellido", "dni", "alergias_medicas"]], use_container_width=True)
            st.markdown(descargar_excel_html(df_alumnos, f"nomina_{id_del}"), unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. GESTIÓN DE PAGOS Y RECAUDACIÓN
# ---------------------------------------------------------
with tab_pagos:
    st.subheader("💰 Gestión de Comprobantes y Recaudación")
    
    pagos_pendientes = api_get("GET_PAGOS_PENDIENTES")
    pagos_todos = api_get("GET_TODOS_PAGOS")
    
    subtab1, subtab2 = st.tabs(["⏳ Pagos Pendientes", "✅ Historial de Pagos y Acumulador"])
    
    with subtab1:
        if not pagos_pendientes:
            st.success("🎉 ¡No hay pagos pendientes de revisión!")
        else:
            for p in pagos_pendientes:
                with st.container():
                    col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                    with col_p1:
                        st.write(f"**ID Pago:** {p.get('id_pago')}")
                        st.write(f"**Delegación:** {p.get('id_delegacion')}")
                        st.write(f"**Monto Informado:** ${p.get('monto')}")
                    with col_p2:
                        url_comp = p.get('drive_file_url')
                        if url_comp:
                            st.markdown(f"🔗 [Ver Comprobante en Drive]({url_comp})", unsafe_allow_html=True)
                        st.write(f"**Estado:** `{p.get('estado_pago')}`")
                    with col_p3:
                        if st.button("Aprobar", key=f"ap_{p.get('id_pago')}"):
                            requests.post(API_URL, json={"action": "CAMBIAR_ESTADO_PAGO", "data": {"id_pago": p.get('id_pago'), "nuevo_estado": "APROBADO"}})
                            st.success("¡Aprobado!")
                            st.rerun()
                        if st.button("Rechazar", key=f"rec_{p.get('id_pago')}"):
                            requests.post(API_URL, json={"action": "CAMBIAR_ESTADO_PAGO", "data": {"id_pago": p.get('id_pago'), "nuevo_estado": "RECHAZADO"}})
                            st.warning("Rechazado.")
                            st.rerun()
                    st.markdown("---")

    with subtab2:
        st.markdown("### Resumen de Recaudación")
        if pagos_todos:
            df_pagos = pd.DataFrame(pagos_todos)
            pagos_aprobados = df_pagos[df_pagos['estado_pago'].astype(str).str.upper() == 'APROBADO']
            total_recaudado = pagos_aprobados['monto'].sum() if not pagos_aprobados.empty else 0
            
            st.metric("Total Recaudado (Pagos Aprobados)", f"${total_recaudado:,.2f}")
            st.dataframe(df_pagos, use_container_width=True)
            st.markdown(descargar_excel_html(df_pagos, "historial_pagos"), unsafe_allow_html=True)
        else:
            st.info("No hay registros de pagos cargados.")

# ---------------------------------------------------------
# 4. PAÍSES Y BANCAS DISPONIBLES
# ---------------------------------------------------------
with tab_paises:
    st.subheader("🌍 Control de Disponibilidad de Órganos y Países")
    st.write("En tu Google Sheet, dirigite a la solapa Organos. Aquellas filas cuya Columna E (id_asignacion) aparezca con un guion '-' indican que ese país u órgano todavía no ha sido asignado a ninguna institución.")

# ---------------------------------------------------------
# 5. ALERTAS MÉDICAS
# ---------------------------------------------------------
with tab_medicos:
    st.subheader("🩺 Reporte General de Salud y Alergias")
    
    nominas_medicas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
    
    if nominas_medicas:
        alerta_nominas = [n for n in nominas_medicas if n.get("alergias_medicas") and str(n.get("alergias_medicas")).strip().lower() not in ["ninguna", "-", ""]]
        
        if not alerta_nominas:
            st.success("✅ No hay alertas médicas registradas.")
        else:
            st.warning(f"⚠️ Se encontraron {len(alerta_nominas)} participantes con observaciones médicas:")
            df_alertas = pd.DataFrame(alerta_nominas)
            st.dataframe(df_alertas[["id_delegacion", "nombre", "apellido", "dni", "rol_mnu", "alergias_medicas"]], use_container_width=True)
            st.markdown(descargar_excel_html(df_alertas, "reporte_alertas_medicas"), unsafe_allow_html=True)
    else:
        st.info("No hay participantes cargados en las nóminas todavía.")
