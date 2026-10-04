# Reglas de calidad RdP (definiciones vigentes)

Están implementadas en `reporte/calidad.py` y `reporte/diario.py`. Si cambias una regla, cambia el código y este archivo juntos.

## Datos

- `Registros`: Id, Planta, NAT, Área Responsable, Evento tiempo perdido (es el **título**), Herramienta, Líder responsable, Fecha Inicio, Estado (`Cerrado` / `En creación`), ¿Se utilizó SAR? (`Si` / `No`).
- `Acciones`: RegistroId, AccionId, Tipo causa raíz, Causa raíz, Acción, Responsable, Estado ejecución, Fecha Compromiso, Estado cumplimiento, Fecha cierre, Cerrada por.
- La unión se hace con `Acciones.RegistroId = Registros.Id`.
- Los nombres se normalizan (espacios dobles) antes de compararlos.
- Limitaciones: no hay descripción, categoría, horas perdidas ni campo de eficacia. `Tipo causa raíz` está mal asignado con frecuencia y **no se usa**. Lo que no está en la base puede estar en un ACR, un aviso SAP o un acta: escribir "no registrado", no "no se hizo".

## Cálculo "a la fecha"

- Solo cuentan los eventos con Fecha Inicio ≤ fecha del reporte.
- Una acción está **cerrada** si tiene Fecha cierre ≤ fecha del reporte.
- `Estado` del evento es el del corte de la base (no hay historial).
- **Novedades**: eventos con Fecha Inicio, o acciones con Fecha cierre, entre `desde` y la fecha. Por defecto `desde` = ayer, y el lunes se cubre desde el viernes.
- **Calidad**: ventana móvil de los últimos 30 días.

## Indicadores y semáforos

| Indicador | Fórmula | Verde | Ámbar | Rojo |
|---|---|---|---|---|
| % acciones sistémicas | S / acciones | ≥ 40 | ≥ 25 | < 25 |
| % acciones en plazo | (cerradas con cierre ≤ compromiso + abiertas no vencidas) / acciones | ≥ 80 | ≥ 65 | < 65 |
| % cierre por tercero | cerradas con Responsable ≠ Cerrada por / cerradas | ≥ 50 | ≥ 20 | < 20 |
| % títulos nulos | títulos nulos / eventos | ≤ 10 | ≤ 25 | > 25 |
| % causa débil | eventos con acciones y todas sus causas débiles / eventos con acciones | ≤ 20 | ≤ 40 | > 40 |
| % sin acción sistémica | eventos con acciones y 0 S / eventos con acciones | ≤ 30 | ≤ 50 | > 50 |

- **Vencida**: abierta con compromiso < fecha.
- **RdP en creación lenta**: más de 7 días. Es la frecuencia semanal de la RdP de categoría 1-2; la categoría 3 se emite en 5 días.
- **Lectura estadística**: con menos de 20 eventos por grupo, no leer como reales diferencias menores a ~15 puntos.

## Título del evento (paso 1 del ciclo RdP)

- **Nulo**: `0`, `no`, `3h`, `.`, vacío o 2 caracteres o menos.
- **Catálogo**: "Otros", "Falla de equipos, componentes, elementos o sistema", "Parada no programada", "Cambio de equipos…", "Falla motor", "Corte de hoja".
- **Específico**: todo lo demás. Lo ideal es fenómeno + equipo/tag.

## Causa raíz (cada fila de acción)

Están ordenadas de peor a mejor:
- `vacia`: sin causa.
- `tarea`: redactada como tarea ("revisar…", "corroborar…").
- `hipotesis`: "posible…", "probable…", "no existe información", "TBD".
- `estado`: el estado del componente, en 4 palabras o menos ("desgaste", "rotura", "falta de perno", "vibraciones").
- `mecanismo`: explica el mecanismo físico o de proceso.
- `control`: **nombra el control que faltó o falló** ("falta de estrategia de mantención…", "ausencia de límites operacionales…", "no existe procedimiento…", "diseño deficiente"). Es la causa que se premia.

Las cuatro primeras son **causa débil**.

## Tipo de acción

- `S`, sistémica o preventiva: cambia un plan, estándar, procedimiento, HTE, pauta, lógica, interlock, secuencia, diseño, estrategia, frecuencia, criterio o límite. Es una barrera permanente.
- `C`, correctiva: cambiar, reparar, reemplazar, ajustar, instalar, limpiar, lubricar o calibrar. Restituye la condición.
- `R`, revisión o difusión: revisar, evaluar, analizar, medir, monitorear una vez, coordinar, informar, reunirse con un proveedor o generar un aviso.

La clasificación automática es por palabras clave y coincide en 83% con la revisión manual de ago-sep 2026. La revisión manual en `config/clasificacion_acciones.csv` (AccionId, tipo, origen) **siempre prevalece**. Para corregir una acción, agrégala ahí.

## Recurrencia

Un evento es **posible recurrencia** si tiene antecedentes de la misma planta y NAT en los 12 meses anteriores que compartan un tag (palabra con dígitos, como `431-31-919` o `M317`) o 2 o más palabras relevantes en el título y las causas.

Es una **alerta a validar**, no una confirmación. Se considera confirmada cuando coincide el mismo equipo o tag y el mismo modo de falla, y hay acciones previas cerradas sin eficacia demostrada.

## Cierre

- **Autocierre**: la persona que cierra la acción es su responsable. En acciones de recurrencias y eventos críticos se pide cierre por un tercero y verificación de eficacia a 60-90 días con un criterio medible.
- Una acción `R` cerrada debe **registrar su resultado**; si no lo hace, no reduce el riesgo.
