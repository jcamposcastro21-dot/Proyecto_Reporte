"""Nivel 3 — Aprendizaje: qué queda de cada RdP y qué puede aprender la organización de ella.

Todo sale de los datos registrados (título, causas, acciones, fechas de cierre y eventos
posteriores). Lo que la base no registra (descripción, evidencia, verificación formal de
eficacia) se informa como limitación, nunca como conclusión.

Conceptos:
- Ejecución: la acción se cerró. No prueba que funcionó.
- Eficacia observable: sin un evento relacionado (mismo NAT, mismo tag o ≥2 palabras clave)
  después del cierre de la acción sistémica. Es un indicio, no una prueba, y solo se lee
  pasados DIAS_EFICACIA días desde el cierre.
- Lectura en el tiempo de cada aspecto: compara los últimos 30 días con los 90 anteriores,
  respetando el tamaño de muestra.
"""
import re
import pandas as pd

from .calidad import claves, norm, _sin_tilde, _EXTENSION, CAUSA_TXT

DIAS_EFICACIA = 60          # días sin repetición, desde el cierre, para leer un indicio de eficacia
VENTANA_RECIENTE = 30       # "últimos 30 días"
VENTANA_ANTERIOR = 90       # período previo con el que se compara (días 31 a 120)
VENTANA_PRACTICAS = 180     # antigüedad máxima de un caso de referencia
N_MIN = 3                   # bajo este número de RdP no se lee tendencia
DEBIL = 50                  # % bajo el cual un aspecto se considera oportunidad

# ---------------------------------------------------------------- aspectos de los tres niveles
# (clave, nivel, texto, base): base 'todas' = todas las RdP; 'acc' = RdP con acciones; 'rec' = RdP con antecedentes
ASPECTOS = [
    ('tit', 1, 'El título dice qué ocurrió (fenómeno; idealmente equipo o tag)', 'todas'),
    ('causa', 2, 'La causa explica el mecanismo o el control que faltó', 'acc'),
    ('sist', 2, 'Al menos una acción cambia plan, estándar, diseño o lógica', 'acc'),
    ('verif', 2, 'Se define cómo verificar que la solución funcionó', 'acc'),
    ('control', 3, 'Llega al control que falló y lo modifica', 'acc'),
    ('extiende', 3, 'Extiende la solución a equipos o líneas similares', 'acc'),
    ('recur', 3, 'Ante un problema repetido, cambia el enfoque respecto de la vez anterior', 'rec'),
]
ASP = {a[0]: a for a in ASPECTOS}

FORTALEZA_TXT = {
    'tit': 'Registran el evento de forma identificable: se puede encontrar y comparar después',
    'causa': 'Sus análisis llegan al mecanismo o al control que faltó, no se quedan en el componente',
    'sist': 'No se quedan en reparar: dejan acciones que cambian plan, estándar o diseño',
    'verif': 'Definen cómo comprobar que la solución funcionó',
    'control': 'Identifican el control que falló y lo corrigen',
    'extiende': 'Extienden lo aprendido a equipos o líneas similares',
    'recur': 'Cuando algo se repite, lo abordan distinto de la vez anterior',
}
OPORTUNIDAD_TXT = {
    'tit': 'Títulos que permitan entender y volver a encontrar el evento',
    'causa': 'Llevar el análisis desde el componente hasta el mecanismo o el control que faltó',
    'sist': 'Pasar de reparar a cambiar la condición que produjo el problema',
    'verif': 'Definir cómo se comprobará que la solución funcionó',
    'control': 'Preguntar qué control o barrera debió evitarlo y actuar sobre él',
    'extiende': 'Revisar si la solución aplica a equipos o líneas similares',
    'recur': 'Cuando el problema se repite, revisar por qué no funcionó lo anterior',
}
ACUERDO_TXT = {
    'tit': 'Registrar cada RdP con fenómeno + equipo o tag en el título (p. ej. «Rotura sprocket rastra 431-31-919»).',
    'causa': 'En cada RdP, que la causa explique por qué ocurrió y qué control debió evitarlo, no el estado del componente.',
    'sist': 'Cada RdP incluye al menos una acción que cambie plan, estándar, diseño o lógica, o justifica por escrito por qué no aplica.',
    'verif': 'Cada acción sistémica indica cómo y cuándo se comprobará que funcionó (criterio medible, 60–90 días).',
    'control': 'Preguntar en cada RdP «¿qué control debió evitarlo?» y dejar una acción sobre ese control.',
    'extiende': 'Al definir una acción sistémica, revisar y registrar si aplica a equipos o líneas similares.',
    'recur': 'Si el problema ya ocurrió antes, abordarlo como un solo análisis (5 porqués o árbol) que parta de por qué no funcionó lo anterior.',
}
PRIORIDAD = ['sist', 'causa', 'recur', 'control', 'verif', 'tit', 'extiende']


def _prefijo(texto, n=4):
    return ' '.join(re.findall(r'[a-z0-9]+', _sin_tilde(norm(texto)))[:n])


def extension_real(acc):
    """Extensión concreta: una acción sistémica que habla de equipos similares, o la misma acción
    sistémica repetida en dos o más equipos (p. ej. «Probar secuencia … X Filter 1/2/3»)."""
    s = acc[acc.tipo == 'S']
    if not len(s):
        return False
    if any(_EXTENSION.search(_sin_tilde(norm(a))) for a in s['Acción']):
        return True
    pref = s['Acción'].map(_prefijo)
    return bool((pref.value_counts() >= 2).any())


def cumple(e, acc, ante):
    """Dict aspecto → True/False/None (None = no aplica a esta RdP)."""
    con = e.nAcc > 0
    rec = None
    if ante:
        rec = bool(e.nS > 0 or any(h in norm(e.Herramienta) for h in ('5 porque', 'árbol', 'ishikawa')))
    return dict(
        tit=bool(e.p_tit >= 2),
        causa=bool(e.p_causa >= 2) if con else None,
        sist=bool(e.nS > 0) if con else None,
        verif=bool(e.verificacion) if con else None,
        control=bool(e.prev_vinculada) if con else None,
        extiende=extension_real(acc) if con else None,
        recur=rec if con else None)


# ---------------------------------------------------------------- recurrencia hacia adelante y eficacia
def posteriores(e, Ep, desde):
    """Eventos relacionados (mismo NAT, tag común o ≥2 palabras clave) con Fecha Inicio > desde."""
    h = Ep[(Ep.NAT == e.NAT) & (Ep.Id != e.Id) & (Ep['Fecha Inicio'] > desde)]
    out = []
    for _, h1 in h.iterrows():
        if (e['_tags'] & h1['_tags']) or len(e['_pal'] & h1['_pal']) >= 2:
            out.append((int(h1.Id), h1['Fecha Inicio']))
    return sorted(out, key=lambda x: x[1])


def eficacia(e, acc, Ep, fecha):
    """Lectura de eficacia de la RdP según sus acciones sistémicas. Devuelve (código, texto, ids_posteriores).
    Códigos: 'sin_s' | 'abierta' | 'pronto' | 'indicio' | 'repite'."""
    s = acc[acc.tipo == 'S']
    if not len(s):
        post = posteriores(e, Ep, e['Fecha Inicio'])
        if post:
            return 'repite', f'Sin acción sistémica y hubo eventos relacionados después: {", ".join(str(i) for i, _ in post[:3])} (confirmar si es el mismo problema)', [i for i, _ in post]
        return 'sin_s', 'Sin acción sistémica: no hay un cambio cuya eficacia evaluar', []
    cerr = s[s.cerr]
    if not len(cerr):
        return 'abierta', 'Acción sistémica aún abierta: ni ejecutada ni evaluable', []
    primer = cerr['Fecha cierre'].min()
    post = posteriores(e, Ep, primer)
    if post:
        i, f = post[0]
        return 'repite', f'Ejecutada, pero hubo un evento relacionado después del cierre ({i}, {f:%d-%m-%Y}; confirmar si es el mismo problema)', [i for i, _ in post]
    dias = int((fecha - primer).days)
    if dias < DIAS_EFICACIA:
        return 'pronto', f'Ejecutada hace {dias} días: aún pronto para leer eficacia (se lee a los {DIAS_EFICACIA})', []
    return 'indicio', f'Ejecutada y sin repetición observada en {dias} días (indicio de eficacia, no prueba)', []


EFICACIA_CHIP = {'sin_s': 'gray', 'abierta': 'gray', 'pronto': 'gray', 'indicio': 'ok', 'repite': 'red'}


def eficacia_accion(r, e, Ep, fecha):
    """Ejecución vs eficacia de una acción. Devuelve (chip, texto)."""
    if not r.cerr:
        return 'gray', 'No ejecutada aún'
    if r.tipo == 'R':
        return 'amb', 'Revisión ejecutada: su eficacia depende de la acción que se decida con el resultado'
    post = posteriores(e, Ep, r['Fecha cierre'])
    if post:
        i, f = post[0]
        return 'red', f'Ejecutada; evento relacionado después del cierre ({i}, {f:%d-%m-%Y}): confirmar si es el mismo problema'
    dias = int((fecha - r['Fecha cierre']).days)
    if dias < DIAS_EFICACIA:
        return 'gray', f'Ejecutada hace {dias} días; eficacia aún no observable'
    return 'ok', f'Ejecutada; sin repetición observada en {dias} días (indicio, no prueba)'


# ---------------------------------------------------------------- nivel 3 por RdP
NIVEL_TXT = {0: 'Sin acciones aún', 1: 'Reparación: no queda un cambio registrado',
             2: 'Aprendizaje local: cambia plan o estándar', 3: 'Aprendizaje transferible'}


def aprendizaje_evento(e, acc, ante, ef):
    """Nivel 0–3 y señales [(chip, texto)] del nivel 3 para una RdP."""
    if e.nAcc == 0:
        return 0, [('gray', 'Sin acciones registradas: el aprendizaje aún no se puede leer')]
    c = cumple(e, acc, ante)
    sen = []
    if c['control']:
        sen.append(('ok', 'Llega al control que falló y deja una acción sobre él'))
    elif c['sist']:
        sen.append(('amb', 'Cambia un plan o estándar, pero la causa no nombra el control que falló'))
    else:
        sen.append(('red', 'Solo repara o revisa: no queda un cambio que evite la repetición'))
    if c['extiende']:
        sen.append(('ok', 'Extiende la solución a equipos o líneas similares'))
    if c['verif']:
        sen.append(('ok', 'Define cómo verificar que funcionó'))
    if ante:
        sen.append(('ok', 'Problema repetido abordado con un enfoque distinto (acción sistémica o análisis estructurado)') if c['recur'] else
                   ('red', 'Problema repetido abordado otra vez solo con reparación'))
    cod, txt, _ = ef
    sen.append((EFICACIA_CHIP[cod], 'Eficacia: ' + txt[0].lower() + txt[1:]))
    if not c['sist']:
        nivel = 1
    elif c['control'] and (c['extiende'] or c['verif'] or cod == 'indicio'):
        nivel = 3
    else:
        nivel = 2
    if cod == 'repite' and nivel > 1:
        sen.append(('red', 'Posible repetición después del cierre: revisar si la acción atacó la causa'))
        nivel = 2 if nivel == 3 else nivel
    return nivel, sen


# ---------------------------------------------------------------- lectura en el tiempo
def serie(evs, aspecto, C):
    """(x, n, ids_cumplen, ids_no) para un conjunto de RdP."""
    v = [(int(i), C[int(i)][aspecto]) for i in evs.Id if C[int(i)][aspecto] is not None]
    si = [i for i, b in v if b]
    no = [i for i, b in v if not b]
    return len(si), len(v), si, no


def lectura(rec, ant, acuerdo=None):
    """Clasifica la evolución de un aspecto. rec/ant = (x, n, ...). Devuelve (código, texto)."""
    xr, nr = rec[:2]
    xa, na = ant[:2]
    pr = 100 * xr / nr if nr else None
    pa = 100 * xa / na if na else None
    if acuerdo:
        if nr >= N_MIN and pa is not None and pr - pa >= 20:
            return 'trabajada', f'trabajada desde el {acuerdo:%d-%m}: mejora'
        return 'trabajada', f'en seguimiento desde el {acuerdo:%d-%m}'
    if nr < N_MIN and na < N_MIN:
        return 'insuf', 'muestra insuficiente'
    if nr < N_MIN:
        return ('antes_ok' if pa >= DEBIL else 'antes_debil'), 'sin casos recientes suficientes'
    if na < N_MIN:
        return ('ok' if pr >= DEBIL else 'debil'), 'sin historia para comparar'
    d = pr - pa
    if pr < DEBIL and pa < DEBIL:
        return ('mejora', 'mejora, aún bajo') if d >= 25 else ('persistente', 'debilidad persistente')
    if pr >= DEBIL and pa >= DEBIL:
        return 'sostenida', 'fortaleza sostenida'
    if d > 0:
        return 'mejora', 'mejora'
    return ('deterioro', 'deterioro') if nr - xr >= 3 else ('puntual', 'situación puntual')


LECTURA_CHIP = {'insuf': 'gray', 'antes_ok': 'gray', 'antes_debil': 'gray', 'ok': 'ok', 'debil': 'amb', 'persistente': 'red',
                'mejora': 'ok', 'sostenida': 'ok', 'deterioro': 'red', 'puntual': 'amb', 'trabajada': 'az'}


def es_debil(cod, rec, ant):
    if cod in ('persistente', 'deterioro', 'debil'):
        return True
    if cod == 'puntual':
        return False
    xr, nr = rec[:2]
    return cod == 'mejora' and nr and 100 * xr / nr < DEBIL


def es_fuerte(cod, rec):
    xr, nr = rec[:2]
    return cod in ('sostenida', 'ok') or (cod == 'mejora' and nr and 100 * xr / nr >= DEBIL)


# ---------------------------------------------------------------- cadenas de recurrencia
def cadena(ids, E, A, fecha):
    """Qué ocurrió entre una RdP y la siguiente. Devuelve dict(filas, lectura, pregunta, aprendizaje)."""
    evs = E[E.Id.isin(ids)].sort_values('Fecha Inicio')
    filas, lect = [], []
    s_cerrada_y_volvio = abierta_al_volver = 0
    hubo_S = False
    lista = list(evs.itertuples(index=False))
    cols = list(evs.columns)
    for k, e in enumerate(lista):
        e = pd.Series(e, index=cols)
        acc = A[A.RegistroId == e.Id]
        mejor = acc.sort_values('causa', key=lambda s: s.map({'control': 0, 'mecanismo': 1}).fillna(2))
        causa = str(mejor['Causa raíz'].iloc[0]) if len(mejor) and pd.notna(mejor['Causa raíz'].iloc[0]) else ''
        cq = CAUSA_TXT[mejor.causa.iloc[0]] if len(mejor) else 'sin acciones'
        sist = acc[acc.tipo == 'S']
        hubo_S = hubo_S or len(sist) > 0
        hizo = (f'{len(sist)} sistémica(s): «{str(sist["Acción"].iloc[0])[:90]}»' if len(sist) else
                f'{int(e.nC)} correctiva(s), {int(e.nR)} de revisión; ninguna sistémica') if len(acc) else 'sin acciones registradas'
        if k + 1 < len(lista):
            sig = pd.Series(lista[k + 1], index=cols)
            f2 = sig['Fecha Inicio']
            cerr_antes = acc[acc['Fecha cierre'].notna() & (acc['Fecha cierre'] <= f2)]
            s_antes = cerr_antes[cerr_antes.tipo == 'S']
            dias = int((f2 - e['Fecha Inicio']).days)
            if len(s_antes):
                s_cerrada_y_volvio += 1
                tras = f'Volvió {dias} días después, con {len(s_antes)} acción(es) sistémica(s) ya cerrada(s)'
                chip = 'red'
            elif len(acc) and len(cerr_antes) < len(acc):
                abierta_al_volver += 1
                tras = f'Volvió {dias} días después, con {len(acc) - len(cerr_antes)} de {len(acc)} acciones aún abiertas'
                chip = 'amb'
            else:
                tras = f'Volvió {dias} días después; lo hecho no incluía un cambio de control'
                chip = 'amb'
        else:
            cerr = acc[acc.cerr]
            ef = eficacia(e, acc, E[E.Planta == e.Planta], fecha)
            tras = f'Hoy: {len(cerr)} de {len(acc)} acciones cerradas. {ef[1]}'
            chip = EFICACIA_CHIP[ef[0]]
        filas.append(dict(id=int(e.Id), f=e['Fecha Inicio'], tit=e['Evento tiempo perdido'], causa=causa, cq=cq, hizo=hizo, tras=tras, chip=chip))
    if s_cerrada_y_volvio:
        lect = 'Se cerraron acciones sistémicas y el problema volvió: lo que se cambió no atacó la causa o no alcanzó.'
        preg = '¿Qué cambiamos la vez anterior y por qué no bastó? ¿Atacamos la causa o el síntoma?'
    elif abierta_al_volver:
        lect = 'El problema volvió antes de que se ejecutaran las acciones: faltó un control interino mientras tanto.'
        preg = '¿Qué control provisorio evita que se repita mientras se ejecuta la solución de fondo?'
    elif not hubo_S:
        lect = 'Ninguna RdP de la cadena cambió un control: se repara y se repite.'
        preg = '¿Qué barrera falta para que esto no vuelva a ocurrir? ¿Quién es el dueño del modo de falla?'
    else:
        lect = 'La última RdP sí cambia un control; falta confirmar que se sostiene.'
        preg = '¿Cómo y cuándo vamos a comprobar que no se repite? ¿Aplica a equipos similares?'
    queda = A[A.RegistroId.isin(ids) & (A.tipo == 'S') & (A.causa == 'control')]
    apr = ('Queda registrado un cambio sobre el control: ' + '; '.join(f'«{str(x)[:80]}» ({int(r)})' for x, r in zip(queda['Acción'][:2], queda.RegistroId[:2]))
           if len(queda) else 'No queda registrado un cambio sobre el control que falló.')
    return dict(filas=filas, lectura=lect, pregunta=preg, aprendizaje=apr)


# ---------------------------------------------------------------- buenas prácticas
def buenas_practicas(Ep, Ap, ANTE, EF, fecha, validadas=None, en_seguimiento=()):
    """Casos de referencia detectados por reglas en los últimos VENTANA_PRACTICAS días.
    Requiere al menos una acción sistémica y alguna señal concreta de aprendizaje.
    Se excluyen los casos donde el problema volvió después del cierre."""
    validadas = validadas or {}
    desde = fecha - pd.Timedelta(days=VENTANA_PRACTICAS)
    out = []
    for _, e in Ep[(Ep['Fecha Inicio'] >= desde) & (Ep.nS > 0)].iterrows():
        i = int(e.Id)
        acc = Ap[Ap.RegistroId == i]
        val = validadas.get(str(i), {})
        if val.get('estado') == 'descartada' or EF[i][0] == 'repite' or (i in en_seguimiento and not val):
            continue
        c = cumple(e, acc, ANTE.get(i))
        que, por, score = [], [], 0
        ctrl = acc[(acc.causa == 'control') & (acc.tipo == 'S')]
        if len(ctrl):
            r = ctrl.iloc[0]
            que.append(f'Identificó «{str(r["Causa raíz"])[:90]}» y actuó sobre ello: «{str(r["Acción"])[:110]}»')
            por.append('llegó al control que falló y lo modificó')
            score += 3
        if c['extiende']:
            s = acc[(acc.tipo == 'S') & ~acc.AccionId.isin(ctrl.AccionId[:1])] if len(ctrl) else acc[acc.tipo == 'S']
            s = s if len(s) else acc[acc.tipo == 'S']
            pref = s['Acción'].map(_prefijo)
            rep = pref.value_counts()
            if (rep >= 2).any():
                n = int(rep.max())
                que.append(f'Aplicó la misma solución en {n} equipos: «{str(s[pref == rep.idxmax()]["Acción"].iloc[0])[:90]}»…')
            else:
                x = s[s['Acción'].map(lambda a: bool(_EXTENSION.search(_sin_tilde(norm(a)))))]
                que.append(f'Extendió la solución: «{str(x["Acción"].iloc[0])[:110]}»' if len(x) else 'Extendió la solución a equipos similares')
            por.append('no se quedó en el equipo que falló')
            score += 2 + (1 if e.p_causa >= 2 else 0)
        if c['verif']:
            por.append('dejó definido cómo verificar que funcionó')
            score += 1
        if c['recur']:
            por.append('ante un problema repetido, cambió el enfoque')
            score += 2
        if EF[i][0] == 'indicio':
            por.append(f'y no se ha repetido desde el cierre ({EF[i][1].split("en ")[-1].split(" (")[0]})')
            score += 1
        if score < 3 and not val:
            continue
        if not que:
            s = acc[acc.tipo == 'S'].iloc[0]
            que.append(f'«{str(s["Acción"])[:120]}»')
        out.append(dict(id=i, nat=e.NAT, f=e['Fecha Inicio'], tit=e['Evento tiempo perdido'], que=que, por=por, score=score,
                        donde=donde_replicar(e, acc, Ep, Ap, fecha), estado=val.get('estado', 'candidata'), nota=val.get('nota', '')))
    return sorted(out, key=lambda x: (-x['score'], -x['f'].value))


GENERICAS = set(_sin_tilde(w) for w in """estrategia mantencion procedimiento procedimientos estandar estandares falta ausencia plan planes control
controles definir definida generar revisar existe existia formal calidad trabajo trabajos equipo inspeccion operacional operacionales
asegurar riesgo riesgos supervision comunicacion deficiente inadecuado insuficiente diseno configuracion original preventiva
preventivo programa planta area areas personal operador operadores tiempo correcto correcta adecuado adecuada""".split())


def _tema(e):
    return e['_tags'], e['_pal'] - GENERICAS


def donde_replicar(e, acc, Ep, Ap, fecha):
    """Otros NAT de la planta con RdP de tema parecido (tag o ≥2 palabras clave) o con el mismo tipo de
    causa raíz, que no tienen acción sistémica. Es una sugerencia para validar, no una conclusión."""
    desde = fecha - pd.Timedelta(days=365)
    otros = Ep[(Ep.NAT != e.NAT) & (Ep['Fecha Inicio'] >= desde) & (Ep.nAcc > 0)]
    s = acc[acc.tipo == 'S']
    kt, kp = _tema(e)
    tema = []
    for _, o in otros.iterrows():
        ot, op = _tema(o)
        comun = (kt & ot) or (kp & op if len(kp & op) >= 2 else set())
        if comun:
            tema.append((int(o.Id), o.NAT, ', '.join(sorted(comun)[:3])))
    if tema:
        return 'Tema parecido en ' + '; '.join(f'{n}: {i} ({k})' for i, n, k in tema[:3])
    tipos = set(s['Tipo causa raíz'].dropna().mode()[:1])
    sinS = otros[otros.nS == 0]
    m = Ap[Ap.RegistroId.isin(sinS.Id) & Ap['Tipo causa raíz'].isin(tipos)].drop_duplicates('RegistroId')
    if len(m):
        por_nat = m.groupby('NAT').RegistroId.apply(list)
        tipo = ', '.join(sorted(tipos))
        return (f'Misma familia de causa ({tipo}) sin acción sistémica en '
                + '; '.join(f'{n}: {", ".join(str(int(x)) for x in ids[:2])}' for n, ids in por_nat.head(3).items()))
    return 'Sin un caso parecido evidente en otros NAT: compartir como referencia general'
