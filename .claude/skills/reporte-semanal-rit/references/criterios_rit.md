# Criterios para evaluar los levantamientos RIT

## 1. Qué es el RIT y qué se espera de él

**Ficha de instancia "Inicio de turno Mantención"**, entregada por el usuario:

- **Participantes**: lo lidera el jefe de especialidad; son obligatorios el líder técnico (si aplica) y los técnicos; son opcionales el SI y las empresas de servicio.
- **Propósito**: asegurar que el equipo inicie el turno alineado, con tareas claras y riesgos controlados, para una ejecución segura y eficiente.
- **Preparación**: programa semanal; riesgos y medidas de control de las tareas del día (SoftExpert y App Gestión de Riesgos).
- **Agenda (5 × 5 min)**:
  1. SSO, MA, paso 3 (si aplica) y novedades.
  2. Novedades y condiciones del área.
  3. Distribución de trabajos.
  4. **Riesgos: seleccionar una tarea a revisar en SoftExpert, analizar sus riesgos y controles en todos los ámbitos de riesgo, identificar posibles ajustes necesarios en SE y registrar.**
  5. Revisión de compromisos y cierre.
- **Producto**: equipo alineado; compromisos claros; **registro del análisis de riesgo en SoftExpert, identificando actualización de documentos, cambios en riesgos y/o cambios en procesos**.

**Playbook MGO** (inicio de turno de Operaciones, 20 minutos):
- Etapas: revisión del turno anterior, revisión de tareas, distribución operativa, priorizar la tarea crítica (repasar riesgos y controles) y análisis de contingencias.
- "Los riesgos se revisarán en el día a día durante el inicio de turno".
- Los levantamientos alimentan la actualización de la **matriz de riesgos** y de los **documentos operativos** (procedimiento, HTE, SOP, checklist).
- Barreras al uso de documentos: desactualizado, no refleja la realidad, no se conoce, no está disponible.
- KPIs relacionados: riesgos latentes, controles implementados para riesgos medios y altos, y documentos actualizados.

## 2. Estructura de la base (lista `InicioTurno_SE`)

Cada fila es una tarea revisada en un RIT:
- Contexto: Área, Especialidad (Operación / Mantención), Equipo (Turno A–E, con L1/L2 en Fibra; Mecánico / Electrocontrol), Fecha (del RIT), Creado (registro) y Tarea (de SoftExpert).
- Lo que se encontró:
  - `FaltaRiesgo` + `RiesgoTexto`
  - `FaltaControl` + `ControlTexto`
  - `FaltaTarea` + `NuevaTarea`
  - `Título` (observación)
- Seguimiento: `EstadoMejora` (Abierta / Cerrada / No Aplica), `ComentarioCierre`, LiderEquipo, Implementador, Ingeniero, Creado por.

"No Aplica" significa que se revisó la tarea y no se encontró nada que mejorar: cuenta para la adherencia, no para la calidad. Las cuentas "Operador …" son compartidas por turno.

## 3. Pilar 1: Adherencia a la práctica (¿se hace y se registra?)

| Indicador | Fórmula | Verde / ámbar |
|---|---|---|
| Adherencia | días con RIT registrado / días esperados (tope 100%) | ≥90 / ≥70 |
| Registro oportuno | registros cargados entre 0 y 12 h después de la hora del RIT | ≥90 / ≥75 |
| Tarea SE seleccionada | registros con una tarea de SoftExpert (no "Notificar sin SE", "Agregar tarea en SE", "Parada de área/PGP") | ≥95 / ≥85 |

Días esperados:
- **Mantención**: días hábiles, de lunes a viernes, sin feriados.
- **Operación**: 0,4 × días de la semana por turno (5 turnos, 2 por día), es decir, unos 2,8 días por semana. Es una aproximación: con el calendario real de turnos se puede reemplazar.

Señales de propósito, no de cumplimiento:
- **Registran sin encontrar nada**: buena adherencia, pero 0 hallazgos en 4 semanas. Puede ser una revisión real de tareas bien documentadas o un registro por cumplir. Se valida acompañando un RIT.
- **Cuentas compartidas**: no permiten saber quién analizó ni quién redactó.

## 4. Pilar 2: Calidad de los hallazgos (¿se entiende qué se pide?)

La pregunta es: **¿el implementador de SoftExpert sabría qué cambiar sin preguntar?** Cada hallazgo marcado "Sí" (riesgo, control o tarea) recibe una nota:

| Nota | Criterio | Ejemplos reales |
|---|---|---|
| 0 | Sin contenido: marca "Sí" pero no escribe nada | (vacío), "s/o" |
| 1 | No se entiende qué hacer: solo el ámbito, genérico, o **lista pegada** de SoftExpert sin acción | "Controles SSO", "Faltan controles", "SSO Y PRODUCCION", "TODAS LAS MEDIDAS", "Similar a plataforma licor", "incluir check list", "CO-ADM-3360 FTSSO-TA-02 … CO-ADM-3361 …" |
| 2 | Identifica el elemento, pero no dice qué hacer con él | "CO-ADM-4199", "Falta riesgos. Exposición radiación solar, condiciones climáticas adversas" |
| 3 | Claro y accionable: **acción + elemento específico**, idealmente con el motivo | "Eliminar: CO-ING-4051 Indicación de presión en terreno", "Falta agregar HTE de actividades específicas de quemadores", "Incluir como control para el riesgo 'Omisión de hallazgos…' la rutina de inspección de operador terreno por área" |

- Un registro con varios hallazgos toma la **nota más baja**: basta una parte incomprensible para que el implementador tenga que preguntar.
- Un **hallazgo claro** tiene nota ≥2.

Formato sugerido para enseñar: **[Agregar / Eliminar / Modificar] + [riesgo, control o documento exacto: código y nombre] + [en la tarea …] + [porque …]**.

Reglas automáticas (`pauta_hallazgo` en `reporte/rit.py`):
- **Acción**: verbos agregar, eliminar, quitar, incorporar, incluir, crear, modificar, actualizar, especificar, corregir, etc., o expresiones como "falta…", "se debe…", "se requiere…", "no aplica", "no corresponde", "duplicado", "repetido".
- **Especificidad**: un código de SoftExpert (CO-ADM-…, SSO-…, FTSSO-…, código de tarea), o al menos 2 palabras de contenido con acción (3 sin acción), excluyendo el vocabulario genérico (SSO, MA, PRO, control, riesgo, falta, HTE, procedimiento…).
- **Lista pegada**: 3 o más códigos sin ninguna acción.

## 5. Cuadrantes (equipos, últimas 4 semanas)

| Cuadrante | Condición | Qué hacer |
|---|---|---|
| Referentes | adherencia ≥90% y hallazgos claros ≥70% | Reconocer y usar como ejemplo |
| Constantes, pero no se entiende lo que piden | adherencia ≥90%, claridad <70% | Apoyar la redacción con el formato y ejemplos |
| Claros, pero sin constancia | adherencia <90%, claridad ≥70% | Reforzar la disciplina con el jefe de especialidad o de turno |
| Registran sin encontrar nada | adherencia ≥70%, 0 hallazgos | Acompañar un RIT y verificar que se abre la tarea y se revisan todos los ámbitos |
| Requieren apoyo | adherencia baja y hallazgos poco claros o inexistentes | Acompañamiento directo del líder |

Personas: referentes si tienen 3 o más hallazgos y ≥70% claros; requieren acompañamiento si tienen 3 o más hallazgos y <50% claros.

## 6. Top 20 piloto SoftExpert

Es un reporte externo que rankea a los usuarios más idóneos para el piloto de la nueva plataforma. Pondera cantidad, frecuencia y calidad de redacción, con balance Operación/Mantención. El reporte RIT lo cruza para ver **si la calidad de esas personas se sostiene** con la pauta RIT en las últimas 4 semanas. Lecturas posibles: "se sostiene", "claridad media", "bajó la claridad", "activo, sin hallazgos" o "sin actividad".

## 7. Cómo comunicar

- **Separar siempre** "hacer el RIT" de "informar bien un hallazgo". Un equipo puede ser excelente en lo primero y débil en lo segundo.
- **Reconocer con nombre** a los referentes, con su mejor ejemplo textual. Para quienes requieren apoyo, hablar de acompañamiento y mostrar el formato correcto con un ejemplo de su propia área. No es un ranking de culpables.
- **Dirigir cada foco a quien puede actuar:**
  - el jefe de especialidad (Mantención) o el jefe de turno (Operación): adherencia y calidad del análisis en su RIT;
  - el ingeniero o implementador de SoftExpert: listas pegadas y pedidos genéricos que no puede implementar.
- Cita los equipos con área y nombre (por ejemplo, "Efluentes · Turno C") y los levantamientos por ID.
- Con pocos registros por equipo, como los turnos de Operación (unos 3 por semana), no saques conclusiones de una sola semana: usa los cuadrantes de 4 semanas y la tendencia de 8.
- No mencionar confirmaciones TBH. No evaluar el cierre de las mejoras.
