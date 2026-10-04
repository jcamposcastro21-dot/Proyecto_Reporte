"""Reporte diario de calidad RdP por NAT.

Formato del Reporte de Calidad RdP (vista planta + radiografía por NAT) complementado con
los criterios del Playbook MGO y del Diagnóstico RDP (pauta 0–3, línea base y metas).

Uso:
    python3 -m reporte.diario --planta "Nueva Aldea" --fecha 2026-10-02 --json
    python3 -m reporte.diario --planta "Nueva Aldea" --fecha 2026-10-02 --comentarios comentarios/2026-10-02_Nueva_Aldea.json

Cálculo "a la fecha": una acción cuenta como cerrada solo si su Fecha cierre es ≤ fecha del
reporte, y solo se consideran eventos con Fecha Inicio ≤ fecha.
"""
import argparse
import html
import json
from pathlib import Path
import pandas as pd

from . import fuente
from .calidad import (calidad_titulo, calidad_causa, clasificar_accion, cargar_clasificacion_manual, pauta_evento,
                      claves, antecedentes, norm, CAUSA_TXT, CAUSA_DEBIL, TIPO_TXT)

CONFIG = Path('config')
VENTANA_CALIDAD = 30
DIAS_CREACION_MAX = 7   # Playbook: RdP cat. 1-2 se revisa 1 vez por semana; cat. 3 se emite en 5 días
GRUPO = {'Operativos': 'Operaciones', 'Procesos': 'Operaciones', 'Mecánicos': 'Mantención', 'Electrocontrol': 'Mantención'}
SUBAREAS = {'Operaciones': ['Operativos', 'Procesos'], 'Mantención': ['Mecánicos', 'Electrocontrol']}
ANALISIS_ESTRUCTURADO = ('5 porque', 'ishikawa', 'árbol')

# Semáforo por indicador: [verde, ámbar, menor_es_mejor]. Verde = meta del diagnóstico;
# ámbar se reemplaza en tiempo de ejecución por la línea base de la planta (rojo = peor que la línea base).
UMBRALES = {
    'pS': [40, 25, False], 'pPlazo': [80, 65, False], 'pTercero': [50, 20, False],
    'pNul': [5, 28, True], 'pCausal': [75, 58, False], 'pSinS': [20, 42, True],
}
PAUTA_TXT = {
    'p_tit': ('Identificación', ['Nulo ("0", "no", "3h")', 'Categoría de catálogo, sin equipo', 'Fenómeno específico', 'Fenómeno + equipo, tag o línea']),
    'p_causa': ('Análisis causal', ['Sin causa o escrita como tarea', 'Síntoma, estado del componente o hipótesis', 'Explica el mecanismo', 'Nombra el control que faltó o falló']),
    'p_acc': ('Acciones', ['Sin acciones', 'Solo correctivas, revisión o difusión', 'Al menos una preventiva o sistémica', 'Dos o más sistémicas, o extendida a equipos similares']),
}


def esc(s):
    return html.escape(str(s)) if s is not None and pd.notna(s) else ''


def fmt(d):
    return d.strftime('%d-%m') if pd.notna(d) else '—'


def fmtl(d):
    return d.strftime('%d-%m-%Y') if pd.notna(d) else '—'


def ev(i):
    return f'<code class="lk" data-ev="{int(i)}">{int(i)}</code>'


def leer_json(nombre, defecto):
    p = CONFIG / nombre
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else defecto


# ================================================================ cálculo
def preparar(reg, acc, fecha):
    """Eventos y acciones de TODAS las plantas a la fecha, con clasificación, pauta y flags."""
    fecha = pd.Timestamp(fecha).normalize()
    E = reg[reg['Fecha Inicio'] <= fecha].copy()
    A = acc[acc.RegistroId.isin(E.Id)].merge(E[['Id', 'Planta', 'NAT', 'Área Responsable', 'Fecha Inicio', '¿Se utilizó SAR?']],
                                             left_on='RegistroId', right_on='Id').drop(columns='Id')
    manual = cargar_clasificacion_manual()
    A['tipo'] = [manual.get(int(i), clasificar_accion(t)) for i, t in zip(A.AccionId, A['Acción'])]
    A['tipo_origen'] = ['manual' if int(i) in manual else 'auto' for i in A.AccionId]
    A['causa'] = A['Causa raíz'].map(calidad_causa)
    A['cerr'] = A['Fecha cierre'].notna() & (A['Fecha cierre'] <= fecha)
    A['tercero'] = A.cerr & (A.Responsable.map(norm) != A['Cerrada por'].map(norm))
    A['tarde'] = A.cerr & (A['Fecha cierre'] > A['Fecha Compromiso'])
    A['venc'] = ~A.cerr & (A['Fecha Compromiso'] < fecha)
    A['enplazo'] = (A.cerr & ~A.tarde) | (~A.cerr & ~A.venc)
    A['dias_atraso'] = (fecha - A['Fecha Compromiso']).dt.days.where(A.venc)
    A['dias_para'] = (A['Fecha Compromiso'] - fecha).dt.days.where(~A.cerr)

    E['tit'] = E['Evento tiempo perdido'].map(calidad_titulo)
    E['grupo'] = E['Área Responsable'].map(GRUPO).fillna('Otros')
    E['dias_abierta'] = (fecha - E['Fecha Inicio']).dt.days
    g = A.groupby('RegistroId')
    E['nAcc'] = E.Id.map(g.size()).fillna(0).astype(int)
    for t in 'SCR':
        E['n' + t] = E.Id.map(g.tipo.apply(lambda s, t=t: int((s == t).sum()))).fillna(0).astype(int)
    E['abiertas'] = E.Id.map(g.cerr.apply(lambda s: int((~s).sum()))).fillna(0).astype(int)
    E['autocierre'] = E.Id.map(g.apply(lambda d: bool(d.cerr.any()) and not d.tercero.any(), include_groups=False)).fillna(False).astype(bool)

    vacio = A.iloc[0:0]
    P = pd.DataFrame.from_dict({i: pauta_evento(t, g.get_group(i) if i in g.groups else vacio)
                                for i, t in zip(E.Id, E['Evento tiempo perdido'])}, orient='index')
    over = CONFIG / 'pauta_eventos.csv'
    if over.exists():
        for _, o in pd.read_csv(over).iterrows():
            for k in ('p_tit', 'p_causa', 'p_acc'):
                if int(o.Id) in P.index and pd.notna(o[k]):
                    P.loc[int(o.Id), k] = int(o[k])
    E = E.join(P, on='Id')
    E['causal_ok'] = E.p_causa >= 2

    causas = A.groupby('RegistroId')['Causa raíz'].apply(lambda s: ' '.join(s.dropna().map(str)))
    E['_texto'] = (E['Evento tiempo perdido'].fillna('').astype(str) + ' ' + E.Id.map(causas).fillna('')).str.lower()
    kt = [claves(t) for t in E['Evento tiempo perdido']]
    kc = [claves(causas.get(i, '')) for i in E.Id]
    E['_tags'] = [t[0] | c[0] for t, c in zip(kt, kc)]
    E['_pal'] = [t[1] | c[1] for t, c in zip(kt, kc)]
    return E, A, fecha


def indicadores(ev_, ac):
    c = ac[ac.cerr]
    fin = ev_[ev_.nAcc > 0]
    ab = ac[~ac.cerr]
    pct = lambda x, n: round(100 * x / n) if n else None
    return dict(
        ev=len(ev_), fin=int((ev_.Estado == 'Cerrado').sum()), cur=int((ev_.Estado != 'Cerrado').sum()),
        acc=len(ac), S=int((ac.tipo == 'S').sum()), C=int((ac.tipo == 'C').sum()), R=int((ac.tipo == 'R').sum()),
        pS=pct((ac.tipo == 'S').sum(), len(ac)),
        plazo=int(ac.enplazo.sum()), pPlazo=pct(ac.enplazo.sum(), len(ac)),
        cerrOk=int((ac.cerr & ~ac.tarde).sum()), tarde=int(ac.tarde.sum()), abOk=int((~ac.cerr & ~ac.venc).sum()), venc=int(ac.venc.sum()),
        abiertas=len(ab), pVencAb=pct(ab.venc.sum(), len(ab)),
        cerr=len(c), tercero=int(c.tercero.sum()), pTercero=pct(c.tercero.sum(), len(c)),
        nul=int((ev_.tit == 'nulo').sum()), cat=int((ev_.tit == 'catalogo').sum()), pNul=pct((ev_.tit == 'nulo').sum(), len(ev_)),
        conAcc=len(fin), causal=int(fin.causal_ok.sum()), pCausal=pct(fin.causal_ok.sum(), len(fin)),
        mediaCausal=round(float(fin.p_causa.mean()), 2) if len(fin) else None,
        sinS=int((fin.nS == 0).sum()), pSinS=pct((fin.nS == 0).sum(), len(fin)),
        cadena=int(fin.cadena.sum()), sist=int(fin.causa_sistemica.sum()), verif=int(fin.verificacion.sum()),
        sar=int((ev_['¿Se utilizó SAR?'] == 'Si').sum()))


def ventana_novedades(fecha, dias):
    """Novedades = Fecha Inicio (o cierre) entre `desde` y la fecha del reporte, ambos incluidos.
    Por defecto: ayer y hoy; los lunes, desde el viernes."""
    if dias is None:
        dias = 3 if fecha.weekday() == 0 else 1
    return fecha - pd.Timedelta(days=dias)


def estado_caso(caso, E, A, base_hasta):
    """Estado vivo de un caso del diagnóstico: acciones clave, acciones abiertas y eventos nuevos relacionados
    (misma planta y NAT, posteriores al diagnóstico, con alguna palabra clave del caso en título o causas)."""
    ac = A[A.RegistroId.isin(caso['eventos']) | A.AccionId.isin(caso.get('acciones_clave', []))]
    pal = [k.lower() for k in caso.get('claves', [])]
    nuevos = E[(E.Planta == caso['planta']) & (E.NAT == caso['nat']) & ~E.Id.isin(caso['eventos'])
               & (E['Fecha Inicio'] > base_hasta) & E._texto.map(lambda t: any(k in t for k in pal))]
    return dict(clave=ac[ac.AccionId.isin(caso.get('acciones_clave', []))], abiertas=ac[~ac.cerr], vencidas=ac[ac.venc], nuevos=nuevos)


def calcular_ambito(E, A, planta, desde, d_cal, base, nat=None):
    Ep = E[E.Planta == planta]
    ev_ = Ep if nat is None else Ep[Ep.NAT == nat]
    ac = A[A.Planta == planta] if nat is None else A[(A.Planta == planta) & (A.NAT == nat)]
    evp, acp = ev_[ev_['Fecha Inicio'] >= d_cal], ac[ac['Fecha Inicio'] >= d_cal]
    evb = ev_[(ev_['Fecha Inicio'] >= base[0]) & (ev_['Fecha Inicio'] <= base[1])]
    acb = ac[ac.RegistroId.isin(evb.Id)]

    nuevos = ev_[ev_['Fecha Inicio'] >= desde].copy()
    nuevos['ante'] = [antecedentes(r, Ep) for _, r in nuevos.iterrows()]
    rec = evp.copy()
    rec['ante'] = [antecedentes(r, Ep) for _, r in rec.iterrows()]
    rec = rec[rec.ante.map(len) > 0]

    abiertas = ac[~ac.cerr]
    m = dict(nat=nat, ev=ev_, evp=evp, acp=acp, ac=ac, nuevos=nuevos, rec=rec,
             creacion=ev_[ev_.Estado == 'En creación'].sort_values('dias_abierta', ascending=False),
             abiertas=abiertas.sort_values('Fecha Compromiso'),
             vencidas=abiertas[abiertas.venc].sort_values('dias_atraso', ascending=False),
             por_vencer=abiertas[~abiertas.venc & (abiertas.dias_para <= 7)].sort_values('dias_para'),
             cerradas=ac[ac.cerr & (ac['Fecha cierre'] >= desde)],
             ind=indicadores(evp, acp), base=indicadores(evb, acb))
    if nat is None:
        Er, Ar = E[(E.Planta != planta) & (E['Fecha Inicio'] >= d_cal)], A[(A.Planta != planta) & (A['Fecha Inicio'] >= d_cal)]
        m['resto'] = indicadores(Er, Ar)
        m['sar'] = {v: indicadores(evp[evp['¿Se utilizó SAR?'] == v], acp[acp['¿Se utilizó SAR?'] == v]) for v in ('Si', 'No')}
    return m


# ================================================================ chequeos y textos automáticos
def chequeo_evento(e, acciones):
    """Lista de (ok|amb|red|gray, texto) con criterios del playbook MGO y del diagnóstico."""
    out = [({0: 'red', 1: 'amb', 2: 'amb'}.get(int(e.p_tit), 'ok'),
            ['Título nulo: no identifica el desvío (paso 1 del ciclo RdP)', 'Título de catálogo: falta fenómeno y equipo/tag',
             'Título con fenómeno; falta equipo/tag', 'Título con fenómeno y equipo'][int(e.p_tit)])]
    herr = norm(e.Herramienta)
    estructurada = any(h in herr for h in ANALISIS_ESTRUCTURADO)
    ante = e.get('ante') if isinstance(e.get('ante'), list) else []
    if ante:
        out.append(('ok' if estructurada else 'red',
                    'Posible recurrencia: ' + ('se usó análisis estructurado' if estructurada else 'el playbook exige 5 porqués / Ishikawa / árbol de falla')))
    if e.nAcc == 0:
        out.append(('amb', 'Sin acciones registradas aún'))
        return out
    pc = int(e.p_causa)
    if pc == 3:
        out.append(('ok', 'Causa nombra el control que faltó o falló'))
    elif pc == 2:
        out.append(('amb', 'Causa explica el mecanismo; falta el control que debió evitarlo'))
    else:
        peor = next((k for k in ('vacia', 'tarea', 'hipotesis', 'estado', 'sintoma') if k in set(acciones.causa)), 'sintoma')
        out.append(('red', f'Causa débil: {CAUSA_TXT[peor]}'))
    if estructurada and pc <= 1:
        out.append(('amb', f'Declara "{e.Herramienta}", pero la causa final no refleja la cadena de análisis'))
    if e.error_humano:
        out.append(('amb', 'Causa atribuida a la persona: preguntar qué condición lo permitió, no solo difundir'))
    out.append(('ok' if e.nS else 'red', f'{e.nS} sistémica · {e.nC} correctiva · {e.nR} revisión'
                + (' (extendida a equipos similares)' if e.extension else '') + ('' if e.nS else ' → sin barrera que evite la repetición')))
    if e.difusion:
        out.append(('amb', f'{e.difusion} acción(es) de difusión: indicar qué conducta o condición cambia'))
    if e.proveedor:
        out.append(('amb', 'Se deriva al proveedor: exigir causa propia del modo de falla'))
    out.append(('ok', 'Define seguimiento o verificación') if e.verificacion else
               ('amb', 'Sin verificación de eficacia definida (paso 5: validar que la solución se sostiene)'))
    if e.autocierre:
        out.append(('amb', 'Todas las acciones cerradas las cerró su propio responsable'))
    out.append(('amb', 'SAR utilizado: registrar qué propuso y qué se aceptó') if e['¿Se utilizó SAR?'] == 'Si' else ('gray', 'SAR no utilizado'))
    return out


def obs_accion(r):
    o = []
    if r.venc:
        o.append(('red', f'vencida hace {int(r.dias_atraso)} d'))
    if r.cerr and not r.tercero:
        o.append(('amb', 'autocierre'))
    if r.tarde:
        o.append(('red', f'cerrada tarde {int((r["Fecha cierre"] - r["Fecha Compromiso"]).days)} d'))
    if r.cerr and r.tipo == 'R':
        o.append(('az', 'registrar resultado'))
    if r.causa in CAUSA_DEBIL:
        o.append(('amb', CAUSA_TXT[r.causa]))
    return o


def exigir_accion(r):
    if r.tipo == 'R':
        return 'Registrar el resultado de la revisión y decidir la acción definitiva: una revisión cerrada sin resultado no reduce el riesgo.'
    if r.tipo == 'C':
        return '¿Qué barrera evita que se repita? Pedir una acción que cambie plan, estándar, diseño o lógica, o justificar por qué no aplica.'
    return '¿Cómo se verificará la eficacia? Definir criterio medible y plazo (60–90 días) y que la cierre un tercero.'


def fortalezas_auto(m):
    i, r = m['ind'], m.get('resto')
    f = []
    if i['pPlazo'] is not None and i['pPlazo'] >= UMBRALES['pPlazo'][1]:
        comp = f' vs {r["pPlazo"]}% en el resto del negocio' if r and r['pPlazo'] is not None else ''
        f.append(f'<b>Disciplina de plazos:</b> {i["pPlazo"]}% de las acciones en plazo ({i["plazo"]}/{i["acc"]}){comp}; {i["venc"]} vencidas.')
    buenas = m['evp'][(m['evp'].p_causa == 3) & (m['evp'].nS > 0)]
    if len(buenas):
        ej = []
        for _, e in buenas.head(3).iterrows():
            a = m['acp'][(m['acp'].RegistroId == e.Id) & (m['acp'].tipo == 'S')].iloc[0]
            c = m['acp'][(m['acp'].RegistroId == e.Id) & (m['acp'].causa == 'control')].iloc[0]
            ej.append(f'{ev(e.Id)} «{esc(str(c["Causa raíz"])[:80])}» → «{esc(str(a["Acción"])[:80])}»')
        f.append(f'<b>Llegan al control que falló y lo corrigen</b> ({len(buenas)} RdP): ' + '; '.join(ej) + '.')
    ext = m['evp'][m['evp'].extension]
    if len(ext):
        f.append(f'<b>Extienden la solución a equipos similares:</b> {", ".join(ev(x) for x in ext.Id)}.')
    if i['ev'] and i['nul'] == 0:
        f.append(f'<b>Registro completo:</b> ningún título nulo en {i["ev"]} eventos.')
    if i['pTercero'] is not None and i['pTercero'] >= UMBRALES['pTercero'][0]:
        f.append(f'<b>Cierre verificado por otro:</b> {i["tercero"]} de {i["cerr"]} acciones cerradas por alguien distinto del responsable.')
    return f[:3]


def brechas_auto(m):
    i, evp, acp = m['ind'], m['evp'], m['acp']
    b = []  # (severidad, texto)
    if i['conAcc'] and i['sinS']:
        ids = evp[(evp.nAcc > 0) & (evp.nS == 0)].Id
        b.append((i['pSinS'] or 0, f'<b>Reparar sin prevenir:</b> {i["sinS"]} de {i["conAcc"]} RdP ({i["pSinS"]}%) no tienen ninguna acción sistémica '
                  f'({", ".join(ev(x) for x in ids[:6])}{"…" if len(ids) > 6 else ""}).'))
    deb = acp[acp.causa.isin(CAUSA_DEBIL)].drop_duplicates('RegistroId')
    if i['conAcc'] and i['pCausal'] is not None and i['pCausal'] < UMBRALES['pCausal'][0] and len(deb):
        ej = ', '.join(f'"{esc(str(r["Causa raíz"])[:40])}" ({ev(r.RegistroId)})' for _, r in deb.head(4).iterrows())
        b.append((100 - i['pCausal'], f'<b>Análisis causal que se queda en el componente:</b> solo {i["causal"]} de {i["conAcc"]} RdP ({i["pCausal"]}%) explican el mecanismo o el control. '
                  f'Causas como estado, síntoma, tarea o hipótesis: {ej}.'))
    if i['cerr'] and i['pTercero'] is not None and i['pTercero'] < UMBRALES['pTercero'][1]:
        b.append((100 - i['pTercero'], f'<b>Cierre sin verificación de eficacia:</b> {i["cerr"] - i["tercero"]} de {i["cerr"]} acciones cerradas ({100 - i["pTercero"]}%) '
                  'las cerró su propio responsable. Cerrada significa ejecutada, no eficaz.'))
    if i['nul'] or i['cat']:
        ids = evp[evp.tit == 'nulo'].Id
        b.append((i['pNul'] or 0, f'<b>Calidad del registro:</b> {i["nul"]} títulos nulos' + (f' ({", ".join(ev(x) for x in ids[:6])})' if len(ids) else '')
                  + f' y {i["cat"]} de catálogo, de {i["ev"]} eventos: sin fenómeno ni equipo no se puede buscar antecedentes.'))
    if i['venc']:
        b.append((i['venc'] * 5, f'<b>Plazos:</b> {i["venc"]} acciones vencidas y {i["tarde"]} cerradas tarde ({i["pPlazo"]}% en plazo).'))
    prov = evp[evp.proveedor > 0]
    if len(prov):
        b.append((30, f'<b>Causa delegada al proveedor:</b> {", ".join(ev(x) for x in prov.Id)} terminan en revisión o reunión con el proveedor sin causa propia del modo de falla.'))
    return [t for _, t in sorted(b, key=lambda x: -x[0])[:3]]


def logro_auto(m):
    i, r = m['ind'], m.get('resto')
    partes = []
    if r and i['pVencAb'] is not None and r['pVencAb'] is not None and i['pVencAb'] < r['pVencAb']:
        partes.append(f'solo {i["venc"]} de {i["abiertas"]} acciones abiertas ({i["pVencAb"]}%) están vencidas, frente a {r["pVencAb"]}% en el resto del negocio')
    cad = m['evp'][m['evp'].cadena]
    if len(cad):
        partes.append(f'{len(cad)} investigación(es) cierran la cadena completa título → causa sistémica → acción preventiva: {", ".join(ev(x) for x in cad.Id)}')
    if not partes and i['pPlazo'] is not None:
        partes.append(f'{i["pPlazo"]}% de las acciones del período están en plazo')
    return ('En los últimos 30 días, ' + '; además, '.join(partes) + '.') if partes else ''


def casos_auto(m, ctx):
    out = []
    for c in ctx['casos']:
        if m['nat'] not in (None, c['nat']):
            continue
        s = estado_caso(c, ctx['E'], ctx['A'], ctx['base'][1])
        clave = '; '.join(f'acción {int(r.AccionId)} de {ev(r.RegistroId)} ' + (
            f'<span class="chip ok">cerrada {fmt(r["Fecha cierre"])}</span>' if r.cerr else
            f'<span class="chip red">vencida {int(r.dias_atraso)} d</span>' if r.venc else
            f'<span class="chip amb">abierta, vence {fmt(r["Fecha Compromiso"])}</span>') for _, r in s['clave'].iterrows())
        nuevo = (f' <span class="chip red">nuevo evento relacionado: {", ".join(str(int(x)) for x in s["nuevos"].Id)}</span>' if len(s['nuevos']) else '')
        color = {'Confirmada': 'red', 'Probable': 'amb'}.get(c['clasificacion'], 'az')
        out.append(f'<b>{esc(c["titulo"])}</b> <span class="chip {color}">recurrencia {c["clasificacion"].lower()}</span>{nuevo}<br>'
                   f'{" → ".join(ev(x) for x in c["eventos"])}. {esc(c["que_vigilar"])}'
                   + (f'<br><small>Hoy: {clave}{"; " if clave else ""}{len(s["abiertas"])} acciones abiertas del caso, {len(s["vencidas"])} vencida(s).</small>'))
    ids_casos = {i for c in ctx['casos'] for i in c['eventos']}
    for _, e in m['rec'].iterrows():
        if e.Id not in ids_casos and len(out) < 6 and not any(i in ids_casos for i, _, _ in e.ante):
            out.append(f'<b>Posible recurrencia nueva: {ev(e.Id)}</b> {esc(e["Evento tiempo perdido"])} — antecedentes {", ".join(ev(i) for i, _, _ in e.ante[:3])}. Validar con el NAT.')
    return out


def focos_auto(m):
    f = []
    for _, e in m['nuevos'][m['nuevos'].ante.map(len) > 0].head(2).iterrows():
        f.append(f'<b>Posible recurrencia en {ev(e.Id)}</b> ({esc(e["Evento tiempo perdido"])}): antecedentes {", ".join(ev(i) for i, _, _ in e.ante[:3])}. '
                 'Revisar si las acciones previas se cerraron sin verificar eficacia y abordar como un solo análisis.')
    sinS = m['nuevos'][(m['nuevos'].nAcc > 0) & (m['nuevos'].nS == 0)]
    if len(sinS):
        f.append(f'<b>{len(sinS)} RdP nueva(s) sin acción sistémica</b> ({", ".join(ev(i) for i in sinS.Id)}): pedir al menos una acción que cambie plan, '
                 'estándar, diseño o lógica, o la justificación escrita de por qué no aplica.')
    v = m['vencidas']
    if len(v):
        f.append(f'<b>{len(v)} acción(es) vencida(s)</b>, la más antigua con {int(v.dias_atraso.max())} días ({ev(v.iloc[0].RegistroId)}/{int(v.iloc[0].AccionId)}): '
                 'reprogramar con fecha y responsable confirmados.')
    cr = m['creacion'][m['creacion'].dias_abierta > DIAS_CREACION_MAX]
    if len(cr):
        f.append(f'<b>{len(cr)} RdP en creación hace más de {DIAS_CREACION_MAX} días</b> ({", ".join(ev(i) for i in cr.Id[:5])}): cerrar el análisis en la próxima reunión RdP.')
    nul = m['nuevos'][m['nuevos'].tit == 'nulo']
    if len(nul):
        f.append(f'<b>Título nulo en {", ".join(ev(i) for i in nul.Id)}</b>: completar fenómeno y equipo/tag antes de analizar.')
    return f[:4]


# ================================================================ HTML
def pill(v, k):
    if v is None:
        return '<span class="pill gray">s/d</span>'
    g, w, inv = UMBRALES[k]
    ok = v <= g if inv else v >= g
    mid = v <= w if inv else v >= w
    return f'<span class="pill {"ok" if ok else "amb" if mid else "red"}">{v}%</span>'


def colk(v, k):
    if v is None:
        return ''
    g, w, inv = UMBRALES[k]
    return '' if (v <= g if inv else v >= g) else 'amb' if (v <= w if inv else v >= w) else 'red'


COLS = [('pS', 'S', 'acc'), ('pPlazo', 'plazo', 'acc'), ('pTercero', 'tercero', 'cerr'), ('pNul', 'nul', 'ev'), ('pCausal', 'causal', 'conAcc'), ('pSinS', 'sinS', 'conAcc')]


def fila(nombre, s, negrita=False, clase=''):
    t = 'b' if negrita else 'span'
    celdas = ''.join(f'<td class="num">{pill(s[k], k)} <small>{s[n]}/{s[d]}</small></td>' for k, n, d in COLS)
    return f'<tr class="{clase}"><td><{t}>{nombre}</{t}></td><td class="num">{s["ev"]}</td><td class="num">{s["acc"]}</td>{celdas}</tr>'


def fila_meta(metas):
    c = ''.join(f'<td class="num"><small>{"≤" if metas[k].get("sentido") == "max" else "≥"}{metas[k]["valor"]}%</small></td>' if k in metas else '<td></td>' for k, _, _ in COLS)
    return f'<tr class="meta"><td><i>Meta (Diagnóstico)</i></td><td></td><td></td>{c}</tr>'


def cabecera(nombre):
    return (f'<tr><th>{nombre}</th><th>Eventos</th><th>Acciones</th><th>% Acciones sistémicas</th><th>% Acciones en plazo</th><th>% Cierre por tercero</th>'
            '<th>% Títulos nulos</th><th>% Análisis causal adecuado</th><th>% RdP solo reparación</th></tr>')


def kpi(label, valor, sub, color='', accent=False):
    return (f'<div class="card kpi{" accent" if accent else ""}"><div class="kpi-label">{label}</div><div class="kpi-value num {color}">{valor}</div>'
            f'<div class="kpi-sub">{sub}</div></div>')


def ul(items):
    return '<ul>' + ''.join(f'<li>{x}</li>' for x in items) + '</ul>' if items else '<p class="ev-meta">Sin elementos.</p>'


def barra(lbl, s):
    a = s['acc'] or 1
    seg = lambda v, c: f'<i style="width:{100 * v / a:.1f}%;background:{c}"></i>'
    return (f'<div class="bar-row"><div class="lbl"><span><b>{lbl}</b></span><span class="num">{s["S"]} sist. · {s["C"]} corr. · {s["R"]} rev. (n={s["acc"]})</span></div>'
            f'<div class="bar-track stk">{seg(s["S"], "var(--ok)")}{seg(s["C"], "var(--naranja)")}{seg(s["R"], "var(--madera)")}</div></div>')


VENC_PILL = '<span class="pill red">vencida</span>'
LEYENDA_TIPO = ('<div class="legend"><span><i style="background:var(--ok)"></i>Preventiva / sistémica</span><span><i style="background:var(--naranja)"></i>Correctiva</span>'
                '<span><i style="background:var(--madera)"></i>Revisión / difusión</span></div>')


def tabla_acciones(df, modo, limite=30):
    if not len(df):
        return '<div class="card vacio">Sin acciones en esta categoría.</div>'
    extra_h = {'vencidas': '<th>Compromiso</th><th>Atraso</th>', 'por_vencer': '<th>Compromiso</th><th>Vence en</th>',
               'cerradas': '<th>Cerrada por</th><th>Cierre</th><th>Observación</th>', 'abiertas': '<th>Compromiso</th><th>Estado</th>'}[modo]
    b = ''
    for _, r in df.head(limite).iterrows():
        base = (f'<tr class="clic" data-ac="{int(r.AccionId)}" title="Clic para ver el detalle"><td>{ev(r.RegistroId)}<div class="ev-meta">{esc(r.NAT)}</div></td>'
                f'<td>{esc(str(r["Acción"])[:140])}<div class="ev-meta">Causa: {esc(str(r["Causa raíz"])[:90])}</div></td>'
                f'<td><span class="chip {dict(S="ok", C="amb", R="az")[r.tipo]}">{TIPO_TXT[r.tipo]}</span></td><td>{esc(r.Responsable)}</td>')
        if modo == 'vencidas':
            b += base + f'<td class="num">{fmt(r["Fecha Compromiso"])}</td><td class="num"><span class="pill red">{int(r.dias_atraso)} d</span></td></tr>'
        elif modo == 'por_vencer':
            b += base + f'<td class="num">{fmt(r["Fecha Compromiso"])}</td><td class="num">{int(r.dias_para)} d</td></tr>'
        elif modo == 'abiertas':
            b += base + f'<td class="num">{fmtl(r["Fecha Compromiso"])}</td><td>{VENC_PILL if r.venc else "al día"}</td></tr>'
        else:
            obs = ' '.join(f'<span class="chip {c}">{t}</span>' for c, t in obs_accion(r) if t in ('autocierre', 'registrar resultado') or t.startswith('cerrada tarde'))
            b += base + f'<td>{esc(r["Cerrada por"])}</td><td class="num">{fmt(r["Fecha cierre"])}</td><td>{obs or "—"}</td></tr>'
    mas = f'<div class="ev-meta" style="padding:8px 10px">… y {len(df) - limite} más</div>' if len(df) > limite else ''
    return f'<div class="card scroll"><table><tr><th>RdP</th><th>Acción</th><th>Tipo</th><th>Responsable</th>{extra_h}</tr>{b}</table>{mas}</div>'


def pauta_chips(e):
    if pd.isna(e.p_causa):
        return f'<span class="chip gray">I {int(e.p_tit)}</span> <span class="chip gray">sin acciones</span>'
    c = lambda v: 'ok' if v >= 2 else 'amb' if v == 1 else 'red'
    return ''.join(f'<span class="chip {c(int(v))}" title="{PAUTA_TXT[k][0]}: {PAUTA_TXT[k][1][int(v)]}">{l} {int(v)}</span> '
                   for k, v, l in (('p_tit', e.p_tit, 'I'), ('p_causa', e.p_causa, 'C'), ('p_acc', e.p_acc, 'A')))


def bloque_nuevos(m):
    if not len(m['nuevos']):
        return '<div class="card vacio">Sin RdP nuevas en la ventana.</div>'
    filas = ''
    icon = {'ok': '✓', 'amb': '!', 'red': '✕', 'gray': '·'}
    for _, e in m['nuevos'].sort_values('Fecha Inicio').iterrows():
        acc = m['ac'][m['ac'].RegistroId == e.Id]
        chk = ''.join(f'<li><span class="chip {c}">{icon[c]}</span> {esc(t)}</li>' for c, t in chequeo_evento(e, acc))
        ante = ', '.join(f'{ev(i)} <small>{fmt(f)} · {esc(k)}</small>' for i, f, k in e.ante[:3]) or '—'
        filas += (f'<tr><td>{ev(e.Id)}<div class="ev-meta">{fmt(e["Fecha Inicio"])} · {esc(e.Estado)}</div><div style="margin-top:4px">{pauta_chips(e)}</div></td>'
                  f'<td><div class="ev-tit">{esc(e["Evento tiempo perdido"])}</div><div class="ev-meta">{esc(e.NAT)} · {esc(e["Área Responsable"])} · '
                  f'{esc(e["Líder responsable"])} · {esc(e.Herramienta)}</div><div class="ev-meta" style="margin-top:4px">{e.nAcc} acciones — clic en el ID para ver causas y acciones</div></td>'
                  f'<td><ul class="chk">{chk}</ul></td><td>{ante}</td></tr>')
    return ('<div class="card scroll"><table><tr><th>RdP · pauta</th><th>Evento</th><th>Chequeo de calidad (playbook MGO + diagnóstico)</th>'
            f'<th>Antecedentes 12 meses</th></tr>{filas}</table></div>'
            '<div class="ev-meta" style="margin-top:6px">Pauta 0–3 del Diagnóstico: I = identificación, C = análisis causal, A = acciones (≥2 = adecuado). '
            'Pase el cursor sobre cada puntaje para ver su criterio.</div>')


def tabla_eventos(evs):
    if not len(evs):
        return '<div class="card vacio">Sin eventos en el período.</div>'
    b = ''
    for _, e in evs.sort_values('Fecha Inicio', ascending=False).iterrows():
        tit = f'<span class="pill red">{esc(e["Evento tiempo perdido"])}</span>' if e.tit == 'nulo' else esc(e['Evento tiempo perdido'])
        est = 'Finalizada' if e.Estado == 'Cerrado' else '<span class="pill amb">En creación</span>'
        sis = '<span class="pill red">0</span>' if e.nAcc and not e.nS else e.nS
        b += (f'<tr class="clic" data-evrow="{int(e.Id)}"><td>{ev(e.Id)}</td><td class="num">{fmt(e["Fecha Inicio"])}</td><td>{tit}</td>'
              f'<td>{esc(e["Área Responsable"])}</td><td>{esc(e["Líder responsable"])}</td><td>{esc(e.Herramienta)}</td><td>{"Sí" if e["¿Se utilizó SAR?"] == "Si" else "No"}</td>'
              f'<td>{est}</td><td>{pauta_chips(e)}</td><td class="num">{e.nAcc}</td><td class="num">{sis}</td><td class="num">{e.abiertas}</td></tr>')
    return ('<div class="card scroll"><table><tr><th>ID</th><th>Inicio</th><th>Título</th><th>Área</th><th>Líder</th><th>Herramienta</th><th>SAR</th><th>Estado</th>'
            f'<th>Pauta 0–3</th><th>Acciones</th><th>Sistémicas</th><th>Abiertas</th></tr>{b}</table></div>')


def bloque_recurrencias(rec):
    if not len(rec):
        return '<div class="card vacio">Sin coincidencias con eventos previos.</div>'
    b = ''.join(f'<tr><td>{ev(e.Id)}<div class="ev-meta">{fmt(e["Fecha Inicio"])} · {esc(e.NAT)}</div></td><td>{esc(e["Evento tiempo perdido"])}</td>'
                f'<td>{", ".join(f"{ev(i)} <small>{fmt(f)} · {esc(k)}</small>" for i, f, k in e.ante[:4])}</td></tr>'
                for _, e in rec.sort_values('Fecha Inicio', ascending=False).iterrows())
    return ('<div class="card scroll"><table><tr><th>Evento</th><th>Título</th><th>Antecedentes (coincidencia)</th></tr>'
            f'{b}</table></div><div class="ev-meta" style="margin-top:6px">Coincidencia por tag o palabras clave en título y causas, misma NAT, 12 meses. '
            'Es una alerta: se confirma con el mismo equipo/tag y modo de falla, y acciones previas cerradas sin eficacia.</div>')


def tabla_sar(sar):
    s, n = sar['Si'], sar['No']
    p = lambda a, b: f'{a}/{b} ({round(100 * a / b)}%)' if b else '—'
    filas = [('Análisis causal adecuado (pauta ≥2)', p(s['causal'], s['conAcc']), p(n['causal'], n['conAcc'])),
             ('RdP con al menos una acción sistémica', p(s['conAcc'] - s['sinS'], s['conAcc']), p(n['conAcc'] - n['sinS'], n['conAcc'])),
             ('% acciones sistémicas', p(s['S'], s['acc']), p(n['S'], n['acc'])),
             ('% acciones en plazo', p(s['plazo'], s['acc']), p(n['plazo'], n['acc'])),
             ('Títulos nulos', p(s['nul'], s['ev']), p(n['nul'], n['ev'])),
             ('Aporte de SAR documentado', '0', '—')]
    b = ''.join(f'<tr><td>{a}</td><td class="num">{x}</td><td class="num">{y}</td></tr>' for a, x, y in filas)
    return (f'<div class="card scroll"><table><tr><th>Indicador (últimos {VENTANA_CALIDAD} días)</th><th>Con SAR ({s["ev"]} eventos)</th><th>Sin SAR ({n["ev"]} eventos)</th></tr>{b}</table></div>'
            '<div class="ev-meta" style="margin-top:6px">El uso de SAR no es aleatorio (depende del líder y del NAT) y la base solo registra Sí/No: '
            'no atribuir diferencias a SAR. El MGO pide impulsar SAR; para evaluarlo hay que registrar qué propuso y qué se aceptó.</div>')


def bloque_medidas(med):
    if not med or not med.get('medidas'):
        return '<div class="card vacio">Sin medidas de control registradas para este NAT. Se agregan en config/medidas_control.json.</div>'
    filas = ''.join(f'<tr><td style="min-width:150px"><b>{x["caso"]}</b><div class="ev-meta">{esc(x.get("estado", ""))}</div></td><td>{esc(x["control_que_falto"])}</td>'
                    f'<td>{esc(x["medida"])}</td><td>{esc(x["verificacion"])}</td></tr>' for x in med['medidas'])
    return (f'<div class="card logro" style="font-size:13px"><b>Conclusión:</b> {med.get("conclusion", "")}</div>'
            f'<div class="card scroll" style="margin-top:12px"><table><tr><th>Caso</th><th>Control que faltó o falló</th><th>Medida de control propuesta</th>'
            f'<th>Verificación de eficacia</th></tr>{filas}</table></div>'
            '<div class="ideas-fuerza-note" style="border:none">Medidas propuestas a partir del texto registrado; deben validarse técnicamente con el NAT. '
            'Cuando el evento se repite, priorizar barreras duras (eliminar, sustituir, rediseñar, separar) sobre controles administrativos.</div>')


def tabla_resumen_planta(m, ctx):
    evp, acp = m['evp'], m['acp']
    sub = lambda mask: indicadores(evp[mask], acp[acp.RegistroId.isin(evp[mask].Id)])
    filas = ''
    for g, subs in SUBAREAS.items():
        filas += fila(g, sub(evp.grupo == g), True)
        for s in subs:
            filas += fila(f'&nbsp;&nbsp;↳ {s}', sub(evp['Área Responsable'] == s))
    for ar in sorted(evp[evp.grupo == 'Otros']['Área Responsable'].unique()):
        filas += fila(f'{esc(ar)} <small>(fuera de la comparación)</small>', sub(evp['Área Responsable'] == ar))
    filas += fila(f'Total {esc(ctx["planta"])}', m['ind'], True)
    filas += fila('Resto del negocio', m['resto'], False, 'ref')
    filas += fila(f'Línea base {esc(ctx["planta"])} ({fmt(ctx["base"][0])} a {fmt(ctx["base"][1])})', m['base'], False, 'ref')
    filas += fila_meta(ctx['metas'])
    return f'<div class="card scroll"><table>{cabecera("Área")}{filas}</table></div>'


def bloque_hoy(m, ctx):
    v, pv = m['vencidas'], m['por_vencer']
    cr_lenta = int((m['creacion'].dias_abierta > DIAS_CREACION_MAX).sum())
    return '<div class="kpi-grid">' + ''.join([
        kpi('RdP nuevas', len(m['nuevos']), f'{fmt(ctx["desde"])} a {fmt(ctx["fecha"])}', accent=True),
        kpi('RdP en creación', len(m['creacion']), f'{cr_lenta} con más de {DIAS_CREACION_MAX} días', 'red' if cr_lenta else ''),
        kpi('Acciones vencidas', len(v), f'de {len(m["abiertas"])} abiertas', 'red' if len(v) else ''),
        kpi('Vencen en 7 días', len(pv), 'para revisar en la reunión', 'amb' if len(pv) else ''),
        kpi('Cerradas en la ventana', len(m['cerradas']), f'{int((~m["cerradas"].tercero).sum())} autocierre(s)'),
    ]) + '</div>'


def bloque_kpis_periodo(i):
    v = lambda k: f'{i[k]}%' if i[k] is not None else 's/d'
    return '<div class="kpi-grid">' + ''.join([
        kpi(f'Eventos {VENTANA_CALIDAD} días', i['ev'], f'{i["fin"]} finalizados · {i["cur"]} en creación'),
        kpi('Acciones sistémicas', v('pS'), f'{i["S"]} de {i["acc"]} acciones', colk(i['pS'], 'pS')),
        kpi('Acciones en plazo', v('pPlazo'), f'{i["tarde"]} cerradas tarde · {i["venc"]} vencidas', colk(i['pPlazo'], 'pPlazo')),
        kpi('Análisis causal adecuado', v('pCausal'), f'{i["causal"]} de {i["conAcc"]} RdP · pauta media {i["mediaCausal"] if i["mediaCausal"] is not None else "s/d"}', colk(i['pCausal'], 'pCausal')),
        kpi('RdP solo reparación', v('pSinS'), f'{i["sinS"]} de {i["conAcc"]} sin acción sistémica', colk(i['pSinS'], 'pSinS')),
        kpi('Cierre por tercero', v('pTercero'), f'{i["tercero"]} de {i["cerr"]} cerradas', colk(i['pTercero'], 'pTercero')),
        kpi('Títulos nulos', v('pNul'), f'{i["nul"]} de {i["ev"]} · {i["cat"]} de catálogo', colk(i['pNul'], 'pNul')),
        kpi('Uso de SAR', f'{i["sar"]} / {i["ev"]}', 'aporte no registrado'),
    ]) + '</div>'


def bloque_foco(com, focos, titulo):
    lectura = f'<div class="card logro" style="margin-bottom:14px">{com["lectura"]}</div>' if com.get('lectura') else ''
    return (f'<div class="section-title">🎯 {titulo}</div>{lectura}<div class="card blk b-az"><ul>'
            + (''.join(f'<li>{x}</li>' for x in focos) or '<li>Sin alertas para hoy.</li>')
            + f'</ul><div class="ideas-fuerza-note">{"Redactado tras revisión" if com.get("focos") else "Generado automáticamente por reglas"}. '
            'Las medidas son propuestas a validar con el NAT.</div></div>')


def bloque_diario(m):
    return (f'<div class="section-title">🆕 RdP nuevas</div>{bloque_nuevos(m)}'
            f'<div class="two-col even"><div><div class="section-title">⏰ Acciones vencidas</div>{tabla_acciones(m["vencidas"], "vencidas")}</div>'
            f'<div><div class="section-title">📅 Vencen en los próximos 7 días</div>{tabla_acciones(m["por_vencer"], "por_vencer")}</div></div>'
            f'<div class="section-title">✔ Acciones cerradas en la ventana</div>{tabla_acciones(m["cerradas"], "cerradas")}')


def vista_planta(m, ctx, com):
    i, evp, acp = m['ind'], m['evp'], m['acp']
    nats = sorted(evp.NAT.unique(), key=lambda n: -len(evp[evp.NAT == n]))
    detalle_nat = ''.join(fila(esc(n), indicadores(evp[evp.NAT == n], acp[acp.NAT == n])) for n in nats)
    grupo = lambda g: indicadores(evp[evp.grupo == g], acp[acp.RegistroId.isin(evp[evp.grupo == g].Id)])
    logro = com.get('logro') or logro_auto(m)
    casos = com.get('casos') or casos_auto(m, ctx)
    return f'''
<div class="mega-title" style="margin-top:22px"><span class="mega-tag">Planta</span> Reporte diario — reunión de líderes NAT</div>
<div class="section-title">📌 Hoy</div>{bloque_hoy(m, ctx)}
{bloque_foco(com, com.get("focos") or focos_auto(m), "Foco para la reunión RdP")}
{f'<div class="section-title">🏆 Logro del período</div><div class="card logro">{logro}<i>Cerrada significa ejecutada, no eficaz: la base no tiene campo de verificación de eficacia, ni descripción del evento, ni registro de qué aportó SAR.</i></div>' if logro else ''}
<div class="section-title">📊 Resumen de calidad — Operaciones vs. Mantención (últimos {VENTANA_CALIDAD} días)</div>
{bloque_kpis_periodo(i)}
<div style="margin-top:14px">{tabla_resumen_planta(m, ctx)}</div>
<div class="ev-meta" style="margin-top:6px">Operaciones = Operativos + Procesos · Mantención = Mecánicos + Electrocontrol. Semáforo: verde = meta del Diagnóstico; ámbar = entre la línea base y la meta; rojo = peor que la línea base.
Análisis causal adecuado = pauta ≥2 (explica el mecanismo o nombra el control). Línea base y resto del negocio calculados con las mismas reglas. Con menos de 20 eventos por fila, no leer diferencias menores a ~15 puntos como reales.</div>
<div class="two-col even"><div class="card card-pad"><h3 class="card-h">Mezcla de acciones</h3>
{barra("Operaciones", grupo("Operaciones"))}{barra("Mantención", grupo("Mantención"))}{barra("Con SAR", m["sar"]["Si"])}{barra("Sin SAR", m["sar"]["No"])}{barra("Total", i)}{LEYENDA_TIPO}</div>
<div class="card card-pad"><h3 class="card-h">Detalle por NAT</h3><div class="scroll"><table>{cabecera("NAT")}{detalle_nat}</table></div></div></div>
<div class="two-col even"><div class="card blk b-ok"><h3>✅ Fortalezas</h3>{ul(com.get("fortalezas") or fortalezas_auto(m))}</div>
<div class="card blk b-red"><h3>❗ Oportunidades de mejora (brechas)</h3>{ul(com.get("brechas") or brechas_auto(m))}</div></div>
<div class="section-title">🔍 Casos críticos en seguimiento</div><div class="card blk b-nar">{ul(casos)}</div>
{bloque_diario(m)}
<div class="section-title">♻ Posibles recurrencias (últimos {VENTANA_CALIDAD} días)</div>{bloque_recurrencias(m["rec"])}
<div class="section-title">🤖 Impacto del SAR</div>{tabla_sar(m["sar"])}'''


def vista_nat(m, ctx, com, med):
    i, n = m['ind'], m['nat']
    lideres = m['evp']['Líder responsable'].value_counts()
    seg = lambda v, c: f'<i style="width:{100 * v / (i["acc"] or 1):.1f}%;background:{c}"></i>'
    areas = ''.join(fila(esc(a), indicadores(m['evp'][m['evp']['Área Responsable'] == a], m['acp'][m['acp']['Área Responsable'] == a]))
                    for a in sorted(m['evp']['Área Responsable'].unique()))
    lbl_base = f'Línea base {esc(n)} ({fmt(ctx["base"][0])} a {fmt(ctx["base"][1])})'
    tabla_area = (f'<div class="card scroll"><table>{cabecera("Área")}{areas}{fila("Total " + esc(n), i, True)}'
                  f'{fila(lbl_base, m["base"], False, "ref")}{fila_meta(ctx["metas"])}</table></div>')
    casos = com.get('casos') or casos_auto(m, ctx)
    if com.get('conclusion') or com.get('medidas'):
        med = dict(conclusion=com.get('conclusion') or (med or {}).get('conclusion', ''),
                   medidas=[dict(zip(('caso', 'control_que_falto', 'medida', 'verificacion'), x)) for x in com['medidas']] if com.get('medidas') else (med or {}).get('medidas', []))
    return f'''
<div class="mega-title" style="margin-top:22px"><span class="mega-tag">Radiografía</span> NAT {esc(n)} — reunión 1 a 1</div>
<div class="section-sub">Líderes responsables ({VENTANA_CALIDAD} días): {" · ".join(f"{esc(k)} ({v})" for k, v in lideres.items()) or "—"}</div>
<div class="section-title">📌 Hoy</div>{bloque_hoy(m, ctx)}
{bloque_foco(com, com.get("focos") or focos_auto(m), "Foco para su reunión")}
<div class="section-title">📊 Estado de cartera (últimos {VENTANA_CALIDAD} días)</div>
{bloque_kpis_periodo(i)}
<div class="two-col even"><div class="card card-pad"><h3 class="card-h">Acciones por estado</h3>
<div class="bar-row"><div class="lbl"><span><b>Plazo</b></span><span class="num">{i["cerrOk"]} en plazo · {i["tarde"]} tarde · {i["abOk"]} abiertas al día · {i["venc"]} vencidas</span></div>
<div class="bar-track stk">{seg(i["cerrOk"], "var(--ok)")}{seg(i["tarde"], "var(--naranja)")}{seg(i["abOk"], "var(--madera)")}{seg(i["venc"], "var(--rojo)")}</div></div>
<div class="legend"><span><i style="background:var(--ok)"></i>Cerrada en plazo</span><span><i style="background:var(--naranja)"></i>Cerrada tarde</span><span><i style="background:var(--madera)"></i>Abierta al día</span><span><i style="background:var(--rojo)"></i>Vencida</span></div>
<div style="margin-top:18px">{barra("Tipo de acción", i)}</div>{LEYENDA_TIPO}</div>
<div class="card blk b-nar"><h3>🔍 Sus casos críticos</h3>{ul(casos)}</div></div>
<div class="two-col even"><div class="card blk b-ok"><h3>✅ Sus fortalezas</h3>{ul(com.get("fortalezas") or fortalezas_auto(m))}</div>
<div class="card blk b-red"><h3>❗ Sus brechas de calidad</h3>{ul(com.get("brechas") or brechas_auto(m))}</div></div>
<div style="margin-top:14px">{tabla_area}</div>
<div class="section-title">🛡 Conclusión y medidas de control propuestas</div>{bloque_medidas(med)}
{bloque_diario(m)}
<div class="section-title">♻ Posibles recurrencias (últimos {VENTANA_CALIDAD} días)</div>{bloque_recurrencias(m["rec"])}
<div class="section-title">📋 Eventos del NAT (últimos {VENTANA_CALIDAD} días y en creación) — clic para el detalle</div>
{tabla_eventos(pd.concat([m["evp"], m["creacion"]]).drop_duplicates("Id"))}
<div class="section-title">📂 Acciones abiertas ({len(m["abiertas"])}) — clic para el detalle</div>{tabla_acciones(m["abiertas"], "abiertas", 80)}'''


# ---------------------------------------------------------------- datos para el detalle (clic)
def datos_detalle(E, A, planta, ambitos):
    Ep, Ap = E[E.Planta == planta], A[A.Planta == planta]
    ante = {}
    for m in ambitos:
        for df in (m['nuevos'], m['rec']):
            for _, e in df.iterrows():
                ante[int(e.Id)] = e.ante
    evs = {}
    for _, e in Ep.iterrows():
        acc = Ap[Ap.RegistroId == e.Id]
        e2 = e.copy()
        e2['ante'] = ante.get(int(e.Id), [])
        evs[int(e.Id)] = dict(
            t=esc(e['Evento tiempo perdido']) and e['Evento tiempo perdido'], nat=e.NAT, area=e['Área Responsable'], lider=e['Líder responsable'],
            f=fmtl(e['Fecha Inicio']), est='Finalizada' if e.Estado == 'Cerrado' else 'En creación', herr=e.Herramienta, sar=e['¿Se utilizó SAR?'],
            dias=int(e.dias_abierta), cadena=bool(e.cadena) if pd.notna(e.p_causa) else None,
            pauta=[[PAUTA_TXT[k][0], int(e[k]), PAUTA_TXT[k][1][int(e[k])]] for k in ('p_tit', 'p_causa', 'p_acc') if pd.notna(e[k])],
            chk=chequeo_evento(e2, acc), ante=[[int(i), fmtl(f), k] for i, f, k in e2['ante']],
            acc=[int(x) for x in acc.sort_values('AccionId').AccionId])
    acs = {}
    for _, r in Ap.iterrows():
        acs[int(r.AccionId)] = dict(
            ev=int(r.RegistroId), causa=r['Causa raíz'] if pd.notna(r['Causa raíz']) else '', cq=CAUSA_TXT[r.causa], cdeb=r.causa in CAUSA_DEBIL,
            a=r['Acción'] if pd.notna(r['Acción']) else '', tipo=r.tipo, tipo_txt=TIPO_TXT[r.tipo], origen=r.tipo_origen,
            resp=r.Responsable, comp=fmtl(r['Fecha Compromiso']), est=r['Estado ejecución'], cump=r['Estado cumplimiento'],
            cierre=fmtl(r['Fecha cierre']) if r.cerr else '—', por=r['Cerrada por'] if r.cerr and pd.notna(r['Cerrada por']) else '—',
            estado='Cerrada' if r.cerr else ('Vencida' if r.venc else 'Abierta al día'), obs=obs_accion(r), exigir=exigir_accion(r))
    return dict(ev=evs, ac=acs)


JS = r'''
const D=JSON.parse(document.getElementById('datos').textContent);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const chip=(c,t)=>`<span class="chip ${c}">${esc(t)}</span>`;
const icon={ok:'✓',amb:'!',red:'✕',gray:'·',az:'i'};
const tcol={S:'ok',C:'amb',R:'az'};
const bg=document.getElementById('modal'),box=document.getElementById('modalBox');
function abrir(h){box.innerHTML='<button class="close-x" style="float:right" onclick="cerrar()" title="Cerrar (Esc)">✕</button>'+h;bg.classList.add('show');box.scrollTop=0;enlazar(box);}
function cerrar(){bg.classList.remove('show');}
bg.addEventListener('click',e=>{if(e.target===bg)cerrar();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')cerrar();});
function verEv(id){const e=D.ev[id];if(!e)return;
 const pz=e.pauta.map(p=>`<div class="pz"><b>${p[0]}</b> ${chip(p[1]>=2?'ok':p[1]==1?'amb':'red',p[1]+' / 3')}<div class="ev-meta">${esc(p[2])}</div></div>`).join('')
  +(e.cadena===null?'':`<div class="pz"><b>Cadena coherente</b> ${e.cadena?chip('ok','Sí'):chip('amb','No')}<div class="ev-meta">título ≥2, causa ≥2, acciones ≥2 y acción sistémica sobre la causa sistémica</div></div>`);
 const filas=e.acc.map(i=>{const a=D.ac[i];return `<tr class="clic" data-ac="${i}" title="Clic para ver la acción"><td>${i}</td><td>${esc(a.causa)}<div class="ev-meta">${esc(a.cq)}</div></td><td>${esc(a.a)}</td><td>${chip(tcol[a.tipo],a.tipo_txt)}</td><td>${esc(a.resp)}</td><td class="num">${a.comp}</td><td>${a.estado==='Vencida'?chip('red','Vencida'):esc(a.estado)}${a.estado==='Cerrada'?'<div class="ev-meta">'+a.cierre+' · '+esc(a.por)+'</div>':''}</td></tr>`}).join('');
 abrir(`<h3><code>${id}</code> ${esc(e.t)||'<i>(sin título)</i>'}</h3>
 <p>${esc(e.nat)} · ${esc(e.area)} · Líder: ${esc(e.lider)}<br>Inicio ${e.f} · ${e.est}${e.est==='En creación'?' hace '+e.dias+' días':''} · Herramienta: ${esc(e.herr)} · SAR: ${esc(e.sar)}</p>
 <h4>Pauta de calidad 0–3 (Diagnóstico)</h4><div class="pauta">${pz}</div>
 <h4>Chequeo de calidad (playbook MGO + diagnóstico)</h4><ul class="chk">${e.chk.map(([c,t])=>`<li>${chip(c,icon[c])} ${esc(t)}</li>`).join('')}</ul>
 ${e.ante.length?`<h4>Antecedentes (posible recurrencia)</h4><p>${e.ante.map(a=>`<code>${a[0]}</code> ${a[1]} · coincidencia: ${esc(a[2])}`).join('<br>')}</p>`:''}
 <h4>Causas y acciones (${e.acc.length}) — clic en una fila para leerla completa</h4>
 ${e.acc.length?`<div class="scroll"><table><tr><th>ID</th><th>Causa raíz</th><th>Acción</th><th>Tipo</th><th>Responsable</th><th>Compromiso</th><th>Estado</th></tr>${filas}</table></div>`:'<p>Sin acciones registradas.</p>'}`);}
function verAc(id){const a=D.ac[id];if(!a)return;const e=D.ev[a.ev]||{};
 abrir(`<h3>Acción ${id} ${chip(tcol[a.tipo],a.tipo_txt)}</h3><p>RdP <code>${a.ev}</code> ${esc(e.t||'')} · ${esc(e.nat||'')} · ${esc(e.area||'')}</p>
 <h4>Causa raíz</h4><div class="txt">${esc(a.causa)||'—'}</div><p>${chip(a.cdeb?'amb':'ok',a.cq)}</p>
 <h4>Acción</h4><div class="txt">${esc(a.a)||'—'}</div>
 <p class="ev-meta">Clasificación ${a.origen==='manual'?'revisada manualmente':'automática por reglas (si no corresponde, corregir en config/clasificacion_acciones.csv)'}.</p>
 <table class="kv"><tr><td>Responsable</td><td>${esc(a.resp)}</td></tr><tr><td>Compromiso</td><td>${a.comp}</td></tr>
 <tr><td>Estado</td><td>${esc(a.estado)} · ejecución: ${esc(a.est)} · cumplimiento: ${esc(a.cump)}</td></tr>
 <tr><td>Cierre</td><td>${a.cierre}</td></tr><tr><td>Cerrada por</td><td>${esc(a.por)}</td></tr></table>
 ${a.obs.length?`<p>${a.obs.map(([c,t])=>chip(c,t)).join(' ')}</p>`:''}
 <div class="card blk b-az" style="margin-top:10px;box-shadow:none"><b>Qué exigir en la reunión RdP:</b> ${esc(a.exigir)}</div>
 <p><a href="#" onclick="verEv('${a.ev}');return false">← Ver la RdP ${a.ev} completa</a></p>`);}
function enlazar(root){
 root.querySelectorAll('code').forEach(c=>{const t=c.textContent.trim();if(D.ev[t]&&!c.dataset.ev){c.dataset.ev=t;c.classList.add('lk');}});
 root.querySelectorAll('[data-ev]').forEach(x=>{if(x._b)return;x._b=1;x.addEventListener('click',ev=>{ev.stopPropagation();verEv(x.dataset.ev);});});
 root.querySelectorAll('[data-ac]').forEach(x=>{if(x._b)return;x._b=1;x.addEventListener('click',()=>verAc(x.dataset.ac));});
 root.querySelectorAll('[data-evrow]').forEach(x=>{if(x._b)return;x._b=1;x.addEventListener('click',()=>verEv(x.dataset.evrow));});}
enlazar(document);
const sel=document.getElementById('natSel');
sel.onchange=()=>{document.querySelectorAll('.vista').forEach(v=>v.classList.toggle('on',v.id===sel.value));
 document.getElementById('vistaTxt').textContent=sel.selectedIndex?'Radiografía de gestión — '+sel.options[sel.selectedIndex].text:'Reporte diario de planta';window.scrollTo(0,0);};
'''

CSS_EXTRA = '''
.lk{cursor:pointer;color:var(--azul);border-color:#C9DAE5}.lk:hover{background:var(--azulBg)}
tr.clic{cursor:pointer}tr.clic:hover td{background:var(--azulBg)}tr.ref td{background:var(--bg2);color:var(--grisC)}tr.meta td{color:var(--ok);background:var(--okBg)}
.chip.gray{background:#F0EFEC;color:var(--grisC)}
.pauta{display:flex;flex-wrap:wrap;gap:10px;margin:6px 0}.pz{border:1px solid var(--linea);border-radius:8px;padding:8px 10px;min-width:170px;flex:1;font-size:12px}
.modal h4{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--gris);margin:16px 0 6px}
.modal .txt{background:var(--bg2);border:1px solid var(--linea);border-radius:8px;padding:10px 12px;font-size:13px;white-space:pre-wrap}
.modal table.kv td:first-child{color:var(--grisC);width:120px}.modal{max-width:920px}
@media print{.modal-bg{display:none!important}}
'''


def render(planta, fecha, desde, vistas_html, nombres, datos, fuente_txt):
    css = Path('ref/estilos_base.css').read_text() + Path('ref/estilos_reporte.css').read_text() + CSS_EXTRA
    opts = ''.join(f'<option value="v{i}">{esc(n)}</option>' for i, n in enumerate(nombres))
    vistas = ''.join(f'<div class="vista{" on" if i == 0 else ""}" id="v{i}">{h}</div>' for i, h in enumerate(vistas_html))
    datos_js = json.dumps(datos, ensure_ascii=False, default=str).replace('</', '<\\/')
    return f'''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RdP diario {esc(planta)} {fecha:%d-%m-%Y}</title><style>{css}</style></head><body>
<header><div class="hd"><div class="hd-left"><div><h1>Calidad de Resolución de Problemas</h1>
<div class="sub">Reporte diario para líderes NAT — efectividad, profundidad y prevención</div><div class="plt">Negocio Celulosa — Planta {esc(planta)}</div></div></div>
<div class="hd-right"><div class="hd-meta">Reporte al <b>{fecha:%d-%m-%Y}</b><br>Novedades: {fmt(desde)} a {fmt(fecha)} · Calidad: últimos {VENTANA_CALIDAD} días<br>{esc(fuente_txt)}</div></div></div></header>
<div class="filterbar"><div class="filterbar-in"><div class="f"><label>NAT</label><select id="natSel">{opts}</select></div>
<div class="f"><label>Vista</label><div id="vistaTxt" style="font-size:12.5px;padding:7px 0">Reporte diario de planta</div></div>
<div class="f"><label>Detalle</label><div style="font-size:12.5px;padding:7px 0">Clic en un ID de RdP o en una fila de acción</div></div>
<button class="btn" onclick="window.print()" style="margin-left:auto">🖨 Imprimir / PDF</button></div></div>
<div class="wrap">{vistas}
<div class="foot-note">Criterios: Playbook MGO (oct-2025) — ciclo RdP de 6 pasos, herramienta y plazo según categoría, soluciones SMART, jerarquía de controles, validar que la solución se sostiene —
y Diagnóstico RDP ago-sep 2026 (pauta 0–3, línea base y metas). Clasificación de acciones y pauta automáticas por reglas, salvo las revisadas en config/.
La base no registra descripción, categoría, horas perdidas ni eficacia: lo que falta en el registro no prueba que no se hizo.</div></div>
<div class="modal-bg" id="modal"><div class="card modal" id="modalBox"></div></div>
<script type="application/json" id="datos">{datos_js}</script>
<script>{JS}</script></body></html>'''


def main(argv=None):
    p = argparse.ArgumentParser(description='Reporte diario de calidad RdP por NAT')
    p.add_argument('--planta', default='Nueva Aldea')
    p.add_argument('--fecha', default=None, help='AAAA-MM-DD; por defecto, hoy')
    p.add_argument('--dias', type=int, default=None, help='Días de novedades; por defecto 1 (lunes: 3)')
    p.add_argument('--excel', default=None, help='Ruta al Excel; por defecto el más reciente en data/')
    p.add_argument('--comentarios', default=None, help='JSON con textos redactados por ámbito ("Planta" o nombre de NAT)')
    p.add_argument('--json', action='store_true', help='Además, guardar out/…json con los datos para redactar comentarios')
    p.add_argument('--salida', default='out')
    a = p.parse_args(argv)

    ruta = Path(a.excel) if a.excel else fuente.ultimo_excel()
    reg, acc = fuente.normalizar(*fuente.cargar_excel(ruta))
    E, A, fecha = preparar(reg, acc, pd.Timestamp(a.fecha or pd.Timestamp.today().date()))
    if not (E.Planta == a.planta).any():
        raise SystemExit(f'No hay registros para la planta "{a.planta}". Plantas: {sorted(reg.Planta.unique())}')
    desde = ventana_novedades(fecha, a.dias)
    d_cal = fecha - pd.Timedelta(days=VENTANA_CALIDAD - 1)
    lb = leer_json('linea_base.json', {}).get(a.planta, {})
    base = ((pd.Timestamp(lb['periodo']['desde']), pd.Timestamp(lb['periodo']['hasta'])) if lb
            else (d_cal - pd.Timedelta(days=60), d_cal - pd.Timedelta(days=1)))
    metas = lb.get('metas', {})
    casos = [c for c in leer_json('casos_seguimiento.json', []) if c.get('planta') == a.planta]
    medidas = {k: v for k, v in leer_json('medidas_control.json', {}).items() if v.get('planta') == a.planta}
    comentarios = json.loads(Path(a.comentarios).read_text(encoding='utf-8')) if a.comentarios else {}

    Ep = E[E.Planta == a.planta]
    nats = sorted(Ep.NAT.unique(), key=lambda n: -len(Ep[Ep.NAT == n]))
    ambitos = [calcular_ambito(E, A, a.planta, desde, d_cal, base)] + [calcular_ambito(E, A, a.planta, desde, d_cal, base, n) for n in nats]
    # Semáforo: verde = meta; ámbar hasta la línea base de la planta; rojo = peor que la línea base
    for k, v in metas.items():
        if k in UMBRALES:
            UMBRALES[k][0] = v['valor']
            b = ambitos[0]['base'].get(k)
            if b is not None:
                UMBRALES[k][1] = max(b, v['valor']) if UMBRALES[k][2] else min(b, v['valor'])
    ctx = dict(E=E, A=A, planta=a.planta, fecha=fecha, desde=desde, d_cal=d_cal, base=base, metas=metas, casos=casos)
    vistas = [vista_planta(ambitos[0], ctx, comentarios.get('Planta', {}))] + \
             [vista_nat(m, ctx, comentarios.get(m['nat'], {}), medidas.get(m['nat'])) for m in ambitos[1:]]

    out = Path(a.salida)
    out.mkdir(exist_ok=True)
    slug = a.planta.replace(' ', '_')
    f = out / f'RdP_diario_{slug}_{fecha:%Y-%m-%d}.html'
    f.write_text(render(a.planta, fecha, desde, vistas, ['Planta completa'] + nats, datos_detalle(E, A, a.planta, ambitos),
                        f'Fuente: {ruta.name}'), encoding='utf-8')
    print(f)
    if a.json:
        resumen = {}
        for m in ambitos:
            resumen[m['nat'] or 'Planta'] = dict(
                indicadores_periodo=m['ind'], linea_base=m['base'], resto_negocio=m.get('resto'),
                nuevos=[dict(Id=int(e.Id), titulo=e['Evento tiempo perdido'], area=e['Área Responsable'], herramienta=e.Herramienta, sar=e['¿Se utilizó SAR?'],
                             pauta=dict(identificacion=int(e.p_tit), causal=None if pd.isna(e.p_causa) else int(e.p_causa), acciones=int(e.p_acc)),
                             chequeo=chequeo_evento(e, m['ac'][m['ac'].RegistroId == e.Id]), antecedentes=[i for i, _, _ in e.ante],
                             acciones=[dict(AccionId=int(r.AccionId), causa=r['Causa raíz'], causa_calidad=r.causa, accion=r['Acción'], tipo=r.tipo,
                                            tipo_origen=r.tipo_origen) for _, r in m['ac'][m['ac'].RegistroId == e.Id].iterrows()])
                        for _, e in m['nuevos'].iterrows()],
                vencidas=[dict(RegistroId=int(r.RegistroId), AccionId=int(r.AccionId), accion=r['Acción'], dias_atraso=int(r.dias_atraso)) for _, r in m['vencidas'].iterrows()],
                en_creacion=[dict(Id=int(e.Id), dias=int(e.dias_abierta)) for _, e in m['creacion'].iterrows()],
                recurrencias=[dict(Id=int(e.Id), titulo=e['Evento tiempo perdido'], antecedentes=[i for i, _, _ in e.ante]) for _, e in m['rec'].iterrows()],
                textos_automaticos=dict(logro=logro_auto(m) if m['nat'] is None else None, fortalezas=fortalezas_auto(m), brechas=brechas_auto(m),
                                        focos=focos_auto(m), casos=casos_auto(m, ctx)))
        j = out / f'RdP_diario_{slug}_{fecha:%Y-%m-%d}.json'
        j.write_text(json.dumps(resumen, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        print(j)


if __name__ == '__main__':
    main()
