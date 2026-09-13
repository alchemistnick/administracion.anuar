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

# Estilo moderno adaptable a Modo Oscuro y Claro
modern_styling = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    
    div.stForm {
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        letter-spacing: 0.3px;
        transition: all 0.3s ease;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    </style>
"""
st.markdown(modern_styling, unsafe_allow_html=True)


@st.cache_resource
def inicializar_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()


db = inicializar_firebase()

# Carga segura y tolerante a fallos de secretos
try:
    API_URL = st.secrets.get("API_URL") or st.secrets["api"]["URL"]
except Exception:
    API_URL = ""

try:
    FOLDER_COMPROBANTES = st.secrets.get("folder_comprobantes") or st.secrets["drive"]["folder_comprobantes"]
except Exception:
    FOLDER_COMPROBANTES = "1-QVd95Y2butIg9DNp3cPuIQI6sII50Rk"

try:
    FOLDER_FICHAS = st.secrets.get("folder_fichas") or st.secrets["drive"]["folder_fichas"]
except Exception:
    FOLDER_FICHAS = "1VSSud30QL9nSLbfu4jAz-dJ9q2rcRg1E"

try:
    FOLDER_SEGUROS = st.secrets.get("folder_seguros") or st.secrets["drive"].get("folder_seguros", "1-QVd95Y2butIg9DNp3cPuIQI6sII50Rk")
except Exception:
    FOLDER_SEGUROS = "1-QVd95Y2butIg9DNp3cPuIQI6sII50Rk"


def mostrar_encabezado_portal():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, rgba(30, 41, 59, 0.05) 0%, rgba(51, 65, 85, 0.1) 100%); border-radius: 16px; border: 1px solid rgba(128, 128, 128, 0.15); margin-bottom: 1rem;">
                <h2 style="margin: 0; font-size: 1.6rem; font-weight: 900; background: linear-gradient(90deg, #1e293b, #0f172a); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">ANU-AR</h2>
                <p style="margin: 2px 0 0 0; font-size: 0.85rem; font-weight: 600; opacity: 0.6;">MODELOS DE NACIONES UNIDAS</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown(
            """
            <div style="text-align: center; margin-top: -5px; margin-bottom: 2rem;">
                <h1 style="font-size: 1.8rem; font-weight: 800; background: linear-gradient(90deg, #3b82f6, #1d4ed8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Portal de Instituciones</h1>
                <p style="margin: 0; font-size: 0.95rem; opacity: 0.75;">Gestión Oficial y Preinscripciones — Modelos ONU</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


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
            API_URL, json=payload, timeout=60, allow_redirects=True
        )
        res_json = res.json()
        if res_json.get("status") == "success":
            file_url = res_json.get("fileUrl") or res_json.get("url")
            if file_url:
                return True, file_url
        return False, f"Error del Script: {res_json.get('message', 'Desconocido')}"
    except Exception as e:
        return False, f"Excepción de red: {e}"


@st.cache_data(ttl=600)
def obtener_modelos_activos():
    try:
        docs = db.collection("modelos").stream()
        return [{**doc.to_dict(), "id_modelo": doc.id} for doc in docs]
    except Exception as e:
        st.error(f"Error al conectar con Firestore: {e}")
        return []


@st.cache_data(ttl=600)
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
        id_modelo_nuevo = str(datos_escuela.get("id_modelo", ""))

        docs_existentes = (
            db.collection("delegaciones")
            .where("docente_email", "==", docente_email)
            .where("id_modelo", "==", id_modelo_nuevo)
            .stream()
        )
        if list(docs_existentes):
            return False, f"El correo '{docente_email}' ya se encuentra preinscripto en este modelo."

        id_doc_delegacion = f"{docente_email}_{id_modelo_nuevo}"
        doc_ref = db.collection("delegaciones").document(id_doc_delegacion)

        payload = {
            "id_delegacion": id_doc_delegacion,
            "estado": "PREINSCRIPTO",
            "fecha_registro": firestore.SERVER_TIMESTAMP,
            **datos_escuela,
        }
        doc_ref.set(payload, merge=True)
        return True, id_doc_delegacion
    except Exception as e:
        return False, f"Error al registrar: {e}"


def validar_acceso_docente(email_doc, hash_ingresado, id_modelo_login=""):
    try:
        email_clean = str(email_doc).strip().lower()
        query = db.collection("delegaciones").where("docente_email", "==", email_clean)
        if id_modelo_login:
            query = query.where("id_modelo", "==", str(id_modelo_login))
            
        docs = list(query.stream())
        if docs:
            for doc in docs:
                datos = doc.to_dict()
                if str(datos.get("secret_hash")).strip() == str(hash_ingresado).strip():
                    datos["id"] = doc.id
                    return True, datos
            return False, "Clave de acceso incorrecta."
        return False, "El correo electrónico no se encuentra registrado en este modelo."
    except Exception as e:
        return False, f"Error al validar acceso: {e}"


@st.cache_data(ttl=60)
def obtener_bancas_asignadas(id_delegacion_doc):
    try:
        docs = (
            db.collection("delegaciones")
            .document(str(id_delegacion_doc))
            .collection("asignaciones")
            .stream()
        )
        return [doc.to_dict() for doc in docs]
    except Exception:
        return []


def obtener_pagos_delegacion(id_delegacion_doc):
    try:
        docs = db.collection("pagos").where("id_delegacion", "==", str(id_delegacion_doc)).stream()
        pagos = []
        for doc in docs:
            p = doc.to_dict()
            p["id_pago"] = doc.id
            pagos.append(p)
        return pagos
    except Exception:
        return []


def guardar_participante_nomina(id_delegacion_doc, dni, datos_participante):
    try:
        id_asig_raw = str(datos_participante.get("id_asignacion", "general"))
        id_asig_limpio = id_asig_raw.replace(" ", "_").replace("/", "_").lower()
        id_documento_integrante = f"{dni}_{id_asig_limpio}"

        db.collection("delegaciones").document(str(id_delegacion_doc)).collection(
            "integrantes"
        ).document(id_documento_integrante).set(datos_participante, merge=True)
        return True, "Participante guardado correctamente."
    except Exception as e:
        return False, f"Error al guardar participante: {e}"


def registrar_pago_comprobante(id_delegacion_doc, email_doc, id_modelo, monto, drive_url):
    try:
        pago_ref = db.collection("pagos").document()
        payload = {
            "id_delegacion": str(id_delegacion_doc),
            "docente_email": str(email_doc).strip().lower(),
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


def actualizar_poliza_seguro(id_delegacion_doc, url_seguro):
    try:
        db.collection("delegaciones").document(str(id_delegacion_doc)).set(
            {"poliza_seguro_url": url_seguro}, merge=True
        )
        return True
    except Exception:
        return False


def notificar_apps_script(action, data):
    try:
        requests.post(API_URL, json={"action": action, "data": data}, timeout=5)
    except Exception:
        pass


mostrar_encabezado_portal()

if "docente_autenticado" not in st.session_state:
    st.session_state["docente_autenticado"] = False
if "modo_preinscripcion" not in st.session_state:
    st.session_state["modo_preinscripcion"] = False

if "limpiar_formulario" in st.session_state and st.session_state["limpiar_formulario"]:
    st.session_state["limpiar_formulario"] = False
    st.rerun()

if st.session_state["modo_preinscripcion"]:
    st.subheader("📝 Formulario de Preinscripción Escolar")
    
    with st.expander("ℹ️ Instrucciones para la Preinscripción (Hacer clic para abrir)", expanded=True):
        st.markdown("""
        Bienvenido al proceso de preinscripción institucional. Por favor, siga las siguientes indicaciones:
        1. **Seleccione el Modelo ONU** correspondiente en el menú desplegable.
        2. **Complete los datos de la institución** (Nombre, dirección, correo y teléfono institucional).
        3. **Complete los datos del docente responsable** (Apellido y nombre, correo electrónico que usará como usuario y su **Clave de Acceso** personal).
        4. **Seleccione la cantidad de delegaciones** requeridas por sección o comisión teniendo en cuenta los cupos máximos permitidos.
        5. Presione el botón **'Enviar Preinscripción'**. Una vez registrado, podrá iniciar sesión con su correo y contraseña.
        """)

    if st.button("⬅️ Volver al Inicio de Sesión"):
        st.session_state["modo_preinscripcion"] = False
        st.rerun()

    modelos = obtener_modelos_activos()
    if not modelos:
        st.warning("⚠️ No hay modelos activos en la base de datos.")
        st.stop()

    dict_mods_full = {m.get("nombre_visible", m.get("id_modelo")): m for m in modelos}
    mod_sel = st.selectbox("Seleccionar Modelo ONU:", list(dict_mods_full.keys()), key="pre_mod_sel")

    modelo_objeto = dict_mods_full[mod_sel]
    id_modelo_elegido = modelo_objeto.get("id_modelo")
    comites = obtener_parametros_comites(id_modelo_elegido)

    with st.form("form_preinscripcion"):
        st.markdown("### 🏛️ Datos de la Institución")
        col1, col2 = st.columns(2)
        with col1:
            nombre_colegio = st.text_input("Nombre de la Institución Educativa *:", key="pre_nombre")
            direccion_escuela = st.text_input("Dirección *:", key="pre_dir")
            email_institucional = st.text_input("Correo Institucional *:", key="pre_email_inst")
            telefono_institucional = st.text_input("Teléfono *:", key="pre_tel_inst")
        with col2:
            st.markdown("### 👨‍🏫 Datos del Responsable")
            docente_apellido_nombre = st.text_input("Apellido y Nombre *:", key="pre_doc_nombre")
            docente_email = st.text_input("Correo Docente (Usuario) *:", key="pre_doc_email").strip().lower()
            docente_telefono = st.text_input("Teléfono Móvil *:", key="pre_doc_tel")
            secret_hash = st.text_input("Clave de Acceso *:", type="password", key="pre_hash").strip()

        st.markdown("---")
        st.markdown("### 🇺🇳 Comisiones y Limitaciones de Preinscripción")

        desglose_seleccionado = {}
        total_cupos_calculados = 0
        exclusiones_map = {}

        if comites:
            secciones = {}
            for c in comites:
                sec = str(c.get("clave_seccion", "GENERAL")).strip()
                secciones.setdefault(sec, []).append(c)
                
                excluye_raw = str(c.get("excluye_secciones", "")).strip()
                if excluye_raw and excluye_raw.lower() != "nan":
                    exclusiones_map.setdefault(sec, set())
                    for e in excluye_raw.split(","):
                        if e.strip():
                            exclusiones_map[sec].add(e.strip())

            for sec_nombre, lista_comites in secciones.items():
                col_sec, col_cant = st.columns([3, 1])
                nombres_comites = ", ".join([str(x.get("organo_comite", "")) for x in lista_comites])
                integrantes_totales = sum([int(x.get("integrantes_por_banca", 1)) for x in lista_comites])

                max_permiso = 4
                for x in lista_comites:
                    val_max = x.get("max_delegaciones_seccion")
                    if val_max is not None and str(val_max).isdigit():
                        max_permiso = int(val_max)
                        break

                opciones_cant = list(range(0, max_permiso + 1))

                with col_sec:
                    st.write(f"**Sección {sec_nombre}:** {nombres_comites} (*{integrantes_totales} part. por delegación - Máx: {max_permiso}*)")
                with col_cant:
                    cant = st.selectbox(f"Cant ({sec_nombre}):", options=opciones_cant, key=f"sec_{sec_nombre}")
                    if cant > 0:
                        desglose_seleccionado[sec_nombre] = cant
                        total_cupos_calculados += cant * integrantes_totales
        else:
            st.warning("⚠️ No hay comisiones parametrizadas para este modelo.")

        docentes_acompanantes = st.number_input("Docentes Acompañantes:", min_value=1, value=1, step=1, key="pre_acompanantes")
        st.info(f"📊 **Total de participantes acumulados:** {total_cupos_calculados} estudiantes.")

        if not comites:
            st.error("❌ Botón bloqueado: Faltan comisiones parametrizadas para este modelo.")
            submitted = st.form_submit_button("Enviar Preinscripción", disabled=True)
        else:
            submitted = st.form_submit_button("Enviar Preinscripción")

        if submitted:
            if not comites:
                st.error("❌ No se puede enviar la preinscripción: faltan parametrizar las comisiones.")
            elif not all([nombre_colegio.strip(), direccion_escuela.strip(), email_institucional.strip(), telefono_institucional.strip(), docente_apellido_nombre.strip(), docente_email.strip(), docente_telefono.strip(), secret_hash.strip()]):
                st.error("❌ Todos los campos son obligatorios.")
            else:
                error_exclusion = False
                secciones_elegidas = list(desglose_seleccionado.keys())
                
                for sec in secciones_elegidas:
                    if sec in exclusiones_map:
                        for prohibida in exclusiones_map[sec]:
                            if prohibida in secciones_elegidas:
                                st.error(f"❌ **Incompatibilidad detectada:** No puede seleccionar simultáneamente las secciones **'{sec}'** y **'{prohibida}'** ya que se excluyen mutuamente.")
                                error_exclusion = True
                                break
                    if error_exclusion:
                        break

                if not error_exclusion:
                    if total_cupos_calculados == 0:
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
                            st.success(f"¡Preinscripción exitosa! Usuario: **{docente_email}**")
                            notificar_apps_script("NUEVA_PREINSCRIPCION", {"id_delegacion": msg, "docente_email": docente_email})
                            st.session_state["limpiar_formulario"] = True
                            st.rerun()
                        else:
                            st.error(msg)

elif not st.session_state["docente_autenticado"]:
    st.subheader("🔑 Inicio de Sesión - Portal de Instituciones")
    
    with st.expander("ℹ️ Instrucciones para el Acceso", expanded=False):
        st.markdown("""
        - Seleccione el **Modelo ONU** en el que se preinscribió.
        - Ingrese el **Correo Electrónico** del docente responsable registrado.
        - Ingrese la **Clave de Acceso** que configuró al momento de enviar su formulario de preinscripción.
        - Si aún no se ha preinscripto, utilice el botón inferior para registrar a su institución.
        """)
    
    modelos = obtener_modelos_activos()
    id_modelo_ingreso = ""
    if modelos:
        dict_mods_login = {m.get("nombre_visible", m.get("id_modelo")): m.get("id_modelo") for m in modelos}
        mod_sel_login = st.selectbox("Seleccionar Modelo ONU:", list(dict_mods_login.keys()), key="login_mod_sel")
        id_modelo_ingreso = dict_mods_login[mod_sel_login]

    with st.form("form_login_escuela"):
        email_doc = st.text_input("Email del Docente Responsable:", key="login_email").strip().lower()
        hash_ingresado = st.text_input("Clave de Acceso:", type="password", key="login_hash").strip()

        if st.form_submit_button("Iniciar Sesión"):
            ok, escuela = validar_acceso_docente(email_doc, hash_ingresado, id_modelo_ingreso)
            if ok:
                st.session_state["docente_autenticado"] = True
                st.session_state["id_delegacion_activa"] = escuela.get("id")
                st.session_state["escuela_info"] = escuela
                st.session_state["id_modelo_activo"] = id_modelo_ingreso
                st.rerun()
            else:
                st.error(escuela)

    st.markdown("---")
    st.markdown("### ¿Desea inscribirse a un Modelo nuevo?")
    if st.button("📝 Inscribirme a un Modelo Nuevo"):
        st.session_state["modo_preinscripcion"] = True
        st.rerun()

else:
    escuela_actual = st.session_state["escuela_info"]
    id_del_activo = st.session_state["id_delegacion_activa"]
    id_modelo_activo = st.session_state.get("id_modelo_activo", "")

    st.sidebar.markdown(f"**🏛️ Institución:** {escuela_actual.get('nombre_colegio')}")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧭 Menú")

    if st.sidebar.button("📊 Estado de mi Institución", use_container_width=True):
        st.session_state["sub_menu"] = "Estado"
        st.rerun()
    if st.sidebar.button("💳 Pagos y Facturación", use_container_width=True):
        st.session_state["sub_menu"] = "Pago"
        st.rerun()
    if st.sidebar.button("🛡️ Póliza de Seguro", use_container_width=True):
        st.session_state["sub_menu"] = "Seguro"
        st.rerun()
    if st.sidebar.button("📋 Carga de Nómina y Documentación", use_container_width=True):
        st.session_state["sub_menu"] = "Nomina"
        st.rerun()
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state["docente_autenticado"] = False
        st.rerun()

    sub_menu = st.session_state.get("sub_menu", "Estado")

    if sub_menu == "Estado":
        st.subheader("🔑 Estado de mi Institución y Asignaciones")
        
        with st.expander("ℹ️ Instrucciones de esta sección", expanded=True):
            st.markdown("""
            - Aquí podrá visualizar el estado actual del legajo de su institución.
            - Una vez que la secretaría del modelo procese las asignaciones, verá en este apartado los países y comités otorgados a su delegación.
            """)

        st.info(f"Estado del legajo: **{escuela_actual.get('estado', 'PREINSCRIPTO')}**")
        
        bancas = obtener_bancas_asignadas(id_del_activo)
        if bancas:
            st.markdown("#### 🌍 Bancas Asignadas:")
            for b in bancas:
                st.write(f"- **{b.get('organo_comite', b.get('organo'))}** — País: **{b.get('pais')}**")
        else:
            st.info("Aún no se han publicado las bancas asignadas.")

    elif sub_menu == "Pago":
        st.subheader("💳 Subir Comprobante de Pago y Facturación")
        
        with st.expander("ℹ️ Instrucciones de Pagos y Facturación", expanded=True):
            st.markdown("""
            - Ingrese el monto exacto abonado en pesos según la transferencia o pago realizado.
            - Adjunte el archivo digital de su comprobante (formatos aceptados: **PDF, PNG, JPG, JPEG**).
            - Una vez que la secretaría apruebe su pago o registre su situación (becado/exento), podrá visualizar y descargar la **factura oficial** desde esta misma sección.
            """)

        pagos = obtener_pagos_delegacion(id_del_activo)
        if pagos:
            st.markdown("### 📑 Historial de Pagos y Facturas")
            for p in pagos:
                st.markdown(f"* **Monto:** ${float(p.get('monto', 0.0)):,.2f} | **Estado:** `{p.get('estado_pago', 'PENDIENTE')}`")
                drive_c = p.get("drive_file_url") or p.get("drive_url") or ""
                if drive_c:
                    st.markdown(f"  * 📄 [Ver Comprobante Subido]({drive_c})", unsafe_allow_html=True)
                
                factura_url = p.get("factura_url")
                if factura_url:
                    st.markdown(f"  * 🧾 **[📥 Ver / Descargar Factura Oficial]({factura_url})**", unsafe_allow_html=True)
                else:
                    st.caption("  * 🧾 Factura pendiente de emisión o exento/becado.")
                st.markdown("---")

        with st.form("form_pago_seguro"):
            monto_pago = st.number_input("Monto Abonado ($):", min_value=0.0, format="%.2f", key="pago_monto")
            archivo_comprobante = st.file_uploader("Comprobante (PDF/Imagen):", type=["pdf", "png", "jpg", "jpeg"], key="pago_archivo")

            if st.form_submit_button("Enviar Comprobante"):
                if not archivo_comprobante:
                    st.error("Adjunta el archivo del comprobante.")
                else:
                    with st.spinner("Subiendo a Google Drive..."):
                        ok_subida, res_url = subir_archivo_a_drive_via_script(
                            archivo_comprobante.read(), f"Pago_{archivo_comprobante.name}", archivo_comprobante.type, FOLDER_COMPROBANTES
                        )
                        if ok_subida:
                            ok_pago, idPago = registrar_pago_comprobante(id_del_activo, escuela_actual.get('docente_email'), id_modelo_activo, float(monto_pago), res_url)
                            if ok_pago:
                                st.success("¡Comprobante subido con éxito!")
                                st.session_state["limpiar_formulario"] = True
                                st.rerun()
                        else:
                            st.error(res_url)

    elif sub_menu == "Seguro":
        st.subheader("🛡️ Gestión de Pólizas de Seguro Institucional")
        
        with st.expander("ℹ️ Instrucciones sobre Pólizas de Seguro", expanded=True):
            st.markdown("""
            - Es obligatorio presentar la póliza de seguro de responsabilidad civil o del establecimiento que cubra a los estudiantes y docentes durante el desarrollo del Modelo ONU.
            - Adjunte el archivo digital de su póliza (formatos aceptados: **PDF, PNG, JPG, JPEG**).
            - Al presionar **'Enviar Póliza de Seguro'**, el documento quedará registrado en su legajo para validación por parte de secretaría.
            """)

        seguro_actual = escuela_actual.get("poliza_seguro_url", "")
        if seguro_actual:
            st.success("✅ Póliza de seguro cargada correctamente.")
            st.markdown(f"🛡️ **[Ver Póliza de Seguro Actual]({seguro_actual})**", unsafe_allow_html=True)
            st.markdown("---")

        with st.form("form_subir_seguro"):
            archivo_seguro = st.file_uploader("Póliza de Seguro (PDF/Imagen):", type=["pdf", "png", "jpg", "jpeg"], key="seguro_archivo")

            if st.form_submit_button("📤 Enviar Póliza de Seguro"):
                if not archivo_seguro:
                    st.error("Por favor, adjunte el archivo de la póliza de seguro.")
                else:
                    with st.spinner("Subiendo póliza a Google Drive..."):
                        ok_subida, res_url = subir_archivo_a_drive_via_script(
                            archivo_seguro.read(), f"Poliza_{archivo_seguro.name}", archivo_seguro.type, FOLDER_SEGUROS
                        )
                        if ok_subida:
                            if actualizar_poliza_seguro(id_del_activo, res_url):
                                st.success("¡Póliza de seguro subida y registrada con éxito!")
                                st.session_state["limpiar_formulario"] = True
                                st.rerun()
                            else:
                                st.error("Error al guardar la póliza en la base de datos.")
                        else:
                            st.error(res_url)

    elif sub_menu == "Nomina":
        st.subheader("📋 Registro de Participantes y Documentación")
        
        with st.expander("ℹ️ Instrucciones para la Carga de Nómina", expanded=True):
            st.markdown("""
            - Seleccione la banca o comisión asignada a su institución en el selector inferior.
            - Complete obligatoriamente el **Nombre, Apellido y DNI** de cada estudiante integrante de dicha banca según los cupos permitidos.
            - Adjunte individualmente la **Ficha Médica** y la **Autorización firmada** de cada participante en formato digital (PDF o Imagen).
            - Al finalizar, presione **'Guardar Integrantes'**.
            """)

        bancas_asignadas = obtener_bancas_asignadas(id_del_activo)
        comites_reglas = obtener_parametros_comites(id_modelo_activo)
        mapa_reglas = {str(c.get("organo_comite")).strip().upper(): c for c in comites_reglas}

        if not bancas_asignadas:
            st.warning("⚠️ Tu institución aún no tiene bancas asignadas.")
        else:
            dict_bancas = {f"{b.get('organo_comite', b.get('organo'))} — {b.get('pais')}": b for b in bancas_asignadas}
            banca_sel_nombre = st.selectbox("Seleccionar Banca:", list(dict_bancas.keys()), key="nom_banca_sel")
            banca_objeto = dict_bancas[banca_sel_nombre]

            organo_banca = str(banca_objeto.get("organo_comite", banca_objeto.get("organo"))).strip().upper()
            integrantes_permitidos = int(mapa_reglas.get(organo_banca, {}).get("integrantes_por_banca", 2))

            with st.form("form_estudiante_multiple"):
                estudiantes_datos = []
                for i in range(1, integrantes_permitidos + 1):
                    st.markdown(f"#### 👤 Integrante N° {i}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        nombre = st.text_input(f"Nombre {i}:", key=f"nombre_{i}")
                        apellido = st.text_input(f"Apellido {i}:", key=f"apellido_{i}")
                        dni = st.text_input(f"DNI {i}:", key=f"dni_{i}")
                    with col_b:
                        alergias = st.text_input(f"Alergias {i}:", value="Ninguna", key=f"alergias_{i}")
                        file_ficha = st.file_uploader(f"Ficha Médica {i}:", type=["pdf", "png", "jpg", "jpeg"], key=f"ficha_{i}")
                        file_aut = st.file_uploader(f"Autorización {i}:", type=["pdf", "png", "jpg", "jpeg"], key=f"aut_{i}")
                    comentarios = st.text_area(f"Comentarios {i}:", key=f"comentarios_{i}")
                    
                    estudiantes_datos.append({"nombre": nombre, "apellido": apellido, "dni": dni, "alergias": alergias, "ficha": file_ficha, "aut": file_aut, "comentarios": comentarios})
                    st.markdown("---")

                if st.form_submit_button("💾 Guardar Integrantes"):
                    if any(not e["nombre"] or not e["apellido"] or not e["dni"] for e in estudiantes_datos):
                        st.error("Completa Nombre, Apellido y DNI de todos los integrantes.")
                    else:
                        exito_total = True
                        for est in estudiantes_datos:
                            ficha_url, aut_url = "", ""
                            if est["ficha"]:
                                _, ficha_url = subir_archivo_a_drive_via_script(est["ficha"].read(), f"Ficha_{est['dni']}", est["ficha"].type, FOLDER_FICHAS)
                            if est["aut"]:
                                _, aut_url = subir_archivo_a_drive_via_script(est["aut"].read(), f"Aut_{est['dni']}", est["aut"].type, FOLDER_FICHAS)
                            
                            guardar_participante_nomina(id_del_activo, est["dni"], {
                                "nombre": est["nombre"], "apellido": est["apellido"], "dni": est["dni"],
                                "alergias_medicas": est["alergias"], "ficha_medica_id": ficha_url,
                                "autorizacion_id": aut_url, "comentarios": est["comentarios"],
                                "id_asignacion": banca_objeto.get("id_asignacion", organo_banca)
                            })
                        st.success("✅ Integrantes guardados con éxito.")
                        st.session_state["limpiar_formulario"] = True
                        st.rerun()
