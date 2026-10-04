# Reglas de calidad RdP (definiciones vigentes)

Están implementadas en `reporte/calidad.py` y `reporte/diario.py`. Si cambias una regla, cambia el código y este archivo juntos.

## Datos

- `Registros`: Id, Planta, NAT, Área Responsable, Evento tiempo perdido (es el **título**), Herramienta, Líder responsable, Fecha Inicio, Estado (`Cerrado` / `En creación`), ¿Se utilizó SAR? (`Si` / `No`).
- `Acciones`: RegistroId, AccionId, Tipo causa raíz, Causa raíz, Acción, Responsable, Estado ejecución, Fecha Compromiso, Estado cumplimiento, Fecha cierre, Cerrada por.
- La unión se hace con `Acciones.RegistroId = Registros.Id`.
- Los nombres se normalizan (espacios dobles) antes de compararlos.
- Limitaciones: no hay descripción, categoría, horas perdidas ni campo de eficacia. `Tipo causa raíz` está mal asignado con frecuencia y **no se usa**.

## Cálculo "a la fecha"

- Solo cuentan los eventos con Fecha Inicio ≤ fecha del reporte.
- Una acción está **cerrada** si tiene Fecha cierre ≤ fecha del reporte.
- `Estado` del evento es el del corte de la base (no hay historial).
- **Novedades**: eventos con Fecha Inicio, o acciones con Fecha cierre, entre `desde` y la fecha. Por defecto `desde` = ayer, y el lunes se cubre desde el viernes.
- **Período de calidad**: los últimos 30 días.
- **Línea base**: el período de `config/linea_base.json` (ago-sep 2026), calculado con las **mismas reglas**.
- **Resto del negocio**: las demás plantas, en el mismo período de 30 días y con las mismas reglas.

## Indicadores

| Indicador | Fórmula | Meta (verde) |
|---|---|---|
| % acciones sistémicas | S / acciones | ≥ 40 |
| % acciones en plazo | (cerradas con cierre ≤ compromiso + abiertas no vencidas) / acciones | ≥ 80 |
| % cierre por tercero | cerradas con Responsable ≠ Cerrada por / cerradas | ≥ 50 |
| % títulos nulos | títulos nulos / eventos | ≤ 5 (Diagnóstico, 30 días) |
| % análisis causal adecuado | RdP con acciones y pauta causal ≥ 2 / RdP con acciones | ≥ 75 (Diagnóstico, 60 días) |
| % RdP solo reparación | RdP con acciones y 0 acciones S / RdP con acciones | ≤ 20 (Diagnóstico, 60 días) |

**Semáforo**:
- verde: cumple la meta;
- ámbar: está entre la línea base de la planta y la meta;
- rojo: está peor que la línea base.

Otras definiciones:
- **Vencida**: acción abierta con compromiso < fecha.
- **RdP en creación lenta**: más de 7 días. Es la frecuencia semanal de la RdP de categoría 1-2; la categoría 3 se emite en 5 días.

## Título → pauta de identificación

| Puntaje | Criterio |
|---|---|
| 0 | Nulo: `0`, `no`, `3h`, `.`, vacío o 2 caracteres o menos |
| 1 | Catálogo: "Otros", "Falla de equipos, componentes, elementos o sistema", "Parada no programada", "Cambio de equipos…", "Falla motor", "Corte de hoja" |
| 2 | Fenómeno específico |
| 3 | Fenómeno + equipo, tag o línea (tiene dígitos o nombra un equipo) |

## Causa raíz (por fila) → pauta causal (máximo del evento)

| Clase | Ejemplos | Puntaje |
|---|---|---|
| `vacia` | Sin causa | 0 |
| `tarea` | "revisar…", "corroborar…", "mediciones para…", "en caso de…", "no aplica", "investigación", "cambio" | 0 |
| `hipotesis` | "posible…", "probable…", "si la válvula…", "no existe información", "TBD" | 1 |
| `estado` | Estado del componente en 4 palabras o menos ("desgaste", "rotura", "falta de perno", "vibraciones"), o "se detecta … en falla" | 1 |
| `sintoma` | Describe lo observado sin explicar por qué ("alta decantación del licor", "zona llena de arena"), o atribuye a la persona ("desconocimiento…") | 1 |
| `mecanismo` | Explica el mecanismo, con un conector causal ("secuencia favorece la cavitación de la bomba") | 2 |
| `control` | **Nombra el control que faltó o falló** ("falta de estrategia de mantención…", "ausencia de límites operacionales…", "no existe procedimiento/canal…", "no identificar riesgo…", "diseño/configuración deficiente") | 3 |

Las clases débiles, de puntaje ≤ 1, son vacía, tarea, hipótesis, estado y síntoma. La regla automática es más estricta que la lectura manual del diagnóstico: NA da 49% de análisis causal adecuado frente al 58% manual. Las correcciones por evento van en `config/pauta_eventos.csv`.

## Tipo de acción → pauta de acciones

- `S`, sistémica o preventiva: cambia un plan, estándar, procedimiento, HTE, pauta, lógica, interlock, secuencia, diseño, estrategia, frecuencia, criterio o límite.
- `C`, correctiva: cambiar, reparar, reemplazar, ajustar, instalar, limpiar, lubricar o calibrar.
- `R`, revisión o difusión: revisar, evaluar, medir, coordinar, informar, reunirse con un proveedor o generar un aviso.

La clasificación manual en `config/clasificacion_acciones.csv` **prevalece**. La automática coincide en 83% con la revisión manual de ago-sep 2026.

Pauta de acciones:
- 0: sin acciones.
- 1: solo C o R.
- 2: al menos una S.
- 3: dos o más S, o una acción extendida a equipos similares ("extender", "todas las líneas", "L2 y L3", "equipos similares", "levantamiento de…").

**Cadena coherente**: título ≥ 2, causa ≥ 2, acciones ≥ 2, y al menos una acción S en una fila cuya causa es `control`.

## Patrones marcados en el chequeo de cada RdP

- Título nulo o de catálogo.
- Posible recurrencia sin análisis estructurado.
- Causa débil (indicando qué tipo).
- Herramienta declarada (5 porqués / árbol / Ishikawa) con causa ≤ 1.
- Causa atribuida a la persona.
- Sin acción sistémica.
- Difusión sin cambio esperado.
- Derivación al proveedor ("reunión con", "revisar con", Andritz, etc.).
- Sin verificación de eficacia ("eficacia", "seguimiento", "a 60 días", "tendencia"…).
- Autocierre de todas las acciones.
- SAR usado sin aporte registrado.

## Recurrencia

Un evento es **posible recurrencia** si tiene antecedentes de la misma planta y NAT en los 12 meses anteriores que compartan un tag (palabra con dígitos) o 2 o más palabras relevantes en el título y las causas. Es una alerta a validar.

Los casos clasificados (confirmada, probable o posible) se siguen en `config/casos_seguimiento.json`. El reporte muestra el estado de hoy de sus acciones clave y avisa de **eventos nuevos relacionados**: misma NAT, posteriores a la línea base, con alguna palabra clave del caso.

## Cierre

- **Autocierre**: la persona que cierra la acción es su responsable. En acciones de recurrencias y eventos críticos se pide cierre por un tercero y verificación a 60-90 días con un criterio medible.
- Una acción `R` cerrada debe **registrar su resultado**.
