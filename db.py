import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st

if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- DELEGACIONES ---


def obtener_todas_delegaciones():
    docs = db.collection("delegaciones").stream()
    delegaciones = []
    for doc in docs:
        datos = doc.to_dict()
        datos["id"] = doc.id
        datos["id_delegacion"] = doc.id
        delegaciones.append(datos)
    return delegaciones


def actualizar_estado_delegacion(id_delegacion, estado, motivo=""):
    payload = {"estado": estado}
    if motivo:
        payload["motivo_rechazo"] = motivo
    db.collection("delegaciones").document(str(id_delegacion)).set(
        payload, merge=True
    )


# --- INTEGRANTES ---


def obtener_integrantes_delegacion(id_delegacion):
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


def obtener_todas_nominas():
    delegaciones = obtener_todas_delegaciones()
    todas_nominas = []
    for d in delegaciones:
        id_del = d.get("id")
        integrantes = obtener_integrantes_delegacion(id_del)
        for i in integrantes:
            i["id_delegacion"] = id_del
            i["nombre_colegio"] = d.get("nombre_colegio", "Sin Nombre")
            todas_nominas.append(i)
    return todas_nominas


# --- PAGOS ---


def obtener_todos_pagos():
    docs = db.collection("pagos").stream()
    pagos = []
    for doc in docs:
        p = doc.to_dict()
        p["id_pago"] = doc.id
        pagos.append(p)
    return pagos


def obtener_pagos_pendientes():
    pagos = obtener_todos_pagos()
    return [
        p
        for p in pagos
        if str(p.get("estado_pago", "")).upper() == "PENDIENTE"
    ]


def actualizar_estado_pago(id_pago, nuevo_estado):
    db.collection("pagos").document(str(id_pago)).set(
        {"estado_pago": nuevo_estado}, merge=True
    )
