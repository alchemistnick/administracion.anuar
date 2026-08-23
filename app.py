import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Panel de Secretaría - Modelos ONU",
    page_icon="👑",
    layout="wide"
)

API_URL = "https://script.google.com/macros/s/AKfycbx3zjc_Ub_OiItFksgr7VfSI19RduFZPS--SSQ3l4qQJi8qi-w4FXCNmy3xIlZsq3x0KQ/exec"

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

modelos = api_get("GET_MODELOS_ACTIVOS")
if not modelos:
    st.warning("⚠️ No hay modelos activos configurados.")
    st.stop()

dict_modelos = {m["nombre_visible"]: m["id_modelo"] for m in modelos}
modelo_seleccionado = st.sidebar.selectbox("Seleccionar Modelo:", list(dict_modelos.keys()))
id_modelo_actual = dict_modelos[modelo_seleccionado]

st.sidebar.markdown("---")

tab_dash, tab_ficha, tab_auditoria, tab_pagos, tab_paises, tab_medicos = st.tabs([
    "📊 Dashboard y KPIs", 
    "🏫 Ficha Nominal por Escuela", 
    "🔍 Auditoría y Aprobación Final",
    "💰 Gestión de Pagos", 
    "🌍 Países y Bancas", 
    "🩺 Alertas Médicas"
])

# 1. DASHBOARD
with tab_dash:
    st.subheader(f"📊 Panel General - {modelo_seleccionado}")
    delegaciones = api_get("GET_TODAS_DELEGACIONES", f"&id_modelo={id_modelo_actual}")
    nominas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
    pagos = api_get("GET_PAGOS_PENDIENTES")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Escuelas Registradas", len(delegaciones))
    with col2:
        docs_completas = sum(1 for d in delegaciones if str(d.get("estado")).upper() in ["DOCUMENTACION_COMPLETA", "APROBADO_FINAL"])
        st.metric("Doc. Completa / Aprobada", docs_completas)
    with col3: st.metric("Estudiantes en Nómina", len(nominas))
    with col4: st.metric("Pagos Pendientes", len(pagos))

    st.markdown("---")
    st.markdown("### 📋 Listado Rápido de Instituciones")
    if delegaciones:
        df_del = pd.DataFrame(delegaciones).astype(str)
        st.dataframe(df_del, width=None)
        descargar_csv_para_excel(df_del, "escuelas_preinscriptas")
    else:
        st.info("No hay delegaciones registradas todavía.")

# 2. FICHA NOMINAL
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
            df_alumnos = pd.DataFrame(alumnos_escuela).astype(str)
            st.dataframe(df_alumnos[["id_asignacion", "rol_mnu", "nombre", "apellido", "dni", "alergias_medicas"]], width=None)
            descargar_csv_para_excel(df_alumnos, f"nomina_{id_del}")

# 3. AUDITORÍA
with tab_auditoria:
    st.subheader("🔍 Auditoría de Documentación y Aprobación Final")
    delegaciones_aud = api_get("GET_TODAS_DELEGACIONES", f"&id_modelo={id_modelo_actual}")
    
    if not delegaciones_aud:
        st.info("No hay escuelas registradas.")
    else:
        opc_aud = {f"[{d.get('id_delegacion')}] {d.get('nombre_colegio')} (Estado: {d.get('estado')})": d for d in delegaciones_aud}
        sel_aud_label = st.selectbox("Seleccionar Institución a Auditar:", list(opc_aud.keys()), key="select_auditoria")
        escuela_aud = opc_aud[sel_aud_label]
        id_del_aud = escuela_aud.get("id_delegacion")

        st.markdown("---")
        st.write(f"**Institución:** {escuela_aud.get('nombre_colegio')} | **Docente:** {escuela_aud.get('docente_apellido_nombre')} ({escuela_aud.get('docente_email')})")
        st.write(f"**Estado actual:** `{escuela_aud.get('estado', 'REGISTRADO')}`")

        nominas_todas_aud = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
        alumnos_aud = [n for n in nominas_todas_aud if str(n.get("id_delegacion")).strip().upper() == str(id_del_aud).strip().upper()]

        if not alumnos_aud:
            st.warning("⚠️ Esta escuela todavía no ha cargado participantes en su nómina.")
        else:
            st.markdown("### 📋 Nómina y Enlaces a Documentos en Drive")
            for idx, alum in enumerate(alumnos_aud):
                st.markdown(f"**{idx+1}. {alum.get('nombre')} {alum.get('apellido')}** (DNI: {alum.get('dni')}) — *Banca:* {alum.get('rol_mnu')}")
                
                col_enla1, col_enla2 = st.columns(2)
                with col_enla1:
                    ficha_id = alum.get('ficha_medica_id') or alum.get('ficha_id') or "-"
                    if ficha_id and ficha_id != "-":
                        st.markdown(f"📄 [Ver Ficha Médica en Drive](https://drive.google.com/open?id={ficha_id})", unsafe_allow_html=True)
                    else:
                        st.write("📄 Ficha Médica: No adjunta")
                with col_enla2:
                    aut_id = alum.get('autorizacion_id') or alum.get('aut_id') or "-"
                    if aut_id and aut_id != "-":
                        st.markdown(f"📝 [Ver Autorización en Drive](https://drive.google.com/open?id={aut_id})", unsafe_allow_html=True)
                    else:
                        st.write("📝 Autorización: No adjunta")
                st.markdown("---")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button(f"✅ Aprobar Legajo Completo", key=f"btn_aprobar_{id_del_aud}", use_container_width=True):
                    payload_aprobacion = {"action": "APROBAR_LEGAJO_ESCUELA", "data": {"id_delegacion": id_del_aud}}
                    with st.spinner("Aprobando legajo y enviando correo..."):
                        try:
                            res_ap = requests.post(API_URL, json=payload_aprobacion).json()
                            if res_ap.get("status") == "SUCCESS":
                                st.success("¡Legajo aprobado con éxito!")
                                st.rerun()
                            else:
                                st.error(f"Error: {res_ap.get('message')}")
                        except Exception as e:
                            st.error(f"Error de conexión: {e}")

            with col_btn2:
                with st.expander("❌ Rechazar Legajo con Observaciones"):
                    with st.form(key=f"form_rechazo_{id_del_aud}"):
                        motivo_rechazo = st.text_area("Indique el motivo del rechazo o corrección necesaria:")
                        btn_enviar_rechazo = st.form_submit_button("Confirmar Rechazo y Notificar")
                        
                        if btn_enviar_rechazo:
                            if not motivo_rechazo.strip():
                                st.error("Debe ingresar un motivo para el rechazo.")
                            else:
                                payload_rechazo = {
                                    "action": "RECHAZAR_LEGAJO_ESCUELA",
                                    "data": {"id_delegacion": id_del_aud, "motivo": motivo_rechazo}
                                }
                                with st.spinner("Procesando rechazo y enviando correo..."):
                                    try:
                                        res_rec = requests.post(API_URL, json=payload_rechazo).json()
                                        if res_rec.get("status") == "SUCCESS":
                                            st.warning("¡Legajo rechazado y notificado a la escuela correctamente!")
                                            st.rerun()
                                        else:
                                            st.error(f"Error: {res_rec.get('message')}")
                                    except Exception as e:
                                        st.error(f"Error de conexión: {e}")

# 4. PAGOS
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
                        if url_comp: st.markdown(f"🔗 [Ver Comprobante en Drive]({url_comp})", unsafe_allow_html=True)
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
            df_pagos = pd.DataFrame(pagos_todos).astype(str)
            pagos_aprobados = df_pagos[df_pagos['estado_pago'].str.upper() == 'APROBADO']
            total_recaudado = pagos_aprobados['monto'].astype(float).sum() if not pagos_aprobados.empty else 0
            
            st.metric("Total Recaudado (Pagos Aprobados)", f"${total_recaudado:,.2f}")
            st.dataframe(df_pagos, width=None)
            descargar_csv_para_excel(df_pagos, "historial_pagos")
        else:
            st.info("No hay registros de pagos cargados.")

# 5. PAÍSES Y BANCAS
with tab_paises:
    st.subheader("🌍 Control de Disponibilidad de Órganos y Países")
    st.write("En tu Google Sheet, dirigite a la solapa Organos. Aquellas filas cuya Columna E (id_asignacion) aparezca con un guion '-' indican que ese país u órgano todavía no ha sido asignado a ninguna institución.")

# 6. ALERTAS MÉDICAS
with tab_medicos:
    st.subheader("🩺 Reporte General de Salud y Alergias")
    nominas_medicas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
    
    if nominas_medicas:
        alerta_nominas = [n for n in nominas_medicas if n.get("alergias_medicas") and str(n.get("alergias_medicas")).strip().lower() not in ["ninguna", "-", ""]]
        if not alerta_nominas:
            st.success("✅ No hay alertas médicas registradas.")
        else:
            st.warning(f"⚠️ Se encontraron {len(alerta_nominas)} participantes con observaciones médicas:")
            df_alertas = pd.DataFrame(alerta_nominas).astype(str)
            st.dataframe(df_alertas[["id_delegacion", "nombre", "apellido", "dni", "rol_mnu", "alergias_medicas"]], width=None)
            descargar_csv_para_excel(df_alertas, "reporte_alertas_medicas")
    else:
        st.info("No hay participantes cargados en las nóminas todavía.")
