import streamlit as st
import requests

st.set_page_config(
    page_title="Secretariado - Control Interno MNU",
    page_icon="🛡️",
    layout="wide"
)

API_URL = "https://script.google.com/macros/s/AKfycbyM7_YhNDZdzKcrrTChJ0hfN_d7nCeQ5WC-y9Uk1VmSGyeKiyqaXxoT3mnJMYTRSqeaDQ/exec"

st.title("🛡️ Panel Interno del Secretariado - Control y Sorteo")

@st.cache_data(ttl=60)
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
            "1. Revisión de Pagos", 
            "2. Asignación Automática de Sorteo",
            "3. Auditoría de Nóminas y Fichas",
            "4. Búsqueda por DNI / Alumno"
        ]
    )

    # ---------------------------------------------------------
    # MÓDULO 1: REVISIÓN DE PAGOS
    # ---------------------------------------------------------
    if menu == "1. Revisión de Pagos":
        st.subheader(f"Gestión y Auditoría de Pagos - {modelo_seleccionado}")
        
        if st.button("🔄 Actualizar Lista de Pagos"):
            st.rerun()
            
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

    # ---------------------------------------------------------
    # MÓDULO 2: ASIGNACIÓN AUTOMÁTICA DESDE MATRIZ DE PAÍSES
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
            escuelas_aprobadas = []
            lista_paises = []
            organos_matriz = []
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
            
            composicion_pais = [
                o for o in organos_matriz 
                if str(o.get('pais', '')).strip().lower() == str(pais_seleccionado).strip().lower()
            ]
            
            st.markdown(f"#### 🔎 Vista Previa de la Representación: **{pais_seleccionado}**")
            
            tot_cupos = 0
            if composicion_pais:
                for c in composicion_pais:
                    cupos = int(c.get('integrantes_totales', 1))
                    tot_cupos += cupos
                    st.write(f"• **{c.get('organo_comite')}**: {cupos} delegado(s)")
                st.info(f"📊 La asignación creará automáticamente **{tot_cupos} cupos** en la base de datos.")
            else:
                st.caption("Seleccioná un país para ver su composición.")

            if st.button(f"🚀 ASIGNAR {pais_seleccionado.upper()} A {escuela_actual['nombre_colegio'].upper()}"):
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
    # MÓDULO 3: AUDITORÍA DE NÓMINAS Y FICHAS
    # ---------------------------------------------------------
    elif menu == "3. Auditoría de Nóminas y Fichas":
        st.subheader(f"Revision General de Nóminas Cargadas - {modelo_seleccionado}")
        
        try:
            res_nom = requests.get(f"{API_URL}?action=GET_TODAS_NOMINAS&id_modelo={id_modelo_actual}").json()
            todas_nominas = res_nom.get("data", [])
        except Exception as e:
            todas_nominas = []
            st.error(f"Error al obtener nóminas: {e}")

        if not todas_nominas:
            st.info("Aún no hay participantes cargados en la base de datos para este modelo.")
        else:
            st.success(f"Total de participantes registrados: **{len(todas_nominas)}**")
            
            tabla_resumen = []
            for n in todas_nominas:
                tabla_resumen.append({
                    "ID Delegado": n.get("id_delegado"),
                    "Escuela/ID": n.get("id_delegacion"),
                    "Nombre Completo": n.get("nombre_completo"),
                    "DNI": n.get("dni"),
                    "Rol / Representación": n.get("rol_mnu"),
                    "Ficha ID": "✅ Cargada" if n.get("drive_ficha_id") != "-" else "❌ Pendiente",
                    "Autorización ID": "✅ Cargada" if n.get("drive_autorizacion_id") != "-" else "❌ Pendiente",
                    "Alergias / Cuidados": n.get("alergias_medicas")
                })
            
            st.dataframe(tabla_resumen, use_container_width=True)

    # ---------------------------------------------------------
    # MÓDULO 4: BÚSQUEDA POR DNI / ALUMNO
    # ---------------------------------------------------------
    elif menu == "4. Búsqueda por DNI / Alumno":
        st.subheader(f"🔍 Buscador Global de Participantes - {modelo_seleccionado}")
        
        busqueda = st.text_input("Ingresá el DNI, Nombre o Código de Delegación (Ej: DEL-001):")
        
        if busqueda:
            try:
                res_nom = requests.get(f"{API_URL}?action=GET_TODAS_NOMINAS&id_modelo={id_modelo_actual}").json()
                todas_nominas = res_nom.get("data", [])
                
                query = busqueda.strip().lower()
                resultados = [
                    n for n in todas_nominas 
                    if query in str(n.get("dni", "")).lower() 
                    or query in str(n.get("nombre_completo", "")).lower() 
                    or query in str(n.get("id_delegacion", "")).lower()
                ]
                
                if not resultados:
                    st.warning(f"No se encontraron participantes que coincidan con '{busqueda}'.")
                else:
                    st.success(f"Se encontraron **{len(resultados)}** coincidencia(s):")
                    
                    for r in resultados:
                        with st.expander(f"👤 {r.get('nombre_completo')} | DNI: {r.get('dni')} | Escuela: {r.get('id_delegacion')}"):
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
