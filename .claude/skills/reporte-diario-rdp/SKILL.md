---
name: reporte-diario-rdp
description: Genera el reporte diario de calidad de Resolución de Problemas (RdP) por NAT de una planta del Negocio Celulosa, evaluado con los criterios del Playbook MGO (oct-2025). Úsala cuando el usuario pida el reporte diario, el reporte de RdP o de calidad operacional por NAT, el foco para la reunión RdP, o revisar la calidad de investigaciones RdP (títulos, causas, acciones sistémicas, plazos, recurrencias), aunque no mencione el playbook. No cubre confirmaciones TBH.
---

# Reporte diario de calidad RdP por NAT

El objetivo es responder cada día si nuestras RdP **evitan que el problema se repita**, no cuántas se hacen. El marco es el Playbook MGO: la RdP es la etapa de **aprendizaje** del ciclo y cierra cuando cambia un estándar. Las confirmaciones TBH quedan fuera del alcance.

Antes de redactar, lee:
- `references/playbook_mgo.md`: categorías, herramienta y plazo por categoría, ciclo de 6 pasos, criterio SMART, jerarquía de controles, roles y KPIs.
- `references/reglas_calidad.md`: fórmulas, semáforos y clasificaciones implementadas en el código.

## Flujo

1. **Datos.** Toma el Excel más reciente `data/RDP_Completo_*.xlsx`, con las hojas `Registros` y `Acciones`. Si `data/` está vacío, pide al usuario el archivo; no está en el repo porque contiene nombres de personas. Cuando exista la conexión a la base de los QVD, usa `reporte/fuente.py` (`cargar_qvd` o `cargar_sql`) para devolver las mismas columnas.
2. **Generar números y borrador.** Requiere `pip install -r requirements.txt`.
   ```
   python3 -m reporte.diario --planta "Nueva Aldea" --fecha AAAA-MM-DD --json
   ```
   Produce `out/RdP_diario_<planta>_<fecha>.html`, con todas las cifras y focos automáticos, y un `.json` con el detalle para redactar. Los números siempre salen del script: nunca los calcules a mano ni los cambies en el texto.
3. **Revisar lo que el script no sabe juzgar.** Lee el JSON, sobre todo `nuevos`, `recurrencias_30d` y `vencidas`, y aplica el playbook:
   - **Clasificación de acciones** con `tipo_origen = auto`: si una está mal, agrégala a `config/clasificacion_acciones.csv` (`AccionId,tipo,origen`) con origen `revision <fecha>`.
   - **Recurrencias**: son alertas por coincidencia de texto. Descarta las falsas, como "hoja" en Máquina, que no es lo mismo que el mismo modo de falla. Confirma solo si coinciden el equipo o tag y el modo de falla.
   - **Herramienta vs. categoría**: una causa repetitiva o desconocida requiere 5 porqués, Ishikawa o árbol de falla. Si el evento parece de categoría 3 o más, requiere un ACR, con 5 días de plazo para emitirlo.
   - **Causa**: ¿nombra el control que faltó o falló (plan, estándar, criterio, diseño, lógica)?
   - **Acciones**: ¿alguna ataca directamente esa causa y cambia un estándar (paso 6)? ¿Son SMART? ¿Qué barrera propondrías según la jerarquía (eliminar > sustituir > ingeniería > administrativo > EPP)?
4. **Redactar comentarios.** Escribe `comentarios/<fecha>_<planta>.json` con el formato de `comentarios/ejemplo.json`. La clave es `"Planta"` o el nombre exacto de la NAT; cada una lleva `lectura` (opcional, 2-3 líneas) y `focos` (máximo 4, HTML simple con `<b>` y `<code>`). Las NAT que no tengan clave mantienen los focos automáticos.
5. **Regenerar con comentarios.**
   ```
   python3 -m reporte.diario --planta "Nueva Aldea" --fecha AAAA-MM-DD --comentarios comentarios/<fecha>_<planta>.json
   ```
   Entrega el HTML. En el chat, resume en 3-5 líneas lo más importante del día.

## Cómo escribir los focos

Cada foco sigue el formato **hecho con ID → por qué importa según el playbook → qué exigir en la reunión RdP**.
- Cita siempre IDs de evento (`<code>11702</code>`) y, cuando ayude, de acción.
- Prioriza en este orden:
  1. Recurrencias con acciones previas cerradas sin eficacia.
  2. RdP nuevas sin acción sistémica o con causa débil.
  3. Acciones vencidas.
  4. RdP en creación por más de 7 días.
  5. Títulos nulos.
- Cuando propongas una medida de control, usa el formato *control que faltó → medida (dónde sube en la jerarquía de controles) → cómo se verifica la eficacia (criterio medible y plazo, típico 60-90 días)*. Son **propuestas a validar con el NAT**: dilo así.
- Dirige cada exigencia al rol que corresponde: el supervisor o ingeniero lidera la RdP, el superintendente asegura la adherencia y evalúa la efectividad de los controles, y la gerencia verifica la calidad del análisis causal.
- Escribe en español, en tono directo y sin adjetivos de relleno. No inventes la categoría ni las horas perdidas, porque la base no las trae; si las infieres, di "probable categoría X, a confirmar".
- Con menos de 20 eventos, no presentes diferencias menores a ~15 puntos como reales.
- Si un dato no está en la base, escribe "no registrado", no "no se hizo".

## Estructura del reporte (no cambiar el orden sin pedirlo)

Hay un selector **Planta completa / cada NAT**. Cada vista tiene:
1. 📌 Estado de cartera a la fecha: RdP nuevas, en creación, acciones vencidas, acciones que vencen en 7 días, cerradas en la ventana y % sistémicas a 30 días.
2. 🎯 Foco para la reunión RdP: lectura opcional y 2 a 4 focos.
3. 🆕 RdP nuevas, con el chequeo de calidad del playbook para cada una.
4. ⏰ Acciones vencidas y 📅 acciones que vencen en los próximos 7 días.
5. ✔ Acciones cerradas en la ventana, marcando autocierre, cierre tarde y revisiones sin resultado.
6. ♻ Posibles recurrencias de los últimos 30 días.
7. 📊 Calidad RdP de los últimos 30 días por NAT (vista planta) o por área (vista NAT), con semáforos.

El diseño usa `ref/estilos_base.css` y `ref/estilos_reporte.css` (paleta gris, verde, naranja y madera). El HTML es un solo archivo autocontenido e imprimible.

## Si el usuario pide cambios de formato o reglas

- Las reglas y umbrales están en `reporte/calidad.py` y en `UMBRALES` de `reporte/diario.py`. Actualiza también `references/reglas_calidad.md`.
- Para validar la clasificación automática contra la manual, compara `clasificar_accion` con `config/clasificacion_acciones.csv` (hoy coincide en 83%).
