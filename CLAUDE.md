# Reportes de calidad MGO — Negocio Celulosa

Este proyecto genera un reporte HTML diario sobre la **calidad** de las investigaciones de Resolución de Problemas (RdP) por NAT. Mantiene el formato del Reporte de Calidad RdP ago-sep 2026 (vista planta + radiografía por NAT) y lo complementa con los criterios del Playbook MGO (oct-2025) y del Diagnóstico RDP (pauta 0–3, línea base, metas y recurrencias). El proyecto y todas sus salidas están en español. Las confirmaciones TBH quedan fuera del alcance: el reporte TBH se usó solo como referencia de formato visual.

Hay dos reportes, cada uno con su skill:
- **RdP diario por NAT**: skill `reporte-diario-rdp` (`python3 -m reporte.diario`).
- **RIT semanal** (levantamientos de las Reuniones de Inicio de Turno en SoftExpert), por área, especialidad, equipo y persona: skill `reporte-semanal-rit` (`python3 -m reporte.rit`). Separa la adherencia a la práctica de la calidad de los hallazgos y no evalúa el cierre.

## Ejecutar

```
pip install -r requirements.txt
python3 -m reporte.diario --planta "Nueva Aldea" --fecha 2026-10-02 --json
python3 -m reporte.rit --planta "Nueva Aldea" --semana 2026-09-21 --json
```

## Estructura

| Ruta | Contenido |
|---|---|
| `reporte/fuente.py` | Carga de datos: Excel hoy; `cargar_qvd` / `cargar_sql` listos para la base de los QVD. Contrato de columnas. |
| `reporte/calidad.py` | Reglas: título, causa, tipo de acción S/C/R, recurrencias |
| `reporte/diario.py` | Cálculo "a la fecha", focos automáticos, HTML y JSON |
| `reporte/rit.py` | Reporte semanal RIT: carga de la lista InicioTurno_SE, pauta 0–3 de hallazgos, adherencia, cuadrantes, personas, cruce con el Top 20 y HTML |
| `config/rit.json` | Parámetros RIT: días esperados, feriados, umbrales |
| `config/clasificacion_acciones.csv` | Clasificación manual de acciones S/C/R; prevalece sobre la automática |
| `config/pauta_eventos.csv` | Corrección manual de la pauta 0–3 por evento |
| `config/linea_base.json` | Período de línea base, metas del Diagnóstico y valores de la lectura manual |
| `config/casos_seguimiento.json` | Recurrencias y casos críticos del Diagnóstico, con acciones clave y palabras clave |
| `config/medidas_control.json` | Conclusión y medidas de control por NAT (caso / control que faltó / medida / verificación) |
| `comentarios/` | Focos y lectura redactados por día (JSON); `ejemplo.json` muestra el formato |
| `ref/estilos_*.css` | Diseño (paleta gris/verde/naranja/madera) |
| `data/`, `out/` | Excel de entrada (RDP_Completo_*.xlsx, RIT_*.xlsx, Top_usuarios*.html) y reportes generados. **No se versionan**: el repo es público y contienen nombres. |

## Convenciones

- Los números salen siempre del script. Los textos los redacta Claude o una persona en `comentarios/`.
- Cada afirmación cita IDs de evento. Las medidas de control son propuestas a validar con el NAT.
- Si cambias una regla o un umbral, actualiza también `.claude/skills/reporte-diario-rdp/references/reglas_calidad.md`.

## Pendientes

- Conectar la base de origen de los QVD: definir las consultas en `cargar_sql`, que deben devolver las columnas de `COLS_REGISTROS` y `COLS_ACCIONES`.
- Si la base trae categoría del evento, horas perdidas o campo de eficacia, agregarlos al contrato y al chequeo (herramienta y plazo según categoría).
- Automatizar la corrida diaria.
