import random
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import requests
import streamlit as st

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

if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()
API_URL = st.secrets["API_URL"]


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


def guardar_catalogo_paises(id_modelo, lista_paises_estructurada):
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"catalogo_paises": lista_paises_estructurada}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar catálogo de países: {e}")
        return False


def obtener_paises_obligatorios(id_modelo):
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("paises_obligatorios", [])
        return []
    except Exception as e:
        return []


def guardar_paises_obligatorios(id_modelo, lista_paises):
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"paises_obligatorios": lista_paises}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar países obligatorios: {e}")
        return False


def obtener_config_condicion_sorteo(id_modelo):
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("condicion_seccion_prioritaria", "")
        return ""
    except Exception as e:
        return ""


def guardar_config_condicion_sorteo(id_modelo, clave_seccion):
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"condicion_seccion_prioritaria": clave_seccion}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar condición de sección: {e}")
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


def obtener_asignaciones_por_modelo(id_modelo):
    try:
        asignaciones = []
        delegaciones = obtener_delegaciones_por_modelo(id_modelo)
        mapa_colegios = {d.get("id"): d.get("nombre_colegio", "Colegio Desconocido") for d in delegaciones}
        
        for d in delegaciones:
            id_del = d.get("id")
            nombre_institucion = mapa_colegios.get(id_del, "Colegio Desconocido")
            docs = db.collection("delegaciones").document(str(id_del)).collection("asignaciones").stream()
            for doc in docs:
                a = doc.to_dict()
                a["id_asignacion"] = doc.id
                a["id_delegacion"] = id_del
                a["nombre_colegio"] = nombre_institucion
                asignaciones.append(a)
        return asignaciones
    except Exception as e:
        return []


def obtener_asignaciones_por_delegacion(id_delegacion):
    try:
        docs = db.collection("delegaciones").document(str(id_delegacion)).collection("asignaciones").stream()
        asignaciones = []
        for doc in docs:
            a = doc.to_dict()
            a["id_asignacion"] = doc.id
            asignaciones.append(a)
        return asignaciones
    except Exception as e:
        return []


def ejecutar_sorteo_automatico(id_modelo):
    try:
        catalogo_paises = obtener_catalogo_paises(id_modelo)
        if not catalogo_paises:
            return False, "No hay un catálogo de países cargado para este modelo."

        comites_reglas = obtener_parametros_comites(id_modelo)
        if not comites_reglas:
            return False, "No se han parametrizado los comités para este modelo."

        delegaciones = obtener_delegaciones_por_modelo(id_modelo)
        if not delegaciones:
            return False, "No hay instituciones registradas para sortear."

        paises_obligatorios = obtener_paises_obligatorios(id_modelo)
        seccion_prioritaria = obtener_config_condicion_sorteo(id_modelo)

        secciones_map = {}
        for c in comites_reglas:
            sec = str(c.get("clave_seccion", "GENERAL")).strip()
            if sec not in secciones_map:
                secciones_map[sec] = []
            secciones_map[sec].append(str(c.get("organo_comite")).strip())

        paises_disponibles = []
        for p in catalogo_paises:
            if isinstance(p, dict):
                paises_disponibles.append(p)
            elif isinstance(p, str):
                paises_disponibles.append({
                    "pais": p,
                    "organos_permitidos": [str(c.get("organo_comite")).strip() for c in comites_reglas],
                })

        paises_obl_objs = [p for p in paises_disponibles if p.get("pais") in paises_obligatorios]
        paises_resto_objs = [p for p in paises_disponibles if p.get("pais") not in paises_obligatorios]
        
        random.shuffle(paises_resto_objs)
        paises_disponibles_ordenados = paises_obl_objs + paises_resto_objs

        if seccion_prioritaria:
            delegaciones_prioritarias = []
            delegaciones_otras = []
            for d in delegaciones:
                desglose_raw = d.get("desglose_modalidades", "{}")
                try:
                    import ast
                    d_dict = ast.literal_eval(desglose_raw) if isinstance(desglose_raw, str) else desglose_raw
                except Exception:
                    d_dict = {}
                
                if seccion_prioritaria in d_dict and int(d_dict.get(seccion_prioritaria, 0)) > 0:
                    delegaciones_prioritarias.append(d)
                else:
                    delegaciones_otras.append(d)
            
            delegaciones_ordenadas = delegaciones_prioritarias + delegaciones_otras
        else:
            delegaciones_ordenadas = delegaciones

        batch = db.batch()
        total_asignaciones_creadas = 0
        paises_asignados_global = set()

        for del_doc in delegaciones_ordenadas:
            email_docente = del_doc.get("id_delegacion")
            desglose_raw = del_doc.get("desglose_modalidades", "{}")
            try:
                import ast
                desglose_dict = ast.literal_eval(desglose_raw) if isinstance(desglose_raw, str) else desglose_raw
            except Exception:
                desglose_dict = {}

            if not desglose_dict:
                desglose_dict = {"GENERAL": 1}

            del_index = 0
            for sec_nombre, cantidad_del in desglose_dict.items():
                comites_de_seccion = secciones_map.get(sec_nombre, [str(c.get("organo_comite")).strip() for c in comites_reglas])

                for i in range(int(cantidad_del)):
                    del_index += 1
                    pais_elegido = None
                    for candidate in paises_disponibles_ordenados:
                        nombre_p = candidate.get("pais")
                        permitidos = candidate.get("organos_permitidos", [])

                        if nombre_p not in paises_asignados_global:
                            if all(com in permitidos for com in comites_de_seccion):
                                pais_elegido = nombre_p
                                paises_asignados_global.add(nombre_p)
                                break

                    if not pais_elegido:
                        for candidate in paises_disponibles_ordenados:
                            nombre_p = candidate.get("pais")
                            if nombre_p not in paises_asignados_global:
                                pais_elegido = nombre_p
                                paises_asignados_global.add(nombre_p)
                                break

                    if pais_elegido:
                        for organo in comites_de_seccion:
                            asig_id = f"{email_docente}_{sec_nombre}_{del_index}_{organo}".replace(" ", "_").replace("/", "_").lower()
                            doc_ref = db.collection("delegaciones").document(email_docente).collection("asignaciones").document(asig_id)

                            payload = {
                                "id_modelo": str(id_modelo),
                                "seccion": sec_nombre,
                                "delegacion_nro": del_index,
                                "organo_comite": organo,
                                "organo": organo,
                                "pais": pais_elegido,
                                "fecha_sorteo": firestore.SERVER_TIMESTAMP,
                            }
                            batch.set(doc_ref, payload, merge=True)
                            total_asignaciones_creadas += 1

        batch.commit()
        return True, f"🎉 Sorteo finalizado con éxito. Se asignaron {len(paises_asignados_global)} países ({total_asignaciones_creadas} bancas en total)."
    except Exception as e:
        return False, f"Error durante la ejecución del sorteo: {e}"


def actualizar_estado_delegacion(id_delegacion, estado, motivo=""):
    try:
        payload = {"estado": estado}
        if motivo:
            payload["motivo_rechazo"] = motivo
        else:
            payload["motivo_rechazo"] = firestore.DELETE_FIELD
        db.collection("delegaciones").document(str(id_delegacion)).set(payload, merge=True)
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado de la delegación: {e}")
        return False


def obtener_integrantes_delegacion(id_delegacion):
    try:
        docs = db.collection("delegaciones").document(str(id_delegacion)).collection("integrantes").stream()
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


def obtener_pagos_por_delegacion(id_delegacion):
    try:
        docs = db.collection("pagos").where("id_delegacion", "==", str(id_delegacion)).stream()
        pagos = []
        for doc in docs:
            p = doc.to_dict()
            p["id_pago"] = doc.id
            pagos.append(p)
        return pagos
    except Exception as e:
        return []


def actualizar_estado_pago(id_pago, nuevo_estado, motivo="", factura_url=""):
    try:
        payload = {"estado_pago": nuevo_estado}
        if motivo:
            payload["motivo_rechazo_pago"] = motivo
        if factura_url:
            payload["factura_url"] = factura_url
        db.collection("pagos").document(str(id_pago)).set(payload, merge=True)
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado del pago: {e}")
        return False


def eliminar_pago(id_pago):
    try:
        db.collection("pagos").document(str(id_pago)).delete()
        return True
    except Exception as e:
        st.error(f"Error al eliminar pago: {e}")
        return False


def procesar_acreditacion_forms(df_forms, id_modelo):
    nominas_oficiales = obtener_nominas_por_modelo(id_modelo)
    dnis_oficiales = {str(n.get("dni")).strip(): n for n in nominas_oficiales if n.get("dni")}
    dnis_acreditados_forms = set(df_forms["DNI"].astype(str).str.strip().tolist())

    total_nominados = len(dnis_oficiales)
    acreditados_correctos = 0
    no_registrados = []

    for dni in dnis_acreditados_forms:
        if dni in dnis_oficiales:
            acreditados_correctos += 1
            p = dnis_oficiales[dni]
            db.collection("delegaciones").document(p["id_delegacion"]).collection("integrantes").document(dni).set({"acreditado": True}, merge=True)
        else:
            no_registrados.append(dni)

    pct = round((acreditados_correctos / total_nominados) * 100, 2) if total_nominados > 0 else 0
    return {
        "total_nominados": total_nominados,
        "total_acreditados": acreditados_correctos,
        "porcentaje": pct,
        "no_registrados": no_registrados,
    }


def notificar_accion_script(action, data):
    if not API_URL:
        return
    try:
        requests.post(API_URL, json={"action": action, "data": data}, timeout=5)
    except Exception as e:
        st.warning(f"No se pudo notificar al servidor externo: {e}")


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


st.title("👑 Panel de Control - Secretaría / Administración")

if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False

if not st.session_state["admin_logueado"]:
    st.markdown("### 🔒 Acceso Restringido al Secretariado")
    with st.expander("ℹ️ Instrucciones de Acceso a Secretaría", expanded=True):
        st.markdown("""
        - Ingrese la contraseña de administración configurada en los secretos de la aplicación.
        - Este panel es exclusivo para los miembros del secretariado y administradores generales del Modelo ONU.
        """)
    with st.form("form_login_admin"):
        pass_ingresada = st.text_input("Contraseña de Administración:", type="password")
        if st.form_submit_button("Ingresar al Panel"):
            clave_Secreta = st.secrets.get("admin_logueado", "admin123")
            if pass_ingresada.strip() == str(clave_Secreta).strip():
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
    st.sidebar.warning("⚠️ No hay modelos creados en Firestore.")
    st.stop()

dict_modelos = {m["nombre_visible"]: m["id_modelo"] for m in modelos}
modelo_seleccionado = st.sidebar.selectbox("📌 Seleccionar Modelo a Gestionar:", list(dict_modelos.keys()))
id_modelo_actual = dict_modelos[modelo_seleccionado]

st.sidebar.markdown(f"**ID Modelo Activo:** `{id_modelo_actual}`")
st.sidebar.markdown("---")

(
    tab_dash,
    tab_auditoria,
    tab_pagos,
    tab_seguros,
    tab_medicos,
    tab_acred,
    tab_reportes,
    tab_config,
) = st.tabs([
    "📊 Dashboard y KPIs",
    "🔍 Auditoría y Ficha Nominal",
    "💰 Gestión de Pagos",
    "🛡️ Pólizas de Seguro",
    "🩺 Alertas Médicas",
    "🎫 Control de Acreditación",
    "📈 Reportes Avanzados",
    "⚙️ Configuración del Modelo",
])

with tab_dash:
    st.subheader(f"📊 Panel General y Recaudación — {modelo_seleccionado}")
    delegaciones = obtener_delegaciones_por_modelo(id_modelo_actual)
    nominas = obtener_nominas_por_modelo(id_modelo_actual)
    pagos = obtener_todos_pagos(id_modelo_actual)
    
    total_recaudacion_esperada = sum(float(d.get("costo_asignado", 0.0)) for d in delegaciones)
    pagos_aprobados_lista = [p for p in pagos if str(p.get("estado_pago", "")).upper() == "APROBADO"]
    total_recaudacion_cobrada = sum(float(p.get("monto") or p.get("monto_abonado") or 0.0) for p in pagos_aprobados_lista)
    
    pagos_pendientes = [p for p in pagos if str(p.get("estado_pago", "")).upper() == "PENDIENTE"]
    total_pendiente_verificacion = sum(float(p.get("monto") or p.get("monto_abonado") or 0.0) for p in pagos_pendientes)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Escuelas Registradas", len(delegaciones))
    with col2:
        docs_completas = sum(1 for d in delegaciones if str(d.get("estado")).upper() in ["DOCUMENTACION_COMPLETA", "APROBADO_FINAL", "APROBADO"])
        st.metric("Doc. Completa / Aprobada", docs_completas)
    with col3:
        st.metric("Participantes en Nómina", len(nominas))
    with col4:
        st.metric("Pagos Pendientes", len(pagos_pendientes))

    st.markdown("---")
    st.markdown("### 💵 Resumen Financiero de la Edición")
    col_fin1, col_fin2, col_fin3 = st.columns(3)
    with col_fin1:
        st.metric("💰 Recaudación Total Esperada", f"${total_recaudacion_esperada:,.2f}")
    with col_fin2:
        st.metric("✅ Recaudación Efectiva Cobrada", f"${total_recaudacion_cobrada:,.2f}")
    with col_fin3:
        st.metric("⏳ Monto Pendiente / En Revisión", f"${total_pendiente_verificacion:,.2f}")

    st.markdown("---")
    st.markdown("### 📋 Listado General de Instituciones")
    if delegaciones:
        df_del = pd.DataFrame(delegaciones).astype(str)
        st.dataframe(df_del, use_container_width=True)
        descargar_csv_para_excel(df_del, f"escuelas_preinscriptas_{id_modelo_actual}")
    else:
        st.info("No hay delegaciones registradas para este modelo.")


with tab_auditoria:
    st.subheader(f"🔍 Auditoría y Ficha Nominal — {modelo_seleccionado}")
    delegaciones_ficha = obtener_delegaciones_por_modelo(id_modelo_actual)

    if not delegaciones_ficha:
        st.info("No hay instituciones registradas para este modelo.")
    else:
        busqueda = st.text_input("🔍 Buscar por Nombre de Escuela o Email:", key="busq_auditoria_unificada").strip()
        escuelas_filtradas = [
            d for d in delegaciones_ficha 
            if busqueda.lower() in str(d.get("nombre_colegio", "")).lower() 
            or busqueda.lower() in str(d.get("id", "")).lower()
        ]

        if not escuelas_filtradas:
            st.warning("No se encontraron instituciones con ese criterio de búsqueda.")
        else:
            opciones_escuelas = {f"[{d.get('id')}] {d.get('nombre_colegio', 'Sin Nombre')}": d for d in escuelas_filtradas}
            escuela_label = st.selectbox("Seleccionar Institución:", list(opciones_escuelas.keys()), key="sel_esc_auditoria_unificada")
            escuela = opciones_escuelas[escuela_label]
            id_del = escuela.get("id")

            st.markdown("### 📋 Historial de Acciones y Estado del Trámite")
            costo_asignado = float(escuela.get("costo_asignado", 0.0))
            pagos_escuela = obtener_pagos_por_delegacion(id_del)
            tiene_pago_cargado = len(pagos_escuela) > 0
            pago_aprobado = any(str(p.get("estado_pago", "")).upper() == "APROBADO" for p in pagos_escuela)
            estado_legajo = str(escuela.get("estado", "PREINSCRIPTO")).upper()

            with st.container():
                st.markdown(
                    f"""
                    * **1. Registro inicial:** ✅ Completado
                    * **2. Envío del costo / presupuesto:** {'✅ Enviado ($ ' + f"{costo_asignado:,.2f}" + ')' if costo_asignado > 0 else '⏳ Pendiente de envío'}
                    * **3. Carga de comprobante de pago:** {'✅ Comprobante subido' if tiene_pago_cargado else '⏳ A la espera de comprobante'}
                    * **4. Verificación del pago:** {'✅ Pago aprobado' if pago_aprobado else '⏳ Pendiente de aprobación'}
                    """
                )
            st.markdown("---")

            col_fin1, col_fin2 = st.columns([2, 1])
            with col_fin1:
                monto_asignado = st.number_input(
                    "Monto a abonar por la institución ($):",
                    min_value=0.0,
                    value=float(escuela.get("costo_asignado", 0.0)),
                    step=100.0,
                    key=f"monto_{id_del}"
                )
            with col_fin2:
                st.write("")
                st.write("")
                if st.button("💾 Guardar y Habilitar Pagos", key=f"btn_enviar_monto_{id_del}"):
                    db.collection("delegaciones").document(id_del).set(
                        {"costo_asignado": float(monto_asignado)}, merge=True
                    )
                    notificar_accion_script("ENVIAR_COSTO_INSTITUCION", {
                        "id_delegacion": id_del,
                        "email_docente": escuela.get('docente_email', ''),
                        "costo_total": float(monto_asignado)
                    })
                    st.success("¡Monto guardado! Módulo de pagos habilitado para el docente.")
                    st.rerun()


with tab_pagos:
    st.subheader(f"💰 Gestión de Comprobantes y Facturación — {modelo_seleccionado}")
    pagos = obtener_todos_pagos(id_modelo_actual)

    if not pagos:
        st.info("No hay pagos registrados en el sistema para este modelo.")
    else:
        df_pagos_export = pd.DataFrame(pagos).astype(str)
        descargar_csv_para_excel(df_pagos_export, f"reporte_pagos_{id_modelo_actual}")
        st.markdown("---")

        delegaciones_lista = obtener_delegaciones_por_modelo(id_modelo_actual)
        mapa_colegios = {d.get("id_delegacion"): d.get("nombre_colegio", "Colegio sin nombre") for d in delegaciones_lista}
        mapa_emails = {d.get("id_delegacion"): d.get("docente_email", "") for d in delegaciones_lista}

        for p in pagos:
            with st.container():
                id_del = p.get('id_delegacion')
                nombre_escuela = mapa_colegios.get(id_del, "Institución no encontrada")
                email_doc = mapa_emails.get(id_del, "")
                id_pago = p.get('id_pago')

                col_p1, col_p2, col_p3, col_p4 = st.columns([2, 2, 2, 2])
                with col_p1:
                    st.markdown(f"**🏫 {nombre_escuela}**")
                    st.caption(f"📧 `{id_del}`")
                with col_p2:
                    monto_val = p.get('monto') or p.get('monto_abonado') or 0.0
                    st.write(f"**Monto:**\n${float(monto_val):.2f}")
                    st.write(f"**Estado:** `{p.get('estado_pago', 'PENDIENTE')}`")
                with col_p3:
                    drive_url = p.get("drive_file_url") or ""
                    if drive_url and str(drive_url).startswith("http"):
                        st.markdown(f"📄 **[Abrir Comprobante]({drive_url})**", unsafe_allow_html=True)
                    else:
                        st.error("❌ Sin enlace adjunto")
                with col_p4:
                    estado_actual = p.get("estado_pago", "PENDIENTE")
                    idx_estado = ["PENDIENTE", "APROBADO", "RECHAZADO"].index(estado_actual) if estado_actual in ["PENDIENTE", "APROBADO", "RECHAZADO"] else 0
                    
                    nuevo_est = st.selectbox("Cambiar Estado:", ["PENDIENTE", "APROBADO", "RECHAZADO"], key=f"sel_pago_{id_pago}", index=idx_estado)
                    factura_val = st.text_input("Nº / Enlace Factura (Opcional):", value=p.get("factura_url", ""), key=f"fact_pago_{id_pago}")

                    if st.button("💾 Actualizar Pago", key=f"btn_pago_{id_pago}"):
                        actualizar_estado_pago(id_pago, nuevo_est, factura_url=factura_val)
                        st.success("Actualizado con éxito.")
                        st.rerun()
                st.markdown("---")


with tab_seguros:
    st.subheader(f"🛡️ Auditoría de Pólizas de Seguro — {modelo_seleccionado}")
    delegaciones_seguros = obtener_delegaciones_por_modelo(id_modelo_actual)
    if delegaciones_seguros:
        data_seguros = []
        for d in delegaciones_seguros:
            url_seguro = d.get("poliza_seguro_url", "")
            data_seguros.append({
                "Institución / Colegio": d.get("nombre_colegio", "-"),
                "Docente Responsable": d.get("docente_apellido_nombre", "-"),
                "Estado Póliza": "Cargada ✅" if url_seguro else "Pendiente ⚠️",
                "Enlace Póliza": url_seguro if url_seguro else "Sin cargar"
            })
        df_seguros = pd.DataFrame(data_seguros)
        st.dataframe(df_seguros, use_container_width=True)
        descargar_csv_para_excel(df_seguros, f"reporte_polizas_{id_modelo_actual}")


with tab_medicos:
    st.subheader(f"🩺 Reporte de Salud — {modelo_seleccionado}")
    nominas_medicas = obtener_nominas_por_modelo(id_modelo_actual)
    if nominas_medicas:
        alerta_nominas = [n for n in nominas_medicas if n.get("alergias_medicas") and str(n.get("alergias_medicas")).strip().lower() not in ["ninguna", "-", ""]]
        if alerta_nominas:
            df_alertas = pd.DataFrame(alerta_nominas).astype(str)
            st.dataframe(df_alertas, use_container_width=True)
            descargar_csv_para_excel(df_alertas, f"alertas_medicas_{id_modelo_actual}")
        else:
            st.info("No hay alertas médicas registradas.")


with tab_acred:
    st.subheader(f"🎫 Acreditaciones Google Forms — {modelo_seleccionado}")
    file_forms = st.file_uploader("Cargar respuestas de Google Forms", type=["xlsx", "csv"])
    if file_forms:
        df_f = pd.read_csv(file_forms) if file_forms.name.endswith(".csv") else pd.read_excel(file_forms)
        if "DNI" in df_f.columns and st.button("🔍 Auditar y Procesar Acreditaciones"):
            res = procesar_acreditacion_forms(df_f, id_modelo_actual)
            st.metric("% Acreditación del Modelo", f"{res['porcentaje']}%")


with tab_reportes:
    st.subheader(f"📈 Módulo de Reportes Avanzados — {modelo_seleccionado}")
    tipo_reporte = st.selectbox("Seleccionar tipo de reporte:", ["🏫 Escuelas que NO han pagado", "📋 Escuelas con Nómina Incompleta", "🌍 Personas con País Asignado"])
    # [Bloque de reportes ya integrado en la estructura anterior]


with tab_config:
    subtab_comites, subtab_catalogo, subtab_sorteo, subtab_formulario = st.tabs([
        "🏛️ Parámetros de Comités", "🌍 Catálogo de Países", "🎲 Sorteo Automático", "📋 Campos del Formulario"
    ])

    with subtab_comites:
        comites_actuales = obtener_parametros_comites(id_modelo_actual)
        df_comites = pd.DataFrame(comites_actuales) if comites_actuales else pd.DataFrame(columns=["clave_seccion", "organo_comite", "integrantes_por_banca", "max_delegaciones_seccion", "excluye_secciones"])
        df_comites_editado = st.data_editor(df_comites, num_rows="dynamic")
        if st.button("💾 Guardar Parámetros de Comités"):
            guardar_parametros_comites(id_modelo_actual, df_comites_editado.to_dict(orient="records"))
            st.success("Guardado con éxito.")
            st.rerun()

    with subtab_catalogo:
        catalogo_existente = obtener_catalogo_paises(id_modelo_actual)
        paises_actuales_str = "\n".join([c.get("pais", "") for c in catalogo_existente if isinstance(c, dict)])
        paises_raw = st.text_area("Lista de países (un país por línea):", value=paises_actuales_str, height=120)
        if st.button("💾 Guardar Catálogo de Países"):
            lista_p = [{"pais": p.strip(), "organos_permitidos": []} for p in paises_raw.split("\n") if p.strip()]
            guardar_catalogo_paises(id_modelo_actual, lista_p)
            st.success("Catálogo guardado.")
            st.rerun()

    with subtab_sorteo:
        st.markdown("### 🎲 Generador y Sorteo de Asignaciones")
        if st.button("🚀 CONFIRMAR Y EJECUTAR SORTEO DE PAÍSES"):
            ok_sorteo, msg_sorteo = ejecutar_sorteo_automatico(id_modelo_actual)
            if ok_sorteo:
                st.balloons()
                st.success(msg_sorteo)
                st.rerun()
            else:
                st.error(msg_sorteo)

    with subtab_formulario:
        campos_actuales = obtener_esquema_formulario(id_modelo_actual)
        df_campos = pd.DataFrame(campos_actuales) if campos_actuales else pd.DataFrame(columns=["nombre_campo", "tipo_dato", "es_requerido"])
        df_fields_editado = st.data_editor(df_campos, num_rows="dynamic")
        if st.button("💾 Guardar Campos"):
            guardar_esquema_formulario(id_modelo_actual, df_fields_editado.to_dict(orient="records"))
            st.success("Actualizado.")
            st.rerun()
