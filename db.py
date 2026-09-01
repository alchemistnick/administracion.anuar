import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st

# Inicialización Singleton de Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ==========================================
# 1. GESTIÓN DE MODELOS
# ==========================================


def obtener_modelos_activos():
    """Recupera la lista de modelos desde Firestore."""
    try:
        docs = db.collection("modelos").stream()
        modelos = []
        for doc in docs:
            m = doc.to_dict()
            m["id_modelo"] = doc.id
            modelos.append(m)

        if not modelos:
            # Lista base de respaldo en caso de que la colección 'modelos' esté vacía inicialmente
            return [
                {
                    "id_modelo": "MONUCBA_2026",
                    "nombre_visible": "MONUCBA 2026",
                },
                {"id_modelo": "CATE_2026", "nombre_visible": "Modelo CATE 2026"},
            ]
        return modelos
    except Exception as e:
        st.error(f"Error al cargar modelos desde Firestore: {e}")
        return [
            {"id_modelo": "MONUCBA_2026", "nombre_visible": "MONUCBA 2026"}
        ]


# ==========================================
# 2. DELEGACIONES / ESCUELAS POR MODELO
# ==========================================


def obtener_delegaciones_por_modelo(id_modelo=None):
    """Obtiene las delegaciones registradas, filtrando opcionalmente por modelo."""
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
        st.error(f"Error al obtener delegaciones: {e}")
        return []


def actualizar_estado_delegacion(id_delegacion, estado, motivo=""):
    """Actualiza el estado de aprobación o rechazo de un legajo de escuela."""
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


# ==========================================
# 3. INTEGRANTES / NÓMINA DE ALUMNOS
# ==========================================


def obtener_integrantes_delegacion(id_delegacion):
    """Obtiene todos los participantes registrados en una delegación específica."""
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
        st.error(f"Error al obtener integrantes de la delegación: {e}")
        return []


def obtener_nominas_por_modelo(id_modelo=None):
    """Obtiene la nómina general de todos los estudiantes y docentes del modelo seleccionado."""
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


# ==========================================
# 4. GESTIÓN DE PAGOS
# ==========================================


def obtener_todos_pagos(id_modelo=None):
    """Recupera los comprobantes e historial de pagos."""
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
    """Filtra únicamente los pagos con estado PENDIENTE del modelo correspondiente."""
    pagos = obtener_todos_pagos(id_modelo)
    return [
        p
        for p in pagos
        if str(p.get("estado_pago", "")).upper() == "PENDIENTE"
    ]


def actualizar_estado_pago(id_pago, nuevo_estado):
    """Cambia el estado de revisión de un pago (APROBADO/RECHAZADO)."""
    try:
        db.collection("pagos").document(str(id_pago)).set(
            {"estado_pago": nuevo_estado}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado del pago: {e}")
        return False
