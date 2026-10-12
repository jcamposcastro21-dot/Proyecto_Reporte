"""Genera confirmacion_tbh.html a partir de la plantilla y de los catálogos
exportados desde SharePoint (sitio CL-SISSO_Plantas_Celulosa).

Uso:
    python build_catalogos.py <carpeta_con_catalogos>

La carpeta debe contener los .xlsx/.csv exportados con los nombres de abajo.
Cuando cambie un catálogo en SharePoint, se vuelve a exportar y se corre de nuevo.
"""
import csv
import json
import sys
from pathlib import Path

import openpyxl

AQUI = Path(__file__).parent


def leer(carpeta, nombre):
    ruta = carpeta / nombre
    if ruta.suffix == ".csv":
        with open(ruta, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    ws = openpyxl.load_workbook(ruta, read_only=True).active
    filas = list(ws.iter_rows(values_only=True))
    cab = [str(c) if c is not None else "" for c in filas[0]]
    return [dict(zip(cab, f)) for f in filas[1:]]


def txt(v):
    return "" if v is None else str(v)


def num(v):
    return int(float(v)) if v not in (None, "") else None


def construir(carpeta):
    c = {}
    c["plantas"] = sorted(
        ({"id": num(r["ID"]), "t": txt(r["Título"]), "p": txt(r["Planta"])}
         for r in leer(carpeta, "Planta_Celulosa_2.xlsx") if r.get("Título")),
        key=lambda x: x["t"])
    c["areas"] = sorted(
        ({"t": txt(r["Titulo"]), "p": txt(r["Planta"])}
         for r in leer(carpeta, "Areas Plantas.xlsx") if r.get("Titulo")),
        key=lambda x: x["t"].strip())
    c["empresas"] = sorted(txt(r["Título"]) for r in leer(carpeta, "Empresas.xlsx") if r.get("Título"))
    c["equipos"] = sorted(
        ({"id": num(r["ID"]), "t": txt(r["Columna1"]), "e": txt(r["Empresa"]), "p": txt(r["Planta"])}
         for r in leer(carpeta, "Equipos Seguros.xlsx") if r.get("Columna1")),
        key=lambda x: (x["t"] + " - " + x["e"]).lower())
    c["areasPgp"] = sorted(
        ({"t": txt(r["Título"]), "c": txt(r["Codigo_area"]), "p": txt(r["Planta"])}
         for r in leer(carpeta, "Areas_PGP.xlsx") if r.get("Título")),
        key=lambda x: x["t"] + " - " + x["c"])
    c["sistemas"] = sorted(
        ({"t": txt(r["Título"]), "c": txt(r["Codigo_sistema"]), "p": txt(r["Planta"])}
         for r in leer(carpeta, "Sistema_PGP.xlsx") if r.get("Título")),
        key=lambda x: x["c"] + " - " + x["t"])
    c["ot"] = sorted(
        ({"t": txt(r["Título"]), "x": txt(r["Texto"])}
         for r in leer(carpeta, "OT_PGP.xlsx") if r.get("Estado") == "Activo" and r.get("Título")),
        key=lambda x: x["x"])
    c["ambitos"] = [{"id": num(r["ID"]), "t": txt(r["Título"])} for r in leer(carpeta, "Ámbito.csv")]
    c["eventos"] = sorted(
        ({"t": txt(r["Title"]), "a": txt(r["Ambito"])}
         for r in leer(carpeta, "Evento.xlsx") if r.get("Title")),
        key=lambda x: x["t"])
    c["accInm"] = [{"id": num(r["ID"]), "t": txt(r["Título"]).strip()} for r in leer(carpeta, "Acciones_Inmediatas.xlsx")]
    c["accCor"] = [{"id": num(r["ID"]), "t": txt(r["Título"]).strip()} for r in leer(carpeta, "Acciones_Correctivas.xlsx")]
    c["lideres"] = sorted(
        ({"id": num(r["ID"]), "n": txt(r["Lider"] or r["Título"])}
         for r in leer(carpeta, "Correo_Lideres.xlsx") if r.get("Lider") or r.get("Título")),
        key=lambda x: x["n"])
    return c


def main():
    carpeta = Path(sys.argv[1])
    catalogos = construir(carpeta)
    plantilla = (AQUI / "plantilla.html").read_text(encoding="utf-8")
    datos = json.dumps(catalogos, ensure_ascii=False, separators=(",", ":"))
    html = plantilla.replace("/*__CATALOGOS__*/{}", datos)
    (AQUI / "confirmacion_tbh.html").write_text(html, encoding="utf-8")
    for k, v in catalogos.items():
        print(f"{k}: {len(v)}")


if __name__ == "__main__":
    main()
