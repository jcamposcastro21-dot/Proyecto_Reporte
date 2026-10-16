# Flujo: Exportar_Catalogos

Copia cada día las listas que usa la aplicación a archivos `.json` en una carpeta de OneDrive.
Claude lee esos archivos con el conector de Microsoft 365 y regenera la aplicación con
`app/build_app.py`, sin exportar nada a mano.

Todas las acciones son estándar (sin Premium). Sitio de lectura: `CL-SISSO_Plantas_Celulosa`.

## 1. Disparador: Periodicidad
- Intervalo `1`, frecuencia **Día**, zona horaria **Santiago**, a las `6:00`.

## 2. Redactar → renombrar a `Listas`
Entradas (texto, no fx). Cada línea es un archivo: `archivo` es el nombre con que se guarda y
`ruta` lo que se le pide a SharePoint (se agrega después de `_api/web/`).
```json
[
  {"archivo": "plantas",              "ruta": "lists/getbytitle('Plantas Celulosa')/items?$top=5000"},
  {"archivo": "areas",                "ruta": "lists/getbytitle('Areas Plantas')/items?$top=5000"},
  {"archivo": "empresas",             "ruta": "lists/getbytitle('Empresas')/items?$top=5000"},
  {"archivo": "equipos",              "ruta": "lists/getbytitle('Equipos Seguros')/items?$top=5000"},
  {"archivo": "areas_pgp",            "ruta": "lists/getbytitle('Areas_PGP')/items?$top=5000"},
  {"archivo": "sistemas_pgp",         "ruta": "lists/getbytitle('Sistemas_PGP')/items?$top=5000"},
  {"archivo": "ot_pgp",               "ruta": "lists/getbytitle('OT PGP')/items?$top=5000"},
  {"archivo": "ambitos",              "ruta": "lists/getbytitle('Ámbito')/items?$top=5000"},
  {"archivo": "eventos",              "ruta": "lists/getbytitle('Eventos')/items?$top=5000"},
  {"archivo": "acciones_inmediatas",  "ruta": "lists/getbytitle('Acciones_inmediatas')/items?$top=5000"},
  {"archivo": "acciones_correctivas", "ruta": "lists/getbytitle('Acciones_correctivas')/items?$top=5000"},
  {"archivo": "lideres",              "ruta": "lists/getbytitle('Correos Líderes')/items?$top=5000&$select=*,Lider/Title,Lider/EMail&$expand=Lider"},
  {"archivo": "campos_instancias",    "ruta": "lists/getbytitle('Instancias')/fields?$filter=Hidden eq false and ReadOnlyField eq false"},
  {"archivo": "campos_coaching",      "ruta": "lists/getbytitle('Coaching Contactos Seguridad')/fields?$filter=Hidden eq false and ReadOnlyField eq false"},
  {"archivo": "campos_contactos",     "ruta": "lists/getbytitle('Contactos de Seguridad')/fields?$filter=Hidden eq false and ReadOnlyField eq false"},
  {"archivo": "listas_sitio",         "ruta": "lists?$filter=Hidden eq false&$select=Id,Title,ItemCount"}
]
```
- Los títulos entre comillas simples deben ser **iguales** a los de *Contenido del sitio*.
- Los archivos `campos_*` traen la definición de las columnas: de ahí salen las opciones de las
  preguntas de Instancias y Coaching.
- Para sumar una lista basta agregar una línea aquí.

## 3. Aplicar a cada uno → renombrar a `Por_cada_lista`
Seleccionar una salida (fx): `outputs('Listas')`

Dentro del ciclo:

### 3a. Enviar una solicitud HTTP a SharePoint → renombrar a `Leer_Lista`
- Dirección del sitio: `CL-SISSO_Plantas_Celulosa`
- Método: `GET`
- URI (fx):
```
concat('_api/web/', items('Por_cada_lista')?['ruta'])
```
- Encabezados: `Accept` = `application/json;odata=nometadata`

### 3b. OneDrive para la Empresa → Crear archivo → renombrar a `Guardar_Archivo`
- Ruta de acceso de la carpeta: la carpeta `Catalogos` del OneDrive propio.
- Nombre de archivo (fx): `concat(items('Por_cada_lista')?['archivo'], '.json')`
- Contenido del archivo (fx): `string(body('Leer_Lista')?['value'])`

Esta acción reemplaza el archivo si ya existe.

## Notas
- `$top=5000` es el máximo por consulta. Si una lista pasa de 5.000 registros hay que leerla por
  tandas (`$filter=Id gt <último>`). Hoy la más grande es OT PGP, con unos 2.300.
- Si un título está mal escrito, solo falla esa vuelta del ciclo; los demás archivos se guardan
  igual. El historial de ejecuciones muestra cuál falló.
- Las acciones deben quedar **dentro** del ciclo; si quedan fuera, el flujo no se guarda
  (error `InvalidTemplate`).
- "Enviar una solicitud HTTP a SharePoint" contra el OneDrive personal devuelve
  `MovedPermanently`; por eso el guardado usa la acción de OneDrive.
