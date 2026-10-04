"""Carga de datos RdP.

Hoy la fuente es el Excel exportado (hojas `Registros` y `Acciones`). Cuando haya
acceso a la base que alimenta los QVD, basta con agregar un cargador nuevo que
devuelva los mismos dos DataFrames con las columnas de `COLS_REGISTROS` y
`COLS_ACCIONES`; el resto del reporte no cambia.
"""
from pathlib import Path
import pandas as pd

COLS_REGISTROS = ['Id', 'Planta', 'NAT', 'Área Responsable', 'Evento tiempo perdido',
                  'Herramienta', 'Líder responsable', 'Fecha Inicio', 'Estado', '¿Se utilizó SAR?']
COLS_ACCIONES = ['RegistroId', 'AccionId', 'Tipo causa raíz', 'Causa raíz', 'Acción', 'Responsable',
                 'Estado ejecución', 'Fecha Compromiso', 'Estado cumplimiento', 'Fecha cierre', 'Cerrada por']


def cargar_excel(ruta):
    x = pd.ExcelFile(ruta)
    return x.parse('Registros'), x.parse('Acciones')


def cargar_qvd(ruta_registros, ruta_acciones):
    """QVD exportados por Qlik. Requiere `pip install pyqvd`."""
    from pyqvd import QvdTable
    return (QvdTable.from_qvd(ruta_registros).to_pandas(),
            QvdTable.from_qvd(ruta_acciones).to_pandas())


def cargar_sql(url, sql_registros, sql_acciones):
    """Base de origen de los QVD. `url` en formato SQLAlchemy; las consultas deben
    devolver (o renombrar con AS) las columnas del contrato."""
    import sqlalchemy
    eng = sqlalchemy.create_engine(url)
    with eng.connect() as c:
        return pd.read_sql(sql_registros, c), pd.read_sql(sql_acciones, c)


def ultimo_excel(carpeta='data'):
    xs = sorted(Path(carpeta).glob('RDP_Completo_*.xlsx'))
    if not xs:
        raise FileNotFoundError(f'No hay RDP_Completo_*.xlsx en {carpeta}/')
    return xs[-1]


def normalizar(reg, acc):
    """Valida el contrato de columnas y normaliza tipos y espacios."""
    faltan = [c for c in COLS_REGISTROS if c not in reg] + [c for c in COLS_ACCIONES if c not in acc]
    if faltan:
        raise ValueError(f'Faltan columnas en la fuente: {faltan}')
    reg, acc = reg[COLS_REGISTROS].copy(), acc[COLS_ACCIONES].copy()
    for c in ['Fecha Inicio']:
        reg[c] = pd.to_datetime(reg[c]).dt.normalize()
    for c in ['Fecha Compromiso', 'Fecha cierre']:
        acc[c] = pd.to_datetime(acc[c]).dt.normalize()
    for df, cols in ((reg, ['Planta', 'NAT', 'Área Responsable', 'Líder responsable', 'Estado', '¿Se utilizó SAR?']),
                     (acc, ['Responsable', 'Cerrada por', 'Estado ejecución'])):
        for c in cols:
            df[c] = df[c].map(lambda s: ' '.join(str(s).split()) if pd.notna(s) else s)
    return reg, acc
