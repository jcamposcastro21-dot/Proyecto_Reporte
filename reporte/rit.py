"""Reporte semanal de calidad de levantamientos RIT (Reunión de Inicio de Turno) en SoftExpert.

Separa dos cosas distintas:
  1. Adherencia a la práctica: ¿se hace y se registra el RIT? (días con registro vs. esperados,
     registro oportuno, tarea de SoftExpert seleccionada, formulario completo).
  2. Calidad de los hallazgos informados: cuando se reporta que falta (o sobra) un riesgo, control o
     tarea en SoftExpert, ¿se entiende qué se pide? (pauta 0–3 por hallazgo).

Uso:
    python3 -m reporte.rit --planta "Nueva Aldea"                 # última semana completa
    python3 -m reporte.rit --planta "Nueva Aldea" --semana 2026-09-22 --json
    python3 -m reporte.rit --semana 2026-09-22 --comentarios comentarios/rit_2026-09-22.json
"""
import argparse
import html
import json
import re
import unicodedata
from pathlib import Path
import pandas as pd

CONFIG = Path('config')
TAREAS_GENERICAS = {'notificar sin se', 'notificar sin softexpert', 'agregar tarea en se', 'parada de área/pgp', 'parada de area/pgp'}
ITEMS = [('Riesgo', 'FaltaRiesgo', 'RiesgoTexto'), ('Control', 'FaltaControl', 'ControlTexto'), ('Tarea', 'FaltaTarea', 'NuevaTarea')]
PAUTA = {0: 'Sin contenido: se marca "Sí" pero no dice nada',
         1: 'No se entiende qué hacer: solo el ámbito, genérico o lista pegada de SoftExpert sin acción',
         2: 'Identifica el elemento, pero no dice qué hacer con él',
         3: 'Claro y accionable: acción + elemento específico (y motivo)'}


def _st(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')


def esc(s):
    return html.escape(str(s)) if s is not None and not (isinstance(s, float) and pd.isna(s)) else ''


def fmt(d):
    return d.strftime('%d-%m') if pd.notna(d) else '—'


# ================================================================ pauta de hallazgos
_COD = re.compile(r'\b(co-(adm|ing|epp)-\d+|sso-\d+|ftsso-[a-z]+-\d+|ce00-[a-z0-9-]+|[a-h]\.\d{2}\.\d{2,3}(\.\d{2})?|\d{2}\.\d{3}\.\d{3}|\d{2}-[a-z]{2,4}-\d+)\b')
_ACCION = re.compile(r'\b(agregar|agrega|agregara|eliminar|elimina|quitar|borrar|sacar|incorporar|incluir|crear|generar|modificar|actualizar|cambiar|'
                     r'especificar|corregir|asociar|separar|reemplazar|reubicar|unificar|definir|subir|cargar|vincular|falta(n)? (agregar|incorporar|incluir|el|la|los|las|un|una)|'
                     r'falta|faltan|hace falta|se debe|se requiere|se sugiere|retirar|no (aplica|corresponde|abre)|duplicad|repetid|sobra)\w*')
_GENERICO = set(_st(w) for w in '''sso ma pro prd eco myc legal produccion productivo productivos productiva calidad ambiental control controles riesgo riesgos falta faltan
medida medidas de del y a la el los las para en con sin todas todos asociados asociadas asociado tarea tareas se no si hay existe existen ambito ambitos
agregar solicito eliminar incorporar documento documentos plataforma revisar generar y/o hte check list checklist procedimiento faltantes faltante
nuevo nueva nuevos actividad actividades que es son al lo le'''.split())


def pauta_hallazgo(texto):
    """0–3 + motivo. Evalúa si un implementador entiende qué cambiar en SoftExpert sin preguntar."""
    s = _st(texto if isinstance(texto, str) else '').strip()
    if len(s) < 3 or s in ('nan', 's/o', 'so', 'na', 'n/a', 'x', 'si', 'sí'):
        return 0, 'sin contenido'
    codigos = len(_COD.findall(s))
    accion = bool(_ACCION.search(s))
    palabras = [w for w in re.findall(r'[a-z]{3,}', s) if w not in _GENERICO]
    if codigos >= 3 and not accion:
        return 1, 'lista pegada de SoftExpert sin decir qué hacer'
    especifico = codigos >= 1 or len(palabras) >= (2 if accion else 3)
    if not especifico:
        return 1, 'genérico: solo el ámbito o "faltan controles" sin decir cuáles'
    if accion:
        return 3, 'acción + elemento específico'
    return 2, 'identifica el elemento, falta la acción'


def sugerencia(tipo, nota):
    base = {'Riesgo': 'Agregar/Eliminar riesgo «nombre del riesgo» (ámbito) en la tarea, porque …',
            'Control': 'Agregar/Eliminar control «código + nombre» al riesgo «…» de la tarea, porque …',
            'Tarea': 'Crear tarea «verbo + objeto + equipo» en el subproceso «…», porque hoy no existe'}[tipo]
    return {0: f'Escribir qué falta. Formato: {base}',
            1: f'Nombrar el elemento exacto y la acción. Formato: {base}',
            2: f'Agregar la acción (agregar, eliminar, modificar) y el motivo. Formato: {base}',
            3: 'Bien redactado: se entiende qué cambiar.'}[nota]


# ================================================================ carga y preparación
def cargar_rotacion(ruta=CONFIG / 'rotacion_turnos.csv'):
    """Calendario de turnos de Operación: {(fecha, turno): D | N | DC | AD | ''}.
    N en el día X = noche que termina el día X (20:00 de X-1 a 08:00 de X)."""
    if not Path(ruta).exists():
        return {}
    r = pd.read_csv(ruta, parse_dates=['fecha'], keep_default_na=False)
    return {(f, t): c for f, t, c in zip(r.fecha, r.turno, r.codigo)}


def cargar(ruta, planta, rot=None):
    rot = rot or {}
    d = pd.read_excel(ruta)
    d.columns = [c.strip() for c in d.columns]
    d = d[d.Planta == planta].copy()
    d['Fecha'] = pd.to_datetime(d.Fecha)
    d['Creado'] = pd.to_datetime(d.Creado)
    d['sin_fecha'] = d.Fecha.isna()  # sin fecha del RIT: se usa la de registro y no cuenta como oportuno
    d['Fecha'] = d.Fecha.fillna(d.Creado)
    d['Equipo'] = d.Equipo.fillna('(sin equipo)')
    d['dia'] = d.Fecha.dt.normalize()
    # Operación: un RIT de las 20:00 o más tarde es el inicio del turno noche, que pertenece a la jornada del día siguiente
    d['turno'] = d.Equipo.str.extract(r'Turno ([A-E])')[0]
    op = (d.Especialidad == 'Operación') & d.turno.notna()
    d.loc[op & (d.Fecha.dt.hour >= 20), 'dia'] = d.dia + pd.Timedelta(days=1)
    d['cod_turno'] = [rot.get((x, t)) if o else None for x, t, o in zip(d.dia, d.turno, op)]
    # día que cuenta para adherencia: en Operación solo si el turno estaba de día (D) o de noche (N) según el calendario;
    # sin calendario para esa fecha, se cuenta igual
    d['en_turno'] = ~op | d.cod_turno.isna() | d.cod_turno.isin(['D', 'N'])
    # AD = administrativo: no necesariamente lidera el RIT; no se exige ni se marca como falta. DC = descanso: registro fuera de turno.
    d['fuera_turno'] = op & d.cod_turno.notna() & ~d.cod_turno.isin(['D', 'N', 'AD'])
    # equipo mal registrado: Operación sin turno A–E, o Mantención con turno / sin equipo; no entra a la adherencia
    d['equipo_mal'] = d.apply(lambda r: not equipo_valido(r.Especialidad, r.Equipo), axis=1)
    d['dia_adh'] = d.dia.where(d.en_turno & ~d.equipo_mal)
    d['semana'] = d.dia - pd.to_timedelta(d.dia.dt.dayofweek, unit='D')
    d['Creado por'] = d['Creado por'].fillna('(sin creador)').map(lambda s: ' '.join(str(s).split()))
    d['compartida'] = d['Creado por'].str.lower().str.startswith('operador')
    d['retraso_h'] = (d.Creado - d.Fecha).dt.total_seconds() / 3600
    d['oportuno'] = d.retraso_h.between(-0.5, 12) & ~d.sin_fecha
    d['tarea_se'] = ~d.Tarea.fillna('').str.strip().str.lower().isin(TAREAS_GENERICAS) & d.Tarea.notna()
    d['completo'] = d[['FaltaRiesgo', 'FaltaControl', 'FaltaTarea']].notna().all(axis=1)
    notas, motivos, n_h = [], [], []
    for _, r in d.iterrows():
        ns, ms = [], []
        for tipo, flag, txt in ITEMS:
            if r[flag] == 'Sí':
                n, m = pauta_hallazgo(r[txt])
                ns.append(n)
                ms.append(f'{tipo}: {m}')
        notas.append(min(ns) if ns else None)
        motivos.append('; '.join(ms))
        n_h.append(len(ns))
    d['nota'] = notas
    d['motivo'] = motivos
    d['n_hallazgos'] = n_h
    d['hallazgo'] = d.n_hallazgos > 0
    d['claro'] = d.nota >= 2
    return d


def cargar_top20(ruta, planta):
    if not ruta or not Path(ruta).exists():
        return pd.DataFrame(columns=['rank', 'nombre', 'area', 'esp', 'rol', 'cantidad', 'calidad', 'frecuencia', 'razon'])
    s = Path(ruta).read_text(encoding='utf-8')
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)
    L = [x.strip() for x in html.unescape(re.sub(r'<[^>]+>', '\n', t)).split('\n') if x.strip()]
    try:
        i = L.index(f'{planta} — Top 20')
    except ValueError:
        return cargar_top20(None, planta)
    j = next((k for k in range(i + 1, len(L)) if L[k].endswith('— Top 20')), len(L))
    seg, filas = L[i:j], []
    for k, x in enumerate(seg):
        if x == 'Cantidad' and k >= 5:
            off = 1 if seg[k - 4] == '👥 turno' else 0
            filas.append(dict(rank=int(seg[k - 5 - off]), nombre=seg[k - 4 - off], area=seg[k - 3], esp=seg[k - 2], rol=seg[k - 1],
                              cantidad=float(seg[k + 1]), calidad=float(seg[k + 3]), frecuencia=float(seg[k + 5]), razon=seg[k + 6]))
    return pd.DataFrame(filas)


def equipo_valido(especialidad, equipo):
    if especialidad == 'Operación':
        return bool(re.search(r'Turno [A-E]', str(equipo)))
    return bool(re.search(r'(Mecánico|Electrocontrol)', str(equipo))) and 'Turno' not in str(equipo)


def esperados(especialidad, desde, hasta, cfg, equipo=None):
    """Días de RIT esperados por equipo entre desde y hasta (inclusive).
    Mantención: días hábiles. Operación: días en que el turno está de día (D) o de noche (N) según
    config/rotacion_turnos.csv; los días AD, DC o sin turno no se esperan. Fuera del calendario: 0,4 por día."""
    if cfg.get('_corte'):
        hasta = min(pd.Timestamp(hasta), pd.Timestamp(cfg['_corte']))
    dias = pd.date_range(desde, hasta)
    if equipo is not None and not equipo_valido(especialidad, equipo):
        return 0
    if especialidad == 'Mantención':
        fer = set(pd.to_datetime(cfg.get('feriados', [])))
        return sum(1 for x in dias if x.dayofweek < 5 and x not in fer)
    rot = cfg.get('_rot', {})
    t = re.search(r'Turno ([A-E])', equipo or '')
    if t and rot:
        n = 0.0
        for x in dias:
            c = rot.get((x, t.group(1)))
            n += cfg.get('operacion_dias_por_dia', 0.4) if c is None else (1 if c in ('D', 'N') else 0)
        return round(n, 1)
    return round(len(dias) * cfg.get('operacion_dias_por_dia', 0.4), 1)


# ================================================================ indicadores
def indicadores(df, esp_dias):
    """esp_dias: días esperados del conjunto (suma de los equipos)."""
    h = df[df.hallazgo]
    dias_rit = df.groupby(['Area', 'Especialidad', 'Equipo']).dia_adh.nunique().sum() if len(df) else 0
    pct = lambda a, b: round(100 * a / b) if b else None
    return dict(reg=len(df), dias=int(dias_rit), esp=esp_dias, pAdh=min(100, pct(dias_rit, esp_dias)) if esp_dias else None,
                pOport=pct(df.oportuno.sum(), len(df)), pTarea=pct(df.tarea_se.sum(), len(df)), pComp=pct(df.completo.sum(), len(df)),
                hall=len(h), pHall=pct(len(h), len(df)), claros=int(h.claro.sum()), pClaro=pct(h.claro.sum(), len(h)),
                nota=round(float(h.nota.mean()), 1) if len(h) else None, n0=int((h.nota == 0).sum()), n1=int((h.nota == 1).sum()),
                pegadas=int(h.motivo.str.contains('lista pegada').sum()), personas=df.loc[~df.compartida, 'Creado por'].nunique(),
                fuera=int((df.fuera_turno | df.equipo_mal).sum()))


def tabla_equipos(d, desde, hasta, cfg):
    filas = []
    for (a, e, q), g in d.groupby(['Area', 'Especialidad', 'Equipo']):
        esp = esperados(e, desde, hasta, cfg, q)
        ind = indicadores(g, esp)
        lider = g.LiderEquipo.dropna().map(lambda s: s.split(',')[0].split('@')[0]).mode()
        filas.append(dict(Area=a, Especialidad=e, Equipo=q, lider=lider.iloc[0] if len(lider) else '', **ind))
    return pd.DataFrame(filas)


def cuadrante(adh, claro, hall, cfg):
    u = cfg['umbrales']
    if adh is None:
        return 'sin_datos'
    if hall == 0:
        return 'sin_hallazgos' if adh >= u['adherencia'][1] else 'apoyo'
    alta_a, alta_c = adh >= u['adherencia'][0], (claro or 0) >= u['claridad'][0]
    return {(True, True): 'referente', (True, False): 'redaccion', (False, True): 'constancia', (False, False): 'apoyo'}[(alta_a, alta_c)]


CUAD = {'referente': ('Referentes', 'ok', 'Hacen el RIT con constancia y sus hallazgos se entienden.'),
        'redaccion': ('Constantes, pero no se entiende lo que piden', 'amb', 'Registran, pero sus hallazgos son genéricos o listas pegadas: apoyar redacción.'),
        'constancia': ('Claros, pero sin constancia', 'amb', 'Cuando levantan, se entiende; falta disciplina en la práctica.'),
        'sin_hallazgos': ('Registran sin encontrar nada', 'az', 'Adherencia buena, pero 0 hallazgos en 4 semanas: confirmar que la revisión es real y no un registro por cumplir.'),
        'apoyo': ('Requieren apoyo', 'red', 'Baja adherencia y hallazgos poco claros o inexistentes.'),
        'sin_datos': ('Sin datos', 'gray', '')}


# ================================================================ HTML
def pill(v, k, cfg, sufijo='%'):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return '<span class="pill gray">s/d</span>'
    v = int(round(v))
    g, w = cfg['umbrales'][k]
    return f'<span class="pill {"ok" if v >= g else "amb" if v >= w else "red"}">{v}{sufijo}</span>'


def delta(a, b, inv=False):
    if a is None or b is None:
        return ''
    d = a - b
    if d == 0:
        return '<small class="dl">= sem. ant.</small>'
    bueno = d < 0 if inv else d > 0
    return f'<small class="dl {"up" if bueno else "down"}">{"▲" if d > 0 else "▼"} {abs(d)} pts</small>'


def kpi(label, valor, sub, color=''):
    return f'<div class="card kpi"><div class="kpi-label">{label}</div><div class="kpi-value num {color}">{valor}</div><div class="kpi-sub">{sub}</div></div>'


def ul(items):
    return '<ul>' + ''.join(f'<li>{x}</li>' for x in items) + '</ul>' if items else '<p class="ev-meta">Sin elementos.</p>'


def colk(v, k, cfg):
    if v is None:
        return ''
    g, w = cfg['umbrales'][k]
    return '' if v >= g else 'amb' if v >= w else 'red'


def tendencia(serie):
    """Mini barras de adherencia de las últimas semanas."""
    if not serie:
        return ''
    b = ''.join(f'<i title="{fmt(s)}: {v if v is not None else "s/d"}%" style="height:{max(2, (v or 0) * 0.22):.0f}px;background:'
                f'{"var(--ok)" if (v or 0) >= 90 else "var(--naranja)" if (v or 0) >= 70 else "var(--rojo)"}"></i>' for s, v in serie)
    return f'<span class="spark">{b}</span>'


def fila_equipo(r, cfg, serie, nivel=0):
    pad = '&nbsp;' * 4 * nivel
    nombre = f'{pad}{"↳ " if nivel else ""}{esc(r["nombre"])}'
    data = f' class="clic" data-eq="{esc(r["clave"])}"' if r.get('clave') else ''
    t = 'b' if nivel == 0 and not r.get('clave') else 'span'
    return (f'<tr{data}><td><{t}>{nombre}</{t}>{"<div class=ev-meta>" + esc(r["lider"]) + "</div>" if r.get("lider") else ""}</td>'
            f'<td class="num">{r["reg"]}</td><td class="num">{r["dias"]}/{r["esp"]:g}</td><td class="num">{pill(r["pAdh"], "adherencia", cfg) if r["esp"] else SIN_TURNO}</td>'
            f'<td class="num">{pill(r["pOport"], "oportuno", cfg)}</td><td class="num">{pill(r["pTarea"], "tarea_se", cfg)}</td>'
            f'<td class="num">{r["hall"]} <small>({int(r["pHall"]) if r["pHall"] is not None else "s/d"}%)</small></td>'
            f'<td class="num">{pill(r["pClaro"], "claridad", cfg)} <small>{r["claros"]}/{r["hall"]}</small></td>'
            f'<td class="num">{r["pegadas"] or "—"}</td><td>{tendencia(serie)}</td></tr>')


SIN_TURNO = '<span class="pill gray" title="El turno no estuvo de día ni de noche esta semana (descanso o administrativo): no se evalúa">sin turno</span>'

CAB = ('<tr><th>Área / Especialidad / Equipo</th><th>Registros</th><th>Días RIT / esperados</th><th>Adherencia</th><th>Registro oportuno</th>'
       '<th>Tarea SE seleccionada</th><th>Con hallazgo</th><th>Hallazgos claros (≥2)</th><th>Listas pegadas</th><th>Adherencia 8 sem.</th></tr>')


def bloque_tabla(dsem, eq_sem, series, cfg, area=None):
    filas = ''
    areas = [area] if area else sorted(eq_sem.Area.unique())
    for a in areas:
        ea = eq_sem[eq_sem.Area == a]
        da = dsem[dsem.Area == a]
        filas += fila_equipo(dict(nombre=a, lider='', **indicadores(da, ea.esp.sum())), cfg, series.get((a,)), 0)
        for e in ('Operación', 'Mantención'):
            ee = ea[ea.Especialidad == e]
            if not len(ee):
                continue
            filas += fila_equipo(dict(nombre=e, lider='', **indicadores(da[da.Especialidad == e], ee.esp.sum())), cfg, series.get((a, e)), 1)
            for _, r in (ee.sort_values('Equipo').iterrows() if area else []):
                clave = f'{a}|{e}|{r.Equipo}'
                filas += fila_equipo(dict(r, nombre=r.Equipo, clave=clave), cfg, series.get((a, e, r.Equipo)), 2)
    return f'<div class="card scroll"><table>{CAB}{filas}</table></div>'


def bloque_cuadrantes(eq4, cfg):
    cards = ''
    for k in ('referente', 'redaccion', 'constancia', 'sin_hallazgos', 'apoyo'):
        g = eq4[eq4.cuad == k].sort_values(['pAdh', 'pClaro'], ascending=False)
        tit, col, txt = CUAD[k]
        chips = ''.join(f'<span class="chip {col} clic" data-eq="{esc(r.clave)}" title="Adherencia {r.pAdh}% · claros {int(r.pClaro) if r.pClaro is not None else "s/d"}% · {r.hall} hallazgos">'
                        f'{esc(r.Area)} · {esc(r.Equipo)}</span> ' for _, r in g.iterrows())
        cards += f'<div class="card card-pad cq cq-{col}"><h3 class="card-h">{tit} ({len(g)})</h3><div class="ev-meta" style="margin-bottom:8px">{txt}</div>{chips or "<span class=ev-meta>—</span>"}</div>'
    return f'<div class="cuad">{cards}</div>'


def bloque_personas(p, top, cfg, limite=12):
    if not len(p):
        return '<div class="card vacio">Sin datos.</div>'

    def filas(df):
        out = ''
        for _, r in df.head(limite).iterrows():
            t = top[top.nombre.str.lower() == r.persona.lower()]
            tt = f'<span class="chip ok" title="Top 20 piloto: cantidad {t.iloc[0].cantidad:g}, calidad {t.iloc[0].calidad:g}, frecuencia {t.iloc[0].frecuencia:g}">Top 20 #{int(t.iloc[0]["rank"])}</span>' if len(t) else ''
            ej = f'<div class="ev-meta">«{esc(str(r.ejemplo)[:110])}»</div>' if r.ejemplo else ''
            out += (f'<tr class="clic" data-per="{esc(r.persona)}"><td>{esc(r.persona)} {"👥" if r.compartida else ""} {tt}<div class="ev-meta">{esc(r.areas)}</div>{ej}</td>'
                    f'<td class="num">{r.reg}</td><td class="num">{r.semanas}/4</td><td class="num">{r.hall}</td>'
                    f'<td class="num">{pill(r.pClaro, "claridad", cfg)}</td><td class="num">{r.nota if r.nota is not None else "s/d"}</td></tr>')
        return out
    cab = '<tr><th>Persona</th><th>Registros 4 sem.</th><th>Semanas activas</th><th>Hallazgos</th><th>Hallazgos claros</th><th>Pauta media</th></tr>'
    ref = p[(p.hall >= cfg['personas']['min_hallazgos']) & (p.pClaro >= cfg['umbrales']['claridad'][0]) & ~p.compartida].sort_values(['pClaro', 'hall'], ascending=False)
    apo = p[(p.hall >= cfg['personas']['min_hallazgos']) & (p.pClaro < cfg['umbrales']['claridad'][1])].sort_values(['pClaro', 'hall'], ascending=[True, False])
    return (f'<div class="card blk b-ok"><h3>✅ Entienden el propósito (referentes)</h3><div class="scroll"><table>{cab}{filas(ref)}</table></div></div>'
            f'<div class="card blk b-red" style="margin-top:14px"><h3>🤝 Requieren acompañamiento en la redacción</h3><div class="scroll"><table>{cab}{filas(apo)}</table></div></div>'
            f'<div class="ev-meta" style="margin-top:6px">Últimas 4 semanas, mínimo {cfg["personas"]["min_hallazgos"]} hallazgos. 👥 = cuenta compartida por turno: '
            'no permite saber quién redactó; conviene que cada persona use su cuenta. Clic en una persona para ver sus levantamientos.</div>')


def bloque_top20(top, p, cfg):
    if not len(top):
        return '<div class="card vacio">No se encontró el reporte Top 20 de la planta en data/.</div>'
    filas = ''
    for _, t in top.iterrows():
        q = p[p.persona.str.lower() == t.nombre.lower()]
        r = q.iloc[0] if len(q) else None
        lectura = '—'
        if r is not None and r.hall:
            lectura = ('Se sostiene' if (r.pClaro or 0) >= cfg['umbrales']['claridad'][0] else 'Bajó la claridad' if (r.pClaro or 0) < cfg['umbrales']['claridad'][1] else 'Claridad media')
        elif r is not None:
            lectura = 'Activo, sin hallazgos'
        else:
            lectura = 'Sin actividad en 4 semanas'
        filas += (f'<tr class="{"clic" if r is not None else ""}" data-per="{esc(t.nombre) if r is not None else ""}"><td class="num">{int(t["rank"])}</td><td>{esc(t.nombre)}<div class="ev-meta">{esc(t.area)} · {esc(t.esp)} · {esc(t.rol)}</div></td>'
                  f'<td class="num">{t.cantidad:g}</td><td class="num">{t.calidad:g}</td><td class="num">{t.frecuencia:g}</td>'
                  f'<td class="num">{r.reg if r is not None else 0}</td><td class="num">{r.semanas if r is not None else 0}/4</td>'
                  f'<td class="num">{pill(r.pClaro, "claridad", cfg) if r is not None else "—"}</td><td>{lectura}</td></tr>')
    return ('<div class="card scroll"><table><tr><th>#</th><th>Persona (Top 20 piloto)</th><th>Cantidad</th><th>Calidad</th><th>Frecuencia</th>'
            f'<th>Registros 4 sem.</th><th>Semanas activas</th><th>Hallazgos claros (pauta RIT)</th><th>Lectura</th></tr>{filas}</table></div>'
            '<div class="ev-meta" style="margin-top:6px">Cantidad, calidad y frecuencia vienen del reporte "Top usuarios SoftExpert" (selección para el piloto de la nueva plataforma). '
            'Las columnas siguientes las calcula este reporte con la pauta RIT, para ver si su calidad se sostiene.</div>')


def bloque_ejemplos(h, n=5):
    if not len(h):
        return '<div class="card vacio">Sin hallazgos en la semana.</div>'
    def lista(df):
        return ''.join(f'<li class="clic" data-reg="{int(r.ID)}"><span class="chip {"ok" if r.nota >= 2 else "red"}">{int(r.nota)}/3</span> '
                       f'<b>{esc(r.Area)} · {esc(r.Equipo)}</b> — {esc(r["Creado por"])}<br><span class="txtq">«{esc(texto_hallazgo(r)[:220])}»</span>'
                       f'<div class="ev-meta">{esc(r.motivo)}</div></li>' for _, r in df.head(n).iterrows())
    buenos = h[h.nota == 3].assign(l=lambda x: x.apply(lambda r: len(texto_hallazgo(r)), axis=1)).sort_values('l', ascending=False)
    malos = h[h.nota <= 1].sort_values('nota')
    return (f'<div class="two-col even"><div class="card blk b-ok"><h3>👍 Así se entiende (pauta 3)</h3><ul class="ej">{lista(buenos)}</ul></div>'
            f'<div class="card blk b-red"><h3>✍ Así no se entiende qué hacer (pauta 0–1)</h3><ul class="ej">{lista(malos)}</ul>'
            '<div class="ideas-fuerza-note">Formato sugerido: <b>[Agregar / Eliminar / Modificar] + [riesgo, control o documento exacto: código y nombre] + [en la tarea …] + [porque …]</b>. '
            'Ej.: «Agregar control CO-ADM-3944 Instructivo descarga de químicos al riesgo SSO-034 de la tarea G.02.03.15, porque incluye descarga desde camión».</div></div></div>')


def texto_hallazgo(r):
    return ' | '.join(f'{t}: {r[c]}' for t, f, c in ITEMS if r[f] == 'Sí' and isinstance(r[c], str)) or '(sin texto)'


def focos_auto(eq_sem, eq4, ind, ind_ant, h):
    f = []
    baja = eq_sem[(eq_sem.pAdh.notna()) & (eq_sem.pAdh < 70)].sort_values('pAdh')
    if len(baja):
        f.append(f'<b>Adherencia bajo 70% en {len(baja)} equipos</b>: ' + ', '.join(f'{esc(r.Area)} {esc(r.Equipo)} ({r.dias}/{r.esp:g} días)' for _, r in baja.head(6).iterrows())
                 + '. Confirmar con el jefe de especialidad o de turno que el RIT se hace y se registra cada turno.')
    sh = eq4[eq4.cuad == 'sin_hallazgos']
    if len(sh):
        f.append(f'<b>{len(sh)} equipos registran sin encontrar nada en 4 semanas</b> (' + ', '.join(f'{esc(r.Area)} {esc(r.Equipo)}' for _, r in sh.head(6).iterrows())
                 + '): acompañar un RIT y verificar que se abre la tarea en SoftExpert y se revisan riesgos y controles en todos los ámbitos.')
    if ind['n0'] + ind['n1']:
        f.append(f'<b>{ind["n0"] + ind["n1"]} de {ind["hall"]} hallazgos no se entienden</b> ({ind["pegadas"]} son listas pegadas de SoftExpert): '
                 'pedir el formato acción + elemento exacto + motivo; el implementador no debería tener que preguntar.')
    if ind_ant and ind['pAdh'] is not None and ind_ant['pAdh'] is not None and ind['pAdh'] < ind_ant['pAdh'] - 5:
        f.append(f'<b>La adherencia de la planta bajó {ind_ant["pAdh"] - ind["pAdh"]} puntos</b> respecto de la semana anterior.')
    return f[:4]


def datos_detalle(d4, eq_claves):
    regs = {}
    for _, r in d4.iterrows():
        items = []
        for t, f, c in ITEMS:
            if r[f] == 'Sí':
                n, m = pauta_hallazgo(r[c])
                items.append(dict(tipo=t, texto=r[c] if isinstance(r[c], str) else '', nota=n, motivo=m, sug=sugerencia(t, n)))
        regs[int(r.ID)] = dict(f=fh(r.Fecha), creado=fh(r.Creado), ret=round(float(r.retraso_h), 1) if pd.notna(r.retraso_h) else None,
                               area=r.Area, esp=r.Especialidad, eq=r.Equipo, per=r['Creado por'], comp=bool(r.compartida), tarea=r.Tarea if isinstance(r.Tarea, str) else '',
                               tarea_se=bool(r.tarea_se), fr=r.FaltaRiesgo if isinstance(r.FaltaRiesgo, str) else '—', fc=r.FaltaControl if isinstance(r.FaltaControl, str) else '—',
                               ft=r.FaltaTarea if isinstance(r.FaltaTarea, str) else '—', tit=r['Título'] if isinstance(r['Título'], str) else '',
                               estado=r.EstadoMejora if isinstance(r.EstadoMejora, str) else '', ct=r.cod_turno if isinstance(r.cod_turno, str) else '', items=items, sem=r.semana.strftime('%Y-%m-%d'))
    eqs = {k: [int(i) for i in d4[(d4.Area + '|' + d4.Especialidad + '|' + d4.Equipo) == k].sort_values('Fecha', ascending=False).ID] for k in eq_claves}
    pers = {p: [int(i) for i in g.sort_values('Fecha', ascending=False).ID] for p, g in d4.groupby('Creado por')}
    return dict(reg=regs, eq=eqs, per=pers)


JS = r'''
const D=JSON.parse(document.getElementById('datos').textContent);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const chip=(c,t)=>`<span class="chip ${c}">${esc(t)}</span>`;
const bg=document.getElementById('modal'),box=document.getElementById('modalBox');
const semSel=document.getElementById('semSel'),areaSel=document.getElementById('areaSel'),cont=document.getElementById('contenido');
function abrir(h){box.innerHTML='<button class="close-x" style="float:right" onclick="cerrar()">✕</button>'+h;bg.classList.add('show');box.scrollTop=0;enlazar(box);}
function cerrar(){bg.classList.remove('show');}
bg.addEventListener('click',e=>{if(e.target===bg)cerrar();});document.addEventListener('keydown',e=>{if(e.key==='Escape')cerrar();});
function filaReg(id){const r=D.reg[id];const h=r.items.length?r.items.map(i=>chip(i.nota>=2?'ok':'red',i.tipo+' '+i.nota+'/3')).join(' '):'<span class="ev-meta">sin hallazgo</span>';
 return `<tr class="clic" data-reg="${id}"><td class="num">${r.f}</td><td>${esc(r.eq)}<div class="ev-meta">${esc(r.per)}</div></td><td>${esc(r.tarea).slice(0,90)}</td><td>${h}</td><td>${esc(r.estado)}</td></tr>`;}
function ventana(){const v=semSel.value;if(v==='ev')return null;const lun=D.semanas[v];const d=new Date(lun+'T00:00:00');d.setDate(d.getDate()-21);return [d.toISOString().slice(0,10),lun];}
function lista(ids,titulo){const w=ventana();const sel=w?ids.filter(i=>D.reg[i].sem>=w[0]&&D.reg[i].sem<=w[1]):ids;const sem={};sel.forEach(i=>{const s=D.reg[i].sem;(sem[s]=sem[s]||[]).push(i);});
 abrir(`<h3>${esc(titulo)}</h3><p>${sel.length} registros ${w?'en las 4 semanas que terminan en la semana seleccionada':'en todo el período'} · clic en un registro para ver el detalle</p>`+Object.keys(sem).sort().reverse().map(s=>`<h4>Semana ${D.num[s]||''} · del ${s.split('-').reverse().join('-')}</h4><div class="scroll"><table><tr><th>Fecha RIT</th><th>Equipo / persona</th><th>Tarea revisada</th><th>Hallazgos (pauta)</th><th>Mejora</th></tr>${sem[s].map(filaReg).join('')}</table></div>`).join(''));}
function verReg(id){const r=D.reg[id];if(!r)return;
 const it=r.items.map(i=>`<div class="card card-pad" style="margin:8px 0;box-shadow:none"><b>${esc(i.tipo)}</b> ${chip(i.nota>=2?'ok':i.nota==1?'amb':'red','pauta '+i.nota+'/3')} <span class="ev-meta">${esc(i.motivo)}</span><div class="txt">${esc(i.texto)||'—'}</div><div class="ev-meta" style="margin-top:6px"><b>Cómo mejorarlo:</b> ${esc(i.sug)}</div></div>`).join('');
 abrir(`<h3>Levantamiento ${id}</h3><p>${esc(r.area)} · ${esc(r.esp)} · ${esc(r.eq)} · ${esc(r.per)}${r.comp?' 👥 cuenta compartida':''} · Semana ${D.num[r.sem]||''}</p>
 <table class="kv"><tr><td>Fecha RIT</td><td>${r.f}</td></tr><tr><td>Registrado</td><td>${r.creado}${r.ret!==null?' ('+r.ret+' h después)':''}</td></tr>
 ${r.ct?`<tr><td>Turno según calendario</td><td>${{D:'D (día)',N:'N (noche)',DC:'DC (descanso)',AD:'AD (administrativo)'}[r.ct]||esc(r.ct)} ${['D','N'].includes(r.ct)?'':r.ct==='AD'?chip('gray','administrativo: no se exige el RIT; no suma ni resta adherencia'):chip('amb','fuera de turno (descanso): revisar si se eligió bien el turno')}</td></tr>`:''}
 <tr><td>Tarea revisada</td><td>${esc(r.tarea)} ${r.tarea_se?'':chip('amb','sin tarea de SoftExpert')}</td></tr>
 <tr><td>¿Falta riesgo / control / tarea?</td><td>${esc(r.fr)} / ${esc(r.fc)} / ${esc(r.ft)}</td></tr><tr><td>Observación</td><td>${esc(r.tit)||'—'}</td></tr><tr><td>Estado mejora</td><td>${esc(r.estado)}</td></tr></table>
 <h4>Hallazgos informados</h4>${it||'<p class="ev-meta">No informa hallazgos: la tarea se revisó y no se encontró nada que mejorar (cuenta para adherencia).</p>'}`);}
function enlazar(root){
 root.querySelectorAll('[data-eq]').forEach(x=>{if(x._b)return;x._b=1;x.addEventListener('click',e=>{e.stopPropagation();const k=x.dataset.eq;lista(D.eq[k]||[],k.replaceAll('|',' · '));});});
 root.querySelectorAll('[data-per]').forEach(x=>{if(x._b||!x.dataset.per)return;x._b=1;x.addEventListener('click',()=>lista(D.per[x.dataset.per]||[],x.dataset.per));});
 root.querySelectorAll('[data-reg]').forEach(x=>{if(x._b)return;x._b=1;x.addEventListener('click',e=>{e.stopPropagation();verReg(x.dataset.reg);});});
 root.querySelectorAll('[data-irsem]').forEach(x=>{if(x._b)return;x._b=1;x.addEventListener('click',e=>{e.stopPropagation();semSel.value=x.dataset.irsem;mostrar();});});}
function mostrar(){const t=document.getElementById(`t-${semSel.value}-${areaSel.value}`);cont.innerHTML='';if(t)cont.appendChild(t.content.cloneNode(true));enlazar(cont);
 try{history.replaceState(null,'','#'+semSel.value+'-'+areaSel.value);}catch(e){}window.scrollTo(0,0);}
function paso(n){const i=semSel.selectedIndex+n;if(i>=0&&i<semSel.options.length){semSel.selectedIndex=i;mostrar();}}
semSel.onchange=mostrar;areaSel.onchange=mostrar;
const h=location.hash.slice(1).split('-');if(h.length===2&&document.getElementById(`t-${h[0]}-${h[1]}`)){semSel.value=h[0];areaSel.value=h[1];}
mostrar();
'''

CSS_EXTRA = '''
.clic{cursor:pointer}tr.clic:hover td{background:var(--azulBg)}
.chip.gray{background:#F0EFEC;color:var(--grisC)}.chip.clic:hover{filter:brightness(.95)}
.cuad{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.cq{border-top:4px solid var(--grisC)}.cq-ok{border-top-color:var(--ok)}.cq-amb{border-top-color:var(--naranja)}.cq-red{border-top-color:var(--rojo)}.cq-az{border-top-color:var(--azul)}
.cq .chip{margin:0 0 5px 0}
.spark{display:inline-flex;align-items:flex-end;gap:2px;height:24px}.spark i{display:block;width:7px;border-radius:2px}
.dl{display:block;font-size:10.5px;margin-top:2px;color:var(--grisC)}.dl.up{color:var(--ok)}.dl.down{color:var(--rojo)}
ul.ej{list-style:none;padding:0}ul.ej li{padding:8px 0;border-bottom:1px solid var(--linea)}.txtq{font-size:12px}
.modal{max-width:960px}.modal h4{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--gris);margin:16px 0 6px}
.modal .txt{background:var(--bg2);border:1px solid var(--linea);border-radius:8px;padding:10px 12px;font-size:13px;white-space:pre-wrap;margin-top:6px}
.modal table.kv td:first-child{color:var(--grisC);width:200px}
.semnav{display:flex;gap:6px;align-items:flex-end}.semnav .btn{padding:6px 10px}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.chart svg{width:100%;height:auto;display:block}.chart .ax{font-size:10px;fill:var(--grisC)}.chart .grid{stroke:var(--linea);stroke-width:1}
.chart .meta{stroke:var(--ok);stroke-width:1.5;stroke-dasharray:4 4}.chart .linea{fill:none;stroke:var(--gris);stroke-width:2}
.chart .pt{fill:var(--gris);stroke:var(--blanco);stroke-width:2}.chart .pt.bajo{fill:var(--blanco);stroke:var(--grisC);stroke-width:1.5}
.chart .hit{fill:transparent;cursor:pointer}.chart .hit:hover+.pt{r:6}.chart .vlab{font-size:11px;font-weight:700;fill:var(--txt)}
.heat td.h{text-align:center;font-size:11px;font-weight:600;padding:5px 4px;min-width:34px;border:2px solid var(--blanco)}
.heat td.h.ok{background:var(--okBg);color:var(--ok)}.heat td.h.amb{background:var(--ambarBg);color:var(--ambar)}.heat td.h.red{background:var(--rojoBg);color:var(--rojo)}
.heat td.h.na{background:transparent;color:var(--linea)}.heat th.sem{text-align:center;cursor:pointer;padding:6px 2px}.heat th.sem:hover{color:var(--txt)}
.heat td.nom{white-space:nowrap;font-size:12px}.heat tr.g td.nom{font-weight:700}
@media print{.modal-bg{display:none!important}}
'''


def vista(nombre, dsem, d4, eq_sem, eq4, personas, top, series, cfg, ind, ind_ant, com, etiqueta, area=None):
    h = dsem[dsem.hallazgo]
    focos = com.get('focos') or focos_auto(eq_sem, eq4, ind, ind_ant, h)
    lectura = f'<div class="card logro" style="margin-bottom:14px">{com["lectura"]}</div>' if com.get('lectura') else ''
    k = '<div class="kpi-grid">' + ''.join([
        kpi('Registros RIT', ind['reg'], f'{ind["personas"]} personas · {int(dsem.compartida.sum())} con cuenta compartida' + (f' · {ind["fuera"]} en descanso o con equipo mal registrado' if ind['fuera'] else '')),
        kpi('Adherencia', f'{ind["pAdh"]}%' if ind['pAdh'] is not None else 's/d', f'{ind["dias"]} de {ind["esp"]:g} días-equipo esperados' + delta(ind['pAdh'], ind_ant and ind_ant['pAdh']), colk(ind['pAdh'], 'adherencia', cfg)),
        kpi('Registro oportuno', f'{ind["pOport"]}%' if ind['pOport'] is not None else 's/d', 'registrado ≤12 h del RIT' + delta(ind['pOport'], ind_ant and ind_ant['pOport']), colk(ind['pOport'], 'oportuno', cfg)),
        kpi('Con hallazgo', f'{ind["hall"]}', f'{ind["pHall"] if ind["pHall"] is not None else "s/d"}% de los registros' + delta(ind['pHall'], ind_ant and ind_ant['pHall'])),
        kpi('Hallazgos claros', f'{ind["pClaro"]}%' if ind['pClaro'] is not None else 's/d', f'{ind["claros"]} de {ind["hall"]} con pauta ≥2' + delta(ind['pClaro'], ind_ant and ind_ant['pClaro']), colk(ind['pClaro'], 'claridad', cfg)),
        kpi('No se entienden', ind['n0'] + ind['n1'], f'{ind["pegadas"]} listas pegadas · {ind["n0"]} sin contenido', 'red' if ind['n0'] + ind['n1'] else ''),
    ]) + '</div>'
    titulo = 'Planta' if area is None else 'Área'
    return f'''
<div class="mega-title" style="margin-top:22px"><span class="mega-tag">{titulo}</span> {esc(nombre)} — {etiqueta}</div>
<div class="section-title">📌 La semana en números (variación vs. semana anterior)</div>{k}
<div class="section-title">🎯 Foco de la semana</div>{lectura}<div class="card blk b-az">{ul(focos)}
<div class="ideas-fuerza-note">{"Redactado tras revisión" if com.get("focos") else "Generado automáticamente por reglas"}. Adherencia = hacer y registrar el RIT; calidad = que el hallazgo informado se entienda.</div></div>
<div class="section-title">🧭 ¿Quién necesita apoyo? Adherencia × claridad por equipo (4 semanas hasta la seleccionada)</div>{bloque_cuadrantes(eq4, cfg)}
<div class="section-title">📊 {"Detalle por área y especialidad (semana) — seleccione un área arriba para ver cada equipo" if area is None else "Detalle por especialidad y equipo (semana)"}</div>{bloque_tabla(dsem, eq_sem, series, cfg, area)}
<div class="ev-meta" style="margin-top:6px">Días esperados: Mantención = días hábiles (lun–vie, sin feriados); Operación = días en que el turno está de día (D) o de noche (N) según la rotación de turnos;
los días de descanso (DC) y administrativos (AD) no se exigen ("sin turno" = el turno no estuvo de D ni N esa semana). Un RIT de las 20:00 en adelante es del turno noche del día siguiente.
Cada equipo entra al cálculo desde su primera semana con registro; los registros con equipo mal informado (Operación sin turno A–E) no cuentan para adherencia. Clic en un equipo para ver sus levantamientos.</div>
<div class="section-title">👤 Personas (4 semanas hasta la seleccionada)</div>{bloque_personas(personas, top, cfg)}
<div class="section-title">📝 Ejemplos de la semana</div>{bloque_ejemplos(h)}
{"" if area else f'<div class="section-title">⭐ Top 20 piloto SoftExpert — ¿se sostiene su calidad?</div>{bloque_top20(top, personas, cfg)}'}'''


def personas_4s(d4):
    filas = []
    for p, g in d4.groupby('Creado por'):
        h = g[g.hallazgo]
        mejor = h.sort_values('nota', ascending=False)
        filas.append(dict(persona=p, compartida=bool(g.compartida.iloc[0]), reg=len(g), semanas=g.semana.nunique(), hall=len(h),
                          pClaro=round(100 * h.claro.mean()) if len(h) else None, nota=round(float(h.nota.mean()), 1) if len(h) else None,
                          areas=', '.join(sorted(set(g.Area + ' ' + g.Equipo)))[:80],
                          ejemplo=texto_hallazgo(mejor.iloc[0]) if len(h) else ''))
    return pd.DataFrame(filas, columns=['persona', 'compartida', 'reg', 'semanas', 'hall', 'pClaro', 'nota', 'areas', 'ejemplo'])


def fh(t):
    return t.strftime('%d-%m-%Y %H:%M') if pd.notna(t) else '—'


def datos_detalle(d, claves, semanas):
    regs = {}
    for _, r in d.iterrows():
        items = []
        for t, f, c in ITEMS:
            if r[f] == 'Sí':
                n, m = pauta_hallazgo(r[c])
                items.append(dict(tipo=t, texto=r[c] if isinstance(r[c], str) else '', nota=n, motivo=m, sug=sugerencia(t, n)))
        regs[int(r.ID)] = dict(f=fh(r.Fecha), creado=fh(r.Creado), ret=round(float(r.retraso_h), 1) if pd.notna(r.retraso_h) else None,
                               area=r.Area, esp=r.Especialidad, eq=r.Equipo, per=r['Creado por'], comp=bool(r.compartida), tarea=r.Tarea if isinstance(r.Tarea, str) else '',
                               tarea_se=bool(r.tarea_se), fr=r.FaltaRiesgo if isinstance(r.FaltaRiesgo, str) else '—', fc=r.FaltaControl if isinstance(r.FaltaControl, str) else '—',
                               ft=r.FaltaTarea if isinstance(r.FaltaTarea, str) else '—', tit=r['Título'] if isinstance(r['Título'], str) else '',
                               estado=r.EstadoMejora if isinstance(r.EstadoMejora, str) else '', ct=r.cod_turno if isinstance(r.cod_turno, str) else '', items=items, sem=r.semana.strftime('%Y-%m-%d'))
    clave = d.Area + '|' + d.Especialidad + '|' + d.Equipo
    eqs = {k: [int(i) for i in d[clave == k].sort_values('Fecha', ascending=False).ID] for k in claves}
    pers = {p: [int(i) for i in g.sort_values('Fecha', ascending=False).ID] for p, g in d.groupby('Creado por')}
    return dict(reg=regs, eq=eqs, per=pers, semanas={f'S{n}': s.strftime('%Y-%m-%d') for n, s in semanas},
                num={s.strftime('%Y-%m-%d'): n for n, s in semanas})


# ================================================================ evolución
def svg_linea(puntos, titulo, sub, umbral=None, alto=170):
    """puntos: [(semana_num, valor|None, n_base, texto_hover)]. Una sola serie, eje 0–100%."""
    ancho, ml, mr, mt, mb = 520, 34, 12, 14, 26
    W, H = ancho - ml - mr, alto - mt - mb
    n = len(puntos)
    x = lambda i: ml + (W * i / max(1, n - 1))
    y = lambda v: mt + H * (1 - v / 100)
    g = ''.join(f'<line class="grid" x1="{ml}" x2="{ancho - mr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/><text class="ax" x="{ml - 6}" y="{y(v) + 3:.1f}" text-anchor="end">{v}</text>'
                for v in (0, 25, 50, 75, 100))
    paso = max(1, n // 12)
    g += ''.join(f'<text class="ax" x="{x(i):.1f}" y="{alto - 8}" text-anchor="middle">S{p[0]}</text>' for i, p in enumerate(puntos) if i % paso == 0 or i == n - 1)
    if umbral is not None:
        g += f'<line class="meta" x1="{ml}" x2="{ancho - mr}" y1="{y(umbral):.1f}" y2="{y(umbral):.1f}"/><text class="ax" x="{ancho - mr}" y="{y(umbral) - 4:.1f}" text-anchor="end">meta {umbral}%</text>'
    tramos, actual = [], []
    for i, p in enumerate(puntos):
        if p[1] is None:
            if actual:
                tramos.append(actual)
            actual = []
        else:
            actual.append(f'{x(i):.1f},{y(p[1]):.1f}')
    if actual:
        tramos.append(actual)
    g += ''.join(f'<polyline class="linea" points="{" ".join(t)}"/>' for t in tramos)
    for i, p in enumerate(puntos):
        if p[1] is None:
            continue
        bajo = p[2] < 20
        g += (f'<g data-irsem="S{p[0]}"><title>{esc(p[3])}</title><circle class="hit" cx="{x(i):.1f}" cy="{y(p[1]):.1f}" r="11"/>'
              f'<circle class="pt{" bajo" if bajo else ""}" cx="{x(i):.1f}" cy="{y(p[1]):.1f}" r="4"/></g>')
    ult = next((p for p in reversed(puntos) if p[1] is not None), None)
    if ult:
        i = puntos.index(ult)
        g += f'<text class="vlab" x="{x(i) - 6:.1f}" y="{y(ult[1]) - 9:.1f}" text-anchor="end">{ult[1]}%</text>'
    return (f'<div class="card card-pad chart"><h3 class="card-h">{titulo}</h3><div class="card-h-sub">{sub}</div>'
            f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="{esc(titulo)} por semana">{g}</svg></div>')


def heat_celda(v, k, cfg, sem):
    if v is None:
        return '<td class="h na">·</td>'
    gv, w = cfg['umbrales'][k]
    c = 'ok' if v >= gv else 'amb' if v >= w else 'red'
    return f'<td class="h {c}" data-irsem="S{sem}" title="Semana {sem}: {v}%">{v}</td>'


def vista_evolucion(nombre, area, sem_lista, serie, filas_heat, cfg, corte):
    """serie: lista de (num, lunes, ind) del ámbito. filas_heat: [(nombre, nivel, {num: (adh, claro)})]."""
    val = lambda k: [(n, ind[k], ind['reg'] if k != 'pClaro' else ind['hall'],
                      f'Semana {n} ({fmt(l)}): {ind[k] if ind[k] is not None else "s/d"}% · {ind["reg"]} registros, {ind["hall"]} hallazgos') for n, l, ind in serie]
    u = cfg['umbrales']
    charts = ''.join([
        svg_linea(val('pAdh'), 'Adherencia', 'Días con RIT registrado / días esperados', u['adherencia'][0]),
        svg_linea(val('pClaro'), 'Hallazgos claros', 'Hallazgos con pauta ≥2 / hallazgos informados', u['claridad'][0]),
        svg_linea(val('pHall'), 'Registros con hallazgo', '% de levantamientos que informan algo que falta o sobra en SoftExpert'),
        svg_linea(val('pOport'), 'Registro oportuno', 'Registrados hasta 12 h después del RIT', u['oportuno'][0]),
        svg_linea(val('pTarea'), 'Tarea de SoftExpert seleccionada', 'Registros con tarea de SE (no "Notificar sin SE")', u['tarea_se'][0]),
    ])
    completas = [(n, l, i) for n, l, i in serie if l + pd.Timedelta(days=6) <= corte]
    ult = completas[-1] if completas else serie[-1]
    prev4 = [i for n, l, i in completas[-5:-1]]
    prom = lambda k: round(sum(i[k] for i in prev4 if i[k] is not None) / max(1, sum(1 for i in prev4 if i[k] is not None))) if any(i[k] is not None for i in prev4) else None
    mejor = lambda k: max(((i[k], n) for n, l, i in completas if i[k] is not None and i['reg'] >= 20), default=(None, None))
    def tarjeta(k, label, umbral):
        v, p, (bv, bn) = ult[2][k], prom(k), mejor(k)
        d = '' if v is None or p is None else f'<small class="dl {"up" if v >= p else "down"}">{"▲" if v >= p else "▼"} {abs(v - p)} pts vs. prom. 4 sem. anteriores ({p}%)</small>'
        return kpi(f'{label} · S{ult[0]}', f'{v}%' if v is not None else 's/d', (f'mejor semana: S{bn} ({bv}%)' if bn else '') + d, colk(v, umbral, cfg) if umbral else '')
    tarjetas = '<div class="kpi-grid">' + ''.join([
        kpi(f'Registros · S{ult[0]}', ult[2]['reg'], f'{ult[2]["personas"]} personas · total período: {sum(i["reg"] for _, _, i in serie)}'),
        tarjeta('pAdh', 'Adherencia', 'adherencia'), tarjeta('pClaro', 'Hallazgos claros', 'claridad'),
        tarjeta('pHall', 'Con hallazgo', None), tarjeta('pOport', 'Registro oportuno', 'oportuno'),
        kpi('Listas pegadas · S' + str(ult[0]), ult[2]['pegadas'], 'copiadas de SoftExpert sin acción', 'red' if ult[2]['pegadas'] else ''),
    ]) + '</div>'
    filas_t = ''.join(
        f'<tr class="clic" data-irsem="S{n}"><td><b>S{n}</b> <small>{fmt(l)}–{fmt(l + pd.Timedelta(days=6))}{" (parcial)" if l + pd.Timedelta(days=6) > corte else ""}</small></td>'
        f'<td class="num">{i["reg"]}</td><td class="num">{i["personas"]}</td><td class="num">{pill(i["pAdh"], "adherencia", cfg)}</td><td class="num">{pill(i["pOport"], "oportuno", cfg)}</td>'
        f'<td class="num">{pill(i["pTarea"], "tarea_se", cfg)}</td><td class="num">{i["hall"]} <small>({i["pHall"] if i["pHall"] is not None else "s/d"}%)</small></td>'
        f'<td class="num">{pill(i["pClaro"], "claridad", cfg)} <small>{i["claros"]}/{i["hall"]}</small></td><td class="num">{i["pegadas"] or "—"}</td><td class="num">{i["nota"] if i["nota"] is not None else "s/d"}</td></tr>'
        for n, l, i in reversed(serie))
    tabla = ('<div class="card scroll"><table><tr><th>Semana</th><th>Registros</th><th>Personas</th><th>Adherencia</th><th>Registro oportuno</th><th>Tarea SE</th>'
             f'<th>Con hallazgo</th><th>Hallazgos claros</th><th>Listas pegadas</th><th>Pauta media</th></tr>{filas_t}</table></div>')
    def heat(k, idx, titulo):
        cab = ''.join(f'<th class="sem" data-irsem="S{n}" title="Ir a la semana {n}">{n}</th>' for n, _ in sem_lista)
        cuerpo = ''.join(f'<tr class="{"g" if nivel == 0 else ""}"><td class="nom">{"&nbsp;" * 4 * nivel}{esc(nom)}</td>'
                         + ''.join(heat_celda(vals.get(n, (None, None))[idx], k, cfg, n) for n, _ in sem_lista) + '</tr>' for nom, nivel, vals in filas_heat)
        return (f'<div class="section-title">{titulo}</div><div class="card scroll heat"><table><tr><th>Semana →</th>{cab}</tr>{cuerpo}</table></div>')
    titulo = 'Planta' if area is None else 'Área'
    return f'''
<div class="mega-title" style="margin-top:22px"><span class="mega-tag">{titulo}</span> {esc(nombre)} — evolución de los KPI RIT, semanas {sem_lista[0][0]} a {sem_lista[-1][0]}</div>
<div class="section-title">📌 Última semana completa vs. promedio de las 4 anteriores</div>{tarjetas}
<div class="section-title">📈 Evolución semanal</div><div class="charts">{charts}</div>
<div class="ev-meta" style="margin-top:6px">Mismas reglas para todas las semanas. Puntos huecos = menos de 20 registros (o hallazgos, en "Hallazgos claros"): leer con cautela, sobre todo en el inicio del despliegue.
Línea punteada = meta (verde del semáforo). Pase el cursor por un punto para ver el detalle; clic para abrir esa semana.</div>
{heat("adherencia", 0, "🗓 Adherencia por semana (%) — clic en una semana para abrirla")}
{heat("claridad", 1, "🗓 Hallazgos claros por semana (%) — vacío = sin hallazgos esa semana")}
<div class="section-title">📋 Tabla semanal</div>{tabla}'''


# ================================================================ cálculo de una semana
def evaluar(d, lun, cfg, ctx):
    dom = lun + pd.Timedelta(days=6)
    ini4 = lun - pd.Timedelta(days=21)
    dsem, dant, d4 = d[d.semana == lun], d[d.semana == lun - pd.Timedelta(days=7)], d[(d.semana >= ini4) & (d.semana <= lun)]
    act = ctx['activos'](lun)
    eq_sem = act.merge(tabla_equipos(dsem, lun, dom, cfg), how='left', on=['Area', 'Especialidad', 'Equipo']) if len(dsem) else act.copy()
    for c in ('reg', 'dias', 'hall', 'claros', 'pegadas', 'n0', 'n1', 'personas'):
        eq_sem[c] = eq_sem[c].fillna(0).astype(int) if c in eq_sem else 0
    for c in ('pOport', 'pTarea', 'pComp', 'pHall', 'pClaro', 'nota', 'lider'):
        if c not in eq_sem:
            eq_sem[c] = None
    eq_sem['esp'] = [esperados(e, lun, dom, cfg, q) for e, q in zip(eq_sem.Especialidad, eq_sem.Equipo)]
    eq_sem['pAdh'] = [min(100, round(100 * x / y)) if y else None for x, y in zip(eq_sem.dias, eq_sem.esp)]
    eq_sem['lider'] = eq_sem.lider.fillna('')
    eq_sem = eq_sem.astype(object).where(eq_sem.notna(), None)

    t4 = tabla_equipos(d4, ini4, dom, cfg)
    eq4 = act.merge(t4, how='left', on=['Area', 'Especialidad', 'Equipo']) if len(t4) else act.assign(dias=0, hall=0, pClaro=None)
    eq4['dias'] = eq4.dias.fillna(0)
    eq4['hall'] = eq4.hall.fillna(0).astype(int)
    # días esperados en 4 semanas, desde la semana en que el equipo empezó a registrar
    eq4['esp'] = [esperados(e, max(ini4, ctx['inicio'][(a, e, q)]), dom, cfg, q) for a, e, q in zip(eq4.Area, eq4.Especialidad, eq4.Equipo)]
    eq4['pAdh'] = [min(100, round(100 * x / y)) if y else None for x, y in zip(eq4.dias, eq4.esp)]
    eq4['pClaro'] = eq4.pClaro.astype(object).where(eq4.pClaro.notna(), None)
    eq4['cuad'] = [cuadrante(x, c, h, cfg) for x, c, h in zip(eq4.pAdh, eq4.pClaro, eq4.hall)]
    eq4['clave'] = eq4.Area + '|' + eq4.Especialidad + '|' + eq4.Equipo

    semanas8 = [lun - pd.Timedelta(days=7 * i) for i in range(7, -1, -1)]
    series = {}
    for _, r in act.iterrows():
        for s in semanas8:
            if s < ctx['inicio'][(r.Area, r.Especialidad, r.Equipo)]:
                continue
            dias = ctx['dias'].get((r.Area, r.Especialidad, r.Equipo, s), 0)
            esp = esperados(r.Especialidad, s, s + pd.Timedelta(days=6), cfg, r.Equipo)
            for clave in ((r.Area,), (r.Area, r.Especialidad), (r.Area, r.Especialidad, r.Equipo)):
                acc = series.setdefault(clave, {}).setdefault(s, [0, 0])
                acc[0] += dias
                acc[1] += esp
    series = {k: [(s, min(100, round(100 * v[s][0] / v[s][1])) if s in v and v[s][1] else None) for s in semanas8] for k, v in series.items()}
    esp_ant = lambda df: sum(esperados(e, lun - pd.Timedelta(days=7), lun - pd.Timedelta(days=1), cfg, q) for e, q in zip(df.Especialidad, df.Equipo))
    act_ant = ctx['activos'](lun - pd.Timedelta(days=7))
    return dict(lun=lun, dom=dom, dsem=dsem, dant=dant, d4=d4, eq_sem=eq_sem, eq4=eq4, series=series, act=act, act_ant=act_ant, esp_ant=esp_ant)


def main(argv=None):
    p = argparse.ArgumentParser(description='Reporte semanal de calidad de levantamientos RIT (todas las semanas + evolución)')
    p.add_argument('--planta', default='Nueva Aldea')
    p.add_argument('--semana', default=None, help='Semana que se abre por defecto: número ISO (39) o un día (AAAA-MM-DD); por defecto, la última completa')
    p.add_argument('--excel', default=None)
    p.add_argument('--top20', default=None)
    p.add_argument('--comentarios', default=None, help='JSON {"S39": {"Planta": {...}, "<Área>": {...}}}')
    p.add_argument('--json', action='store_true')
    p.add_argument('--salida', default='out')
    a = p.parse_args(argv)

    cfg = json.loads((CONFIG / 'rit.json').read_text(encoding='utf-8'))
    ruta = Path(a.excel) if a.excel else sorted(Path('data').glob('RIT_*.xlsx'))[-1]
    top_ruta = a.top20 or next(iter(sorted(Path('data').glob('Top_usuarios*.html'))), None)
    rot = cargar_rotacion()
    cfg['_rot'] = rot
    d = cargar(ruta, a.planta, rot)
    top = cargar_top20(top_ruta, a.planta)
    corte = d[d.Fecha.dt.hour < 20].dia.max() if len(d) else d.dia.max()
    cfg['_corte'] = str(corte.date())

    lunes = list(pd.date_range(d.semana.min(), d.semana.max(), freq='7D'))
    sem_lista = [(int(l.isocalendar().week), l) for l in lunes]
    num = {l: n for n, l in sem_lista}
    completas = [l for l in lunes if l + pd.Timedelta(days=6) <= corte]
    if a.semana:
        if a.semana.isdigit():
            defecto = next(l for n, l in sem_lista if n == int(a.semana))
        else:
            x = pd.Timestamp(a.semana).normalize()
            defecto = x - pd.Timedelta(days=x.dayofweek)
    else:
        defecto = completas[-1] if completas else lunes[-1]

    equipos = d.groupby(['Area', 'Especialidad', 'Equipo']).semana.min()
    inicio = {k: v for k, v in equipos.items()}
    ctx = dict(inicio=inicio, dias=d.groupby(['Area', 'Especialidad', 'Equipo', 'semana']).dia_adh.nunique().to_dict(),
               activos=lambda lun: pd.DataFrame([k for k, v in inicio.items() if v <= lun], columns=['Area', 'Especialidad', 'Equipo']))
    areas = sorted(d.Area.unique())
    comentarios = json.loads(Path(a.comentarios).read_text(encoding='utf-8')) if a.comentarios else {}

    plantillas, resumen, evol = [], {}, {None: [], **{ar: [] for ar in areas}}
    heat_vals = {}
    for n, lun in sem_lista:
        e = evaluar(d, lun, cfg, ctx)
        parcial = e['dom'] > corte
        etiqueta = f'Semana {n} · {fmt(lun)} a {e["dom"]:%d-%m-%Y}' + (f' (parcial, datos hasta {fmt(corte)})' if parcial else '')
        com = comentarios.get(f'S{n}', {})
        ind = indicadores(e['dsem'], e['eq_sem'].esp.sum())
        ind_ant = indicadores(e['dant'], e['esp_ant'](e['act_ant'])) if len(e['act_ant']) else None
        evol[None].append((n, lun, ind))
        plantillas.append((f'S{n}', 'p', vista(a.planta, e['dsem'], e['d4'], e['eq_sem'], e['eq4'], personas_4s(e['d4']), top, e['series'], cfg, ind, ind_ant,
                                               com.get('Planta', {}), etiqueta)))
        for i, ar in enumerate(areas):
            ea = e['eq_sem'][e['eq_sem'].Area == ar]
            ia = indicadores(e['dsem'][e['dsem'].Area == ar], ea.esp.sum())
            aa = e['act_ant'][e['act_ant'].Area == ar] if len(e['act_ant']) else e['act_ant']
            ia_ant = indicadores(e['dant'][e['dant'].Area == ar], e['esp_ant'](aa)) if len(aa) else None
            evol[ar].append((n, lun, ia))
            plantillas.append((f'S{n}', f'a{i}', vista(ar, e['dsem'][e['dsem'].Area == ar], e['d4'][e['d4'].Area == ar], ea, e['eq4'][e['eq4'].Area == ar],
                                                      personas_4s(e['d4'][e['d4'].Area == ar]), top, e['series'], cfg, ia, ia_ant, com.get(ar, {}), etiqueta, area=ar)))
        # valores para los mapas de calor (área, especialidad, equipo)
        for ar in areas:
            ea = e['eq_sem'][e['eq_sem'].Area == ar]
            if not len(ea):
                continue
            da = e['dsem'][e['dsem'].Area == ar]
            heat_vals.setdefault((ar,), {})[n] = (indicadores(da, ea.esp.sum())['pAdh'], indicadores(da, ea.esp.sum())['pClaro'])
            for es in ('Operación', 'Mantención'):
                ee = ea[ea.Especialidad == es]
                if len(ee):
                    ii = indicadores(da[da.Especialidad == es], ee.esp.sum())
                    heat_vals.setdefault((ar, es), {})[n] = (ii['pAdh'], ii['pClaro'])
                for _, r in ee.iterrows():
                    heat_vals.setdefault((ar, es, r.Equipo), {})[n] = (r.pAdh, int(r.pClaro) if r.pClaro is not None else None)
        if lun == defecto:
            resumen = dict(semana=n, rango=[str(lun.date()), str(e['dom'].date())], planta=ind, semana_anterior=ind_ant,
                           equipos=e['eq_sem'].drop(columns=['lider']).to_dict('records'),
                           cuadrantes={k: [f'{r.Area} · {r.Equipo}' for _, r in e['eq4'][e['eq4'].cuad == k].iterrows()] for k in CUAD},
                           personas_4s=personas_4s(e['d4']).to_dict('records'),
                           hallazgos_semana=[dict(ID=int(r.ID), area=r.Area, equipo=r.Equipo, persona=r['Creado por'], texto=texto_hallazgo(r), pauta=int(r.nota), motivo=r.motivo)
                                             for _, r in e['dsem'][e['dsem'].hallazgo].iterrows()],
                           focos_automaticos=focos_auto(e['eq_sem'], e['eq4'], ind, ind_ant, e['dsem'][e['dsem'].hallazgo]))

    def filas_heat(area=None):
        out = []
        for ar in ([area] if area else areas):
            out.append((ar, 0, heat_vals.get((ar,), {})))
            for es in ('Operación', 'Mantención'):
                if (ar, es) in heat_vals:
                    out.append((es, 1, heat_vals[(ar, es)]))
                    if area:
                        for k in sorted(x for x in heat_vals if len(x) == 3 and x[0] == ar and x[1] == es):
                            out.append((k[2], 2, heat_vals[k]))
        return out
    plantillas.append(('ev', 'p', vista_evolucion(a.planta, None, sem_lista, evol[None], filas_heat(), cfg, corte)))
    for i, ar in enumerate(areas):
        plantillas.append(('ev', f'a{i}', vista_evolucion(ar, ar, sem_lista, evol[ar], filas_heat(ar), cfg, corte)))

    css = Path('ref/estilos_base.css').read_text() + Path('ref/estilos_reporte.css').read_text() + CSS_EXTRA
    opt_sem = '<option value="ev">📈 Evolución global (todas las semanas)</option>' + ''.join(
        f'<option value="S{n}"{" selected" if l == defecto else ""}>Semana {n} · {fmt(l)} a {fmt(l + pd.Timedelta(days=6))}{" (parcial)" if l + pd.Timedelta(days=6) > corte else ""}</option>'
        for n, l in reversed(sem_lista))
    opt_area = '<option value="p">Planta completa</option>' + ''.join(f'<option value="a{i}">{esc(ar)}</option>' for i, ar in enumerate(areas))
    claves = set(d.Area + '|' + d.Especialidad + '|' + d.Equipo)
    datos = json.dumps(datos_detalle(d, claves, sem_lista), ensure_ascii=False, default=str).replace('</', '<\\/')
    tpls = ''.join(f'<template id="t-{s}-{v}">{h}</template>' for s, v, h in plantillas)
    pag = f'''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RIT semanal {esc(a.planta)}</title><style>{css}</style></head><body>
<header><div class="hd"><div class="hd-left"><div><h1>Calidad de levantamientos RIT</h1>
<div class="sub">Reunión de Inicio de Turno · revisión de riesgos y controles en SoftExpert — adherencia y calidad de los hallazgos</div><div class="plt">Negocio Celulosa — Planta {esc(a.planta)}</div></div></div>
<div class="hd-right"><div class="hd-meta">Semanas {sem_lista[0][0]} a {sem_lista[-1][0]} (numeración ISO, lunes a domingo)<br>Datos hasta el <b>{corte:%d-%m-%Y}</b><br>Fuente: {esc(ruta.name)}</div></div></div></header>
<div class="filterbar"><div class="filterbar-in"><div class="f"><label>Semana</label><div class="semnav"><button class="btn" onclick="paso(1)" title="Semana anterior">◀</button>
<select id="semSel">{opt_sem}</select><button class="btn" onclick="paso(-1)" title="Semana siguiente">▶</button></div></div>
<div class="f"><label>Área</label><select id="areaSel">{opt_area}</select></div>
<div class="f"><label>Detalle</label><div style="font-size:12.5px;padding:7px 0">Clic en un equipo, una persona, un ejemplo o una semana</div></div>
<button class="btn" onclick="window.print()" style="margin-left:auto">🖨 Imprimir / PDF</button></div></div>
<div class="wrap"><div id="contenido"></div>
<div class="foot-note">Propósito del RIT (ficha de instancia): asegurar que el equipo inicie el turno alineado, con tareas claras y riesgos controlados; el producto esperado es el registro del análisis de riesgo en SoftExpert,
identificando actualización de documentos, cambios en riesgos o en procesos. Playbook MGO: los riesgos se revisan en el día a día durante el inicio de turno.
Pauta de hallazgos 0–3 automática por reglas de texto, igual para todas las semanas; los casos dudosos se revisan en el detalle.</div></div>
{tpls}
<div class="modal-bg" id="modal"><div class="card modal" id="modalBox"></div></div>
<script type="application/json" id="datos">{datos}</script><script>{JS}</script></body></html>'''
    out = Path(a.salida)
    out.mkdir(exist_ok=True)
    f = out / f'RIT_semanal_{a.planta.replace(" ", "_")}.html'
    f.write_text(pag, encoding='utf-8')
    print(f, f'({len(pag) // 1024} KB, semanas {sem_lista[0][0]}–{sem_lista[-1][0]})')
    if a.json:
        resumen['evolucion_planta'] = [dict(semana=n, lunes=str(l.date()), **{k: i[k] for k in ('reg', 'personas', 'pAdh', 'pOport', 'pTarea', 'hall', 'pHall', 'pClaro', 'pegadas', 'nota')})
                                       for n, l, i in evol[None]]
        resumen['evolucion_areas'] = {ar: [dict(semana=n, **{k: i[k] for k in ('reg', 'pAdh', 'pHall', 'pClaro')}) for n, l, i in evol[ar]] for ar in areas}
        j = out / f'RIT_semanal_{a.planta.replace(" ", "_")}_S{num[defecto]}.json'
        j.write_text(json.dumps(resumen, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        print(j)


if __name__ == '__main__':
    main()
