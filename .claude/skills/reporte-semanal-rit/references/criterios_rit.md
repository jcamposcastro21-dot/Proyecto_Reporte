# Criterios para evaluar los levantamientos RIT

## 1. Qué es el RIT y qué se espera de él

**Ficha de instancia "Inicio de turno Mantención"**, entregada por el usuario:
- **Líder**: jefe de especialidad. **Obligatorios**: líder técnico (si aplica) y técnicos. **Opcionales**: SI y empresas de servicio.
- **Propósito**: que el equipo inicie el turno alineado, con tareas claras y riesgos controlados.
- **Agenda (5 × 5 min)**:
  1. SSO, MA y novedades.
  2. Condiciones del área.
  3. Distribución de trabajos.
  4. **Riesgos: seleccionar una tarea en SoftExpert, analizar sus riesgos y controles en todos los ámbitos, identificar ajustes en SE y registrar.**
  5. Compromisos y cierre.
- **Producto**: registro del análisis de riesgo en SoftExpert, con la actualización de documentos, riesgos o procesos que corresponda.

**Playbook MGO**: los riesgos se revisan en el día a día durante el inicio de turno. Los levantamientos alimentan la matriz de riesgos y los documentos operativos (procedimiento, HTE, SOP, checklist).

## 2. Datos (lista `InicioTurno_SE`)

Cada fila es un RIT, es decir, una tarea revisada:
- Contexto: Área, Especialidad, Equipo, Fecha (del RIT), Creado (registro), Creado por, Tarea.
- Hallazgos: `FaltaRiesgo`/`RiesgoTexto`, `FaltaControl`/`ControlTexto`, `FaltaTarea`/`NuevaTarea`, `Título` (observación).
- Seguimiento: `EstadoMejora`, `ComentarioCierre`, Implementador, Ingeniero, LiderEquipo.

Configuración:
- `config/rotacion_turnos.csv`: abril a diciembre de 2026.
- `config/cuentas_compartidas.csv`: correos genéricos ce05.* del listado PCNA.
- `config/validacion_tecnica.csv`: validaciones de pertinencia.

## 3. Los cinco niveles (no se combinan en un puntaje único)

| Nivel | Pregunta | Indicador | Cálculo |
|---|---|---|---|
| 1 | ¿Se realiza cuando corresponde? | **Adherencia** | Días con RIT en un día exigido / días exigidos, por equipo y semana, con tope por equipo-semana. Meta 90% |
| 2 | ¿Es trazable? | **Trazabilidad individual** | RIT con cuenta personal / RIT. Compartida = cuenta genérica de turno o puesto |
| 2 | ¿Quedó bien registrado? | **Registro completo** | Tarea SE seleccionada + formulario completo + registrado ≤12 h. Los componentes se muestran por separado |
| 3 | ¿El hallazgo se entiende? | **Redacción 0–3** (automática) | Entendibles = ≥2; claros y accionables = 3. El RIT toma la nota más baja de sus ítems |
| 4 | ¿Lo propuesto corresponde? | **Pertinencia técnica** | Solo con validación registrada; si no, "Pendiente de validación técnica" |
| 5 | ¿Mejoró SoftExpert? | **Efectividad** | Estado de la mejora en la lista y tareas con hallazgos repetidos. Aceptado / rechazado / corregido: no disponible |

**Días exigidos para la adherencia:**
- **Mantención**: días hábiles, sin feriados.
- **Operación**: según la rotación de turnos.

| Código | Significado | ¿Se exige el RIT? |
|---|---|---|
| D | Día, de 08:00 a 20:00 | Sí |
| N | Noche: la N del día X va de 20:00 de X−1 a 08:00 de X. Un RIT de las 20:00 en adelante cuenta para el día siguiente | Sí |
| DC | Descanso | No. Si registra, se marca "en descanso" |
| AD | Administrativo: no necesariamente lidera el RIT | No. Si registra, no suma ni resta |

Otras reglas:
- Un turno sin días D ni N en el período queda "sin turno" y no se evalúa.
- **Semana de inicio general: S26**, la primera en que registran todas las áreas en ambas especialidades. Madera fue piloto desde S6. Antes de S26 la adherencia no se evalúa.
- Un **equipo mal registrado** (Operación sin turno A–E, o sin equipo) no cuenta para la adherencia, pero sus hallazgos sí se evalúan.
- La **adherencia por persona no existe**: el RIT se exige al equipo/turno.
- **Muestra reducida**: denominador menor que 5. Se marca y no se interpreta sola.

## 4. Pauta automática de redacción (nivel 3)

Es una evaluación de **redacción**, no de calidad técnica. La pregunta es: ¿quien implementa en SoftExpert entendería qué cambiar sin preguntar?

| Nota | Nombre | Criterio | Ejemplos reales |
|---|---|---|---|
| 3 | Clara y accionable | Acción + elemento identificado (código, tag o nombre específico) + tarea. Si se elimina o modifica algo, además el porqué. Si se agrega algo sin justificar, la identificación debe ser fuerte | "Falta riesgos: exposición radiación solar, condiciones climáticas adversas, exposición a ruido"; "Los riesgos de atrapamiento… no aplica a la tarea de ajuste" |
| 2 | Entendible pero incompleta | Identifica el elemento, pero falta la acción, la tarea o el porqué | "Eliminar: CO-ING-4051 Indicación de presión en terreno" (falta el porqué); "CO-ADM-4199" (falta la acción); "Incorporar HTE de toma de muestras" |
| 1 | Ambigua / genérica | Nombra un tema sin identificar el elemento exacto | "Riesgos asociados a SSO", "Faltan controles", "Cargar pauta inspección", "Mejorar control", "incluir check list" |
| 0 | No utilizable | Vacío, **lista copiada** (3 o más códigos sin acción) o no permite saber qué se pide | "SSO Y PRODUCCION", "ECO. LYR.", "Similar a plataforma licor", listas CO-ADM-… pegadas |

Para evitar premiar frases artificiales, un verbo de acción no basta para llegar a 3. Se detectan cinco elementos:
- **acción**;
- **objeto** (riesgo, control, documento, HTE…);
- **identificación** (términos que no sean genéricos, código o tag);
- **contexto** (la tarea del RIT o una mencionada en el texto);
- **justificación**.

El detalle de cada RIT muestra estos elementos (Sí/No) y una **versión sugerida**. La versión sugerida solo usa lo que está en el registro; lo que falta queda entre corchetes.

Formato recomendado (guía, no obligación): **[ACCIÓN] + [ELEMENTO EXACTO] + [TAREA/CONTEXTO] + [POR QUÉ]**.

## 5. Categorías de gestión (equipos, 4 semanas hasta la semana seleccionada)

| Categoría | Condición |
|---|---|
| Referentes | Adherencia ≥90% y ≥60% de hallazgos entendibles |
| Constantes, pero requieren mejorar la calidad de sus hallazgos | Adherencia ≥90%, entendibles <60% |
| Buen desempeño cuando participa, pero requiere constancia | Adherencia <90%, entendibles ≥60% |
| Requieren apoyo | Adherencia <90%, entendibles <60% |
| RIT realizado sin hallazgos suficientes para evaluar redacción | Menos de 3 hallazgos. **No es negativo por sí solo** |
| Sin turno exigido | El turno estuvo en DC o AD todo el período |

Alerta adicional ⚠👥 **problema de trazabilidad**: 50% o más de los RIT del equipo vienen de cuentas compartidas.

## 6. Personas

- Solo cuentas individuales.
- Conceptos separados, sin ranking único:
  - mayor actividad (RIT registrados);
  - mayor constancia (semanas activas);
  - mejor redacción (al menos 3 hallazgos, % accionables);
  - requieren apoyo (al menos 3 hallazgos y 50% o más genéricos o no utilizables).
- Las cuentas compartidas se listan aparte, como dato del equipo.
- El **Top 20 del piloto** es una referencia externa. Sus puntajes (cantidad, calidad, frecuencia) se muestran por separado, junto a los indicadores del reporte, sin volver a combinarlos.

## 7. Cómo comunicar

- Usa el patrón **Problema → Dónde → Evidencia → Causa probable → Acción sugerida**. Si los datos no determinan la causa, escribe "Posible causa / requiere revisión".
- El orden de lectura es: **dato → tendencia → contexto → semáforo**. Nunca uses solo el color, y siempre da n/N.
- No sobrerreacciones a una semana: usa la tendencia y la persistencia de 4 semanas.
- No incentives hallazgos artificiales: un RIT sin hallazgo es válido.
- Dirige cada foco a quien puede actuar:
  - el jefe de turno o de especialidad: adherencia y calidad del análisis;
  - quien administra las cuentas: trazabilidad;
  - el ingeniero o implementador: listas copiadas y pedidos genéricos.
- No menciones confirmaciones TBH.

## 8. No disponible con los datos actuales

- Si la tarea revisada es la correcta para el área. Requiere el maestro de tareas: el prefijo del código se repite entre macroprocesos (Planta Térmica y Madera usan "A").
- Los riesgos, controles y documentos asociados a la tarea en SoftExpert.
- La pertinencia técnica. La estructura está lista en `config/validacion_tecnica.csv`.
- Si la mejora fue aceptada, rechazada o corregida, su fecha de cierre y si se implementó de verdad.
- La adherencia individual.
- Quién lideró el RIT cuando se usó una cuenta compartida.
- La rotación antes de abril y después de diciembre de 2026.
