import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Panel de Secretaría - Modelos ONU",
    page_icon="👑",
    layout="wide"
)

API_URL = "https://script.google.com/macros/s/AKfycbwHMPNXP7WizfswDjmTmNvTReNQUy9uvpSTTk-lpsc2DNXQojhg2ssSbyKfPQdPKUoBhQ/exec"

def api_get(action, params=""):
    try:
        url = f"{API_URL}?action={action}{params}"
        res = requests.get(url).json()
        if res.get("status") == "SUCCESS":
            return res.get("data", [])
        return []
    except Exception:
        return []

def descargar_csv_para_excel(df, nombre_archivo):
    df_clean = df.astype(str)
    csv = df_clean.to_csv(index=False).encode('utf-8-sig')
    return st.download_button(
        label=f"📥 Descargar {nombre_archivo} (Compatible con Excel)",
        data=csv,
        file_name=f"{nombre_archivo}.csv",
        mime="text/csv",
        key=f"btn_{nombre_archivo}"
    )

st.title("👑 Panel de Control - Secretaría / Administración")

if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False

if not st.session_state["admin_logueado"]:
    st.markdown("### 🔒 Acceso Restringido al Secretariado")
    with st.form("form_login_admin"):
        pass_ingresada = st.text_input("Contraseña de Administración:", type="password")
        if st.form_submit_button("Ingresar"):
            if pass_ingresada.strip() == "secreta2026":
                st.session_state["admin_logueado"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()

if st.sidebar.button("Cerrar Sesión Admin"):
    st.session_state["admin_logueado"] = False
    st.rerun()

modelos = api_get("GET_MODELOS_ACTIVOS")
if not modelos:
    st.warning("⚠️ No hay modelos activos.")
    st.stop()

dict_modelos = {m["nombre_visible"]: m["id_modelo"] for m in modelos}
modelo_seleccionado = st.sidebar.selectbox("Seleccionar Modelo:", list(dict_modelos.keys()))
id_modelo_actual = dict_modelos[modelo_seleccionado]

st.sidebar.markdown("---")

tab_dash, tab_ficha, tab_auditoria, tab_pagos, tab_paises, tab_medicos, tab_acred = st.tabs([
    "📊 Dashboard", 
    "🏫 Ficha Nominal", 
    "🔍 Auditoría",
    "💰 Pagos", 
    "🌍 Países", 
    "🩺 Médicas",
    "🎫 Control de Acreditación"
])

# 1. DASHBOARD
with tab_dash:
    st.subheader(f"📊 Panel General - {modelo_seleccionado}")
    delegaciones = api_get("GET_TODAS_DELEGACIONES", f"&id_modelo={id_modelo_actual}")
    nominas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Escuelas Registradas", len(delegaciones))
    with col2: st.metric("Participantes en Nómina", len(nominas))
    with col3: st.metric("Modelo Activo", modelo_seleccionado)

# 2. FICHA NOMINAL
with tab_ficha:
    st.subheader("🏫 Ficha Integral por Institución")
    delegaciones_ficha = api_get("GET_TODAS_DELEGACIONES", f"&id_modelo={id_modelo_actual}")
    if delegaciones_ficha:
        opciones_escuelas = {f"[{d.get('id_delegacion')}] {d.get('nombre_colegio')}": d for d in delegaciones_ficha}
        escuela_label = st.selectbox("Seleccionar Institución:", list(opciones_escuelas.keys()))
        escuela = opciones_escuelas[escuela_label]
        id_del = escuela.get("id_delegacion")
        st.write(f"**Responsable:** {escuela.get('docente_apellido_nombre')} | **Email:** {escuela.get('docente_email')}")
        
        nominas_todas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
        registros_escuela = [n for n in nominas_todas if str(n.get("id_delegacion")).strip().upper() == str(id_del).strip().upper()]
        if registros_escuela:
            st.dataframe(pd.DataFrame(registros_escuela)[["rol_mnu", "nombre", "apellido", "dni", "alergias_medicas"]], use_container_width=True)

# 3. AUDITORÍA
with tab_auditoria:
    st.subheader("🔍 Auditoría y Aprobación Final")
    delegaciones_aud = api_get("GET_TODAS_DELEGACIONES", f"&id_modelo={id_modelo_actual}")
    if delegaciones_aud:
        opc_aud = {f"[{d.get('id_delegacion')}] {d.get('nombre_colegio')}": d for d in delegaciones_aud}
        sel_aud_label = st.selectbox("Institución:", list(opc_aud.keys()))
        escuela_aud = opc_aud[sel_aud_label]
        id_del_aud = escuela_aud.get("id_delegacion")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("✅ Aprobar Legajo Completo"):
                res = requests.post(API_URL, json={"action": "APROBAR_LEGAJO_ESCUELA", "data": {"id_delegacion": id_del_aud}}).json()
                if res.get("status") == "SUCCESS": st.success("¡Aprobado!"); st.rerun()
        with col_btn2:
            if st.button("❌ Rechazar Legajo"):
                requests.post(API_URL, json={"action": "RECHAZAR_LEGAJO_ESCUELA", "data": {"id_delegacion": id_del_aud}})
                st.warning("Legajo rechazado.")

# 4. PAGOS
with tab_pagos:
    st.subheader("💰 Gestión de Pagos")
    pagos_pendientes = api_get("GET_PAGOS_PENDIENTES")
    if pagos_pendientes:
        for p in pagos_pendientes:
            st.write(f"**Pago:** {p.get('id_pago')} | **Delegación:** {p.get('id_delegacion')} | **Monto:** ${p.get('monto')} | [Ver Comprobante]({p.get('drive_file_url')})")
            if st.button("Aprobar Pago", key=f"ap_{p.get('id_pago')}"):
                requests.post(API_URL, json={"action": "CAMBIAR_ESTADO_PAGO", "data": {"id_pago": p.get('id_pago'), "nuevo_estado": "APROBADO"}})
                st.success("Aprobado"); st.rerun()

# 5. PAÍSES Y BANCAS
with tab_paises:
    st.subheader("🌍 Países y Bancas Disponibles")
    res_orgs = requests.get(f"{API_URL}?action=GET_ORGANOS_GENERAL").json()
    tabla_organos = res_orgs.get("data", [])
    if tabla_organos:
        df_orgs = pd.DataFrame(tabla_organos).astype(str)
        sin_asignar = df_orgs[df_orgs['id_asignacion'].str.strip().isin(["", "-", "nan", "None"]) | df_orgs['id_asignacion'].isna()]
        st.markdown(f"### 🟢 Disponibles (Sin Asignar): `{len(sin_asignar)}`")
        st.dataframe(sin_asignar[["organo_comite", "pais", "integrantes"]], use_container_width=True)

# 6. ALERTAS MÉDICAS
with tab_medicos:
    st.subheader("🩺 Reporte de Alergias y Salud")
    nominas_medicas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
    if nominas_medicas:
        alertas = [n for n in nominas_medicas if n.get("alergias_medicas") and str(n.get("alergias_medicas")).strip().lower() not in ["ninguna", "-", ""]]
        if alertas:
            st.dataframe(pd.DataFrame(alertas)[["id_delegacion", "nombre", "apellido", "dni", "rol_mnu", "alergias_medicas"]], use_container_width=True)
        else:
            st.success("No hay alertas médicas.")

# 7. CONTROL DE ACREDITACIÓN (NUEVO)
with tab_acred:
    st.subheader("🎫 Control de Acreditaciones en Tiempo Real")
    try:
        res_acred = requests.get(f"{API_URL}?action=GET_ESTADISTICAS_ACREDITACION").json()
        if res_acred.get("status") == "SUCCESS":
            d_acred = res_acred.get("data", {})
            col_a1, col_a2, col_a3 = st.columns(3)
            with col_a1: st.metric("Total en Nóminas", d_acred.get("total_nominados", 0))
            with col_a2: st.metric("Total Acreditados", d_acred.get("total_acreditados", 0))
            with col_a3: st.metric("Porcentaje de Acreditación", f"{d_acred.get('porcentaje', 0)}%")
            
            st.markdown("---")
            st.markdown("### ❌ Participantes Pendientes de Acreditación (Ausentes)")
            no_acred = d_acred.get("no_acreditados", [])
            if no_acred:
                df_no = pd.DataFrame(no_acred).astype(str)
                st.dataframe(df_no[["id_delegacion", "nombre", "apellido", "dni", "rol_mnu"]], use_container_width=True)
                descargar_csv_para_excel(df_no, "participantes_pendientes_acreditacion")
            else:
                st.success("🎉 ¡Todos los participantes se encuentran acreditados!")
    except Exception as e:
        st.error(f"Error al cargar estadísticas: {e}")
