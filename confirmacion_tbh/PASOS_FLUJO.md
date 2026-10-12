# Flujo: Confirmación TBH desde HTML

El HTML envía un JSON con dos partes:

- `item`: el registro con los **nombres internos** de las columnas de *Contactos de Seguridad*.
- `buscar`: los valores cuyo ID busca el flujo (Área, Empresa y Responsable).

El flujo busca esos IDs y crea el registro con una sola acción. Si más adelante se agregan
o cambian preguntas, **solo cambia el HTML**; el flujo queda igual.

Sitio de todas las acciones de SharePoint: `CL-SISSO_Plantas_Celulosa`.

## 1. Disparador
**Cuando se recibe una solicitud de webhook de Teams** (la versión que permite **Cualquiera**).

## 2. Redactar → renombrar a `Datos`
Entradas (fx):
```
json(string(triggerBody()))
```

## 3. Obtener elementos (SharePoint) → renombrar a `Buscar_area`
- Lista: **Areas Plantas**
- Consulta de filtro (fx):
```
concat('Title eq ''', replace(coalesce(outputs('Datos')?['buscar']?['area'],'-'),'''',''''''), ''' and field_0 eq ''', replace(coalesce(outputs('Datos')?['buscar']?['area_planta'],'-'),'''',''''''), '''')
```
- Recuento superior: `1`

## 4. Obtener elementos (SharePoint) → renombrar a `Buscar_empresa`
- Lista: **Empresas**
- Consulta de filtro (fx):
```
concat('Title eq ''', replace(coalesce(outputs('Datos')?['buscar']?['empresa'],'-'),'''',''''''), '''')
```
- Recuento superior: `1`

## 5. Enviar una solicitud HTTP a SharePoint → renombrar a `Buscar_lider`
- Método: `GET`
- URI (fx):
```
concat('_api/web/lists/getbytitle(''Correos Líderes'')/items?$select=LiderId&$filter=Id eq ', string(coalesce(outputs('Datos')?['buscar']?['lider_id'],0)))
```
- Encabezados: `Accept` = `application/json;odata=nometadata`

## 6. Redactar → renombrar a `Registro`
Entradas (fx):
```
setProperty(setProperty(setProperty(outputs('Datos')?['item'],'AreaId',first(outputs('Buscar_area')?['body/value'])?['ID']),'EmpresaId',first(outputs('Buscar_empresa')?['body/value'])?['ID']),'RespMedidaCorrectivaId',first(body('Buscar_lider')?['value'])?['LiderId'])
```

## 7. Enviar una solicitud HTTP a SharePoint → renombrar a `Crear_registro`
- Método: `POST`
- URI: `_api/web/lists/getbytitle('Contactos de Seguridad')/items`
- Encabezados:
  - `Accept` = `application/json;odata=nometadata`
  - `Content-Type` = `application/json;odata=nometadata`
- Cuerpo: contenido dinámico **Salidas** de `Registro`.

## Notas
- **Creado por** queda con el dueño del flujo. Quien confirma va en la columna **VsApp**
  (`HTML 1.0 | Nombre`). Conviene crear una columna "Registrado por" más adelante.
- Fuera de esta etapa: correo de confirmación, adjuntos y edición/cierre de medidas.
- Actualizar catálogos: exportar de nuevo las listas y correr
  `python build_catalogos.py <carpeta>`. El HTML generado **no se sube al repositorio**
  (el repositorio es público y el HTML contiene datos internos).
