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

st.title("🛡️ Panel Interno del Secretariado - Control y Gestión Global")

@st.cache_data(ttl=30)
def cargar_modelos_activos():
    try:
        res = requests.get(f"{API_URL}?action=GET_MODELOS_ACTIVOS").json()
        if res.get("status") == "SUCCESS":
            modelos = res.get("data", [])
            return {m["nombre_visible"]: m["id_modelo"] for m in modelos}
        return {}
    except Exception:
        return {}

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
            try:
                res_del = requests.get(f"{API_URL}?action=GET_DELEGACIONES_APROBADAS&id_modelo={id_modelo_actual}").json()
                escuelas_aprobadas = res_del.get("data", [])
                
                res_nom = requests.get(f"{API_URL}?action=GET_TODAS_NOMINAS&id_modelo={id_modelo_actual}").json()
                todas_nominas = res_nom.get("data", [])
                
                res_org = requests.get(f"{API_URL}?action=GET_ORGANOS&id_modelo={id_modelo_actual}").json()
                organos_matriz = res_org.get("data", [])
            except Exception as e:
                escuelas_aprobadas, todas_nominas, organos_matriz = [], [], []
                st.error(f"Error al sincronizar datos: {e}")

        # METRICAS PRINCIPALES (TARJETAS GIGANTES)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("🏫 Escuelas Preinscriptas Aprobadas", len(escuelas_aprobadas))
        with m2:
            tot_cupos = sum([int(e.get("cupos_solicitados", 0)) for e in escuelas_aprobadas])
            st.metric("👥 Cupos Estudiantiles Aprobados", tot_cupos)
        with m3:
            st.metric("👤 Participantes Cargados", len(todas_nominas))
        with m4:
            fichas_ok = sum([1 for n in todas_nominas if n.get("drive_ficha_id") and n.get("drive_ficha_id") != "-"])
            st.metric("📄 Fichas Médicas Recibidas", fichas_ok)

        st.markdown("---")
        st.markdown("### 🏛️ Matriz de Representación: Países y Cupos por Órgano / Comité")

        if not organos_matriz:
            st.info("No hay información de la matriz de órganos cargada en la pestaña ORGANOS para este modelo.")
        else:
            df_organos = pd.DataFrame(organos_matriz)
            
            # Limpieza y conversión numérica
            df_organos["integrantes_totales"] = pd.to_numeric(df_organos["integrantes_totales"], errors='coerce').fillna(1)
            
            # Agrupación de países e integrantes por Órgano / Comité
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
        
        # TAB 1: PAGOS PENDIENTES
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
                        with st.expander(f"💳 Pago {pago['id_pago']} | Delegación: {pago['id_delegacion']} | Monto: ${pago['monto']}"):
                            col_a, col_b = st.columns([2, 1])
                            with col_a:
                                st.write(f"**Fecha de Subida:** {pago['fecha_subida']}")
                                if pago.get('drive_file_url') and pago['drive_file_url'] != "-":
                                    st.markdown(f"[📄 **Ver Comprobante Adjunto en Drive**]({pago['drive_file_url']})", unsafe_allow_html=True)
                            
                            with col_b:
                                if st.button("✅ APROBAR PAGO", key=f"app_{pago['id_pago']}"):
                                    payload = {
                                        "action": "CAMBIAR_ESTADO_PAGO",
                                        "usuario": "ADMIN",
                                        "data": {"id_pago": pago['id_pago'], "nuevo_estado": "APROBADO"}
                                    }
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.success("Pago Aprobado con Éxito")
                                        st.rerun()

                                if st.button("❌ RECHAZAR PAGO", key=f"rej_{pago['id_pago']}"):
                                    payload = {
                                        "action": "CAMBIAR_ESTADO_PAGO",
                                        "usuario": "ADMIN",
                                        "data": {"id_pago": pago['id_pago'], "nuevo_estado": "RECHAZADO"}
                                    }
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.warning("Pago Rechazado")
                                        st.rerun()
            except Exception as e:
                st.error(f"Error al conectar con la base de datos: {e}")

        # TAB 2: VALIDACIÓN DE MODIFICACIONES DE PREINSCRIPCIÓN
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
                                if st.button("✅ APROBAR MODIFICACIÓN", key=f"app_mod_{esc['id_delegacion']}"):
                                    payload = {
                                        "action": "RESPONDER_MODIFICACION_PREINSCRIPCION",
                                        "usuario": "ADMIN",
                                        "data": {
                                            "id_delegacion": esc['id_delegacion'],
                                            "aprobar": True,
                                            "nuevos_cupos": nuevos_cupos,
                                            "nuevo_desglose": nuevo_desglose,
                                            "docentes_acompanantes": docentes_acomp
                                        }
                                    }
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.success("Modificación Aprobada y actualizada en la base de datos.")
                                        st.rerun()

                            with col_m2:
                                if st.button("❌ RECHAZAR CAMBIO", key=f"rej_mod_{esc['id_delegacion']}"):
                                    payload = {
                                        "action": "RESPONDER_MODIFICACION_PREINSCRIPCION",
                                        "usuario": "ADMIN",
                                        "data": {
                                            "id_delegacion": esc['id_delegacion'],
                                            "aprobar": False
                                        }
                                    }
                                    r = requests.post(API_URL, json=payload).json()
                                    if r.get("status") == "SUCCESS":
                                        st.info("Modificación Rechazada. Se mantiene la inscripción anterior.")
                                        st.rerun()
            except Exception as e:
                st.error(f"Error al consultar solicitudes de modificación: {e}")

# ---------------------------------------------------------
    # MÓDULO 2: ASIGNACIÓN AUTOMÁTICA DE SORTEO CON VALIDACIÓN
    # ---------------------------------------------------------
    elif menu == "2. Asignación Automática de Sorteo":
        st.subheader(f"⚡ Asignación Directa por Matriz Predefinida - {modelo_seleccionado}")
        
        try:
            res_del = requests.get(f"{API_URL}?action=GET_DELEGACIONES_APROBADAS&id_modelo={id_modelo_actual}").json()
            escuelas_aprobadas = res_del.get("data", [])
            
            res_paises = requests.get(f"{API_URL}?action=GET_PAISES_MATRIZ&id_modelo={id_modelo_actual}").json()
            lista_paises = res_paises.get("data", [])
            
            res_org = requests.get(f"{API_URL}?action=GET_ORGANOS&id_modelo={id_modelo_actual}").json()
            organos_matriz = res_org.get("data", [])
        except Exception as e:
            escuelas_aprobadas, lista_paises, organos_matriz = [], [], []
            st.error(f"Error al consultar la matriz de países: {e}")

        if not escuelas_aprobadas:
            st.warning("No hay escuelas con pagos aprobados listos para el sorteo.")
        elif not lista_paises:
            st.warning("⚠️ No se encontraron países en la solapa ORGANOS para este modelo.")
        else:
            col_a, col_b = st.columns(2)
            
            with col_a:
                opciones_del = {f"{d['id_delegacion']} - {d['nombre_colegio']}": d for d in escuelas_aprobadas}
                escuela_sel_label = st.selectbox("1. Seleccioná la Escuela que sorteó:", list(opciones_del.keys()))
                escuela_actual = opciones_del[escuela_sel_label]
            
            with col_b:
                pais_seleccionado = st.selectbox("2. Seleccioná el País Sorteado:", sorted(lista_paises))

            st.markdown("---")
            
            # Datos de preinscripción de la escuela
            cupos_permitidos = int(escuela_actual.get("cupos_solicitados", 0))
            desglose_escuela = str(escuela_actual.get("desglose_modalidades", "")).lower()

            # Composición del país seleccionado
            composicion_pais = [
                o for o in organos_matriz 
                if str(o.get('pais', '')).strip().lower() == str(pais_seleccionado).strip().lower()
            ]
            
            st.markdown(f"#### 🔎 Verificación de Compatibilidad: **{pais_seleccionado}** vs **{escuela_actual['nombre_colegio']}**")
            
            # Métricas rápidas de la escuela
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                st.info(f"📋 **Modalidades pedidas por la escuela:** {desglose_escuela or 'No especificado'}")
            with col_e2:
                st.info(f"👥 **Cupos totales autorizados para la escuela:** {cupos_permitidos} delegados")

            tot_cupos_pais = 0
            alertas_compatibilidad = []

            if composicion_pais:
                st.markdown("##### Composición de la representación:")
                for c in composicion_pais:
                    cupos = int(c.get('integrantes_totales', 1))
                    organo_nombre = str(c.get('organo_comite', ''))
                    tot_cupos_pais += cupos
                    
                    # Validaciones de comités especiales (CS y ECOSOC)
                    if "consejo de seguridad" in organo_nombre.lower() or "cs" in organo_nombre.lower():
                        if "cs" not in desglose_escuela and "9d" not in desglose_escuela and "7d_cs" not in desglose_escuela:
                            alertas_compatibilidad.append(f"⚠️ **{pais_seleccionado}** incluye **{organo_nombre}**, pero la escuela NO solicitó modalidad con Consejo de Seguridad.")
                    
                    if "ecosoc" in organo_nombre.lower():
                        if "eco" not in desglose_escuela and "9d" not in desglose_escuela and "7d_eco" not in desglose_escuela:
                            alertas_compatibilidad.append(f"⚠️ **{pais_seleccionado}** incluye **{organo_nombre}**, pero la escuela NO solicitó modalidad con ECOSOC.")

                    st.write(f"• **{organo_nombre}**: {cupos} delegado(s)")

                # Mostrar alertas de ineligibilidad o advertencias
                if alertas_compatibilidad:
                    for al in alertas_compatibilidad:
                        st.error(al)

                if tot_cupos_pais > cupos_permitidos:
                    st.warning(f"⚠️ **Atención:** Este país requiere **{tot_cupos_pais} delegados**, pero la escuela solo tiene autorizados **{cupos_permitidos} cupos**.")

            else:
                st.caption("Seleccioná un país para ver su composición.")

            # Botón de asignación con confirmación/bloqueo opcional
            puedo_asignar = len(alertas_compatibilidad) == 0

            if st.button(f"🚀 ASIGNAR {pais_seleccionado.upper()} A {escuela_actual['nombre_colegio'].upper()}"):
                if not puedo_asignar:
                    st.error("❌ No se puede realizar la asignación debido a las incompatibilidades de comité señaladas arriba.")
                else:
                    payload = {
                        "action": "ASIGNAR_PAIS_AUTOMATICO_DESDE_MATRIZ",
                        "usuario": "ADMIN",
                        "data": {
                            "id_modelo": id_modelo_actual,
                            "id_delegacion": escuela_actual['id_delegacion'],
                            "pais": pais_seleccionado
                        }
                    }
                    with st.spinner("Vinculando matriz automática..."):
                        res = requests.post(API_URL, json=payload).json()
                        if res.get("status") == "SUCCESS":
                            st.balloons()
                            st.success(f"🎉 ¡**{pais_seleccionado}** ({res.get('cupos_agregados')} cupos) fue asignado exitosamente!")
                        else:
                            st.error(f"Error: {res.get('message')}")

            st.markdown("---")
            st.markdown("##### 📋 Países ya asignados a esta escuela:")
            res_asig_curr = requests.get(f"{API_URL}?action=GET_ASIGNACIONES_DELEGACION&id_delegacion={escuela_actual['id_delegacion']}").json()
            asig_list = res_asig_curr.get("data", [])
            if asig_list:
                paises_resumen = {}
                for a in asig_list:
                    p = a.get('pais')
                    paises_resumen[p] = paises_resumen.get(p, 0) + 1
                for p_k, p_v in paises_resumen.items():
                    st.write(f"• **{p_k}**: {p_v} lugares asignados.")
            else:
                st.caption("Aún no tiene países adjudicados.")
    # ---------------------------------------------------------
    # MÓDULO 3: SOLAPA DEDUCTIVA Y COMPLETA DE NÓMINA GENERAL
    # ---------------------------------------------------------
    elif menu == "3. Nómina General de Participantes":
        st.subheader(f"📋 Nómina Consolidada de Participantes - {modelo_seleccionado}")
        
        try:
            res_nom = requests.get(f"{API_URL}?action=GET_TODAS_NOMINAS&id_modelo={id_modelo_actual}").json()
            todas_nominas = res_nom.get("data", [])
        except Exception as e:
            todas_nominas = []
            st.error(f"Error al obtener nóminas: {e}")

        if not todas_nominas:
            st.info("Aún no hay participantes cargados en la base de datos para este modelo.")
        else:
            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                filtro_busqueda = st.text_input("🔍 Filtrar por Nombre, Apellido, DNI o Escuela:")
            with col_f2:
                filtro_doc = st.selectbox("Filtrar por Estado de Documentación:", ["Todos", "Ficha Médica Pendiente", "Autorización Pendiente", "Documentación Completa"])

            # Procesar datos para la tabla consolidada
            lista_procesada = []
            for n in todas_nominas:
                ficha_ok = n.get("drive_ficha_id") and n.get("drive_ficha_id") != "-"
                aut_ok = n.get("drive_autorizacion_id") and n.get("drive_autorizacion_id") != "-"
                
                # Filtro por documentación
                if filtro_doc == "Ficha Médica Pendiente" and ficha_ok:
                    continue
                if filtro_doc == "Autorización Pendiente" and aut_ok:
                    continue
                if filtro_doc == "Documentación Completa" and (not ficha_ok or not aut_ok):
                    continue

                # Filtro por búsqueda de texto
                nom_comp = f"{n.get('nombre', '')} {n.get('apellido', '')}".strip() or n.get("nombre_completo", "")
                query = filtro_busqueda.strip().lower()
                if query:
                    if not (query in nom_comp.lower() or query in str(n.get("dni", "")).lower() or query in str(n.get("id_delegacion", "")).lower()):
                        continue

                lista_procesada.append({
                    "ID Delegado": n.get("id_delegado"),
                    "Escuela / ID": n.get("id_delegacion"),
                    "Nombre": n.get("nombre", "-"),
                    "Apellido": n.get("apellido", "-"),
                    "DNI": n.get("dni"),
                    "Rol / Representación": n.get("rol_mnu"),
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
            try:
                res_nom = requests.get(f"{API_URL}?action=GET_TODAS_NOMINAS&id_modelo={id_modelo_actual}").json()
                todas_nominas = res_nom.get("data", [])
                
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
                        with st.expander(f"👤 {nombre_mostrar} | DNI: {r.get('dni')} | Escuela: {r.get('id_delegacion')}"):
                            st.write(f"**Rol / Comisión:** {r.get('rol_mnu')}")
                            st.write(f"**Indicaciones Médicas / Alergias:** {r.get('alergias_medicas')}")
                            
                            col_f1, col_f2 = st.columns(2)
                            with col_f1:
                                ficha_id = r.get("drive_ficha_id")
                                if ficha_id and ficha_id != "-":
                                    st.markdown(f"[📄 Ver Ficha Médica en Drive](https://drive.google.com/file/d/{ficha_id}/view)", unsafe_allow_html=True)
                                else:
                                    st.caption("Ficha médica no adjuntada.")
                                    
                            with col_f2:
                                aut_id = r.get("drive_autorizacion_id")
                                if aut_id and aut_id != "-":
                                    st.markdown(f"[📄 Ver Autorización en Drive](https://drive.google.com/file/d/{aut_id}/view)", unsafe_allow_html=True)
                                else:
                                    st.caption("Autorización de imagen no adjuntada.")
            except Exception as e:
                st.error(f"Error al realizar la búsqueda: {e}")

elif admin_pass:
    st.error("🔒 Contraseña incorrecta. Acceso denegado al Panel del Secretariado.")
else:
    st.warning("👈 Por favor ingresá la contraseña del Secretariado en el menú lateral para acceder.")
