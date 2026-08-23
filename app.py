# ---------------------------------------------------------
    # MÓDULO 1: REVISIÓN DE PAGOS Y MODIFICACIONES (REPARADO Y VINCULADO)
    # ---------------------------------------------------------
    elif menu == "1. Revisión de Pagos y Modificaciones":
        st.subheader(f"Auditoría General - {modelo_seleccionado}")
        tab_pagos, tab_modificaciones = st.tabs(["💳 Comprobantes de Pago PENDIENTES", "✏️ Solicitudes de Cambio de Cupos"])
        
        with tab_pagos:
            try:
                # 1. Obtener pagos pendientes
                res_pagos = requests.get(f"{API_URL}?action=GET_PAGOS_PENDIENTES").json()
                pagos = res_pagos.get("data", [])
                
                # 2. Obtener TODAS las delegaciones (Aprobadas, Registradas o Modificadas) para cruzar los datos
                res_escuelas = requests.get(f"{API_URL}?action=GET_TODAS_DELEGACIONES&id_modelo={id_modelo_actual}").json()
                escuelas = res_escuelas.get("data", [])
                
                # Crear diccionario de mapeo tolerante a minúsculas/mayúsculas y espacios: { "DEL-001": dict_escuela }
                mapa_escuelas = {}
                for e in escuelas:
                    id_d = str(e.get("id_delegacion", "")).strip().upper()
                    if id_d:
                        mapa_escuelas[id_d] = e

                pagos_filtrados = [p for p in pagos if str(p.get("id_modelo", "")).strip() == id_modelo_actual or not p.get("id_modelo")]
                
                if not pagos_filtrados:
                    st.success(f"🎉 No hay comprobantes pendientes de revisión para {modelo_seleccionado}.")
                else:
                    for pago in pagos_filtrados:
                        id_pago = str(pago.get('id_pago', '-')).strip()
                        id_del = str(pago.get('id_delegacion', '-')).strip().upper()
                        monto = pago.get('monto', 0)
                        
                        # Cruzar datos con la solapa DELEGACIONES
                        datos_escuela = mapa_escuelas.get(id_del, {})
                        
                        nombre_colegio = datos_escuela.get("nombre_colegio") or datos_escuela.get("institucion") or "Escuela Registrada"
                        docente_resp = datos_escuela.get("docente_apellido_nombre") or datos_escuela.get("docente_a_cargo") or "No informado"
                        docente_email = datos_escuela.get("docente_email") or datos_escuela.get("email_docente_responsable") or datos_escuela.get("email_institucional") or "-"
                        docente_tel = datos_escuela.get("docente_telefono") or datos_escuela.get("cel_docente") or datos_escuela.get("telefono_institucional") or "-"
                        cupos_pedidos = datos_escuela.get("cupos_solicitados") or datos_escuela.get("cant_de_delegados") or 0
                        desglose_pedidos = datos_escuela.get("desglose_modalidades") or "No especificado"
                        docentes_acomp = datos_escuela.get("docentes_acompanantes") or 1

                        # Tarjeta aislada por ID de Pago
                        with st.expander(f"💳 {id_pago} | {nombre_colegio} ({id_del}) — Monto Subido: ${monto:,.2f}"):
                            st.markdown("##### 📄 Resumen de la Preinscripción Solicitada:")
                            
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.write(f"• **Institución:** {nombre_colegio}")
                                st.write(f"• **Docente Responsable:** {docente_resp}")
                                st.write(f"• **Contacto:** 📧 {docente_email} | 📞 {docente_tel}")
                            
                            with col_info2:
                                st.write(f"• **Cupos Solicitados:** {cupos_pedidos} estudiantes")
                                st.write(f"• **Docentes Acompañantes:** {docentes_acomp}")
                                st.write(f"• **Desglose Solicitado:** `{desglose_pedidos}`")

                            st.markdown("---")
                            
                            col_b1, col_b2 = st.columns([2, 1])
                            with col_b1:
                                st.write(f"**Fecha de Envío:** {pago.get('fecha_subida', '-')}")
                                if pago.get('drive_file_url') and pago['drive_file_url'] != "-":
                                    st.markdown(f"[📄 **ABRIR COMPROBANTE DE PAGO (DRIVE)**]({pago['drive_file_url']})", unsafe_allow_html=True)
                                else:
                                    st.warning("Sin archivo adjunto.")

                            with col_b2:
                                btn_aprobar = st.button("✅ APROBAR PAGO", key=f"btn_app_{id_pago}")
                                btn_rechazar = st.button("❌ RECHAZAR PAGO", key=f"btn_rej_{id_pago}")

                                if btn_aprobar:
                                    payload = {
                                        "action": "CAMBIAR_ESTADO_PAGO", 
                                        "usuario": "ADMIN", 
                                        "data": {"id_pago": id_pago, "nuevo_estado": "APROBADO"}
                                    }
                                    with st.spinner("Aprobando pago..."):
                                        r = requests.post(API_URL, json=payload).json()
                                        if r.get("status") == "SUCCESS":
                                            st.cache_data.clear()
                                            st.success(f"¡Pago {id_pago} aprobado exitosamente!")
                                            st.rerun()
                                        else:
                                            st.error(f"Error: {r.get('message')}")

                                if btn_rechazar:
                                    payload = {
                                        "action": "CAMBIAR_ESTADO_PAGO", 
                                        "usuario": "ADMIN", 
                                        "data": {"id_pago": id_pago, "nuevo_estado": "RECHAZADO"}
                                    }
                                    with st.spinner("Rechazando pago..."):
                                        r = requests.post(API_URL, json=payload).json()
                                        if r.get("status") == "SUCCESS":
                                            st.cache_data.clear()
                                            st.info(f"Pago {id_pago} marcado como rechazado.")
                                            st.rerun()
                                        else:
                                            st.error(f"Error: {r.get('message')}")

            except Exception as e:
                st.error(f"Error al cargar la solapa de pagos: {e}")
