# Reportes de calidad MGO — Negocio Celulosa

Este proyecto genera un reporte HTML diario sobre la **calidad** de las investigaciones de Resolución de Problemas (RdP) por NAT. Mantiene el formato del Reporte de Calidad RdP ago-sep 2026 (vista planta + radiografía por NAT) y lo complementa con los criterios del Playbook MGO (oct-2025) y del Diagnóstico RDP (pauta 0–3, línea base, metas y recurrencias). El proyecto y todas sus salidas están en español. Las confirmaciones TBH quedan fuera del alcance: el reporte TBH se usó solo como referencia de formato visual.

Hay dos reportes, cada uno con su skill:
- **RdP diario por NAT**: skill `reporte-diario-rdp` (`python3 -m reporte.diario`). Tiene una segunda versión, el **informe de gestión** (`python3 -m reporte.gestion`): el mismo formato, orientado a conversar con cada NAT (tres niveles de calidad —levantamiento, resolución, aprendizaje—, «x de n» y lectura en el tiempo, ejecución vs. eficacia, cadenas de recurrencia, casos de referencia para compartir y guía de conversación 1 a 1 con seguimiento de acuerdos).
- **RIT** (levantamientos de las Reuniones de Inicio de Turno en SoftExpert): skill `reporte-semanal-rit` (`python3 -m reporte.rit`). Herramienta de consulta con 5 niveles separados (adherencia, ejecución/trazabilidad, redacción, pertinencia técnica, efectividad), filtros que recalculan todo en el navegador y validación en `pruebas/validar_rit.py`.

## Ejecutar

```
pip install -r requirements.txt
python3 -m reporte.diario --planta "Nueva Aldea" --fecha 2026-10-02 --json
python3 -m reporte.gestion --planta "Nueva Aldea" --fecha 2026-10-02 --json   # informe de gestión para la conversación con cada NAT
python3 -m reporte.rit --planta "Nueva Aldea" --json                  # HTML autónomo con todos los RIT evaluados
python3 pruebas/validar_rit.py out/RIT_semanal_Nueva_Aldea.html        # validación lógica (requiere playwright)
```

## Estructura

| Ruta | Contenido |
|---|---|
| `reporte/fuente.py` | Carga de datos: Excel hoy; `cargar_qvd` / `cargar_sql` listos para la base de los QVD. Contrato de columnas. |
| `reporte/calidad.py` | Reglas: título, causa, tipo de acción S/C/R, recurrencias |
| `reporte/diario.py` | Cálculo "a la fecha", focos automáticos, HTML y JSON |
| `reporte/aprendizaje.py` | Nivel 3: aspectos de los tres niveles, lectura en el tiempo, eficacia observable, nivel de aprendizaje, cadenas de recurrencia y buenas prácticas |
| `reporte/gestion.py` | Informe de gestión: reutiliza `diario.py` y agrega la guía de conversación, la tabla en tres niveles, el mapa por NAT y los casos de referencia |
| `config/acuerdos_nat.json` | Acuerdos de cada conversación 1 a 1 (aspecto, fecha, revisión): el informe muestra la evolución antes/después |
| `config/buenas_practicas.json` | Biblioteca de casos de referencia: validada, compartida o descartada |
| `reporte/rit.py` | Reporte RIT: carga, evaluación automática de redacción 0–3, días exigidos por equipo y semana; arma los datos del HTML (definiciones de KPI en el docstring) |
| `reporte/plantillas/rit_app.*` | HTML, CSS y JS del reporte RIT: cálculo de indicadores con filtros, secciones por nivel, detalle |
| `config/cuentas_compartidas.csv` | Cuentas genéricas (correos ce05.*): RIT no atribuibles a una persona |
| `config/validacion_tecnica.csv` | Validación humana de pertinencia técnica por hallazgo (vacío hoy) |
| `pruebas/validar_rit.py` | Validación lógica del HTML RIT (porcentajes, sumas, filtros, trazabilidad, ejemplos) |
| `config/rit.json` | Parámetros RIT: metas, umbrales de categorías, muestra mínima, semana de inicio, feriados |
| `config/rotacion_turnos.csv` | Rotación de turnos de Operación (fecha, turno A–E, código D/N/DC/AD), abr–dic 2026; define los días en que se exige el RIT |
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
