"""
lector_maestro.py
Lee el Excel datos_fondos.xlsx y el Excel de VCP y retorna
todos los datos necesarios para generar la Ficha Única de cada fondo.

Uso como módulo:
    from lector_maestro import leer_datos_fondo, leer_vcp
    config = leer_datos_fondo("datos_fondos.xlsx", "fondo_uno")
    vcp    = leer_vcp("vcp.xlsx", "fondo_uno", clase="B")
"""

import re
import pandas as pd


def normalizar_nombre(nombre: str) -> str:
    """'Fondo Uno' → 'fondo_uno'"""
    nombre = str(nombre).strip().lower()
    nombre = re.sub(r"[áàä]", "a", nombre)
    nombre = re.sub(r"[éèë]", "e", nombre)
    nombre = re.sub(r"[íìï]", "i", nombre)
    nombre = re.sub(r"[óòö]", "o", nombre)
    nombre = re.sub(r"[úùü]", "u", nombre)
    nombre = re.sub(r"[ñ]", "n", nombre)
    nombre = re.sub(r"[^a-z0-9]+", "_", nombre)
    nombre = nombre.strip("_")
    return nombre


def leer_datos_fondo(path_excel: str, fdo_nombre: str) -> dict:
    """
    Lee la configuración de un fondo desde el Excel maestro.
    fdo_nombre puede ser el nombre normalizado o el nombre original del XML.
    Retorna dict con todos los campos de DATOS_FONDO, RENDIMIENTOS y HONORARIOS.
    """
    fdo_key = normalizar_nombre(fdo_nombre)

    xl = pd.ExcelFile(path_excel)

    # ── DATOS_FONDO ───────────────────────────────────────────────────────────
    df_datos = pd.read_excel(xl, sheet_name="DATOS_FONDO", header=2)
    # Fila 0 en el df es la fila de descripciones (índice 3 en Excel) — saltarla
    df_datos = df_datos.iloc[1:].reset_index(drop=True)
    df_datos.columns = [str(c).strip() for c in df_datos.columns]

    # Buscar la fila del fondo
    mask = df_datos["fdo_nombre"].apply(
        lambda x: normalizar_nombre(str(x)) == fdo_key
    )
    if not mask.any():
        raise ValueError(
            f"Fondo '{fdo_nombre}' (normalizado: '{fdo_key}') no encontrado "
            f"en DATOS_FONDO. Fondos disponibles: "
            f"{list(df_datos['fdo_nombre'].dropna())}"
        )
    fila = df_datos[mask].iloc[0].to_dict()

    # ── RENDIMIENTOS ──────────────────────────────────────────────────────────
    df_rend = pd.read_excel(xl, sheet_name="RENDIMIENTOS", header=2)
    df_rend = df_rend.iloc[1:].reset_index(drop=True)
    df_rend.columns = [str(c).strip() for c in df_rend.columns]

    mask_r = df_rend["fdo_nombre"].apply(
        lambda x: normalizar_nombre(str(x)) == fdo_key
    )
    rendimientos = []
    for _, row in df_rend[mask_r].iterrows():
        rendimientos.append([
            row.get("periodo", ""),
            row.get("clase_a", "") or "",
            row.get("clase_b", "") or "",
            row.get("clase_c", "") or "",
        ])

    # ── HONORARIOS ────────────────────────────────────────────────────────────
    df_hon = pd.read_excel(xl, sheet_name="HONORARIOS", header=2)
    df_hon = df_hon.iloc[1:].reset_index(drop=True)
    df_hon.columns = [str(c).strip() for c in df_hon.columns]

    mask_h = df_hon["fdo_nombre"].apply(
        lambda x: normalizar_nombre(str(x)) == fdo_key
    )
    honorarios = []
    for _, row in df_hon[mask_h].iterrows():
        honorarios.append([
            row.get("concepto", ""),
            row.get("clase_a", "") or "",
            row.get("clase_b", "") or "",
            row.get("clase_c", "") or "",
        ])

    return {
        "datos":        fila,
        "rendimientos": rendimientos,
        "honorarios":   honorarios,
    }


def leer_vcp(path_vcp: str, fdo_nombre: str, clase: str = "B",
             ultimos_dias: int = 365) -> list[list]:
    """
    Lee la evolución del valor de cuotaparte de los últimos `ultimos_dias` días.

    Busca columnas con prefijo igual al nombre normalizado del fondo:
      fondo_uno_a, fondo_uno_b, fondo_uno_c

    Si la clase solicitada no existe, cae al primer disponible (A → B → C).

    Retorna lista de [fecha_str, valor] para el gráfico.
    """
    fdo_key = normalizar_nombre(fdo_nombre)

    df = pd.read_excel(path_vcp, sheet_name=0, header=0)
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Columna de fecha
    col_fecha = df.columns[0]
    df[col_fecha] = pd.to_datetime(df[col_fecha])

    # Filtrar últimos N días
    fecha_max  = df[col_fecha].max()
    fecha_min  = fecha_max - pd.Timedelta(days=ultimos_dias)
    df = df[df[col_fecha] >= fecha_min].copy()

    # Buscar columna de la clase solicitada
    col_clase = _buscar_columna_clase(df.columns, fdo_key, clase)
    if col_clase is None:
        raise ValueError(
            f"No se encontró columna para fondo '{fdo_key}' clase '{clase}'. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    print(f"  → VCP: usando columna '{col_clase}' ({len(df)} días)")

    resultado = []
    for _, row in df.iterrows():
        fecha = row[col_fecha]
        valor = row[col_clase]
        if pd.notna(valor):
            resultado.append([
                fecha.strftime("%d/%m/%y"),
                float(valor),
            ])

    return resultado


def _buscar_columna_clase(columnas, fdo_key: str, clase_preferida: str) -> str | None:
    """
    Busca la columna VCP para un fondo y clase.
    Orden de preferencia: clase solicitada → A → B → C
    """
    clase_preferida = clase_preferida.lower()
    orden = [clase_preferida] + [c for c in ["a", "b", "c"] if c != clase_preferida]

    for clase in orden:
        # Patrones posibles: fondo_uno_a, fondo_uno_clase_a, fondo_uno-a
        candidatos = [
            f"{fdo_key}_{clase}",
            f"{fdo_key}_clase_{clase}",
        ]
        for col in columnas:
            col_norm = col.strip().lower()
            if any(col_norm == c or col_norm.endswith(f"_{clase}") and
                   col_norm.startswith(fdo_key) for c in candidatos):
                return col

    return None


def listar_fondos(path_excel: str) -> list[str]:
    """Retorna la lista de fdo_nombre disponibles en el Excel maestro."""
    df = pd.read_excel(path_excel, sheet_name="DATOS_FONDO", header=2)
    df = df.iloc[1:].reset_index(drop=True)
    return [str(v).strip() for v in df["fdo_nombre"].dropna() if str(v).strip()]


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/datos_fondos.xlsx"
    fondos = listar_fondos(path)
    print(f"Fondos en {path}: {fondos}")
    for f in fondos:
        try:
            d = leer_datos_fondo(path, f)
            print(f"\n✓ {f}: {len(d['rendimientos'])} períodos, {len(d['honorarios'])} conceptos")
        except Exception as e:
            print(f"\n✗ {f}: {e}")
