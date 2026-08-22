import streamlit as st
import requests
import json
import pandas as pd

st.set_page_config(
    page_title="Secretariado - Control Interno MNU",
    page_icon="🛡️",
    layout="wide"
)

API_URL = "https://script.google.com/macros/s/AKfycbzCVDquLKvY64UMPLtZ6brcuC_1817FHCSvyVbOBVCAGhBA9F0KFiP31OMNMUfwDOHJ7Q/exec"

@st.cache_data(ttl=60)
def cargar_modelos_activos():
    try:
        res = requests.get(f"{API_URL}?action=GET_MODELOS_ACTIVOS").json()
        if res.get("status") == "SUCCESS":
            modelos = res.get("data", [])
            return {m.get("nombre_visible", "Modelo"): m.get("id_modelo") for m in modelos if m.get("id_modelo")}
        return {}
    except Exception:
        return {}

@st.cache_data(ttl=30)
def cargar_todas_nominas_cached(id_mod):
    try:
        res = requests.get(f"{API_URL}?action=GET_TODAS_NOMINAS&id_modelo={id_mod}").json()
        return res.get("data", [])
    except Exception:
        return []

@st.cache_data(ttl=30)
def cargar_escuelas_aprobadas_cached(id_mod):
    try:
        res = requests.get(f"{API_URL}?action=GET_DELEGACIONES_APROBADAS&id_modelo={id_mod}").json()
        return res.get("data", [])
    except Exception:
        return []

st.title("🛡️ Panel Interno del Secretariado - Control y Gestión Global")

CONFIG_MODELOS = cargar_modelos_activos()

st.sidebar.markdown("### 🌐 Selección de Evento")

if not CONFIG_MODELOS:
    st.sidebar.warning("⚠️ No hay modelos activos configurados en la planilla.")
    st.stop()
else:
    modelo_seleccionado = st.sidebar.selectbox("Elegí el Modelo a Auditar:", list(CONFIG_MODELOS.keys()))
    id_modelo_actual = CONFIG_MODELOS[modelo_seleccionado]

st.sidebar.markdown("---")

admin_pass = st.sidebar.text_input("🔐 Contraseña Secretariado", type="password")

if admin_pass == "Secretaria2026":
    st.sidebar.success("Acceso Autorizado")
    
    menu = st.sidebar.radio(
        "Módulos de Gestión",
        [
            "📊 Dashboard & Estado del Modelo",
            "1. Revisión de Pagos y Modificaciones", 
            "2. Nómina General de Participantes",
            "3. Búsqueda Rápida por DNI"
        ]
    )

    # ---------------------------------------------------------
    # MÓDULO 0: DASHBOARD
    # ---------------------------------------------------------
    if menu == "📊 Dashboard & Estado del Modelo":
        st.subheader(f"📈 Estado General del Evento - {modelo_seleccionado}")
        
        with st.spinner("Cargando métricas..."):
            escuelas_aprobadas = cargar_escuelas_aprobadas_cached(id_modelo_actual)
            todas_nominas = cargar_todas_nominas_cached(id_modelo_actual)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("🏫 Escuelas Aprobadas", len(escuelas_aprobadas))
        with m2:
            tot_cupos = sum([int(e.get("cupos_solicitados", 0)) for e in escuelas_aprobadas if str(e.get("cupos_solicitados", "0")).isdigit()])
            st.metric("👥 Cupos Solicitados", tot_cupos)
        with m3:
            st.metric("👤 Participantes Cargados", len(todas_nominas))
        with m4:
            fichas_ok = sum([1 for n in todas_nominas if n.get("drive_ficha_id") and str(n.get("drive_ficha_id")).strip() != "-"])
            st.metric("📄 Fichas Médicas Recibidas", fichas_ok)

        st.markdown("---")
        st.info("ℹ️ Para asignar países a las escuelas, cargá las filas directamente en la solapa **`ASIGNACIONES`** de tu Google Sheets. El portal de los docentes las mostrará automáticamente.")

    # ---------------------------------------------------------
    # MÓDULO 1: REVISIÓN DE PAGOS Y MODIFICACIONES
    # ---------------------------------------------------------
    elif menu == "1. Revisión de Pagos y Modificaciones":
        st.subheader(f"Auditoría General - {modelo_seleccionado}")
        tab_pagos, tab_modificaciones = st.tabs(["💳 Comprobantes de Pago", "✏️ Solicitudes de Cambio de Cupos"])
        
        with tab_pagos:
            try:
                res = requests.get(f"{API_URL}?action=GET_PAGOS_PENDIENTES").json()
                pagos = res.get("data", [])
                pagos_filtrados = [p for p in pagos if p.get("id_modelo") == id_modelo_actual or not p.get("id_modelo")]
                
                if not pagos_filtrados:
                    st.success(f"No hay comprobantes pendientes para {modelo_seleccionado}.")
                else:
                    for pago in pagos_filtrados:
                        with st.expander(f"💳 Pago {pago.get('id_pago', '-')} | Delegación: {pago.get('id_delegacion', '-')} | Monto: ${pago.get('monto', 0)}"):
                            col_a, col_b = st.columns([2, 1])
                            with col_a:
                                st.write(f"**Fecha:** {pago.get('fecha_subida', '-')}")
                                if pago.get('drive_file_url') and pago['drive_file_url'] != "-":
                                    st.markdown(f"[📄 **Ver Comprobante**]({pago['drive_file_url']})", unsafe_allow_html=True)
                            with col_b:
                                if st.button("✅ APROBAR PAGO", key=f"app_{pago.get('id_pago')}"):
                                    payload = {"action": "CAMBIAR_ESTADO_PAGO", "usuario": "ADMIN", "data": {"id_pago": pago.get('id_pago'), "nuevo_estado": "APROBADO"}}
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.cache_data.clear()
                                        st.success("Aprobado")
                                        st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        with tab_modificaciones:
            try:
                res_mod = requests.get(f"{API_URL}?action=GET_MODIFICACIONES_PENDIENTES").json()
                pendientes_mod = res_mod.get("data", [])
                pendientes_filtrados = [d for d in pendientes_mod if d.get("id_modelo") == id_modelo_actual or not d.get("id_modelo")]
                
                if not pendientes_filtrados:
                    st.success("No hay solicitudes pendientes.")
                else:
                    for esc in pendientes_filtrados:
                        with st.expander(f"🏫 {esc.get('nombre_colegio')} ({esc.get('id_delegacion')})"):
                            st.write(f"**Docente Cargo:** {esc.get('docente_apellido_nombre')} ({esc.get('docente_email')}) | Tel: {esc.get('docente_telefono')}")
                            st.write(f"**Dirección Institucional:** {esc.get('direccion_escuela')}")
                            
                            propuesta_raw = esc.get("propuesta_modificacion", "{}")
                            try:
                                prop = json.loads(propuesta_raw)
                            except Exception:
                                prop = {}
                            
                            nuevos_cupos = prop.get("nuevos_cupos", esc.get("cupos_solicitados"))
                            nuevo_desglose = prop.get("nuevo_desglose", esc.get("desglose_modalidades"))
                            docentes_acomp = prop.get("docentes_acompanantes", esc.get("docentes_acompanantes"))

                            st.write(f"• **Nuevos Cupos Estudiantes:** {nuevos_cupos}")
                            st.write(f"• **Nuevos Docentes Acompañantes:** {docentes_acomp}")
                            st.write(f"• **Desglose:** {nuevo_desglose}")
                            
                            col_m1, col_m2 = st.columns(2)
                            with col_m1:
                                if st.button("✅ APROBAR MODIFICACIÓN", key=f"app_mod_{esc.get('id_delegacion')}"):
                                    payload = {"action": "RESPONDER_MODIFICACION_PREINSCRIPCION", "usuario": "ADMIN", "data": {"id_delegacion": esc.get('id_delegacion'), "aprobar": True, "nuevos_cupos": nuevos_cupos, "nuevo_desglose": nuevo_desglose, "docentes_acompanantes": docentes_acomp}}
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.cache_data.clear()
                                        st.success("Aprobado")
                                        st.rerun()

                            with col_m2:
                                if st.button("❌ RECHAZAR CAMBIO", key=f"rej_mod_{esc.get('id_delegacion')}"):
                                    payload = {"action": "RESPONDER_MODIFICACION_PREINSCRIPCION", "usuario": "ADMIN", "data": {"id_delegacion": esc.get('id_delegacion'), "aprobar": False}}
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.cache_data.clear()
                                        st.info("Rechazado")
                                        st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # ---------------------------------------------------------
    # MÓDULO 2: NÓMINA GENERAL
    # ---------------------------------------------------------
    elif menu == "2. Nómina General de Participantes":
        st.subheader(f"📋 Nómina Consolidada de Participantes - {modelo_seleccionado}")
        todas_nominas = cargar_todas_nominas_cached(id_modelo_actual)

        if not todas_nominas:
            st.info("Aún no hay participantes cargados.")
        else:
            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                filtro_busqueda = st.text_input("🔍 Filtrar por Nombre, Apellido, DNI o Escuela:")
            with col_f2:
                filtro_doc = st.selectbox("Estado Documentación:", ["Todos", "Ficha Médica Pendiente", "Autorización Pendiente", "Documentación Completa"])

            lista_procesada = []
            for n in todas_nominas:
                ficha_ok = n.get("drive_ficha_id") and str(n.get("drive_ficha_id")).strip() != "-"
                aut_ok = n.get("drive_autorizacion_id") and str(n.get("drive_autorizacion_id")).strip() != "-"
                
                if filtro_doc == "Ficha Médica Pendiente" and ficha_ok:
                    continue
                if filtro_doc == "Autorización Pendiente" and aut_ok:
                    continue
                if filtro_doc == "Documentación Completa" and (not ficha_ok or not aut_ok):
                    continue

                nom_comp = f"{n.get('nombre', '')} {n.get('apellido', '')}".strip() or n.get("nombre_completo", "")
                query = filtro_busqueda.strip().lower()
                if query:
                    if not (query in nom_comp.lower() or query in str(n.get("dni", "")).lower() or query in str(n.get("id_delegacion", "")).lower()):
                        continue

                lista_procesada.append({
                    "ID Delegado": n.get("id_delegado", "-"),
                    "Escuela / ID": n.get("id_delegacion", "-"),
                    "Nombre": n.get("nombre", "-"),
                    "Apellido": n.get("apellido", "-"),
                    "DNI": n.get("dni", "-"),
                    "Rol": n.get("rol_mnu", "-"),
                    "Ficha Médica": "✅ OK" if ficha_ok else "❌ Pendiente",
                    "Autorización Imagen": "✅ OK" if aut_ok else "❌ Pendiente"
                })

            st.dataframe(pd.DataFrame(lista_procesada), use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # MÓDULO 3: BÚSQUEDA RÁPIDA POR DNI
    # ---------------------------------------------------------
    elif menu == "3. Búsqueda Rápida por DNI":
        st.subheader(f"🔍 Buscador Global de Participantes - {modelo_seleccionado}")
        busqueda = st.text_input("Ingresá DNI, Nombre, Apellido o ID Delegación:")
        
        if busqueda:
            todas_nominas = cargar_todas_nominas_cached(id_modelo_actual)
            query = busqueda.strip().lower()
            resultados = [n for n in todas_nominas if query in str(n.get("dni", "")).lower() or query in str(n.get("nombre", "")).lower() or query in str(n.get("apellido", "")).lower() or query in str(n.get("id_delegacion", "")).lower()]
            
            if not resultados:
                st.warning(f"No hay coincidencias para '{busqueda}'.")
            else:
                for r in resultados:
                    nombre_mostrar = f"{r.get('nombre', '')} {r.get('apellido', '')}".strip() or r.get("nombre_completo", "")
                    with st.expander(f"👤 {nombre_mostrar} | DNI: {r.get('dni', '-')} | Escuela: {r.get('id_delegacion', '-')}"):
                        st.write(f"**Rol:** {r.get('rol_mnu', '-')}")
                        st.write(f"**Alergias:** {r.get('alergias_medicas', 'Ninguna')}")

elif admin_pass:
    st.error("🔒 Contraseña incorrecta.")
else:
    st.warning("👈 Por favor ingresá la contraseña del Secretariado en el menú lateral.")
