import streamlit as st
import requests
import pandas as pd
import db_firebase

st.stop()  # Detiene app.py para mostrar solo la interfaz de prueba de Firebase

# Ocultar la barra superior, el menú de opciones y el pie de página
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
st.set_page_config(
    page_title="Panel de Secretaría - Modelos ONU",
    page_icon="👑",
    layout="wide")


API_URL = st.secrets ["API_URL"]

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
            if pass_ingresada.strip() == st.secrets ["admin_logueado"]:
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

tab_dash, tab_ficha, tab_auditoria, tab_pagos, tab_paises, tab_medicos, tab_acred = st.tabs([
    "📊 Dashboard y KPIs", 
    "🏫 Ficha Nominal por Escuela", 
    "🔍 Auditoría y Aprobación Final",
    "💰 Gestión de Pagos", 
    "🌍 Países y Bancas", 
    "🩺 Alertas Médicas",
    "🎫 Control de Acreditación"
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
    with col3: st.metric("Participantes en Nómina", len(nominas))
    with col4: st.metric("Pagos Pendientes", len(pagos))

    st.markdown("---")
    st.markdown("### 📋 Listado Rápido de Instituciones")
    if delegaciones:
        df_del = pd.DataFrame(delegaciones).astype(str)
        st.dataframe(df_del, use_container_width=True)
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
        st.markdown("### 👨‍🏫 Docentes Acompañantes Registrados")
        nominas_todas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
        registros_escuela = [n for n in nominas_todas if str(n.get("id_delegacion")).strip().upper() == str(id_del).strip().upper()]
        
        docentes_escuela = [r for r in registros_escuela if r.get("rol_mnu") == "Docente Acompañante"]
        alumnos_escuela = [r for r in registros_escuela if r.get("rol_mnu") != "Docente Acompañante"]

        if not docentes_escuela:
            st.info("La escuela aún no ha registrado docentes acompañantes.")
        else:
            for doc in docentes_escuela:
                st.write(f"- **{doc.get('nombre')} {doc.get('apellido')}** (DNI: {doc.get('dni')}) — {doc.get('alergias_medicas')}")

        st.markdown("### 👥 Estudiantes Registrados en Nómina")
        if not alumnos_escuela:
            st.info("La escuela aún no ha cargado participantes en su nómina.")
        else:
            df_alumnos = pd.DataFrame(alumnos_escuela).astype(str)
            st.dataframe(df_alumnos[["id_asignacion", "rol_mnu", "nombre", "apellido", "dni", "alergias_medicas"]], use_container_width=True)
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
        registros_aud = [n for n in nominas_todas_aud if str(n.get("id_delegacion")).strip().upper() == str(id_del_aud).strip().upper()]

        if not registros_aud:
            st.warning("⚠️ Esta escuela todavía no ha cargado participantes en su nómina.")
        else:
            st.markdown("### 📋 Nómina Completa y Enlaces a Documentos en Drive")
            for idx, reg in enumerate(registros_aud):
                rol_txt = reg.get('rol_mnu')
                st.markdown(f"**{idx+1}. {reg.get('nombre')} {reg.get('apellido')}** (DNI: {reg.get('dni')}) — *Rol/Banca:* {rol_txt}")
                
                col_enla1, col_enla2 = st.columns(2)
                with col_enla1:
                    ficha_id = reg.get('ficha_medica_id') or "-"
                    if ficha_id and ficha_id != "-":
                        st.markdown(f"📄 [Ver Ficha / Constancia en Drive](https://drive.google.com/open?id={ficha_id})", unsafe_allow_html=True)
                    else:
                        st.write("📄 Documento 1: No adjunto")
                with col_enla2:
                    aut_id = reg.get('autorizacion_id') or "-"
                    if aut_id and aut_id != "-":
                        st.markdown(f"📝 [Ver Autorización en Drive](https://drive.google.com/open?id={aut_id})", unsafe_allow_html=True)
                    else:
                        st.write("📝 Documento 2: No adjunto")
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
    
    delegaciones_pagos = api_get("GET_TODAS_DELEGACIONES")
    mapa_colegios = {d.get("id_delegacion"): d.get("nombre_colegio") for d in delegaciones_pagos}
    mapa_responsables = {d.get("id_delegacion"): d.get("docente_apellido_nombre") for d in delegaciones_pagos}

    pagos_pendientes = api_get("GET_PAGOS_PENDIENTES")
    pagos_todos = api_get("GET_TODAS_PAGOS")
    
    subtab1, subtab2 = st.tabs(["⏳ Pagos Pendientes", "✅ Historial de Pagos y Acumulador"])
    
    with subtab1:
        if not pagos_pendientes:
            st.success("🎉 ¡No hay pagos pendientes de revisión!")
        else:
            for p in pagos_pendientes:
                id_del = p.get('id_delegacion')
                nombre_escuela = mapa_colegios.get(id_del, "Institución Desconocida")
                responsable = mapa_responsables.get(id_del, "-")

                with st.container():
                    col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                    with col_p1:
                        st.write(f"**ID Pago:** `{p.get('id_pago')}`")
                        st.write(f"**🏛️ Institución:** {nombre_escuela} (`{id_del}`)")
                        st.write(f"**👤 Responsable:** {responsable}")
                        st.write(f"**💵 Monto Informado:** **${p.get('monto')}**")
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
            df_pagos = pd.DataFrame(pagos_todos).astype(str)
            df_pagos['nombre_colegio'] = df_pagos['id_delegacion'].map(mapa_colegios).fillna("Desconocido")
            
            cols = ['id_pago', 'id_delegacion', 'nombre_colegio', 'monto', 'estado_pago', 'fecha_subida']
            cols_disponibles = [c for c in cols if c in df_pagos.columns]
            
            pagos_aprobados = df_pagos[df_pagos['estado_pago'].str.upper() == 'APROBADO']
            total_recaudado = pagos_aprobados['monto'].astype(float).sum() if not pagos_aprobados.empty else 0
            
            st.metric("Total Recaudado (Pagos Aprobados)", f"${total_recaudado:,.2f}")
            st.dataframe(df_pagos[cols_disponibles], use_container_width=True)
            descargar_csv_para_excel(df_pagos, "historial_pagos")
        else:
            st.info("No hay registros de pagos cargados.")

# 5. PAÍSES Y BANCAS
with tab_paises:
    st.subheader("🌍 Control de Disponibilidad de Órganos y Países")
    
    try:
        res_orgs = requests.get(f"{API_URL}?action=GET_ORGANOS_GENERAL").json()
        tabla_organos = res_orgs.get("data", [])
        
        if tabla_organos:
            df_orgs = pd.DataFrame(tabla_organos).astype(str)
            
            sin_asignar_orgs = df_orgs[
                df_orgs['id_asignacion'].str.strip().isin(["", "-", "nan", "None"]) | 
                df_orgs['id_asignacion'].isna()
            ]
            
            asignados_orgs = df_orgs[
                ~df_orgs['id_asignacion'].str.strip().isin(["", "-", "nan", "None"]) & 
                df_orgs['id_asignacion'].notna()
            ]

            st.markdown(f"### 🟢 Países y Bancas Disponibles / Sin Asignar (Solapa Organos): `{len(sin_asignar_orgs)}`")
            if not sin_asignar_orgs.empty:
                st.dataframe(sin_asignar_orgs[["id_modelo", "organo_comite", "pais", "integrantes"]], use_container_width=True)
                descargar_csv_para_excel(sin_asignar_orgs, "paises_disponibles_organos")
            else:
                st.success("🎉 ¡No hay países libres en la solapa Organos! Todos tienen asignación.")

            st.markdown("---")
            st.markdown(f"### 🔒 Países y Bancas Asignadas: `{len(asignados_orgs)}`")
            if not asignados_orgs.empty:
                st.dataframe(asignados_orgs, use_container_width=True)
                descargar_csv_para_excel(asignados_orgs, "paises_asignados_organos")
            else:
                st.info("Aún no hay registros con ID de asignación en la solapa Organos.")
        else:
            st.info("No se encontraron datos en la solapa Organos de tu Google Sheet.")
    except Exception as e:
        st.error(f"Error al cargar el control de órganos: {e}")

# 6. ALERTAS MÉDICAS
with tab_medicos:
    st.subheader("🩺 Reporte General de Salud y Alergias")
    nominas_medicas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")
    
    if nominas_medicas:
        alerta_nominas = [n for n in nominas_medicas if n.get("alergias_medicas") and str(n.get("alergias_medicas")).strip().lower() not in ["ninguna", "-", ""]]
        if not alerta_nominas:
            st.success("✅ No hay alertas médicas registradas.")
        else:
            st.warning(f"⚠️ Se encontraron {len(alerta_nominas)} registros con observaciones médicas o de contacto:")
            df_alertas = pd.DataFrame(alerta_nominas).astype(str)
            st.dataframe(df_alertas[["id_delegacion", "nombre", "apellido", "dni", "rol_mnu", "alergias_medicas"]], use_container_width=True)
            descargar_csv_para_excel(df_alertas, "reporte_alertas_medicas")
    else:
        st.info("No hay participantes cargados en las nóminas todavía.")

# 7. CONTROL DE ACREDITACIÓN (FILTRADO POR MODELO ACTUAL)
with tab_acred:
    st.subheader(f"🎫 Control de Acreditaciones - {modelo_seleccionado}")
    try:
        res_acred = requests.get(f"{API_URL}?action=GET_ESTADISTICAS_ACREDITACION&id_modelo={id_modelo_actual}").json()
        if res_acred.get("status") == "SUCCESS":
            d_acred = res_acred.get("data", {})
            col_a1, col_a2, col_a3 = st.columns(3)
            with col_a1: st.metric("Total en Nóminas", d_acred.get("total_nominados", 0))
            with col_a2: st.metric("Total Acreditados", d_acred.get("total_acreditados", 0))
            with col_a3: st.metric("Porcentaje de Acreditación", f"{d_acred.get('porcentaje', 0)}%")
            
            st.markdown("---")
            st.markdown("### ❌ Participantes Pendientes de Acreditación (Ausentes en este Modelo)")
            no_acred = d_acred.get("no_acreditados", [])
            if no_acred:
                df_no = pd.DataFrame(no_acred).astype(str)
                st.dataframe(df_no[["id_delegacion", "nombre", "apellido", "dni", "rol_mnu"]], use_container_width=True)
                descargar_csv_para_excel(df_no, f"pendientes_acreditacion_{id_modelo_actual}")
            else:
                st.success("🎉 ¡Todos los participantes de este modelo se encuentran acreditados!")
    except Exception as e:
        st.error(f"Error al cargar estadísticas de acreditación: {e}")
