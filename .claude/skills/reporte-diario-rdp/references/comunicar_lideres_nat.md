# Cómo presentar los hallazgos a los líderes NAT

El formato y el tono vienen del **Reporte de Calidad RdP Nueva Aldea ago-sep 2026**, que el usuario validó como formato a seguir, y del *Diagnóstico RDP*. El reporte diario conserva esa estructura y suma la capa diaria (novedades, vencidas, cerradas) y los criterios del Playbook MGO.

## Estructura (no cambiar sin pedirlo)

**Vista planta**, para la reunión de líderes NAT:
1. 📌 Hoy: RdP nuevas, en creación, acciones vencidas, acciones que vencen en 7 días y cerradas en la ventana.
2. 🎯 Foco para la reunión RdP: lectura de 2 a 3 líneas y de 2 a 4 focos.
3. 🏆 Logro del período: una sola frase con evidencia, más la advertencia "cerrada ≠ eficaz".
4. 📊 Resumen de calidad: Operaciones vs. Mantención, con sub-áreas, resto del negocio, línea base y meta. También la mezcla de acciones y el detalle por NAT.
5. ✅ Fortalezas (3) / ❗ Oportunidades de mejora (3).
6. 🔍 Casos críticos en seguimiento: casos del diagnóstico con su estado de hoy y recurrencias nuevas.
7. 🆕 RdP nuevas con pauta y chequeo; ⏰ acciones vencidas; 📅 acciones por vencer; ✔ acciones cerradas.
8. ♻ Posibles recurrencias y 🤖 Impacto del SAR.

**Vista NAT**, la radiografía para la reunión 1 a 1:
1. 📌 Hoy.
2. 🎯 Foco para su reunión.
3. 📊 Estado de cartera: KPIs, acciones por estado y tipo, y "Sus casos críticos".
4. ✅ Sus fortalezas (2) / ❗ Sus brechas de calidad (2–3).
5. Tabla por área contra la línea base y la meta.
6. 🛡 Conclusión y medidas de control propuestas: caso / control que faltó o falló / medida / verificación de eficacia.
7. Detalle diario, recurrencias, eventos del NAT y acciones abiertas. Todo se puede abrir con un clic.

## Reglas de redacción

- **Cada afirmación cita IDs de evento** (`<code>11702</code>`). En el HTML, todo `<code>ID</code>` de una RdP se vuelve clicable.
- **Formato de los mensajes**: evidencia → implicancia → decisión o qué exigir. Ejemplo del diagnóstico: *"Evidencia: 15/36 RdP solo tienen acciones correctivas o de revisión vs 21% del resto. Implicancia: el equipo queda operativo, pero la condición que originó la falla sigue ahí. Decisión: exigir al menos una acción que cambie plan, estándar, diseño o lógica, o una justificación escrita."*
- **Distinguir el tipo de afirmación** cuando importe:
  - [H] hecho comprobado en la base;
  - [I] interpretación;
  - [P] hipótesis por validar.
- Números con su base: "7 de 45 (16%)", no "16%" solo.
- Compara contra la **línea base** y el **resto del negocio**, no entre NAT como ranking. Con menos de 20 eventos, no leas diferencias menores a ~15 puntos.
- **Fortalezas**: concretas y con ID. Reconocen prácticas que se pueden copiar. Ejemplos del reporte anterior:
  - *"Mejor práctica de la planta en paradas: 9600 identifica que no se evaluó el riesgo de no poder extraer el accionamiento y establece un punto de no retorno más un hitograma de uso del puente grúa."*
  - *"Va más allá del error humano: 9606 analiza por qué se subestimó el trabajo e incorpora la revisión del programa semanal en la reunión de inicio de turno."*
- **Brechas**: nombra el patrón y da ejemplos textuales entre comillas. Ejemplos:
  - *"Reparar sin explicar: 7 de 10 eventos no tienen ninguna acción sistémica. Causas de una o dos palabras: 'Rotura' (12746), 'Soltura Modulos' (11735)…"*
  - *"Pruebas cerradas sin resultado: las acciones 'probar secuencia con retardo' de 9594 se cerraron sin registrar si funcionó."*
- **Foco / acciones directas a exigir**: verbo, objeto y plazo. Ejemplos:
  - *"Regularizar esta semana las 3 acciones vencidas al 30-sep… con fecha nueva y responsable confirmado."*
  - *"No aprobar ninguna RdP de transportadores que cierre con una reunión con el proveedor: exigir el modo de falla con tag, la causa propia y una acción que entre al plan de mantenimiento."*
- **Casos críticos**: equipo, cadena de eventos con fechas, qué acción está pendiente o se cerró sin eficacia, y qué se requiere. Ejemplo: *"11702 / 11671: corte de hoja por pérdida de napa del paño PU. Recurrencia confirmada de 2230; el paño falló a 75 días frente a 90 y se vuelve a pedir revisión a Andritz."*
- **Conclusión del NAT**: un párrafo con la causa de fondo del patrón, no un resumen de números. Ejemplo (Máquina): *"La vida del paño PU se gestiona por calendario y no por condición… La acción que ataca el mecanismo espera una parada y no tiene ningún control interino, así que el riesgo sigue intacto hasta la P/A."*
- **Medidas de control**: siempre en 4 columnas.
  - *Control que faltó o falló*: plan, estándar, criterio, límite operacional, inspección, diseño o QA/QC.
  - *Medida*: subir en la jerarquía del playbook cuando el evento se repite. Si la medida de fondo espera una parada, proponer un **control interino**.
  - *Verificación de eficacia*: criterio medible y plazo, por ejemplo "90 días sin detención por rotura" o "el siguiente paño alcanza 90 días".
  - Siempre "propuesta a validar con el NAT".
- **Rol al que se dirige la exigencia** (playbook):
  - el supervisor o ingeniero lidera la RdP y busca la causa;
  - el superintendente asegura la adherencia y evalúa la efectividad de los controles;
  - la gerencia verifica la calidad del análisis causal.
- **Tono**: directo, en español, sin adjetivos de relleno ni juicios sobre personas. Hablar de RdP, acciones y controles, no de "el líder X lo hizo mal".
- **Nunca**:
  - mencionar confirmaciones TBH (están fuera del alcance);
  - inventar la categoría ni las horas perdidas;
  - escribir "no se hizo" cuando solo "no está registrado";
  - atribuirle calidad a SAR.

## Dónde van los textos

En `comentarios/<fecha>_<planta>.json`, con una clave por ámbito: `"Planta"` o el nombre exacto de la NAT. Cada ámbito acepta:

| Clave | Contenido |
|---|---|
| `lectura` | Texto de 2 a 3 líneas |
| `focos` | Lista |
| `logro` | Solo para la planta |
| `fortalezas` | Lista |
| `brechas` | Lista |
| `casos` | Lista |
| `conclusion` | Texto |
| `medidas` | Lista de `[caso, control_que_falto, medida, verificacion]` |

Lo que no se completa usa el texto automático del script. Las medidas que deban quedar vigentes entre días van en `config/medidas_control.json`, actualizando `estado`: propuesta → validada con NAT → en implementación → verificada.
