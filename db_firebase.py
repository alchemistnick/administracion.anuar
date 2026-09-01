import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st

# 1. Inicializar la conexión con Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.title("🔥 Prueba de Conexión — Proyecto DELTA (DELTANUAR)")

st.subheader("1. Probar Escritura")
if st.button("Guardar Escuela de Prueba"):
    doc_ref = db.collection("delegaciones").document("DEL-001")
    doc_ref.set(
        {
            "nombre_colegio": "Instituto de Prueba DELTA",
            "docente_responsable": "Prof. Pérez",
            "docente_email": "docente@prueba.edu.ar",
            "cupos_solicitados": 10,
            "estado_tramite": "REGISTRADO",
        }
    )
    st.success("¡Datos guardados con éxito en la colección 'delegaciones'!")

st.subheader("2. Probar Lectura")
if st.button("Consultar Delegaciones"):
    docs = db.collection("delegaciones").stream()
    delegaciones = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        delegaciones.append(d)

    if delegaciones:
        st.write("Delegaciones encontradas en la nube:")
        st.json(delegaciones)
    else:
        st.info("No hay registros en la colección.")
