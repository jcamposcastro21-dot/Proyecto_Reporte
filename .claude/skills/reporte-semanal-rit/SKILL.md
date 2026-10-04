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
   python3 -m reporte.rit --planta "Nueva Aldea" --semana 39 --json
   ```
   Se genera **un solo HTML** (`out/RIT_semanal_<planta>.html`) con **todas las semanas**, desde la primera con registros hasta la última de la base. Las semanas usan la numeración ISO, de lunes a domingo (la semana 39 de 2026 va del 21 al 27 de septiembre). La última semana se marca "parcial" si la base no llega al domingo.
   - `--semana` define la semana que se abre por defecto. Acepta el número ISO o cualquier fecha; si se omite, abre la última semana completa.
   - `--json` genera `out/RIT_semanal_<planta>_S<n>.json` con el detalle de esa semana y la evolución semanal de la planta y de cada área.

   Los números salen siempre del script. Todas las semanas se calculan con las mismas reglas: cada equipo entra al cálculo de adherencia desde su primera semana con registro y sigue contando después, aunque deje de registrar.
3. **Revisar con criterio:**
   - **Pauta de hallazgos**: la nota es automática, por reglas de texto. Lee los hallazgos con nota 1 y 3 de la semana y confirma que el criterio se sostiene: "¿un implementador sabría qué cambiar?". Si una regla se equivoca de forma sistemática, ajústala en `pauta_hallazgo` de `reporte/rit.py` y documenta el cambio en `references/criterios_rit.md`.
   - **Equipos "registran sin encontrar nada"**: no es malo por sí solo, pero si dura varias semanas sugiere un registro por cumplir. Míralo junto con las tareas revisadas: ¿siempre la misma tarea? ¿Tareas rutinarias de bajo riesgo?
   - **Cuentas compartidas** ("Operador …"): impiden saber quién redacta. Repórtalo como brecha de práctica, no como problema de una persona.
4. **Redactar** `comentarios/rit.json`, con una clave por semana: `{"S39": {"Planta": {...}, "Efluentes": {...}}}`. Dentro de cada semana, las claves son `"Planta"` o el nombre exacto del área, y cada una acepta `lectura` (2–3 líneas) y `focos` (máximo 4). Al redactar, usa la vista de evolución para decir si un cambio es tendencia o una semana aislada. Sigue las reglas de comunicación de la referencia.
5. **Regenerar** con `--comentarios comentarios/rit.json`, entregar el HTML y resumir en el chat, en 3–5 líneas, qué equipos y personas necesitan apoyo y quiénes son referentes.

## Qué incluye el HTML

Hay dos selectores: **Semana** (con ◀ ▶ para avanzar o retroceder, más la opción "📈 Evolución global") y **Área** (planta completa o cada área).

**Vista de una semana**:
1. La semana en números, con la variación respecto de la semana anterior.
2. Foco de la semana.
3. Cuadrantes adherencia × claridad por equipo, en las 4 semanas que terminan en la seleccionada: referentes; constantes pero poco claros; claros pero sin constancia; registran sin encontrar nada; requieren apoyo.
4. Tabla por área, especialidad y equipo, con la tendencia de adherencia de 8 semanas. En la vista planta llega hasta especialidad; en la de área, hasta cada equipo.
5. Personas en 4 semanas: referentes y quienes requieren acompañamiento.
6. Ejemplos de la semana.
7. Top 20 piloto SoftExpert (solo en la vista planta).

**Evolución global**, para la planta o el área seleccionada:
- Tarjetas de la última semana completa contra el promedio de las 4 anteriores, y la mejor semana.
- Una línea por KPI: adherencia, hallazgos claros, registros con hallazgo, registro oportuno y tarea SE. Todas usan escala 0–100% y llevan la meta punteada. Los puntos huecos son semanas con menos de 20 registros.
- Mapa de calor semana × área / especialidad / equipo, uno para adherencia y otro para hallazgos claros.
- Tabla semanal con todos los KPI.

Al hacer clic en una semana (punto, columna o fila), se abre esa semana. Al hacer clic en un equipo, una persona o un ejemplo, se abren sus levantamientos de las 4 semanas de la semana elegida (en la vista de evolución, de todo el período). Al hacer clic en un levantamiento, se abre su detalle con la nota de cada hallazgo y "cómo mejorarlo".

## Parámetros

Están en `config/rit.json`:
- días esperados de Operación (`operacion_dias_por_dia`, hoy 0,4: 5 turnos, 2 por día);
- feriados;
- umbrales `[verde, ámbar]` de adherencia, registro oportuno, tarea SE y claridad;
- mínimo de hallazgos para evaluar a una persona.

Si el usuario entrega el calendario real de turnos, reemplaza la aproximación de 0,4.
