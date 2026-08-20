import streamlit as st
import requests
import base64

st.set_page_config(
    page_title="Gestión MNU - Portal Escuelas",
    page_icon="🇺🇳",
    layout="wide"
)

API_URL = "https://script.google.com/macros/s/AKfycbw99vCAavy6ELN2LD7-jDYEa5mt2_gXEMm7a6dySthwNq4yYplspJGRGhbaK-APMrfoqQ/exec"

st.title("🇺🇳 Portal de Inscripción y Carga - Modelos ONU")

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
    st.warning("El portal no tiene eventos habilitados en este momento.")
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
# MÓDULO 1: PREINSCRIPCIÓN
# ---------------------------------------------------------
if menu == "1. Preinscripción Escuela":
    st.subheader(f"Ficha de Inscripción por Escuela - {modelo_seleccionado}")
    
    with st.form("form_registro_unificado"):
        colegio = st.text_input("Nombre de la Institución / Colegio")
        docente = st.text_input("Docente / Tutor Acompañante")
        email = st.text_input("Correo Electrónico de Contacto")
        clave = st.text_input("Creá una Clave Secreta para el Portal", type="password")
        
        st.markdown("---")
        st.markdown("#### Seleccioná la cantidad de Delegaciones por Modalidad")
        
        col1, col2 = st.columns(2)
        with col1:
            del_5 = st.number_input("Sin CS ni ECOSOC (5 delegados)", min_value=0, max_value=5, value=0, key=f"{id_modelo_actual}_del5")
            del_7_eco = st.number_input("Sin CS con ECOSOC (7 delegados)", min_value=0, max_value=5, value=0, key=f"{id_modelo_actual}_del7eco")
            del_9_comp = st.number_input("Con CS y ECOSOC (9 delegados)", min_value=0, max_value=2, value=0, key=f"{id_modelo_actual}_del9")
        with col2:
            del_7_cs = st.number_input("Con CS sin ECOSOC (7 delegados)", min_value=0, max_value=2, value=0, key=f"{id_modelo_actual}_del7cs")
            del_davos = st.number_input("Foro de Davos (Unipersonales)", min_value=0, max_value=5, value=0, key=f"{id_modelo_actual}_davos")
            del_prensa = st.number_input("Comité de Prensa (3 delegados)", min_value=0, max_value=2, value=0, key=f"{id_modelo_actual}_prensa")
            
        tot_alumnos = (del_5 * 5) + (del_7_eco * 7) + (del_9_comp * 9) + (del_7_cs * 7) + (del_davos * 1) + (del_prensa * 3)
        desglose_str = f"5d:{del_5} | 7d_eco:{del_7_eco} | 9d:{del_9_comp} | 7d_cs:{del_7_cs} | davos:{del_davos} | prensa:{del_prensa}"

        st.info(f"📊 **Total de participantes a inscribir en la nómina:** {tot_alumnos} personas.")
        
        submitted = st.form_submit_button("Enviar Preinscripción")
        
        if submitted:
            if not colegio or not docente or not email or not clave:
                st.error("Por favor completá los datos institucionales obligatorios.")
            elif tot_alumnos == 0:
                st.warning("Debes seleccionar al menos 1 delegación en alguna modalidad.")
            else:
                payload = {
                    "action": "REGISTRAR_DELEGACION",
                    "data": {
                        "id_modelo": id_modelo_actual,
                        "nombre_colegio": colegio,
                        "docente_cargo": docente,
                        "email_contacto": email,
                        "secret_hash": clave,
                        "cupos_solicitados": tot_alumnos,
                        "desglose_modalidades": desglose_str
                    }
                }
                
                with st.spinner("Registrando preinscripción en el sistema..."):
                    try:
                        res = requests.post(API_URL, json=payload).json()
                        if res.get("status") == "SUCCESS":
                            st.success(f"¡Preinscripción enviada para **{modelo_seleccionado}**! ID asignado: **{res['data']['id_delegacion']}**")
                        else:
                            st.error(f"Error: {res.get('message')}")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")

# ---------------------------------------------------------
# MÓDULO 2: CARGA DE COMPROBANTES DE PAGO
# ---------------------------------------------------------
elif menu == "2. Cargar Comprobante":
    st.subheader(f"Subida de Comprobantes - {modelo_seleccionado}")
    
    id_delegacion = st.text_input("Ingresá tu ID de Delegación (Ej: DEL-001)")
    monto = st.number_input("Monto Transferido ($)", min_value=100)
    archivo = st.file_uploader("Adjuntá el comprobante (JPG, PNG o PDF)", type=["jpg", "png", "pdf"])
    
    if st.button("Subir Comprobante"):
        if not id_delegacion or not archivo:
            st.warning("Completá tu ID y adjuntá el archivo.")
        else:
            bytes_file = archivo.read()
            base64_file = base64.b64encode(bytes_file).decode('utf-8')
            
            payload = {
                "action": "SUBIR_COMPROBANTE",
                "data": {
                    "id_modelo": id_modelo_actual,
                    "id_delegacion": id_delegacion,
                    "monto": monto,
                    "file_name": archivo.name,
                    "mime_type": archivo.type,
                    "base64_file": base64_file
                }
            }
            
            with st.spinner("Subiendo archivo a Google Drive..."):
                try:
                    res = requests.post(API_URL, json=payload).json()
                    if res.get("status") == "SUCCESS":
                        st.success("Comprobante subido correctamente. En revisión por el Secretariado.")
                    else:
                        st.error(f"Error al subir: {res.get('message')}")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

# ---------------------------------------------------------
# MÓDULO 3: CARGA DE NÓMINA POR PAÍS DELEGACIÓN
# ---------------------------------------------------------
elif menu == "3. Carga de Nómina y Fichas":
    st.subheader(f"Carga de Integrantes de la Delegación - {modelo_seleccionado}")
    
    with st.spinner("Cargando escuelas habilitadas..."):
        try:
            res_del = requests.get(f"{API_URL}?action=GET_DELEGACIONES_APROBADAS&id_modelo={id_modelo_actual}").json()
            delegaciones_aprobadas = res_del.get("data", [])
        except Exception as e:
            delegaciones_aprobadas = []
            st.error(f"Error al consultar el servidor: {e}")

    if not delegaciones_aprobadas:
        st.warning("⚠️ No hay escuelas con pago **APROBADO** para este modelo aún.")
    else:
        opciones_del = {f"{d['id_delegacion']} - {d['nombre_colegio']}": d for d in delegaciones_aprobadas}
        del_seleccionada_label = st.selectbox("Seleccioná tu Escuela / Institución Aprobada:", list(opciones_del.keys()))
        delegacion_actual = opciones_del[del_seleccionada_label]
        id_delegacion_sel = delegacion_actual['id_delegacion']

        st.markdown("---")
        st.markdown("#### 🔒 Autenticación del Docente")
        
        col_auth1, col_auth2 = st.columns(2)
        with col_auth1:
            email_ingresado = st.text_input("Correo Electrónico de Contacto:", key=f"auth_email_{id_delegacion_sel}")
        with col_auth2:
            clave_ingresada = st.text_input("Contraseña Secreta:", type="password", key=f"auth_pass_{id_delegacion_sel}")

        if email_ingresado and clave_ingresada:
            email_valido = email_ingresado.strip().lower() == str(delegacion_actual.get('email_contacto', '')).strip().lower()
            clave_valida = clave_ingresada == str(delegacion_actual.get('secret_hash', ''))

            if email_valido and clave_valida:
                nombre_docente = delegacion_actual.get('docente_cargo', 'Docente/Tutor')
                nombre_colegio = delegacion_actual.get('nombre_colegio', '')
                
                st.success(f"👋 **¡Hola, {nombre_docente}!** Bienvenido/a al portal de **{nombre_colegio}**.")
                
                try:
                    res_asig = requests.get(f"{API_URL}?action=GET_ASIGNACIONES_DELEGACION&id_delegacion={id_delegacion_sel}").json()
                    asignaciones = res_asig.get("data", [])
                except Exception as e:
                    asignaciones = []
                    st.error(f"Error al consultar asignaciones: {e}")

                if not asignaciones:
                    st.info("ℹ️ Tu pago está APROBADO, pero el Secretariado todavía no le asignó países a tu escuela.")
                else:
                    paises_dict = {}
                    for a in asignaciones:
                        p = a.get('pais', 'Delegación Sin País')
                        if p not in paises_dict:
                            paises_dict[p] = []
                        paises_dict[p].append(a)

                    pais_elegido = st.selectbox("🌍 Seleccioná el País / Delegación a cargar:", list(paises_dict.keys()))
                    cargos_pais = paises_dict[pais_elegido]
                    cant_delegados_pais = len(cargos_pais)

                    st.markdown(f"📋 **Cargando Integrantes para {pais_elegido} ({cant_delegados_pais} delegados requeridos)**")

                    with st.form(key=f"form_pais_{id_delegacion_sel}_{pais_elegido}"):
                        datos_a_enviar = []
                        
                        for idx, cargo in enumerate(cargos_pais, 1):
                            comision_nombre = cargo.get('organo', f'Comisión #{idx}')
                            st.markdown(f"### 👤 Delegado #{idx}: {pais_elegido} - {comision_nombre}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                nom = st.text_input("Nombre y Apellido del Estudiante", key=f"nom_{id_delegacion_sel}_{pais_elegido}_{idx}")
                                dni = st.text_input("DNI / Documento", key=f"dni_{id_delegacion_sel}_{pais_elegido}_{idx}")
                            
                            with col2:
                                ale = st.text_area("Alergias / Dieta Especial / Cuidados Médicos", value="Ninguna", key=f"ale_{id_delegacion_sel}_{pais_elegido}_{idx}")
                            
                            col_doc1, col_doc2 = st.columns(2)
                            with col_doc1:
                                fic = st.file_uploader("Ficha Médica (PDF/Foto)", type=["pdf", "jpg", "png"], key=f"fic_{id_delegacion_sel}_{pais_elegido}_{idx}")
                            with col_doc2:
                                aut = st.file_uploader("Autorización de Imagen (PDF/Foto)", type=["pdf", "jpg", "png"], key=f"aut_{id_delegacion_sel}_{pais_elegido}_{idx}")
                            
                            st.markdown("---")
                            
                            datos_a_enviar.append({
                                "idx": idx,
                                "pais": pais_elegido,
                                "comision": comision_nombre,
                                "nom": nom,
                                "dni": dni,
                                "ale": ale,
                                "fic": fic,
                                "aut": aut
                            })

                        btn_guardar_pais = st.form_submit_button(f"🚀 GUARDAR TODOS LOS DELEGADOS DE {pais_elegido.upper()}")

                    if btn_guardar_pais:
                        errores = []
                        for d in datos_a_enviar:
                            if not d["nom"] or not d["dni"]:
                                errores.append(f"Faltan datos obligatorios en Delegado #{d['idx']} ({d['comision']}).")

                        if errores:
                            for err in errores:
                                st.error(err)
                        else:
                            con_exito = 0
                            with st.spinner(f"Subiendo fichas y guardando delegación de {pais_elegido}..."):
                                for d in datos_a_enviar:
                                    b64_ficha, mime_ficha, ext_ficha = "", "", ""
                                    if d["fic"]:
                                        b64_ficha = base64.b64encode(d["fic"].read()).decode('utf-8')
                                        mime_ficha = d["fic"].type
                                        ext_ficha = d["fic"].name.split('.')[-1]

                                    b64_aut, mime_aut, ext_aut = "", "", ""
                                    if d["aut"]:
                                        b64_aut = base64.b64encode(d["aut"].read()).decode('utf-8')
                                        mime_aut = d["aut"].type
                                        ext_aut = d["aut"].name.split('.')[-1]

                                    payload = {
                                        "action": "GUARDAR_NOMINA",
                                        "data": {
                                            "id_modelo": id_modelo_actual,
                                            "id_delegacion": id_delegacion_sel,
                                            "nombre_completo": d["nom"],
                                            "dni": d["dni"],
                                            "rol_mnu": f"DELEGADO ({d['pais']} - {d['comision']})",
                                            "alergias_medicas": d["ale"],
                                            "base64_ficha": b64_ficha,
                                            "mime_ficha": mime_ficha,
                                            "ext_ficha": ext_ficha,
                                            "base64_autorizacion": b64_aut,
                                            "mime_autorizacion": mime_aut,
                                            "ext_autorizacion": ext_aut
                                        }
                                    }

                                    try:
                                        res = requests.post(API_URL, json=payload).json()
                                        if res.get("status") == "SUCCESS":
                                            con_exito += 1
                                    except Exception:
                                        pass

                            if con_exito > 0:
                                st.balloons()
                                st.success(f"🎉 ¡Se guardó exitosamente la delegación completa de **{pais_elegido}** ({con_exito} estudiantes)!")
            else:
                st.error("❌ El correo o la contraseña ingresados son incorrectos.")
        else:
            st.info("👈 Por favor ingresá las credenciales para acceder a la carga de la delegación.")
