# Reporte diario de calidad RdP por NAT — Negocio Celulosa

Este proyecto genera un reporte HTML diario sobre la **calidad** de las investigaciones de Resolución de Problemas (RdP) por NAT, con los criterios del Playbook MGO (oct-2025). El proyecto y todas sus salidas están en español. Las confirmaciones TBH quedan fuera del alcance: el reporte TBH se usó solo como referencia de formato visual.

Para generar o redactar un reporte, usa la skill `reporte-diario-rdp` (`.claude/skills/reporte-diario-rdp/`).

## Ejecutar

```
pip install -r requirements.txt
python3 -m reporte.diario --planta "Nueva Aldea" --fecha 2026-10-02 --json
```

## Estructura

| Ruta | Contenido |
|---|---|
| `reporte/fuente.py` | Carga de datos: Excel hoy; `cargar_qvd` / `cargar_sql` listos para la base de los QVD. Contrato de columnas. |
| `reporte/calidad.py` | Reglas: título, causa, tipo de acción S/C/R, recurrencias |
| `reporte/diario.py` | Cálculo "a la fecha", focos automáticos, HTML y JSON |
| `config/clasificacion_acciones.csv` | Clasificación manual de acciones; prevalece sobre la automática |
| `comentarios/` | Focos y lectura redactados por día (JSON); `ejemplo.json` muestra el formato |
| `ref/estilos_*.css` | Diseño (paleta gris/verde/naranja/madera) |
| `data/`, `out/` | Excel de entrada y reportes generados. **No se versionan**: el repo es público y contienen nombres. |

## Convenciones

- Los números salen siempre del script. Los textos los redacta Claude o una persona en `comentarios/`.
- Cada afirmación cita IDs de evento. Las medidas de control son propuestas a validar con el NAT.
- Si cambias una regla o un umbral, actualiza también `.claude/skills/reporte-diario-rdp/references/reglas_calidad.md`.

## Pendientes

- Conectar la base de origen de los QVD: definir las consultas en `cargar_sql`, que deben devolver las columnas de `COLS_REGISTROS` y `COLS_ACCIONES`.
- Si la base trae categoría del evento, horas perdidas o campo de eficacia, agregarlos al contrato y al chequeo (herramienta y plazo según categoría).
- Automatizar la corrida diaria.
