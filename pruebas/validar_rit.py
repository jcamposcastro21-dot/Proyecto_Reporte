"""Validación lógica del reporte RIT en el navegador (punto 25 de la especificación).
Uso: python3 pruebas/validar_rit.py out/RIT_semanal_Nueva_Aldea.html
Requiere playwright; usa el Chromium indicado en CHROMIUM o el de Playwright por defecto."""
import json, os, sys
from playwright.sync_api import sync_playwright
JS = r"""() => {
 const out = []; const ok = (c, t) => out.push((c ? 'OK  ' : 'FALLA ') + t);
 const reset = () => { Object.assign(F, {sem: M.defecto, per: 'sem', esp:'', area:'', eq:'', turno:'', per2:'', tarea:'', hall:'', red:'', est:'', cta:''}); };
 reset();
 // 1. porcentajes = numerador/denominador
 const K = calc(regs(periodo())), A = adherencia(periodo());
 ok(A.p === Math.round(100*A.n/A.N), `adherencia ${A.p}% = ${A.n}/${A.N}`);
 ok(K.ind + K.comp + K.sinid === K.N, `trazabilidad: ${K.ind}+${K.comp}+${K.sinid} = ${K.N} RIT`);
 ok(K.con + K.sin === K.N, `con hallazgo ${K.con} + sin hallazgo ${K.sin} = ${K.N}`);
 ok(K.d.reduce((a,b)=>a+b,0) === K.con, `distribución 0-3 suma ${K.con} hallazgos`);
 ok(K.ent === K.d[2]+K.d[3] && K.acc === K.d[3], 'entendibles = 2+3; accionables = 3');
 ok(K.lista <= K.d[0], `listas copiadas (${K.lista}) incluidas en nota 0 (${K.d[0]})`);
 // 10/11. consistencia semanal y jerárquica
 const w4 = hasta(F.sem, 4, false), A4 = adherencia(w4); let sn = 0, sN = 0; w4.forEach(s => { const a = adherencia([s]); sn += a.n; sN += a.N; });
 ok(Math.abs(sn - A4.n) < 1e-6 && Math.abs(sN - A4.N) < 1e-6, `suma semanal (${sn}/${sN}) = 4 semanas (${A4.n}/${A4.N})`);
 let en = 0, eN = 0; Object.values(A.por).forEach(v => { en += v.n; eN += v.N; });
 ok(en === A.n && eN === A.N, 'suma por equipo = total planta (adherencia)');
 const esps = [...new Set(D.equipos.map(e => e.esp))]; let rn = 0; esps.forEach(es => { F.esp = es; rn += calc(regs(periodo())).N; }); reset();
 ok(rn === K.N, `suma por especialidad (${rn}) = total RIT (${K.N})`);
 // 2. los filtros modifican los resultados
 F.area = 'Efluentes'; const Ka = calc(regs(periodo())), Aa = adherencia(periodo()); reset();
 ok(Ka.N < K.N && Aa.N < A.N, `filtro área Efluentes: ${Ka.N} RIT, adherencia ${Aa.n}/${Aa.N}`);
 F.turno = 'C'; const Kt = calc(regs(periodo())); ok(Kt.N > 0 && regs(periodo()).every(r => r.e.tl === 'C'), `filtro turno C: ${Kt.N} RIT, todos del turno C`); reset();
 F.cta = 'comp'; const Kc = calc(regs(periodo())); ok(Kc.N === K.comp && adherencia(periodo()).na, 'filtro cuenta compartida = KPI compartidas y adherencia no aplica'); reset();
 F.red = '3'; ok(regs(periodo()).every(r => r.h && r.n === 3) && regs(periodo()).length === K.d[3], 'filtro redacción 3 = distribución'); reset();
 F.hall = 'sin'; ok(regs(periodo()).length === K.sin, 'filtro sin hallazgo = KPI sin hallazgo'); reset();
 F.per = '4s'; ok(calc(regs(periodo())).N > K.N, 'período 4 semanas > 1 semana'); reset();
 // 4. cuentas compartidas no atribuidas a personas
 const comp = new Set(REG.filter(r => r.cta === 'comp').map(r => r.per));
 ok([...comp].every(p => /^(operador|despachador|volante)/i.test(p)), 'cuentas compartidas detectadas: ' + [...comp].join(', '));
 render(); const perInd = [...document.querySelectorAll('#s-per .two-col [data-per]')].map(x => x.dataset.per);
 ok(perInd.every(p => !comp.has(p)), `ninguna cuenta compartida en los rankings de personas (${perInd.length} filas)`);
 // 5. sin hallazgo no es malo: equipos sin hallazgos no caen en "Requieren apoyo"
 const apoyo = [...document.querySelectorAll('#s-cat .cq-red [data-eq]')].map(x => +x.dataset.eq);
 const sinH = apoyo.filter(k => !regs(ventana4()).some(r => r.k === k && r.h));
 ok(sinH.length === 0, `"Requieren apoyo" no incluye equipos solo por no tener hallazgos (${apoyo.length} equipos)`);
 // 6. claridad ≠ pertinencia
 ok(document.querySelector('#s-resumen').innerText.includes('Pendiente de validación técnica'), 'pertinencia técnica = pendiente de validación');
 // 7. muestras pequeñas identificables
 ok(document.querySelectorAll('.mr').length > 0, `${document.querySelectorAll('.mr').length} marcas de muestra reducida`);
 // 9. ejemplos reales
 const ej = [...document.querySelectorAll('#s-n3 .ej[data-reg]')]; ok(ej.length > 0 && ej.every(x => { const r = BYID[+x.dataset.reg]; const q = x.querySelector('.q').innerText.replace(/[«»]/g,'').replace(/\s+/g,' ').trim().slice(0,40); return r && r.it.some(i => i.x.replace(/\s+/g,' ').includes(q)); }), `${ej.length} ejemplos coinciden con el texto del RIT de origen`);
 // 11. drill-down equipo = tabla
 const k0 = +Object.keys(A.por)[5]; const fila = adherencia(periodo(), e => e.k === k0); ok(fila.n === A.por[k0].n && fila.N === A.por[k0].N, `drill-down equipo ${EQ[k0].area} ${EQ[k0].eq}: ${fila.n}/${fila.N}`);
 // semanas sin turno no penalizan
 const sinTurno = Object.entries(A.por).filter(([k, v]) => v.N === 0); ok(sinTurno.every(([k, v]) => v.n === 0), `${sinTurno.length} equipos sin turno en la semana: esperado 0, no penalizados`);
 // tope por equipo-semana
 ok(Object.values(A.por).every(v => v.n <= v.N), 'realizados ≤ esperados en todos los equipos');
 // pilotos
 F.sem = 20; ok(adherencia(periodo()).na && adherencia(periodo()).na.includes('piloto'), 'S20 (piloto): adherencia no evaluada'); reset();
 return out;
}"""
with sync_playwright() as p:
    import os; b = p.chromium.launch(**({'executable_path': os.environ['CHROMIUM']} if os.environ.get('CHROMIUM') else {})); pg = b.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('file://' + os.path.abspath(sys.argv[1])); pg.wait_for_timeout(800)
    for l in pg.evaluate(JS): print(l)
    print('errores JS:', errs)
