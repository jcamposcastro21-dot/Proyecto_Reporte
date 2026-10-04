# Playbook MGO (v03, oct-2025): conceptos que aplican a la calidad de RdP

Resumen de trabajo para redactar y evaluar el reporte. Fuente: *Playbook MGO — Hacia una operación más estable y eficiente*, ARAUCO, octubre 2025. Las confirmaciones de Trabajo Bien Hecho (TBH) **no** están en el alcance del reporte; aquí no se resumen.

## 1. Dónde está la RdP dentro del MGO

El MGO tiene un ciclo de 4 etapas: **Planificación** (procesos, riesgos, controles) → **Ejecución** (gestión documental, competencias) → **Verificación** → **Aprendizaje** (resolución de problemas y gestión del cambio).

La RdP es la etapa de aprendizaje: *"Si tenemos un problema, lo resolvemos y mejoramos los estándares"*. Una RdP de calidad cierra el ciclo y vuelve a la planificación: cambia el mapa de procesos, la matriz de riesgos o un documento operativo.

Objetivos del MGO: **estabilidad** (continuidad operacional, procesos estables, operación segura) y **eficiencia**. Principios: simplicidad, integración, transformación digital y **adherencia**, es decir, disciplina en cumplir los principios del modelo.

## 2. Para qué sirve una RdP

Es un proceso estructurado para identificar las causas de las desviaciones y definir un plan que las corrija o **prevenga su recurrencia**. Según el playbook, conduce a:
1. **Prevenir la recurrencia**: identificar la causa minimiza la repetición.
2. **Promover el aprendizaje**: compartir lecciones entre áreas y plantas.
3. **Fortalecer la cultura**: mejora continua y decisiones basadas en hechos.

Herramientas: 5 porqués, Ishikawa (espina de pescado), árbol de falla, ICAM y "malos actores" de confiabilidad.

## 3. Por qué importan los eventos menores

Hoy la RdP se concentra en las categorías 3, 4 y 5, que son cerca del 20% de los eventos y explican el 80% de las pérdidas. El MGO propone **fortalecer el análisis de las categorías 1 y 2** para evitar que escalen a eventos de mayor gravedad. Por eso el reporte diario exige calidad también en eventos chicos.

## 4. Categoría del evento (5 ámbitos; manda el ámbito de mayor categoría)

| Cat. | Producción celulosa (h equivalentes en digestor) | Costos fuera de presupuesto | Seguridad y salud ocupacional |
|---|---|---|---|
| 1 | Sin pérdida en digestor, pero con pérdida o baja de ritmo en otra área (< 0,5 h fuera de estándar) | < 50 mil USD | Accidente sin tiempo perdido (STP) |
| 2 | 1 a 8 h | 50 a 100 mil USD | Accidente con tiempo perdido (CTP) |
| 3 | 8 a 24 h | 100 a 500 mil USD | Incapacidad permanente / accidente grave |
| 4 | 25 a 50 h | 500 mil a 1 M USD | Fatalidad o incapacidad total |
| 5 | ≥ 50 h | > 1 M USD | Múltiples fatalidades |

Los ámbitos restantes son medio ambiente, comunidades, legal y reputación, y calidad. **La base RDP actual no registra la categoría ni las horas perdidas**: no inventarla. Si el título o la causa permiten inferirla, decir "probable categoría X, a confirmar".

## 5. Herramienta y plazo según la categoría

| Cat. | Registro / reporte | Herramienta de análisis | Plazo |
|---|---|---|---|
| 5 | Herramienta RdP + Reporte Flash | ICAM | En el turno / 30 días |
| 4 | Herramienta RdP + plataforma de pérdidas + Reporte Flash | Árbol de falla / ICAM | En el turno / 30 días |
| 3 | Herramienta RdP + plataforma de pérdidas + Reporte Flash | 5 porqués / Ishikawa / árbol de falla | En el turno / 5 días |
| 1-2 | Herramienta RdP | Si la causa es **desconocida o repetitiva**, hacer un análisis (5 porqués, árbol, Ishikawa, malos actores); si ya se conoce, pasar a definir la solución | Registro en el turno; RdP **1 vez por semana** |

Regla para el reporte: un evento con **posible recurrencia** analizado solo con "Lluvia de ideas" no cumple el playbook.

## 6. Ciclo RdP para eventos de categoría 1 y 2 (6 pasos)

| Paso | Qué | Responsable | Plazo |
|---|---|---|---|
| 1. Registro del desvío | Fecha y hora, **equipo**, **descripción**, impacto, foto opcional y **causa raíz preliminar** | Operador | Durante el turno |
| 2. Identificar eventos relevantes | Pareto / diagrama jack-knife de los más frecuentes | Ing. operaciones | Antes de la reunión RdP |
| 3. Definir solución | Definir el problema. Si la causa es desconocida o repetitiva, asignar análisis | Supervisores, Ing. ops/mtto | Reunión RdP |
| 4. Plan de acción | Acciones correctivas, roles, hitos y plazos; seguimiento en la reunión RdP | Ing. ops/mtto | Reunión RdP |
| 5. Seguimiento y validación | Una vez cumplido el plan, **validar que la solución se sostiene en el tiempo** | Ing. ops/mtto | Reunión RdP |
| 6. Asegurar aprendizaje | Compartir aprendizajes y **modificar estándares** si aplica | Supervisores, Ing. ops/mtto | Reunión RdP y mesa de trabajo del área |

Lectura para el reporte:
- Paso 1: un título nulo ("0", "no", "3h") o de catálogo incumple el registro, porque no identifica el equipo ni el fenómeno.
- Paso 5: "cerrada" no significa "eficaz". Un cierre sin verificación, hecho por el mismo responsable o en una acción de revisión sin resultado registrado, no valida la solución.
- Paso 6: una RdP sin acciones que cambien un estándar no deja aprendizaje.

## 7. Plan de acción: qué es una buena acción

- Debe **eliminar la causa raíz** y evitar la recurrencia, con **impacto directo sobre la causa**.
- Las soluciones se evalúan con el criterio **SMART**: específica, medible, alcanzable, realista y con plazo.
- Cada acción tiene un responsable y un plazo asignados en la instancia, y se **valida con el responsable designado**.
- Las acciones se registran y se comunican a los interesados.

## 8. Jerarquía de controles (para proponer medidas)

Primero van los **controles de ingeniería**, o barreras duras: medidas físicas o tecnológicas.
1. **Eliminar** la fuente del riesgo.
2. **Sustituir** el proceso, material o actividad.
3. **Control de ingeniería**: *rediseñar* el equipo o sistema, o *separar* con barreras físicas.

Después vienen los **controles administrativos y el EPP**, o barreras blandas:
4. **Administrar**: procedimientos, formación, inspecciones y monitoreo regulares.
5. **EPP**.

Los riesgos altos deben mitigarse con **barreras duras** siempre que se pueda. En el reporte, una medida propuesta debe subir en esta jerarquía cuando el evento se repite.

Magnitud del riesgo = probabilidad (1-5) × consecuencia (1-5), lo que da bajo, medio o alto. En SSO, las consecuencias 4 y 5 son siempre riesgo alto.

## 9. Del aprendizaje a la actualización de estándares

Las RdP son una de las tres fuentes para actualizar los elementos del MGO. Las nuevas medidas de mitigación pueden exigir ajustes en:
- el **mapa de procesos** (macroproceso → proceso → subproceso → actividad → tarea);
- la **matriz de riesgos** (riesgos y controles que no estaban);
- los **documentos operativos**: procedimiento (qué y para qué), **HTE** (hoja de trabajo estándar: el cómo, paso a paso), **SOP** (árbol de decisión en sala de control) y **checklists o pautas de inspección** (registro y trazabilidad).

En el reporte, una acción sistémica bien escrita nombra **qué documento, plan, lógica o diseño cambia**.

## 10. Roles frente a la RdP

| Rol | Responsabilidad en RdP |
|---|---|
| Gerentes y subgerentes | Promover una cultura de aprendizaje. **Verificar la calidad del análisis de causa raíz.** Facilitar el aprendizaje entre plantas. Desafiar a los equipos a buscar nuevas soluciones. |
| Superintendente de área | **Asegurar la adherencia a las sesiones de RdP.** Proponer nuevas medidas de control y **evaluar la efectividad de los controles**. Asegurar la implementación de las mitigaciones. |
| Supervisor del proceso (ingeniero y/o jefe de área) | **Liderar las sesiones de RdP** y reunir la información para buscar la causa raíz. Proponer soluciones ante desvíos de KPIs. Ayudar a actualizar el mapa de procesos. |
| Operador y técnico | Participar en el análisis de RdP y registrar el desvío durante el turno. |

## 11. KPIs de gestión del MGO relacionados con RdP

- Cumplimiento de las acciones correctivas de RdP (%).
- Cantidad de RdP (#).
- ACR y acciones atrasadas.

Lineamientos para los KPIs:
1. Reflejan estabilidad y eficiencia.
2. Son **gestionables por el área responsable**.
3. Tienen jerarquía.
4. Usan un **cálculo estandarizado**.
5. Usan **criterios unificados**, sin interpretaciones ambiguas.

Por eso el reporte define cada indicador con su fórmula, igual para todas las NAT.

## 12. Sistemas

- **SAR**: identifica y resuelve problemas con multiagentes de inteligencia artificial. El MGO busca impulsar su uso.
- **Plataforma de pérdidas y ACR**: registro de eventos de categoría 3 o mayor.
- **Qliksense**: visualización de indicadores (de aquí vienen los QVD).
- **SoftExpert**: procesos, riesgos y documentos.
- **SAP**: gestión de activos (avisos y OT).

La base no registra qué aportó SAR. Informar el uso de SAR, pero no atribuirle calidad.
