import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st

# Inicializar Firebase (singleton para evitar múltiples instanciaciones)
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ==========================================
# 1. DELEGACIONES / ESCUELAS
# ==========================================


def obtener_todas_delegaciones():
    """Recupera la lista completa de delegaciones."""
    docs = db.collection("delegaciones").stream()
    delegaciones = []
    for doc in docs:
        datos = doc.to_dict()
        datos["id"] = doc.id
        delegaciones.append(datos)
    return delegaciones


def obtener_delegacion_por_id(id_delegacion):
    """Busca una delegación por su ID único."""
    doc = db.collection("delegaciones").document(id_delegacion).get()
    if doc.exists:
        datos = doc.to_dict()
        datos["id"] = doc.id
        return datos
    return None


def guardar_o_actualizar_delegacion(id_delegacion, datos_dict):
    """Crea o actualiza los datos de una delegación (merge=True evita sobrescribir campos no enviados)."""
    try:
        db.collection("delegaciones").document(str(id_delegacion)).set(
            datos_dict, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar delegación en Firestore: {e}")
        return False


# ==========================================
# 2. INTEGRANTES / ALUMNOS / DELEGADOS
# ==========================================


def guardar_integrante(id_delegacion, dni_o_id, datos_integrante):
    """Guarda un participante dentro de la subcolección de su delegación."""
    try:
        db.collection("delegaciones").document(str(id_delegacion)).collection(
            "integrantes"
        ).document(str(dni_o_id)).set(datos_integrante, merge=True)
        return True
    except Exception as e:
        st.error(f"Error al guardar participante: {e}")
        return False


def obtener_integrantes_delegacion(id_delegacion):
    """Obtiene la nómina completa de integrantes de una escuela."""
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
