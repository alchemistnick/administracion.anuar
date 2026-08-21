# ---------------------------------------------------------
    # MÓDULO 2: ASIGNACIÓN RÁPIDA Y STRICTA DE PAÍSES
    # ---------------------------------------------------------
    elif menu == "2. Asignación Automática de Sorteo":
        st.subheader(f"⚡ Asignación Directa y Validación de Cupos - {modelo_seleccionado}")

        # Carga optimizada con Cache para evitar consultas HTTP repetidas
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

        with st.spinner("Cargando matriz de sorteo..."):
            escuelas_aprobadas, lista_paises, organos_matriz, modalidades_evento = cargar_datos_sorteo(id_modelo_actual)

        if not escuelas_aprobadas:
            st.warning("No hay escuelas con pagos aprobados disponibles para asignar.")
        elif not lista_paises:
            st.warning("⚠️ No se encontraron países en la solapa ORGANOS para este modelo.")
        else:
            col_a, col_b = st.columns(2)
            
            with col_a:
                opciones_del = {f"{d['id_delegacion']} - {d['nombre_colegio']}": d for d in escuelas_aprobadas}
                escuela_sel_label = st.selectbox("1. Escuela que realizó el Sorteo:", list(opciones_del.keys()))
                escuela_actual = opciones_del[escuela_sel_label]
            
            with col_b:
                pais_seleccionado = st.selectbox("2. País a Asignar:", sorted(lista_paises))

            st.markdown("---")
            
            # 1. Datos de la preinscripción de la escuela
            cupos_autorizados = int(escuela_actual.get("cupos_solicitados", 0))
            desglose_str = str(escuela_actual.get("desglose_modalidades", ""))
            
            # Extraer las modalidades solicitadas por la escuela en un diccionario -> {'del_5': 2, 'del_9_CS': 1}
            modalidades_escuela = {}
            if desglose_str:
                items = desglose_str.split("|")
                for it in items:
                    if ":" in it:
                        k, v = it.split(":")
                        cant = int(v.strip()) if v.strip().isdigit() else 0
                        if cant > 0:
                            modalidades_escuela[k.strip()] = cant

            # 2. Verificar qué facultades/comités contrataron las modalidades de esta escuela
            escuela_tiene_cs = False
            escuela_tiene_eco = False
            escuela_tiene_davos = False
            escuela_tiene_prensa = False

            # Mapa rápido de las modalidades del modelo actual desde Sheets
            dict_modalidades_config = {m.get("clave_modalidad"): m for m in modalidades_evento}

            for clave_mod in modalidades_escuela.keys():
                config_mod = dict_modalidades_config.get(clave_mod, {})
                etiqueta = str(config_mod.get("etiqueta_visible", "")).lower()
                clave_lower = str(clave_mod).lower()

                # Detectar Consejo de Seguridad
                if "cs" in clave_lower or "consejo" in etiqueta or "con cs" in etiqueta:
                    if "sin cs" not in etiqueta or "seco_cs" in clave_lower or "9" in clave_lower:
                        escuela_tiene_cs = True
                
                # Detectar ECOSOC
                if "eco" in clave_lower or "ecosoc" in etiqueta or "con ecosoc" in etiqueta:
                    if "sin ecosoc" not in etiqueta and "sin_ecosoc" not in clave_lower:
                        escuela_tiene_eco = True

                # Detectar Davos
                if "davos" in clave_lower or "davos" in etiqueta:
                    escuela_tiene_davos = True

                # Detectar Prensa
                if "prensa" in clave_lower or "prensa" in etiqueta:
                    escuela_tiene_prensa = True

            # 3. Requerimientos del País Seleccionado
            composicion_pais = [
                o for o in organos_matriz 
                if str(o.get('pais', '')).strip().lower() == str(pais_seleccionado).strip().lower()
            ]
            
            st.markdown(f"#### 🔎 Análisis de Viabilidad: **{pais_seleccionado}** ➔ **{escuela_actual['nombre_colegio']}**")
            
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                st.info(f"📋 **Modalidades contratadas por el colegio:** `{desglose_str}`")
            with col_e2:
                st.info(f"👥 **Cupos Totales Autorizados:** {cupos_autorizados} delegados")

            bloqueos_criticos = []
            tot_cupos_pais = 0

            if composicion_pais:
                st.markdown("##### Comités requeridos por este país:")
                for c in composicion_pais:
                    cupos = int(c.get('integrantes_totales', 1))
                    organo_nombre = str(c.get('organo_comite', '')).strip()
                    organo_lower = organo_nombre.lower()
                    tot_cupos_pais += cupos
                    
                    st.write(f"• **{organo_nombre}**: {cupos} delegado(s)")

                    # VALIDACIONES ESTRICTAS DE RESTRICCIÓN
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

                # Verificación de exceso de cupos totales
                if tot_cupos_pais > cupos_autorizados:
                    bloqueos_criticos.append(f"⛔ **EXCESO DE CUPOS:** El país requiere **{tot_cupos_pais} integrantes**, pero el colegio solo dispone de **{cupos_autorizados} cupos**.")

            # Muestra de Alertas y Bloqueos
            if bloqueos_criticos:
                for b in bloqueos_criticos:
                    st.error(b)
            else:
                st.success("✅ **Compatibilidad Verificada:** La escuela cuenta con las modalidades y cupos necesarios para este país.")

            # BOTÓN DE ASIGNACIÓN (DESHABILITADO SI HAY BLOQUEOS)
            puedo_asignar = len(bloqueos_criticos) == 0

            if st.button(f"🚀 ASIGNAR {pais_seleccionado.upper()}", disabled=not puedo_asignar):
                payload = {
                    "action": "ASIGNAR_PAIS_AUTOMATICO_DESDE_MATRIZ",
                    "usuario": "ADMIN",
                    "data": {
                        "id_modelo": id_modelo_actual,
                        "id_delegacion": escuela_actual['id_delegacion'],
                        "pais": pais_seleccionado
                    }
                }
                with st.spinner("Procesando asignación..."):
                    res = requests.post(API_URL, json=payload).json()
                    if res.get("status") == "SUCCESS":
                        st.cache_data.clear() # Limpia el cache para refrescar
                        st.balloons()
                        st.success(f"🎉 ¡**{pais_seleccionado}** ({res.get('cupos_agregados')} cupos) fue asignado a {escuela_actual['nombre_colegio']}!")
                        st.rerun()
                    else:
                        st.error(f"Error del servidor: {res.get('message')}")

            st.markdown("---")
            st.markdown("##### 📋 Asignaciones actuales de esta escuela:")
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
                st.caption("Esta escuela aún no tiene países asignados.")
