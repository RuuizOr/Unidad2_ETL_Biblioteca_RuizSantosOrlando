# Unidad 2 - ETL Prestamos de Biblioteca

## 1. Objetivo del proyecto

Construir un mini proyecto de ETL que lea el dataset `prestamos_biblioteca_100.csv`,
lo limpie, valide los registros, cargue los datos correctos a un mini Data
Warehouse en MySQL (`biblioteca_dw`) con modelo estrella (dimensiones + hechos),
registre los registros con error en `etl_errores` y deje una bitácora de cada
ejecución en `etl_log`.

Resultado esperado:

- Registros procesados: 100
- Registros correctos cargados: 98
- Registros con error: 2
  - `id_prestamo` 5099: `total_multa` incorrecto
  - `id_prestamo` 5002: `id_prestamo` duplicado

## 2. Requisitos para ejecutarlo

- Python 3.9 o superior
- MySQL Server (local o remoto)
- Librerías: `pandas`, `mysql-connector-python`

## 3. Como crear la base de datos

Antes de ejecutar el script, crea la base de datos vacía (desde MySQL,
consola o DataGrip):

```sql
CREATE DATABASE biblioteca_dw;
```

El script se encarga de crear todas las tablas (`dim_alumno`, `dim_carrera`,
`dim_libro`, `dim_sede`, `dim_fecha`, `fact_prestamos`, `etl_errores`,
`etl_log`) si no existen.

## 4. Como instalar librerías

Desde la raíz del repositorio:

```bash
pip install pandas mysql-connector-python
```

## 5. Como ejecutar el script

1. Edita `scripts/etl_biblioteca.py` y ajusta:
   - `DB_CONFIG["password"]` con tu contraseña de MySQL.
   - `NOMBRE_ALUMNO` con tu nombre completo.
2. Ejecuta desde la raíz del repositorio (`unidad2_etl_biblioteca/`):

```bash
python scripts/etl_biblioteca.py
```

El script es idempotente: puede ejecutarse varias veces sin duplicar datos,
ya que limpia las tablas de dimensiones, hechos y errores antes de volver a
cargar (la tabla `etl_log` conserva el historial de todas las ejecuciones).

## 6. Resultado esperado

Al finalizar la ejecución, en consola y en `evidencias/reporte_ejecucion.txt`
debe verse:

```
Filas leidas: 100
Filas cargadas: 98
Filas rechazadas: 2
Estado: FINALIZADO_CON_ERRORES
```

- `fact_prestamos` debe tener 98 registros.
- `etl_errores` debe tener 2 registros (5099 y 5002).
- Las consultas de verificación están en `sql/consultas_verificacion.sql`.