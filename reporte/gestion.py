"""Informe de calidad RdP para conversar con cada NAT (versión de gestión).

Es el mismo reporte diario (`reporte.diario`), con el mismo formato y los mismos cálculos,
más una lógica de gestión orientada a la conversación 1 a 1:

- Tres niveles de calidad: 1 levantamiento, 2 resolución, 3 aprendizaje.
- Cada porcentaje va con su "x de n"; con pocos casos no se pinta semáforo ni se lee tendencia.
- Lectura en el tiempo de cada aspecto (últimos 30 días vs. los 90 anteriores): debilidad
  persistente, situación puntual, mejora, deterioro, fortaleza sostenida o trabajada (con acuerdo).
- Ejecución ≠ eficacia: una acción cerrada es una acción ejecutada; la eficacia solo se lee como
  indicio cuando no hubo eventos relacionados en los 60 días siguientes al cierre.
- Cadenas de recurrencia: qué ocurrió entre una RdP y la siguiente.
- Casos de referencia (buenas prácticas) detectados en los datos: qué hizo → por qué → dónde replicar.
- Guía de conversación por NAT y seguimiento de acuerdos (config/acuerdos_nat.json).

Uso:
    python3 -m reporte.gestion --planta "Nueva Aldea" --fecha 2026-10-02 --json
"""
import argparse
import json
from pathlib import Path
import pandas as pd

from . import fuente
from . import diario as d
from . import aprendizaje as ap
from .diario import (esc, fmt, fmtl, ev, ul, pill, indicadores, pauta_chips, barra, LEYENDA_TIPO, UMBRALES, VENTANA_CALIDAD,
                     SUBAREAS, COLS, cabecera, fila_meta, bloque_hoy, bloque_medidas, tabla_sar, chequeo_evento, obs_accion,
                     focos_auto, logro_auto, fortalezas_auto, brechas_auto, tabla_acciones, bloque_kpis_periodo, leer_json, CONFIG)
from .calidad import antecedentes, calidad_titulo, TIPO_TXT

N_PCT = 5            # bajo este n se muestra "x de n" sin semáforo
VENTANA_CONV = ap.VENTANA_RECIENTE + ap.VENTANA_ANTERIOR   # 120 días: base de la conversación con el NAT
NIVEL_NOMBRE = {1: 'Nivel 1 — Levantamiento', 2: 'Nivel 2 — Resolución', 3: 'Nivel 3 — Aprendizaje'}
NIVEL_CHIP = {0: ('gray', 'sin acciones'), 1: ('amb', 'reparación'), 2: ('az', 'aprendizaje local'), 3: ('ok', 'transferible')}


# ================================================================ formato con tamaño de muestra
def xn(x, n, k=None):
    """'50% — 2 de 4'. Con n < N_PCT, sin semáforo (gris) y con aviso de muestra pequeña."""
    if not n:
        return '<span class="pill gray">sin casos</span>'
    p = round(100 * x / n)
    if n < N_PCT:
        return f'<span class="pill gray" title="Muestra pequeña: leer como casos, no como porcentaje">{p}% — {x} de {n}</span>'
    if k is None:
        return f'<b>{p}%</b> <small>— {x} de {n}</small>'
    return f'{pill(p, k)} <small>{x} de {n}</small>'


def fila(nombre, s, negrita=False, clase=''):
    t = 'b' if negrita else 'span'
    celdas = ''.join(f'<td class="num">{xn(s[n], s[dd], k)}</td>' for k, n, dd in COLS)
    return f'<tr class="{clase}"><td><{t}>{nombre}</{t}></td><td class="num">{s["ev"]}</td><td class="num">{s["acc"]}</td>{celdas}</tr>'


def titulo(t, k=70):
    """Título del evento; los nulos («0», «no», «3h») se muestran como tales para no confundir."""
    if calidad_titulo(t) == 'nulo':
        return f'<i>sin título (registrado «{esc(t)}»)</i>'
    return esc(str(t)[:k])


def chip(c, t, title=''):
    return f'<span class="chip {c}"{f" title={chr(34)}{esc(title)}{chr(34)}" if title else ""}>{t}</span>'


def ids(lst, k=3):
    lst = list(lst)
    return ', '.join(ev(i) for i in lst[:k]) + ('…' if len(lst) > k else '')


# ================================================================ contexto de aprendizaje
def preparar_aprendizaje(E, A, planta, fecha):
    Ep, Ap = E[E.Planta == planta], A[A.Planta == planta]
    ANTE, EF, C, APR = {}, {}, {}, {}
    for _, e in Ep.iterrows():
        i = int(e.Id)
        acc = Ap[Ap.RegistroId == i]
        ANTE[i] = antecedentes(e, Ep)
        EF[i] = ap.eficacia(e, acc, Ep, fecha)
        C[i] = ap.cumple(e, acc, ANTE[i])
        APR[i] = ap.aprendizaje_evento(e, acc, ANTE[i], EF[i])
    return dict(Ep=Ep, Ap=Ap, ANTE=ANTE, EF=EF, C=C, APR=APR)


def acuerdos_de(ctx, nat):
    return [a for a in ctx['acuerdos'] if a.get('nat') == nat and pd.Timestamp(a['fecha']) <= ctx['fecha']]


def aspectos(evs, ctx, nat=None):
    """Una fila por aspecto de los tres niveles, con serie reciente/anterior, lectura y casos."""
    F, fecha, C = evs['Fecha Inicio'], ctx['fecha'], ctx['L']['C']
    d_rec = fecha - pd.Timedelta(days=ap.VENTANA_RECIENTE - 1)
    d_ant = d_rec - pd.Timedelta(days=ap.VENTANA_ANTERIOR)
    rec_ev, ant_ev = evs[F >= d_rec], evs[(F < d_rec) & (F >= d_ant)]
    conv = evs[F >= d_ant]
    acu = {a['aspecto']: a for a in acuerdos_de(ctx, nat)} if nat else {}
    out = []
    for k, nivel, texto, base in ap.ASPECTOS:
        r, a = ap.serie(rec_ev, k, C), ap.serie(ant_ev, k, C)
        tot = ap.serie(conv, k, C)
        if k in acu:
            fa = pd.Timestamp(acu[k]['fecha'])
            r2 = ap.serie(evs[F >= fa], k, C)
            a2 = ap.serie(evs[(F < fa) & (F >= fa - pd.Timedelta(days=ap.VENTANA_ANTERIOR))], k, C)
            cod, txt = ap.lectura(r2, a2, fa)
            txt += f' (antes {a2[0]} de {a2[1]}, después {r2[0]} de {r2[1]})'
        else:
            cod, txt = ap.lectura(r, a)
            if cod in ('insuf', 'antes_ok', 'antes_debil') and tot[1] >= ap.N_MIN:
                cod = 'ok' if 100 * tot[0] / tot[1] >= ap.DEBIL else 'debil'
                txt = f'pocos casos: leído en {VENTANA_CONV} días'
        out.append(dict(k=k, nivel=nivel, texto=texto, rec=r, ant=a, tot=tot, cod=cod, txt=txt, acuerdo=acu.get(k)))
    return out


def debiles(asp):
    rank = {'persistente': 0, 'deterioro': 1, 'debil': 2, 'mejora': 3}
    x = [a for a in asp if ap.es_debil(a['cod'], a['rec'] if a['rec'][1] >= ap.N_MIN else a['tot'], a['ant'])]
    return sorted(x, key=lambda a: (rank.get(a['cod'], 4), ap.PRIORIDAD.index(a['k'])))


def fuertes(asp):
    x = [a for a in asp if ap.es_fuerte(a['cod'], a['rec'] if a['rec'][1] >= ap.N_MIN else a['tot']) and a['tot'][1] >= ap.N_MIN]
    return sorted(x, key=lambda a: (a['cod'] != 'sostenida', -a['tot'][0] / a['tot'][1], -a['nivel']))


# ================================================================ bloques nuevos
def tabla_niveles(asp, ctx, titulo_rec, titulo_ant):
    filas, nivel = '', 0
    for a in asp:
        if a['nivel'] != nivel:
            nivel = a['nivel']
            filas += f'<tr class="grp"><td colspan="5">{NIVEL_NOMBRE[nivel]}</td></tr>'
        c = ap.LECTURA_CHIP[a['cod']]
        ej = []
        if a['tot'][3]:
            ej.append('revisar ' + ids(sorted(a['tot'][3], reverse=True), 3))
        if a['tot'][2]:
            ej.append('referencia ' + ids(sorted(a['tot'][2], reverse=True), 2))
        filas += (f'<tr><td>{a["texto"]}</td><td class="num">{xn(*a["rec"][:2])}</td><td class="num">{xn(*a["ant"][:2])}</td>'
                  f'<td>{chip(c, a["txt"])}</td><td><small>{"<br>".join(ej) or "—"}</small></td></tr>')
    return (f'<div class="card scroll"><table><tr><th>Aspecto</th><th>{titulo_rec}</th><th>{titulo_ant}</th><th>Lectura</th><th>Casos</th></tr>{filas}</table></div>'
            f'<div class="ev-meta" style="margin-top:6px">Cada cifra es «x de n RdP». Con menos de {N_PCT} casos no se pinta semáforo y con menos de {ap.N_MIN} no se lee tendencia. '
            'Lectura: compara los últimos 30 días con los 90 anteriores (persistente = bajo en ambos; puntual = cae con pocos casos; mejora / deterioro = cambio ≥25 puntos o cruce del 50%). '
            '«Revisar» = RdP recientes que no cumplen; «referencia» = RdP que sí cumplen. Ningún aspecto es un objetivo en sí mismo: sirven para encontrar casos que conversar.</div>')


def bloque_eficacia(evs, ctx):
    """Ejecución vs eficacia en el período de conversación."""
    L = ctx['L']
    conv = evs[(evs['Fecha Inicio'] >= ctx['fecha'] - pd.Timedelta(days=VENTANA_CONV - 1)) & (evs.nS > 0)]
    g = {}
    for i in conv.Id:
        g.setdefault(L['EF'][int(i)][0], []).append(int(i))
    n = len(conv)
    if not n:
        return f'<p class="ev-meta">Sin RdP con acción sistémica en los últimos {VENTANA_CONV} días: no hay cambios cuya eficacia leer.</p>'
    it = []
    lbl = [('abierta', 'gray', 'acción sistémica aún abierta (no ejecutada)'), ('pronto', 'gray', f'ejecutada hace menos de {ap.DIAS_EFICACIA} días: aún pronto'),
           ('indicio', 'ok', f'ejecutada y sin eventos relacionados en ≥{ap.DIAS_EFICACIA} días (indicio)'),
           ('repite', 'red', 'ejecutada, con evento relacionado posterior (confirmar si es el mismo problema)')]
    for k, c, t in lbl:
        if g.get(k):
            it.append(f'{chip(c, f"{len(g[k])} de {n}")} {t}: {ids(g[k], 4)}')
    return ('<ul class="chk">' + ''.join(f'<li>{x}</li>' for x in it) + '</ul>'
            '<div class="ev-meta">Cerrada = ejecutada. La base no tiene un campo de verificación de eficacia: lo único observable es si después del cierre '
            'aparece un evento parecido en el mismo NAT. Ausencia de repetición es un indicio, no una prueba.</div>')


def practica_html(b, corto=False):
    est = {'candidata': chip('gray', 'candidata — validar con el NAT'), 'validada': chip('ok', 'validada'), 'compartida': chip('az', 'compartida')}.get(b['estado'], '')
    if corto:
        return f'{ev(b["id"])} {esc(b["por"][0]) if b["por"] else ""}'
    return (f'<b>{ev(b["id"])} {titulo(b["tit"])}</b> <small>({esc(b["nat"])}, {fmt(b["f"])})</small> {est}'
            f'<div><b>Qué hizo:</b> {"; ".join(esc(x) for x in b["que"])}</div>'
            f'<div><b>Por qué vale:</b> {", ".join(esc(x) for x in b["por"])}.</div>'
            f'<div><b>Dónde podría replicarse:</b> {esc(b["donde"])}.</div>' + (f'<div class="ev-meta">{esc(b["nota"])}</div>' if b['nota'] else ''))


def bloque_practicas(bps, vacio, max_vis=4):
    if not bps:
        return f'<div class="card vacio">{vacio}</div>'
    li = lambda xs: ''.join(f'<li style="margin-bottom:10px">{practica_html(b)}</li>' for b in xs)
    mas = (f'<details><summary>{len(bps) - max_vis} caso(s) más</summary><ul>{li(bps[max_vis:])}</ul></details>' if len(bps) > max_vis else '')
    return ('<div class="card blk b-ok"><ul>' + li(bps[:max_vis]) + '</ul>' + mas +
            '<div class="ideas-fuerza-note">Detectadas por reglas en los datos (acción sistémica sobre el control que falló, extensión a equipos similares, verificación definida, '
            f'cambio de enfoque ante una recurrencia, sin evento relacionado tras el cierre). Se excluyen las que tuvieron un evento relacionado después del cierre. '
            'Para la biblioteca de casos, marcar en config/buenas_practicas.json como validada, compartida o descartada.</div></div>')


def cadena_html(ids_, ctx, plegada=False):
    ch = ap.cadena(ids_, ctx['E'], ctx['A'], ctx['fecha'])
    filas = ''.join(f'<tr><td>{ev(f["id"])}<div class="ev-meta">{fmt(f["f"])}</div></td><td>{esc(str(f["tit"])[:60])}</td>'
                    f'<td>{esc(f["causa"][:90]) or "—"}<div class="ev-meta">{f["cq"]}</div></td><td>{esc(f["hizo"])}</td><td>{chip(f["chip"], "●")} {esc(f["tras"])}</td></tr>'
                    for f in ch['filas'])
    tabla = (f'<div class="scroll"><table class="cad"><tr><th>RdP</th><th>Evento</th><th>Causa registrada</th><th>Qué se hizo</th><th>Qué pasó después</th></tr>{filas}</table></div>')
    if plegada:
        tabla = f'<details><summary>Ver la cadena evento → acción → cierre → nuevo evento</summary>{tabla}</details>'
    return (f'{tabla}<div class="cad-l"><b>Lectura:</b> {esc(ch["lectura"])} <b>Aprendizaje:</b> {esc(ch["aprendizaje"])}<br>'
            f'<b>Para conversar:</b> <i>{esc(ch["pregunta"])}</i></div>')


def casos_cadena(m, ctx, plegada=False):
    out = []
    for c in ctx['casos']:
        if m['nat'] not in (None, c['nat']):
            continue
        s = d.estado_caso(c, ctx['E'], ctx['A'], ctx['base'][1])
        nuevo = chip('red', 'nuevo evento relacionado: ' + ', '.join(str(int(x)) for x in s['nuevos'].Id)) if len(s['nuevos']) else ''
        color = {'Confirmada': 'red', 'Probable': 'amb'}.get(c['clasificacion'], 'az')
        ids_ = list(c['eventos']) + [int(x) for x in s['nuevos'].Id]
        out.append(f'<b>{esc(c["titulo"])}</b> {chip(color, "recurrencia " + c["clasificacion"].lower())} {nuevo}'
                   f'<div class="ev-meta" style="margin:2px 0 6px">{esc(c["que_vigilar"])}</div>{cadena_html(ids_, ctx, plegada)}')
    ids_casos = {i for c in ctx['casos'] for i in c['eventos']}
    for _, e in m['rec'].iterrows():
        if e.Id not in ids_casos and len(out) < 8 and not any(i in ids_casos for i, _, _ in e.ante):
            ids_ = [i for i, _, _ in e.ante[:3]] + [int(e.Id)]
            out.append(f'<b>Posible recurrencia nueva: {ev(e.Id)} {titulo(e["Evento tiempo perdido"])}</b> {chip("az", "validar con el NAT")}'
                       f'{cadena_html(ids_, ctx, plegada)}')
    return out


# ================================================================ guía de conversación (NAT)
def guia_auto(m, ctx, asp):
    L, fecha = ctx['L'], ctx['fecha']
    bps = [b for b in ctx['bp'] if b['nat'] == m['nat']]
    fu, de = fuertes(asp), debiles(asp)
    bien = []
    if bps:
        b = bps[0]
        bien.append(f'<b>{esc(b["por"][0].capitalize())}</b> en {ev(b["id"])} ({titulo(b["tit"], 50)}).')
    for a in fu[:2 - len(bien)]:
        bien.append(f'<b>{ap.FORTALEZA_TXT[a["k"]]}</b>: {a["tot"][0]} de {a["tot"][1]} RdP en {VENTANA_CONV} días ({a["txt"]}); p. ej. {ids(sorted(a["tot"][2], reverse=True), 2)}.')
    if not bien:
        i = m['ind']
        if i['pPlazo'] is not None and i['acc'] >= N_PCT and i['pPlazo'] >= 80:
            bien.append(f'<b>Disciplina de plazos</b>: {i["plazo"]} de {i["acc"]} acciones en plazo.')
    mejorar = []
    for a in de[:2]:
        no = sorted(a['tot'][3], reverse=True)
        base = a['rec'] if a['rec'][1] >= ap.N_MIN else a['tot']
        mejorar.append(f'<b>{ap.OPORTUNIDAD_TXT[a["k"]]}</b>: hoy {base[0]} de {base[1]} RdP lo logran ({a["txt"]}). Casos: {ids(no, 3)}.')
    revisar, vistos = [], set()

    def add(i, por):
        if i not in vistos and len(revisar) < 4 and i in ctx['L']['C']:
            vistos.add(i)
            t = ctx['E'].loc[ctx['E'].Id == i, 'Evento tiempo perdido'].iloc[0]
            revisar.append(f'{ev(i)} <small>{titulo(t, 45)}</small> — {por}')
    for a in de[:2]:
        no = sorted(a['tot'][3], reverse=True)
        if no:
            add(no[0], ap.OPORTUNIDAD_TXT[a['k']].lower())
    for c in ctx['casos']:
        if c['nat'] == m['nat']:
            add(int(max(c['eventos'])), f'recurrencia {c["clasificacion"].lower()}: ¿qué pasó entre un evento y el siguiente?')
            break
    if bps:
        add(bps[0]['id'], 'buen ejemplo: reconocerlo y ver si se puede extender')
    practica = practica_html(bps[0]) if bps else (f'Sin un caso con evidencia suficiente en los últimos {ap.VENTANA_PRACTICAS} días. No se propone ninguno: '
                                                    'si el NAT conoce uno, registrarlo en config/buenas_practicas.json.')
    if de:
        a = de[0]
        base = a['rec'] if a['rec'][1] >= ap.N_MIN else a['tot']
        acuerdo = (f'{ap.ACUERDO_TXT[a["k"]]}<div class="ev-meta">Cómo lo veremos: «{a["texto"]}» — hoy {base[0]} de {base[1]}. '
                   f'Revisar el {fecha + pd.Timedelta(days=30):%d-%m-%Y} con las RdP del período. Registrar el acuerdo en config/acuerdos_nat.json '
                   f'(aspecto «{a["k"]}») para que el informe muestre su evolución.</div>')
    else:
        acuerdo = 'Sin una oportunidad con evidencia suficiente: acordar mantener lo que funciona y revisar en 30 días.'
    return dict(bien=bien, mejorar=mejorar, revisar=revisar, practica=practica, acuerdo=acuerdo)


def bloque_guia(m, ctx, com, asp):
    g = guia_auto(m, ctx, asp)
    cv = com.get('conversacion', {})
    for k in ('bien', 'mejorar', 'revisar', 'practica', 'acuerdo'):
        if cv.get(k):
            g[k] = cv[k]
    lista = lambda x: ul(x) if isinstance(x, list) else x
    vac = '<span class="ev-meta">Sin evidencia suficiente en el período.</span>'
    filas = [('1', 'Qué hacemos bien', lista(g['bien']) if g['bien'] else vac),
             ('2', 'Qué debemos mejorar', lista(g['mejorar']) if g['mejorar'] else vac),
             ('3', 'Qué casos lo muestran', lista(g['revisar']) if g['revisar'] else vac),
             ('4', 'Qué podemos compartir', g['practica']),
             ('5', 'Qué haremos diferente y cuándo lo revisamos', g['acuerdo'])]
    seg = ''
    acs = acuerdos_de(ctx, m['nat'])
    if acs:
        asp_k = {a['k']: a for a in asp}
        seg = '<div class="seg"><b>Seguimiento de acuerdos anteriores</b><ul>' + ''.join(
            f'<li>{pd.Timestamp(a["fecha"]):%d-%m-%Y}: {esc(a["acuerdo"])} — '
            + (f'{chip(ap.LECTURA_CHIP[asp_k[a["aspecto"]]["cod"]], asp_k[a["aspecto"]]["txt"])}' if a.get('aspecto') in asp_k else '')
            + (f' · revisar el {pd.Timestamp(a["revisar_el"]):%d-%m-%Y}' if a.get('revisar_el') else '') + '</li>' for a in acs) + '</ul></div>'
    filas_html = ''.join(f'<tr><td class="gn">{n}</td><td class="gq">{q}</td><td>{r}</td></tr>' for n, q, r in filas)
    return (f'<div class="section-title">🗣 Conversación 1 a 1</div><div class="card guia"><table>{filas_html}</table>{seg}'
            f'<div class="ideas-fuerza-note">{"Redactado tras revisión" if cv else "Propuesta generada por reglas a partir de los últimos " + str(VENTANA_CONV) + " días"}. '
            'Es un punto de partida para la conversación, no una evaluación del NAT: confirmar los casos con el equipo antes de acordar.</div></div>')


# ================================================================ fortalezas y oportunidades
def fortalezas_g(m, ctx, asp):
    bps = [b for b in ctx['bp'] if m['nat'] in (None, b['nat'])]
    out = []
    for b in bps[:1 if m['nat'] else 0]:
        out.append(f'<b>{esc(b["por"][0].capitalize())}</b> — {ev(b["id"])}: {esc(b["que"][0])}. <i>Dónde replicar:</i> {esc(b["donde"])}.')
    for a in fuertes(asp)[:3 - len(out)]:
        out.append(f'<b>{ap.FORTALEZA_TXT[a["k"]]}</b> — {a["tot"][0]} de {a["tot"][1]} RdP en {VENTANA_CONV} días ({a["txt"]}). '
                   f'Ejemplos: {ids(sorted(a["tot"][2], reverse=True), 3)}.')
    if len(out) < 2:
        # del reporte diario solo se toman las fortalezas de gestión (plazos, registro, cierre por tercero);
        # las de análisis y extensión ya están evaluadas arriba con criterios más estrictos
        out += [f for f in fortalezas_auto(m) if f.startswith(('<b>Disciplina', '<b>Registro', '<b>Cierre'))][:2 - len(out)]
    return out


def oportunidades_g(m, ctx, asp):
    out = []
    for a in debiles(asp)[:3]:
        no = sorted(a['tot'][3], reverse=True)
        out.append(f'<b>{ap.OPORTUNIDAD_TXT[a["k"]]}</b> — últimos 30 días: {a["rec"][0]} de {a["rec"][1]}; 90 días anteriores: {a["ant"][0]} de {a["ant"][1]} '
                   f'→ {chip(ap.LECTURA_CHIP[a["cod"]], a["txt"])}. Casos para conversar: {ids(no, 3)}.<br><i>Propuesta:</i> {ap.ACUERDO_TXT[a["k"]]}')
    i = m['ind']
    if len(out) < 3 and i['cerr'] >= N_PCT and i['pTercero'] is not None and i['pTercero'] < 20:
        out.append(f'<b>Distinguir ejecutada de eficaz</b> — {i["cerr"] - i["tercero"]} de {i["cerr"]} acciones cerradas las cerró su propio responsable. '
                   '<br><i>Propuesta:</i> que las acciones sistémicas de recurrencias las cierre un tercero tras comprobar el resultado.')
    prov = m['evp'][m['evp'].proveedor > 0]
    if len(out) < 3 and len(prov):
        out.append(f'<b>Ser dueños del modo de falla</b> — {ids(prov.Id, 4)} terminan en reunión o revisión con el proveedor sin causa propia. '
                   '<br><i>Propuesta:</i> que el NAT registre su propia hipótesis de causa antes de derivar.')
    return out


# ================================================================ planta: mapa y aprendizaje
def mapa_nat(ctx, ambitos):
    filas = ''
    for m in sorted(ambitos[1:], key=lambda m: m['nat']):
        n = m['nat']
        asp = m['asp']
        fu, de = fuertes(asp), debiles(asp)
        bps = [b for b in ctx['bp'] if b['nat'] == n]
        conv = m['ev'][m['ev']['Fecha Inicio'] >= ctx['fecha'] - pd.Timedelta(days=VENTANA_CONV - 1)]
        casos = [c for c in ctx['casos'] if c['nat'] == n]
        f_txt = (f'{ap.FORTALEZA_TXT[fu[0]["k"]]} <small>({fu[0]["tot"][0]} de {fu[0]["tot"][1]})</small>' if fu else
                 '<span class="ev-meta">sin evidencia suficiente</span>')
        o_txt = (f'{ap.OPORTUNIDAD_TXT[de[0]["k"]]} {chip(ap.LECTURA_CHIP[de[0]["cod"]], de[0]["txt"])}' if de else
                 '<span class="ev-meta">sin evidencia suficiente</span>')
        p_txt = practica_html(bps[0], corto=True) if bps else '—'
        r_txt = f'{len(casos)} en seguimiento' if casos else '—'
        filas += (f'<tr><td><a href="#" data-nat="{esc(n)}"><b>{esc(n)}</b></a></td><td class="num">{len(m["evp"])} / {len(conv)}</td>'
                  f'<td>{f_txt}</td><td>{o_txt}</td><td>{p_txt}</td><td>{r_txt}</td></tr>')
    return ('<div class="card scroll"><table><tr><th>NAT</th><th>RdP 30 d / 120 d</th><th>Fortaleza a reconocer</th><th>Oportunidad prioritaria</th>'
            f'<th>Práctica para compartir</th><th>Recurrencias</th></tr>{filas}</table></div>'
            '<div class="ev-meta" style="margin-top:6px">Orden alfabético: no es un ranking. Más o menos RdP no significa mejor o peor gestión. '
            'Clic en el NAT para abrir su radiografía y la guía de conversación.</div>')


def aprendizaje_planta(evs, ctx):
    L = ctx['L']
    conv = evs[(evs['Fecha Inicio'] >= ctx['fecha'] - pd.Timedelta(days=VENTANA_CONV - 1)) & (evs.nAcc > 0)]
    n = len(conv)
    if not n:
        return '<p class="ev-meta">Sin RdP con acciones en el período.</p>'
    niv = {k: [int(i) for i in conv.Id if L['APR'][int(i)][0] == k] for k in (1, 2, 3)}
    ext = [int(i) for i in conv.Id if L['C'][int(i)]['extiende']]
    rec = [int(i) for i in conv.Id if L['C'][int(i)]['recur'] is not None]
    rec_ok = [i for i in rec if L['C'][i]['recur']]
    return (f'<p>De <b>{n} RdP con acciones</b> en los últimos {VENTANA_CONV} días:</p><ul class="chk">'
            f'<li>{chip("ok", f"{len(niv[3])} de {n}")} dejan un aprendizaje transferible (cambian el control que falló y lo extienden, lo verifican o no se ha repetido): {ids(niv[3], 4)}</li>'
            f'<li>{chip("az", f"{len(niv[2])} de {n}")} cambian un plan o estándar (aprendizaje local)</li>'
            f'<li>{chip("amb", f"{len(niv[1])} de {n}")} solo reparan o revisan: no queda un cambio registrado</li>'
            f'<li>{len(ext)} extienden la solución a equipos similares{": " + ids(ext, 4) if ext else ""}</li>'
            f'<li>{len(rec_ok)} de {len(rec)} problemas repetidos se abordaron con un enfoque distinto al anterior</li></ul>'
            f'<h3 class="card-h" style="margin-top:12px">Ejecución vs. eficacia</h3>{bloque_eficacia(evs, ctx)}')


# ================================================================ tablas modificadas
def bloque_nuevos(m, ctx):
    if not len(m['nuevos']):
        return '<div class="card vacio">Sin RdP nuevas en la ventana.</div>'
    filas = ''
    for _, e in m['nuevos'].sort_values('Fecha Inicio').iterrows():
        niveles = chequeo3(e, ctx)
        chk = ''.join(f'<li class="nv">{t}</li>' + ''.join(f'<li>{chip(c, ICON[c])} {esc(x)}</li>' for c, x in it) for t, it in niveles)
        ante = ', '.join(f'{ev(i)} <small>{fmt(f)} · {esc(k)}</small>' for i, f, k in e.ante[:3]) or '—'
        filas += (f'<tr><td>{ev(e.Id)}<div class="ev-meta">{fmt(e["Fecha Inicio"])} · {esc(e.Estado)}</div><div style="margin-top:4px">{pauta_chips(e)}</div></td>'
                  f'<td><div class="ev-tit">{esc(e["Evento tiempo perdido"])}</div><div class="ev-meta">{esc(e.NAT)} · {esc(e["Área Responsable"])} · '
                  f'{esc(e["Líder responsable"])} · {esc(e.Herramienta)}</div></td><td><ul class="chk">{chk}</ul></td><td>{ante}</td></tr>')
    return ('<div class="card scroll"><table><tr><th>RdP · pauta</th><th>Evento</th><th>Chequeo en tres niveles</th>'
            f'<th>Antecedentes 12 meses</th></tr>{filas}</table></div>')


ICON = {'ok': '✓', 'amb': '!', 'red': '✕', 'gray': '·', 'az': 'i'}


def chequeo3(e, ctx):
    i = int(e.Id)
    acc = ctx['A'][ctx['A'].RegistroId == i]
    e2 = e.copy()
    e2['ante'] = ctx['L']['ANTE'].get(i, [])
    chk = chequeo_evento(e2, acc)
    n1 = [chk[0], ('gray', 'Descripción y evidencia del evento: no se registran en la base')]
    n2 = [x for x in chk[1:] if 'SAR' not in x[1]]
    n3 = ctx['L']['APR'][i][1]
    return [(NIVEL_NOMBRE[1], n1), (NIVEL_NOMBRE[2], n2), (NIVEL_NOMBRE[3], n3)]


def tabla_eventos(evs, ctx):
    if not len(evs):
        return '<div class="card vacio">Sin eventos en el período.</div>'
    b = ''
    for _, e in evs.sort_values('Fecha Inicio', ascending=False).iterrows():
        tit = f'<span class="pill red">{esc(e["Evento tiempo perdido"])}</span>' if e.tit == 'nulo' else esc(e['Evento tiempo perdido'])
        est = 'Finalizada' if e.Estado == 'Cerrado' else '<span class="pill amb">En creación</span>'
        sis = '<span class="pill red">0</span>' if e.nAcc and not e.nS else e.nS
        nv = ctx['L']['APR'][int(e.Id)][0]
        b += (f'<tr class="clic" data-evrow="{int(e.Id)}"><td>{ev(e.Id)}</td><td class="num">{fmt(e["Fecha Inicio"])}</td><td>{tit}</td>'
              f'<td>{esc(e["Área Responsable"])}</td><td>{esc(e["Líder responsable"])}</td><td>{esc(e.Herramienta)}</td>'
              f'<td>{est}</td><td>{pauta_chips(e)}</td><td class="num">{e.nAcc}</td><td class="num">{sis}</td><td>{chip(*NIVEL_CHIP[nv])}</td></tr>')
    return ('<div class="card scroll"><table><tr><th>ID</th><th>Inicio</th><th>Título</th><th>Área</th><th>Líder</th><th>Herramienta</th><th>Estado</th>'
            f'<th>Pauta 0–3</th><th>Acciones</th><th>Sistémicas</th><th>Aprendizaje</th></tr>{b}</table></div>')


def bloque_recurrencias(rec, ctx):
    if not len(rec):
        return '<div class="card vacio">Sin coincidencias con eventos previos.</div>'
    b = ''
    for _, e in rec.sort_values('Fecha Inicio', ascending=False).iterrows():
        prev = e.ante[0][0]
        f0 = ap.cadena([prev, int(e.Id)], ctx['E'], ctx['A'], ctx['fecha'])['filas'][0]
        b += (f'<tr><td>{ev(e.Id)}<div class="ev-meta">{fmt(e["Fecha Inicio"])} · {esc(e.NAT)}</div></td><td>{esc(e["Evento tiempo perdido"])}</td>'
              f'<td>{", ".join(f"{ev(i)} <small>{fmt(f)} · {esc(k)}</small>" for i, f, k in e.ante[:4])}</td>'
              f'<td><small>En {ev(prev)}: {esc(f0["hizo"])}.<br>{chip(f0["chip"], "●")} {esc(f0["tras"])}.</small></td></tr>')
    return ('<div class="card scroll"><table><tr><th>Evento</th><th>Título</th><th>Antecedentes (coincidencia)</th><th>Qué pasó entre el anterior y este</th></tr>'
            f'{b}</table></div><div class="ev-meta" style="margin-top:6px">Coincidencia por tag o palabras clave en título y causas, misma NAT, 12 meses. '
            'Es una alerta: se confirma con el mismo equipo/tag y modo de falla. La pregunta no es cuántas RdP hay, sino qué cambió entre una y otra.</div>')


def tabla_cerradas(df, ctx):
    if not len(df):
        return '<div class="card vacio">Sin acciones en esta categoría.</div>'
    b = ''
    for _, r in df.iterrows():
        e = ctx['E'][ctx['E'].Id == r.RegistroId].iloc[0]
        c, t = ap.eficacia_accion(r, e, ctx['L']['Ep'], ctx['fecha'])
        obs = ' '.join(chip(c2, t2) for c2, t2 in obs_accion(r) if t2 in ('autocierre', 'registrar resultado') or t2.startswith('cerrada tarde'))
        b += (f'<tr class="clic" data-ac="{int(r.AccionId)}"><td>{ev(r.RegistroId)}<div class="ev-meta">{esc(r.NAT)}</div></td>'
              f'<td>{esc(str(r["Acción"])[:140])}<div class="ev-meta">Causa: {esc(str(r["Causa raíz"])[:90])}</div></td>'
              f'<td>{chip(dict(S="ok", C="amb", R="az")[r.tipo], TIPO_TXT[r.tipo])}</td><td>{esc(r["Cerrada por"])}</td><td class="num">{fmt(r["Fecha cierre"])}</td>'
              f'<td>{obs or "—"}<div class="ev-meta">{chip(c, "eficacia")} {esc(t)}</div></td></tr>')
    return ('<div class="card scroll"><table><tr><th>RdP</th><th>Acción</th><th>Tipo</th><th>Cerrada por</th><th>Cierre</th><th>Ejecución → eficacia</th></tr>'
            f'{b}</table></div>')


def bloque_diario(m, ctx):
    return (f'<div class="section-title">🆕 RdP nuevas</div>{bloque_nuevos(m, ctx)}'
            f'<div class="two-col even"><div><div class="section-title">⏰ Acciones vencidas</div>{tabla_acciones(m["vencidas"], "vencidas")}</div>'
            f'<div><div class="section-title">📅 Vencen en los próximos 7 días</div>{tabla_acciones(m["por_vencer"], "por_vencer")}</div></div>'
            f'<div class="section-title">✔ Acciones cerradas en la ventana — ejecutadas, no necesariamente eficaces</div>{tabla_cerradas(m["cerradas"], ctx)}')


def bloque_foco_operativo(com, focos, titulo):
    return (f'<div class="section-title">🎯 {titulo}</div><div class="card blk b-az"><ul>'
            + (''.join(f'<li>{x}</li>' for x in focos) or '<li>Sin alertas para hoy.</li>')
            + f'</ul><div class="ideas-fuerza-note">{"Redactado tras revisión" if com.get("focos") else "Generado automáticamente por reglas"}. '
            'Pendientes de gestión del día (plazos, RdP sin cerrar, recurrencias nuevas).</div></div>')


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


# ================================================================ vistas
def vista_planta(m, ctx, com, ambitos):
    i, evp, acp = m['ind'], m['evp'], m['acp']
    grupo = lambda g: indicadores(evp[evp.grupo == g], acp[acp.RegistroId.isin(evp[evp.grupo == g].Id)])
    logro = com.get('logro') or logro_auto(m)
    casos = com.get('casos') or casos_cadena(m, ctx, plegada=True)
    nats = sorted(evp.NAT.unique())
    detalle_nat = ''.join(fila(esc(n), indicadores(evp[evp.NAT == n], acp[acp.NAT == n])) for n in nats)
    asp = m['asp']
    fort = com.get('fortalezas') or fortalezas_g(m, ctx, asp)
    brec = com.get('brechas') or oportunidades_g(m, ctx, asp)
    return f'''
<div class="mega-title" style="margin-top:22px"><span class="mega-tag">Planta</span> Reporte diario — reunión de líderes NAT</div>
<div class="section-title">📌 Hoy</div>{bloque_hoy(m, ctx)}
{bloque_foco_operativo(com, com.get("focos") or focos_auto(m), "Foco para la reunión RdP")}
{f'<div class="section-title">🏆 Logro del período</div><div class="card logro">{logro}<i>Cerrada significa ejecutada, no eficaz: la base no tiene campo de verificación de eficacia, ni descripción del evento, ni registro de qué aportó SAR.</i></div>' if logro else ''}
<div class="section-title">📊 Resumen de calidad — Operaciones vs. Mantención (últimos {VENTANA_CALIDAD} días)</div>
{bloque_kpis_periodo(i)}
<div style="margin-top:14px">{tabla_resumen_planta(m, ctx)}</div>
<div class="ev-meta" style="margin-top:6px">Operaciones = Operativos + Procesos · Mantención = Mecánicos + Electrocontrol. Cada celda: porcentaje — x de n. Semáforo: verde = meta del Diagnóstico; ámbar = entre la línea base y la meta; rojo = peor que la línea base;
gris = menos de {N_PCT} casos (leer como casos, no como porcentaje). Análisis causal adecuado = pauta ≥2 (explica el mecanismo o nombra el control).</div>
<div class="two-col even"><div class="card card-pad"><h3 class="card-h">Mezcla de acciones</h3>
{barra("Operaciones", grupo("Operaciones"))}{barra("Mantención", grupo("Mantención"))}{barra("Con SAR", m["sar"]["Si"])}{barra("Sin SAR", m["sar"]["No"])}{barra("Total", i)}{LEYENDA_TIPO}</div>
<div class="card card-pad"><h3 class="card-h">Qué está aprendiendo la planta (nivel 3)</h3>{aprendizaje_planta(m["ev"], ctx)}</div></div>
<div class="section-title">🧭 Mapa de conversación por NAT</div>{mapa_nat(ctx, ambitos)}
<details class="det"><summary>Indicadores por NAT (últimos {VENTANA_CALIDAD} días, x de n)</summary><div class="card scroll">
<table>{cabecera("NAT")}{detalle_nat}</table></div></details>
<div class="section-title">📐 Calidad en tres niveles — planta</div>
{tabla_niveles(asp, ctx, "Últimos 30 días", "90 días anteriores")}
<div class="two-col even"><div class="card blk b-ok"><h3>✅ Fortalezas para reconocer</h3>{ul(fort)}</div>
<div class="card blk b-red"><h3>🔧 Oportunidades de mejora</h3>{ul(brec)}</div></div>
<div class="section-title">📚 Casos de referencia para compartir (últimos {ap.VENTANA_PRACTICAS} días)</div>
{bloque_practicas(ctx["bp"], "Sin casos con evidencia suficiente en el período.")}
<div class="section-title">🔍 Casos críticos en seguimiento — qué pasó entre un RdP y el siguiente</div><div class="card blk b-nar">{ul(casos)}</div>
{bloque_diario(m, ctx)}
<div class="section-title">♻ Posibles recurrencias (últimos {VENTANA_CALIDAD} días)</div>{bloque_recurrencias(m["rec"], ctx)}
<div class="section-title">🤖 Impacto del SAR</div>{tabla_sar(m["sar"])}'''


def vista_nat(m, ctx, com, med):
    i, n, asp = m['ind'], m['nat'], m['asp']
    lideres = m['evp']['Líder responsable'].value_counts()
    seg = lambda v, c: f'<i style="width:{100 * v / (i["acc"] or 1):.1f}%;background:{c}"></i>'
    areas = ''.join(fila(esc(a), indicadores(m['evp'][m['evp']['Área Responsable'] == a], m['acp'][m['acp']['Área Responsable'] == a]))
                    for a in sorted(m['evp']['Área Responsable'].unique()))
    lbl_base = f'Línea base {esc(n)} ({fmt(ctx["base"][0])} a {fmt(ctx["base"][1])})'
    tabla_area = (f'<div class="card scroll"><table>{cabecera("Área")}{areas}{fila("Total " + esc(n), i, True)}'
                  f'{fila(lbl_base, m["base"], False, "ref")}{fila_meta(ctx["metas"])}</table></div>')
    casos = com.get('casos') or casos_cadena(m, ctx)
    if com.get('conclusion') or com.get('medidas'):
        med = dict(conclusion=com.get('conclusion') or (med or {}).get('conclusion', ''),
                   medidas=[dict(zip(('caso', 'control_que_falto', 'medida', 'verificacion'), x)) for x in com['medidas']] if com.get('medidas') else (med or {}).get('medidas', []))
    fort = com.get('fortalezas') or fortalezas_g(m, ctx, asp)
    brec = com.get('brechas') or oportunidades_g(m, ctx, asp)
    conv = m['ev'][m['ev']['Fecha Inicio'] >= ctx['fecha'] - pd.Timedelta(days=VENTANA_CONV - 1)]
    return f'''
<div class="mega-title" style="margin-top:22px"><span class="mega-tag">Radiografía</span> NAT {esc(n)} — reunión 1 a 1</div>
<div class="section-sub">Líderes responsables ({VENTANA_CALIDAD} días): {" · ".join(f"{esc(k)} ({v})" for k, v in lideres.items()) or "—"} ·
RdP en los últimos {VENTANA_CONV} días: {len(conv)} (base de la conversación)</div>
<div class="section-title">📌 Hoy</div>{bloque_hoy(m, ctx)}
{bloque_guia(m, ctx, com, asp)}
<div class="section-title">📐 Calidad en tres niveles — evolución del NAT</div>
{tabla_niveles(asp, ctx, "Últimos 30 días", "90 días anteriores")}
<div class="two-col even"><div class="card blk b-ok"><h3>✅ Fortalezas para reconocer</h3>{ul(fort)}</div>
<div class="card blk b-red"><h3>🔧 Oportunidades de mejora</h3>{ul(brec)}</div></div>
<div class="two-col even"><div class="card card-pad"><h3 class="card-h">Acciones por estado (últimos {VENTANA_CALIDAD} días)</h3>
<div class="bar-row"><div class="lbl"><span><b>Plazo</b></span><span class="num">{i["cerrOk"]} en plazo · {i["tarde"]} tarde · {i["abOk"]} abiertas al día · {i["venc"]} vencidas</span></div>
<div class="bar-track stk">{seg(i["cerrOk"], "var(--ok)")}{seg(i["tarde"], "var(--naranja)")}{seg(i["abOk"], "var(--madera)")}{seg(i["venc"], "var(--rojo)")}</div></div>
<div class="legend"><span><i style="background:var(--ok)"></i>Cerrada en plazo</span><span><i style="background:var(--naranja)"></i>Cerrada tarde</span><span><i style="background:var(--madera)"></i>Abierta al día</span><span><i style="background:var(--rojo)"></i>Vencida</span></div>
<div style="margin-top:18px">{barra("Tipo de acción", i)}</div>{LEYENDA_TIPO}</div>
<div class="card card-pad"><h3 class="card-h">Ejecución vs. eficacia (RdP con acción sistémica, {VENTANA_CONV} días)</h3>{bloque_eficacia(m["ev"], ctx)}</div></div>
<div class="section-title">🔍 Sus casos críticos — qué pasó entre un RdP y el siguiente</div><div class="card blk b-nar">{ul(casos)}</div>
<div class="section-title">🛡 Conclusión y medidas de control propuestas</div>{bloque_medidas(med)}
{bloque_foco_operativo(com, com.get("focos") or focos_auto(m), "Pendientes operativos del NAT")}
{bloque_diario(m, ctx)}
<div class="section-title">♻ Posibles recurrencias (últimos {VENTANA_CALIDAD} días)</div>{bloque_recurrencias(m["rec"], ctx)}
<div class="section-title">📋 Eventos del NAT (últimos {VENTANA_CALIDAD} días y en creación) — clic para el detalle</div>
{tabla_eventos(pd.concat([m["evp"], m["creacion"]]).drop_duplicates("Id"), ctx)}
<details class="det"><summary>Indicadores por área del NAT (últimos {VENTANA_CALIDAD} días, x de n)</summary>{tabla_area}</details>
<div class="section-title">📂 Acciones abiertas ({len(m["abiertas"])}) — clic para el detalle</div>{tabla_acciones(m["abiertas"], "abiertas", 80)}'''


# ================================================================ detalle (clic) y render
def datos_detalle(ctx):
    D = d.datos_detalle(ctx['E'], ctx['A'], ctx['planta'], [])
    L = ctx['L']
    for _, e in L['Ep'].iterrows():
        i = int(e.Id)
        x = D['ev'][i]
        x['ante'] = [[int(a), fmtl(f), k] for a, f, k in L['ANTE'][i]]
        x['chk3'] = chequeo3(e, ctx)
        nv = L['APR'][i][0]
        x['nivel'] = [NIVEL_CHIP[nv][0], ap.NIVEL_TXT[nv]]
    for _, r in L['Ap'].iterrows():
        e = L['Ep'][L['Ep'].Id == r.RegistroId].iloc[0]
        D['ac'][int(r.AccionId)]['efi'] = list(ap.eficacia_accion(r, e, L['Ep'], ctx['fecha']))
    return D


JS = d.JS.replace(
    """ <h4>Chequeo de calidad (playbook MGO + diagnóstico)</h4><ul class="chk">${e.chk.map(([c,t])=>`<li>${chip(c,icon[c])} ${esc(t)}</li>`).join('')}</ul>""",
    """ <h4>Chequeo en tres niveles ${chip(e.nivel[0],e.nivel[1])}</h4><ul class="chk">${e.chk3.map(([n,it])=>`<li class="nv">${esc(n)}</li>`+it.map(([c,t])=>`<li>${chip(c,icon[c])} ${esc(t)}</li>`).join('')).join('')}</ul>""").replace(
    """ <tr><td>Cierre</td><td>${a.cierre}</td></tr><tr><td>Cerrada por</td><td>${esc(a.por)}</td></tr></table>""",
    """ <tr><td>Cierre</td><td>${a.cierre}</td></tr><tr><td>Cerrada por</td><td>${esc(a.por)}</td></tr>
 <tr><td>Ejecución</td><td>${a.estado==='Cerrada'?'Ejecutada (cerrada el '+a.cierre+')':'No ejecutada aún'}</td></tr>
 <tr><td>Eficacia</td><td>${a.efi?chip(a.efi[0],'●')+' '+esc(a.efi[1]):'—'}</td></tr></table>""") + r'''
document.querySelectorAll('[data-nat]').forEach(x=>x.addEventListener('click',ev=>{ev.preventDefault();
 const o=[...sel.options].find(o=>o.text===x.dataset.nat);if(o){sel.value=o.value;sel.onchange();}}));
'''
assert 'chk3' in JS and 'efi' in JS, 'No se pudo adaptar el JS del reporte diario'

CSS_GESTION = '''
tr.grp td{background:var(--bg2);font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--gris);font-weight:700}
.chk li.nv{font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--grisC);margin-top:6px;list-style:none}
.guia table td{vertical-align:top;padding:10px 12px;border-bottom:1px solid var(--linea)}.guia table tr:last-child td{border-bottom:none}
.guia .gn{width:28px;font-weight:700;color:var(--gris);font-size:18px}.guia .gq{width:200px;font-weight:700}
.guia ul{margin:0;padding-left:18px}.guia .seg{margin-top:12px;padding-top:10px;border-top:1px dashed var(--linea);font-size:13px}
.cad{font-size:12.5px;margin-top:6px}.cad-l{font-size:12.5px;margin:6px 0 4px;padding:8px 10px;background:var(--bg2);border-radius:6px}
details.det{margin-top:10px}details.det summary,details summary{cursor:pointer;color:var(--azul);font-size:12.5px;margin:6px 0}
@media print{details{display:block}details>summary{display:none}}
'''


def render(ctx, vistas_html, nombres, datos, fuente_txt):
    html = d.render(ctx['planta'], ctx['fecha'], ctx['desde'], vistas_html, nombres, datos, fuente_txt)
    html = html.replace(d.JS, JS).replace('</style>', CSS_GESTION + '</style>', 1)
    html = html.replace('<title>RdP diario', '<title>RdP gestión')
    html = html.replace('Reporte diario para líderes NAT — efectividad, profundidad y prevención',
                        'Para conversar con cada NAT: medir → diagnosticar → conversar → mejorar → verificar → aprender → compartir')
    html = html.replace('La base no registra descripción, categoría, horas perdidas ni eficacia: lo que falta en el registro no prueba que no se hizo.',
                        'La base no registra descripción, evidencia, categoría, horas perdidas ni verificación de eficacia: lo que falta en el registro no prueba que no se hizo. '
                        f'La eficacia se lee solo como indicio (sin eventos relacionados ≥{ap.DIAS_EFICACIA} días después del cierre). Las buenas prácticas y las lecturas son '
                        'propuestas para validar con el NAT, no evaluaciones.')
    return html


def main(argv=None):
    p = argparse.ArgumentParser(description='Informe de calidad RdP para conversar con cada NAT')
    p.add_argument('--planta', default='Nueva Aldea')
    p.add_argument('--fecha', default=None, help='AAAA-MM-DD; por defecto, hoy')
    p.add_argument('--dias', type=int, default=None, help='Días de novedades; por defecto 1 (lunes: 3)')
    p.add_argument('--excel', default=None)
    p.add_argument('--comentarios', default=None, help='JSON con textos redactados por ámbito ("Planta" o nombre de NAT)')
    p.add_argument('--json', action='store_true')
    p.add_argument('--salida', default='out')
    a = p.parse_args(argv)

    ruta = Path(a.excel) if a.excel else fuente.ultimo_excel()
    reg, acc = fuente.normalizar(*fuente.cargar_excel(ruta))
    E, A, fecha = d.preparar(reg, acc, pd.Timestamp(a.fecha or pd.Timestamp.today().date()))
    if not (E.Planta == a.planta).any():
        raise SystemExit(f'No hay registros para la planta "{a.planta}". Plantas: {sorted(reg.Planta.unique())}')
    desde = d.ventana_novedades(fecha, a.dias)
    d_cal = fecha - pd.Timedelta(days=VENTANA_CALIDAD - 1)
    lb = leer_json('linea_base.json', {}).get(a.planta, {})
    base = ((pd.Timestamp(lb['periodo']['desde']), pd.Timestamp(lb['periodo']['hasta'])) if lb
            else (d_cal - pd.Timedelta(days=60), d_cal - pd.Timedelta(days=1)))
    metas = lb.get('metas', {})
    casos = [c for c in leer_json('casos_seguimiento.json', []) if c.get('planta') == a.planta]
    medidas = {k: v for k, v in leer_json('medidas_control.json', {}).items() if v.get('planta') == a.planta}
    acuerdos = [x for x in leer_json('acuerdos_nat.json', {}).get('acuerdos', []) if x.get('planta') == a.planta]
    validadas = leer_json('buenas_practicas.json', {}).get('casos', {})
    comentarios = json.loads(Path(a.comentarios).read_text(encoding='utf-8')) if a.comentarios else {}

    L = preparar_aprendizaje(E, A, a.planta, fecha)
    seguimiento = {i for c in casos if c['clasificacion'] in ('Confirmada', 'Probable') for i in c['eventos']}
    bp = ap.buenas_practicas(L['Ep'], L['Ap'], L['ANTE'], L['EF'], fecha, validadas, seguimiento)
    ctx = dict(E=E, A=A, planta=a.planta, fecha=fecha, desde=desde, d_cal=d_cal, base=base, metas=metas, casos=casos,
               L=L, bp=bp, acuerdos=acuerdos)

    Ep = L['Ep']
    nats = sorted(Ep.NAT.unique(), key=lambda n: -len(Ep[Ep.NAT == n]))
    ambitos = [d.calcular_ambito(E, A, a.planta, desde, d_cal, base)] + [d.calcular_ambito(E, A, a.planta, desde, d_cal, base, n) for n in nats]
    for k, v in metas.items():
        if k in UMBRALES:
            UMBRALES[k][0] = v['valor']
            b = ambitos[0]['base'].get(k)
            if b is not None:
                UMBRALES[k][1] = max(b, v['valor']) if UMBRALES[k][2] else min(b, v['valor'])
    for m in ambitos:
        m['asp'] = aspectos(m['ev'], ctx, m['nat'])
    vistas = [vista_planta(ambitos[0], ctx, comentarios.get('Planta', {}), ambitos)] + \
             [vista_nat(m, ctx, comentarios.get(m['nat'], {}), medidas.get(m['nat'])) for m in ambitos[1:]]

    out = Path(a.salida)
    out.mkdir(exist_ok=True)
    slug = a.planta.replace(' ', '_')
    f = out / f'RdP_gestion_{slug}_{fecha:%Y-%m-%d}.html'
    f.write_text(render(ctx, vistas, ['Planta completa'] + nats, datos_detalle(ctx), f'Fuente: {ruta.name}'), encoding='utf-8')
    print(f)
    if a.json:
        res = {}
        for m in ambitos:
            res[m['nat'] or 'Planta'] = dict(
                aspectos=[dict(aspecto=x['k'], nivel=x['nivel'], texto=x['texto'], ultimos_30=x['rec'][:2], anteriores_90=x['ant'][:2],
                               lectura=x['txt'], no_cumplen=x['tot'][3], cumplen=x['tot'][2]) for x in m['asp']],
                guia=guia_auto(m, ctx, m['asp']) if m['nat'] else None,
                fortalezas=fortalezas_g(m, ctx, m['asp']), oportunidades=oportunidades_g(m, ctx, m['asp']))
        res['buenas_practicas'] = [dict(b, f=str(b['f'].date())) for b in bp]
        j = out / f'RdP_gestion_{slug}_{fecha:%Y-%m-%d}.json'
        j.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        print(j)


if __name__ == '__main__':
    main()
