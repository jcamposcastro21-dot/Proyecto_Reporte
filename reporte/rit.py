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
def cargar(ruta, planta):
    d = pd.read_excel(ruta)
    d.columns = [c.strip() for c in d.columns]
    d = d[d.Planta == planta].copy()
    d['Fecha'] = pd.to_datetime(d.Fecha)
    d['Creado'] = pd.to_datetime(d.Creado)
    d['dia'] = d.Fecha.dt.normalize()
    d['semana'] = d.dia - pd.to_timedelta(d.dia.dt.dayofweek, unit='D')
    d['Equipo'] = d.Equipo.fillna('(sin equipo)')
    d['Creado por'] = d['Creado por'].fillna('(sin creador)').map(lambda s: ' '.join(str(s).split()))
    d['compartida'] = d['Creado por'].str.lower().str.startswith('operador')
    d['retraso_h'] = (d.Creado - d.Fecha).dt.total_seconds() / 3600
    d['oportuno'] = d.retraso_h.between(-0.5, 12)
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


def esperados(especialidad, desde, hasta, cfg):
    """Días de RIT esperados por equipo entre desde y hasta (inclusive)."""
    dias = pd.date_range(desde, hasta)
    if especialidad == 'Mantención':
        fer = set(pd.to_datetime(cfg.get('feriados', [])))
        return sum(1 for x in dias if x.dayofweek < 5 and x not in fer)
    return round(len(dias) * cfg.get('operacion_dias_por_dia', 0.4), 1)


# ================================================================ indicadores
def indicadores(df, esp_dias):
    """esp_dias: días esperados del conjunto (suma de los equipos)."""
    h = df[df.hallazgo]
    dias_rit = df.groupby(['Area', 'Especialidad', 'Equipo']).dia.nunique().sum() if len(df) else 0
    pct = lambda a, b: round(100 * a / b) if b else None
    return dict(reg=len(df), dias=int(dias_rit), esp=esp_dias, pAdh=min(100, pct(dias_rit, esp_dias)) if esp_dias else None,
                pOport=pct(df.oportuno.sum(), len(df)), pTarea=pct(df.tarea_se.sum(), len(df)), pComp=pct(df.completo.sum(), len(df)),
                hall=len(h), pHall=pct(len(h), len(df)), claros=int(h.claro.sum()), pClaro=pct(h.claro.sum(), len(h)),
                nota=round(float(h.nota.mean()), 1) if len(h) else None, n0=int((h.nota == 0).sum()), n1=int((h.nota == 1).sum()),
                pegadas=int(h.motivo.str.contains('lista pegada').sum()), personas=df.loc[~df.compartida, 'Creado por'].nunique())


def tabla_equipos(d, desde, hasta, cfg):
    filas = []
    for (a, e, q), g in d.groupby(['Area', 'Especialidad', 'Equipo']):
        esp = esperados(e, desde, hasta, cfg)
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
            f'<td class="num">{r["reg"]}</td><td class="num">{r["dias"]}/{r["esp"]:g}</td><td class="num">{pill(r["pAdh"], "adherencia", cfg)}</td>'
            f'<td class="num">{pill(r["pOport"], "oportuno", cfg)}</td><td class="num">{pill(r["pTarea"], "tarea_se", cfg)}</td>'
            f'<td class="num">{r["hall"]} <small>({int(r["pHall"]) if r["pHall"] is not None else "s/d"}%)</small></td>'
            f'<td class="num">{pill(r["pClaro"], "claridad", cfg)} <small>{r["claros"]}/{r["hall"]}</small></td>'
            f'<td class="num">{r["pegadas"] or "—"}</td><td>{tendencia(serie)}</td></tr>')


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
        regs[int(r.ID)] = dict(f=r.Fecha.strftime('%d-%m-%Y %H:%M'), creado=r.Creado.strftime('%d-%m-%Y %H:%M'), ret=round(float(r.retraso_h), 1) if pd.notna(r.retraso_h) else None,
                               area=r.Area, esp=r.Especialidad, eq=r.Equipo, per=r['Creado por'], comp=bool(r.compartida), tarea=r.Tarea if isinstance(r.Tarea, str) else '',
                               tarea_se=bool(r.tarea_se), fr=r.FaltaRiesgo if isinstance(r.FaltaRiesgo, str) else '—', fc=r.FaltaControl if isinstance(r.FaltaControl, str) else '—',
                               ft=r.FaltaTarea if isinstance(r.FaltaTarea, str) else '—', tit=r['Título'] if isinstance(r['Título'], str) else '',
                               estado=r.EstadoMejora if isinstance(r.EstadoMejora, str) else '', items=items, sem=r.semana.strftime('%Y-%m-%d'))
    eqs = {k: [int(i) for i in d4[(d4.Area + '|' + d4.Especialidad + '|' + d4.Equipo) == k].sort_values('Fecha', ascending=False).ID] for k in eq_claves}
    pers = {p: [int(i) for i in g.sort_values('Fecha', ascending=False).ID] for p, g in d4.groupby('Creado por')}
    return dict(reg=regs, eq=eqs, per=pers)


JS = r'''
const D=JSON.parse(document.getElementById('datos').textContent);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const chip=(c,t)=>`<span class="chip ${c}">${esc(t)}</span>`;
const bg=document.getElementById('modal'),box=document.getElementById('modalBox');
function abrir(h){box.innerHTML='<button class="close-x" style="float:right" onclick="cerrar()">✕</button>'+h;bg.classList.add('show');box.scrollTop=0;enlazar(box);}
function cerrar(){bg.classList.remove('show');}
bg.addEventListener('click',e=>{if(e.target===bg)cerrar();});document.addEventListener('keydown',e=>{if(e.key==='Escape')cerrar();});
function filaReg(id){const r=D.reg[id];const h=r.items.length?r.items.map(i=>chip(i.nota>=2?'ok':'red',i.tipo+' '+i.nota+'/3')).join(' '):'<span class="ev-meta">sin hallazgo</span>';
 return `<tr class="clic" data-reg="${id}"><td class="num">${r.f}</td><td>${esc(r.eq)}<div class="ev-meta">${esc(r.per)}</div></td><td>${esc(r.tarea).slice(0,90)}</td><td>${h}</td><td>${esc(r.estado)}</td></tr>`;}
function lista(ids,titulo){const sem={};ids.forEach(i=>{const s=D.reg[i].sem;(sem[s]=sem[s]||[]).push(i);});
 abrir(`<h3>${esc(titulo)}</h3><p>${ids.length} registros en las últimas 4 semanas · clic en un registro para ver el detalle</p>`+Object.keys(sem).sort().reverse().map(s=>`<h4>Semana del ${s.split('-').reverse().join('-')}</h4><div class="scroll"><table><tr><th>Fecha RIT</th><th>Equipo / persona</th><th>Tarea revisada</th><th>Hallazgos (pauta)</th><th>Mejora</th></tr>${sem[s].map(filaReg).join('')}</table></div>`).join(''));}
function verReg(id){const r=D.reg[id];if(!r)return;
 const it=r.items.map(i=>`<div class="card card-pad" style="margin:8px 0;box-shadow:none"><b>${esc(i.tipo)}</b> ${chip(i.nota>=2?'ok':i.nota==1?'amb':'red','pauta '+i.nota+'/3')} <span class="ev-meta">${esc(i.motivo)}</span><div class="txt">${esc(i.texto)||'—'}</div><div class="ev-meta" style="margin-top:6px"><b>Cómo mejorarlo:</b> ${esc(i.sug)}</div></div>`).join('');
 abrir(`<h3>Levantamiento ${id}</h3><p>${esc(r.area)} · ${esc(r.esp)} · ${esc(r.eq)} · ${esc(r.per)}${r.comp?' 👥 cuenta compartida':''}</p>
 <table class="kv"><tr><td>Fecha RIT</td><td>${r.f}</td></tr><tr><td>Registrado</td><td>${r.creado}${r.ret!==null?' ('+r.ret+' h después)':''}</td></tr>
 <tr><td>Tarea revisada</td><td>${esc(r.tarea)} ${r.tarea_se?'':chip('amb','sin tarea de SoftExpert')}</td></tr>
 <tr><td>¿Falta riesgo / control / tarea?</td><td>${esc(r.fr)} / ${esc(r.fc)} / ${esc(r.ft)}</td></tr><tr><td>Observación</td><td>${esc(r.tit)||'—'}</td></tr><tr><td>Estado mejora</td><td>${esc(r.estado)}</td></tr></table>
 <h4>Hallazgos informados</h4>${it||'<p class="ev-meta">No informa hallazgos: la tarea se revisó y no se encontró nada que mejorar (cuenta para adherencia).</p>'}`);}
function enlazar(root){
 root.querySelectorAll('[data-eq]').forEach(x=>{if(x._b)return;x._b=1;x.addEventListener('click',e=>{e.stopPropagation();const k=x.dataset.eq;lista(D.eq[k]||[],k.replaceAll('|',' · '));});});
 root.querySelectorAll('[data-per]').forEach(x=>{if(x._b||!x.dataset.per)return;x._b=1;x.addEventListener('click',()=>lista(D.per[x.dataset.per]||[],x.dataset.per));});
 root.querySelectorAll('[data-reg]').forEach(x=>{if(x._b)return;x._b=1;x.addEventListener('click',e=>{e.stopPropagation();verReg(x.dataset.reg);});});}
enlazar(document);
const sel=document.getElementById('areaSel');
sel.onchange=()=>{document.querySelectorAll('.vista').forEach(v=>v.classList.toggle('on',v.id===sel.value));window.scrollTo(0,0);};
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
@media print{.modal-bg{display:none!important}}
'''


def vista(nombre, dsem, d4, eq_sem, eq4, personas, top, series, cfg, ind, ind_ant, com, area=None):
    h = dsem[dsem.hallazgo]
    focos = com.get('focos') or focos_auto(eq_sem, eq4, ind, ind_ant, h)
    lectura = f'<div class="card logro" style="margin-bottom:14px">{com["lectura"]}</div>' if com.get('lectura') else ''
    k = '<div class="kpi-grid">' + ''.join([
        kpi('Registros RIT', ind['reg'], f'{ind["personas"]} personas · {dsem.compartida.sum()} con cuenta compartida'),
        kpi('Adherencia', f'{ind["pAdh"]}%' if ind['pAdh'] is not None else 's/d', f'{ind["dias"]} de {ind["esp"]:g} días-equipo esperados' + delta(ind['pAdh'], ind_ant and ind_ant['pAdh']), colk(ind['pAdh'], 'adherencia', cfg)),
        kpi('Registro oportuno', f'{ind["pOport"]}%' if ind['pOport'] is not None else 's/d', 'registrado ≤12 h del RIT' + delta(ind['pOport'], ind_ant and ind_ant['pOport']), colk(ind['pOport'], 'oportuno', cfg)),
        kpi('Con hallazgo', f'{ind["hall"]}', f'{ind["pHall"] if ind["pHall"] is not None else "s/d"}% de los registros' + delta(ind['pHall'], ind_ant and ind_ant['pHall'])),
        kpi('Hallazgos claros', f'{ind["pClaro"]}%' if ind['pClaro'] is not None else 's/d', f'{ind["claros"]} de {ind["hall"]} con pauta ≥2' + delta(ind['pClaro'], ind_ant and ind_ant['pClaro']), colk(ind['pClaro'], 'claridad', cfg)),
        kpi('No se entienden', ind['n0'] + ind['n1'], f'{ind["pegadas"]} listas pegadas · {ind["n0"]} sin contenido', 'red' if ind['n0'] + ind['n1'] else ''),
    ]) + '</div>'
    titulo = 'Planta' if area is None else 'Área'
    return f'''
<div class="mega-title" style="margin-top:22px"><span class="mega-tag">{titulo}</span> {esc(nombre)} — evaluación semanal de levantamientos RIT</div>
<div class="section-title">📌 La semana en números</div>{k}
<div class="section-title">🎯 Foco de la semana</div>{lectura}<div class="card blk b-az">{ul(focos)}
<div class="ideas-fuerza-note">{"Redactado tras revisión" if com.get("focos") else "Generado automáticamente por reglas"}. Adherencia = hacer y registrar el RIT; calidad = que el hallazgo informado se entienda.</div></div>
<div class="section-title">🧭 ¿Quién necesita apoyo? Adherencia × claridad por equipo (últimas 4 semanas)</div>{bloque_cuadrantes(eq4, cfg)}
<div class="section-title">📊 {"Detalle por área y especialidad (semana) — seleccione un área arriba para ver cada equipo" if area is None else "Detalle por especialidad y equipo (semana)"}</div>{bloque_tabla(dsem, eq_sem, series, cfg, area)}
<div class="ev-meta" style="margin-top:6px">Días esperados: Mantención = días hábiles (lun–vie, sin feriados); Operación = {cfg["operacion_dias_por_dia"]:g} × días de la semana por turno (5 turnos, 2 por día).
Clic en un equipo para ver sus levantamientos.</div>
<div class="section-title">👤 Personas (últimas 4 semanas)</div>{bloque_personas(personas, top, cfg)}
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
    return pd.DataFrame(filas)


def main(argv=None):
    p = argparse.ArgumentParser(description='Reporte semanal de calidad de levantamientos RIT')
    p.add_argument('--planta', default='Nueva Aldea')
    p.add_argument('--semana', default=None, help='Cualquier día de la semana a evaluar (AAAA-MM-DD); por defecto, la última semana completa')
    p.add_argument('--excel', default=None)
    p.add_argument('--top20', default=None)
    p.add_argument('--comentarios', default=None)
    p.add_argument('--json', action='store_true')
    p.add_argument('--salida', default='out')
    a = p.parse_args(argv)

    cfg = json.loads((CONFIG / 'rit.json').read_text(encoding='utf-8'))
    ruta = Path(a.excel) if a.excel else sorted(Path('data').glob('RIT_*.xlsx'))[-1]
    top_ruta = a.top20 or next(iter(sorted(Path('data').glob('Top_usuarios*.html'))), None)
    d = cargar(ruta, a.planta)
    top = cargar_top20(top_ruta, a.planta)
    if a.semana:
        lun = pd.Timestamp(a.semana).normalize()
        lun -= pd.Timedelta(days=lun.dayofweek)
    else:
        ult = d.dia.max()
        lun = ult - pd.Timedelta(days=ult.dayofweek) - (pd.Timedelta(days=7) if ult.dayofweek < 6 else pd.Timedelta(0))
    dom = lun + pd.Timedelta(days=6)
    ini4 = lun - pd.Timedelta(days=21)
    dsem, dant, d4 = d[d.semana == lun], d[d.semana == lun - pd.Timedelta(days=7)], d[(d.semana >= ini4) & (d.semana <= lun)]

    eq_sem = tabla_equipos(dsem.assign(), lun, dom, cfg)
    # equipos activos en las últimas 8 semanas, aunque no hayan registrado esta semana (adherencia 0)
    d8 = d[(d.semana > lun - pd.Timedelta(days=56)) & (d.semana <= lun)]
    activos = d8[['Area', 'Especialidad', 'Equipo']].drop_duplicates()
    eq_sem = activos.merge(eq_sem, how='left', on=['Area', 'Especialidad', 'Equipo'])
    for c in ('reg', 'dias', 'hall', 'claros', 'pegadas', 'n0', 'n1', 'personas'):
        eq_sem[c] = eq_sem[c].fillna(0).astype(int)
    eq_sem['esp'] = [esperados(e, lun, dom, cfg) for e in eq_sem.Especialidad]
    eq_sem['pAdh'] = [min(100, round(100 * x / y)) if y else None for x, y in zip(eq_sem.dias, eq_sem.esp)]
    eq_sem['lider'] = eq_sem.lider.fillna('')
    eq_sem = eq_sem.astype(object).where(eq_sem.notna(), None)

    eq4 = activos.merge(tabla_equipos(d4, ini4, dom, cfg), how='left', on=['Area', 'Especialidad', 'Equipo'])
    eq4['dias'] = eq4.dias.fillna(0)
    eq4['hall'] = eq4.hall.fillna(0).astype(int)
    eq4['esp'] = [esperados(e, ini4, dom, cfg) for e in eq4.Especialidad]
    eq4['pAdh'] = [min(100, round(100 * x / y)) if y else None for x, y in zip(eq4.dias, eq4.esp)]
    eq4['pClaro'] = eq4.pClaro.astype(object).where(eq4.pClaro.notna(), None)
    eq4['cuad'] = [cuadrante(x, c, h, cfg) for x, c, h in zip(eq4.pAdh, eq4.pClaro, eq4.hall)]
    eq4['clave'] = eq4.Area + '|' + eq4.Especialidad + '|' + eq4.Equipo

    # series de adherencia 8 semanas (equipo, especialidad, área)
    series = {}
    semanas = [lun - pd.Timedelta(days=7 * i) for i in range(7, -1, -1)]
    for s in semanas:
        ds = d[d.semana == s]
        fin = s + pd.Timedelta(days=6)
        for _, r in activos.iterrows():
            g = ds[(ds.Area == r.Area) & (ds.Especialidad == r.Especialidad) & (ds.Equipo == r.Equipo)]
            esp = esperados(r.Especialidad, s, fin, cfg)
            for clave in ((r.Area,), (r.Area, r.Especialidad), (r.Area, r.Especialidad, r.Equipo)):
                acc = series.setdefault(clave, {}).setdefault(s, [0, 0])
                acc[0] += g.dia.nunique()
                acc[1] += esp
    series = {k: [(s, min(100, round(100 * v[s][0] / v[s][1])) if v[s][1] else None) for s in semanas] for k, v in series.items()}

    comentarios = json.loads(Path(a.comentarios).read_text(encoding='utf-8')) if a.comentarios else {}
    personas = personas_4s(d4)
    areas = sorted(activos.Area.unique())
    ind = indicadores(dsem, eq_sem.esp.sum())
    ind_ant = indicadores(dant, sum(esperados(e, lun - pd.Timedelta(days=7), lun - pd.Timedelta(days=1), cfg) for e in activos.Especialidad))
    vistas = [vista(a.planta, dsem, d4, eq_sem, eq4, personas, top, series, cfg, ind, ind_ant, comentarios.get('Planta', {}))]
    for ar in areas:
        ea = eq_sem[eq_sem.Area == ar]
        ia = indicadores(dsem[dsem.Area == ar], ea.esp.sum())
        ia_ant = indicadores(dant[dant.Area == ar], sum(esperados(e, lun - pd.Timedelta(days=7), lun - pd.Timedelta(days=1), cfg) for e in activos[activos.Area == ar].Especialidad))
        vistas.append(vista(ar, dsem[dsem.Area == ar], d4[d4.Area == ar], ea, eq4[eq4.Area == ar], personas_4s(d4[d4.Area == ar]), top, series, cfg, ia, ia_ant,
                            comentarios.get(ar, {}), area=ar))

    css = Path('ref/estilos_base.css').read_text() + Path('ref/estilos_reporte.css').read_text() + CSS_EXTRA
    opts = ''.join(f'<option value="v{i}">{esc(n)}</option>' for i, n in enumerate(['Planta completa'] + areas))
    datos = json.dumps(datos_detalle(d4, set(eq4.clave)), ensure_ascii=False, default=str).replace('</', '<\\/')
    cuerpo = ''.join(f'<div class="vista{" on" if i == 0 else ""}" id="v{i}">{h}</div>' for i, h in enumerate(vistas))
    pag = f'''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RIT semanal {esc(a.planta)} {lun:%d-%m-%Y}</title><style>{css}</style></head><body>
<header><div class="hd"><div class="hd-left"><div><h1>Calidad de levantamientos RIT</h1>
<div class="sub">Reunión de Inicio de Turno · revisión de riesgos y controles en SoftExpert — adherencia y calidad de los hallazgos</div><div class="plt">Negocio Celulosa — Planta {esc(a.planta)}</div></div></div>
<div class="hd-right"><div class="hd-meta">Semana <b>{lun:%d-%m} a {dom:%d-%m-%Y}</b><br>Comparación con la semana anterior · cuadrantes y personas: 4 semanas<br>Fuente: {esc(ruta.name)}</div></div></div></header>
<div class="filterbar"><div class="filterbar-in"><div class="f"><label>Área</label><select id="areaSel">{opts}</select></div>
<div class="f"><label>Detalle</label><div style="font-size:12.5px;padding:7px 0">Clic en un equipo, una persona o un ejemplo</div></div>
<button class="btn" onclick="window.print()" style="margin-left:auto">🖨 Imprimir / PDF</button></div></div>
<div class="wrap">{cuerpo}
<div class="foot-note">Propósito del RIT (ficha de instancia): asegurar que el equipo inicie el turno alineado, con tareas claras y riesgos controlados; el producto esperado es el registro del análisis de riesgo en SoftExpert,
identificando actualización de documentos, cambios en riesgos o en procesos. Playbook MGO: los riesgos se revisan en el día a día durante el inicio de turno.
Pauta de hallazgos 0–3 automática por reglas de texto; los casos dudosos se revisan en el detalle.</div></div>
<div class="modal-bg" id="modal"><div class="card modal" id="modalBox"></div></div>
<script type="application/json" id="datos">{datos}</script><script>{JS}</script></body></html>'''
    out = Path(a.salida)
    out.mkdir(exist_ok=True)
    f = out / f'RIT_semanal_{a.planta.replace(" ", "_")}_{lun:%Y-%m-%d}.html'
    f.write_text(pag, encoding='utf-8')
    print(f)
    if a.json:
        res = dict(semana=[str(lun.date()), str(dom.date())], planta=ind, semana_anterior=ind_ant,
                   equipos=eq_sem.drop(columns=[c for c in eq_sem.columns if c in ('lider',)]).to_dict('records'),
                   cuadrantes={k: [f'{r.Area} · {r.Equipo}' for _, r in eq4[eq4.cuad == k].iterrows()] for k in CUAD},
                   personas_4s=personas.to_dict('records'),
                   hallazgos_semana=[dict(ID=int(r.ID), area=r.Area, equipo=r.Equipo, persona=r['Creado por'], texto=texto_hallazgo(r), pauta=int(r.nota), motivo=r.motivo)
                                     for _, r in dsem[dsem.hallazgo].iterrows()],
                   focos_automaticos=focos_auto(eq_sem, eq4, ind, ind_ant, dsem[dsem.hallazgo]))
        j = f.with_suffix('.json')
        j.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        print(j)


if __name__ == '__main__':
    main()
