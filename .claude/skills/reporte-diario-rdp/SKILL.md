---
name: reporte-diario-rdp
description: Genera el reporte diario de calidad de Resolución de Problemas (RdP) por NAT de una planta del Negocio Celulosa, con el formato del Reporte de Calidad RdP (vista planta + radiografía por NAT), evaluado con los criterios del Playbook MGO (oct-2025) y del Diagnóstico RDP (pauta 0–3, línea base, metas, recurrencias). Úsala cuando el usuario pida el reporte diario, el reporte de RdP o de calidad operacional por NAT, el foco para la reunión RdP o 1 a 1, o revisar la calidad de investigaciones RdP (títulos, causas, acciones sistémicas, plazos, recurrencias, medidas de control), aunque no mencione el playbook. No cubre confirmaciones TBH.
---

# Reporte diario de calidad RdP por NAT

El objetivo es responder cada día si nuestras RdP **evitan que el problema se repita**, no cuántas se hacen. Para eso se usan tres fuentes, y las tres se leen antes de redactar:

| Fuente | Archivo | Qué aporta |
|---|---|---|
| **Playbook MGO** | `references/playbook_mgo.md` | El marco. La RdP es la etapa de aprendizaje y cierra cuando cambia un estándar. Categorías, herramienta y plazo, ciclo de 6 pasos, criterio SMART, jerarquía de controles, roles y KPIs. |
| **Diagnóstico RDP ago-sep 2026** | `references/diagnostico_rdp.md` | Qué buscar: pauta 0–3, los 12 patrones con ejemplos, cómo clasificar recurrencias, línea base y metas a 30, 60 y 90 días, y aprendizaje entre plantas. |
| **Reporte de Calidad RdP anterior** | `references/comunicar_lideres_nat.md` | El formato validado por el usuario y cómo redactar fortalezas, brechas, focos, casos críticos y medidas de control para los líderes NAT. |

Las fórmulas, umbrales y clasificaciones del código están en `references/reglas_calidad.md`. Las confirmaciones TBH quedan fuera del alcance: el reporte TBH solo se usó como referencia visual.

## Flujo

1. **Datos.** Usa el Excel más reciente `data/RDP_Completo_*.xlsx`, con las hojas `Registros` y `Acciones`. Si `data/` está vacío, pide el archivo al usuario; no está en el repo porque contiene nombres. Cuando exista la conexión a la base de los QVD, usa `cargar_qvd` o `cargar_sql` de `reporte/fuente.py`, que deben devolver las mismas columnas.
2. **Generar números y borrador.** Requiere `pip install -r requirements.txt`.
   ```
   python3 -m reporte.diario --planta "Nueva Aldea" --fecha AAAA-MM-DD --json
   ```
   Genera dos archivos en `out/`:
   - `RdP_diario_<planta>_<fecha>.html`, con todas las cifras y textos automáticos.
   - `.json`, con lo necesario para redactar: indicadores, línea base, resto del negocio, RdP nuevas con su pauta y chequeo, vencidas, en creación, recurrencias y textos automáticos.

   **Los números siempre salen del script.** Nunca los calcules a mano ni los cambies en el texto.
3. **Revisar con criterio lo que el script no sabe juzgar.**
   - **RdP nuevas**: aplica la pauta 0–3 y los 12 patrones de `diagnostico_rdp.md` §4. Si la pauta automática no corresponde, corrígela en `config/pauta_eventos.csv` (`Id,p_tit,p_causa,p_acc,nota`).
   - **Acciones `tipo_origen = auto` mal clasificadas**: corrígelas en `config/clasificacion_acciones.csv` (`AccionId,tipo,origen`).
   - **Recurrencias**: son alertas por coincidencia de texto. Clasifícalas como confirmada, probable o posible según §5 del diagnóstico. Si una es nueva y real, agrégala a `config/casos_seguimiento.json`.
   - **Casos en seguimiento**: revisa si cambiaron. Por ejemplo, si se cerró una acción clave sin verificación de eficacia o si apareció un evento relacionado.
   - **Herramienta vs. categoría (playbook)**: una causa repetitiva o desconocida requiere 5 porqués, Ishikawa o árbol de falla. Si el evento parece de categoría 3 o más, requiere un ACR con 5 días de plazo de emisión.
4. **Redactar** `comentarios/<fecha>_<planta>.json` (formato en `comentarios/ejemplo.json`), siguiendo `references/comunicar_lideres_nat.md`:
   - **Planta**: lectura, focos (2–4), logro, fortalezas (3), brechas (3) y casos.
   - **NAT con novedades o alertas**: focos, fortalezas (2), brechas (2–3), casos, y conclusión y medidas si cambiaron.

   No es necesario redactar todos los NAT todos los días. Los que no tengan clave muestran los textos automáticos. Si una medida de control debe quedar vigente entre días, actualiza `config/medidas_control.json`.
5. **Regenerar con comentarios.**
   ```
   python3 -m reporte.diario --planta "Nueva Aldea" --fecha AAAA-MM-DD --comentarios comentarios/<fecha>_<planta>.json
   ```
   Entrega el HTML. En el chat, resume en 3-5 líneas lo más importante del día.

## Criterios no negociables

- Cada afirmación cita IDs de evento (`<code>ID</code>`, que en el HTML se vuelve clicable).
- Usa el formato evidencia → implicancia → qué exigir, y marca [H]/[I]/[P] cuando importe.
- Las medidas de control llevan siempre caso / control que faltó / medida (subiendo en la jerarquía si se repite; con control interino si la de fondo espera una parada) / verificación con criterio medible y plazo. Son **propuestas a validar con el NAT**.
- Compara contra la línea base y el resto del negocio, nunca como ranking entre NAT. Con menos de 20 eventos, no leas diferencias menores a ~15 puntos.
- No inventes la categoría ni las horas perdidas. Escribe "no registrado", no "no se hizo". No atribuyas calidad a SAR. No menciones TBH.

## Qué incluye el HTML

Tiene un selector **Planta completa / cada NAT**:
- **Vista planta**: Hoy · Foco · Logro · Resumen de calidad (con resto del negocio, línea base y meta) · Mezcla de acciones · Detalle por NAT · Fortalezas / Brechas · Casos críticos en seguimiento · RdP nuevas con pauta y chequeo · Acciones vencidas, por vencer y cerradas · Recurrencias · Impacto del SAR.
- **Vista NAT (radiografía 1 a 1)**: Hoy · Foco · Estado de cartera · Sus casos críticos · Fortalezas / Brechas · Tabla por área · Conclusión y medidas de control · Detalle diario · Recurrencias · Eventos del NAT · Acciones abiertas.
- **Clic** en cualquier ID de RdP: abre título, NAT, líder, herramienta, SAR, pauta 0–3, cadena coherente, chequeo del playbook, antecedentes y todas sus causas y acciones.
- **Clic** en una fila de acción: abre la causa y la acción completas, su clasificación, fechas, quién la cerró, observaciones (autocierre, tarde, revisión sin resultado) y **qué exigir en la reunión RdP**.

El diseño usa `ref/estilos_base.css` y `ref/estilos_reporte.css`. El HTML es un solo archivo autocontenido e imprimible.

## Si el usuario pide cambios de formato o reglas

- Las reglas están en `reporte/calidad.py`.
- Los umbrales y las secciones están en `reporte/diario.py` (`UMBRALES`, `vista_planta`, `vista_nat`).
- Las metas y la línea base están en `config/linea_base.json`.
- Al cambiar una regla, actualiza también `references/reglas_calidad.md`.
