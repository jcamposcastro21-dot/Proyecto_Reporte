"""Reglas de calidad RdP: clasificación de acciones, redacción de causas y títulos,
plazos, cierre y recurrencias. Todas las reglas son heurísticas sobre el texto
registrado; las salidas marcan "a validar" donde corresponde."""
import re
import unicodedata
from pathlib import Path
import pandas as pd


def _sin_tilde(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')


def norm(s):
    return ' '.join(str(s).split()).lower() if pd.notna(s) else ''


# ---------- Títulos ----------
TITULOS_NULOS = {'0', 'no', '3h', 'nan', '.', '', '-', 'na', 'n/a'}
TITULOS_CATALOGO = {'otros', 'falla de equipos, componentes, elementos o sistema', 'parada no programada',
                    'cambio de equipos, componentes, elementos o sistema', 'falla motor', 'corte de hoja'}


def calidad_titulo(t):
    """'nulo' | 'catalogo' | 'especifico'"""
    t = norm(t)
    if t in TITULOS_NULOS or len(t) <= 2:
        return 'nulo'
    if t in TITULOS_CATALOGO:
        return 'catalogo'
    return 'especifico'


# ---------- Causas ----------
_TAREA = re.compile(r'^(revisar|corroborar|verificar|evaluar|analizar|realizar|chequear|confirmar|determinar|investigar|cambiar|caracterizacion)\b')
_HIPOTESIS = re.compile(r'\b(posible|posiblemente|probable|probablemente|hipotesis|podria|se cree|sospecha|tbd|por definir|por confirmar|no existe informacion|sin informacion|desconocid)')
_ESTADO = re.compile(r'\b(falta de|desgaste|rotura|roto|falla|fatiga|corrosion|soltura|quebrad|cortad|obstru|tapad|vibracion|mal estado|dano|perdida)')
_DOC = r'(plan|pauta|procedimiento|estandar|estrategia|criterio|logica|frecuencia|limite|instructivo|matriz|control|controles|supervision|coordinacion|capacitacion|parametro|rango)(e?s)?'
_CONTROL = re.compile(r'\b((falta|ausencia|carencia) de (un |una |la |el )?' + _DOC + r'|no (existe|existia|se cuenta|contar|hay|considera|se evaluo|se contaba)|sin ' + _DOC
                      + r'|' + _DOC + r' (deficiente|inadecuad|insuficiente|desactualizad|no definid)|(error|deficiencia) de diseno|(diseno|configuracion) (original )?deficiente)\b')


def calidad_causa(c):
    """'vacia' | 'tarea' | 'hipotesis' | 'estado' | 'control' | 'mecanismo'.
    'control' es la mejor: nombra el control que faltó o falló (playbook: barreras)."""
    s = _sin_tilde(norm(c))
    if not s or s in ('nan', '0', '.'):
        return 'vacia'
    if _TAREA.search(s):
        return 'tarea'
    if _HIPOTESIS.search(s):
        return 'hipotesis'
    if _CONTROL.search(s):
        return 'control'
    if len(s.split()) <= 4 and _ESTADO.search(s):
        return 'estado'
    if len(s.split()) <= 2:
        return 'estado'
    return 'mecanismo'


CAUSA_TXT = {'vacia': 'sin causa', 'tarea': 'causa escrita como tarea', 'hipotesis': 'causa hipotética / no confirmada',
             'estado': 'causa = estado del componente', 'control': 'nombra el control que faltó', 'mecanismo': 'explica el mecanismo'}
CAUSA_DEBIL = {'vacia', 'tarea', 'hipotesis', 'estado'}


# ---------- Acciones S / C / R ----------
_S_FUERTE = re.compile(r'\b(plan (de mantencion|preventivo|matriz)|plan\b(?! de trabajo)|(en |al )?programa (semanal|de mantencion|de parada)|pauta|procedimiento|estandar|instructivo|hte|sop|checklist|logica|interlock|secuencia|diseno|redisen|estrategia|frecuencia|ruta de inspeccion|matriz|hitograma|videoanalitica|preventiv|propot|inspeccion temprana|criterio|limites?|rangos? operacional|parametro en)')
_C = re.compile(r'^(se )?(cambi|reemplaz|repar|ajust|instal|limpi|sold|monta|normaliz|lubric|calibr|regulariz|despresuriz|dosific|disminuir|recuperar|aumenta|mantencion|baipas|reapriete|retir|sacar|coordinar (la )?(llegada|entrega|calibracion)|coordinacion y entrega|busqueda de repuesto|generar ot|validar cambio)')
_R = re.compile(r'^(se )?(revisar|revision|evaluar|evaluacion|analizar|analisis|verificar|monitorear|medir|medicion|coordinar|informar|difundir|comunicar|reunion|realizar reunion|consultar|corroborar|chequear|programar chequeo|inspeccion|inspeccionar|levantar|levantamiento|generar listado|encontrar|determinar|seguimiento|solicitar|generar aviso|crear aviso)\b')
_S = re.compile(r'\b(incorporar|actualizar|estandarizar|crear|definir|emitir|implementar|modificar|establecer|nuevo punto|asegurar|disponer|probar)')


def clasificar_accion(texto):
    """S: cambia plan, estándar, procedimiento, lógica o diseño (barrera permanente).
    C: repara/reemplaza/ajusta (restituye la condición). R: revisa, mide, coordina, informa."""
    s = _sin_tilde(norm(texto))
    if _S_FUERTE.search(s):
        return 'S'
    if _C.search(s):
        return 'C'
    if _R.search(s):
        return 'R'
    if _S.search(s):
        return 'S'
    return 'R'


TIPO_TXT = {'S': 'sistémica / preventiva', 'C': 'correctiva', 'R': 'revisión / difusión'}


def cargar_clasificacion_manual(ruta='config/clasificacion_acciones.csv'):
    p = Path(ruta)
    if not p.exists():
        return {}
    m = pd.read_csv(p)
    return dict(zip(m.AccionId.astype(int), m.tipo))


# ---------- Recurrencias ----------
_STOP = set(_sin_tilde(w) for w in '''de del la el los las en por con sin para a al y o u e un una se que no lado falla fallas
equipo equipos componentes elementos sistema otros parada programada cambio corte linea l1 l2 l3 alta alto bajo baja
mayor menor perdida problema evento ajuste aumento retraso'''.split())


def claves(texto):
    """Tags (palabras con dígitos, p. ej. 431-31-919, M317) y palabras relevantes."""
    s = _sin_tilde(norm(texto))
    tags = set(t for t in re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)*', s) if len(t) >= 3 and re.search(r'\d', t))
    pal = set(w for w in re.findall(r'[a-z]{4,}', s) if w not in _STOP)
    return tags, pal


def antecedentes(evento, historia, dias=365):
    """Eventos previos (misma planta y NAT) que comparten un tag o ≥2 palabras
    relevantes en título + causas. Devuelve lista de (Id, fecha, motivo)."""
    t0, p0 = evento['_tags'], evento['_pal']
    desde = evento['Fecha Inicio'] - pd.Timedelta(days=dias)
    h = historia[(historia.Planta == evento['Planta']) & (historia.NAT == evento['NAT']) &
                 (historia['Fecha Inicio'] < evento['Fecha Inicio']) & (historia['Fecha Inicio'] >= desde) &
                 (historia.Id != evento['Id'])]
    out = []
    for _, h1 in h.iterrows():
        tag = t0 & h1['_tags']
        pal = p0 & h1['_pal']
        if tag or len(pal) >= 2:
            out.append((int(h1.Id), h1['Fecha Inicio'], ', '.join(sorted(tag or pal))[:60]))
    return sorted(out, key=lambda x: x[1], reverse=True)
