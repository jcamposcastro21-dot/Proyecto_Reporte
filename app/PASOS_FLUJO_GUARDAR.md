# Flujo: Guardar_Liderazgo_Visible

Un solo flujo guarda los tres formularios de la aplicación. La aplicación envía:

```json
{ "lista": "Instancias", "item": { "PlantaId": 5, "Fecha": "2026-10-16T12:00:00Z", "...": "..." } }
```

- `lista`: lista de destino. Solo se aceptan **Contactos de Seguridad**, **Instancias** y
  **Coaching Contactos Seguridad**.
- `item`: el registro con los **nombres internos** de SharePoint. Las búsquedas y personas ya
  vienen como ID (`PlantaId`, `AreaId`, `Rol_x0020_LiderId`, …), así que el flujo no busca nada.

Si se agregan o cambian preguntas, **solo cambia la aplicación**. El flujo queda igual.

Todas las acciones son estándar (sin Premium). Sitio: `CL-SISSO_Plantas_Celulosa`.

## 1. Disparador
**Cuando se recibe una solicitud de webhook de Teams**, con *¿Quién puede desencadenar el flujo?* =
**Cualquiera**.

## 2. Redactar → renombrar a `Datos`
Entradas (fx):
```
json(string(triggerBody()))
```

## 3. Condición → renombrar a `Lista_permitida`
Modo de expresión avanzada (o fx en el primer valor, `es igual a`, `true`):
```
contains(createArray('Contactos de Seguridad','Instancias','Coaching Contactos Seguridad'), outputs('Datos')?['lista'])
```

### Si es verdadero: Enviar una solicitud HTTP a SharePoint → renombrar a `Crear_registro`
- Dirección del sitio: `CL-SISSO_Plantas_Celulosa`
- Método: `POST`
- URI (fx):
```
concat('_api/web/lists/getbytitle(''', outputs('Datos')?['lista'], ''')/items')
```
- Encabezados:
  - `Accept` = `application/json;odata=nometadata`
  - `Content-Type` = `application/json;odata=nometadata`
- Cuerpo (fx): `outputs('Datos')?['item']`

### Si es falso: Terminar
- Estado: **Error**, mensaje: `Lista no permitida`.

## Notas
- La URL del disparador **no se guarda en el repositorio**. Se entrega a `build_app.py` con
  `--flow-url` al generar la aplicación.
- Quien registra va en **VsApp** (`HTML 2.0 | Nombre`). "Creado por" queda con el dueño del flujo.
- Las personas (líder de la instancia, líder evaluado, responsables) se eligen de la lista
  **Correos Líderes**: se envía su `LiderId`, que es el ID del usuario en el sitio.
- La Power App enviaba un correo al responsable de la acción de mejora (Instancias y Coaching).
  Este flujo todavía no lo hace; se puede agregar con la acción estándar de Outlook.
- El flujo anterior de Confirmación TBH (con `buscar`) deja de usarse: la aplicación ya envía
  `AreaId`, `EmpresaId` y `RespMedidaCorrectivaId`.
