import os
import sys
import json
from datetime import datetime

import pandas as pd
import mysql.connector
from mysql.connector import Error

# =========================================================
# CONFIGURACION - AJUSTA ESTOS DATOS A TU ENTORNO
# =========================================================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "biblioteca_dw",
}

NOMBRE_ALUMNO = "Orlando Ruiz Santos" 

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "prestamos_biblioteca_100.csv")
REPORTE_PATH = os.path.join(BASE_DIR, "evidencias", "reporte_ejecucion.txt")

COLUMNAS_OBLIGATORIAS = [
    "id_prestamo", "fecha_prestamo", "alumno", "carrera", "libro",
    "categoria", "dias_prestamo", "multa_diaria", "sede", "total_multa",
]


# =========================================================
# PARTE 1: LECTURA Y LIMPIEZA BASICA
# =========================================================
def leer_y_limpiar(csv_path):
    df = pd.read_csv(csv_path)

    df.columns = [c.strip().lower() for c in df.columns]

    columnas_texto = ["alumno", "carrera", "libro", "categoria", "sede"]
    for col in columnas_texto:
        df[col] = df[col].astype(str).str.strip()

    df["fecha_prestamo"] = pd.to_datetime(df["fecha_prestamo"], errors="coerce")

    for col in ["dias_prestamo", "multa_diaria", "total_multa"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["fila_csv"] = df.index + 2

    return df


def validar_nulos_obligatorios(df):
    """Devuelve dataframe de filas con nulos en columnas obligatorias."""
    return df[df[COLUMNAS_OBLIGATORIAS].isnull().any(axis=1)]


# =========================================================
# PARTE 4: VALIDACIONES (duplicados y total_multa)
# =========================================================
def validar(df):
    """
    Devuelve:
        df_validos: filas correctas listas para cargar
        errores: lista de dicts para etl_errores
    """
    errores = []
    filas_con_error_idx = set()

    nulos = validar_nulos_obligatorios(df)
    for _, fila in nulos.iterrows():
        errores.append({
            "fila_csv": int(fila["fila_csv"]),
            "id_registro": str(fila.get("id_prestamo", "")),
            "descripcion_error": "Valor nulo en columna obligatoria",
            "datos_originales": fila.to_dict(),
        })
        filas_con_error_idx.add(fila.name)

    duplicados_mask = df["id_prestamo"].duplicated(keep="first")
    for idx in df[duplicados_mask].index:
        if idx in filas_con_error_idx:
            continue
        fila = df.loc[idx]
        errores.append({
            "fila_csv": int(fila["fila_csv"]),
            "id_registro": str(fila["id_prestamo"]),
            "descripcion_error": "id_prestamo duplicado",
            "datos_originales": fila.drop("fila_csv").to_dict(),
        })
        filas_con_error_idx.add(idx)

    esperado = df["dias_prestamo"] * df["multa_diaria"]
    mismatch_mask = (df["total_multa"] != esperado)
    for idx in df[mismatch_mask].index:
        if idx in filas_con_error_idx:
            continue
        fila = df.loc[idx]
        errores.append({
            "fila_csv": int(fila["fila_csv"]),
            "id_registro": str(fila["id_prestamo"]),
            "descripcion_error": (
                f"total_multa incorrecto (esperado="
                f"{fila['dias_prestamo'] * fila['multa_diaria']}, "
                f"recibido={fila['total_multa']})"
            ),
            "datos_originales": fila.drop("fila_csv").to_dict(),
        })
        filas_con_error_idx.add(idx)

    df_validos = df.drop(index=list(filas_con_error_idx)).copy()
    return df_validos, errores


# =========================================================
# PARTE 2 y 3: CREACION DE TABLAS
# =========================================================
def crear_tablas(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_alumno (
            id_alumno INT AUTO_INCREMENT PRIMARY KEY,
            alumno VARCHAR(150) NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_carrera (
            id_carrera INT AUTO_INCREMENT PRIMARY KEY,
            carrera VARCHAR(100) NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_libro (
            id_libro INT AUTO_INCREMENT PRIMARY KEY,
            libro VARCHAR(200) NOT NULL,
            categoria VARCHAR(100) NOT NULL,
            UNIQUE KEY uq_libro_categoria (libro, categoria)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_sede (
            id_sede INT AUTO_INCREMENT PRIMARY KEY,
            sede VARCHAR(100) NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_fecha (
            id_fecha INT AUTO_INCREMENT PRIMARY KEY,
            fecha DATE NOT NULL UNIQUE,
            anio INT NOT NULL,
            mes INT NOT NULL,
            dia INT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_prestamos (
            id_prestamo INT PRIMARY KEY,
            id_fecha INT NOT NULL,
            id_alumno INT NOT NULL,
            id_carrera INT NOT NULL,
            id_libro INT NOT NULL,
            id_sede INT NOT NULL,
            dias_prestamo INT NOT NULL,
            multa_diaria DECIMAL(10,2) NOT NULL,
            total_multa DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (id_fecha) REFERENCES dim_fecha(id_fecha),
            FOREIGN KEY (id_alumno) REFERENCES dim_alumno(id_alumno),
            FOREIGN KEY (id_carrera) REFERENCES dim_carrera(id_carrera),
            FOREIGN KEY (id_libro) REFERENCES dim_libro(id_libro),
            FOREIGN KEY (id_sede) REFERENCES dim_sede(id_sede)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS etl_errores (
            id_error INT AUTO_INCREMENT PRIMARY KEY,
            fecha_error DATETIME NOT NULL,
            archivo_origen VARCHAR(200) NOT NULL,
            fila_csv INT NOT NULL,
            id_registro VARCHAR(50),
            descripcion_error VARCHAR(300) NOT NULL,
            datos_originales TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS etl_log (
            id_log INT AUTO_INCREMENT PRIMARY KEY,
            fecha_ejecucion DATETIME NOT NULL,
            archivo_origen VARCHAR(200) NOT NULL,
            filas_leidas INT NOT NULL,
            filas_cargadas INT NOT NULL,
            filas_rechazadas INT NOT NULL,
            estado VARCHAR(50) NOT NULL
        )
    """)


def limpiar_tablas_antes_de_cargar(cursor):
    """Permite re-ejecutar el script sin duplicar datos. etl_log NO se limpia."""
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for tabla in ["fact_prestamos", "etl_errores", "dim_alumno",
                  "dim_carrera", "dim_libro", "dim_sede", "dim_fecha"]:
        cursor.execute(f"TRUNCATE TABLE {tabla}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


# =========================================================
# CARGA DE DIMENSIONES Y HECHOS
# =========================================================
def cargar_dimensiones(cursor, df_validos):
    alumnos = sorted(df_validos["alumno"].unique())
    carreras = sorted(df_validos["carrera"].unique())
    sedes = sorted(df_validos["sede"].unique())
    libros = df_validos[["libro", "categoria"]].drop_duplicates().values.tolist()
    fechas = sorted(df_validos["fecha_prestamo"].dt.date.unique())

    cursor.executemany(
        "INSERT INTO dim_alumno (alumno) VALUES (%s)",
        [(a,) for a in alumnos]
    )
    cursor.executemany(
        "INSERT INTO dim_carrera (carrera) VALUES (%s)",
        [(c,) for c in carreras]
    )
    cursor.executemany(
        "INSERT INTO dim_sede (sede) VALUES (%s)",
        [(s,) for s in sedes]
    )
    cursor.executemany(
        "INSERT INTO dim_libro (libro, categoria) VALUES (%s, %s)",
        [(lib, cat) for lib, cat in libros]
    )
    cursor.executemany(
        "INSERT INTO dim_fecha (fecha, anio, mes, dia) VALUES (%s, %s, %s, %s)",
        [(f, f.year, f.month, f.day) for f in fechas]
    )


def obtener_mapeos(cursor):
    mapeos = {}

    cursor.execute("SELECT id_alumno, alumno FROM dim_alumno")
    mapeos["alumno"] = {alumno: id_ for id_, alumno in cursor.fetchall()}

    cursor.execute("SELECT id_carrera, carrera FROM dim_carrera")
    mapeos["carrera"] = {carrera: id_ for id_, carrera in cursor.fetchall()}

    cursor.execute("SELECT id_sede, sede FROM dim_sede")
    mapeos["sede"] = {sede: id_ for id_, sede in cursor.fetchall()}

    cursor.execute("SELECT id_libro, libro, categoria FROM dim_libro")
    mapeos["libro"] = {(lib, cat): id_ for id_, lib, cat in cursor.fetchall()}

    cursor.execute("SELECT id_fecha, fecha FROM dim_fecha")
    mapeos["fecha"] = {fecha: id_ for id_, fecha in cursor.fetchall()}

    return mapeos


def cargar_fact_prestamos(cursor, df_validos, mapeos):
    filas = []
    for _, r in df_validos.iterrows():
        filas.append((
            int(r["id_prestamo"]),
            mapeos["fecha"][r["fecha_prestamo"].date()],
            mapeos["alumno"][r["alumno"]],
            mapeos["carrera"][r["carrera"]],
            mapeos["libro"][(r["libro"], r["categoria"])],
            mapeos["sede"][r["sede"]],
            int(r["dias_prestamo"]),
            float(r["multa_diaria"]),
            float(r["total_multa"]),
        ))

    cursor.executemany("""
        INSERT INTO fact_prestamos
        (id_prestamo, id_fecha, id_alumno, id_carrera, id_libro, id_sede,
         dias_prestamo, multa_diaria, total_multa)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, filas)


def cargar_errores(cursor, errores, archivo_origen):
    ahora = datetime.now()
    filas = []
    for e in errores:
        filas.append((
            ahora,
            archivo_origen,
            e["fila_csv"],
            e["id_registro"],
            e["descripcion_error"],
            json.dumps(e["datos_originales"], default=str, ensure_ascii=False),
        ))

    cursor.executemany("""
        INSERT INTO etl_errores
        (fecha_error, archivo_origen, fila_csv, id_registro,
         descripcion_error, datos_originales)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, filas)


def registrar_log(cursor, archivo_origen, leidas, cargadas, rechazadas, estado):
    cursor.execute("""
        INSERT INTO etl_log
        (fecha_ejecucion, archivo_origen, filas_leidas, filas_cargadas,
         filas_rechazadas, estado)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (datetime.now(), archivo_origen, leidas, cargadas, rechazadas, estado))


# =========================================================
# PARTE 6: REPORTE DE EJECUCION
# =========================================================
def generar_reporte(path, leidas, cargadas, rechazadas, estado, errores, archivo_origen):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("REPORTE DE EJECUCION - ETL BIBLIOTECA\n")
        f.write("=" * 45 + "\n")
        f.write(f"Nombre del alumno: {NOMBRE_ALUMNO}\n")
        f.write(f"Fecha y hora de ejecucion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Archivo procesado: {archivo_origen}\n")
        f.write(f"Filas leidas: {leidas}\n")
        f.write(f"Filas cargadas: {cargadas}\n")
        f.write(f"Filas rechazadas: {rechazadas}\n")
        f.write(f"Estado final: {estado}\n")
        f.write("\nErrores detectados:\n")
        if errores:
            for e in errores:
                f.write(
                    f"  - id_prestamo {e['id_registro']} "
                    f"(fila CSV {e['fila_csv']}): {e['descripcion_error']}\n"
                )
        else:
            f.write("  - Ninguno\n")


# =========================================================
# MAIN
# =========================================================
def main():
    archivo_origen = os.path.basename(CSV_PATH)

    print(f"Leyendo dataset: {CSV_PATH}")
    df = leer_y_limpiar(CSV_PATH)
    filas_leidas = len(df)

    print("Validando registros...")
    df_validos, errores = validar(df)
    filas_cargadas = len(df_validos)
    filas_rechazadas = len(errores)
    estado = "FINALIZADO_CON_ERRORES" if errores else "FINALIZADO_OK"

    conexion = None
    try:
        conexion = mysql.connector.connect(**DB_CONFIG)
        cursor = conexion.cursor()

        print("Creando tablas (si no existen)...")
        crear_tablas(cursor)
        conexion.commit()

        print("Limpiando tablas antes de cargar (ejecucion idempotente)...")
        limpiar_tablas_antes_de_cargar(cursor)
        conexion.commit()

        print("Cargando dimensiones...")
        cargar_dimensiones(cursor, df_validos)
        conexion.commit()

        mapeos = obtener_mapeos(cursor)

        print("Cargando fact_prestamos...")
        cargar_fact_prestamos(cursor, df_validos, mapeos)

        print("Registrando errores en etl_errores...")
        cargar_errores(cursor, errores, archivo_origen)

        print("Registrando ejecucion en etl_log...")
        registrar_log(cursor, archivo_origen, filas_leidas, filas_cargadas,
                      filas_rechazadas, estado)

        conexion.commit()

    except Error as e:
        if conexion:
            conexion.rollback()
        print(f"ERROR de MySQL: {e}")
        sys.exit(1)
    finally:
        if conexion and conexion.is_connected():
            cursor.close()
            conexion.close()

    print("Generando evidencias/reporte_ejecucion.txt...")
    generar_reporte(REPORTE_PATH, filas_leidas, filas_cargadas,
                     filas_rechazadas, estado, errores, archivo_origen)

    print("\n--- RESUMEN ---")
    print(f"Filas leidas: {filas_leidas}")
    print(f"Filas cargadas: {filas_cargadas}")
    print(f"Filas rechazadas: {filas_rechazadas}")
    print(f"Estado: {estado}")


if __name__ == "__main__":
    main()