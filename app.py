import firebase_admin
from firebase_admin import credentials, firestore
import requests
import streamlit as st

st.set_page_config(
    page_title="Panel de Secretaría - Modelos ONU",
    page_icon="⚡",
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
API_URL = st.secrets.get("API_URL", "")


# ==========================================
# FUNCIONES AUXILIARES DE SECRETARÍA
# ==========================================
def obtener_delegaciones():
    try:
        docs = db.collection("delegaciones").stream()
        return [ {**doc.to_dict(), "id": doc.id} for doc in docs ]
    except Exception as e:
        st.error(f"Error al cargar delegaciones: {e}")
        return []


def obtener_pagos():
    try:
        docs = db.collection("pagos").stream()
        return [ {**doc.to_dict(), "id": doc.id} for doc in docs ]
    except Exception as e:
        st.error(f"Error al cargar pagos: {e}")
        return []


def actualizar_estado_delegacion(email_delegacion, nuevo_estado):
    try:
        db.collection("delegaciones").document(email_delegacion).update({"estado": nuevo_estado})
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado: {e}")
        return False


def actualizar_estado_pago(pago_id, nuevo_estado):
    try:
        db.collection("pagos").document(pago_id).update({"estado_pago": nuevo_estado})
        return True
    except Exception as e:
        st.error(f"Error al actualizar pago: {e}")
        return False


def notificar_accion_script(action, data):
    if not API_URL:
        return
    try:
        requests.post(API_URL, json={"action": action, "data": data}, timeout=5)
    except Exception:
        pass


# ==========================================
# INTERFAZ PANEL DE SECRETARÍA
# ==========================================
st.title("⚡ Panel de Control — Secretaría y Administración")

tab1, tab2, tab3 = st.tabs(["🏛️ Delegaciones e Instituciones", "💳 Gestión de Pagos", "📋 Auditoría de Legajos"])

# --- TAB 1: DELEGACIONES ---
with tab1:
    st.subheader("Listado General de Instituciones Preinscriptas")
    delegaciones = obtener_delegaciones()

    if not delegaciones:
        st.info("No hay instituciones registradas todavía.")
    else:
        for d in delegaciones:
            with st.expander(f"🏫 {d.get('nombre_colegio', 'Colegio')} — Docente: {d.get('docente_apellido_nombre', 'N/A')} ({d.get('id_delegacion')})"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Email Institucional:** {d.get('email_institucional')}")
                    st.write(f"**Teléfono:** {d.get('telefono_institucional')}")
                    st.write(f"**Localidad/Dir:** {d.get('direccion_escuela')}")
                with col2:
                    st.write(f"**Docente Responsable:** {d.get('docente_apellido_nombre')}")
                    st.write(f"**Email Docente:** {d.get('docente_email')}")
                    st.write(f"**Móvil Docente:** {d.get('docente_telefono')}")
                with col3:
                    st.write(f"**Cupos Solicitados:** {d.get('cupos_solicitados')}")
                    st.write(f"**Acompañantes:** {d.get('docentes_acompanantes')}")
                    estado_actual = d.get('estado', 'PREINSCRIPTO')
                    st.markdown(f"**Estado Actual:** `{estado_actual}`")

                # Botones de gestión rápida de estado
                st.markdown("---")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"✅ Aprobar Legajo", key=f"aprobar_{d.get('id_delegacion')}"):
                        if actualizar_estado_delegacion(d.get('id_delegacion'), "APROBADO"):
                            notificar_accion_script("APROBAR_LEGAJO_ESCUELA", {"id_delegacion": d.get('id_delegacion')})
                            st.success("¡Institución aprobada con éxito!")
                            st.rerun()
                with col_btn2:
                    motivo_rechazo = st.text_input("Motivo de observación/rechazo:", key=f"mot_{d.get('id_delegacion')}")
                    if st.button(f"⚠️ Rechazar / Observar", key=f"rech_{d.get('id_delegacion')}"):
                        if actualizar_estado_delegacion(d.get('id_delegacion'), "OBSERVADO"):
                            notificar_accion_script("RECHAZAR_LEGAJO_ESCUELA", {"id_delegacion": d.get('id_delegacion'), "motivo": motivo_rechazo or "Revisar documentación faltante."})
                            st.warning("Se ha marcado como observado y notificado.")
                            st.rerun()

# --- TAB 2: PAGOS ---
with tab2:
    st.subheader("💳 Comprobantes de Pago Subidos")
    pagos = obtener_pagos()

    if not pagos:
        st.info("No hay pagos registrados en el sistema.")
    else:
        for p in pagos:
            with st.container():
                col_p1, col_p2, col_p3, col_p4 = st.columns([2, 2, 2, 2])
                with col_p1:
                    st.write(f"**Institución/Delegación:**\n{p.get('id_delegacion')}")
                with col_p2:
                    st.write(f"**Monto:**\n${p.get('monto', 0):.2f}")
                    st.write(f"**Estado:** `{p.get('estado_pago', 'PENDIENTE')}`")
                with col_p3:
                    drive_url = p.get('drive_file_url', '#')
                    # Enlace directo al comprobante real en Google Drive
                    st.markdown(f"[📄 Ver Comprobante en Drive]({drive_url})", unsafe_allow_html=True)
                with col_p4:
                    nuevo_est = st.selectbox(
                        "Cambiar Estado:",
                        ["PENDIENTE", "APROBADO", "RECHAZADO"],
                        key=f"sel_pago_{p.get('id')}",
                        index=["PENDIENTE", "APROBADO", "RECHAZADO"].index(p.get('estado_pago', 'PENDIENTE'))
                    )
                    if st.button("💾 Actualizar Pago", key=f"btn_pago_{p.get('id')}"):
                        if actualizar_estado_pago(p.get('id'), nuevo_est):
                            st.success("Estado de pago actualizado.")
                            st.rerun()
                st.markdown("---")

# --- TAB 3: AUDITORÍA DE LEGAJOS ---
with tab3:
    st.subheader("📋 Auditoría de Nómina y Estudiantes por Delegación")
    delegaciones = obtener_delegaciones()
    
    if not delegaciones:
        st.info("No hay delegaciones para auditar.")
    else:
        emails_del = [d.get('id_delegacion') for d in delegaciones]
        delegacion_sel = st.selectbox("Seleccionar Institución para ver Estudiantes:", emails_del)
        
        if delegacion_sel:
            st.markdown(f"### Estudiantes de: `{delegacion_sel}`")
            try:
                integrantes_docs = db.collection("delegaciones").document(delegacion_sel).collection("integrantes").stream()
                integrantes = [doc.to_dict() for doc in integrantes_docs]

                if not integrantes:
                    st.info("Esta institución aún no ha cargado estudiantes en su nómina.")
                else:
                    for est in integrantes:
                        with st.expander(f"👤 {est.get('nombre')} {est.get('apellido')} (DNI: {est.get('dni')})"):
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                st.write(f"**Alergias / Condiciones:** {est.get('alergias_medicas', 'Ninguna')}")
                                st.write(f"**Asignación:** {est.get('id_asignacion', 'Sin asignar')}")
                                st.write(f"**Observaciones:** {est.get('comentarios', 'Ninguna')}")
                            with col_e2:
                                ficha_url = est.get('ficha_medica_id', '')
                                aut_url = est.get('autorizacion_id', '')
                                
                                if ficha_url:
                                    st.markdown(f"[📄 Ver Ficha Médica]({ficha_url})", unsafe_allow_html=True)
                                else:
                                    st.write("⚠️ Sin Ficha Médica cargada.")
                                    
                                if aut_url:
                                    st.markdown(f"[✍️ Ver Autorización Firmada]({aut_url})", unsafe_allow_html=True)
                                else:
                                    st.write("⚠️ Sin Autorización cargada.")
            except Exception as ex:
                st.error(f"Error al cargar la nómina de integrantes: {ex}")
