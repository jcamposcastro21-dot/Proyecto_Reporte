"""Reporte diario de calidad RdP por NAT.

Uso:
    python3 -m reporte.diario --planta "Nueva Aldea" --fecha 2026-10-02
    python3 -m reporte.diario --planta "Nueva Aldea" --fecha 2026-10-02 --comentarios comentarios/2026-10-02_Nueva_Aldea.json

Todos los cálculos son "a la fecha": una acción cuenta como cerrada solo si su
Fecha cierre es ≤ fecha del reporte, y solo se consideran eventos con Fecha Inicio ≤ fecha.
"""
import argparse
import html
import json
from pathlib import Path
import pandas as pd

from . import fuente
from .calidad import (calidad_titulo, calidad_causa, clasificar_accion, cargar_clasificacion_manual,
                      claves, antecedentes, norm, CAUSA_TXT, CAUSA_DEBIL, TIPO_TXT)

# Semáforos (verde, ámbar); inv=True cuando menor es mejor
UMBRALES = {
    'pS': (40, 25, False),        # % acciones sistémicas
    'pPlazo': (80, 65, False),    # % acciones en plazo
    'pTercero': (50, 20, False),  # % cierres por alguien distinto al responsable
    'pNul': (10, 25, True),       # % títulos nulos
    'pDebil': (20, 40, True),     # % eventos con todas sus causas débiles
    'pSinS': (30, 50, True),      # % eventos sin ninguna acción sistémica
}
DIAS_CREACION_MAX = 7   # Playbook: RdP cat. 1-2 se revisa 1 vez por semana; cat. 3 se emite en 5 días
VENTANA_CALIDAD = 30
GRUPO = {'Operativos': 'Operaciones', 'Procesos': 'Operaciones', 'Mecánicos': 'Mantención', 'Electrocontrol': 'Mantención'}
ANALISIS_ESTRUCTURADO = ('5 porque', 'ishikawa', 'árbol')


def esc(s):
    return html.escape(str(s)) if pd.notna(s) else ''


def fmt(d):
    return d.strftime('%d-%m') if pd.notna(d) else '—'


# ---------------------------------------------------------------- cálculo
def preparar(reg, acc, planta, fecha):
    fecha = pd.Timestamp(fecha).normalize()
    reg = reg[reg['Fecha Inicio'] <= fecha].copy()
    hist = reg[reg.Planta == planta].copy()
    causas = acc.groupby('RegistroId')['Causa raíz'].apply(lambda s: ' '.join(s.dropna().map(str)))
    kt = [claves(t) for t in hist['Evento tiempo perdido']]
    kc = [claves(causas.get(i, '')) for i in hist.Id]
    hist['_tags'] = [t[0] | c[0] for t, c in zip(kt, kc)]
    hist['_pal'] = [t[1] | c[1] for t, c in zip(kt, kc)]
    hist['tit'] = hist['Evento tiempo perdido'].map(calidad_titulo)
    hist['grupo'] = hist['Área Responsable'].map(GRUPO).fillna('Otros')

    a = acc.merge(hist[['Id', 'NAT', 'Área Responsable', 'grupo', 'Fecha Inicio']], left_on='RegistroId', right_on='Id')
    manual = cargar_clasificacion_manual()
    a['tipo'] = [manual.get(int(i), clasificar_accion(t)) for i, t in zip(a.AccionId, a['Acción'])]
    a['tipo_origen'] = ['manual' if int(i) in manual else 'auto' for i in a.AccionId]
    a['causa'] = a['Causa raíz'].map(calidad_causa)
    a['cerr'] = a['Fecha cierre'].notna() & (a['Fecha cierre'] <= fecha)
    a['tercero'] = a.cerr & (a.Responsable.map(norm) != a['Cerrada por'].map(norm))
    a['tarde'] = a.cerr & (a['Fecha cierre'] > a['Fecha Compromiso'])
    a['venc'] = ~a.cerr & (a['Fecha Compromiso'] < fecha)
    a['enplazo'] = (a.cerr & ~a.tarde) | (~a.cerr & ~a.venc)
    a['dias_atraso'] = (fecha - a['Fecha Compromiso']).dt.days.where(a.venc)
    a['dias_para'] = (a['Fecha Compromiso'] - fecha).dt.days.where(~a.cerr)

    # resumen por evento
    g = a.groupby('RegistroId')
    hist['nAcc'] = hist.Id.map(g.size()).fillna(0).astype(int)
    for t in 'SCR':
        hist['n' + t] = hist.Id.map(g.tipo.apply(lambda s, t=t: int((s == t).sum()))).fillna(0).astype(int)
    hist['causas_debiles'] = hist.Id.map(g.causa.apply(lambda s: bool(len(s)) and s.isin(CAUSA_DEBIL).all())).fillna(True).astype(bool)
    hist['causa_control'] = hist.Id.map(g.causa.apply(lambda s: (s == 'control').any())).fillna(False).astype(bool)
    hist['dias_abierta'] = (fecha - hist['Fecha Inicio']).dt.days
    return hist, a, fecha


def indicadores(ev, ac):
    c = ac[ac.cerr]
    fin = ev[ev.nAcc > 0]
    pct = lambda x, n: round(100 * x / n) if n else None
    return dict(
        ev=len(ev), acc=len(ac), S=int((ac.tipo == 'S').sum()), pS=pct((ac.tipo == 'S').sum(), len(ac)),
        plazo=int(ac.enplazo.sum()), pPlazo=pct(ac.enplazo.sum(), len(ac)),
        cerr=len(c), tercero=int(c.tercero.sum()), pTercero=pct(c.tercero.sum(), len(c)),
        nul=int((ev.tit == 'nulo').sum()), pNul=pct((ev.tit == 'nulo').sum(), len(ev)),
        debil=int(fin.causas_debiles.sum()), pDebil=pct(fin.causas_debiles.sum(), len(fin)),
        sinS=int((fin.nS == 0).sum()), pSinS=pct((fin.nS == 0).sum(), len(fin)), conAcc=len(fin),
        sar=int((ev['¿Se utilizó SAR?'] == 'Si').sum()))


def ventana_novedades(fecha, dias):
    """Novedades = Fecha Inicio (o cierre) entre `desde` y la fecha del reporte, ambos incluidos.
    Por defecto: ayer y hoy; los lunes, desde el viernes."""
    if dias is None:
        dias = 3 if fecha.weekday() == 0 else 1
    return fecha - pd.Timedelta(days=dias), fecha


def calcular_ambito(hist, a, fecha, desde, nat=None):
    ev = hist if nat is None else hist[hist.NAT == nat]
    ac = a if nat is None else a[a.NAT == nat]
    d30 = fecha - pd.Timedelta(days=VENTANA_CALIDAD)
    ev30, ac30 = ev[ev['Fecha Inicio'] > d30], ac[ac['Fecha Inicio'] > d30]

    nuevos = ev[(ev['Fecha Inicio'] >= desde) & (ev['Fecha Inicio'] <= fecha)].copy()
    nuevos['ante'] = [antecedentes(r, hist) for _, r in nuevos.iterrows()]
    rec30 = ev30.copy()
    rec30['ante'] = [antecedentes(r, hist) for _, r in rec30.iterrows()]
    rec30 = rec30[rec30.ante.map(len) > 0]

    creacion = ev[(ev.Estado == 'En creación')].sort_values('dias_abierta', ascending=False)
    abiertas = ac[~ac.cerr]
    vencidas = abiertas[abiertas.venc].sort_values('dias_atraso', ascending=False)
    por_vencer = abiertas[(~abiertas.venc) & (abiertas.dias_para <= 7)].sort_values('dias_para')
    cerradas = ac[ac.cerr & (ac['Fecha cierre'] >= desde) & (ac['Fecha cierre'] <= fecha)]

    filas = []
    if nat is None:
        for n in sorted(hist.NAT.unique(), key=lambda n: -len(ev30[ev30.NAT == n])):
            filas.append((n, indicadores(ev30[ev30.NAT == n], ac30[ac30.NAT == n])))
    else:
        for ar in sorted(ev30['Área Responsable'].unique()):
            filas.append((ar, indicadores(ev30[ev30['Área Responsable'] == ar], ac30[ac30['Área Responsable'] == ar])))
    filas.append(('Total' + ('' if nat is None else f' {nat}'), indicadores(ev30, ac30)))

    return dict(nat=nat, nuevos=nuevos, rec30=rec30, creacion=creacion, abiertas=abiertas, vencidas=vencidas,
                por_vencer=por_vencer, cerradas=cerradas, filas=filas, ind30=indicadores(ev30, ac30), ac=ac)


def chequeo_evento(e, acciones):
    """Lista de (ok|amb|red, texto) con los criterios del playbook MGO para una RdP nueva."""
    out = []
    t = e.tit
    out.append(('red' if t == 'nulo' else 'amb' if t == 'catalogo' else 'ok',
                {'nulo': 'Título nulo: no identifica el desvío', 'catalogo': 'Título de catálogo: falta equipo/tag',
                 'especifico': 'Título identifica el desvío'}[t]))
    herr = norm(e.Herramienta)
    estructurada = any(h in herr for h in ANALISIS_ESTRUCTURADO)
    if e.ante:
        out.append(('ok' if estructurada else 'red',
                    'Posible recurrencia: ' + ('análisis estructurado aplicado' if estructurada else 'exige 5 porqués / Ishikawa / árbol de falla (playbook)')))
    if e.nAcc == 0:
        out.append(('amb', 'Sin acciones registradas aún'))
    else:
        cc = acciones.causa.value_counts()
        if e.causa_control:
            out.append(('ok', 'Causa nombra el control que faltó o falló'))
        elif e.causas_debiles:
            peor = next(k for k in ('vacia', 'tarea', 'hipotesis', 'estado') if k in cc)
            out.append(('red', f'Causa débil: {CAUSA_TXT[peor]}'))
        else:
            out.append(('amb', 'Causa explica el mecanismo, pero no el control que faltó'))
        out.append(('ok' if e.nS > 0 else 'red',
                    f'{e.nS} sistémica(s) · {e.nC} correctiva(s) · {e.nR} revisión' + ('' if e.nS else ' → sin barrera que evite la repetición')))
    out.append(('ok' if e['¿Se utilizó SAR?'] == 'Si' else 'amb', 'SAR utilizado' if e['¿Se utilizó SAR?'] == 'Si' else 'SAR no utilizado'))
    return out


def focos_automaticos(m):
    """Hasta 4 puntos para la reunión RdP, priorizados por riesgo de recurrencia."""
    f = []
    rec = m['nuevos'][m['nuevos'].ante.map(len) > 0]
    for _, e in rec.head(2).iterrows():
        ids = ', '.join(f'<code>{i}</code>' for i, _, _ in e.ante[:3])
        f.append(f'<b>Posible recurrencia en <code>{e.Id}</code></b> ({esc(e["Evento tiempo perdido"])}): antecedentes {ids}. '
                 'Revisar si las acciones previas se cerraron sin verificar eficacia y abordar como un solo análisis.')
    sinS = m['nuevos'][(m['nuevos'].nAcc > 0) & (m['nuevos'].nS == 0)]
    if len(sinS):
        f.append(f'<b>{len(sinS)} RdP nueva(s) sin acción sistémica</b> ({", ".join(f"<code>{i}</code>" for i in sinS.Id)}): '
                 'pedir al menos una acción que cambie plan, estándar, diseño o lógica, o justificar por qué no aplica.')
    v = m['vencidas']
    if len(v):
        f.append(f'<b>{len(v)} acción(es) vencida(s)</b>, la más antigua con {int(v.dias_atraso.max())} días '
                 f'(<code>{int(v.iloc[0].RegistroId)}</code>/{int(v.iloc[0].AccionId)}): reprogramar con fecha y responsable confirmados.')
    cr = m['creacion'][m['creacion'].dias_abierta > DIAS_CREACION_MAX]
    if len(cr):
        f.append(f'<b>{len(cr)} RdP en creación hace más de {DIAS_CREACION_MAX} días</b> '
                 f'({", ".join(f"<code>{i}</code>" for i in cr.Id[:5])}): cerrar el análisis en la próxima reunión RdP.')
    nul = m['nuevos'][m['nuevos'].tit == 'nulo']
    if len(nul):
        f.append(f'<b>Título nulo en {", ".join(f"<code>{i}</code>" for i in nul.Id)}</b>: completar equipo/tag y fenómeno antes de analizar.')
    return f[:4]


# ---------------------------------------------------------------- HTML
def pill(v, k):
    if v is None:
        return '<span class="pill gray">s/d</span>'
    g, w, inv = UMBRALES[k]
    ok = v <= g if inv else v >= g
    mid = v <= w if inv else v >= w
    return f'<span class="pill {"ok" if ok else "amb" if mid else "red"}">{v}%</span>'


def tabla_calidad(filas, nombre_col):
    h = (f'<tr><th>{nombre_col}</th><th>Eventos</th><th>Acciones</th><th>% Sistémicas</th><th>% En plazo</th>'
         '<th>% Cierre por tercero</th><th>% Títulos nulos</th><th>% Causa débil</th><th>% Sin acción sistémica</th><th>SAR</th></tr>')
    b = ''
    for n, s in filas:
        tag = 'b' if n.startswith('Total') else 'span'
        b += (f'<tr><td><{tag}>{esc(n)}</{tag}></td><td class="num">{s["ev"]}</td><td class="num">{s["acc"]}</td>'
              f'<td class="num">{pill(s["pS"], "pS")} <small>{s["S"]}/{s["acc"]}</small></td>'
              f'<td class="num">{pill(s["pPlazo"], "pPlazo")} <small>{s["plazo"]}/{s["acc"]}</small></td>'
              f'<td class="num">{pill(s["pTercero"], "pTercero")} <small>{s["tercero"]}/{s["cerr"]}</small></td>'
              f'<td class="num">{pill(s["pNul"], "pNul")} <small>{s["nul"]}/{s["ev"]}</small></td>'
              f'<td class="num">{pill(s["pDebil"], "pDebil")} <small>{s["debil"]}/{s["conAcc"]}</small></td>'
              f'<td class="num">{pill(s["pSinS"], "pSinS")} <small>{s["sinS"]}/{s["conAcc"]}</small></td>'
              f'<td class="num"><small>{s["sar"]}/{s["ev"]}</small></td></tr>')
    return f'<div class="card scroll"><table>{h}{b}</table></div>'


def kpi(label, valor, sub, color=''):
    return (f'<div class="card kpi"><div class="kpi-label">{label}</div><div class="kpi-value num {color}">{valor}</div>'
            f'<div class="kpi-sub">{sub}</div></div>')


def bloque_eventos(m):
    if not len(m['nuevos']):
        return '<div class="card vacio">Sin RdP nuevas en la ventana.</div>'
    filas = ''
    for _, e in m['nuevos'].sort_values('Fecha Inicio').iterrows():
        acc = m['ac'][m['ac'].RegistroId == e.Id]
        chk = ''.join(f'<li><span class="chip {c}">{"✓" if c == "ok" else "!" if c == "amb" else "✕"}</span> {esc(t)}</li>'
                      for c, t in chequeo_evento(e, acc))
        causas = '<br>'.join(f'<span class="chip {dict(S="ok", C="amb", R="az")[r.tipo]}" title="{TIPO_TXT[r.tipo]}">{r.tipo}</span> {esc(str(r["Causa raíz"])[:90])} → {esc(str(r["Acción"])[:90])}'
                             for _, r in acc.iterrows()) or '<span class="ev-meta">—</span>'
        ante = ', '.join(f'<code>{i}</code> <small>{fmt(f)} · {esc(k)}</small>' for i, f, k in e.ante[:3]) or '—'
        filas += (f'<tr><td><code>{e.Id}</code><div class="ev-meta">{fmt(e["Fecha Inicio"])} · {esc(e.Estado)}</div></td>'
                  f'<td><div class="ev-tit">{esc(e["Evento tiempo perdido"])}</div><div class="ev-meta">{esc(e.NAT)} · {esc(e["Área Responsable"])} · '
                  f'{esc(e["Líder responsable"])} · {esc(e.Herramienta)}</div><div style="margin-top:6px;font-size:11.5px">{causas}</div></td>'
                  f'<td><ul class="chk">{chk}</ul></td><td>{ante}</td></tr>')
    return ('<div class="card scroll"><table><tr><th>ID</th><th>Evento · causa → acción</th><th>Chequeo de calidad (playbook MGO)</th>'
            f'<th>Antecedentes 12 meses</th></tr>{filas}</table></div>')


def tabla_acciones(df, modo):
    if not len(df):
        return '<div class="card vacio">Sin acciones en esta categoría.</div>'
    if modo == 'cerradas':
        h = '<tr><th>Evento</th><th>Acción</th><th>Tipo</th><th>Responsable</th><th>Cerrada por</th><th>Compromiso</th><th>Cierre</th><th>Observación</th></tr>'
    else:
        h = '<tr><th>Evento</th><th>Acción</th><th>Tipo</th><th>Responsable</th><th>Compromiso</th><th>' + ('Días atraso' if modo == 'vencidas' else 'Vence en') + '</th></tr>'
    b = ''
    for _, r in df.head(25).iterrows():
        base = (f'<tr><td><code>{int(r.RegistroId)}</code><div class="ev-meta">{esc(r.NAT)}</div></td><td>{esc(str(r["Acción"])[:120])}</td>'
                f'<td><small>{TIPO_TXT[r.tipo]}</small></td><td>{esc(r.Responsable)}</td>')
        if modo == 'cerradas':
            obs = []
            if not r.tercero:
                obs.append('<span class="chip amb">autocierre</span>')
            if r.tarde:
                obs.append(f'<span class="chip red">tarde {int((r["Fecha cierre"] - r["Fecha Compromiso"]).days)} d</span>')
            if r.tipo == 'R':
                obs.append('<span class="chip az">registrar resultado</span>')
            b += base + f'<td>{esc(r["Cerrada por"])}</td><td class="num">{fmt(r["Fecha Compromiso"])}</td><td class="num">{fmt(r["Fecha cierre"])}</td><td>{" ".join(obs) or "—"}</td></tr>'
        elif modo == 'vencidas':
            b += base + f'<td class="num">{fmt(r["Fecha Compromiso"])}</td><td class="num"><span class="pill red">{int(r.dias_atraso)}</span></td></tr>'
        else:
            b += base + f'<td class="num">{fmt(r["Fecha Compromiso"])}</td><td class="num">{int(r.dias_para)} d</td></tr>'
    extra = f'<div class="ev-meta" style="padding:8px 10px">… y {len(df) - 25} más</div>' if len(df) > 25 else ''
    return f'<div class="card scroll"><table>{h}{b}</table>{extra}</div>'


def bloque_recurrencias(rec):
    if not len(rec):
        return '<div class="card vacio">Sin coincidencias con eventos previos en los últimos 30 días.</div>'
    b = ''.join(f'<tr><td><code>{e.Id}</code><div class="ev-meta">{fmt(e["Fecha Inicio"])} · {esc(e.NAT)}</div></td><td>{esc(e["Evento tiempo perdido"])}</td>'
                f'<td>{", ".join(f"<code>{i}</code> <small>{fmt(f)} · {esc(k)}</small>" for i, f, k in e.ante[:4])}</td></tr>'
                for _, e in rec.sort_values('Fecha Inicio', ascending=False).iterrows())
    return ('<div class="card scroll"><table><tr><th>Evento</th><th>Título</th><th>Antecedentes (coincidencia)</th></tr>'
            f'{b}</table></div><div class="ev-meta" style="margin-top:6px">Coincidencia por tag o palabras clave en título y causas, misma NAT, 12 meses. Es una alerta: validar con el NAT.</div>')


def vista(m, fecha, desde, comentario):
    ind = m['ind30']
    v, pv = m['vencidas'], m['por_vencer']
    cr_lenta = (m['creacion'].dias_abierta > DIAS_CREACION_MAX).sum()
    k = ''.join([
        kpi('RdP nuevas', len(m['nuevos']), f'{fmt(desde)} a {fmt(fecha)}'),
        kpi('RdP en creación', len(m['creacion']), f'{cr_lenta} con más de {DIAS_CREACION_MAX} días', 'red' if cr_lenta else ''),
        kpi('Acciones vencidas', len(v), f'de {len(m["abiertas"])} abiertas', 'red' if len(v) else ''),
        kpi('Vencen en 7 días', len(pv), 'para revisar en la reunión', 'amb' if len(pv) else ''),
        kpi('Cerradas en la ventana', len(m['cerradas']), f'{int((~m["cerradas"].tercero).sum())} autocierre(s)'),
        kpi(f'Sistémicas {VENTANA_CALIDAD} d', f'{ind["pS"] if ind["pS"] is not None else "s/d"}%', f'{ind["S"]} de {ind["acc"]} acciones',
            '' if ind['pS'] is None or ind['pS'] >= 40 else 'red' if ind['pS'] < 25 else 'amb'),
    ])
    focos = (comentario.get('focos') if comentario else None) or focos_automaticos(m)
    focos_html = ''.join(f'<li>{f}</li>' for f in focos) or '<li>Sin alertas para hoy.</li>'
    lectura = (f'<div class="card logro" style="margin-bottom:14px">{comentario["lectura"]}</div>'
               if comentario and comentario.get('lectura') else '')
    origen = 'redactado tras revisión' if comentario and comentario.get('focos') else 'generado automáticamente por reglas'
    nombre_col = 'NAT' if m['nat'] is None else 'Área'
    return f'''
<div class="section-title">📌 Estado de cartera a la fecha</div><div class="kpi-grid">{k}</div>
<div class="section-title">🎯 Foco para la reunión RdP</div>{lectura}
<div class="card blk b-nar"><ul>{focos_html}</ul><div class="ideas-fuerza-note">Foco {origen}. Las medidas son propuestas a validar con el NAT.</div></div>
<div class="section-title">🆕 RdP nuevas</div>{bloque_eventos(m)}
<div class="two-col even"><div><div class="section-title">⏰ Acciones vencidas</div>{tabla_acciones(v, 'vencidas')}</div>
<div><div class="section-title">📅 Vencen en los próximos 7 días</div>{tabla_acciones(pv, 'por_vencer')}</div></div>
<div class="section-title">✔ Acciones cerradas en la ventana</div>{tabla_acciones(m['cerradas'], 'cerradas')}
<div class="section-title">♻ Posibles recurrencias (eventos de los últimos {VENTANA_CALIDAD} días)</div>{bloque_recurrencias(m['rec30'])}
<div class="section-title">📊 Calidad RdP — últimos {VENTANA_CALIDAD} días por {nombre_col}</div>{tabla_calidad(m['filas'], nombre_col)}
<div class="ev-meta" style="margin-top:6px">Con menos de 20 eventos por fila, no leer diferencias menores a ~15 puntos como reales.</div>'''


def render(planta, fecha, desde, ambitos, comentarios, fuente_txt):
    css = Path('ref/estilos_base.css').read_text() + Path('ref/estilos_reporte.css').read_text()
    opts = ''.join(f'<option value="v{i}">{esc(m["nat"] or "Planta completa")}</option>' for i, m in enumerate(ambitos))
    vistas = ''.join(f'<div class="vista{" on" if i == 0 else ""}" id="v{i}">{vista(m, fecha, desde, comentarios.get(m["nat"] or "Planta"))}</div>'
                     for i, m in enumerate(ambitos))
    return f'''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RdP diario {esc(planta)} {fecha:%d-%m-%Y}</title><style>{css}</style></head><body>
<header><div class="hd"><div class="hd-left"><div><h1>Calidad de Resolución de Problemas</h1>
<div class="sub">Reporte diario por NAT — ¿nuestras RdP evitan que el problema se repita?</div><div class="plt">Negocio Celulosa — Planta {esc(planta)}</div></div></div>
<div class="hd-right"><div class="hd-meta">Reporte al <b>{fecha:%d-%m-%Y}</b><br>Novedades: {fmt(desde)} a {fmt(fecha)}<br>{esc(fuente_txt)}</div></div></div></header>
<div class="filterbar"><div class="filterbar-in"><div class="f"><label>NAT</label><select id="natSel">{opts}</select></div>
<button class="btn" onclick="window.print()" style="margin-left:auto">🖨 Imprimir / PDF</button></div></div>
<div class="wrap">{vistas}
<div class="foot-note">Criterios: Playbook MGO (oct-2025) — ciclo RdP, análisis según categoría, soluciones SMART, barreras duras sobre administrativas, validación de solución sostenida.
Clasificación de acciones automática salvo las revisadas en config/clasificacion_acciones.csv. La base no registra descripción, categoría ni eficacia: lo que falta en el registro no prueba que no se hizo.</div></div>
<script>document.getElementById('natSel').onchange=e=>{{document.querySelectorAll('.vista').forEach(v=>v.classList.toggle('on',v.id===e.target.value));}};</script>
</body></html>'''


def main(argv=None):
    p = argparse.ArgumentParser(description='Reporte diario de calidad RdP por NAT')
    p.add_argument('--planta', default='Nueva Aldea')
    p.add_argument('--fecha', default=None, help='AAAA-MM-DD; por defecto, hoy')
    p.add_argument('--dias', type=int, default=None, help='Días de novedades; por defecto 1 (lunes: 3)')
    p.add_argument('--excel', default=None, help='Ruta al Excel; por defecto el más reciente en data/')
    p.add_argument('--comentarios', default=None, help='JSON con focos/lectura redactados por NAT')
    p.add_argument('--json', action='store_true', help='Además, guardar out/…json con los datos para redactar comentarios')
    p.add_argument('--salida', default='out')
    a = p.parse_args(argv)

    ruta = Path(a.excel) if a.excel else fuente.ultimo_excel()
    reg, acc = fuente.normalizar(*fuente.cargar_excel(ruta))
    fecha = pd.Timestamp(a.fecha or pd.Timestamp.today().date())
    hist, ac, fecha = preparar(reg, acc, a.planta, fecha)
    if not len(hist):
        raise SystemExit(f'No hay registros para la planta "{a.planta}". Plantas: {sorted(reg.Planta.unique())}')
    desde, _ = ventana_novedades(fecha, a.dias)
    nats = sorted(hist.NAT.unique(), key=lambda n: -len(hist[hist.NAT == n]))
    ambitos = [calcular_ambito(hist, ac, fecha, desde)] + [calcular_ambito(hist, ac, fecha, desde, n) for n in nats]
    comentarios = json.loads(Path(a.comentarios).read_text()) if a.comentarios else {}

    out = Path(a.salida)
    out.mkdir(exist_ok=True)
    slug = a.planta.replace(' ', '_')
    f = out / f'RdP_diario_{slug}_{fecha:%Y-%m-%d}.html'
    f.write_text(render(a.planta, fecha, desde, ambitos, comentarios, f'Fuente: {ruta.name}'), encoding='utf-8')
    print(f)
    if a.json:
        resumen = {}
        for m in ambitos:
            resumen[m['nat'] or 'Planta'] = dict(
                indicadores_30d=m['ind30'],
                nuevos=[dict(Id=int(e.Id), titulo=e['Evento tiempo perdido'], area=e['Área Responsable'], herramienta=e.Herramienta,
                             sar=e['¿Se utilizó SAR?'], antecedentes=[i for i, _, _ in e.ante],
                             acciones=[dict(AccionId=int(r.AccionId), causa=r['Causa raíz'], causa_calidad=r.causa, accion=r['Acción'], tipo=r.tipo,
                                            tipo_origen=r.tipo_origen) for _, r in ac[ac.RegistroId == e.Id].iterrows()])
                        for _, e in m['nuevos'].iterrows()],
                vencidas=[dict(RegistroId=int(r.RegistroId), AccionId=int(r.AccionId), accion=r['Acción'], dias_atraso=int(r.dias_atraso)) for _, r in m['vencidas'].iterrows()],
                en_creacion=[dict(Id=int(e.Id), dias=int(e.dias_abierta)) for _, e in m['creacion'].iterrows()],
                recurrencias_30d=[dict(Id=int(e.Id), titulo=e['Evento tiempo perdido'], antecedentes=[i for i, _, _ in e.ante]) for _, e in m['rec30'].iterrows()],
                focos_automaticos=focos_automaticos(m))
        j = out / f'RdP_diario_{slug}_{fecha:%Y-%m-%d}.json'
        j.write_text(json.dumps(resumen, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        print(j)


if __name__ == '__main__':
    main()
