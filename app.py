import base64
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import streamlit as st

st.set_page_config(
    page_title="Inscripción y Gestión Escolar - Modelos ONU",
    page_icon="🏫",
    layout="wide",
)

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()
API_URL = st.secrets["API_URL"]

# IDs de carpetas desde tus enlaces de Google Drive
FOLDER_COMPROBANTES = "1-QVd95Y2butIg9DNp3cPuIQI6sII50Rk"
FOLDER_FICHAS = "1VSSud30QL9nSLbfu4jAz-dJ9q2rcRg1E"


# ==========================================
# FUNCIONES AUXILIARES Y BASE DE DATOS
# ==========================================
def subir_archivo_a_drive_via_script(
    file_bytes, file_name, mime_type, folder_id
):
    try:
        base64_data = base64.b64encode(file_bytes).decode("utf-8")
        payload = {
            "action": "UPLOAD_FILE",
            "fileData": base64_data,
            "fileName": file_name,
            "mimeType": mime_type,
            "folderId": folder_id,
        }
        res = requests.post(
            API_URL, json=payload, timeout=45, allow_redirects=True
        )
        try:
            res_json = res.json()
            url_devuelta = res_json.get("fileUrl", "")
            if url_devuelta:
                return url_devuelta
        except Exception:
            pass
        
        # Respaldo si la respuesta JSON falla pero el script procesó
        return f"https://drive.google.com/drive/folders/{folder_id}"
    except Exception:
        return f"https://drive.google.com/drive/folders/{folder_id}"


def obtener_modelos_activos():
    try:
        docs = db.collection("modelos").stream()
        modelos = []
        for doc in docs:
            m = doc.to_dict()
            m["id_modelo"] = doc.id
            modelos.append(m)
        return modelos
    except Exception as e:
        st.error(f"Error al conectar con Firestore: {e}")
        return []


def obtener_parametros_comites(id_modelo):
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("parametros_comites", [])
        return []
    except Exception:
        return []


def preinscribir_escuela(datos_escuela):
    try:
        docente_email = str(datos_escuela.get("docente_email", "")).strip().lower()
        if not docente_email or "@" not in docente_email:
            return False, "Debe ingresar un correo electrónico válido."

        doc_ref = db.collection("delegaciones").document(docente_email)
        if doc_ref.get().exists:
            return (
                False,
                f"El correo '{docente_email}' ya se encuentra preinscripto.",
            )

        payload = {
            "id_delegacion": docente_email,
            "estado": "PREINSCRIPTO",
            "fecha_registro": firestore.SERVER_TIMESTAMP,
            **datos_escuela,
        }

        doc_ref.set(payload)
        return True, docente_email
    except Exception as e:
        return False, f"Error al registrar la institución: {e}"


def validar_acceso_docente(email_doc, hash_ingresado):
    try:
        email_clean = str(email_doc).strip().lower()
        doc = db.collection("delegaciones").document(email_clean).get()
        if doc.exists:
            datos = doc.to_dict()
            if str(datos.get("secret_hash")).strip() == str(hash_ingresado).strip():
                datos["id"] = doc.id
                return True, datos
            return False, "Clave de acceso incorrecta."
        return False, "El correo electrónico no se encuentra registrado."
    except Exception as e:
        return False, f"Error al validar acceso: {e}"


def obtener_bancas_asignadas(email_doc):
    try:
        email_clean = str(email_doc).strip().lower()
        docs = (
            db.collection("delegaciones")
            .document(email_clean)
            .collection("asignaciones")
            .stream()
        )
        return [doc.to_dict() for doc in docs]
    except Exception:
        return []


def guardar_participante_nomina(email_doc, dni, datos_participante):
    try:
        email_clean = str(email_doc).strip().lower()
        db.collection("delegaciones").document(email_clean).collection(
            "integrantes"
        ).document(str(dni)).set(datos_participante, merge=True)
        return True, "Participante guardado correctamente."
    except Exception as e:
        return False, f"Error al guardar participante: {e}"


def registrar_pago_comprobante(email_doc, id_modelo, monto, drive_url):
    try:
        pago_ref = db.collection("pagos").document()
        payload = {
            "id_delegacion": str(email_doc).strip().lower(),
            "id_modelo": str(id_modelo),
            "monto": float(monto),
            "drive_file_url": drive_url,
            "estado_pago": "PENDIENTE",
            "fecha_subida": firestore.SERVER_TIMESTAMP,
        }
        pago_ref.set(payload)
        return True, pago_ref.id
    except Exception as e:
        return False, str(e)


def actualizar_estado_legajo(email_doc, estado):
    try:
        email_clean = str(email_doc).strip().lower()
        db.collection("delegaciones").document(email_clean).set(
            {"estado": estado}, merge=True
        )
        return True
    except Exception:
        return False


def notificar_apps_script(action, data):
    try:
        requests.post(API_URL, json={"action": action, "data": data}, timeout=5)
    except Exception:
        pass


# ==========================================
# INTERFAZ PORTAL DOCENTE
# ==========================================
st.title("🏫 Portal de Instituciones - Modelos ONU")

menu = st.sidebar.selectbox(
    "Seleccionar Opción:",
    [
        "📝 Preinscripción Institucional",
        "🔑 Ingreso a Mi Delegación",
        "💳 Subir Comprobante de Pago",
        "📋 Carga de Nómina y Documentación",
    ],
)

# 1. PREINSCRIPCIÓN
if menu == "📝 Preinscripción Institucional":
    st.subheader("📝 Formulario de Preinscripción Escolar")

    modelos = obtener_modelos_activos()
    if not modelos:
        st.warning(
            "⚠️ No hay modelos activos en la base de datos. Por favor contacte"
            " a Secretaría para habilitar un evento."
        )
        st.stop()

    dict_mods_full = {
        m.get("nombre_visible", m.get("id_modelo")): m for m in modelos
    }
    mod_sel = st.selectbox(
        "Seleccionar Modelo ONU:", list(dict_mods_full.keys())
    )

    modelo_objeto = dict_mods_full[mod_sel]
    id_modelo_elegido = modelo_objeto.get("id_modelo")
    comites = obtener_parametros_comites(id_modelo_elegido)

    with st.form("form_preinscripcion"):
        st.markdown("### 🏛️ Datos de la Institución")
        col1, col2 = st.columns(2)
        with col1:
            nombre_colegio = st.text_input(
                "Nombre de la Institución Educativa (con N° DIPE/CUE):"
            )
            direccion_escuela = st.text_input(
                "Dirección (Localidad, Provincia, País):"
            )
            email_institucional = st.text_input("Correo Electrónico:")
            telefono_institucional = st.text_input("Número de Teléfono:")

        with col2:
            st.markdown("### 👨‍🏫 Datos del Responsable / Docente")
            docente_apellido_nombre = st.text_input("Apellido y Nombre:")
            docente_email = st.text_input(
                "Correo Electrónico Docente (Será su usuario) *:"
            ).strip().lower()
            docente_telefono = st.text_input("Teléfono Móvil:")
            secret_hash = st.text_input(
                "Crear Clave de Acceso para la Escuela *:", type="password"
            ).strip()

        st.markdown("---")
        st.markdown("### 🇺🇳 Datos de las Delegaciones y Comisiones")

        desglose_seleccionado = {}
        total_cupos_calculados = 0

        if comites:
            secciones = {}
            for c in comites:
                sec = str(c.get("clave_seccion", "GENERAL")).strip()
                if sec not in secciones:
                    secciones[sec] = []
                secciones[sec].append(c)

            for sec_nombre, lista_comites in secciones.items():
                col_sec, col_cant = st.columns([3, 1])
                nombres_comites = ", ".join(
                    [
                        str(x.get("organo_comite", "")).strip()
                        for x in lista_comites
                    ]
                )
                integrantes_totales = sum(
                    [
                        int(x.get("integrantes_por_banca", 1))
                        for x in lista_comites
                    ]
                )

                max_permiso = 4
                for x in lista_comites:
                    val_max = x.get("max_delegaciones_seccion")
                    if val_max is not None and str(val_max).isdigit():
                        max_permiso = int(val_max)
                        break

                opciones_cant = list(range(0, max_permiso + 1))

                with col_sec:
                    st.write(
                        f"**Sección {sec_nombre}:** {nombres_comites} "
                        f"(*{integrantes_totales} participantes por delegación"
                        f" - Máx: {max_permiso}*)"
                    )
                with col_cant:
                    cant = st.selectbox(
                        f"Cantidad ({sec_nombre}):",
                        options=opciones_cant,
                        key=f"sec_{sec_nombre}",
                    )
                    if cant > 0:
                        desglose_seleccionado[sec_nombre] = cant
                        total_cupos_calculados += cant * integrantes_totales
        else:
            st.warning("⚠️ No se han parametrizado comisiones para este modelo.")

        docentes_acompanantes = st.number_input(
            "Docentes Acompañantes:", min_value=1, value=1, step=1
        )
        st.info(
            f"📊 **Total de participantes acumulados:** {total_cupos_calculados}"
            " estudiantes."
        )

        if st.form_submit_button("Enviar Preinscripción Institucional"):
            if not nombre_colegio or not docente_email or not secret_hash:
                st.error("Por favor completa los campos obligatorios.")
            elif total_cupos_calculados == 0:
                st.error("Seleccione al menos 1 delegación para inscribir.")
            else:
                datos_escuela = {
                    "nombre_colegio": nombre_colegio,
                    "direccion_escuela": direccion_escuela,
                    "email_institucional": email_institucional,
                    "telefono_institucional": telefono_institucional,
                    "docente_apellido_nombre": docente_apellido_nombre,
                    "docente_email": docente_email,
                    "docente_telefono": docente_telefono,
                    "cupos_solicitados": total_cupos_calculados,
                    "desglose_modalidades": str(desglose_seleccionado),
                    "docentes_acompanantes": docentes_acompanantes,
                    "secret_hash": secret_hash,
                    "id_modelo": id_modelo_elegido,
                }
                ok, msg = preinscribir_escuela(datos_escuela)
                if ok:
                    st.success(
                        "¡Preinscripción exitosa! Su usuario de acceso es:"
                        f" **{docente_email}**."
                    )
                    notificar_apps_script(
                        "NUEVA_PREINSCRIPCION",
                        {
                            "id_delegacion": docente_email,
                            "docente_email": docente_email,
                        },
                    )
                else:
                    st.error(msg)

# 2. INGRESO A MI DELEGACIÓN
elif menu == "🔑 Ingreso a Mi Delegación":
    st.subheader("🔑 Estado de mi Institución y Asignaciones")
    with st.form("form_login_escuela"):
        email_doc = st.text_input("Email del Docente Responsable:").strip().lower()
        hash_ingresado = st.text_input(
            "Clave de Acceso:", type="password"
        ).strip()

        if st.form_submit_button("Consultar Estado"):
            ok, escuela = validar_acceso_docente(email_doc, hash_ingresado)
            if ok:
                st.success("¡Acceso correcto!")
                st.markdown(f"### 🏛️ {escuela.get('nombre_colegio')}")
                bancas = obtener_bancas_asignadas(email_doc)
                if bancas:
                    for b in bancas:
                        st.write(
                            f"- **{b.get('organo_comite', b.get('organo'))}** —"
                            f" País: **{b.get('pais')}**"
                        )
                else:
                    st.info("Aún no se han publicado las bancas asignadas.")
            else:
                st.error(escuela)

# 3. SUBIR COMPROBANTE DE PAGO
elif menu == "💳 Subir Comprobante de Pago":
    st.subheader("💳 Subir Comprobante de Pago")
    with st.form("form_pago"):
        email_doc = st.text_input("Email del Docente Responsable:").strip().lower()
        hash_pago = st.text_input("Clave de Acceso:", type="password").strip()
        monto_pago = st.number_input(
            "Monto Abonado ($):", min_value=0.0, format="%.2f"
        )
        archivo_comprobante = st.file_uploader(
            "Seleccionar Comprobante de Pago (PDF o Imagen):",
            type=["pdf", "png", "jpg", "jpeg"],
        )

        if st.form_submit_button("Enviar Comprobante"):
            if not email_doc or not hash_pago or not archivo_comprobante:
                st.error("Completa todos los campos y adjunta el comprobante.")
            else:
                ok_val, escuela = validar_acceso_docente(email_doc, hash_pago)
                if not ok_val:
                    st.error(f"Error de acceso: {escuela}")
                else:
                    try:
                        with st.spinner("Procesando y registrando comprobante..."):
                            file_bytes = archivo_comprobante.read()
                            file_name = f"Pago_{email_doc}_{archivo_comprobante.name}"
                            mime_type = archivo_comprobante.type

                            res_url = subir_archivo_a_drive_via_script(
                                file_bytes,
                                file_name,
                                mime_type,
                                FOLDER_COMPROBANTES,
                            )

                            id_modelo = escuela.get("id_modelo", "modelo_general")
                            ok_pago, idPago = registrar_pago_comprobante(
                                email_doc, id_modelo, monto_pago, res_url
                            )
                            
                            if ok_pago:
                                st.success(
                                    "¡Comprobante procesado y registrado correctamente en el sistema! ID de pago: "
                                    f"`{idPago}`"
                                )
                                notificar_apps_script(
                                    "NUEVO_PAGO_REGISTRADO",
                                    {
                                        "id_delegacion": email_doc,
                                        "monto": monto_pago,
                                        "drive_url": res_url,
                                    },
                                )
                                st.balloons()
                            else:
                                st.error(f"Error al registrar en la base de datos: {idPago}")
                    except Exception as ex:
                        st.error(f"Error crítico en el proceso: {ex}")

# 4. CARGA DE NÓMINA Y DOCUMENTACIÓN
elif menu == "📋 Carga de Nómina y Documentación":
    st.subheader("📋 Registro de Participantes y Documentación")

    with st.form("form_verif_nomina"):
        st.markdown("### 🔑 Acceso al Legajo Escolar")
        email_doc_nom = st.text_input("Email del Docente Responsable:").strip().lower()
        hash_nom = st.text_input("Clave de Acceso:", type="password").strip()
        if st.form_submit_button("Ingresar a Carga de Nómina"):
            st.session_state["email_doc_nom"] = email_doc_nom
            st.session_state["hash_nom"] = hash_nom

    if (
        "email_doc_nom" in st.session_state
        and st.session_state["email_doc_nom"]
    ):
        email_doc_nom = st.session_state["email_doc_nom"]
        hash_nom = st.session_state.get("hash_nom", "")

        ok_acc, escuela = validar_acceso_docente(email_doc_nom, hash_nom)

        if not ok_acc:
            st.error("❌ Email o contraseña incorrecta.")
        else:
            id_modelo = escuela.get("id_modelo", "")
            st.success(
                f"🏛️ **Institución:** {escuela.get('nombre_colegio')}"
                f" (`{email_doc_nom}`)"
            )

            bancas_asignadas = obtener_bancas_asignadas(email_doc_nom)
            comites_reglas = obtener_parametros_comites(id_modelo)
            mapa_reglas = {
                str(c.get("organo_comite")).strip().upper(): c
                for c in comites_reglas
            }

            if not bancas_asignadas:
                st.warning(
                    "⚠️ Tu institución aún no tiene bancas/países asignados por"
                    " la organización."
                )
            else:
                dict_bancas = {
                    f"{b.get('organo_comite', b.get('organo'))} — {b.get('pais')}": b
                    for b in bancas_asignadas
                }
                banca_sel_nombre = st.selectbox(
                    "Seleccionar Banca / Asignación para cargar participante:",
                    list(dict_bancas.keys()),
                )
                banca_objeto = dict_bancas[banca_sel_nombre]

                organo_banca = (
                    str(
                        banca_objeto.get(
                            "organo_comite", banca_objeto.get("organo")
                        )
                    )
                    .strip()
                    .upper()
                )
                regla_comite = mapa_reglas.get(organo_banca, {})
                integrantes_permitidos = int(
                    regla_comite.get("integrantes_por_banca", 2)
                )

                st.info(
                    f"📌 El órgano **{organo_banca}** permite hasta"
                    f" **{integrantes_permitidos} estudiante(s)**."
                )

                with st.form("form_estudiante"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        nombre = st.text_input("Nombre del Estudiante:")
                        apellido = st.text_input("Apellido:")
                        dni = st.text_input("DNI:")
                    with col_b:
                        alergias = st.text_input(
                            "Alergias / Condición Médica:", value="Ninguna"
                        )
                        file_ficha = st.file_uploader(
                            "Ficha Médica (PDF/Imagen):",
                            type=["pdf", "png", "jpg", "jpeg"],
                        )
                        file_aut = st.file_uploader(
                            "Autorización Firmada (PDF/Imagen):",
                            type=["pdf", "png", "jpg", "jpeg"],
                        )

                    comentarios_participante = st.text_area(
                        "Comentarios / Observaciones sobre este participante"
                        " (opcional):",
                        placeholder=(
                            "Escriba aquí aclaraciones médicas, de"
                            " documentación o generales..."
                        ),
                    )

                    if st.form_submit_button(
                        "💾 Guardar Participante en Nómina"
                    ):
                        if not nombre or not apellido or not dni:
                            st.error(
                                "Por favor completa Nombre, Apellido y DNI."
                            )
                        else:
                            ficha_url = ""
                            aut_url = ""

                            with st.spinner(
                                "Subiendo documentación y guardando..."
                            ):
                                if file_ficha:
                                    ficha_url = subir_archivo_a_drive_via_script(
                                        file_ficha.read(),
                                        f"Ficha_{dni}_{file_ficha.name}",
                                        file_ficha.type,
                                        FOLDER_FICHAS,
                                    )
                                if file_aut:
                                    aut_url = subir_archivo_a_drive_via_script(
                                        file_aut.read(),
                                        f"Aut_{dni}_{file_aut.name}",
                                        file_aut.type,
                                        FOLDER_FICHAS,
                                    )

                            datos_estudiante = {
                                "nombre": nombre,
                                "apellido": apellido,
                                "dni": dni,
                                "alergias_medicas": alergias,
                                "ficha_medica_id": ficha_url,
                                "autorizacion_id": aut_url,
                                "comentarios": comentarios_participante,
                                "rol_mnu": "Delegado/a",
                                "id_asignacion": banca_objeto.get(
                                    "id_asignacion", organo_banca
                                ),
                            }
                            ok_g, msg_g = guardar_participante_nomina(
                                email_doc_nom, dni, datos_estudiante
                            )
                            if ok_g:
                                st.success(
                                    f"✅ ¡{nombre} {apellido} guardado/a con"
                                    " éxito!"
                                )
                                st.rerun()
                            else:
                                st.error(msg_g)

                st.markdown("---")
                st.markdown("### 🚨 Cierre Oficial de Carga")
                st.warning(
                    "⚠️ **IMPORTANTE:** Una vez que haya cargado a **TODOS** los"
                    " estudiantes de **TODAS** sus delegaciones asignadas,"
                    " presione el botón inferior para notificar al Secretariado."
                )

                st.markdown(
                    """
                    <style>
                    div.stButton > button:first-child {
                        background-color: #D32F2F !important;
                        color: white !important;
                        font-size: 18px !important;
                        font-weight: bold !important;
                        padding: 15px 25px !important;
                        border-radius: 8px !important;
                        border: none !important;
                        width: 100% !important;
                    }
                    div.stButton > button:first-child:hover {
                        background-color: #B71C1C !important;
                        color: white !important;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    "🔴 CONFIRMAR CARGA COMPLETA DE TODA LA DELEGACIÓN (APRETAR"
                    " SOLO UNA VEZ SUBIDA TODA LA DOCUMENTACIÓN)"
                ):
                    actualizar_estado_legajo(email_doc_nom, "CARGA_COMPLETA")
                    notificar_apps_script(
                        "CONFIRMAR_CARGA_DOCUMENTACION",
                        {
                            "id_delegacion": email_doc_nom,
                            "secret_hash": hash_nom,
                            "email_docente": email_doc_nom,
                        },
                    )
                    st.balloons()
                    st.success(
                        "🎉 **¡Carga de documentación confirmada con éxito!**"
                        " Se ha enviado un correo electrónico de confirmación"
                        " a su casilla con la constancia de recepción."
                    )
