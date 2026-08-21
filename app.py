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

# =========================================================
# FUNCIONES DE CACHÉ GLOBALES (BLINDADAS CONTRA ERRORES)
# =========================================================

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
def cargar_datos_sorteo(id_mod):
    try:
        r_del = requests.get(f"{API_URL}?action=GET_DELEGACIONES_APROBADAS&id_modelo={id_mod}").json().get("data", [])
        r_pai = requests.get(f"{API_URL}?action=GET_PAISES_MATRIZ&id_modelo={id_mod}").json().get("data", [])
        r_org = requests.get(f"{API_URL}?action=GET_ORGANOS&id_modelo={id_mod}").json().get("data", [])
        r_mod = requests.get(f"{API_URL}?action=GET_MODALIDADES_MODELO&id_modelo={id_mod}").json().get("data", [])
        return r_del, r_pai, r_org, r_mod
    except Exception:
        return [], [], [], []

@st.cache_data(ttl=30)
def cargar_todas_nominas_cached(id_mod):
    try:
        res = requests.get(f"{API_URL}?action=GET_TODAS_NOMINAS&id_modelo={id_mod}").json()
        return res.get("data", [])
    except Exception:
        return []

@st.cache_data(ttl=10)
def cargar_asignaciones_escuela_cached(id_del):
    try:
        res = requests.get(f"{API_URL}?action=GET_ASIGNACIONES_DELEGACION&id_delegacion={id_del}").json()
        return res.get("data", [])
    except Exception:
        return []

# =========================================================
# INICIALIZACIÓN DE LA APP
# =========================================================

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
            "2. Asignación Automática de Sorteo",
            "3. Nómina General de Participantes",
            "4. Búsqueda Rápida por DNI"
        ]
    )

    # ---------------------------------------------------------
    # MÓDULO 0: DASHBOARD Y CUADRO DE MÉTRICAS DEL EVENTO
    # ---------------------------------------------------------
    if menu == "📊 Dashboard & Estado del Modelo":
        st.subheader(f"📈 Estado General del Evento - {modelo_seleccionado}")
        
        with st.spinner("Cargando métricas en tiempo real..."):
            escuelas_aprobadas, _, organos_matriz, _ = cargar_datos_sorteo(id_modelo_actual)
            todas_nominas = cargar_todas_nominas_cached(id_modelo_actual)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("🏫 Escuelas Preinscriptas Aprobadas", len(escuelas_aprobadas))
        with m2:
            tot_cupos = sum([int(e.get("cupos_solicitados", 0)) for e in escuelas_aprobadas if str(e.get("cupos_solicitados", "0")).isdigit()])
            st.metric("👥 Cupos Estudiantiles Aprobados", tot_cupos)
        with m3:
            st.metric("👤 Participantes Cargados", len(todas_nominas))
        with m4:
            fichas_ok = sum([1 for n in todas_nominas if n.get("drive_ficha_id") and str(n.get("drive_ficha_id")).strip() != "-"])
            st.metric("📄 Fichas Médicas Recibidas", fichas_ok)

        st.markdown("---")
        st.markdown("### 🏛️ Matriz de Representación: Países y Cupos por Órgano / Comité")

        if not organos_matriz:
            st.info("No hay información de la matriz de órganos cargada en la pestaña ORGANOS para este modelo.")
        else:
            df_organos = pd.DataFrame(organos_matriz)
            if "integrantes_totales" in df_organos.columns:
                df_organos["integrantes_totales"] = pd.to_numeric(df_organos["integrantes_totales"], errors='coerce').fillna(1)
                
                resumen_organos = df_organos.groupby("organo_comite").agg(
                    Cantidad_Paises=("pais", "nunique"),
                    Total_Delegados=("integrantes_totales", "sum")
                ).reset_index()

                resumen_organos.columns = ["Órgano / Comité", "Paises Representados", "Cupos / Delegados Totales"]

                col_t1, col_t2 = st.columns([2, 1])
                with col_t1:
                    st.dataframe(resumen_organos, use_container_width=True, hide_index=True)
                with col_t2:
                    st.markdown("#### 📊 Distribución de Cupos")
                    for _, row in resumen_organos.iterrows():
                        st.write(f"• **{row['Órgano / Comité']}**: {row['Paises Representados']} países ({int(row['Cupos / Delegados Totales'])} delegados)")

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
                    st.success(f"No hay comprobantes pendientes de revisión para {modelo_seleccionado}.")
                else:
                    st.info(f"Se encontraron **{len(pagos_filtrados)}** comprobantes pendientes de acreditación.")
                    for pago in pagos_filtrados:
                        with st.expander(f"💳 Pago {pago.get('id_pago', '-')} | Delegación: {pago.get('id_delegacion', '-')} | Monto: ${pago.get('monto', 0)}"):
                            col_a, col_b = st.columns([2, 1])
                            with col_a:
                                st.write(f"**Fecha de Subida:** {pago.get('fecha_subida', '-')}")
                                if pago.get('drive_file_url') and pago['drive_file_url'] != "-":
                                    st.markdown(f"[📄 **Ver Comprobante Adjunto en Drive**]({pago['drive_file_url']})", unsafe_allow_html=True)
                            
                            with col_b:
                                if st.button("✅ APROBAR PAGO", key=f"app_{pago.get('id_pago')}"):
                                    payload = {
                                        "action": "CAMBIAR_ESTADO_PAGO",
                                        "usuario": "ADMIN",
                                        "data": {"id_pago": pago.get('id_pago'), "nuevo_estado": "APROBADO"}
                                    }
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.cache_data.clear()
                                        st.success("Pago Aprobado con Éxito")
                                        st.rerun()

                                if st.button("❌ RECHAZAR PAGO", key=f"rej_{pago.get('id_pago')}"):
                                    payload = {
                                        "action": "CAMBIAR_ESTADO_PAGO",
                                        "usuario": "ADMIN",
                                        "data": {"id_pago": pago.get('id_pago'), "nuevo_estado": "RECHAZADO"}
                                    }
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.cache_data.clear()
                                        st.warning("Pago Rechazado")
                                        st.rerun()
            except Exception as e:
                st.error(f"Error al conectar con la base de datos: {e}")

        with tab_modificaciones:
            try:
                res_mod = requests.get(f"{API_URL}?action=GET_MODIFICACIONES_PENDIENTES").json()
                pendientes_mod = res_mod.get("data", [])
                
                pendientes_filtrados = [d for d in pendientes_mod if d.get("id_modelo") == id_modelo_actual or not d.get("id_modelo")]
                
                if not pendientes_filtrados:
                    st.success("No hay solicitudes de modificación de cupos pendientes.")
                else:
                    st.warning(f"Hay **{len(pendientes_filtrados)}** solicitudes de cambio en espera de validación:")
                    
                    for esc in pendientes_filtrados:
                        with st.expander(f"🏫 {esc.get('nombre_colegio')} ({esc.get('id_delegacion')}) - Solicitud de Cambio"):
                            st.write(f"**Docente Responsable:** {esc.get('docente_cargo')} ({esc.get('email_contacto')}) | Teléfono: {esc.get('telefono_contacto')}")
                            
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
                            st.write(f"• **Detalle Desglose:** {nuevo_desglose}")
                            
                            col_m1, col_m2 = st.columns(2)
                            with col_m1:
                                if st.button("✅ APROBAR MODIFICACIÓN", key=f"app_mod_{esc.get('id_delegacion')}"):
                                    payload = {
                                        "action": "RESPONDER_MODIFICACION_PREINSCRIPCION",
                                        "usuario": "ADMIN",
                                        "data": {
                                            "id_delegacion": esc.get('id_delegacion'),
                                            "aprobar": True,
                                            "nuevos_cupos": nuevos_cupos,
                                            "nuevo_desglose": nuevo_desglose,
                                            "docentes_acompanantes": docentes_acomp
                                        }
                                    }
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.cache_data.clear()
                                        st.success("Modificación Aprobada.")
                                        st.rerun()

                            with col_m2:
                                if st.button("❌ RECHAZAR CAMBIO", key=f"rej_mod_{esc.get('id_delegacion')}"):
                                    payload = {
                                        "action": "RESPONDER_MODIFICACION_PREINSCRIPCION",
                                        "usuario": "ADMIN",
                                        "data": {
                                            "id_delegacion": esc.get('id_delegacion'),
                                            "aprobar": False
                                        }
                                    }
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.cache_data.clear()
                                        st.info("Modificación Rechazada.")
                                        st.rerun()
            except Exception as e:
                st.error(f"Error al consultar solicitudes de modificación: {e}")

    # ---------------------------------------------------------
    # MÓDULO 2: ASIGNACIÓN RÁPIDA Y STRICTA DE PAÍSES (CORREGIDO)
    # ---------------------------------------------------------
    elif menu == "2. Asignación Automática de Sorteo":
        st.subheader(f"⚡ Asignación Directa y Validación de Cupos - {modelo_seleccionado}")

        with st.spinner("Sincronizando matriz de sorteo..."):
            escuelas_aprobadas, lista_paises, organos_matriz, modalidades_evento = cargar_datos_sorteo(id_modelo_actual)

        if not escuelas_aprobadas:
            st.warning("No hay escuelas con pagos aprobados disponibles para asignar.")
        elif not lista_paises:
            st.warning("⚠️ No se encontraron países en la solapa ORGANOS para este modelo.")
        else:
            col_a, col_b = st.columns(2)
            
            with col_a:
                opciones_del = {f"{d.get('id_delegacion', 'DEL')} - {d.get('nombre_colegio', 'Escuela')}": d for d in escuelas_aprobadas if d.get('id_delegacion')}
                escuela_sel_label = st.selectbox("1. Escuela que realizó el Sorteo:", list(opciones_del.keys()))
                escuela_actual = opciones_del[escuela_sel_label]
            
            with col_b:
                lista_paises_valida = [p for p in lista_paises if p]
                pais_seleccionado = st.selectbox("2. País a Asignar:", sorted(lista_paises_valida))

            st.markdown("---")
            
            cupos_autorizados = int(escuela_actual.get("cupos_solicitados", 0)) if str(escuela_actual.get("cupos_solicitados", "0")).isdigit() else 0
            desglose_str = str(escuela_actual.get("desglose_modalidades", ""))
            
            modalidades_escuela = {}
            if desglose_str:
                items = desglose_str.split("|")
                for it in items:
                    if ":" in it:
                        k, v = it.split(":")
                        cant = int(v.strip()) if v.strip().isdigit() else 0
                        if cant > 0:
                            modalidades_escuela[k.strip().lower()] = cant

            escuela_tiene_cs = False
            escuela_tiene_eco = False
            escuela_tiene_davos = False
            escuela_tiene_prensa = False

            dict_modalidades_config = {str(m.get("clave_modalidad", "")).strip().lower(): m for m in modalidades_evento}

            for clave_mod in modalidades_escuela.keys():
                config_mod = dict_modalidades_config.get(clave_mod, {})
                etiqueta = str(config_mod.get("etiqueta_visible", "")).lower()
                clave_lower = str(clave_mod).lower()

                if "cs" in clave_lower or "consejo" in etiqueta or "con cs" in etiqueta:
                    if "sin cs" not in etiqueta or "seco_cs" in clave_lower or "9" in clave_lower:
                        escuela_tiene_cs = True
                
                if "eco" in clave_lower or "ecosoc" in etiqueta or "con ecosoc" in etiqueta:
                    if "sin ecosoc" not in etiqueta and "sin_ecosoc" not in clave_lower:
                        escuela_tiene_eco = True

                if "davos" in clave_lower or "davos" in etiqueta:
                    escuela_tiene_davos = True

                if "prensa" in clave_lower or "prensa" in etiqueta:
                    escuela_tiene_prensa = True

            composicion_pais = [
                o for o in organos_matriz 
                if str(o.get('pais', '')).strip().lower() == str(pais_seleccionado).strip().lower()
            ]
            
            st.markdown(f"#### 🔎 Análisis de Viabilidad: **{pais_seleccionado}** ➔ **{escuela_actual.get('nombre_colegio', '')}**")
            
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                st.info(f"📋 **Modalidades contratadas:** `{desglose_str}`")
            with col_e2:
                st.info(f"👥 **Cupos Totales Autorizados:** {cupos_autorizados} delegados")

            bloqueos_criticos = []
            tot_cupos_pais = 0

            if composicion_pais:
                st.markdown("##### Comités requeridos por este país:")
                for c in composicion_pais:
                    cupos = int(c.get('integrantes_totales', 1)) if str(c.get('integrantes_totales', '1')).isdigit() else 1
                    organo_nombre = str(c.get('organo_comite', '')).strip()
                    organo_lower = organo_nombre.lower()
                    tot_cupos_pais += cupos
                    
                    st.write(f"• **{organo_nombre}**: {cupos} delegado(s)")

                    if ("consejo de seguridad" in organo_lower or "cs" in organo_lower) and "ecosoc" not in organo_lower:
                        if not escuela_tiene_cs:
                            bloqueos_criticos.append(f"⛔ **RESTRICCIÓN:** {pais_seleccionado} requiere asiento en **{organo_nombre}**, pero la escuela NO compró ninguna modalidad con Consejo de Seguridad.")
                    
                    if "ecosoc" in organo_lower:
                        if not escuela_tiene_eco:
                            bloqueos_criticos.append(f"⛔ **RESTRICCIÓN:** {pais_seleccionado} requiere asiento en **{organo_nombre}**, pero la escuela NO compró ninguna modalidad con ECOSOC.")

                    if "davos" in organo_lower and not escuela_tiene_davos:
                        bloqueos_criticos.append(f"⛔ **RESTRICCIÓN:** {pais_seleccionado} pertenece al **Foro de Davos**, y la escuela no preinscribió cupos para Davos.")

                    if "prensa" in organo_lower and not escuela_tiene_prensa:
                        bloqueos_criticos.append(f"⛔ **RESTRICCIÓN:** {pais_seleccionado} requiere **Comité de Prensa**, no contratado por la escuela.")

                if tot_cupos_pais > cupos_autorizados:
                    bloqueos_criticos.append(f"⛔ **EXCESO DE CUPOS:** El país requiere **{tot_cupos_pais} integrantes**, pero el colegio solo dispone de **{cupos_autorizados} cupos**.")

            if bloqueos_criticos:
                for b in bloqueos_criticos:
                    st.error(b)
            else:
                st.success("✅ **Compatibilidad Verificada:** La escuela cuenta con las modalidades y cupos necesarios para este país.")

            puedo_asignar = len(bloqueos_criticos) == 0

            if st.button(f"🚀 ASIGNAR {str(pais_seleccionado).upper()}", disabled=not puedo_asignar):
                payload = {
                    "action": "ASIGNAR_PAIS_AUTOMATICO_DESDE_MATRIZ",
                    "usuario": "ADMIN",
                    "data": {
                        "id_modelo": id_modelo_actual,
                        "id_delegacion": escuela_actual.get('id_delegacion'),
                        "pais": pais_seleccionado
                    }
                }
                with st.spinner("Procesando asignación..."):
                    res = requests.post(API_URL, json=payload).json()
                    if res.get("status") == "SUCCESS":
                        st.cache_data.clear()
                        st.balloons()
                        st.success(f"🎉 ¡**{pais_seleccionado}** ({res.get('cupos_agregados')} cupos) fue asignado a {escuela_actual.get('nombre_colegio')}!")
                        st.rerun()
                    else:
                        st.error(f"Error del servidor: {res.get('message')}")

            st.markdown("---")
            st.markdown("##### 📋 Asignaciones actuales de esta escuela:")
            
            asig_list = cargar_asignaciones_escuela_cached(escuela_actual.get('id_delegacion'))
            if asig_list:
                paises_resumen = {}
                for a in asig_list:
                    p = a.get('pais')
                    paises_resumen[p] = paises_resumen.get(p, 0) + 1
                for p_k, p_v in paises_resumen.items():
                    st.write(f"• **{p_k}**: {p_v} lugares asignados.")
            else:
                st.caption("Esta escuela aún no tiene países asignados.")

    # ---------------------------------------------------------
    # MÓDULO 3: SOLAPA DEDUCTIVA Y COMPLETA DE NÓMINA GENERAL
    # ---------------------------------------------------------
    elif menu == "3. Nómina General de Participantes":
        st.subheader(f"📋 Nómina Consolidada de Participantes - {modelo_seleccionado}")
        
        todas_nominas = cargar_todas_nominas_cached(id_modelo_actual)

        if not todas_nominas:
            st.info("Aún no hay participantes cargados en la base de datos para este modelo.")
        else:
            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                filtro_busqueda = st.text_input("🔍 Filtrar por Nombre, Apellido, DNI o Escuela:")
            with col_f2:
                filtro_doc = st.selectbox("Filtrar por Estado de Documentación:", ["Todos", "Ficha Médica Pendiente", "Autorización Pendiente", "Documentación Completa"])

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
                    "Rol / Representación": n.get("rol_mnu", "-"),
                    "Ficha Médica": "✅ OK" if ficha_ok else "❌ Pendiente",
                    "Autorización Imagen": "✅ OK" if aut_ok else "❌ Pendiente",
                    "Alergias / Cuidados Médicos": n.get("alergias_medicas", "Ninguna")
                })

            st.markdown(f"**Mostrando {len(lista_procesada)} de {len(todas_nominas)} participantes.**")
            st.dataframe(pd.DataFrame(lista_procesada), use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # MÓDULO 4: BÚSQUEDA RÁPIDA POR DNI / ALUMNO
    # ---------------------------------------------------------
    elif menu == "4. Búsqueda Rápida por DNI":
        st.subheader(f"🔍 Buscador Global de Participantes - {modelo_seleccionado}")
        
        busqueda = st.text_input("Ingresá el DNI, Nombre, Apellido o Código de Delegación (Ej: DEL-001):")
        
        if busqueda:
            todas_nominas = cargar_todas_nominas_cached(id_modelo_actual)
            
            query = busqueda.strip().lower()
            resultados = [
                n for n in todas_nominas 
                if query in str(n.get("dni", "")).lower() 
                or query in str(n.get("nombre", "")).lower() 
                or query in str(n.get("apellido", "")).lower()
                or query in str(n.get("nombre_completo", "")).lower() 
                or query in str(n.get("id_delegacion", "")).lower()
            ]
            
            if not resultados:
                st.warning(f"No se encontraron participantes que coincidan con '{busqueda}'.")
            else:
                st.success(f"Se encontraron **{len(resultados)}** coincidencia(s):")
                
                for r in resultados:
                    nombre_mostrar = f"{r.get('nombre', '')} {r.get('apellido', '')}".strip() or r.get("nombre_completo", "")
                    with st.expander(f"👤 {nombre_mostrar} | DNI: {r.get('dni', '-')} | Escuela: {r.get('id_delegacion', '-')}"):
                        st.write(f"**Rol / Comisión:** {r.get('rol_mnu', '-')}")
                        st.write(f"**Indicaciones Médicas / Alergias:** {r.get('alergias_medicas', 'Ninguna')}")
                        
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            ficha_id = r.get("drive_ficha_id")
                            if ficha_id and str(ficha_id).strip() != "-":
                                st.markdown(f"[📄 Ver Ficha Médica en Drive](https://drive.google.com/file/d/{ficha_id}/view)", unsafe_allow_html=True)
                            else:
                                st.caption("Ficha médica no adjuntada.")
                                
                        with col_f2:
                            aut_id = r.get("drive_autorizacion_id")
                            if aut_id and str(aut_id).strip() != "-":
                                st.markdown(f"[📄 Ver Autorización en Drive](https://drive.google.com/file/d/{aut_id}/view)", unsafe_allow_html=True)
                            else:
                                st.caption("Autorización de imagen no adjuntada.")

elif admin_pass:
    st.error("🔒 Contraseña incorrecta. Acceso denegado al Panel del Secretariado.")
else:
    st.warning("👈 Por favor ingresá la contraseña del Secretariado en el menú lateral para acceder.")
