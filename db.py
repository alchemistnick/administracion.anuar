import random
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
    """Recupera la lista de modelos registrados desde Firestore."""
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
    """Obtiene los comités/órganos del modelo (replicando la estructura PARAMETROS_COMITES)."""
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("parametros_comites", [])
        return []
    except Exception as e:
        st.error(f"Error al leer parámetros de comités: {e}")
        return []


def guardar_parametros_comites(id_modelo, lista_comites):
    """Guarda la lista de comités del modelo."""
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"parametros_comites": lista_comites}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar parámetros de comités: {e}")
        return False


def obtener_esquema_formulario(id_modelo):
    """Recupera los campos personalizados para el formulario de inscripción."""
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("campos_personalizados", [])
        return []
    except Exception as e:
        st.error(f"Error al obtener esquema del formulario: {e}")
        return []


def guardar_esquema_formulario(id_modelo, lista_campos):
    """Guarda la lista de campos personalizados del formulario."""
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"campos_personalizados": lista_campos}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar esquema del formulario: {e}")
        return False


# ==========================================
# 2. CATÁLOGO MAESTRO Y SORTEO AUTOMÁTICO
# ==========================================


def obtener_catalogo_paises(id_modelo):
    """Obtiene la lista maestra de países/bancas disponibles para el modelo."""
    try:
        doc = db.collection("configuracion").document(str(id_modelo)).get()
        if doc.exists:
            return doc.to_dict().get("catalogo_paises", [])
        return []
    except Exception as e:
        st.error(f"Error al leer catálogo de países: {e}")
        return []


def guardar_catalogo_paises(id_modelo, lista_paises):
    """Guarda la lista maestra de países disponibles."""
    try:
        db.collection("configuracion").document(str(id_modelo)).set(
            {"catalogo_paises": lista_paises}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar catálogo de países: {e}")
        return False


def ejecutar_sorteo_automatico(id_modelo):
    """Ejecuta el sorteo aleatorio de países/bancas asignando a cada escuela

    los países del catálogo sin repetirlos por comité.
    """
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


# ==========================================
# 3. DELEGACIONES, INTEGRANTES Y PAGOS
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
    """Actualiza el estado de aprobación/rechazo de un legajo."""
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
    """Recupera los integrantes pertenecientes a una delegación."""
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
    """Filtra los pagos pendientes de revisión."""
    pagos = obtener_todos_pagos(id_modelo)
    return [
        p
        for p in pagos
        if str(p.get("estado_pago", "")).upper() == "PENDIENTE"
    ]


def actualizar_estado_pago(id_pago, nuevo_estado):
    """Actualiza el estado de un comprobante de pago."""
    try:
        db.collection("pagos").document(str(id_pago)).set(
            {"estado_pago": nuevo_estado}, merge=True
        )
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado del pago: {e}")
        return False


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
