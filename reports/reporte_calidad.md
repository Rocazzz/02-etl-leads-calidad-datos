# Reporte de calidad de datos · Leads 2025
_Generado automáticamente por `src/etl.py` el 2026-11-21 13:23_

## Resumen
| métrica                      | valor   |
|:-----------------------------|:--------|
| email válido (crudo)         | 94.0%   |
| telefono válido (crudo)      | 94.5%   |
| Filas crudas                 | 1950    |
| Filas limpias                | 1799    |
| Duplicados eliminados        | 151     |
| Variantes de ciudad (crudo)  | 19      |
| Ciudades estandarizadas      | 6       |
| Formatos de fecha detectados | 3       |
| Leads contactables           | 99.7%   |

## Nulos por columna en el archivo crudo
|                   |   % nulos (crudo) |
|:------------------|------------------:|
| id_origen         |               0   |
| fuente            |               0   |
| fecha_creacion    |               0   |
| nombre_completo   |               0   |
| email             |               2.7 |
| telefono          |               0   |
| ciudad            |               6.5 |
| servicio_interes  |               0   |
| utm_source_medium |               9.3 |
| agendo_cita       |               9.9 |
| es_cliente        |               0   |
| valor_venta       |              79.5 |

## Reglas de validación
| Regla | Resultado |
|---|---|
| lead_id único | ✅ OK |
| fecha_creacion sin nulos | ✅ OK |
| fechas dentro de 2025 | ✅ OK |
| cliente => agendó cita | ✅ OK |
| cliente => valor_venta > 0 | ✅ OK |
| no cliente => sin valor | ✅ OK |