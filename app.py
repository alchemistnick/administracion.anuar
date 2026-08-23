import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Panel de Secretaría - Modelos ONU",
    page_icon="👑",
    layout="wide"
)

# URL DE TU API DE APPS SCRIPT ACTUALIZADA
API_URL = "https://script.google.com/macros/s/AKfycbxMsoNWVYS9CJRHSj22s25ivYY6ITSK6vj059JmjDKb_YMr0Qy8GyLQx3fQqQWf7PwJHA/exec"

@st.cache_data(ttl=30)
def api_get(action, params=""):
    try:
        url = f"{API_URL}?action={action}{params}"
        res = requests.get(url).json()
        if res.get("status") == "SUCCESS":
            return res.get("data", [])
        return []
    except Exception:
        return []

st.title("👑 Panel de Control - Secretaría / Administración")

# Selección de Modelo
modelos = api_get("GET_MODELOS_ACTIVOS")
if not modelos:
    st.warning("⚠️ No hay modelos activos configurados.")
    st.stop()

dict_modelos = {m["nombre_visible"]: m["id_modelo"] for m in modelos}
modelo_seleccionado = st.sidebar.selectbox("Seleccionar Modelo:", list(dict_modelos.keys()))
id_modelo_actual = dict_modelos[modelo_seleccionado]

st.sidebar.markdown("---")
menu_admin = st.sidebar.radio(
    "Navegación Admin",
    [
        "📊 Dashboard y KPIs", 
        "🏫 Control de Escuelas y Documentación", 
        "💰 Gestión de Pagos", 
        "🌍 Países Sin Asignar", 
        "🩺 Alertas Médicas"
    ]
)

# Cargar datos globales filtrados por modelo
delegaciones = api_get("GET_TODAS_DELEGACIONES", f"&id_modelo={id_modelo_actual}")
pagos = api_get("GET_PAGOS_PENDIENTES") # O todos si prefieres
nominas = api_get("GET_TODAS_NOMINAS", f"&id_modelo={id_modelo_actual}")

# ---------------------------------------------------------
# 1. DASHBOARD Y KPIS
# ---------------------------------------------------------
if menu_admin == "📊 Dashboard y KPIs":
    st.subheader(f"📊 Panel General - {modelo_seleccionado}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Escuelas Registradas", len(delegaciones))
    with col2:
        docs_completas = sum(1 for d in delegaciones if str(d.get("estado")).upper() == "DOCUMENTACION_COMPLETA")
        st.metric("Documentación Completa", docs_completas)
    with col3:
        st.metric("Estudiantes en Nómina", len(nominas))
    with col4:
        pagos_aprobados = sum(1 for p in pagos if str(p.get("estado_pago")).upper() == "APROBADO")
        st.metric("Pagos Aprobados", pagos_aprobados)

    st.markdown("---")
    st.markdown("### 📋 Resumen Rápido de Instituciones")
    if delegaciones:
        df_del = pd.DataFrame(delegaciones)
        st.dataframe(df_del[["id_delegacion", "nombre_colegio", "docente_apellido_nombre", "cupos_solicitados", "estado"]], use_container_width=True)
    else:
        st.info("No hay delegaciones registradas todavía.")

# ---------------------------------------------------------
# 2. CONTROL DE ESCUELAS Y DOCUMENTACIÓN
# ---------------------------------------------------------
elif menu_admin == "🏫 Control de Escuelas y Documentación":
    st.subheader("🏫 Estado de Carga Documental por Escuela")
    
    if delegaciones:
        for d in delegaciones:
            estado = str(d.get("estado", "REGISTRADO")).upper()
            color_badge = "🟢" if estado == "DOCUMENTACION_COMPLETA" else "🟡"
            
            with st.expander(f"{color_badge} [{d.get('id_delegacion')}] {d.get('nombre_colegio')} — Estado: *{estado}*"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Responsable:** {d.get('docente_apellido_nombre')}")
                    st.write(f"**Correo:** {d.get('docente_email')}")
                    st.write(f"**Teléfono:** {d.get('docente_telefono')}")
                with col_b:
                    st.write(f"**Cupos Solicitados:** {d.get('cupos_solicitados')}")
                    st.write(f"**Desglose:** {d.get('desglose_modalidades')}")
                
                # Filtrar alumnos de esta delegación
                alumnos_escuela = [n for n in nominas if str(n.get("id_delegacion")).strip().upper() == str(d.get("id_delegacion")).strip().upper()]
                st.markdown(f"**Estudiantes cargados en nómina:** {len(alumnos_escuela)}")
                if alumnos_escuela:
                    df_alumnos = pd.DataFrame(alumnos_escuela)
                    st.dataframe(df_alumnos[["id_asignacion", "rol_mnu", "nombre", "apellido", "dni"]], use_container_width=True)
    else:
        st.info("No hay escuelas cargadas.")

# ---------------------------------------------------------
# 3. GESTIÓN DE PAGOS
# ---------------------------------------------------------
elif menu_admin == "💰 Gestión de Pagos":
    st.subheader("💰 Comprobantes de Pago Pendientes")
    
    # Usamos la acción para traer pagos pendientes
    pagos_pendientes = api_get("GET_PAGOS_PENDIENTES")
    
    if not pagos_pendientes:
        st.success("🎉 ¡No hay pagos pendientes de revisión!")
    else:
        for p in pagos_pendientes:
            with st.container():
                col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                with col_p1:
                    st.write(f"**ID Pago:** {p.get('id_pago')}")
                    st.write(f"**Delegación:** {p.get('id_delegacion')}")
                    st.write(f"**Monto:** ${p.get('monto')}")
                with col_p2:
                    url_comprobante = p.get('drive_file_url')
                    if url_comprobante:
                        st.markdown(f"🔗 [Ver Comprobante en Drive]({url_comprobante})", unsafe_allow_html=True)
                    st.write(f"**Estado actual:** {p.get('estado_pago')}")
                with col_p3:
                    if st.button("Aprobar", key=f"ap_{p.get('id_pago')}"):
                        payload = {"action": "CAMBIAR_ESTADO_PAGO", "data": {"id_pago": p.get('id_pago'), "nuevo_estado": "APROBADO"}}
                        requests.post(API_URL, json=payload)
                        st.success("¡Pago aprobado!")
                        st.rerun()
                    if st.button("Rechazar", key=f"rec_{p.get('id_pago')}"):
                        payload = {"action": "CAMBIAR_ESTADO_PAGO", "data": {"id_pago": p.get('id_pago'), "nuevo_estado": "RECHAZADO"}}
                        requests.post(API_URL, json=payload)
                        st.warning("Pago rechazado.")
                        st.rerun()
                st.markdown("---")

# ---------------------------------------------------------
# 4. PAÍSES SIN ASIGNAR
# ---------------------------------------------------------
elif menu_admin == "🌍 Países Sin Asignar":
    st.subheader("🌍 Control de Países y Bancas Disponibles")
    st.markdown("Este reporte compara la matriz maestra de órganos contra las asignaciones actuales para mostrarte qué lugares siguen libres.")

    # Obtenemos los órganos y las asignaciones actuales de la API de Apps Script
    # (Asegurate de que tu backend tenga o devuelva los datos de ambas solapas)
    try:
        res_org = requests.get(f"{API_URL}?action=GET_TODAS_ASIGNACIONES_O_ORGANOS").json() # O lectura directa
    except Exception:
        pass

    st.info("💡 **Tip:** Para verificar rápidamente los países sin asignar, revisa la solapa **`Organos`** de tu Google Sheet: los que tengan un guion `"-"` en la **Columna E (`id_asignacion`)** son los países o bancas que todavía no fueron sorteados ni asignados a ninguna escuela.")

# ---------------------------------------------------------
# 5. ALERTAS MÉDICAS
# ---------------------------------------------------------
elif menu_admin == "🩺 Alertas Médicas y Alergias":
    st.subheader("🩺 Reporte de Salud y Alergias Declaradas")
    
    if nominas:
        # Filtramos aquellos que cargaron alguna alergia distinta a "Ninguna"
        alerta_nominas = [n for n in nominas if n.get("alergias_medicas") and str(n.get("alergias_medicas")).strip().lower() not in ["ninguna", "-", ""]]
        
        if not alerta_nominas:
            st.success("✅ No hay alertas médicas registradas en las nóminas actuales.")
        else:
            st.warning(f"⚠️ Se encontraron {len(alerta_nominas)} participantes con observaciones médicas:")
            df_alertas = pd.DataFrame(alerta_nominas)
            st.dataframe(df_alertas[["id_delegacion", "nombre", "apellido", "dni", "rol_mnu", "alergias_medicas"]], use_container_width=True)
    else:
        st.info("No hay participantes cargados en las nóminas todavía.")
