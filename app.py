import random
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import requests
import streamlit as st

# Configuración de página
st.set_page_config(
    page_title="Panel de Secretaría - Modelos ONU", page_icon="👑", layout="wide"
)

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Inicialización Singleton de Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()
API_URL = st.secrets["API_URL"]


# ==========================================
# FUNCIONES DE BASE DE DATOS (db.py)
# ==========================================
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
        st.error(f"Error al cargar modelos desde Firestore: {e}")
        return []


def obtener_parametros_comites(id_modelo):
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("parametros_comites", [])
        return []
    except Exception as e:
        st.error(f"Error al leer parámetros de comités: {e}")
        return []


def guardar_parametros_comites(id_modelo, lista_comites):
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"parametros_comites": lista_comites}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar parámetros de comités: {e}")
        return False


def obtener_esquema_formulario(id_modelo):
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("campos_personalizados", [])
        return []
    except Exception as e:
        st.error(f"Error al obtener esquema del formulario: {e}")
        return []


def guardar_esquema_formulario(id_modelo, lista_campos):
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"campos_personalizados": lista_campos}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar esquema del formulario: {e}")
        return False


def obtener_catalogo_paises(id_modelo):
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("catalogo_paises", [])
        return []
    except Exception as e:
        st.error(f"Error al leer catálogo de países: {e}")
        return []


def guardar_catalogo_paises(id_modelo, lista_paises):
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"catalogo_paises": lista_paises}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar catálogo de países: {e}")
        return False


def obtener_delegaciones_por_modelo(id_modelo=None):
    try:
        ref = db.collection("delegaciones")
        if id_modelo:
            docs = ref.where("id_modelo", "==", str(id_modelo)).stream()
        else:
            docs = ref.stream()

        delegaciones = []
        for doc in docs:
            datos = doc.to_dict()
            datos["id"] = doc.id
            datos["id_delegacion"] = doc.id
            delegaciones.append(datos)
        return delegaciones
    except Exception as e:
        st.error(f"Error al consultar delegaciones: {e}")
        return []


def ejecutar_sorteo_automatico(id_modelo):
    try:
        paises_disponibles = obtener_catalogo_paises(id_modelo)
        if not paises_disponibles:
            return (
                False,
                "No hay un catálogo de países cargado para este modelo.",
            )

        comites_reglas = obtener_parametros_comites(id_modelo)
        if not comites_reglas:
            return False, "No se han parametrizado los comités para este modelo."

        delegaciones = obtener_delegaciones_por_modelo(id_modelo)
        if not delegaciones:
            return False, "No hay instituciones registradas para sortear."

        batch = db.batch()
        total_asignaciones_creadas = 0

        pozos_comites = {}
        for c in comites_reglas:
            organo = str(c.get("organo_comite")).strip()
            lista_mezclada = paises_disponibles.copy()
            random.shuffle(lista_mezclada)
            pozos_comites[organo] = lista_mezclada

        for del_doc in delegaciones:
            email_docente = del_doc.get("id_delegacion")

            for c in comites_reglas:
                organo = str(c.get("organo_comite")).strip()
                pozo = pozos_comites.get(organo, [])

                if pozo:
                    pais_asignado = pozo.pop(0)
                    asig_id = (
                        f"{email_docente}_{organo}".replace(" ", "_")
                        .replace("/", "_")
                        .lower()
                    )
                    doc_ref = (
                        db.collection("delegaciones")
                        .document(email_docente)
                        .collection("asignaciones")
                        .document(asig_id)
                    )

                    payload = {
                        "id_modelo": id_modelo,
                        "organo_comite": organo,
                        "organo": organo,
                        "pais": pais_asignado,
                        "fecha_sorteo": firestore.SERVER_TIMESTAMP,
                    }

                    batch.set(doc_ref, payload, merge=True)
                    total_asignaciones_creadas += 1

        batch.commit()
        return (
            True,
            f"🎉 Sorteo finalizado con éxito. Se generaron {total_asignaciones_creadas} asignaciones de bancas/países.",
        )

    except Exception as e:
        return False, f"Error durante la ejecución del sorteo: {e}"


def actualizar_estado_delegacion(id_delegacion, estado, motivo=""):
    try:
        payload = {"estado": estado}
        if motivo:
            payload["motivo_rechazo"] = motivo
        db.collection("delegaciones").document(str(id_delegacion)).set(
            payload, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado de la delegación: {e}")
        return False


def obtener_integrantes_delegacion(id_delegacion):
    try:
        docs = (
            db.collection("delegaciones")
            .document(str(id_delegacion))
            .collection("integrantes")
            .stream()
        )
        integrantes = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            integrantes.append(d)
        return integrantes
    except Exception as e:
        st.error(f"Error al obtener integrantes: {e}")
        return []


def obtener_nominas_por_modelo(id_modelo=None):
    delegaciones = obtener_delegaciones_por_modelo(id_modelo)
    todas_nominas = []
    for d in delegaciones:
        id_del = d.get("id")
        integrantes = obtener_integrantes_delegacion(id_del)
        for i in integrantes:
            i["id_delegacion"] = id_del
            i["nombre_colegio"] = d.get("nombre_colegio", "Sin Nombre")
            todas_nominas.append(i)
    return todas_nominas


def obtener_todos_pagos(id_modelo=None):
    try:
        ref = db.collection("pagos")
        if id_modelo:
            docs = ref.where("id_modelo", "==", str(id_modelo)).stream()
        else:
            docs = ref.stream()

        pagos = []
        for doc in docs:
            p = doc.to_dict()
            p["id_pago"] = doc.id
            pagos.append(p)
        return pagos
    except Exception as e:
        st.error(f"Error al consultar pagos: {e}")
        return []


def obtener_pagos_pendientes(id_modelo=None):
    pagos = obtener_todos_pagos(id_modelo)
    return [
        p
        for p in pagos
        if str(p.get("estado_pago", "")).upper() == "PENDIENTE"
    ]


def actualizar_estado_pago(id_pago, nuevo_estado):
    try:
        db.collection("pagos").document(str(id_pago)).set(
            {"estado_pago": nuevo_estado}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado del pago: {e}")
        return False


def procesar_acreditacion_forms(df_forms, id_modelo):
    nominas_oficiales = obtener_nominas_por_modelo(id_modelo)
    dnis_oficiales = {
        str(n.get("dni")).strip(): n for n in nominas_oficiales if n.get("dni")
    }
    dnis_acreditados_forms = set(
        df_forms["DNI"].astype(str).str.strip().tolist()
    )

    total_nominados = len(dnis_oficiales)
    acreditados_correctos = 0
    no_registrados = []

    for dni in dnis_acreditados_forms:
        if dni in dnis_oficiales:
            acreditados_correctos += 1
            p = dnis_oficiales[dni]
            db.collection("delegaciones").document(
                p["id_delegacion"]
            ).collection("integrantes").document(dni).set(
                {"acreditado": True}, merge=True
            )
        else:
            no_registrados.append(dni)

    pct = (
        round((acreditados_correctos / total_nominados) * 100, 2)
        if total_nominados > 0
        else 0
    )

    return {
        "total_nominados": total_nominados,
        "total_acreditados": acreditados_correctos,
        "porcentaje": pct,
        "no_registrados": no_registrados,
    }


def notificar_apps_script(action, data):
    try:
        requests.post(API_URL, json={"action": action, "data": data}, timeout=5)
    except Exception:
        pass


def descargar_csv_para_excel(df, nombre_archivo):
    df_clean = df.astype(str)
    csv = df_clean.to_csv(index=False).encode("utf-8-sig")
    return st.download_button(
        label=f"📥 Descargar {nombre_archivo} (Compatible con Excel)",
        data=csv,
        file_name=f"{nombre_archivo}.csv",
        mime="text/csv",
        key=f"btn_{nombre_archivo}",
    )


# ==========================================
# INTERFAZ SECRETARÍA
# ==========================================
st.title("👑 Panel de Control - Secretaría / Administración")

if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False

if not st.session_state["admin_logueado"]:
    st.markdown("### 🔒 Acceso Restringido al Secretariado")
    with st.form("form_login_admin"):
        pass_ingresada = st.text_input(
            "Contraseña de Administración:", type="password"
        )
        if st.form_submit_button("Ingresar al Panel"):
            if pass_ingresada.strip() == st.secrets["admin_logueado"]:
                st.session_state["admin_logueado"] = True
                st.success("¡Acceso concedido!")
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()

if st.sidebar.button("Cerrar Sesión Admin"):
    st.session_state["admin_logueado"] = False
    st.rerun()

modelos = obtener_modelos_activos()
if not modelos:
    st.sidebar.warning(
        "⚠️ No hay modelos creados en Firestore. Cargue un modelo en la"
        " colección 'modelos'."
    )
    st.stop()

dict_modelos = {m["nombre_visible"]: m["id_modelo"] for m in modelos}
modelo_seleccionado = st.sidebar.selectbox(
    "📌 Seleccionar Modelo a Gestionar:", list(dict_modelos.keys())
)
id_modelo_actual = dict_modelos[modelo_seleccionado]

st.sidebar.markdown(f"**ID Modelo Activo:** `{id_modelo_actual}`")
st.sidebar.markdown("---")

(
    tab_dash,
    tab_ficha,
    tab_auditoria,
    tab_pagos,
    tab_medicos,
    tab_acred,
    tab_config,
) = st.tabs([
    "📊 Dashboard y KPIs",
    "🏫 Ficha Nominal por Escuela",
    "🔍 Auditoría de Legajos",
    "💰 Gestión de Pagos",
    "🩺 Alertas Médicas",
    "🎫 Control de Acreditación",
    "⚙️ Configuración del Modelo",
])

# 1. DASHBOARD
with tab_dash:
    st.subheader(f"📊 Panel General — {modelo_seleccionado}")
    delegaciones = obtener_delegaciones_por_modelo(id_modelo_actual)
    nominas = obtener_nominas_por_modelo(id_modelo_actual)
    pagos_pendientes = obtener_pagos_pendientes(id_modelo_actual)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Escuelas Registradas", len(delegaciones))
    with col2:
        docs_completas = sum(
            1
            for d in delegaciones
            if str(d.get("estado")).upper()
            in ["DOCUMENTACION_COMPLETA", "APROBADO_FINAL"]
        )
        st.metric("Doc. Completa / Aprobada", docs_completas)
    with col3:
        st.metric("Participantes en Nómina", len(nominas))
    with col4:
        st.metric("Pagos Pendientes", len(pagos_pendientes))

    st.markdown("---")
    if delegaciones:
        df_del = pd.DataFrame(delegaciones).astype(str)
        st.dataframe(df_del, use_container_width=True)
        descargar_csv_para_excel(
            df_del, f"escuelas_preinscriptas_{id_modelo_actual}"
        )
    else:
        st.info("No hay delegaciones registradas para este modelo.")

# 2. FICHA NOMINAL
with tab_ficha:
    st.subheader(f"🏫 Ficha Integral por Institución — {modelo_seleccionado}")
    delegaciones_ficha = obtener_delegaciones_por_modelo(id_modelo_actual)

    if delegaciones_ficha:
        busqueda = st.text_input("🔍 Buscar por Nombre de Escuela o Email:").strip()
        escuelas_filtradas = [
            d
            for d in delegaciones_ficha
            if busqueda.lower() in str(d.get("nombre_colegio", "")).lower()
            or busqueda.lower() in str(d.get("id", "")).lower()
        ]

        if escuelas_filtradas:
            opciones_escuelas = {
                f"[{d.get('id')}] {d.get('nombre_colegio', 'Sin Nombre')}": d
                for d in escuelas_filtradas
            }
            escuela_label = st.selectbox(
                "Seleccionar Institución:", list(opciones_escuelas.keys())
            )
            escuela = opciones_escuelas[escuela_label]
            id_del = escuela.get("id")

            cols_info = st.columns(3)
            with cols_info[0]:
                st.markdown(
                    f"**🏛️ Institución:** {escuela.get('nombre_colegio', '-')}"
                )
                st.markdown(
                    f"**📍 Dirección:** {escuela.get('direccion_escuela', '-')}"
                )
                st.markdown(f"**📧 Email / ID:** `{id_del}`")
            with cols_info[1]:
                st.markdown(
                    "**👤 Responsable:**"
                    f" {escuela.get('docente_apellido_nombre', '-')}"
                )
                st.markdown(
                    f"**📱 Teléfono:** {escuela.get('docente_telefono', '-')}"
                )
            with cols_info[2]:
                st.markdown(
                    "**📊 Cupos Solicitados:**"
                    f" {escuela.get('cupos_solicitados', '-')}"
                )
                st.markdown(
                    f"**🔑 Clave Hash:** `{escuela.get('secret_hash', '-')}`"
                )

            st.markdown("---")
            registros_escuela = obtener_integrantes_delegacion(id_del)
            if registros_escuela:
                df_alumnos = pd.DataFrame(registros_escuela).astype(str)
                st.dataframe(df_alumnos, use_container_width=True)
                descargar_csv_para_excel(df_alumnos, f"nomina_{id_del}")

# 3. AUDITORÍA
with tab_auditoria:
    st.subheader(f"🔍 Auditoría y Aprobaciones — {modelo_seleccionado}")
    delegaciones_aud = obtener_delegaciones_por_modelo(id_modelo_actual)
    if delegaciones_aud:
        opc_aud = {
            f"[{d.get('id')}] {d.get('nombre_colegio')} (Estado: {d.get('estado')})": d
            for d in delegaciones_aud
        }
        sel_aud_label = st.selectbox(
            "Seleccionar Institución a Auditar:", list(opc_aud.keys())
        )
        escuela_aud = opc_aud[sel_aud_label]
        id_del_aud = escuela_aud.get("id")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(
                "✅ Aprobar Legajo Completo", key=f"btn_aprobar_{id_del_aud}"
            ):
                actualizar_estado_delegacion(
                    id_del_aud, "DOCUMENTACION_COMPLETA"
                )
                notificar_apps_script(
                    "APROBAR_LEGAJO_ESCUELA", {"id_delegacion": id_del_aud}
                )
                st.success("Legajo aprobado.")
                st.rerun()

        with col_btn2:
            with st.expander("❌ Rechazar Legajo"):
                with st.form(key=f"form_rechazo_{id_del_aud}"):
                    motivo = st.text_area("Motivo del rechazo:")
                    if st.form_submit_button("Confirmar Rechazo"):
                        actualizar_estado_delegacion(
                            id_del_aud, "RECHAZADO", motivo
                        )
                        notificar_apps_script(
                            "RECHAZAR_LEGAJO_ESCUELA",
                            {"id_delegacion": id_del_aud, "motivo": motivo},
                        )
                        st.warning("Legajo rechazado.")
                        st.rerun()

# 4. PAGOS
with tab_pagos:
    st.subheader(f"💰 Gestión de Comprobantes — {modelo_seleccionado}")
    pagos_pendientes = obtener_pagos_pendientes(id_modelo_actual)
    if pagos_pendientes:
        for p in pagos_pendientes:
            id_pago = p.get("id_pago")
            col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
            with col_p1:
                st.write(
                    f"**Delegación:** `{p.get('id_delegacion')}` | **Monto:**"
                    f" ${p.get('monto')}"
                )
            with col_p2:
                if p.get("drive_file_url"):
                    st.markdown(f"🔗 [Ver Comprobante]({p.get('drive_file_url')})")
            with col_p3:
                if st.button("Aprobar", key=f"ap_{id_pago}"):
                    actualizar_estado_pago(id_pago, "APROBADO")
                    st.rerun()
                if st.button("Rechazar", key=f"rec_{id_pago}"):
                    actualizar_estado_pago(id_pago, "RECHAZADO")
                    st.rerun()

# 5. ALERTAS MÉDICAS
with tab_medicos:
    st.subheader(f"🩺 Reporte de Salud — {modelo_seleccionado}")
    nominas_medicas = obtener_nominas_por_modelo(id_modelo_actual)
    if nominas_medicas:
        alerta_nominas = [
            n
            for n in nominas_medicas
            if n.get("alergias_medicas")
            and str(n.get("alergias_medicas")).strip().lower()
            not in ["ninguna", "-", ""]
        ]
        if alerta_nominas:
            df_alertas = pd.DataFrame(alerta_nominas).astype(str)
            st.dataframe(df_alertas, use_container_width=True)

# 6. ACREDITACIÓN GOOGLE FORMS
with tab_acred:
    st.subheader(f"🎫 Acreditaciones Google Forms — {modelo_seleccionado}")
    file_forms = st.file_uploader(
        "Cargar respuestas de Google Forms", type=["xlsx", "csv"]
    )
    if file_forms:
        df_f = (
            pd.read_csv(file_forms)
            if file_forms.name.endswith(".csv")
            else pd.read_excel(file_forms)
        )
        if "DNI" in df_f.columns and st.button(
            "🔍 Auditar y Procesar Acreditaciones"
        ):
            res = procesar_acreditacion_forms(df_f, id_modelo_actual)
            st.metric("% Acreditación del Modelo", f"{res['porcentaje']}%")

# 7. CONFIGURACIÓN COMPLETA
with tab_config:
    st.subheader(f"⚙️ Configuración del Modelo — {modelo_seleccionado}")

    subtab_comites, subtab_catalogo, subtab_sorteo, subtab_formulario = st.tabs([
        "🏛️ Parámetros de Comités",
        "🌍 Catálogo de Países",
        "🎲 Sorteo Automático",
        "📋 Campos del Formulario",
    ])

    with subtab_comites:
        st.markdown("### 🏛️ Estructura de Órganos y Comités")
        comites_actuales = obtener_parametros_comites(id_modelo_actual)
        df_comites = (
            pd.DataFrame(comites_actuales)
            if comites_actuales
            else pd.DataFrame(
                columns=[
                    "clave_seccion",
                    "organo_comite",
                    "integrantes_por_banca",
                    "requiere_marca",
                    "max_delegaciones_seccion",
                ]
            )
        )

        df_comites_editado = st.data_editor(
            df_comites, num_rows="dynamic", key="editor_parametros_comites"
        )
        if st.button("💾 Guardar Parámetros de Comités"):
            guardar_parametros_comites(
                id_modelo_actual, df_comites_editado.to_dict(orient="records")
            )
            st.success("Parámetros actualizados.")
            st.rerun()

    with subtab_catalogo:
        st.markdown("### 🌍 Catálogo Maestro de Países Disponibles")
        catalogo_actual = obtener_catalogo_paises(id_modelo_actual)
        paises_input = st.text_area(
            "Lista de Países (Un país por línea):",
            value="\n".join(catalogo_actual) if catalogo_actual else "",
            height=250,
        )
        if st.button("💾 Guardar Catálogo de Países"):
            lista_paises = [
                p.strip() for p in paises_input.split("\n") if p.strip()
            ]
            guardar_catalogo_paises(id_modelo_actual, lista_paises)
            st.success("Catálogo guardado.")
            st.rerun()

    with subtab_sorteo:
        st.markdown("### 🎲 Generador y Sorteo de Asignaciones")
        if st.button("🚀 CONFIRMAR Y EJECUTAR SORTEO DE PAÍSES"):
            ok_sorteo, msg_sorteo = ejecutar_sorteo_automatico(id_modelo_actual)
            if ok_sorteo:
                st.balloons()
                st.success(msg_sorteo)
            else:
                st.error(msg_sorteo)

    with subtab_formulario:
        st.markdown("### 📋 Diseñador de Campos Adicionales")
        campos_actuales = obtener_esquema_formulario(id_modelo_actual)
        df_campos = (
            pd.DataFrame(campos_actuales)
            if campos_actuales
            else pd.DataFrame(
                columns=[
                    "nombre_campo",
                    "tipo_dato",
                    "opciones_separadas_por_coma",
                    "es_requerido",
                ]
            )
        )

        df_fields_editado = st.data_editor(
            df_campos, num_rows="dynamic", key="editor_esquema_formulario"
        )
        if st.button("💾 Guardar Campos del Formulario"):
            guardar_esquema_formulario(
                id_modelo_actual, df_fields_editado.to_dict(orient="records")
            )
            st.success("Formulario actualizado.")
            st.rerun()
