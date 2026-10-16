"""Genera la aplicación Liderazgo Visible (un solo .html) a partir de plantilla.html y de los
catálogos .json que deja el flujo Exportar_Catalogos en la carpeta Catalogos.

Uso:
    python build_app.py <carpeta_catalogos> <salida.html> [--flow-url URL]

Sin --flow-url la aplicación queda en MODO PRUEBA (muestra lo que enviaría, no guarda nada).

El .html generado contiene datos internos y, si se indica, la URL del flujo: NO subirlo al
repositorio.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).parent

# Columnas de opción cuyas alternativas se leen de la definición de la lista en SharePoint.
OPCIONES = {
    "instancias": ("campos_instancias.json",
                   ["Instancias", "Serealizo", "Inicioreu", "Finalreu", "Asistentes", "Cumplerol"]),
    "coaching": ("campos_coaching.json",
                 ["P1_El_lider_planifico_el_contact", "P2_En_terreno_x002c__el_lider_ex",
                  "P3_El_lider_observo_y_reconocio_", "P4_El_lider_realizo_la_conversac",
                  "P5_El_lider_logro_un_dialogo_sob", "P6_El_lider_realizo_preguntas_ab",
                  "P8_El_lider_logro_que_los_trabaj", "_x0050_10"]),
}


def leer(carpeta, nombre):
    return json.loads((carpeta / nombre).read_text(encoding="utf-8"))


def txt(v):
    return "" if v is None else str(v).strip()


def opciones(carpeta):
    resultado = {}
    for clave, (archivo, campos) in OPCIONES.items():
        por_nombre = {f["InternalName"]: f for f in leer(carpeta, archivo)}
        resultado[clave] = {}
        for campo in campos:
            choices = (por_nombre.get(campo) or {}).get("Choices")
            if not choices:
                raise SystemExit(f"No encontré las opciones de la columna {campo} en {archivo}.")
            resultado[clave][campo] = choices
    return resultado


def construir(carpeta):
    ambitos = {a["ID"]: txt(a["Title"]) for a in leer(carpeta, "ambitos.json")}
    c = {}
    c["plantas"] = sorted(
        ({"id": p["ID"], "t": txt(p["Title"]), "p": txt(p["Planta"])} for p in leer(carpeta, "plantas.json")),
        key=lambda x: x["t"])
    c["areas"] = sorted(
        ({"id": a["ID"], "t": a["Title"], "p": txt(a.get("field_0")), "pid": a.get("Planta_x002a_Id")}
         for a in leer(carpeta, "areas.json") if txt(a.get("Title"))),
        key=lambda x: x["t"].strip())
    c["empresas"] = [{"id": e["ID"], "t": txt(e["Title"])} for e in leer(carpeta, "empresas.json")]
    c["equipos"] = sorted(
        ({"id": e["ID"], "t": txt(e["Title"]), "e": txt(e.get("field_1")), "p": txt(e.get("field_0")),
          "pid": e.get("Planta_x002a_Id")}
         for e in leer(carpeta, "equipos.json") if txt(e.get("Title"))),
        key=lambda x: (x["t"] + " - " + x["e"]).lower())
    c["areasPgp"] = sorted(
        ({"t": txt(a["Title"]), "c": txt(a.get("Codigoarea")), "p": txt(a.get("Planta"))}
         for a in leer(carpeta, "areas_pgp.json") if txt(a.get("Title"))),
        key=lambda x: x["t"] + " - " + x["c"])
    c["sistemas"] = sorted(
        ({"t": txt(s["Title"]), "c": txt(s.get("Codigo_sistema")), "p": txt(s.get("Planta"))}
         for s in leer(carpeta, "sistemas_pgp.json") if txt(s.get("Title"))),
        key=lambda x: x["c"] + " - " + x["t"])
    # Igual que la Power App: solo OT activas, de todas las plantas, ordenadas por Texto.
    c["ot"] = sorted(
        ({"t": txt(o["Title"]), "x": txt(o.get("Texto"))}
         for o in leer(carpeta, "ot_pgp.json") if o.get("Estado") == "Activo" and txt(o.get("Title"))),
        key=lambda x: x["x"])
    c["ambitos"] = [{"id": k, "t": v} for k, v in sorted(ambitos.items())]
    c["eventos"] = sorted(
        ({"t": e["Title"], "a": e.get("AmbitoId")}
         for e in leer(carpeta, "eventos.json") if txt(e.get("Title")) and e.get("Presentar") is not False),
        key=lambda x: x["t"])
    c["accInm"] = [{"id": a["ID"], "t": txt(a["Title"])} for a in leer(carpeta, "acciones_inmediatas.json")]
    c["accCor"] = [{"id": a["ID"], "t": txt(a["Title"])} for a in leer(carpeta, "acciones_correctivas.json")]
    # u = ID del usuario en el sitio (lo que guardan las columnas Persona).
    lideres = [{"u": l["LiderId"], "n": txt((l.get("Lider") or {}).get("Title") or l.get("Title")),
                "m": txt((l.get("Lider") or {}).get("EMail")).lower()}
               for l in leer(carpeta, "lideres.json") if l.get("LiderId")]
    vistos = {}
    for l in lideres:
        vistos[l["n"]] = vistos.get(l["n"], 0) + 1
    for l in lideres:   # nombres repetidos: se distinguen por el correo
        if vistos[l["n"]] > 1 and l["m"]:
            l["n"] = f'{l["n"]} ({l["m"]})'
    c["lideres"] = sorted(({"u": l["u"], "n": l["n"]} for l in lideres if l["n"]), key=lambda x: x["n"])
    c["opciones"] = opciones(carpeta)
    c["generado"] = datetime.now().strftime("%d-%m-%Y %H:%M")
    return c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", type=Path, help="carpeta con los .json de Catalogos")
    ap.add_argument("salida", type=Path, help="archivo .html a generar (fuera del repositorio)")
    ap.add_argument("--flow-url", default="", help="URL del disparador del flujo de guardado")
    args = ap.parse_args()

    catalogos = construir(args.carpeta)
    html = (AQUI / "plantilla.html").read_text(encoding="utf-8")
    for marca in ("/*__CATALOGOS__*/{}", '"__FLOW_URL__"'):
        if html.count(marca) != 1:
            raise SystemExit(f"La plantilla debe contener una vez {marca}.")
    datos = json.dumps(catalogos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__CATALOGOS__*/{}", datos)
    if args.flow_url:
        html = html.replace('"__FLOW_URL__"', json.dumps(args.flow_url))
    args.salida.write_text(html, encoding="utf-8")

    for k, v in catalogos.items():
        if isinstance(v, list):
            print(f"{k}: {len(v)}")
    print("Modo:", "guardado real" if args.flow_url else "PRUEBA (sin URL del flujo)")
    print("Generado:", args.salida)


if __name__ == "__main__":
    main()
