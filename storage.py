import os
import sqlite3
import uuid
from datetime import datetime, timezone


# ============================================================
# RUTAS DE ALMACENAMIENTO
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

DB_PATH = os.path.join(DATA_DIR, "plantmedic.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)


EXTENSIONES_POR_MIME = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


# ============================================================
# INICIALIZAR BASE DE DATOS
# ============================================================

def init_db():

    conexion = sqlite3.connect(DB_PATH)

    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS plantas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            imagen_archivo TEXT NOT NULL,
            status TEXT NOT NULL,
            nombre_planta TEXT NOT NULL,
            nombre_cientifico TEXT NOT NULL,
            familia TEXT NOT NULL,
            hoja TEXT NOT NULL,
            tallo TEXT NOT NULL,
            epoca TEXT NOT NULL,
            clima TEXT NOT NULL,
            riego TEXT NOT NULL,
            tipo_problema TEXT NOT NULL,
            severidad TEXT NOT NULL,
            observation TEXT NOT NULL,
            recommendation TEXT NOT NULL
        )
        """
    )

    conexion.commit()
    conexion.close()


# ============================================================
# GUARDAR UN ANÁLISIS (IMAGEN + RESULTADO)
# ============================================================

def guardar_analisis(
    resultado: dict,
    imagen_bytes: bytes,
    mime_type: str
) -> dict:

    extension = EXTENSIONES_POR_MIME.get(
        mime_type,
        "jpg"
    )

    nombre_archivo = f"{uuid.uuid4().hex}.{extension}"

    ruta_archivo = os.path.join(
        UPLOADS_DIR,
        nombre_archivo
    )

    with open(ruta_archivo, "wb") as archivo:
        archivo.write(imagen_bytes)

    caracteristicas = resultado.get(
        "caracteristicas",
        {}
    )

    fecha = datetime.now(
        timezone.utc
    ).isoformat()

    conexion = sqlite3.connect(DB_PATH)

    cursor = conexion.execute(
        """
        INSERT INTO plantas (
            fecha, imagen_archivo, status,
            nombre_planta, nombre_cientifico, familia,
            hoja, tallo, epoca, clima, riego,
            tipo_problema, severidad, observation, recommendation
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fecha,
            nombre_archivo,
            resultado.get("status", "inconcluso"),
            resultado.get("nombre_planta", "No identificada"),
            resultado.get("nombre_cientifico", "No disponible"),
            resultado.get("familia", "No disponible"),
            caracteristicas.get("hoja", "Información no disponible"),
            caracteristicas.get("tallo", "Información no disponible"),
            caracteristicas.get("epoca", "Información no disponible"),
            caracteristicas.get("clima", "Información no disponible"),
            caracteristicas.get("riego", "Información no disponible"),
            resultado.get("tipo_problema", "desconocido"),
            resultado.get("severidad", "desconocida"),
            resultado.get("observation", ""),
            resultado.get("recommendation", ""),
        )
    )

    conexion.commit()

    nuevo_id = cursor.lastrowid

    conexion.close()

    return obtener_analisis(nuevo_id)


# ============================================================
# CONVERTIR FILA -> DICCIONARIO
# ============================================================

def _fila_a_dict(fila: sqlite3.Row) -> dict:

    return {

        "id": fila["id"],

        "fecha": fila["fecha"],

        "imagen_url": f"/uploads/{fila['imagen_archivo']}",

        "status": fila["status"],

        "nombre_planta": fila["nombre_planta"],

        "nombre_cientifico": fila["nombre_cientifico"],

        "familia": fila["familia"],

        "caracteristicas": {

            "hoja": fila["hoja"],

            "tallo": fila["tallo"],

            "epoca": fila["epoca"],

            "clima": fila["clima"],

            "riego": fila["riego"],

        },

        "tipo_problema": fila["tipo_problema"],

        "severidad": fila["severidad"],

        "observation": fila["observation"],

        "recommendation": fila["recommendation"],

    }


def _conectar_con_filas() -> sqlite3.Connection:

    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row

    return conexion


# ============================================================
# LISTAR TODOS LOS ANÁLISIS GUARDADOS
# ============================================================

def listar_analisis() -> list:

    conexion = _conectar_con_filas()

    filas = conexion.execute(
        "SELECT * FROM plantas ORDER BY fecha DESC"
    ).fetchall()

    conexion.close()

    return [_fila_a_dict(fila) for fila in filas]


# ============================================================
# OBTENER UN ANÁLISIS POR ID
# ============================================================

def obtener_analisis(id_planta: int):

    conexion = _conectar_con_filas()

    fila = conexion.execute(
        "SELECT * FROM plantas WHERE id = ?",
        (id_planta,)
    ).fetchone()

    conexion.close()

    if fila is None:
        return None

    return _fila_a_dict(fila)


# ============================================================
# ELIMINAR UN ANÁLISIS
# ============================================================

def eliminar_analisis(id_planta: int) -> bool:

    conexion = _conectar_con_filas()

    fila = conexion.execute(
        "SELECT imagen_archivo FROM plantas WHERE id = ?",
        (id_planta,)
    ).fetchone()

    if fila is None:
        conexion.close()
        return False

    conexion.execute(
        "DELETE FROM plantas WHERE id = ?",
        (id_planta,)
    )

    conexion.commit()
    conexion.close()

    ruta_archivo = os.path.join(
        UPLOADS_DIR,
        fila["imagen_archivo"]
    )

    if os.path.exists(ruta_archivo):
        os.remove(ruta_archivo)

    return True


# ============================================================
# ELIMINAR TODOS LOS ANÁLISIS
# ============================================================

def eliminar_todos() -> int:

    conexion = _conectar_con_filas()

    filas = conexion.execute(
        "SELECT imagen_archivo FROM plantas"
    ).fetchall()

    conexion.execute(
        "DELETE FROM plantas"
    )

    conexion.commit()
    conexion.close()

    for fila in filas:

        ruta_archivo = os.path.join(
            UPLOADS_DIR,
            fila["imagen_archivo"]
        )

        if os.path.exists(ruta_archivo):
            os.remove(ruta_archivo)

    return len(filas)
