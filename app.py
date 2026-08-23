import streamlit as st
import requests
import base64

st.set_page_config(
    page_title="Gestión MNU - Portal Escuelas",
    page_icon="🇺🇳",
    layout="wide"
)

# NUEVA URL DE LA API DE APPS SCRIPT ACTUALIZADA
API_URL = "https://script.google.com/macros/s/AKfycbxMsoNWVYS9CJRHSj22s25ivYY6ITSK6vj059JmjDKb_YMr0Qy8GyLQx3fQqQWf7PwJHA/exec"

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

@st.cache_data(ttl=60)
def cargar_modalidades_modelo(id_modelo):
    try:
        res = requests.get(f"{API_URL}?action=GET_MODALIDADES_MODELO&id_modelo={id_modelo}").json()
        if res.get("status") == "SUCCESS":
            return res.get("data", [])
        return []
    except Exception:
        return []

@st.cache_data(ttl=30)
def cargar_todas_delegaciones_cached(id_modelo):
    try:
        res = requests.get(f"{API_URL}?action=GET_TODAS_DELEGACIONES&id_modelo={id_modelo}").json()
        if res.get("status") == "SUCCESS":
            return res.get("data", [])
        return []
    except Exception:
        return []

st.title("🇺🇳 Portal de Inscripción y Carga - Modelos ONU")

CONFIG_MODELOS = cargar_modelos_activos()

st.sidebar.markdown("### 🌐 Selección de Evento")

if not CONFIG_MODELOS:
    st.sidebar.warning("⚠️ No hay modelos activos configurados en la planilla.")
    st.stop()
else:
    modelo_seleccionado = st.sidebar.selectbox("Elegí el Modelo a Gestionar:", list(CONFIG_MODELOS.keys()))
    id_modelo_actual = CONFIG_MODELOS[modelo_seleccionado]

st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navegación",
    [
        "1. Preinscripción Escuela", 
        "2. Cargar Comprobante", 
        "3. Carga de Nómina y Fichas"
    ]
)

# ---------------------------------------------------------
# MÓDULO 1: PREINSCRIPCIÓN ESCUELA
# ---------------------------------------------------------
if menu == "1. Preinscripción Escuela":
    st.subheader(f"Ficha de Preinscripción por Escuela - {modelo_seleccionado}")
    modalidades_evento = cargar_modalidades_modelo(id_modelo_actual)

    with st.form("form_registro_unificado"):
        st.markdown("### 🏛️ DATOS DE LA INSTITUCIÓN")
        colegio = st.text_input("Nombre de la Escuela *")
        direccion = st.text_input("Dirección (Localidad, Provincia, País) *")
        
        col_inst1, col_inst2 = st.columns(2)
        with col_inst1:
            email_inst = st.text_input("Correo electrónico institucional *")
        with col_inst2:
            tel_inst = st.text_input("Número de teléfono de la escuela *")
        
        st.markdown("---")
        st.markdown("### 👤 DATOS DEL RESPONSABLE / PROFESOR A CARGO")
        
        docente_ape_nom = st.text_input("Apellido y Nombre del Responsable *")
        
        col_doc1, col_doc2 = st.columns(2)
        with col_doc1:
            docente_email = st.text_input("Correo electrónico personal/docente (Usuario de Acceso) *")
        with col_doc2:
            docente_tel = st.text_input("Número de teléfono móvil *")

        col_sec1, col_sec2 = st.columns(2)
        with col_sec1:
            cant_docentes = st.number_input("Cantidad TOTAL de Docentes Acompañantes que asistirán:", min_value=1, max_value=10, value=1)
        with col_sec2:
            clave = st.text_input("Creá una Clave Secreta para acceder al Portal *", type="password")
        
        st.markdown("---")
        st.markdown("### 🇺🇳 DATOS DE LAS DELEGACIONES")
        
        respuestas_modalidades = {}
        tot_alumnos = 0
        
        cols = st.columns(2)
        for idx, mod in enumerate(modalidades_evento):
            col_curr = cols[idx % 2]
            with col_curr:
                lbl = f"{mod['etiqueta_visible']} ({mod['delegados_por_unidad']} delegados/unidad)"
                cant = st.number_input(
                    lbl, 
                    min_value=0, 
                    max_value=int(mod.get('max_permitido', 5)), 
                    value=0, 
                    key=f"new_{id_modelo_actual}_{mod['clave_modalidad']}"
                )
                respuestas_modalidades[mod['clave_modalidad']] = cant
                tot_alumnos += cant * int(mod['delegados_por_unidad'])
                
        desglose_str = " | ".join([f"{k}:{v}" for k, v in respuestas_modalidades.items()])

        st.info(f"📊 **Total de participantes a inscribir:** {tot_alumnos} estudiantes + {cant_docentes} docente(s) acompañante(s).")
        
        submitted = st.form_submit_button("Enviar Preinscripción")
        
        if submitted:
            if not colegio or not direccion or not email_inst or not tel_inst or not docente_ape_nom or not docente_email or not docente_tel or not clave:
                st.error("Por favor completá todos los campos obligatorios (*).")
            elif tot_alumnos == 0:
                st.warning("Debés seleccionar al menos 1 delegación en alguna modalidad.")
            else:
                payload = {
                    "action": "REGISTRAR_DELEGACION",
                    "data": {
                        "id_modelo": id_modelo_actual,
                        "nombre_colegio": colegio,
                        "direccion_escuela": direccion,
                        "email_institucional": email_inst,
                        "telefono_institucional": tel_inst,
                        "docente_apellido_nombre": docente_ape_nom,
                        "docente_email": docente_email,
                        "docente_telefono": docente_tel,
                        "docentes_acompanantes": cant_docentes,
                        "secret_hash": clave,
                        "cupos_solicitados": tot_alumnos,
                        "desglose_modalidades": desglose_str
                    }
                }
                
                with st.spinner("Registrando preinscripción..."):
                    try:
                        res = requests.post(API_URL, json=payload).json()
                        if res.get("status") == "SUCCESS":
                            st.success(f"¡Preinscripción enviada con éxito para **{modelo_seleccionado}**! Código de delegación: **{res['data']['id_delegacion']}**")
                        else:
                            st.error(f"Error: {res.get('message')}")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")

# ---------------------------------------------------------
# MÓDULO 2: CARGAR COMPROBANTE DE PAGO
# ---------------------------------------------------------
elif menu == "2. Cargar Comprobante":
    st.subheader(f"Acreditación de Pago - {modelo_seleccionado}")
    
    with st.form("form_pago"):
        id_del = st.text_input("Código de Delegación (Ej: DEL-001) *")
        clave = st.text_input("Clave Secreta de la Escuela *", type="password")
        monto = st.number_input("Monto Transferido ($) *", min_value=1.0, step=100.0)
        archivo = st.file_uploader("Adjuntar Comprobante (PDF o Imagen) *", type=["pdf", "png", "jpg", "jpeg"])
        
        btn_pago = st.form_submit_button("Subir Comprobante")
        
        if btn_pago:
            if not id_del or not clave or not archivo:
                st.error("Completá todos los campos obligatorios.")
            else:
                file_bytes = archivo.read()
                base64_file = base64.b64encode(file_bytes).decode('utf-8')
                
                payload = {
                    "action": "SUBIR_COMPROBANTE_PAGO",
                    "data": {
                        "id_delegacion": id_del.strip().upper(),
                        "secret_hash": clave,
                        "monto": monto,
                        "file_base64": base64_file,
                        "file_name": archivo.name,
                        "file_mime": archivo.type
                    }
                }
                with st.spinner("Subiendo comprobante a Drive..."):
                    try:
                        res = requests.post(API_URL, json=payload).json()
                        if res.get("status") == "SUCCESS":
                            st.success("¡Comprobante recibido! Queda en revisión por el Secretariado.")
                        else:
                            st.error(f"Error: {res.get('message')}")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")

# ---------------------------------------------------------
# MÓDULO 3: CARGA DE NÓMINA Y FICHAS (LOGIN PRIVADO + CONFIRMACIÓN)
# ---------------------------------------------------------
elif menu == "3. Carga de Nómina y Fichas":
    st.subheader(f"Nómina de Participantes y Documentación - {modelo_seleccionado}")
    
    if "escuela_sesion" not in st.session_state:
        st.markdown("Ingresá las credenciales asignadas a tu institución para acceder al sistema.")
        
        with st.form("form_login_escuela"):
            input_email = st.text_input("📧 Correo Electrónico (Docente o Institucional):")
            input_pass = st.text_input("🔑 Contraseña Secreta:", type="password")
            btn_login = st.form_submit_button("Iniciar Sesión")

        if btn_login:
            if not input_email or not input_pass:
                st.error("Por favor completá ambos campos.")
            else:
                with st.spinner("Verificando credenciales..."):
                    delegaciones = cargar_todas_delegaciones_cached(id_modelo_actual)
                    
                    escuela_encontrada = None
                    email_clean = input_email.strip().lower()

                    for e in delegaciones:
                        mail_docente = str(e.get("docente_email", "")).strip().lower()
                        mail_inst = str(e.get("email_institucional", "")).strip().lower()
                        
                        if email_clean == mail_docente or email_clean == mail_inst:
                            escuela_encontrada = e
                            break

                    if not escuela_encontrada:
                        st.error("❌ Credenciales inválidas.")
                    else:
                        clave_guardada = str(escuela_encontrada.get("secret_hash", "")).strip()
                        if input_pass.strip() != clave_guardada:
                            st.error("❌ Credenciales inválidas.")
                        else:
                            st.session_state["escuela_sesion"] = escuela_encontrada
                            st.success("¡Sesión iniciada correctamente!")
                            st.rerun()

    else:
        escuela_activa = st.session_state["escuela_sesion"]
        id_del_seleccionado = escuela_activa.get("id_delegacion")

        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            st.info(f"🏫 Institución conectada: **{escuela_activa.get('nombre_colegio')}**")
        with col_s2:
            if st.button("Cerrar Sesión"):
                del st.session_state["escuela_sesion"]
                st.rerun()

        try:
            res_asig = requests.get(f"{API_URL}?action=GET_ASIGNACIONES_DELEGACION&id_delegacion={id_del_seleccionado}").json()
            asignaciones = res_asig.get("data", [])

            if not asignaciones:
                st.warning("Aún no se registran bancas de países asignadas para tu institución.")
            else:
                st.write(f"📋 **Bancas / Lugares Asignados ({len(asignaciones)}):**")

                for asig in asignaciones:
                    with st.expander(f"📌 {asig.get('organo')} — País / Representación: **{asig.get('pais')}**"):
                        with st.form(f"form_nom_{asig.get('id_asignacion')}"):
                            nombre = st.text_input("Nombre del Estudiante *")
                            apellido = st.text_input("Apellido del Estudiante *")
                            dni = st.text_input("DNI / Pasaporte *")
                            alergias = st.text_area("Alergias o Indicaciones Médicas", value="Ninguna")
                            
                            ficha_file = st.file_uploader("Ficha Médica (PDF/Imagen) *", type=["pdf", "png", "jpg", "jpeg"], key=f"f_{asig.get('id_asignacion')}")
                            aut_file = st.file_uploader("Autorización de Imagen (PDF/Imagen) *", type=["pdf", "png", "jpg", "jpeg"], key=f"a_{asig.get('id_asignacion')}")
                            
                            btn_nom = st.form_submit_button("Guardar Alumno")
                            
                            if btn_nom:
                                if not nombre or not apellido or not dni:
                                    st.error("Nombre, Apellido y DNI son obligatorios.")
                                else:
                                    f_b64, a_b64 = "", ""
                                    f_name, a_name = "", ""
                                    f_mime, a_mime = "", ""
                                    
                                    if ficha_file:
                                        f_b64 = base64.b64encode(ficha_file.read()).decode('utf-8')
                                        f_name = ficha_file.name
                                        f_mime = ficha_file.type
                                    if aut_file:
                                        a_b64 = base64.b64encode(aut_file.read()).decode('utf-8')
                                        a_name = aut_file.name
                                        a_mime = aut_file.type
                                        
                                    payload = {
                                        "action": "GUARDAR_PARTICIPANTE_NOMINA",
                                        "data": {
                                            "id_delegacion": id_del_seleccionado,
                                            "secret_hash": escuela_activa.get("secret_hash"),
                                            "id_modelo": id_modelo_actual,
                                            "id_asignacion": asig.get("id_asignacion"),
                                            "rol_mnu": f"{asig.get('organo')} - {asig.get('pais')}",
                                            "nombre": nombre,
                                            "apellido": apellido,
                                            "dni": dni,
                                            "alergias_medicas": alergias,
                                            "ficha_b64": f_b64, "ficha_name": f_name, "ficha_mime": f_mime,
                                            "aut_b64": a_b64, "aut_name": a_name, "aut_mime": a_mime
                                        }
                                    }
                                    res_save = requests.post(API_URL, json=payload).json()
                                    if res_save.get("status") == "SUCCESS":
                                        st.success("¡Alumno cargado con éxito!")
                                    else:
                                        st.error(f"Error: {res_save.get('message')}")

                # --- BOTÓN DE CONFIRMACIÓN DE CARGA TOTAL DE DOCUMENTACIÓN ---
                st.markdown("---")
                st.markdown("### 🏁 Finalización del Proceso")
                
                estado_actual = str(escuela_activa.get("estado", "REGISTRADO")).upper()
                
                if estado_actual == "DOCUMENTACION_COMPLETA":
                    st.success("✅ Ya confirmaste la carga total de tu documentación. El secretariado la está verificando.")
                else:
                    st.warning("⚠️ Una vez que hayas cargado a todos los participantes con sus fichas y autorizaciones, hacé clic en el botón para notificar al secretariado.")
                    if st.button("📤 Confirmar Carga Total de Documentación"):
                        payload_conf = {
                            "action": "CONFIRMAR_CARGA_DOCUMENTACION",
                            "data": {
                                "id_delegacion": id_del_seleccionado,
                                "secret_hash": escuela_activa.get("secret_hash")
                            }
                        }
                        with st.spinner("Enviando confirmación..."):
                            try:
                                res_conf = requests.post(API_URL, json=payload_conf).json()
                                if res_conf.get("status") == "SUCCESS":
                                    st.success("¡Documentación confirmada con éxito! Se ha notificado al equipo organizador.")
                                    # Actualizamos temporalmente el estado en la sesión para refrescar la vista
                                    escuela_activa["estado"] = "DOCUMENTACION_COMPLETA"
                                    st.rerun()
                                else:
                                    st.error(f"Error: {res_conf.get('message')}")
                            except Exception as e:
                                st.error(f"Error de conexión: {e}")

        except Exception as e:
            st.error(f"Error de conexión al obtener asignaciones: {e}")
