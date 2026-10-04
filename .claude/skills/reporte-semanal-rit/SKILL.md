---
name: reporte-semanal-rit
description: Genera la evaluación semanal de la calidad de los levantamientos de las Reuniones de Inicio de Turno (RIT) registrados en SoftExpert, por área, especialidad, equipo y persona, para una planta del Negocio Celulosa. Separa la adherencia a la práctica (hacer y registrar el RIT) de la calidad de los hallazgos informados (si se entiende qué riesgo, control o tarea cambiar), e identifica equipos y personas referentes y los que requieren apoyo, cruzando con el Top 20 de usuarios SoftExpert. Úsala cuando el usuario pida el reporte RIT, la evaluación de inicios de turno, la calidad de levantamientos en SoftExpert o quién necesita apoyo en el RIT.
---

# Reporte semanal de calidad de levantamientos RIT

El objetivo es responder cada semana si **se hace el RIT** y si **lo que se levanta sirve**, es decir, si un implementador entiende qué cambiar en SoftExpert sin tener que preguntar. Son dos preguntas distintas y no se mezclan: una cosa es la adherencia a la práctica y otra es informar hallazgos. **El cierre de las mejoras no se evalúa.**

Antes de redactar, lee `references/criterios_rit.md`. Contiene:
- la ficha de instancia del RIT de Mantención;
- lo que dice el playbook;
- la pauta 0–3 de hallazgos;
- los cuadrantes;
- cómo comunicar los resultados.

## Flujo

1. **Datos**, ambos en `data/` y fuera del repo porque contienen nombres y correos:
   - `data/RIT_*.xlsx`: exportación de la lista `InicioTurno_SE` de SoftExpert. Se usa el más reciente.
   - `data/Top_usuarios*.html`: reporte Top 20 de usuarios SoftExpert por planta. Es opcional.

   Si faltan, pídelos al usuario.
2. **Generar** (requiere `pip install -r requirements.txt`):
   ```
   python3 -m reporte.rit --planta "Nueva Aldea" --semana AAAA-MM-DD --json
   ```
   `--semana` acepta cualquier día de la semana a evaluar, de lunes a domingo. Sin ese parámetro, usa la última semana completa. Produce:
   - `out/RIT_semanal_<planta>_<lunes>.html`
   - `.json` con los indicadores de la planta y de la semana anterior, cada equipo, los cuadrantes, las personas en 4 semanas, los hallazgos de la semana con su pauta y los focos automáticos.

   Los números salen siempre del script.
3. **Revisar con criterio:**
   - **Pauta de hallazgos**: la nota es automática, por reglas de texto. Lee los hallazgos con nota 1 y 3 de la semana y confirma que el criterio se sostiene: "¿un implementador sabría qué cambiar?". Si una regla se equivoca de forma sistemática, ajústala en `pauta_hallazgo` de `reporte/rit.py` y documenta el cambio en `references/criterios_rit.md`.
   - **Equipos "registran sin encontrar nada"**: no es malo por sí solo, pero si dura varias semanas sugiere un registro por cumplir. Míralo junto con las tareas revisadas: ¿siempre la misma tarea? ¿Tareas rutinarias de bajo riesgo?
   - **Cuentas compartidas** ("Operador …"): impiden saber quién redacta. Repórtalo como brecha de práctica, no como problema de una persona.
4. **Redactar** `comentarios/rit_<lunes>.json`. Las claves son `"Planta"` o el nombre exacto del área, y cada una acepta `lectura` (2–3 líneas) y `focos` (máximo 4). Sigue las reglas de comunicación de la referencia.
5. **Regenerar** con `--comentarios comentarios/rit_<lunes>.json`, entregar el HTML y resumir en el chat, en 3–5 líneas, qué equipos y personas necesitan apoyo y quiénes son referentes.

## Qué incluye el HTML

Tiene un selector **Planta completa / cada área**. Cada vista incluye:
1. La semana en números, con la variación respecto de la semana anterior.
2. Foco de la semana.
3. Cuadrantes adherencia × claridad por equipo en 4 semanas: referentes; constantes pero poco claros; claros pero sin constancia; registran sin encontrar nada; requieren apoyo.
4. Tabla por área, especialidad y equipo, con adherencia, registro oportuno, tarea de SoftExpert seleccionada, hallazgos, hallazgos claros, listas pegadas y la tendencia de adherencia en 8 semanas. En la vista planta llega hasta especialidad; en la vista de área, hasta cada equipo.
5. Personas en 4 semanas: referentes y quienes requieren acompañamiento en la redacción, con un ejemplo textual de cada una.
6. Ejemplos de la semana: los que se entienden (pauta 3) y los que no (pauta 0–1), con el formato sugerido.
7. Top 20 piloto SoftExpert: si la calidad de cada persona se sostiene con la pauta RIT (solo en la vista planta).

**Clic** en un equipo, una persona o un ejemplo: abre sus levantamientos de las 4 semanas. **Clic** en un levantamiento: abre el detalle completo con la nota de cada hallazgo y "cómo mejorarlo".

## Parámetros

Están en `config/rit.json`:
- días esperados de Operación (`operacion_dias_por_dia`, hoy 0,4: 5 turnos, 2 por día);
- feriados;
- umbrales `[verde, ámbar]` de adherencia, registro oportuno, tarea SE y claridad;
- mínimo de hallazgos para evaluar a una persona.

Si el usuario entrega el calendario real de turnos, reemplaza la aproximación de 0,4.
