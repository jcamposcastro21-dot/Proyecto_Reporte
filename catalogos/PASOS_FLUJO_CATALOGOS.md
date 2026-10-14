# Flujo: Exportar_Catalogos

Copia cada día las listas que usa la aplicación a archivos `.json` en una carpeta de OneDrive.
Claude lee esos archivos con el conector de Microsoft 365 y regenera la aplicación, sin exportar
nada a mano.

Todas las acciones son estándar (sin Premium). Sitio de lectura: `CL-SISSO_Plantas_Celulosa`.

## 1. Disparador: Periodicidad
- Intervalo `1`, frecuencia **Día**, zona horaria **Santiago**, a las `6:00`.

## 2. Redactar → renombrar a `Listas`
Entradas (texto, no fx). `lista` es el **título exacto** de la lista tal como aparece en
*Contenido del sitio*; `archivo` es el nombre del archivo que se guarda.
```json
[
  {"archivo": "plantas",              "lista": "Plantas Celulosas",     "consulta": "$top=5000"},
  {"archivo": "areas",                "lista": "Areas Plantas",         "consulta": "$top=5000"},
  {"archivo": "empresas",             "lista": "Empresas",              "consulta": "$top=5000"},
  {"archivo": "equipos",              "lista": "Equipos Seguros",       "consulta": "$top=5000"},
  {"archivo": "areas_pgp",            "lista": "Areas_PGP",             "consulta": "$top=5000"},
  {"archivo": "sistemas_pgp",         "lista": "Sistemas_PGP",          "consulta": "$top=5000"},
  {"archivo": "ot_pgp",               "lista": "OT_PGP",                "consulta": "$top=5000"},
  {"archivo": "ambitos",              "lista": "Ámbito",                "consulta": "$top=5000"},
  {"archivo": "eventos",              "lista": "Eventos",               "consulta": "$top=5000"},
  {"archivo": "acciones_inmediatas",  "lista": "Acciones_inmediatas",   "consulta": "$top=5000"},
  {"archivo": "acciones_correctivas", "lista": "Acciones_correctivas",  "consulta": "$top=5000"},
  {"archivo": "lideres",              "lista": "Correos Líderes",       "consulta": "$top=5000&$select=*,Lider/Title,Lider/EMail&$expand=Lider"}
]
```
Para sumar una lista (Coaching, Instancias, etc.) basta agregar una línea aquí.

## 3. Aplicar a cada uno → renombrar a `Por_cada_lista`
Seleccionar una salida (fx): `outputs('Listas')`

Dentro del ciclo:

### 3a. Enviar una solicitud HTTP a SharePoint → renombrar a `Leer_lista`
- Dirección del sitio: `CL-SISSO_Plantas_Celulosa`
- Método: `GET`
- URI (fx):
```
concat('_api/web/lists/getbytitle(''', items('Por_cada_lista')?['lista'], ''')/items?', items('Por_cada_lista')?['consulta'])
```
- Encabezados: `Accept` = `application/json;odata=nometadata`

### 3b. Enviar una solicitud HTTP a SharePoint → renombrar a `Guardar_archivo`
- Dirección del sitio (valor personalizado): la URL del OneDrive propio,
  `https://<inquilino>-my.sharepoint.com/personal/<usuario>`
- Método: `POST`
- URI (fx):
```
concat('_api/web/GetFolderByServerRelativeUrl(''<ruta de la carpeta Catalogos>'')/Files/add(url=''', items('Por_cada_lista')?['archivo'], '.json'',overwrite=true)')
```
- Encabezados: `Accept` = `application/json;odata=nometadata`
- Cuerpo (fx): `string(body('Leer_lista')?['value'])`

## Notas
- `$top=5000` es el máximo por consulta. Si una lista pasa de 5.000 registros, hay que leerla
  por tandas (`$filter=Id gt <último>`).
- Si un título está mal escrito, solo falla esa vuelta del ciclo; las demás listas se guardan igual.
  El historial de ejecuciones muestra cuál falló.
- Después de la primera ejecución se pueden achicar los archivos con `$select` en `consulta`
  (solo las columnas que usa la aplicación) y `$filter` (por ejemplo, OT activas).
