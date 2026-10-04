---
name: reporte-semanal-rit
description: Genera el reporte de gestión de los levantamientos de las Reuniones de Inicio de Turno (RIT) registrados en SoftExpert para una planta del Negocio Celulosa. Separa cinco niveles sin combinarlos en un puntaje único (1 adherencia, 2 ejecución y trazabilidad, 3 redacción del hallazgo, 4 pertinencia técnica, 5 efectividad), con filtros que recalculan todo, recorrido semana a semana, diagnóstico problema → evidencia → causa → acción, categorías por equipo, análisis por persona y ejemplos reales. Úsala cuando el usuario pida el reporte RIT, la evaluación de inicios de turno, la calidad de levantamientos en SoftExpert o quién necesita apoyo en el RIT.
---

# Reporte RIT: herramienta de gestión de los levantamientos en SoftExpert

El reporte responde cuatro preguntas, cada una por separado:

1. ¿Se realiza el RIT cuando corresponde? → **nivel 1, adherencia**.
2. ¿Se ejecuta correctamente y es trazable? → **nivel 2, ejecución y trazabilidad**.
3. Cuando hay un hallazgo, ¿está bien redactado? → **nivel 3, evaluación automática de redacción 0–3**.
4. ¿El hallazgo sirve? → **nivel 4, pertinencia técnica** (pendiente de validación humana) y **nivel 5, efectividad** (solo lo que permiten los datos).

Reglas que no se rompen:
- **Sin puntaje único.** Cada indicador se muestra como % + n/N.
- **La redacción no es la pertinencia técnica.**
- **Un RIT sin hallazgo no es un mal RIT.**
- **Las cuentas compartidas son un problema de trazabilidad.** No se le atribuyen a ninguna persona.
- **No se inventan datos.** Lo no disponible se dice.
- El reporte es solo de **consulta**: no modifica SoftExpert ni el Excel.

Antes de redactar, lee `references/criterios_rit.md`: la ficha de instancia, el playbook, las definiciones, la pauta, las categorías y cómo comunicar.

## Flujo

1. **Datos**, todos en `data/` y fuera del repo porque contienen nombres y correos:
   - `data/RIT_*.xlsx`: exportación de la lista `InicioTurno_SE`. Se usa el más reciente.
   - `data/Top_usuarios*.html`: ranking del piloto (opcional).

   Configuración versionada:
   - `config/rotacion_turnos.csv` (D/N/DC/AD por turno)
   - `config/cuentas_compartidas.csv` (correos genéricos)
   - `config/rit.json` (metas, umbrales, feriados, semana de inicio)
   - `config/validacion_tecnica.csv` (validaciones de pertinencia; hoy vacío)
2. **Generar** (requiere `pip install -r requirements.txt`):
   ```
   python3 -m reporte.rit --planta "Nueva Aldea" [--semana 39] [--json] [--comentarios comentarios/rit.json]
   ```
   Se genera un solo HTML autónomo, `out/RIT_semanal_<planta>.html`, con todos los RIT evaluados. Los indicadores se calculan en el navegador, así que los filtros recalculan todo. Las semanas usan la numeración ISO. Abre en la última semana completa, salvo que se indique `--semana`. `--json` guarda los datos evaluados en `out/RIT_datos_<planta>.json`.
3. **Validar**:
   ```
   python3 pruebas/validar_rit.py out/RIT_semanal_<planta>.html
   ```
   Comprueba que los % coincidan con n/N, las sumas por semana, equipo y especialidad, el efecto de los filtros, que las cuentas compartidas queden fuera de los rankings, que un RIT sin hallazgo no caiga en "Requieren apoyo", la muestra reducida, que los ejemplos sean reales y que el drill-down coincida. Todo debe dar `OK`.
4. **Revisar con criterio** lo automático:
   - Lee hallazgos con nota 1 y 3: ¿un implementador sabría qué cambiar? Si una regla falla de forma sistemática, ajusta `pauta_redaccion` en `reporte/rit.py` y documenta el cambio.
   - En los equipos "sin hallazgos suficientes", mira las tareas revisadas antes de concluir nada.
   - Si alguien valida la pertinencia técnica, regístrala en `config/validacion_tecnica.csv`.
5. **Redactar** (opcional) `comentarios/rit.json`: `{"S39": {"Planta": {"lectura": "...", "focos": ["..."]}}}`. Aparece en el resumen y en el diagnóstico de esa semana.
6. **Entregar** el HTML y resumir en 3–5 líneas: qué ocurre, dónde, evidencia y acción.

## Estructura del HTML

- **Filtros**:
  - semana (◀ ▶) y período (semana o 4 semanas);
  - especialidad, área, equipo y turno;
  - persona, tarea, hallazgo, redacción, estado de la mejora y tipo de cuenta.

  La adherencia y las categorías solo aplican con filtros de equipo.
- **Secciones**, en orden:
  1. Resumen ejecutivo: 6 tarjetas (adherencia, trazabilidad, ejecución, redacción, pertinencia y efectividad), cada una con dato, n/N, comparación con las 4 semanas anteriores y estado.
  2. Diagnóstico: problema → dónde → evidencia → causa probable → acción sugerida.
  3. Tendencia de las últimas 4 semanas completas, con persistencia.
  4. Nivel 1: tabla Especialidad → Área → Equipo.
  5. Nivel 2: tabla de ejecución y trazabilidad, con el detalle de cuentas compartidas.
  6. Nivel 3: distribución de la redacción y tabla por equipo, más ejemplos buenos, para mejorar y deficientes, con su versión sugerida.
  7. Niveles 4–5: pertinencia y efectividad.
  8. Categorías de gestión por equipo (adherencia × hallazgos entendibles, con la alerta de trazabilidad).
  9. Personas: actividad, constancia, mejor redacción y requiere apoyo, más el Top 20 como referencia separada.
  10. Registros.
  11. Histórico S6–S40.
  12. Definiciones.
- **Detalle**:
  - RIT: fecha, turno según el calendario, cuenta, tarea, ejecución, cada hallazgo con su redacción, los elementos detectados, cómo mejorarlo y la pertinencia.
  - Persona: identificación, adherencia del equipo, trazabilidad, ejecución, redacción, ejemplos y alertas.
  - Equipo: lo mismo a nivel de equipo.

## Parámetros (`config/rit.json`)

- `metas`: la adherencia (90) es la meta de la planta; trazabilidad, ejecución y redacción accionable son referencias de trabajo.
- `categorias`: umbrales de adherencia alta (90) y calidad alta (60% entendibles), mínimo de hallazgos (3) y alerta de trazabilidad (50% de cuenta compartida).
- `muestra_minima`: 5.
- `inicio_general_semana`: `null` = automática (S26).
- `feriados` y `operacion_dias_por_dia` (solo fuera del calendario de turnos).

Cuando llegue la rotación de 2027, agrégala a `config/rotacion_turnos.csv`.
