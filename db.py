import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import streamlit as st

# Inicialización Singleton de Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ==========================================
# 1. GESTIÓN DE MODELOS Y CONFIGURACIÓN
# ==========================================


def obtener_modelos_activos():
    """Obtiene la lista de modelos desde Firestore o genera una lista de respaldo."""
    try:
        docs = db.collection("modelos").stream()
        modelos = []
        for doc in docs:
            m = doc.to_dict()
            m["id_modelo"] = doc.id
            modelos.append(m)

        if not modelos:
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


def obtener_parametros_comites(id_modelo):
    """Obtiene la lista de comités u órganos configurados para el modelo."""
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("parametros_comites", [])
        return []
    except Exception as e:
        st.error(f"Error al leer parámetros de comités: {e}")
        return []


def guardar_parametros_comites(id_modelo, lista_comites):
    """Guarda la estructura de comités (replicando la tabla PARAMETROS_COMITES)."""
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"parametros_comites": lista_comites}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar parámetros de comités: {e}")
        return False


def obtener_esquema_formulario(id_modelo):
    """Recupera los campos personalizados para los formularios de inscripción."""
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("campos_personalizados", [])
        return []
    except Exception as e:
        st.error(f"Error al obtener esquema de formulario: {e}")
        return []


def guardar_esquema_formulario(id_modelo, lista_campos):
    """Guarda la lista de campos personalizados del formulario."""
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"campos_personalizados": lista_campos}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar esquema de formulario: {e}")
        return False


# ==========================================
# 2. DELEGACIONES Y ESCUELAS
# ==========================================


def obtener_delegaciones_por_modelo(id_modelo=None):
    """Obtiene las delegaciones filtradas por el modelo activo."""
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


def actualizar_estado_delegacion(id_delegacion, estado, motivo=""):
    """Actualiza el estado de aprobación/rechazo del legajo de una institución."""
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
# 3. INTEGRANTES Y NÓMINAS
# ==========================================


def obtener_integrantes_delegacion(id_delegacion):
    """Recupera los participantes pertenecientes a una delegación."""
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
    """Consolida la nómina de todos los participantes del modelo seleccionado."""
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
    """Obtiene el historial de comprobantes de pago."""
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
    """Filtra únicamente los pagos pendientes de revisión."""
    pagos = obtener_todos_pagos(id_modelo)
    return [
        p
        for p in pagos
        if str(p.get("estado_pago", "")).upper() == "PENDIENTE"
    ]


def actualizar_estado_pago(id_pago, nuevo_estado):
    """Actualiza el estado de aprobación o rechazo de un comprobante de pago."""
    try:
        db.collection("pagos").document(str(id_pago)).set(
            {"estado_pago": nuevo_estado}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado del pago: {e}")
        return False


# ==========================================
# 5. AUDITORÍA DE ACREDITACIÓN EN VIVO
# ==========================================


def procesar_acreditacion_forms(df_forms, id_modelo):
    """Cruza los DNI cargados vía Google Forms contra la nómina en Firestore."""
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
