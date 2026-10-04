# Diagnóstico RDP Nueva Aldea (ago-sep 2026): qué buscar en las RdP

Resumen de trabajo del *Diagnóstico de investigaciones RDP – Planta Nueva Aldea vs. resto del negocio* (emitido el 02-10-2026). Es la **línea base** del reporte diario: define qué problemas buscar, cómo medirlos y qué metas perseguir. Es una pauta de trabajo, no una evaluación oficial.

## 1. Pauta 0–3 por investigación

| Dimensión | 0 = no documentada | 1 = débil | 2 = adecuada con brechas | 3 = sólida |
|---|---|---|---|---|
| **Identificación** (título) | Nulo: "0", "no", "3h" | Categoría de catálogo ("Falla de equipos…") sin equipo | Fenómeno específico | Fenómeno + equipo, tag o línea |
| **Análisis causal** | Sin causa, o solo "desgaste", "diseño", "TBD", o escrita como tarea | Síntoma o estado del componente; causa hipotética | Al menos una causa que explica el mecanismo | Lo anterior + **un control que faltó o falló** (plan, estándar, diseño, criticidad, supervisión, coordinación) |
| **Acciones** | Sin acciones | Solo correctivas, revisiones o difusión | Al menos una preventiva o sistémica | Dos o más preventivas, o una **extendida a equipos similares** |

Se considera **análisis causal adecuado** un puntaje de 2 o más.

**Indicadores complementarios:**
- Causa sistémica documentada.
- Acción preventiva **vinculada a esa causa en la misma fila**.
- Mención de verificación o seguimiento.
- Extensión a equipos o líneas similares.
- **Cadena coherente**: título ≥2, causa ≥2, acciones ≥2 y vínculo causa sistémica → acción preventiva.

En el código, la pauta se calcula con reglas de texto (`pauta_evento` en `reporte/calidad.py`). Para corregir el puntaje de un evento revisado, agrégalo a `config/pauta_eventos.csv`.

## 2. Línea base (lectura manual del diagnóstico)

| Indicador | Nueva Aldea | Resto del negocio | Lectura |
|---|---|---|---|
| Título nulo | 10/36 (28%) | 80/262 (31%) | Problema transversal |
| Análisis causal adecuado (≥2) | 21/36 (58%) | 198/262 (76%) | **Brecha real de NA (p = 0,04)** |
| Puntaje causal medio | 1,67 | 1,88 | |
| Causa sistémica documentada | 5/36 (14%) | 56/262 (21%) | Bajo en todo el negocio |
| Causa escrita como tarea | 3/36 (8%) | 1/262 (0,4%) | Práctica propia de NA |
| Causa hipotética no confirmada | 5/36 (14%) | 14/262 (5%) | Se cierra sin confirmar la causa |
| Solo acciones correctivas o de revisión | 15/36 (42%) | 54/262 (21%) | **Brecha real de NA (p = 0,01)** |
| Mezcla de acciones (correctivas / preventivas) | 29% / 21% | 12% / 36% | NA repara más |
| Cadena coherente completa | 3/36 (8%) | 23/262 (9%) | Bajo en todo el negocio |
| Mención de verificación | 3/36 (8%) | 27/262 (10%) | No hay campo de eficacia |
| Acciones atrasadas sobre abiertas | 7/45 (16%) | 65/272 (24%) | **Fortaleza de NA** |
| Cerradas después del compromiso | 37/75 (49%) | 175/418 (42%) | Mediana de atraso: 2 días |
| Cerradas por su propio responsable | 69/75 (92%) | 385/418 (92%) | Sin control independiente |
| SAR = Sí | 20/36 (56%) | 154/262 (59%) | Aporte no registrado |
| Herramienta "Lluvia de ideas" / "5 porqués" | 72% / 11% | 38% / 52% | NA usa menos análisis estructurado |

Con las mismas reglas automáticas, la línea base de NA da: 26% de acciones sistémicas, 26% de títulos nulos, 8% de cierre por tercero, pauta causal media 1,62 y 49% de análisis causal adecuado. La regla automática es más estricta que la lectura manual en el análisis causal. Por eso **el reporte compara siempre contra la línea base calculada con la misma regla** y no contra estos valores manuales.

## 3. Metas (prioridades de gestión del diagnóstico)

| Plazo | Prioridad | Rol responsable | Cómo medirlo |
|---|---|---|---|
| 30 días | ACR único para las recurrencias del paño PU y la rastra 919; confirmar el ajuste del Uhlebox (2730) y adelantar las acciones de 10624 | Jefe de Máquina PM1, Jefe de Planta Térmica, Confiabilidad | Eventos repetidos en esos equipos; acciones de fondo ejecutadas a tiempo |
| 30 días | Estándar mínimo de registro: qué pasó, dónde, equipo/tag, desviación, consecuencia, horas perdidas; causa redactada como condición; campo "antecedentes revisados" | Coordinador de mejora continua y administrador corporativo del RDP | **Títulos nulos 28% → <5%**; causas como tarea 3 → 0 |
| 60 días | Revisión de calidad antes del cierre con la pauta 0–3; no cerrar sin causa sistémica o sin justificar por qué solo hay correctivas | Jefes de área como revisores | **Análisis causal adecuado 58% → ≥75%**; **solo correctivas 42% → ≤20%** |
| 90 días | Verificación de eficacia y cierre por un tercero en acciones de recurrencias y eventos críticos; registrar el aporte de SAR | Jefe de Confiabilidad y dueño del proceso RDP | 100% de las recurrencias con verificación definida; cierre por tercero; SAR con aporte registrado |

Las metas están en `config/linea_base.json` y fijan el **verde** del semáforo.

## 4. Patrones a buscar en cada RdP

Estos patrones vienen de la lectura del diagnóstico, con ejemplos reales:

1. **Causa = estado del componente**: "Desgaste" (11698), "Falla rodamiento" (9526), "Rotura de Sprocket" (12746), "Soltura Modulos" (11735). Se repara el síntoma.
2. **Causa escrita como tarea**: "Corroborar buen funcionamiento de ventosas…" (12737), "Investigación" / "Cambio" (10623), "Mediciones para identificar causa raíz" (10613).
3. **Causa hipotética que se cierra sin confirmar**: "Posible Falla VDF" (10613), "hipótesis mayor carga extremos" (10629).
4. **Herramienta declarada que no se refleja en el registro**: las RdP que declaran "Árbol de eventos/fallas" tienen el puntaje causal más bajo (1,50), porque el árbol no queda en el registro y la causa final es de 1 o 2 palabras. *Hipótesis: se elige la herramienta, pero no se completa la cadena.*
5. **Error humano**: la buena práctica es preguntar qué condición lo permitió. 9606 analizó por qué se subestimó el trabajo y cambió la revisión del programa semanal en el inicio de turno. La mala práctica es quedarse en la conducta: 10657, "Desconocimiento detalle técnico" → "no cambiar polín trabado", sin abordar por qué faltaba el conocimiento.
6. **Difusión sin cambio esperado**: "Difundir al turno… pasos a seguir en caso de que la falla vuelva a ocurrir" (10613) no dice qué conducta o condición cambia.
7. **Dependencia del proveedor**: investigaciones que terminan en "reunión con Andritz" o "revisar con Andritz" sin causa propia del modo de falla (Madera: 11735, 12746, 11695). *[P] Puede estar retrasando la solución.*
8. **Revisión cerrada sin resultado**: 2731, "revisar con proveedor el desgaste acelerado", se cerró sin resultado y el paño volvió a fallar. Cerrar una acción "revisar" sin resultado no reduce el riesgo.
9. **Acción de fondo que llega tarde**: la acción que ataca el mecanismo (2730, Uhlebox) espera una P/A **sin control interino**, y el evento se repite mientras tanto. Lo mismo pasa con las acciones preventivas de 10624, que vencen después de que ocurrió 12744.
10. **Acción cerrada después del nuevo evento**: 11439, "habilitar sensor de posición", se cerró el 2-sep, después del evento 9568.
11. **Planes de una sola acción** y **RdP en creación sin acciones** (11677, 12750).
12. **Posibles duplicados**: 11677 (9-sep, sin acciones) podría duplicar 11671 (8-sep).

**Buenas prácticas para reconocer**, que van en las fortalezas:
- 9600: punto de no retorno e hitograma del puente grúa.
- 10624: detección tardía, falta de supervisión y comunicación con la EESS.
- 11710: estrategia para válvulas de seguridad fuera del DS, con levantamiento del área 555.
- 11729: procedimiento de cierre mensual.
- 9606: va más allá del error humano.
- 12744: procedimiento de régimen severo con gatillos de carga y corriente.
- 11676: límites operacionales de los X-Filters.

## 5. Recurrencias: cómo clasificarlas

- **Confirmada**: mismo equipo y modo de falla, con acciones previas cerradas sin eficacia o con la acción de fondo pendiente. Ejemplo: paño PU de la 2ª prensa (2230 → 11671, 11677, 11702).
- **Probable**: mismo sistema y modo parecido; falta validar el tag. Ejemplo: rastra 919 (2222 → 10624, 12744); validar si 431-26-919 y 431-31-919 son el mismo equipo.
- **Posible**: mismo sistema y modo distinto, o coincidencia parcial. Ejemplos: compuertas del astillador (4335 → 9568); transportadores de entrada (2227, 6413 → 11735, 12746); Rotabarker (1071, 4343 → 9569); dregs y X-Filters (2226 → 9594, 11676, 12756).
- Los títulos parecidos no siempre son eventos equivalentes. Por ejemplo, el corte de hoja en el secador de otras plantas no es el corte por paño de NA.

Solo 2 de 76 registros de NA mencionan un antecedente: **el registro no obliga a buscarlos**. Por eso el reporte los busca solo. Los casos activos están en `config/casos_seguimiento.json`.

## 6. Aprendizaje entre plantas (antecedentes útiles)

- Corteza y nitens: Arauco L3 1103 (plan de componentes abrasivos del Rotabarker para todas las líneas) y Valdivia 8465 (geometría del chute, detección de obstrucción, rutina con criterio de aceptación).
- Horno de cal / VDF: Esperanza 4373.
- Lecho mixto: Arauco L2 9513 (la inspección no revisaba el mesh de los insertos).
- Causas que nombran el control con criterio verificable: Valdivia 8465 y 8490. Punto de control de efectividad en la pauta de trabajo: Valdivia 2120.
- NA también es referencia: Arauco L2 1063 la visitó por transportadores y Valdivia 11706 pidió benchmarking del sello de la bomba de bisulfito.

## 7. SAR

No hay ningún aporte documentado en ninguna planta. En NA, las RdP con SAR tienen algo más de acciones preventivas, pero peor análisis causal (10/20 vs 11/16), sin significancia estadística. El uso no es aleatorio, porque depende del líder y del NAT. **No se le atribuye calidad**: se pide registrar qué propuso SAR y qué se aceptó.

## 8. Limitaciones que siempre se declaran

- No hay descripción, consecuencia ni horas perdidas, y en muchos casos el título es nulo.
- "Fecha Inicio" no siempre es la fecha del evento.
- "Tipo causa raíz" está mal asignado; no se usa.
- Lo que no está en la base puede estar en un ACR, un aviso SAP o un acta.
- Con muestras de este tamaño, diferencias menores a ~15 puntos pueden ser azar.
