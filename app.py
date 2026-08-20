import streamlit as st
import requests

st.set_page_config(
    page_title="Secretariado - Control Interno MNU",
    page_icon="🛡️",
    layout="wide"
)

API_URL = "https://script.google.com/macros/s/AKfycby8moCFp2NDWnSapd9TaA0OJPERRZf249QwFF9SJuw3QnKmAlc8RCHJdze-o3QTmCXwCA/exec"

st.title("🛡️ Panel Interno del Secretariado - Control y Auditoría")

CONFIG_MODELOS = {
    f"MUNEJEMPLO{i}": f"MUNEJEMPLO_{i}" for i in range(1, 11)
}

st.sidebar.markdown("### 🌐 Selección de Evento")
modelo_seleccionado = st.sidebar.selectbox("Elegí el Modelo a Auditar:", list(CONFIG_MODELOS.keys()))
id_modelo_actual = CONFIG_MODELOS[modelo_seleccionado]

st.sidebar.markdown("---")

# Control de Acceso Global para el Panel de Administración
admin_pass = st.sidebar.text_input("🔐 Contraseña Secretariado", type="password")

if admin_pass == "Secretaria2026":
    st.sidebar.success("Acceso Autorizado")
    
    menu = st.sidebar.radio(
        "Módulos de Gestión",
        [
            "Revisión de Pagos", 
            "Auditoría de Nóminas y Fichas",
            "Métricas del Evento"
        ]
    )

    # ---------------------------------------------------------
    # MÓDULO 1: REVISIÓN DE PAGOS
    # ---------------------------------------------------------
    if menu == "Revisión de Pagos":
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
    # MÓDULO 2: AUDITORÍA DE NÓMINAS Y FICHAS
    # ---------------------------------------------------------
    elif menu == "Auditoría de Nóminas y Fichas":
        st.subheader(f"Control de Documentación y Fichas Médicas - {modelo_seleccionado}")
        st.info("Próximamente: Vista consolidada de descargas de fichas por delegación y acreditaciones.")

    # ---------------------------------------------------------
    # MÓDULO 3: MÉTRICAS DEL EVENTO
    # ---------------------------------------------------------
    elif menu == "Métricas del Evento":
        st.subheader(f"Tablero de Control - {modelo_seleccionado}")
        st.info("Próximamente: Estadísticas de recaudación, total de delegados cargados y estado de la matriz.")

elif admin_pass:
    st.error("🔒 Contraseña incorrecta. Acceso denegado al Panel del Secretariado.")
else:
    st.warning("👈 Por favor ingresá la contraseña del Secretariado en el menú lateral para acceder.")
