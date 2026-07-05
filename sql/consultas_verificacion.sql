CREATE DATABASE biblioteca_dw;

USE biblioteca_dw;

-- 1. Cuantos registros hay en fact_prestamos = 98
SELECT COUNT(*) AS total_fact_prestamos
FROM fact_prestamos;

-- 2. Cuantos registros hay en etl_errores = 2
SELECT COUNT(*) AS total_etl_errores
FROM etl_errores;

-- 3. Que errores fueron registrados = id_registro 5099  -> total_multa incorrecto (esperado=70, recibido=40) y id_registro 5002  -> id_prestamo duplicado
SELECT id_error, fecha_error, fila_csv, id_registro, descripcion_error
FROM etl_errores
ORDER BY id_error;

-- 4. Cual fue el ultimo estado registrado en etl_log = FINALIZADO_CON_ERRORES, filas_leidas = 100, filas_cargadas = 98 y filas_rechazadas = 2
SELECT estado, fecha_ejecucion, filas_leidas, filas_cargadas, filas_rechazadas
FROM etl_log
ORDER BY fecha_ejecucion DESC
LIMIT 1;

-- 5. Total de multas por carrera = DNAM 1050; IRD 900; IDGS 750; ITI 560; IGE 450
SELECT c.carrera, SUM(f.total_multa) AS total_multa
FROM fact_prestamos f
JOIN dim_carrera c ON f.id_carrera = c.id_carrera
GROUP BY c.carrera
ORDER BY total_multa DESC;

-- 6. Total de multas por categoria de libro = Inteligencia artificial 850; Analitica 710; Bases de datos 600; Matematicas 600; Sistemas 400; Redes 200; Software 200; Programacion 150
SELECT l.categoria, SUM(f.total_multa) AS total_multa
FROM fact_prestamos f
JOIN dim_libro l ON f.id_libro = l.id_libro
GROUP BY l.categoria
ORDER BY total_multa DESC;

-- 7. Promedio de dias de prestamo por sede = Biblioteca Central 6.20; Sala Sur 6.08; Sala Norte 4.80; Laboratorio Digital 4.58
SELECT s.sede, AVG(f.dias_prestamo) AS promedio_dias_prestamo
FROM fact_prestamos f
JOIN dim_sede s ON f.id_sede = s.id_sede
GROUP BY s.sede
ORDER BY promedio_dias_prestamo DESC;

-- 8. Los 5 libros con mayor total de multa = Fundamentos de IA (Inteligencia artificial) 850; Estadistica Aplicada (Matematicas) 600; Bases de Datos I (Bases de datos) 500; Linux para Todos (Sistemas) 400; Analisis de Datos (Analitica) 360
SELECT l.libro, l.categoria, SUM(f.total_multa) AS total_multa
FROM fact_prestamos f
JOIN dim_libro l ON f.id_libro = l.id_libro
GROUP BY l.libro, l.categoria
ORDER BY total_multa DESC
LIMIT 5;

-- 9. Prestamos detallados con fecha, alumno, carrera, libro, categoria, sede y total de multa
SELECT
    f.id_prestamo,
    fe.fecha,
    a.alumno,
    c.carrera,
    l.libro,
    l.categoria,
    s.sede,
    f.total_multa
FROM fact_prestamos f
JOIN dim_fecha fe   ON f.id_fecha = fe.id_fecha
JOIN dim_alumno a   ON f.id_alumno = a.id_alumno
JOIN dim_carrera c  ON f.id_carrera = c.id_carrera
JOIN dim_libro l    ON f.id_libro = l.id_libro
JOIN dim_sede s     ON f.id_sede = s.id_sede
ORDER BY fe.fecha;

-- 10. Conteo de prestamos por sede = Biblioteca Central 25; Sala Norte 25; Laboratorio Digital 24; Sala Sur 24
SELECT s.sede, COUNT(*) AS total_prestamos
FROM fact_prestamos f
JOIN dim_sede s ON f.id_sede = s.id_sede
GROUP BY s.sede
ORDER BY total_prestamos DESC;