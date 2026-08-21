import streamlit as st
import requests
import json
import pandas as pd

st.set_page_config(
    page_title="Secretariado - Control Interno MNU",
    page_icon="🛡️",
    layout="wide"
)

API_URL = "https://script.google.com/macros/s/AKfycbz0zBX3gXipKIXKAb5ZNHfQMy1YVYJrXVAf51IydmmDIdPM-VSMa91_HSmBdvsGL4Q4yw/exec"

# =========================================================
# FUNCIONES DE CACHÉ OPTIMIZADAS
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

@st.cache_data(ttl=15)
def cargar_datos_sorteo(id_mod):
    try:
        r_del = requests.get(f"{API_URL}?action=GET_DELEGACIONES_APROBADAS&id_modelo={id_mod}").json().get("data", [])
        r_pai = requests.get(f"{API_URL}?action=GET_PAISES_MATRIZ&id_modelo={id_mod}").json().get("data", [])
        r_org = requests.get(f"{API_URL}?action=GET_ORGANOS&id_modelo={id_mod}").json().get("data", [])
        r_mod = requests.get(f"{API_URL}?action=GET_MODALIDADES_MODELO&id_modelo={id_mod}").json().get("data", [])
        r_asig = requests.get(f"{API_URL}?action=GET_TODAS_ASIGNACIONES").json().get("data", [])
        return r_del, r_pai, r_org, r_mod, r_asig
    except Exception:
        return [], [], [], [], []

@st.cache_data(ttl=30)
def cargar_todas_nominas_cached(id_mod):
    try:
        res = requests.get(f"{API_URL}?action=GET_TODAS_NOMINAS&id_modelo={id_mod}").json()
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
    # MÓDULO 0: DASHBOARD
    # ---------------------------------------------------------
    if menu == "📊 Dashboard & Estado del Modelo":
        st.subheader(f"📈 Estado General del Evento - {modelo_seleccionado}")
        
        with st.spinner("Cargando métricas..."):
            escuelas_aprobadas, _, organos_matriz, _, _ = cargar_datos_sorteo(id_modelo_actual)
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
            st.metric("📄 Fichas Médicas", fichas_ok)

        st.markdown("---")
        st.markdown("### 🏛️ Matriz de Representación: Países y Cupos por Órgano / Comité")

        if organos_matriz:
            df_organos = pd.DataFrame(organos_matriz)
            if "integrantes_totales" in df_organos.columns:
                df_organos["integrantes_totales"] = pd.to_numeric(df_organos["integrantes_totales"], errors='coerce').fillna(1)
                
                resumen_organos = df_organos.groupby("organo_comite").agg(
                    Cantidad_Paises=("pais", "nunique"),
                    Total_Delegados=("integrantes_totales", "sum")
                ).reset_index()

                resumen_organos.columns = ["Órgano / Comité", "Paises Representados", "Cupos Totales"]

                col_t1, col_t2 = st.columns([2, 1])
                with col_t1:
                    st.dataframe(resumen_organos, use_container_width=True, hide_index=True)
                with col_t2:
                    st.markdown("#### 📊 Resumen de Representaciones")
                    for _, row in resumen_organos.iterrows():
                        st.write(f"• **{row['Órgano / Comité']}**: {row['Paises Representados']} países ({int(row['Cupos Totales'])} lugares)")

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
                            st.write(f"**Contacto:** {esc.get('docente_cargo')} ({esc.get('email_contacto')})")
                            propuesta_raw = esc.get("propuesta_modificacion", "{}")
                            try:
                                prop = json.loads(propuesta_raw)
                            except Exception:
                                prop = {}
                            
                            nuevos_cupos = prop.get("nuevos_cupos", esc.get("cupos_solicitados"))
                            nuevo_desglose = prop.get("nuevo_desglose", esc.get("desglose_modalidades"))
                            docentes_acomp = prop.get("docentes_acompanantes", esc.get("docentes_acompanantes"))

                            st.write(f"• **Nuevos Cupos Estudiantes:** {nuevos_cupos}")
                            st.write(f"• **Nuevos Docentes:** {docentes_acomp}")
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
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------------------------------------------------
    # MÓDULO 2: ASIGNACIÓN MULTI-PAÍS EN TIEMPO REAL (CORREGIDO)
    # ---------------------------------------------------------
    elif menu == "2. Asignación Automática de Sorteo":
        st.subheader(f"⚡ Asignación Directa y Validación de Cupos - {modelo_seleccionado}")

        # Carga general de la matriz
        with st.spinner("Sincronizando matriz y asignaciones..."):
            escuelas_aprobadas, lista_paises, organos_matriz, modalidades_evento, _ = cargar_datos_sorteo(id_modelo_actual)

        if not escuelas_aprobadas:
            st.warning("No hay escuelas con pagos aprobados disponibles.")
        elif not lista_paises:
            st.warning("⚠️ No hay países configurados en la solapa ORGANOS.")
        else:
            col_a, col_b = st.columns(2)
            
            with col_a:
                opciones_del = {f"{d.get('id_delegacion', 'DEL')} - {d.get('nombre_colegio', 'Escuela')}": d for d in escuelas_aprobadas if d.get('id_delegacion')}
                escuela_sel_label = st.selectbox("1. Escuela que realizó el Sorteo:", list(opciones_del.keys()))
                escuela_actual = opciones_del[escuela_sel_label]
                id_del_actual = str(escuela_actual.get('id_delegacion')).strip()

            # CONSULTA EN TIEMPO REAL DE LAS ASIGNACIONES DE ESTA ESCUELA Y DE TODO EL MODELO
            try:
                res_asig_escuela = requests.get(f"{API_URL}?action=GET_ASIGNACIONES_DELEGACION&id_delegacion={id_del_actual}").json().get("data", [])
                res_todas_asig = requests.get(f"{API_URL}?action=GET_TODAS_ASIGNACIONES").json().get("data", [])
            except Exception:
                res_asig_escuela = []
                res_todas_asig = []

            # CÁLCULO DINÁMICO DE CUPOS RESTANTES DE LA ESCUELA
            cupos_ya_usados = len(res_asig_escuela)
            cupos_totales_contratados = int(escuela_actual.get("cupos_solicitados", 0)) if str(escuela_actual.get("cupos_solicitados", "0")).isdigit() else 0
            cupos_restantes = max(0, cupos_totales_contratados - cupos_ya_usados)

            # FILTRAR Y EXCLUIR PAÍSES QUE YA FUERON ASIGNADOS A CUALQUIER ESCUELA EN EL MODELO
            paises_ya_asignados_global = set([str(a.get("pais")).strip().lower() for a in res_todas_asig if a.get("pais")])
            lista_paises_disponibles = [p for p in lista_paises if str(p).strip().lower() not in paises_ya_asignados_global]

            with col_b:
                if not lista_paises_disponibles:
                    st.warning("⚠️ Todos los países de la matriz ya fueron adjudicados.")
                    pais_seleccionado = None
                else:
                    pais_seleccionado = st.selectbox("2. País Disponible a Asignar:", sorted(lista_paises_disponibles))

            st.markdown("---")
            
            # Modalidades pedidas por la escuela
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

            escuela_tiene_cs = any("cs" in k or "9" in k or "con cs" in k for k in modalidades_escuela.keys())
            escuela_tiene_eco = any("eco" in k or "ecosoc" in k for k in modalidades_escuela.keys())
            escuela_tiene_davos = any("davos" in k for k in modalidades_escuela.keys())

            st.markdown(f"#### 🔎 Estado de Asignación: **{escuela_actual.get('nombre_colegio')}**")
            
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1:
                st.info(f"👥 **Cupos Solicitados:** {cupos_totales_contratados}")
            with col_e2:
                st.warning(f"📌 **Cupos Ya Asignados:** {cupos_ya_usados}")
            with col_e3:
                if cupos_restantes > 0:
                    st.success(f"🟢 **Cupos Libres para Asignar:** {cupos_restantes}")
                else:
                    st.error("🔴 **Cupos Agotados:** Esta escuela ya completó todas sus asignaciones.")

            if pais_seleccionado and cupos_restantes > 0:
                composicion_pais = [o for o in organos_matriz if str(o.get('pais', '')).strip().lower() == str(pais_seleccionado).strip().lower()]
                
                bloqueos_criticos = []
                tot_cupos_pais = 0

                st.markdown(f"##### Comités requeridos por **{pais_seleccionado}**:")
                for c in composicion_pais:
                    cupos = int(c.get('integrantes_totales', 1)) if str(c.get('integrantes_totales', '1')).isdigit() else 1
                    organo_nombre = str(c.get('organo_comite', '')).strip()
                    organo_lower = organo_nombre.lower()
                    tot_cupos_pais += cupos
                    
                    st.write(f"• **{organo_nombre}**: {cupos} delegado(s)")

                    if ("consejo de seguridad" in organo_lower or "cs" in organo_lower) and "ecosoc" not in organo_lower:
                        if not escuela_tiene_cs:
                            bloqueos_criticos.append(f"⛔ **RESTRICCIÓN:** {pais_seleccionado} requiere asiento en **{organo_nombre}**, pero la escuela no solicitó modalidad con CS.")
                    
                    if "ecosoc" in organo_lower and not escuela_tiene_eco:
                        bloqueos_criticos.append(f"⛔ **RESTRICCIÓN:** {pais_seleccionado} requiere asiento en **{organo_nombre}**, pero la escuela no solicitó ECOSOC.")

                if tot_cupos_pais > cupos_restantes:
                    bloqueos_criticos.append(f"⛔ **EXCESO DE CUPOS:** El país requiere **{tot_cupos_pais} lugares**, pero a la escuela solo le quedan **{cupos_restantes} cupos disponibles**.")

                if bloqueos_criticos:
                    for b in bloqueos_criticos:
                        st.error(b)
                else:
                    st.success(f"✅ **Compatibilidad Verificada:** Este país requiere {tot_cupos_pais} lugares y tenés {cupos_restantes} disponibles.")

                puedo_asignar = len(bloqueos_criticos) == 0

                if st.button(f"🚀 ASIGNAR {str(pais_seleccionado).upper()}", disabled=not puedo_asignar):
                    payload = {
                        "action": "ASIGNAR_PAIS_AUTOMATICO_DESDE_MATRIZ",
                        "usuario": "ADMIN",
                        "data": {
                            "id_modelo": id_modelo_actual,
                            "id_delegacion": id_del_actual,
                            "pais": pais_seleccionado
                        }
                    }
                    with st.spinner(f"Asignando {pais_seleccionado} a la planilla..."):
                        res = requests.post(API_URL, json=payload).json()
                        if res.get("status") == "SUCCESS":
                            st.cache_data.clear()  # Limpia la memoria por completo
                            st.balloons()
                            st.success(f"🎉 ¡**{pais_seleccionado}** ({res.get('cupos_agregados')} cupos) fue asignado exitosamente!")
                            st.rerun()  # Vuelve a cargar la interfaz actualizada inmediatamente
                        else:
                            st.error(f"Error del servidor: {res.get('message')}")

            st.markdown("---")
            st.markdown("##### 📋 Países ya adjudicados a esta escuela:")
            if res_asig_escuela:
                paises_resumen = {}
                for a in res_asig_escuela:
                    p = a.get('pais')
                    paises_resumen[p] = paises_resumen.get(p, 0) + 1
                for p_k, p_v in paises_resumen.items():
                    st.write(f"• **{p_k}**: {p_v} lugares asignados.")
            else:
                st.caption("Esta escuela aún no tiene ningún país asignado.")
    # ---------------------------------------------------------
    # MÓDULO 3 Y 4: NÓMINA Y BÚSQUEDA
    # ---------------------------------------------------------
    elif menu == "3. Nómina General de Participantes":
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

    elif menu == "4. Búsqueda Rápida por DNI":
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
