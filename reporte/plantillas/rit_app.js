'use strict';
/* =====================================================================================================
   REPORTE RIT — lógica de cálculo y presentación (solo consulta; no modifica datos de origen).

   DEFINICIONES DE KPI (todas se muestran como % + numerador/denominador; nunca se combinan en un puntaje único):
   NIVEL 1 · ADHERENCIA = días con RIT realizado en día exigido / días exigidos, por equipo y semana.
       Exigidos: Mantención = días hábiles; Operación = días D o N del turno según la rotación (DC y AD no se exigen).
       Tope por equipo-semana (realizados ≤ exigidos). Se evalúa desde la semana de inicio general (M.inicio).
       Solo se calcula con filtros de equipo (especialidad, área, equipo, turno): no existe adherencia por persona,
       tarea o tipo de hallazgo, porque el RIT se exige al equipo/turno.
   NIVEL 2 · TRAZABILIDAD = RIT con cuenta individual / RIT. Compartida = cuenta genérica de turno o puesto.
             EJECUCIÓN: componentes separados (tarea SE seleccionada, formulario completo, registro oportuno ≤12 h);
             "registro completo" = los tres a la vez. "Tarea correcta" no es verificable con los datos actuales.
   NIVEL 3 · REDACCIÓN (evaluación automática 0–3, por reglas de texto; NO es calidad técnica):
             entendibles = nota ≥2 / hallazgos; claros y accionables = nota 3 / hallazgos. Un RIT con varios
             hallazgos toma la nota más baja. Las listas copiadas valen 0 y se informan aparte.
             Un RIT sin hallazgo NO es un mal RIT: se informa en gris, sin meta.
   NIVEL 4 · PERTINENCIA TÉCNICA: pendiente de validación salvo registros en config/validacion_tecnica.csv.
   NIVEL 5 · EFECTIVIDAD: estado de la mejora en la lista (Abierta/Cerrada/No Aplica) y tareas con hallazgos
             repetidos. Aceptado/rechazado/corregido: no disponible con los datos actuales.
   Comparaciones: contra las 4 semanas completas anteriores al período (no se compara contra una sola semana).
   Muestra reducida: denominador < M.muestra.
   ===================================================================================================== */
const M = D.meta, SEM = {}, ORD = D.semanas.map(s => s.n);
D.semanas.forEach(s => { SEM[s.n] = s; });
const EQ = {}; D.equipos.forEach(e => { EQ[e.k] = e; });
const REG = D.regs; const BYID = {};
REG.forEach(r => { r.e = EQ[r.k]; BYID[r.id] = r; });
const DI = {};  // DI[equipo][semana] = días distintos con RIT que cuentan para adherencia
REG.forEach(r => { if (!r.en) return; DI[r.k] = DI[r.k] || {}; (DI[r.k][r.s] = DI[r.k][r.s] || new Set()).add(r.dia); });
const F = { sem: M.defecto, per: 'sem', esp: '', area: '', eq: '', turno: '', per2: '', tarea: '', hall: '', red: '', est: '', cta: '' };
const RED = M.redaccion, ABIERTOS = new Set();
let PAG = 0;

// ---------------------------------------------------------------- utilidades
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = (n, N) => N ? Math.round(100 * n / N) : null;
const f1 = x => (Math.round(x * 10) / 10).toString().replace('.', ',');
const nn = x => Number.isInteger(x) ? x : f1(x);
const fd = s => s.split('-').reverse().slice(0, 2).join('-');
const semTxt = n => `S${n} (${fd(SEM[n].lun)} a ${fd(SEM[n].dom)})`;
const mr = N => N < M.muestra ? `<span class="mr" title="Menos de ${M.muestra} observaciones: leer con cautela">muestra reducida</span>` : '';
const chip = (c, t, title) => `<span class="chip ${c}"${title ? ` title="${esc(title)}"` : ''}>${esc(t)}</span>`;
const ctaTxt = { ind: 'cuenta individual', comp: 'cuenta compartida', sinid: 'sin identificación' };
const RCOL = { 3: 'ok', 2: 'ok', 1: 'amb', 0: 'red' };
function pv(n, N, opts = {}) {  // "82% — 41/50" + muestra reducida
  const p = pct(n, N);
  return p === null ? `<span class="est-na">s/d</span> <small>0/0</small>` : `<b>${p}%</b> <small>${nn(n)}/${nn(N)}</small>${opts.mr === false ? '' : mr(N)}`;
}
function estado(p, meta, ref) {   // texto + ícono: el color nunca comunica solo
  if (p === null || meta == null) return '';
  const lbl = ref ? `la referencia de ${meta}%` : `la meta de ${meta}%`;
  return p >= meta ? `<span class="est-ok">✓ Cumple ${lbl}</span>` : `<span class="${p < meta - 15 ? 'est-red' : 'est-amb'}">⚠ Bajo ${lbl}</span>`;
}
function delta(p, prev, inv) {
  if (p === null || prev === null || prev === undefined) return '<span class="flat">Sin base de comparación</span>';
  const d = p - prev; if (Math.abs(d) < 1) return `<span class="flat">→ igual que las 4 semanas anteriores (${prev}%)</span>`;
  const bueno = inv ? d < 0 : d > 0;
  return `<span class="${bueno ? 'up' : 'down'}">${d > 0 ? '↑' : '↓'} ${Math.abs(d)} pp vs. 4 semanas anteriores (${prev}%)</span>`;
}

// ---------------------------------------------------------------- períodos
function hasta(n, k, completas) { const i = ORD.indexOf(n), out = []; for (let j = i; j >= 0 && out.length < k; j--) { const s = SEM[ORD[j]]; if (completas && s.parcial) continue; out.unshift(s.n); } return out; }
const periodo = () => F.per === 'sem' ? [F.sem] : hasta(F.sem, 4, false);
function previas(per) { const i = ORD.indexOf(per[0]), out = []; for (let j = i - 1; j >= 0 && out.length < 4; j--) { const s = SEM[ORD[j]]; if (s.parcial || s.piloto) continue; out.unshift(s.n); } return out; }
const ventana4 = () => hasta(F.sem, 4, false).filter(s => !SEM[s].piloto);
const tend4 = () => hasta(F.sem, 4, true).filter(s => !SEM[s].piloto);
const rango = ws => ws.length ? (ws.length === 1 ? semTxt(ws[0]) : `S${ws[0]}–S${ws[ws.length - 1]} (${fd(SEM[ws[0]].lun)} a ${fd(SEM[ws[ws.length - 1]].dom)})`) : '—';

// ---------------------------------------------------------------- filtros
const eqMatch = e => (!F.esp || e.esp === F.esp) && (!F.area || e.area === F.area) && (F.eq === '' || e.k == F.eq) && (!F.turno || e.tl === F.turno);
const noAdh = () => !!(F.per2 || F.tarea || F.hall || F.red || F.est || F.cta);
function regMatch(r, ign = {}) {
  if (!eqMatch(r.e)) return false;
  if (!ign.per2 && F.per2 && r.per !== F.per2) return false;
  if (F.tarea && !r.tarea.toLowerCase().includes(F.tarea.toLowerCase())) return false;
  if (!ign.hall && F.hall === 'con' && !r.h) return false;
  if (!ign.hall && F.hall === 'sin' && r.h) return false;
  if (!ign.red && F.red === 'lista' && !r.lista) return false;
  if (!ign.red && F.red !== '' && F.red !== 'lista' && (!r.h || r.n !== +F.red)) return false;
  if (F.est && r.est !== F.est) return false;
  if (!ign.cta && F.cta && r.cta !== F.cta) return false;
  return true;
}
function regs(ws, ign) { const W = new Set(ws); return REG.filter(r => W.has(r.s) && regMatch(r, ign)); }

// ---------------------------------------------------------------- cálculos
function adherencia(ws, filtroEq) {
  if (noAdh()) return { na: 'La adherencia se mide por equipo: no aplica con filtros de persona, tarea, hallazgo, redacción, estado o cuenta.' };
  const v = ws.filter(s => !SEM[s].piloto);
  if (!v.length) return { na: `Etapa piloto (antes de S${M.inicio}): la adherencia no se evalúa.` };
  let n = 0, N = 0; const por = {};
  D.equipos.forEach(e => {
    if (!e.valido || !(filtroEq ? filtroEq(e) : eqMatch(e))) return;
    const t = D.esp[e.k] || {}; let a = 0, b = 0; const sem = {};
    v.forEach(s => { const x = t[s] || 0, h = Math.min(DI[e.k] && DI[e.k][s] ? DI[e.k][s].size : 0, x); a += h; b += x; sem[s] = { n: h, N: x }; });
    por[e.k] = { n: a, N: b, sem }; n += a; N += b;
  });
  return { n, N, p: pct(n, N), por };
}
function calc(R) {
  const k = { N: R.length, ind: 0, comp: 0, sinid: 0, tse: 0, cmp: 0, op: 0, todo: 0, fuera: 0, mal: 0, con: 0, sin: 0, d: [0, 0, 0, 0], lista: 0, valid: 0, est: {} };
  R.forEach(r => {
    k[r.cta]++; if (r.tse) k.tse++; if (r.cmp) k.cmp++; if (r.op) k.op++; if (r.tse && r.cmp && r.op) k.todo++; if (r.fuera) k.fuera++; if (r.mal) k.mal++;
    if (r.h) { k.con++; k.d[r.n]++; if (r.lista) k.lista++; if (D.valid[r.id]) k.valid++; const e = r.est || '(sin estado)'; k.est[e] = (k.est[e] || 0) + 1; } else k.sin++;
  });
  k.ent = k.d[2] + k.d[3]; k.acc = k.d[3]; k.prom = k.con ? (k.d[1] + 2 * k.d[2] + 3 * k.d[3]) / k.con : null;
  return k;
}
function grupos(R, nivel) {  // agrupa registros por especialidad / área / equipo
  const g = {}; R.forEach(r => { const key = nivel === 0 ? r.e.esp : nivel === 1 ? r.e.esp + '|' + r.e.area : String(r.k); (g[key] = g[key] || []).push(r); }); return g;
}
function arbol() {   // especialidad → área → equipos (solo equipos que coinciden con los filtros de equipo)
  const t = {};
  D.equipos.filter(eqMatch).forEach(e => { t[e.esp] = t[e.esp] || {}; (t[e.esp][e.area] = t[e.esp][e.area] || []).push(e); });
  return t;
}
function faltantes(items) { // qué elemento falta más en los hallazgos que no llegan a 3
  const nom = ['acción', 'elemento (riesgo/control/documento)', 'identificación exacta', 'tarea/contexto', 'justificación'], c = [0, 0, 0, 0, 0]; let n = 0;
  items.forEach(i => { if (i.n === 3 || i.n === 0) return; n++; i.el.forEach((v, j) => { if (!v && (j !== 4 || i.jr)) c[j]++; }); });  // justificación: solo si se exige
  return { n, top: c.map((v, j) => [nom[j], v]).filter(x => x[1]).sort((a, b) => b[1] - a[1]) };
}

// ---------------------------------------------------------------- render principal
function render() {
  const per = periodo(), prev = previas(per), R = regs(per), Rp = regs(prev), K = calc(R), Kp = calc(Rp);
  const AD = adherencia(per), ADp = adherencia(prev);
  const ctx = { per, prev, R, K, Kp, AD, ADp };
  $('contexto').innerHTML = `<b>Período evaluado:</b> ${rango(per)}${per.some(s => SEM[s].parcial) ? ' <span class="mr">semana parcial: datos hasta ' + fd(M.corte) + '</span>' : ''}${per.some(s => SEM[s].piloto) ? ' <span class="mr">etapa piloto</span>' : ''}
   · <b>Comparación:</b> ${prev.length ? rango(prev) : 'sin semanas anteriores evaluables'} · <b>${K.N}</b> RIT con los filtros activos.`;
  chipsFiltro();
  resumen(ctx); diagnostico(ctx); tendencia(); nivel1(ctx); nivel2(ctx); nivel3(ctx); nivel45(ctx); categorias(); personas(); registros(ctx); historico(); definiciones();
  enlazar(document);
}

// ---------------------------------------------------------------- 1. resumen ejecutivo
function kcard(o) {
  const cls = o.cls || (o.p === null || o.meta == null ? 'k-az' : o.p >= o.meta ? 'k-ok' : o.p < o.meta - 15 ? 'k-red' : 'k-amb');
  return `<div class="card kg ${cls}"><div class="kq">${o.q}</div><div class="kt">${o.t}</div>
   ${o.na ? `<div class="na-box">${o.na}</div>` : `<div class="kv">${o.txtV || (o.p === null ? 's/d' : o.p + '%')}<small>${o.nN || ''}</small>${o.N !== undefined ? mr(o.N) : ''}</div>
   <div class="kn">${o.sub || ''}</div><div class="kd">${o.delta || ''}</div><div class="ke">${o.est || ''}</div>`}
   ${o.lista ? '<ul>' + o.lista.map(x => `<li><span>${x[0]}</span><span>${x[1]}</span></li>`).join('') + '</ul>' : ''}${o.extra || ''}</div>`;
}
function resumen({ K, Kp, AD, ADp, per, R }) {
  const m = M.metas, com = (D.comentarios['S' + F.sem] || {}).Planta;
  const pAdP = ADp && !ADp.na ? ADp.p : null;
  const distBar = K.con ? `<div class="dist">${[3, 2, 1, 0].map(n => K.d[n] ? `<i class="r${n}" style="width:${100 * K.d[n] / K.con}%" title="${n} · ${RED[n]}: ${K.d[n]}"></i>` : '').join('')}</div>
    <div class="leg">${[3, 2, 1, 0].map(n => `<span><i class="r${n}"></i>${n}: ${K.d[n]}</span>`).join('')}</div>` : '';
  const cards = [
    kcard({ q: 'Nivel 1 · Adherencia', t: '¿Se realiza el RIT cuando corresponde?', na: AD.na, p: AD.p, N: AD.N, nN: AD.na ? '' : `${nn(AD.n)} / ${nn(AD.N)}`,
      sub: 'RIT realizados / RIT esperados (días exigidos)', delta: delta(AD.p, pAdP), est: estado(AD.p, m.adherencia) }),
    kcard({ q: 'Nivel 2 · Trazabilidad', t: '¿Se sabe quién hizo el RIT?', p: pct(K.ind, K.N), N: K.N, nN: `${K.ind} / ${K.N} RIT`, sub: 'con cuenta individual',
      delta: delta(pct(K.ind, K.N), pct(Kp.ind, Kp.N)), est: estado(pct(K.ind, K.N), m.trazabilidad, true),
      lista: [['Cuenta individual', K.ind], ['Cuenta compartida (no atribuible)', K.comp], ['Sin identificación', K.sinid]] }),
    kcard({ q: 'Nivel 2 · Ejecución', t: '¿Quedó bien registrado?', p: pct(K.todo, K.N), N: K.N, nN: `${K.todo} / ${K.N} RIT`, sub: 'registro completo: tarea SE + formulario + oportuno',
      delta: delta(pct(K.todo, K.N), pct(Kp.todo, Kp.N)), est: estado(pct(K.todo, K.N), m.ejecucion, true),
      lista: [['Tarea SoftExpert seleccionada', `${K.tse}/${K.N}`], ['Formulario completo', `${K.cmp}/${K.N}`], ['Registrado ≤12 h', `${K.op}/${K.N}`],
        ['En día de descanso del turno', K.fuera], ['Equipo mal registrado', K.mal], ['Tarea correcta para el área', 'no disponible']] }),
    kcard({ q: 'Nivel 3 · Redacción (evaluación automática)', t: '¿El hallazgo se entiende?', p: pct(K.acc, K.con), N: K.con, nN: `${K.acc} / ${K.con} hallazgos`,
      sub: 'claros y accionables (3/3)', delta: delta(pct(K.acc, K.con), pct(Kp.acc, Kp.con)), est: estado(pct(K.acc, K.con), m.redaccion_accionable, true),
      lista: [['RIT con hallazgo', `${K.con} de ${K.N}`], ['RIT sin hallazgo (no es falta)', K.sin], ['Entendibles (≥2)', `${K.ent}/${K.con}`],
        ['Redacción promedio', K.prom === null ? 's/d' : f1(K.prom) + ' / 3'], ['Listas copiadas (cuentan como 0)', K.lista]], extra: distBar }),
    kcard({ q: 'Nivel 4 · Pertinencia técnica', t: '¿Lo propuesto corresponde?', cls: 'k-az', p: K.valid ? pct(K.valid, K.con) : null, N: K.valid ? K.con : undefined,
      nN: `${K.valid} / ${K.con} validados`, txtV: K.valid ? null : 'Pendiente',
      sub: K.valid ? 'hallazgos con validación técnica registrada' : 'Pendiente de validación técnica: ningún hallazgo del período tiene validación registrada.', delta: '', est: '<span class="est-na">Una redacción clara no garantiza que el hallazgo sea técnicamente correcto.</span>' }),
    kcard({ q: 'Nivel 5 · Efectividad', t: '¿Mejoró SoftExpert?', cls: 'k-az', p: null, N: undefined, nN: '', txtV: 'Parcial', sub: 'Solo se dispone del estado de la mejora en la lista (hallazgos del período):',
      lista: Object.entries(K.est).sort((a, b) => b[1] - a[1]).map(([k, v]) => [esc(k), `${v} (${pct(v, K.con)}%)`]).concat([['Aceptado / rechazado / corregido', 'no disponible']]),
      est: '<span class="est-na">"Cerrada" en la lista no verifica que el cambio esté implementado ni que sea eficaz.</span>' }),
  ];
  $('s-resumen').innerHTML = `<div class="section-title">📌 Resumen ejecutivo — ${rango(per)}</div>
   ${com && com.lectura ? `<div class="card logro" style="margin-bottom:12px">${com.lectura}</div>` : ''}<div class="kpis">${cards.join('')}</div>
   <div class="sm" style="margin-top:6px">Cada indicador muestra dato, n/N, comparación con las 4 semanas completas anteriores y estado frente a la meta (adherencia) o a la referencia de trabajo (resto). No existe un puntaje único: cada nivel se lee por separado.</div>`;
}

// ---------------------------------------------------------------- 2. diagnóstico para la reunión
function diagnostico({ AD, K, R, per }) {
  const m = M.metas, out = [], com = (D.comentarios['S' + F.sem] || {}).Planta;
  const nomEq = k => `${EQ[k].area} · ${EQ[k].eq}`;
  if (!AD.na && AD.p !== null && AD.p < m.adherencia) {
    const faltan = Object.entries(AD.por).map(([k, v]) => [k, v.N - v.n, v]).filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]);
    out.push({ c: 'red', t: `Adherencia ${AD.p}% (${nn(AD.n)}/${nn(AD.N)}), bajo la meta de ${m.adherencia}%`,
      donde: faltan.slice(0, 4).map(x => `<span class="clic" data-eq="${x[0]}"><b>${esc(nomEq(x[0]))}</b> ${nn(x[2].n)}/${nn(x[2].N)}</span>`).join(' · ') || '—',
      ev: `${nn(AD.N - AD.n)} RIT exigidos sin registro en el período, en ${faltan.length} equipos.`,
      causa: 'Posible causa / requiere revisión: RIT no realizado, o realizado y no registrado en SoftExpert.',
      acc: 'Revisar con el jefe de turno o de especialidad los días faltantes de esos equipos y confirmar quién registra el RIT cuando el líder no está.' });
  }
  if (K.comp > 0) {
    const cu = {}; R.filter(r => r.cta === 'comp').forEach(r => { cu[r.per] = cu[r.per] || { n: 0, a: new Set() }; cu[r.per].n++; cu[r.per].a.add(r.e.area + ' ' + r.e.eq); });
    out.push({ c: 'red', t: `Problema de trazabilidad: ${K.comp} RIT (${pct(K.comp, K.N)}%) registrados con cuentas compartidas`,
      donde: Object.entries(cu).sort((a, b) => b[1].n - a[1].n).slice(0, 4).map(([p, v]) => `<span class="clic" data-per="${esc(p)}"><b>${esc(p)}</b> ${v.n} RIT</span>`).join(' · '),
      ev: `No es posible atribuir individualmente la calidad de estos ${K.comp} registros; tampoco se evalúa a una persona por ellos.`,
      causa: 'Uso de la cuenta genérica del turno o del puesto (correos ce05.*).',
      acc: 'Que cada integrante registre con su cuenta personal; si la cuenta genérica es la única con acceso, gestionar el acceso individual.' });
  }
  const H = R.filter(r => r.h), items = H.flatMap(r => r.it.map(i => Object.assign({ r }, i)));
  if (K.con >= 3 && pct(K.ent, K.con) < M.categorias.calidad_alta) {
    const g = grupos(H, 2), peor = Object.entries(g).map(([k, rs]) => [k, rs.filter(r => r.n <= 1).length, rs.length]).filter(x => x[1]).sort((a, b) => b[1] - a[1]);
    const fal = faltantes(items), ej = H.filter(r => r.n <= 1 && !r.lista && r.it[0].x.trim()).slice(-2);
    out.push({ c: '', t: `Hallazgos poco entendibles: ${K.con - K.ent} de ${K.con} (${100 - pct(K.ent, K.con)}%) son genéricos o no utilizables`,
      donde: peor.slice(0, 4).map(x => `<span class="clic" data-eq="${x[0]}"><b>${esc(nomEq(x[0]))}</b> ${x[1]}/${x[2]}</span>`).join(' · '),
      ev: (fal.top.length ? `En los hallazgos con redacción 1–2, lo que más falta: <b>${fal.top[0][0]}</b> (${fal.top[0][1]} de ${fal.n})` + (fal.top[1] ? `, luego ${fal.top[1][0]} (${fal.top[1][1]})` : '') + '. ' : '') +
        ej.map(r => `<span class="clic" data-reg="${r.id}">«${esc(r.it[0].x.slice(0, 70))}»</span>`).join(' · '),
      causa: 'Posible causa / requiere revisión: el registro nombra el tema (p. ej. "riesgos SSO") pero no el elemento exacto de SoftExpert ni la acción.',
      acc: 'Reforzar en el RIT el formato [ACCIÓN] + [ELEMENTO EXACTO] + [TAREA] + [POR QUÉ], usando los ejemplos reales de la sección 3.' });
  }
  if (K.lista > 0) out.push({ c: 'info', t: `${K.lista} hallazgos son listas copiadas de SoftExpert`, donde: Object.entries(grupos(H.filter(r => r.lista), 2)).sort((a, b) => b[1].length - a[1].length).slice(0, 4).map(([k, v]) => `<span class="clic" data-eq="${k}"><b>${esc(nomEq(k))}</b> ${v.length}</span>`).join(' · '),
    ev: 'Copian los riesgos o controles de la tarea sin indicar cuál agregar, eliminar o modificar; se cuentan como redacción 0 y no como hallazgo de calidad.',
    causa: 'Posible causa / requiere revisión: se pega el contenido de la tarea para "dejar constancia".', acc: 'Pedir que se elija el elemento concreto de la lista y se diga qué hacer con él.' });
  if (K.N >= 5 && pct(K.todo, K.N) < M.metas.ejecucion) {
    const g = grupos(R, 2), peor = Object.entries(g).map(([k, rs]) => [k, rs.filter(r => !(r.tse && r.cmp && r.op)).length, rs.length]).filter(x => x[1]).sort((a, b) => b[1] - a[1]);
    out.push({ c: '', t: `Registro incompleto o tardío en ${K.N - K.todo} de ${K.N} RIT (${100 - pct(K.todo, K.N)}%)`,
      donde: peor.slice(0, 4).map(x => `<span class="clic" data-eq="${x[0]}"><b>${esc(nomEq(x[0]))}</b> ${x[1]}/${x[2]}</span>`).join(' · '),
      ev: `Sin tarea SE: ${K.N - K.tse} · formulario incompleto: ${K.N - K.cmp} · registrado después de 12 h: ${K.N - K.op}.`,
      causa: 'Posible causa / requiere revisión.', acc: 'Revisar en terreno que el registro se haga durante el RIT y seleccionando la tarea revisada.' });
  }
  const w4 = ventana4();
  if (!noAdh() && w4.length) {
    const R4 = regs(w4), g = grupos(R4, 2), sinh = Object.entries(g).filter(([k, rs]) => rs.length >= 4 && !rs.some(r => r.h));
    if (sinh.length) out.push({ c: 'info', t: `${sinh.length} equipos realizaron RIT sin registrar hallazgos en 4 semanas`,
      donde: sinh.slice(0, 6).map(([k, rs]) => `<span class="clic" data-eq="${k}"><b>${esc(nomEq(k))}</b> ${rs.length} RIT</span>`).join(' · '),
      ev: sinh.slice(0, 3).map(([k, rs]) => `${esc(nomEq(k))}: ${new Set(rs.map(r => r.tarea)).size} tareas distintas revisadas, tarea SE ${pct(rs.filter(r => r.tse).length, rs.length)}%`).join(' · '),
      causa: 'No necesariamente es un problema: puede reflejar tareas bien documentadas. Requiere revisión.',
      acc: 'Acompañar un RIT y confirmar que se revisan riesgos y controles en todos los ámbitos. No pedir hallazgos para "cumplir": un RIT sin hallazgo es válido.' });
  }
  $('s-diag').innerHTML = `<div class="section-title">🎯 Diagnóstico para la reunión — problema → dónde → evidencia → causa probable → acción sugerida</div>
   ${com && com.focos ? `<div class="card blk b-az" style="margin-bottom:10px"><h3>Focos redactados</h3><ul>${com.focos.map(x => `<li>${x}</li>`).join('')}</ul></div>` : ''}
   <div class="diag">${out.length ? out.map(o => `<div class="card dg ${o.c}"><h4>${o.t}</h4><dl><dt>Dónde</dt><dd>${o.donde || '—'}</dd><dt>Evidencia</dt><dd>${o.ev}</dd>
   <dt>Causa probable</dt><dd>${o.causa}</dd><dt>Acción sugerida</dt><dd>${o.acc}</dd></dl></div>`).join('') : '<div class="card vacio">Sin alertas con los filtros activos.</div>'}</div>
   <div class="sm" style="margin-top:6px">Generado por reglas a partir de los datos. Las causas no se infieren: cuando los datos no las determinan se indica "requiere revisión".</div>`;
}

// ---------------------------------------------------------------- 3. tendencia (4 semanas completas)
function tendencia() {
  const ws = tend4();
  if (!ws.length) { $('s-tend').innerHTML = '<div class="section-title">📈 Tendencia</div><div class="card vacio">Sin semanas completas evaluables.</div>'; return; }
  const col = ws.map(s => ({ s, K: calc(regs([s])), A: adherencia([s]) }));
  const filas = [
    ['Adherencia', c => c.A.na ? null : [c.A.n, c.A.N], M.metas.adherencia, false],
    ['Trazabilidad individual', c => [c.K.ind, c.K.N], M.metas.trazabilidad, false],
    ['Registro completo', c => [c.K.todo, c.K.N], M.metas.ejecucion, false],
    ['RIT sin hallazgo (informativo)', c => [c.K.sin, c.K.N], null, null],
    ['Hallazgos entendibles (≥2)', c => [c.K.ent, c.K.con], null, false],
    ['Hallazgos claros y accionables (3)', c => [c.K.acc, c.K.con], M.metas.redaccion_accionable, false],
    ['Listas copiadas (n)', c => ['n', c.K.lista], null, true],
    ['RIT con cuenta compartida (n)', c => ['n', c.K.comp], null, true],
  ];
  const body = filas.map(([lbl, f, meta, inv]) => {
    const v = col.map(c => f(c)), num = v.map(x => x === null ? null : x[0] === 'n' ? x[1] : pct(x[0], x[1]));
    const celdas = v.map((x, i) => x === null ? '<td class="num"><small>no aplica</small></td>' : x[0] === 'n' ? `<td class="num"><b>${x[1]}</b></td>` :
      `<td class="num">${pv(x[0], x[1])}<span class="bar"><b style="width:${pct(x[0], x[1]) || 0}%"></b></span></td>`).join('');
    const ok = num.filter(x => x !== null), filaN = v.some(x => x && x[0] === 'n');
    let t = '—';
    if (ok.length >= 2) { const a = ok.slice(0, Math.ceil(ok.length / 2)), b = ok.slice(Math.floor(ok.length / 2)), d = b.reduce((s, x) => s + x, 0) / b.length - a.reduce((s, x) => s + x, 0) / a.length;
      const fl = d > 0 ? '↑' : '↓', dd = (d > 0 ? '+' : '') + f1(d) + (filaN ? '' : ' pp');
      t = Math.abs(d) < 3 ? '<span class="flat">→ estable</span>' : inv === null ? `<span class="flat">${fl} ${d > 0 ? 'sube' : 'baja'} (${dd})</span>` : (inv ? d < 0 : d > 0) ? `<span class="up">${fl} mejora (${dd})</span>` : `<span class="down">${fl} deterioro (${dd})</span>`; }
    const pers = meta == null ? '—' : `${num.filter(x => x !== null && x < meta).length} de ${ok.length} semanas bajo ${meta}%`;
    return `<tr><td><b>${lbl}</b></td>${celdas}<td>${t}</td><td><small>${pers}</small></td></tr>`;
  }).join('');
  $('s-tend').innerHTML = `<div class="section-title">📈 Tendencia — últimas 4 semanas completas hasta S${F.sem}</div>
   <div class="card scroll"><table><tr><th>Indicador</th>${ws.map(s => `<th class="clic" data-irsem="${s}" title="Abrir semana">S${s} <small>${fd(SEM[s].lun)}</small></th>`).join('')}<th>Tendencia</th><th>Persistencia</th></tr>${body}</table></div>
   <div class="sm" style="margin-top:6px">Tendencia = promedio de la segunda mitad vs. la primera (±3 pp = estable). Persistencia = semanas bajo la meta o referencia. No sobrerreaccionar a una sola semana.</div>`;
}

// ---------------------------------------------------------------- tablas jerárquicas (niveles 1, 2 y 3)
function tablaJer(id, cab, filaFn, notaVacia) {
  const t = arbol(), esps = Object.keys(t).sort(); let html = '';
  esps.forEach(es => {
    html += filaFn({ nivel: 0, esp: es, label: es, eqs: Object.values(t[es]).flat() });
    Object.keys(t[es]).sort().forEach(ar => {
      const key = id + es + ar, ab = ABIERTOS.has(key) || !!F.area || F.eq !== '';
      html += filaFn({ nivel: 1, esp: es, area: ar, label: ar, eqs: t[es][ar], key, ab });
      if (ab) t[es][ar].slice().sort((a, b) => a.eq.localeCompare(b.eq)).forEach(e => { html += filaFn({ nivel: 2, label: e.eq, eqs: [e], e }); });
    });
  });
  return `<div class="card scroll"><table class="jer"><tr>${cab}</tr>${html || `<tr><td colspan="12">${notaVacia || 'Sin equipos con los filtros activos.'}</td></tr>`}</table></div>`;
}
function celdaNom(o) {
  const tog = o.nivel === 1 ? `<span class="tog">${o.ab ? '▾' : '▸'}</span>` : '';
  const attr = o.nivel === 1 ? ` class="n1 clic" data-tog="${esc(o.key)}"` : o.nivel === 2 ? ` class="n2 clic" data-eq="${o.e.k}"` : ' class="n0"';
  return `<td${attr}>${tog}${esc(o.label)}${o.e && !o.e.valido ? ' <span class="mr">equipo mal registrado: sin adherencia</span>' : ''}${o.e && o.e.lider ? `<div class="sm">${esc(o.e.lider)}</div>` : ''}</td>`;
}
function nivel1({ per, prev, AD }) {
  const w4 = tend4(), cab = '<th>Especialidad / Área / Equipo</th><th>Realizados / esperados</th><th>Δ vs. 4 semanas anteriores</th><th>Últimas 4 semanas completas</th><th>Estado</th>';
  let cuerpo;
  if (AD.na) cuerpo = `<div class="card vacio">${AD.na}</div>`;
  else {
    const A4 = adherencia(w4), Ap = adherencia(prev);
    cuerpo = tablaJer('n1', cab, o => {
      const ks = o.eqs.filter(e => e.valido).map(e => e.k), sum = (A, s) => ks.reduce((t, k) => { const x = A.por[k]; if (!x) return t; const y = s ? (x.sem[s] || { n: 0, N: 0 }) : x; return [t[0] + y.n, t[1] + y.N]; }, [0, 0]);
      const [n, N] = sum(AD), [pn, pN] = sum(Ap), p = pct(n, N);
      const mini = w4.map(s => { const [a, b] = sum(A4, s), q = pct(a, b); return `<i class="${q === null ? 'na' : q >= M.metas.adherencia ? 'ok' : q >= M.metas.adherencia - 15 ? 'amb' : 'red'}" style="height:${q === null ? 3 : Math.max(3, q * 0.22)}px" title="S${s}: ${q === null ? 'sin turno' : q + '% (' + nn(a) + '/' + nn(b) + ')'}"></i>`; }).join('');
      const est = !ks.length ? '<span class="est-na">no evaluable</span>' : N === 0 ? '<span class="est-na">sin turno en el período</span>' : estado(p, M.metas.adherencia);
      return `<tr class="${o.nivel === 0 ? 'g0' : ''}">${celdaNom(o)}<td class="num">${N ? pv(n, N) : '—'}</td><td>${N ? delta(p, pct(pn, pN)) : ''}</td><td><span class="mini">${mini}</span></td><td>${est}</td></tr>`;
    });
  }
  $('s-n1').innerHTML = `<div class="section-title">1 · ¿Se está realizando el RIT cuando corresponde? (${rango(per)})</div>${cuerpo}
   <div class="sm" style="margin-top:6px">Esperados: Mantención = días hábiles; Operación = días en que el turno estuvo de día (D) o de noche (N) según la rotación. Los turnos en descanso (DC) o administrativo (AD) no se exigen, también en el mini-gráfico. Clic en un área para ver sus equipos y en un equipo para su detalle.</div>`;
}
function nivel2({ per, R, K }) {
  const g = grupos(R, 2), cab = '<th>Especialidad / Área / Equipo</th><th>RIT</th><th>Trazabilidad individual</th><th>Cuenta compartida</th><th>Registro completo</th><th>Tarea SE</th><th>Formulario completo</th><th>Registro ≤12 h</th><th>En descanso</th>';
  const tabla = tablaJer('n2', cab, o => {
    const rs = o.eqs.flatMap(e => g[e.k] || []), k = calc(rs);
    if (!rs.length && o.nivel === 2) return `<tr>${celdaNom(o)}<td class="num">0</td><td colspan="7"><small>sin RIT en el período</small></td></tr>`;
    return `<tr class="${o.nivel === 0 ? 'g0' : ''}">${celdaNom(o)}<td class="num">${k.N}</td><td class="num">${pv(k.ind, k.N)}</td><td class="num">${k.comp ? `<b class="est-red">${k.comp}</b>` : '—'}</td>
     <td class="num">${pv(k.todo, k.N)}</td><td class="num">${pv(k.tse, k.N, { mr: false })}</td><td class="num">${pv(k.cmp, k.N, { mr: false })}</td><td class="num">${pv(k.op, k.N, { mr: false })}</td><td class="num">${k.fuera || '—'}</td></tr>`;
  });
  const cu = {}; R.filter(r => r.cta === 'comp').forEach(r => { cu[r.per] = cu[r.per] || []; cu[r.per].push(r); });
  const traz = Object.keys(cu).length ? `<div class="card blk b-red" style="margin-top:12px"><h3>⚠ Problema de trazabilidad</h3>
   <p style="font-size:12.5px;margin:0 0 8px">${K.comp} RIT fueron registrados mediante cuentas compartidas. No es posible atribuir individualmente la calidad de estos registros, y no se evalúa a ninguna persona por ellos.</p>
   <table><tr><th>Cuenta compartida</th><th>RIT</th><th>Con hallazgo</th><th>Equipos</th></tr>${Object.entries(cu).sort((a, b) => b[1].length - a[1].length).map(([p, rs]) =>
    `<tr class="clic" data-per="${esc(p)}"><td>${esc(p)} 👥</td><td class="num">${rs.length}</td><td class="num">${rs.filter(r => r.h).length}</td><td><small>${esc([...new Set(rs.map(r => r.e.area + ' · ' + r.e.eq))].join(', '))}</small></td></tr>`).join('')}</table></div>` : '';
  $('s-n2').innerHTML = `<div class="section-title">2 · ¿El RIT se ejecuta correctamente y es trazable? (${rango(per)})</div>${tabla}${traz}
   <div class="sm" style="margin-top:6px">Registro completo = tarea SoftExpert seleccionada + formulario completo (respondió si falta riesgo, control o tarea) + registrado hasta 12 h después del RIT. "Tarea correcta para el área", y si existen los riesgos, controles y documentos asociados, no son verificables con los datos actuales.</div>`;
}
function nivel3({ per, R, K }) {
  const g = grupos(R, 2), cab = '<th>Especialidad / Área / Equipo</th><th>RIT</th><th>Sin hallazgo</th><th>Con hallazgo</th><th>3 · 2 · 1 · 0</th><th>Listas copiadas</th><th>Entendibles (≥2)</th><th>Claros y accionables (3)</th>';
  const tabla = tablaJer('n3', cab, o => {
    const rs = o.eqs.flatMap(e => g[e.k] || []), k = calc(rs);
    return `<tr class="${o.nivel === 0 ? 'g0' : ''}">${celdaNom(o)}<td class="num">${k.N}</td><td class="num"><small>${k.sin} (${pct(k.sin, k.N) ?? '–'}%)</small></td><td class="num">${k.con}</td>
     <td class="num"><small>${k.d[3]} · ${k.d[2]} · ${k.d[1]} · ${k.d[0]}</small></td><td class="num">${k.lista || '—'}</td><td class="num">${pv(k.ent, k.con)}</td><td class="num">${pv(k.acc, k.con)}</td></tr>`;
  });
  const items = R.filter(r => r.h).flatMap(r => r.it.map(i => Object.assign({ r }, i))).reverse();
  const usados = new Set(), ej = (fn, n) => items.filter(i => fn(i) && !usados.has(i.x.trim().toLowerCase()) && usados.add(i.x.trim().toLowerCase())).slice(0, n);
  const fila = i => `<div class="ej clic" data-reg="${i.r.id}"><div>${chip(RCOL[i.n], i.n + '/3 · ' + RED[i.n])} ${i.lista ? chip('red', 'lista copiada') : ''} <span class="sm">${esc(i.t)} · ${esc(i.r.e.area)} · ${esc(i.r.e.eq)} · ${esc(i.r.per)}${i.r.cta === 'comp' ? ' 👥' : ''} · ${i.r.fh.slice(0, 5)}</span></div>
     <div class="q">«${esc(i.x.replace(/\s+/g, ' ').slice(0, 230))}»</div><div class="sm">${esc(i.m)}</div>${i.sug ? `<div class="sg"><b>Versión sugerida:</b> ${esc(i.sug)}</div>` : ''}</div>`;
  const bloques = [['👍 Buenos ejemplos — claros y accionables', 'b-ok', ej(i => i.n === 3, 4)], ['✍ Para mejorar — entendibles pero incompletos', 'b-nar', ej(i => i.n === 2, 4)],
    ['✕ Deficientes — genéricos, ambiguos o inutilizables', 'b-red', ej(i => i.n <= 1, 4)]];
  $('s-n3').innerHTML = `<div class="section-title">3 · Cuando hay un hallazgo, ¿está bien redactado? (${rango(per)}) — evaluación automática de redacción</div>
   <div class="card card-pad"><div class="two-col even" style="margin-top:0"><div><b>RIT del período</b> (${K.N})<div class="dist"><i class="rs" style="width:${100 * K.sin / Math.max(1, K.N)}%" title="Sin hallazgo: ${K.sin}"></i><i style="width:${100 * K.con / Math.max(1, K.N)}%;background:var(--gris)" title="Con hallazgo: ${K.con}"></i></div>
   <div class="leg"><span><i class="rs"></i>Sin hallazgo: ${K.sin} (${pct(K.sin, K.N) ?? '–'}%) — válido, no es falta</span><span><i style="background:var(--gris)"></i>Con hallazgo: ${K.con}</span></div></div>
   <div><b>Redacción de los hallazgos</b> (${K.con})<div class="dist">${[3, 2, 1, 0].map(n => K.d[n] ? `<i class="r${n}" style="width:${100 * K.d[n] / Math.max(1, K.con)}%" title="${RED[n]}: ${K.d[n]}"></i>` : '').join('')}</div>
   <div class="leg">${[3, 2, 1, 0].map(n => `<span><i class="r${n}"></i>${n} · ${RED[n]}: ${K.d[n]}</span>`).join('')}<span>(incluye ${K.lista} listas copiadas en 0)</span></div></div></div></div>
   <div style="margin-top:12px">${tabla}</div>
   <div class="section-title">📝 Ejemplos reales del período (herramienta de capacitación)</div>
   <div class="ej3">${bloques.map(([t, c, xs]) => `<div class="card blk ${c}"><h3>${t}</h3>${xs.length ? xs.map(fila).join('') : '<p class="sm">Sin ejemplos con los filtros activos.</p>'}</div>`).join('')}</div>
   <div class="formato"><b>Formato recomendado</b> (guía, no obligación cuando el caso no lo requiere): <b>[ACCIÓN]</b> + <b>[ELEMENTO EXACTO]</b> + <b>[TAREA / CONTEXTO]</b> + <b>[POR QUÉ]</b><br>
   Ej.: «Agregar control <code>CO-ADM-3944</code> "Instructivo descarga de químicos" al riesgo <code>SSO-034</code> de la tarea <code>G.02.03.15</code>, porque la tarea incluye descarga desde camión».</div>
   <div class="sm" style="margin-top:6px">Pauta automática: 3 = acción + elemento identificado + tarea (+ porqué si se elimina o modifica); 2 = entendible pero falta un elemento; 1 = ambiguo o genérico; 0 = no utilizable (vacío, lista copiada o sin pedido identificable). Es una evaluación de redacción, no de pertinencia técnica.</div>`;
}

// ---------------------------------------------------------------- 4–5. pertinencia y efectividad
function nivel45({ per, R, K }) {
  const H = R.filter(r => r.h), tar = {};
  H.forEach(r => { if (!r.tse) return; tar[r.tarea] = tar[r.tarea] || []; tar[r.tarea].push(r); });
  const rep = Object.entries(tar).filter(x => x[1].length >= 2).sort((a, b) => b[1].length - a[1].length);
  const vals = H.filter(r => D.valid[r.id]).flatMap(r => D.valid[r.id]), vc = {}; vals.forEach(v => { vc[v.pert || '(sin dato)'] = (vc[v.pert || '(sin dato)'] || 0) + 1; });
  $('s-n45').innerHTML = `<div class="section-title">4 · ¿El hallazgo es técnicamente pertinente? · 5 · ¿Mejora la gestión en SoftExpert? (${rango(per)})</div>
   <div class="two-col even" style="margin-top:0"><div class="card blk b-az"><h3>Nivel 4 · Pertinencia técnica</h3>
   <p style="font-size:13px"><b>${K.valid ? K.valid + ' de ' + K.con + ' hallazgos con validación técnica' : 'Pendiente de validación técnica'}</b> — ${K.con - K.valid} hallazgos sin validar.</p>
   ${vals.length ? `<ul>${Object.entries(vc).map(([k, v]) => `<li>${esc(k)}: ${v}</li>`).join('')}</ul>` : ''}
   <p class="sm">La pertinencia (si lo propuesto realmente corresponde en la operación) no se puede deducir del texto. Una redacción 3/3 puede ser técnicamente incorrecta.
   Para incorporarla, registrar la revisión del ingeniero o implementador en <code>config/validacion_tecnica.csv</code> (ID, ítem, pertinencia: Pertinente / No pertinente / Requiere corrección, implementado, comentario, validador, fecha) y regenerar el reporte.</p></div>
   <div class="card blk b-az"><h3>Nivel 5 · Efectividad</h3><table><tr><th>Estado de la mejora (hallazgos del período)</th><th>n</th></tr>
   ${Object.entries(K.est).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${v} <small>(${pct(v, K.con)}%)</small></td></tr>`).join('') || '<tr><td colspan="2">Sin hallazgos</td></tr>'}</table>
   <p class="sm">"Cerrada" indica que la mejora se cerró en la lista; no verifica que el cambio esté en SoftExpert ni que haya sido eficaz. Aceptado / rechazado / requirió corrección: <b>no disponible con los datos actuales</b>.</p>
   <h4 style="margin:10px 0 4px;font-size:12px">Tareas con hallazgos repetidos en el período (${rep.length})</h4>
   ${rep.length ? `<table>${rep.slice(0, 8).map(([t, rs]) => `<tr class="clic" data-lista="${rs.map(r => r.id).join(',')}" data-tit="${esc(t)}"><td><small>${esc(t)}</small></td><td class="num">${rs.length} hallazgos</td><td><small>${esc([...new Set(rs.map(r => r.est))].join(' / '))}</small></td></tr>`).join('')}</table>
   <p class="sm">Una misma tarea con hallazgos en varios RIT puede indicar que el problema persiste o que la mejora no se ha implementado: requiere revisión.</p>` : '<p class="sm">Ninguna tarea con más de un hallazgo.</p>'}</div></div>`;
}

// ---------------------------------------------------------------- categorías de gestión (4 semanas)
function categorias() {
  const w4 = ventana4(), C = M.categorias;
  let cuerpo;
  if (noAdh()) cuerpo = '<div class="card vacio">Las categorías combinan adherencia (por equipo) y calidad: no aplican con filtros de persona, tarea, hallazgo, redacción, estado o cuenta.</div>';
  else if (!w4.length) cuerpo = '<div class="card vacio">Etapa piloto: sin categorías.</div>';
  else {
    const A = adherencia(w4), g = grupos(regs(w4), 2), cats = { ref: [], cons: [], buen: [], apoyo: [], sinh: [], sint: [] };
    D.equipos.filter(e => e.valido && eqMatch(e)).forEach(e => {
      const a = A.por[e.k] || { n: 0, N: 0 }, rs = g[e.k] || [], k = calc(rs), pa = pct(a.n, a.N), pc = pct(k.ent, k.con), comp = pct(k.comp, k.N);
      const it = { e, a, k, pa, pc, comp, traz: comp !== null && comp >= C.trazabilidad_alerta };
      if (!a.N) cats.sint.push(it); else if (k.con < C.min_hallazgos) cats.sinh.push(it);
      else if (pa >= C.adherencia_alta) (pc >= C.calidad_alta ? cats.ref : cats.cons).push(it); else (pc >= C.calidad_alta ? cats.buen : cats.apoyo).push(it);
    });
    const def = [['ref', 'Referentes', 'ok', `Adherencia ≥${C.adherencia_alta}% y ≥${C.calidad_alta}% de hallazgos entendibles.`],
      ['cons', 'Constantes, pero requieren mejorar la calidad de sus hallazgos', 'amb', 'Hacen el RIT; sus hallazgos son mayoritariamente genéricos o no utilizables.'],
      ['buen', 'Buen desempeño cuando participa, pero requiere constancia', 'amb', 'Hallazgos entendibles; faltan días de RIT.'],
      ['apoyo', 'Requieren apoyo', 'red', 'Baja adherencia y hallazgos poco entendibles.'],
      ['sinh', 'RIT realizado sin hallazgos suficientes para evaluar redacción', 'az', `Menos de ${C.min_hallazgos} hallazgos en 4 semanas. No es negativo por sí solo: se lee junto con la adherencia y el registro.`],
      ['sint', 'Sin turno exigido en el período', 'gray', 'El turno estuvo en descanso o administrativo.']];
    cuerpo = `<div class="cuad">${def.filter(([k]) => cats[k].length || k !== 'sint').map(([k, t, c, d]) => `<div class="card card-pad cq cq-${c === 'gray' ? 'az' : c}"><h3 class="card-h">${t} (${cats[k].length})</h3><div class="sm" style="margin-bottom:8px">${d}</div>
      ${cats[k].sort((a, b) => (b.pa ?? 0) - (a.pa ?? 0)).map(x => `<span class="chip ${c === 'az' ? 'flt' : c} clic" data-eq="${x.e.k}" title="Adherencia ${x.pa ?? 's/d'}% (${nn(x.a.n)}/${nn(x.a.N)}) · entendibles ${x.pc ?? 's/d'}% (${x.k.ent}/${x.k.con}) · registro completo ${pct(x.k.todo, x.k.N) ?? 's/d'}% · cuenta compartida ${x.comp ?? 0}%">${esc(x.e.area)} · ${esc(x.e.eq)}${x.traz ? ' ⚠👥' : ''}</span>`).join('') || '<span class="sm">—</span>'}</div>`).join('')}</div>
      <div class="sm" style="margin-top:6px">⚠👥 = problema de trazabilidad: ≥${C.trazabilidad_alerta}% de sus RIT con cuenta compartida (la calidad no es atribuible a una persona). Pase el cursor por un equipo para ver sus cifras; clic para el detalle.</div>`;
  }
  $('s-cat').innerHTML = `<div class="section-title">🧭 Categorías de gestión por equipo — ${rango(w4)} · eje X adherencia, eje Y hallazgos entendibles</div>${cuerpo}`;
}

// ---------------------------------------------------------------- personas (4 semanas)
function resumenPersona(rs) {
  const k = calc(rs);
  return { rs, k, n: rs.length, sem: new Set(rs.map(r => r.s)).size, dias: new Set(rs.map(r => r.dia)).size, pe: pct(k.ent, k.con), pa: pct(k.acc, k.con), malos: k.d[0] + k.d[1],
    eqs: [...new Set(rs.map(r => r.e.area + ' · ' + r.e.eq))] };
}
function alertaPersona(p) {
  const C = M.categorias, out = [];
  if (p.k.con >= C.min_hallazgos && p.malos / p.k.con >= 0.5) out.push(`${pct(p.malos, p.k.con)}% de sus hallazgos son genéricos o no utilizables`);
  if (p.k.con >= C.min_hallazgos && p.pa >= 50) out.push('buena calidad de redacción');
  if (p.k.lista) out.push(`${p.k.lista} listas copiadas`);
  if (p.k.N >= 5 && pct(p.k.op, p.k.N) < 75) out.push(`registra tarde (${pct(p.k.op, p.k.N)}% dentro de 12 h)`);
  if (!p.k.con) out.push('sin hallazgos en el período (no es negativo por sí solo)');
  return out.join(' · ');
}
function personas() {
  const w4 = hasta(F.sem, 4, false), R = regs(w4, { per2: true }), por = {};
  R.forEach(r => { (por[r.per] = por[r.per] || []).push(r); });
  const P = Object.entries(por).map(([n, rs]) => Object.assign({ nombre: n, cta: rs[0].cta }, resumenPersona(rs)));
  const ind = P.filter(p => p.cta === 'ind'), comp = P.filter(p => p.cta !== 'ind'), C = M.categorias;
  const tab = (titulo, sub, lista, cols) => `<div class="card card-pad"><h3 class="card-h">${titulo}</h3><div class="card-h-sub">${sub}</div><div class="scroll"><table><tr><th>Persona</th>${cols.map(c => `<th>${c[0]}</th>`).join('')}</tr>
    ${lista.length ? lista.slice(0, 8).map(p => `<tr class="clic" data-per="${esc(p.nombre)}"><td>${esc(p.nombre)}${top20(p.nombre) ? ' ' + chip('flt', 'Top 20 #' + top20(p.nombre).rank, 'Ranking piloto (fuente externa)') : ''}<div class="sm">${esc(p.eqs.slice(0, 2).join(', '))}</div></td>${cols.map(c => `<td class="num">${c[1](p)}</td>`).join('')}</tr>`).join('') : `<tr><td colspan="${cols.length + 1}"><small>Sin personas que cumplan el criterio.</small></td></tr>`}</table></div></div>`;
  const act = ind.slice().sort((a, b) => b.n - a.n), cons = ind.slice().sort((a, b) => b.sem - a.sem || b.dias - a.dias);
  const cal = ind.filter(p => p.k.con >= C.min_hallazgos).sort((a, b) => b.pa - a.pa || b.pe - a.pe), apo = ind.filter(p => p.k.con >= C.min_hallazgos && p.malos / p.k.con >= 0.5).sort((a, b) => b.malos / b.k.con - a.malos / a.k.con);
  $('s-per').innerHTML = `<div class="section-title">👤 Personas — ${rango(w4)} (solo cuentas individuales; conceptos separados, sin ranking único)</div>
   <div class="two-col even" style="margin-top:0">${tab('Mayor actividad en la lista RIT', 'RIT registrados con su cuenta', act, [['RIT', p => p.n], ['Semanas activas', p => p.sem + '/' + w4.length]])}
   ${tab('Mayor constancia', 'Semanas con al menos un RIT. La adherencia individual no existe: el RIT se exige al equipo/turno.', cons, [['Semanas activas', p => p.sem + '/' + w4.length], ['Días con RIT', p => p.dias]])}</div>
   <div class="two-col even">${tab('Mejor calidad de redacción', `Mínimo ${C.min_hallazgos} hallazgos · % claros y accionables`, cal, [['Accionables (3)', p => pv(p.k.acc, p.k.con)], ['Entendibles (≥2)', p => pv(p.k.ent, p.k.con, { mr: false })]])}
   ${tab('Requieren apoyo en redacción', `Mínimo ${C.min_hallazgos} hallazgos · ≥50% genéricos o no utilizables`, apo, [['Genéricos / no utilizables', p => pv(p.malos, p.k.con)], ['Alerta', p => `<small>${esc(alertaPersona(p))}</small>`]])}</div>
   ${comp.length ? `<div class="card card-pad" style="margin-top:12px"><h3 class="card-h">Cuentas compartidas — no atribuibles a una persona (trazabilidad)</h3><table><tr><th>Cuenta</th><th>RIT</th><th>Hallazgos</th><th>Entendibles</th></tr>
   ${comp.sort((a, b) => b.n - a.n).map(p => `<tr class="clic" data-per="${esc(p.nombre)}"><td>${esc(p.nombre)} 👥</td><td class="num">${p.n}</td><td class="num">${p.k.con}</td><td class="num">${pv(p.k.ent, p.k.con)}</td></tr>`).join('')}</table>
   <p class="sm">Su calidad se informa como dato del equipo, no de una persona.</p></div>` : ''}
   ${tablaTop20(P, w4)}`;
}
const top20 = n => D.top20.find(t => t.nombre.toLowerCase() === n.toLowerCase());
function tablaTop20(P, w4) {
  if (!D.top20.length) return '';
  const filas = D.top20.map(t => {
    const p = P.find(x => x.nombre.toLowerCase() === t.nombre.toLowerCase());
    return `<tr class="${p ? 'clic' : ''}" ${p ? `data-per="${esc(p.nombre)}"` : ''}><td class="num">${t.rank}</td><td>${esc(t.nombre)}${t.compartida ? ' 👥' : ''}<div class="sm">${esc(t.area)} · ${esc(t.esp)} · ${esc(t.rol)}</div></td>
      <td class="num">${t.cantidad}</td><td class="num">${t.calidad}</td><td class="num">${t.frecuencia}</td><td class="num">${p ? p.n : 0}</td><td class="num">${p ? p.sem + '/' + w4.length : '0/' + w4.length}</td>
      <td class="num">${p ? pv(p.k.ent, p.k.con) : '—'}</td><td class="num">${p ? pv(p.k.acc, p.k.con, { mr: false }) : '—'}</td></tr>`;
  }).join('');
  return `<div class="card card-pad" style="margin-top:12px"><h3 class="card-h">Referencia externa: ranking del piloto de la nueva plataforma (Top 20)</h3>
   <div class="card-h-sub">Las columnas "Cantidad", "Calidad" y "Frecuencia" vienen de ese reporte, que las combina en un ranking. Aquí se muestran por separado y junto a los indicadores de este reporte (${rango(w4)}), sin volver a combinarlos.</div>
   <div class="scroll"><table><tr><th>#</th><th>Persona</th><th>Cantidad (piloto)</th><th>Calidad (piloto)</th><th>Frecuencia (piloto)</th><th>RIT 4 sem.</th><th>Semanas activas</th><th>Entendibles (≥2)</th><th>Accionables (3)</th></tr>${filas}</table></div></div>`;
}

// ---------------------------------------------------------------- registros (consulta)
function registros({ per, R }) {
  const xs = R.slice().reverse(), tot = xs.length, pp = 25, pags = Math.max(1, Math.ceil(tot / pp)); if (PAG >= pags) PAG = 0;
  const filas = xs.slice(PAG * pp, PAG * pp + pp).map(r => `<tr class="clic" data-reg="${r.id}"><td class="num">${r.fh}<div class="sm">S${r.s}</div></td><td>${esc(r.e.area)} · ${esc(r.e.eq)}<div class="sm">${esc(r.e.esp)}${r.ct ? ' · turno ' + r.ct : ''}</div></td>
    <td>${esc(r.per)} ${r.cta === 'comp' ? '👥' : ''}</td><td><small>${esc(r.tarea.slice(0, 80))}</small>${r.tse ? '' : ' ' + chip('amb', 'sin tarea SE')}</td>
    <td>${r.h ? r.it.map(i => chip(RCOL[i.n], i.t + ' ' + i.n + '/3')).join(' ') : '<span class="sm">sin hallazgo</span>'}</td><td><small>${esc(r.est)}</small></td></tr>`).join('');
  $('s-reg').innerHTML = `<div class="section-title">🔎 Registros RIT — ${rango(per)} (${tot})</div><div class="card scroll"><table><tr><th>Fecha RIT</th><th>Área · Equipo</th><th>Persona / cuenta</th><th>Tarea SoftExpert</th><th>Hallazgos (redacción)</th><th>Estado mejora</th></tr>
   ${filas || '<tr><td colspan="6"><small>Sin registros con los filtros activos.</small></td></tr>'}</table>
   <div class="pag"><button class="btn" data-pag="-1" ${PAG ? '' : 'disabled'}>◀</button> página ${PAG + 1} de ${pags} <button class="btn" data-pag="1" ${PAG < pags - 1 ? '' : 'disabled'}>▶</button></div></div>`;
}

// ---------------------------------------------------------------- histórico (todas las semanas)
function historico() {
  const filas = ORD.slice().reverse().map(s => {
    const S = SEM[s], k = calc(regs([s])), a = adherencia([s]);
    return `<tr class="clic" data-irsem="${s}"><td><b>S${s}</b> <small>${fd(S.lun)} a ${fd(S.dom)}</small> ${S.parcial ? '<span class="mr">parcial</span>' : ''}${S.piloto ? '<span class="mr">piloto</span>' : ''}</td><td class="num">${k.N}</td>
     <td class="num">${a.na ? `<small>${S.piloto ? 'piloto: no se evalúa' : 'no aplica'}</small>` : pv(a.n, a.N)}</td><td class="num">${pv(k.ind, k.N, { mr: false })}</td><td class="num">${pv(k.todo, k.N, { mr: false })}</td>
     <td class="num">${k.con}</td><td class="num">${pv(k.ent, k.con, { mr: false })}</td><td class="num">${pv(k.acc, k.con, { mr: false })}</td><td class="num">${k.lista || '—'}</td></tr>`;
  }).join('');
  $('s-hist').innerHTML = `<div class="section-title">🗂 Histórico S${ORD[0]}–S${ORD[ORD.length - 1]} (con los filtros activos) — clic en una semana para abrirla</div>
   <div class="card scroll"><table><tr><th>Semana</th><th>RIT</th><th>Adherencia</th><th>Trazabilidad individual</th><th>Registro completo</th><th>Con hallazgo</th><th>Entendibles (≥2)</th><th>Accionables (3)</th><th>Listas copiadas</th></tr>${filas}</table></div>
   <div class="sm" style="margin-top:6px">S${ORD[0]}–S${M.inicio - 1}: etapa piloto y despliegue (Madera desde S${ORD[0]}); la adherencia se evalúa desde S${M.inicio}, cuando todas las áreas registran.</div>`;
}

// ---------------------------------------------------------------- definiciones
function definiciones() {
  if ($('s-def').dataset.ok) return; $('s-def').dataset.ok = 1;
  $('s-def').innerHTML = `<div class="section-title">📚 Definiciones, datos y limitaciones</div>
  <details class="def"><summary>Cómo se calcula cada indicador</summary>
   <table><tr><th>Nivel</th><th>Indicador</th><th>Cálculo</th><th>Campos del Excel</th></tr>
   <tr><td>1</td><td>Adherencia</td><td>Días con RIT en día exigido / días exigidos, por equipo y semana (tope por equipo-semana). Mantención: días hábiles sin feriados. Operación: días D o N del turno según la rotación (DC y AD no se exigen). RIT de 20:00 o después = turno noche del día siguiente. Desde S${M.inicio}.</td><td>Fecha, Especialidad, Área, Equipo + rotación de turnos</td></tr>
   <tr><td>2</td><td>Trazabilidad individual</td><td>RIT con cuenta personal / RIT. Compartida = cuenta genérica de turno o puesto (listado de correos genéricos ce05.*, "Operador …", "Despachador de Carga", "Volante …").</td><td>Creado por</td></tr>
   <tr><td>2</td><td>Registro completo</td><td>Tarea SoftExpert seleccionada (no "Notificar sin SE", "Agregar tarea en SE", "Parada de área/PGP") + formulario completo (respondió falta riesgo/control/tarea) + registrado entre 0 y 12 h después del RIT.</td><td>Tarea, FaltaRiesgo, FaltaControl, FaltaTarea, Fecha, Creado</td></tr>
   <tr><td>3</td><td>Redacción 0–3 (automática)</td><td>Por cada ítem marcado "Sí": 3 = acción + elemento identificado (código, tag o nombre específico) + tarea, y porqué si se elimina o modifica; 2 = entendible pero falta un elemento; 1 = ambiguo/genérico; 0 = vacío, lista copiada o sin pedido identificable. El RIT toma la nota más baja de sus ítems. Entendibles = ≥2; accionables = 3.</td><td>RiesgoTexto, ControlTexto, NuevaTarea</td></tr>
   <tr><td>3</td><td>Lista copiada</td><td>3 o más códigos de SoftExpert sin ninguna acción (agregar, eliminar, modificar…). Cuenta como 0.</td><td>ídem</td></tr>
   <tr><td>4</td><td>Pertinencia técnica</td><td>Solo con validación registrada en config/validacion_tecnica.csv; si no, "Pendiente de validación técnica".</td><td>—</td></tr>
   <tr><td>5</td><td>Efectividad</td><td>Estado de la mejora en la lista y tareas con más de un hallazgo en el período.</td><td>EstadoMejora, ComentarioCierre, Tarea</td></tr>
   <tr><td>—</td><td>Comparación</td><td>Contra las 4 semanas completas anteriores al período (n y N acumulados). Tendencia: 4 semanas completas hasta la seleccionada.</td><td>—</td></tr>
   <tr><td>—</td><td>Muestra reducida</td><td>Denominador menor que ${M.muestra}.</td><td>—</td></tr></table></details>
  <details class="def"><summary>Cambios de definición respecto de la versión anterior</summary><ul>
   <li>La pauta 0–3 se renombra "evaluación automática de redacción" y es más exigente: un verbo de acción ya no basta para 3; faltan elementos → baja. Las listas copiadas valen 0 (antes 1).</li>
   <li>"Hallazgo claro" (≥2) pasa a llamarse "entendible"; "claro y accionable" = 3.</li>
   <li>Las cuentas genéricas del listado de correos (p. ej. "Despachador de Carga", 37 RIT) dejan de contarse como personas.</li>
   <li>La adherencia tiene tope por equipo-semana y se evalúa desde S${M.inicio} (todas las áreas registrando); antes, cada equipo desde su primer registro.</li>
   <li>"Registran sin encontrar nada" pasa a "RIT realizado sin hallazgos suficientes para evaluar redacción": un RIT sin hallazgo es válido.</li>
   <li>El Top 20 deja de usarse como ranking único: sus puntajes se muestran por separado.</li></ul></details>
  <details class="def"><summary>No disponible con los datos actuales</summary><ul>
   <li>Tarea correcta para el área (requiere el maestro de tareas por área de SoftExpert; el prefijo del código se repite entre macroprocesos).</li>
   <li>Si la tarea revisada tiene riesgos, controles y documentos asociados en SoftExpert (no viene en la lista).</li>
   <li>Pertinencia técnica de cada hallazgo (estructura lista en config/validacion_tecnica.csv; hoy sin validaciones).</li>
   <li>Hallazgo aceptado, rechazado o que requirió corrección; fecha de cierre y verificación de implementación.</li>
   <li>Adherencia individual (el RIT se exige al equipo/turno; no hay calendario por persona).</li>
   <li>Quién lideró el RIT cuando se usó una cuenta compartida.</li>
   <li>Rotación de turnos antes de abril de 2026 (se usa 0,4 días por día) y después de diciembre de 2026.</li></ul></details>`;
}

// ---------------------------------------------------------------- detalle (modales)
const bg = $('modal'), box = $('modalBox');
function abrir(h) { box.innerHTML = '<button class="close-x" style="float:right" onclick="cerrar()" title="Cerrar (Esc)">✕</button>' + h; bg.classList.add('show'); box.scrollTop = 0; enlazar(box); }
function cerrar() { bg.classList.remove('show'); }
bg.addEventListener('click', e => { if (e.target === bg) cerrar(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') cerrar(); });
const siNo = (v, t) => `<span class="${v ? 'si' : 'no'}">${t}: ${v ? 'Sí' : 'No'}</span>`;
function verReg(id) {
  const r = BYID[id]; if (!r) return; const e = r.e, ct = { D: 'D (día)', N: 'N (noche)', DC: 'DC (descanso)', AD: 'AD (administrativo)' }[r.ct] || (r.ct || 'sin calendario');
  const items = r.it.map(i => {
    const v = (D.valid[r.id] || []).filter(x => !x.item || x.item === i.t);
    return `<div class="card card-pad" style="margin:8px 0;box-shadow:none"><b>${esc(i.t)}</b> — texto original<div class="txt">${esc(i.x) || '—'}</div>
     <table class="kv"><tr><td>Redacción (automática)</td><td>${chip(RCOL[i.n], i.n + '/3 — ' + RED[i.n])} ${i.lista ? chip('red', 'lista copiada') : ''}<div class="sm">${esc(i.m)}</div></td></tr>
     <tr><td>Elementos detectados</td><td><div class="el">${siNo(i.el[0], 'Acción')}${siNo(i.el[1], 'Objeto')}${siNo(i.el[2], 'Identificación')}${siNo(i.el[3], 'Tarea/contexto')}${siNo(i.el[4], 'Justificación' + (i.jr ? '' : ' (opcional)'))}</div></td></tr>
     <tr><td>Cómo mejorarlo</td><td>${i.sug ? `<div class="sg" style="background:var(--okBg);border-radius:6px;padding:6px 8px">${esc(i.sug)}</div>` : 'Bien redactado: se entiende qué cambiar.'}</td></tr>
     <tr><td>Pertinencia técnica</td><td>${v.length ? v.map(x => `<b>${esc(x.pert)}</b>${x.impl ? ' · implementado: ' + esc(x.impl) : ''}${x.com ? ' · ' + esc(x.com) : ''} <small>${esc(x.por)} ${esc(x.f)}</small>`).join('<br>') : '<b>Pendiente de validación técnica</b> <small>(la redacción no indica si es correcto)</small>'}</td></tr></table></div>`;
  }).join('');
  abrir(`<h3>RIT ${id} ${r.h ? chip(RCOL[r.n], 'redacción ' + r.n + '/3') : chip('gray', 'sin hallazgo')}</h3>
   <h4>RIT</h4><table class="kv"><tr><td>Fecha y hora</td><td>${r.fh} <small>(semana S${r.s}; registrado ${r.crt}${r.ret !== null ? ', ' + f1(r.ret) + ' h después' : ''})</small></td></tr>
   <tr><td>Turno según calendario</td><td>${esc(ct)} ${r.fuera ? chip('amb', 'día de descanso: no suma adherencia') : r.ct === 'AD' ? chip('gray', 'administrativo: no se exige') : ''}</td></tr>
   <tr><td>Persona / cuenta</td><td><span class="clic" data-per="${esc(r.per)}"><b>${esc(r.per)}</b></span> — ${ctaTxt[r.cta]}${r.cta === 'comp' ? ' <span class="mr">problema de trazabilidad</span>' : ''}</td></tr>
   <tr><td>Especialidad · Área · Equipo</td><td>${esc(e.esp)} · ${esc(e.area)} · <span class="clic" data-eq="${e.k}"><b>${esc(e.eq)}</b></span>${r.mal ? ' <span class="mr">equipo mal registrado</span>' : ''}</td></tr>
   <tr><td>Tarea SoftExpert</td><td>${esc(r.tarea) || '—'} ${r.tse ? '' : chip('amb', 'sin tarea de SoftExpert')}</td></tr></table>
   <h4>Ejecución</h4><div class="el">${siNo(r.tse, 'Tarea SE seleccionada')}${siNo(r.cmp, 'Formulario completo')}${siNo(r.op, 'Registrado ≤12 h')}${siNo(!r.fuera, 'En día de su turno')}</div>
   <table class="kv"><tr><td>¿Falta riesgo / control / tarea?</td><td>${esc(r.fr || '—')} / ${esc(r.fc || '—')} / ${esc(r.ft || '—')}</td></tr><tr><td>Observación</td><td>${esc(r.tit) || '—'}</td></tr></table>
   <h4>Hallazgos</h4>${items || '<p class="sm">Sin hallazgo: la tarea se revisó y no se registró nada que mejorar. Es un resultado válido y cuenta para la adherencia.</p>'}
   <h4>Seguimiento (nivel 5)</h4><table class="kv"><tr><td>Estado de la mejora</td><td>${esc(r.est) || '—'} <small>("Cerrada" no verifica implementación ni eficacia)</small></td></tr>
   <tr><td>Comentario de cierre</td><td>${esc(r.cc) || '—'}</td></tr><tr><td>Implementador / ingeniero</td><td><small>${esc(r.impl) || '—'} / ${esc(r.ing) || '—'}</small></td></tr></table>`);
}
function listaRegs(rs, titulo, extra) {
  const sem = {}; rs.forEach(r => { (sem[r.s] = sem[r.s] || []).push(r); });
  return (extra || '') + Object.keys(sem).sort((a, b) => b - a).map(s => `<h4>${semTxt(+s)}</h4><div class="scroll"><table><tr><th>Fecha</th><th>Equipo / persona</th><th>Tarea</th><th>Hallazgos</th><th>Mejora</th></tr>
   ${sem[s].slice().reverse().map(r => `<tr class="clic" data-reg="${r.id}"><td class="num">${r.fh}</td><td>${esc(r.e.area)} · ${esc(r.e.eq)}<div class="sm">${esc(r.per)}${r.cta === 'comp' ? ' 👥' : ''}</div></td><td><small>${esc(r.tarea.slice(0, 80))}</small></td>
   <td>${r.h ? r.it.map(i => chip(RCOL[i.n], i.t + ' ' + i.n + '/3')).join(' ') : '<span class="sm">sin hallazgo</span>'}</td><td><small>${esc(r.est)}</small></td></tr>`).join('')}</table></div>`).join('');
}
function verEquipo(k) {
  const e = EQ[k], w4 = ventana4(), rs = REG.filter(r => r.k == k && new Set(hasta(F.sem, 4, false)).has(r.s)), K = calc(rs);
  const A = e.valido && w4.length ? adherencia(w4, x => x.k == k) : null, a = A && !A.na ? A.por[k] : null;
  const alertas = [];
  if (a && a.N && pct(a.n, a.N) < M.metas.adherencia) alertas.push(`Adherencia ${pct(a.n, a.N)}% (${nn(a.n)}/${nn(a.N)}): bajo la meta de ${M.metas.adherencia}%.`);
  if (K.comp && pct(K.comp, K.N) >= M.categorias.trazabilidad_alerta) alertas.push(`${pct(K.comp, K.N)}% de sus RIT con cuenta compartida: la calidad no es atribuible a personas.`);
  if (K.con >= 3 && pct(K.ent, K.con) < M.categorias.calidad_alta) alertas.push(`${100 - pct(K.ent, K.con)}% de sus hallazgos son genéricos o no utilizables.`);
  if (!K.con && K.N) alertas.push('Sin hallazgos en 4 semanas: válido por sí solo; revisar que se analicen todos los ámbitos.');
  const semRows = a ? Object.entries(a.sem).map(([s, v]) => `<td class="num">S${s}<br>${v.N ? pv(v.n, v.N, { mr: false }) : '<small>sin turno</small>'}</td>`).join('') : '';
  abrir(`<h3>${esc(e.area)} · ${esc(e.esp)} · ${esc(e.eq)}</h3><p class="sm">Líder de equipo: ${esc(e.lider) || '—'} · ${rango(hasta(F.sem, 4, false))}</p>
   ${alertas.length ? alertas.map(x => `<div class="alerta">⚠ ${x}</div>`).join('') : ''}
   <h4>Adherencia</h4>${!e.valido ? '<p class="sm">Equipo mal registrado (sin turno A–E o especialidad inconsistente): no se evalúa adherencia.</p>' : a ? `<p>${pv(a.n, a.N)} días con RIT / exigidos</p><table><tr>${semRows}</tr></table>` : '<p class="sm">No evaluable en este período.</p>'}
   <h4>Trazabilidad y ejecución</h4><div class="el"><span class="si">Individual: ${K.ind}/${K.N}</span><span class="${K.comp ? 'no' : 'si'}">Compartida: ${K.comp}</span><span>Tarea SE: ${K.tse}/${K.N}</span><span>Formulario: ${K.cmp}/${K.N}</span><span>≤12 h: ${K.op}/${K.N}</span></div>
   <h4>Redacción de hallazgos</h4><p>${K.con} hallazgos de ${K.N} RIT · entendibles ${pv(K.ent, K.con)} · accionables ${pv(K.acc, K.con, { mr: false })} · distribución 3/2/1/0: ${K.d[3]}/${K.d[2]}/${K.d[1]}/${K.d[0]} · listas copiadas ${K.lista}</p>
   <h4>Levantamientos (4 semanas) — clic para el detalle</h4>${listaRegs(rs)}`);
}
function verPersona(nombre) {
  const w4 = hasta(F.sem, 4, false), rs = REG.filter(r => r.per === nombre && new Set(w4).has(r.s)), p = resumenPersona(rs), K = p.k, cta = rs[0] ? rs[0].cta : 'ind';
  const t = top20(nombre), eqs = [...new Set(rs.map(r => r.k))];
  const A = w4.length && eqs.length ? adherencia(w4.filter(s => !SEM[s].piloto), x => eqs.includes(x.k)) : null;
  const ej = rs.filter(r => r.h).flatMap(r => r.it.map(i => Object.assign({ r }, i)));
  const mejor = ej.slice().sort((a, b) => b.n - a.n)[0], peor = ej.slice().sort((a, b) => a.n - b.n)[0];
  const concl = [];
  if (cta !== 'ind') concl.push('Cuenta compartida: los registros no se pueden atribuir a una persona; se evalúan como dato del equipo.');
  else {
    if (K.con >= 3 && p.malos / K.con >= 0.5) concl.push(`${pct(p.malos, K.con)}% de sus hallazgos son genéricos o no utilizables: acompañar con el formato y ejemplos.`);
    if (K.con >= 3 && p.pa >= 50) concl.push(`Buena calidad de redacción (${p.pa}% claros y accionables): referente para su equipo.`);
    if (p.sem < Math.min(3, w4.length)) concl.push(`Baja constancia: registró en ${p.sem} de ${w4.length} semanas.`);
    if (!K.con) concl.push('Sin hallazgos en el período: no es negativo por sí solo.');
  }
  abrir(`<h3>${esc(nombre)} ${cta === 'comp' ? '👥' : ''}</h3><p class="sm">${ctaTxt[cta]} · ${rango(w4)}${t ? ` · Top 20 piloto #${t.rank} (cantidad ${t.cantidad}, calidad ${t.calidad}, frecuencia ${t.frecuencia} — fuente externa)` : ''}</p>
   ${concl.map(x => `<div class="alerta">${x}</div>`).join('')}
   <h4>Identificación</h4><table class="kv"><tr><td>Equipos / áreas donde registra</td><td>${eqs.map(k => `<span class="clic" data-eq="${k}">${esc(EQ[k].esp)} · ${esc(EQ[k].area)} · <b>${esc(EQ[k].eq)}</b></span>`).join('<br>') || '—'}</td></tr></table>
   <h4>Adherencia</h4><p>RIT registrados: <b>${p.n}</b> · días con RIT: ${p.dias} · semanas activas: ${p.sem}/${w4.length}.<br>
   <small>La adherencia se exige al equipo/turno, no a cada persona (no hay calendario individual).</small>${A && !A.na ? ` Adherencia de su(s) equipo(s): ${pv(A.n, A.N)}.` : ''}</p>
   <h4>Trazabilidad</h4><p>${cta === 'ind' ? `Cuenta individual: ${p.n} RIT atribuibles.` : `Cuenta compartida: ${p.n} RIT no atribuibles individualmente.`}</p>
   <h4>Ejecución</h4><div class="el"><span>Tarea SE: ${K.tse}/${K.N}</span><span>Formulario completo: ${K.cmp}/${K.N}</span><span>≤12 h: ${K.op}/${K.N}</span><span>Registro completo: ${K.todo}/${K.N}</span></div>
   <h4>Calidad de redacción</h4><p>${K.con} hallazgos · promedio ${K.prom === null ? 's/d' : f1(K.prom)} / 3 · distribución 3/2/1/0: ${K.d[3]}/${K.d[2]}/${K.d[1]}/${K.d[0]} · listas copiadas ${K.lista} · entendibles ${pv(K.ent, K.con)}</p>
   ${mejor ? `<div class="ej clic" data-reg="${mejor.r.id}"><b>Mejor ejemplo</b> ${chip(RCOL[mejor.n], mejor.n + '/3')}<div class="q">«${esc(mejor.x.slice(0, 220))}»</div></div>` : ''}
   ${peor && peor !== mejor ? `<div class="ej clic" data-reg="${peor.r.id}"><b>Ejemplo a mejorar</b> ${chip(RCOL[peor.n], peor.n + '/3')}<div class="q">«${esc(peor.x.slice(0, 220))}»</div>${peor.sug ? `<div class="sg"><b>Versión sugerida:</b> ${esc(peor.sug)}</div>` : ''}</div>` : ''}
   <h4>Levantamientos (4 semanas)</h4>${listaRegs(rs)}`);
}

// ---------------------------------------------------------------- eventos y filtros
function enlazar(root) {
  root.querySelectorAll('[data-reg]').forEach(x => { if (x._b) return; x._b = 1; x.addEventListener('click', ev => { ev.stopPropagation(); verReg(+x.dataset.reg); }); });
  root.querySelectorAll('[data-eq]').forEach(x => { if (x._b) return; x._b = 1; x.addEventListener('click', ev => { ev.stopPropagation(); verEquipo(+x.dataset.eq); }); });
  root.querySelectorAll('[data-per]').forEach(x => { if (x._b || !x.dataset.per) return; x._b = 1; x.addEventListener('click', ev => { ev.stopPropagation(); verPersona(x.dataset.per); }); });
  root.querySelectorAll('[data-irsem]').forEach(x => { if (x._b) return; x._b = 1; x.addEventListener('click', () => { F.sem = +x.dataset.irsem; $('fSem').value = F.sem; cerrar(); render(); window.scrollTo(0, 0); }); });
  root.querySelectorAll('[data-tog]').forEach(x => { if (x._b) return; x._b = 1; x.addEventListener('click', () => { const k = x.dataset.tog; ABIERTOS.has(k) ? ABIERTOS.delete(k) : ABIERTOS.add(k); render(); }); });
  root.querySelectorAll('[data-pag]').forEach(x => { if (x._b) return; x._b = 1; x.addEventListener('click', () => { PAG += +x.dataset.pag; render(); $('s-reg').scrollIntoView(); }); });
  root.querySelectorAll('[data-lista]').forEach(x => { if (x._b) return; x._b = 1; x.addEventListener('click', () => abrir(`<h3>${esc(x.dataset.tit)}</h3>` + listaRegs(x.dataset.lista.split(',').map(i => BYID[+i])))); });
}
function opciones(sel, vals, todos, actual) { sel.innerHTML = `<option value="">${todos}</option>` + vals.map(v => `<option value="${esc(v[0])}">${esc(v[1])}</option>`).join(''); sel.value = vals.some(v => String(v[0]) === String(actual)) ? actual : ''; }
function cascada() {
  opciones($('fEsp'), [...new Set(D.equipos.map(e => e.esp))].sort().map(x => [x, x]), 'Todas', F.esp); F.esp = $('fEsp').value;
  opciones($('fArea'), [...new Set(D.equipos.filter(e => !F.esp || e.esp === F.esp).map(e => e.area))].sort().map(x => [x, x]), 'Todas', F.area); F.area = $('fArea').value;
  opciones($('fEq'), D.equipos.filter(e => (!F.esp || e.esp === F.esp) && (!F.area || e.area === F.area)).sort((a, b) => (a.area + a.eq).localeCompare(b.area + b.eq)).map(e => [e.k, `${F.area ? '' : e.area + ' · '}${e.eq}${F.esp ? '' : ' (' + e.esp.slice(0, 4) + '.)'}${e.valido ? '' : ' ⚠'}`]), 'Todos', F.eq); F.eq = $('fEq').value;
}
function leer() {
  F.sem = +$('fSem').value; F.per = $('fPer').value; F.esp = $('fEsp').value; F.area = $('fArea').value; F.eq = $('fEq').value; F.turno = $('fTurno').value;
  F.per2 = $('fPer2').value.trim(); F.tarea = $('fTarea').value.trim(); F.hall = $('fHall').value; F.red = $('fRed').value; F.est = $('fEst').value; F.cta = $('fCta').value;
}
function chipsFiltro() {
  const n = { esp: 'Especialidad', area: 'Área', eq: 'Equipo', turno: 'Turno', per2: 'Persona', tarea: 'Tarea', hall: 'Hallazgo', red: 'Redacción', est: 'Estado', cta: 'Cuenta' };
  const val = k => k === 'eq' ? (EQ[F.eq] ? EQ[F.eq].area + ' · ' + EQ[F.eq].eq : '') : F[k];
  $('chipsFiltro').innerHTML = Object.keys(n).filter(k => F[k] !== '').map(k => `<span class="chip flt clic" data-quitar="${k}">${n[k]}: ${esc(val(k))} ✕</span>`).join('') +
    (noAdh() ? '<span class="chip gray">Adherencia y categorías no aplican con estos filtros (se miden por equipo)</span>' : '');
  $('chipsFiltro').querySelectorAll('[data-quitar]').forEach(x => x.addEventListener('click', () => { const k = x.dataset.quitar; F[k] = ''; sinc(); render(); }));
}
function sinc() {
  $('fSem').value = F.sem; $('fPer').value = F.per; cascada(); $('fTurno').value = F.turno; $('fPer2').value = F.per2; $('fTarea').value = F.tarea;
  $('fHall').value = F.hall; $('fRed').value = F.red; $('fEst').value = F.est; $('fCta').value = F.cta;
}
function init() {
  const evals = ORD.filter(s => !SEM[s].piloto).reverse(), pil = ORD.filter(s => SEM[s].piloto).reverse();
  $('fSem').innerHTML = `<optgroup label="Evaluación (desde S${M.inicio})">${evals.map(s => `<option value="${s}">Semana ${s} · ${fd(SEM[s].lun)} a ${fd(SEM[s].dom)}${SEM[s].parcial ? ' (parcial)' : ''}</option>`).join('')}</optgroup>` +
    (pil.length ? `<optgroup label="Piloto / despliegue (sin adherencia)">${pil.map(s => `<option value="${s}">Semana ${s} · ${fd(SEM[s].lun)} a ${fd(SEM[s].dom)}</option>`).join('')}</optgroup>` : '');
  $('lPersonas').innerHTML = [...new Set(REG.map(r => r.per))].sort().map(p => `<option value="${esc(p)}">`).join('');
  $('hdMeta').innerHTML = `Datos hasta el <b>${M.corte.split('-').reverse().join('-')}</b> · ${REG.length} RIT<br>Semanas S${ORD[0]}–S${ORD[ORD.length - 1]} (ISO, lun–dom) · evaluación desde S${M.inicio}<br>Fuente: ${esc(M.fuente)} · generado ${esc(M.generado)}`;
  $('pie').innerHTML = 'Herramienta de consulta: no modifica SoftExpert ni el Excel. Propósito del RIT (ficha de instancia): iniciar el turno alineado, con tareas claras y riesgos controlados; producto esperado: registro del análisis de riesgo en SoftExpert con los cambios necesarios en riesgos, controles, documentos o procesos. Playbook MGO: los riesgos se revisan en el día a día durante el inicio de turno.';
  sinc();
  ['fSem', 'fPer', 'fTurno', 'fHall', 'fRed', 'fEst', 'fCta'].forEach(id => $(id).addEventListener('change', () => { leer(); PAG = 0; render(); }));
  ['fEsp', 'fArea'].forEach(id => $(id).addEventListener('change', () => { leer(); cascada(); leer(); PAG = 0; render(); }));
  $('fEq').addEventListener('change', () => { leer(); PAG = 0; render(); });
  let t; ['fPer2', 'fTarea'].forEach(id => $(id).addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { leer(); PAG = 0; render(); }, 300); }));
  $('fLimpiar').addEventListener('click', () => { Object.assign(F, { esp: '', area: '', eq: '', turno: '', per2: '', tarea: '', hall: '', red: '', est: '', cta: '' }); sinc(); PAG = 0; render(); });
  const mover = d => { const i = ORD.indexOf(F.sem) + d; if (i >= 0 && i < ORD.length) { F.sem = ORD[i]; $('fSem').value = F.sem; render(); } };
  $('semPrev').addEventListener('click', () => mover(-1)); $('semNext').addEventListener('click', () => mover(1));
  render();
}
init();
