"""Reporte RIT (Reunión de Inicio de Turno) — calidad de levantamientos en SoftExpert.

Este módulo PREPARA los datos y la evaluación automática de cada RIT; el HTML (reporte/plantillas/rit_app.js)
calcula todos los indicadores en el navegador, para que los filtros recalculen todo de forma consistente.
El reporte es de CONSULTA: no modifica SoftExpert ni el Excel de origen.

Niveles de evaluación (no se mezclan ni se combinan en un puntaje único):
  1. ADHERENCIA — ¿se hizo el RIT que correspondía?  realizados / esperados por equipo y semana.
     · Esperados Mantención: días hábiles (lun–vie, sin feriados de config/rit.json).
     · Esperados Operación: días en que el turno está de día (D) o de noche (N) según config/rotacion_turnos.csv.
       DC (descanso) y AD (administrativo, no necesariamente lidera el RIT) no se exigen.
       La N del día X es la noche de 20:00 de X−1 a 08:00 de X: un RIT de las 20:00 o más tarde es del día siguiente.
     · Realizados: días distintos con RIT en un día exigido, con tope = esperados por equipo-semana
       (un día extra no compensa un día faltante de otra semana).
     · Se evalúa desde la semana de inicio general (todas las áreas registrando; S26 en 2026). Antes: etapa piloto.
     · Registros con equipo mal informado (Operación sin turno A–E, p. ej. "Electrocontrol L1") no cuentan.
  2. EJECUCIÓN Y TRAZABILIDAD — ¿el RIT quedó bien registrado y atribuible?
     · Trazabilidad: cuenta individual / cuenta compartida (config/cuentas_compartidas.csv, correos genéricos ce05.*)
       / sin identificación. Una cuenta compartida es un problema de trazabilidad, no de redacción.
     · Ejecución (componentes, se muestran por separado): tarea SoftExpert seleccionada (no "Notificar sin SE",
       "Agregar tarea en SE", "Parada de área/PGP"); formulario completo (respondió falta riesgo/control/tarea);
       registro oportuno (cargado entre 0 y 12 h después de la hora del RIT); RIT en día de su turno.
       "Registro completo" = las tres primeras condiciones a la vez.
  3. CALIDAD DE REDACCIÓN del hallazgo (EVALUACIÓN AUTOMÁTICA DE REDACCIÓN, no calidad técnica). Ver pauta_redaccion().
  4. PERTINENCIA TÉCNICA — no se puede inferir del texto: queda "Pendiente de validación técnica" salvo que exista
     una validación en config/validacion_tecnica.csv.
  5. EFECTIVIDAD — con los datos actuales solo: estado de la mejora en la lista (Abierta / Cerrada / No Aplica) y
     tareas con hallazgos repetidos. Aceptado / rechazado / requirió corrección: no disponible.

Cambios de definición respecto de la versión anterior (documentados):
  · Pauta 0–3 redefinida: 3 exige acción + elemento identificado + contexto (+ justificación si se elimina o modifica);
    frases con solo un verbo de acción ya no suben a 3. Las listas copiadas valen 0 (antes 1).
    "Hallazgo claro" pasa a llamarse "entendible" (>=2); "accionable" = 3.
  · Cuentas compartidas: además de "Operador …", se reconocen las cuentas genéricas del listado de correos
    (p. ej. "Despachador de Carga"), que antes se contaban como personas.
  · Adherencia: tope por equipo-semana (antes solo a nivel agregado) y desde la semana de inicio general.

Uso:
    python3 -m reporte.rit --planta "Nueva Aldea"              # abre en la última semana completa
    python3 -m reporte.rit --planta "Nueva Aldea" --semana 39 --json
"""
import argparse
import html
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
import pandas as pd

CONFIG = Path('config')
PLANTILLAS = Path(__file__).parent / 'plantillas'
TAREAS_GENERICAS = {'notificar sin se', 'notificar sin softexpert', 'agregar tarea en se', 'parada de área/pgp', 'parada de area/pgp'}
ITEMS = [('Riesgo', 'FaltaRiesgo', 'RiesgoTexto'), ('Control', 'FaltaControl', 'ControlTexto'), ('Tarea', 'FaltaTarea', 'NuevaTarea')]


def _st(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')


def txt(v):
    return v if isinstance(v, str) else ''


# ================================================================ nivel 3: evaluación automática de redacción
_COD = re.compile(r'\b(co-(adm|ing|epp)-\d+|sso-\d+|ftsso-[a-z]+-\d+|ce\d\d-[a-z0-9-]+|mam-\d+|[a-h]\.\d{2}\.\d{2,3}(\.\d{2,3})?'
                  r'|\d{2}\.\d{3}\.\d{3}[a-z0-9.]*|\d{2}-[a-z]{2,4}-\d+|p\.\d{2}\.\d{3}\.\d{3})\b')
_TAG = re.compile(r'\b(?=[a-z]*\d)(?=\d*[a-z])[a-z0-9]{2,}(-[a-z0-9]+)*\b')  # tags de equipo: tg2, hv940, 431-31-919
_ACC_CAMBIO = r'eliminar|elimina|quitar|retirar|borrar|sacar|modificar|cambiar|reemplazar|corregir|reubicar|separar|unificar|bajar'
_ACC_AGREGA = (r'agregar|agrega|agregara|agregra|incorporar|incluir|crear|generar|asociar|cargar|subir|vincular|definir|especificar|'
               r'actualizar|falta|faltan|hace falta|carece|se debe|se requiere|se sugiere|solicito')
_ACCION = re.compile(r'\b(' + _ACC_CAMBIO + '|' + _ACC_AGREGA + r'|no aplica|no corresponde|duplicad\w*|repetid\w*|sobra\w*)\b')
_CAMBIO = re.compile(r'\b(' + _ACC_CAMBIO + r'|no aplica|no corresponde|duplicad\w*|repetid\w*|sobra\w*)\b')
_OBJETO = re.compile(r'\b(riesgos?|controles?|control|documentos?|procedimientos?|instructivos?|hte|sop|check ?list|checklist|pautas?|fichas?|'
                     r'tareas?|epp|matriz|plan|protocolos?|permisos?|rutinas?|medidas?|estandar|formulario|registro|actividad(es)?)\b')
_JUST = re.compile(r'\b(porque|ya que|debido|dado que|puesto que|para (evitar|asegurar|que|controlar|el|la)|no aplica|no corresponde|se repite|'
                   r'repetid\w*|duplicad\w*|no existe|no tiene|no esta|no se realiza|ya no|actualmente|corresponde a|por (falta|no|ser|el|la|riesgo))\b')
# Vocabulario que NO identifica un elemento concreto (ámbitos, tipos de documento, verbos y relleno).
_GENERICO = set(_st(w) for w in '''sso ssoo ma pro prd eco myc lyr legal produccion productivo productivos productiva calidad ambiental ambito ambitos
control controles riesgo riesgos risgos falta faltan medida medidas de del y a la el los las para en con sin todas todos asociados asociadas asociado asociada
tarea tareas se no si hay existe existen agregar solicito eliminar incorporar incluir documento documentos documentacion plataforma revisar generar crear cargar
hte sop check list checklist procedimiento procedimientos instructivo instructivos pauta pautas ficha fichas faltantes faltante nuevo nueva nuevos nuevas
actividad actividades que es son al lo le debe deben requiere sugiere mejorar actualizar inspeccion inspecciones especificos especificas especifico
operacion operacional operacionales mantencion general generales seguridad salud aplica corresponde similar similares igual iguales plan protocolo matriz epp uso
registro formulario estandar estandares rutina rutinas permiso permisos otros otras etc favor dicha dicho esta este estos estas pendiente pendientes
licor fibra madera maquina efluentes caustificacion termica planta area areas realizar correspondientes correspondiente necesario necesarios'''.split())
REDACCION = {3: 'Clara y accionable', 2: 'Entendible pero incompleta', 1: 'Ambigua / genérica', 0: 'No utilizable'}


def elementos(texto, tarea_se=True):
    """Elementos detectados en el texto de un hallazgo (para la pauta y para mostrarlos en el detalle)."""
    s = _st(txt(texto)).strip()
    cods = _COD.findall(s)
    tags = _TAG.findall(s)
    palabras = set(w for w in re.findall(r'[a-z]{3,}', s) if w not in _GENERICO)
    accion = bool(_ACCION.search(s))
    objeto = bool(_OBJETO.search(s)) or bool(cods)
    ident = (len(palabras) + 2 * bool(cods) + 2 * bool(tags)) >= 2 or (objeto and len(palabras) >= 1)
    return dict(s=s, accion=accion, objeto=objeto, ident=ident,
                fuerte=bool(cods) or bool(tags) or len(palabras) >= 3,       # código, tag o >=3 términos específicos
                contexto=bool(tarea_se) or bool(re.search(r'\b(tarea|[a-h]\.\d{2}\.)', s)),  # el RIT ya tiene la tarea
                just=bool(_JUST.search(s)), lista=len(cods) >= 3 and not accion, cambio=bool(_CAMBIO.search(s)))


def pauta_redaccion(texto, tarea_se=True):
    """Evaluación automática de REDACCIÓN 0–3 (no evalúa si el hallazgo es técnicamente correcto).
    3 Clara y accionable: acción + elemento identificado + contexto (tarea) y, si se elimina o modifica algo, el porqué;
      si se agrega algo sin justificar, la identificación debe ser fuerte (código, tag o >=3 términos específicos).
    2 Entendible pero incompleta: identifica el elemento, pero falta la acción, el contexto o la justificación.
    1 Ambigua / genérica: menciona un tema ("riesgos SSO", "mejorar control") sin identificar el elemento exacto.
    0 No utilizable: vacío, lista copiada de SoftExpert sin acción, o no permite determinar qué se pide."""
    e = elementos(texto, tarea_se)
    s = e['s']
    if len(s) < 3 or s in ('nan', 's/o', 'so', 'na', 'n/a', 'x', 'si', 'no', 'ok'):
        return 0, 'Sin contenido: se marcó que falta algo, pero no se escribió qué.', e
    if e['lista']:
        return 0, 'Lista copiada de SoftExpert: no indica qué agregar, eliminar o modificar.', e
    if not e['objeto'] and not e['accion']:
        return 0, 'No permite determinar qué se solicita (no hay acción ni elemento de SoftExpert).', e
    if not e['ident']:
        return 1, 'Genérico: nombra un tema, pero no identifica el riesgo, control o documento exacto.', e
    falta = []
    if not e['accion']:
        falta.append('la acción (agregar, eliminar, modificar)')
    if not e['contexto']:
        falta.append('la tarea donde aplica')
    if e['cambio'] and not e['just']:
        falta.append('por qué se elimina o modifica')
    if not e['cambio'] and not e['just'] and not e['fuerte']:
        falta.append('la identificación exacta (código o nombre) o el motivo')
    if not falta:
        return 3, 'Claro y accionable: acción + elemento identificado + tarea' + (' + justificación.' if e['just'] else '.'), e
    return 2, 'Entendible, pero falta ' + ', '.join(falta) + '.', e


def version_sugerida(tipo, texto, tarea, e, nota):
    """Reescritura guiada con el formato [ACCIÓN] + [ELEMENTO EXACTO] + [TAREA] + [POR QUÉ].
    Solo usa lo que está en el registro; lo que falta queda entre corchetes para completar (no se inventa contenido)."""
    if nota == 3:
        return ''
    s = e['s']
    if e['cambio']:
        acc = 'Eliminar' if re.search(r'elimin|quitar|retirar|borrar|sacar|no aplica|no corresponde|duplicad|repetid|sobra', s) else 'Modificar'
    elif e['accion']:
        acc = 'Agregar'
    else:
        acc = '[Agregar / Eliminar / Modificar]'
    cods = [m.group(0).upper() for m in _COD.finditer(s)]
    if e['lista']:
        elem = f'[elegir el {tipo.lower()} concreto de la lista copiada, p. ej. {cods[0]}]'
    elif cods:
        elem = f'{tipo.lower()} {", ".join(cods[:2])} [nombre]'
    elif e['ident'] and nota >= 1:
        t = re.sub(r'\s+', ' ', txt(texto)).strip()
        elem = f'{tipo.lower()} «{t[:80]}»' + ('' if e['fuerte'] else ' [precisar código o nombre exacto]')
    else:
        elem = f'[{tipo.lower()} exacto: código y nombre en SoftExpert]'
    lugar = f'en la tarea «{tarea[:70]}»' if tarea else '[en la tarea …]'
    return f'{acc} {elem} {lugar}, porque [motivo: qué condición de la tarea lo hace necesario o innecesario].'


# ================================================================ carga
def cargar_rotacion(ruta=CONFIG / 'rotacion_turnos.csv'):
    """Calendario de turnos de Operación: {(fecha, turno): D | N | DC | AD | ''}."""
    if not Path(ruta).exists():
        return {}
    r = pd.read_csv(ruta, parse_dates=['fecha'], keep_default_na=False)
    return {(f, t): c for f, t, c in zip(r.fecha, r.turno, r.codigo)}


def cuentas_compartidas(ruta=CONFIG / 'cuentas_compartidas.csv'):
    if not Path(ruta).exists():
        return set()
    return set(_st(n).strip() for n in pd.read_csv(ruta).nombre)


def equipo_valido(especialidad, equipo):
    if especialidad == 'Operación':
        return bool(re.search(r'Turno [A-E]', str(equipo)))
    return bool(re.search(r'(Mecánico|Electrocontrol)', str(equipo))) and 'Turno' not in str(equipo)


def tipo_cuenta(nombre, compartidas):
    n = _st(nombre).strip()
    if not n or n in ('(sin creador)', 'nan'):
        return 'sinid'
    if n in compartidas or n.startswith('operador ') or n.startswith('volante '):
        return 'comp'
    return 'ind'


def cargar(ruta, planta, rot=None, compartidas=None):
    rot, compartidas = rot or {}, compartidas or set()
    d = pd.read_excel(ruta)
    d.columns = [c.strip() for c in d.columns]
    d = d[d.Planta == planta].copy()
    d['Fecha'] = pd.to_datetime(d.Fecha)
    d['Creado'] = pd.to_datetime(d.Creado)
    d['sin_fecha'] = d.Fecha.isna()  # sin fecha del RIT: se usa la de registro y no cuenta como oportuno
    d['Fecha'] = d.Fecha.fillna(d.Creado)
    d['Equipo'] = d.Equipo.fillna('(sin equipo)')
    d['Creado por'] = d['Creado por'].fillna('').map(lambda s: ' '.join(str(s).split()))
    d['cuenta'] = d['Creado por'].map(lambda n: tipo_cuenta(n, compartidas))
    d['dia'] = d.Fecha.dt.normalize()
    d['turno'] = d.Equipo.str.extract(r'Turno ([A-E])')[0]
    op = (d.Especialidad == 'Operación') & d.turno.notna()
    d.loc[op & (d.Fecha.dt.hour >= 20), 'dia'] = d.dia + pd.Timedelta(days=1)  # inicio del turno noche = jornada siguiente
    d['cod_turno'] = [rot.get((x, t)) if o else None for x, t, o in zip(d.dia, d.turno, op)]
    d['en_turno'] = ~op | d.cod_turno.isna() | d.cod_turno.isin(['D', 'N'])
    d['fuera_turno'] = op & d.cod_turno.notna() & ~d.cod_turno.isin(['D', 'N', 'AD'])  # registró en su día de descanso
    d['equipo_mal'] = [not equipo_valido(e, q) for e, q in zip(d.Especialidad, d.Equipo)]
    d['cuenta_adh'] = d.en_turno & ~d.equipo_mal
    d['semana'] = d.dia - pd.to_timedelta(d.dia.dt.dayofweek, unit='D')
    d['retraso_h'] = (d.Creado - d.Fecha).dt.total_seconds() / 3600
    d['oportuno'] = d.retraso_h.between(-0.5, 12) & ~d.sin_fecha
    d['tarea_se'] = ~d.Tarea.fillna('').str.strip().str.lower().isin(TAREAS_GENERICAS) & d.Tarea.notna()
    d['completo'] = d[['FaltaRiesgo', 'FaltaControl', 'FaltaTarea']].notna().all(axis=1)
    return d


def evaluar_items(r):
    out = []
    for tipo, flag, col in ITEMS:
        if r[flag] == 'Sí':
            n, motivo, e = pauta_redaccion(r[col], r.tarea_se)
            out.append(dict(t=tipo, x=txt(r[col]), n=n, m=motivo, el=[int(e[k]) for k in ('accion', 'objeto', 'ident', 'contexto', 'just')],
                            lista=int(e['lista']), jr=int(e['cambio'] or not e['fuerte']),  # jr: la justificación se exige
                            sug=version_sugerida(tipo, r[col], txt(r.Tarea), e, n)))
    return out


def cargar_top20(ruta, planta):
    if not ruta or not Path(ruta).exists():
        return []
    s = Path(ruta).read_text(encoding='utf-8')
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)
    L = [x.strip() for x in html.unescape(re.sub(r'<[^>]+>', '\n', t)).split('\n') if x.strip()]
    try:
        i = L.index(f'{planta} — Top 20')
    except ValueError:
        return []
    j = next((k for k in range(i + 1, len(L)) if L[k].endswith('— Top 20')), len(L))
    seg, filas = L[i:j], []
    for k, x in enumerate(seg):
        if x == 'Cantidad' and k >= 5:
            off = 1 if seg[k - 4] == '👥 turno' else 0
            filas.append(dict(rank=int(seg[k - 5 - off]), nombre=seg[k - 4 - off], area=seg[k - 3], esp=seg[k - 2], rol=seg[k - 1],
                              cantidad=float(seg[k + 1]), calidad=float(seg[k + 3]), frecuencia=float(seg[k + 5]), compartida=bool(off)))
    return filas


def esperados(especialidad, equipo, desde, hasta, cfg, rot):
    """Días de RIT exigidos al equipo entre desde y hasta (inclusive, recortado a la fecha de corte)."""
    hasta = min(pd.Timestamp(hasta), pd.Timestamp(cfg['_corte']))
    if hasta < desde or not equipo_valido(especialidad, equipo):
        return 0
    dias = pd.date_range(desde, hasta)
    if especialidad == 'Mantención':
        fer = set(pd.to_datetime(cfg.get('feriados', [])))
        return sum(1 for x in dias if x.dayofweek < 5 and x not in fer)
    t = re.search(r'Turno ([A-E])', equipo).group(1)
    n = 0.0
    for x in dias:
        c = rot.get((x, t))
        n += cfg.get('operacion_dias_por_dia', 0.4) if c is None else (1 if c in ('D', 'N') else 0)
    return round(n, 1)


# ================================================================ armado de datos para el HTML
def preparar(ruta, planta, cfg, top_ruta):
    rot = cargar_rotacion()
    d = cargar(ruta, planta, rot, cuentas_compartidas())
    cfg['_corte'] = str(d[d.Fecha.dt.hour < 20].dia.max().date())
    corte = pd.Timestamp(cfg['_corte'])
    lunes = list(pd.date_range(d.semana.min(), d.semana.max(), freq='7D'))
    num = {l: int(l.isocalendar().week) for l in lunes}
    # semana de inicio general: todas las áreas registrando en ambas especialidades
    if cfg.get('inicio_general_semana'):
        inicio = next(l for l in lunes if num[l] == int(cfg['inicio_general_semana']))
    else:
        tot = set(d.groupby(['Area', 'Especialidad']).size().index)
        inicio = next(l for l in lunes if set(d[d.semana == l].groupby(['Area', 'Especialidad']).size().index) >= tot)

    eqs = d[['Especialidad', 'Area', 'Equipo']].drop_duplicates().sort_values(['Especialidad', 'Area', 'Equipo']).reset_index(drop=True)
    key = {(r.Especialidad, r.Area, r.Equipo): i for i, r in enumerate(eqs.itertuples())}
    lider = d.groupby(['Especialidad', 'Area', 'Equipo']).LiderEquipo.agg(
        lambda s: s.dropna().map(lambda x: x.split(',')[0].split('@')[0].strip()).mode().iloc[0] if s.notna().any() else '')
    equipos = []
    for (esp, area, eq), k in key.items():
        t = re.search(r'Turno ([A-E])', eq)
        equipos.append(dict(k=k, esp=esp, area=area, eq=eq, tl=t.group(1) if t else '', valido=equipo_valido(esp, eq),
                            lider=lider.get((esp, area, eq), '')))
    esp_tab = {e['k']: {num[l]: esperados(e['esp'], e['eq'], l, l + pd.Timedelta(days=6), cfg, rot) for l in lunes if l >= inicio}
               for e in equipos if e['valido']}

    valid = {}
    vp = CONFIG / 'validacion_tecnica.csv'
    if vp.exists():
        for _, v in pd.read_csv(vp, dtype=str).fillna('').iterrows():
            valid.setdefault(v.ID, []).append(dict(item=v['item'], pert=v.pertinencia, impl=v.implementado, com=v.comentario, por=v.validador, f=v.fecha))

    regs = []
    for _, r in d.sort_values('Fecha').iterrows():
        it = evaluar_items(r)
        regs.append(dict(
            id=int(r.ID), s=num[r.semana], dia=r.dia.strftime('%Y-%m-%d'), fh=r.Fecha.strftime('%d-%m-%Y %H:%M'), hora=int(r.Fecha.hour),
            crt=r.Creado.strftime('%d-%m-%Y %H:%M') if pd.notna(r.Creado) else '', ret=round(float(r.retraso_h), 1) if pd.notna(r.retraso_h) else None,
            k=key[(r.Especialidad, r.Area, r.Equipo)], per=r['Creado por'] or '(sin identificación)', cta=r.cuenta,
            tarea=txt(r.Tarea), tse=int(r.tarea_se), cmp=int(r.completo), op=int(r.oportuno), ct=txt(r.cod_turno),
            en=int(r.cuenta_adh), fuera=int(r.fuera_turno), mal=int(r.equipo_mal),
            fr=txt(r.FaltaRiesgo), fc=txt(r.FaltaControl), ft=txt(r.FaltaTarea),
            h=int(len(it) > 0), n=min(i['n'] for i in it) if it else None, lista=int(any(i['lista'] for i in it)), it=it,
            est=txt(r.EstadoMejora), cc=txt(r.ComentarioCierre), tit=txt(r['Título']),
            impl=txt(r.Implementador), ing=txt(r.get('Ingeniero', '')), lid=txt(r.LiderEquipo)))

    semanas = [dict(n=num[l], lun=l.strftime('%Y-%m-%d'), dom=(l + pd.Timedelta(days=6)).strftime('%Y-%m-%d'),
                    parcial=bool(l + pd.Timedelta(days=6) > corte), piloto=bool(l < inicio)) for l in lunes]
    meta = dict(planta=planta, corte=cfg['_corte'], fuente=Path(ruta).name, generado=datetime.now().strftime('%d-%m-%Y %H:%M'),
                inicio=num[inicio], metas=cfg['metas'], categorias=cfg['categorias'], muestra=cfg.get('muestra_minima', 5),
                redaccion=REDACCION)
    return d, dict(meta=meta, semanas=semanas, equipos=equipos, esp=esp_tab, regs=regs, top20=cargar_top20(top_ruta, planta), valid=valid)


def main(argv=None):
    p = argparse.ArgumentParser(description='Reporte RIT: adherencia, ejecución, trazabilidad y calidad de redacción de hallazgos')
    p.add_argument('--planta', default='Nueva Aldea')
    p.add_argument('--semana', default=None, help='Semana que se abre por defecto (número ISO); por defecto, la última completa')
    p.add_argument('--excel', default=None)
    p.add_argument('--top20', default=None)
    p.add_argument('--comentarios', default=None, help='JSON {"S39": {"Planta": {"lectura": "...", "focos": [...]}}}')
    p.add_argument('--json', action='store_true', help='Además, guardar out/RIT_datos_<planta>.json con los datos evaluados')
    p.add_argument('--salida', default='out')
    a = p.parse_args(argv)

    cfg = json.loads((CONFIG / 'rit.json').read_text(encoding='utf-8'))
    ruta = Path(a.excel) if a.excel else sorted(Path('data').glob('RIT_*.xlsx'))[-1]
    top_ruta = a.top20 or next(iter(sorted(Path('data').glob('Top_usuarios*.html'))), None)
    d, datos = preparar(ruta, a.planta, cfg, top_ruta)
    completas = [s for s in datos['semanas'] if not s['parcial'] and not s['piloto']]
    datos['meta']['defecto'] = int(a.semana) if a.semana else (completas[-1]['n'] if completas else datos['semanas'][-1]['n'])
    datos['comentarios'] = json.loads(Path(a.comentarios).read_text(encoding='utf-8')) if a.comentarios else {}

    css = ''.join((Path('ref') / f).read_text(encoding='utf-8') for f in ('estilos_base.css', 'estilos_reporte.css')) + (PLANTILLAS / 'rit_app.css').read_text(encoding='utf-8')
    js = (PLANTILLAS / 'rit_app.js').read_text(encoding='utf-8')
    cuerpo = (PLANTILLAS / 'rit_app.html').read_text(encoding='utf-8')
    data_js = json.dumps(datos, ensure_ascii=False, default=str, separators=(',', ':')).replace('</', '<\\/')
    pag = cuerpo.replace('/*CSS*/', css).replace('/*DATOS*/', data_js).replace('/*JS*/', js).replace('{{PLANTA}}', html.escape(a.planta))
    out = Path(a.salida)
    out.mkdir(exist_ok=True)
    f = out / f'RIT_semanal_{a.planta.replace(" ", "_")}.html'
    f.write_text(pag, encoding='utf-8')
    print(f, f'({len(pag) // 1024} KB, {len(datos["regs"])} RIT, semanas {datos["semanas"][0]["n"]}–{datos["semanas"][-1]["n"]}, inicio general S{datos["meta"]["inicio"]})')
    if a.json:
        j = out / f'RIT_datos_{a.planta.replace(" ", "_")}.json'
        j.write_text(json.dumps(datos, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        print(j)


if __name__ == '__main__':
    main()
