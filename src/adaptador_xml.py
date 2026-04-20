"""
adaptador_xml.py
Extrae desde el XML de cartera (formato CNV/CAFCI):
  - Tenencias principales (top N, expresadas en moneda del fondo)
  - Composición de cartera por subclase (<SCl>)
  - Clases disponibles (solo A, B, C)
  - Tipo de cambio del día
  - Moneda del fondo
  - Patrimonio neto total
  - Fecha del informe

Uso standalone:
    python adaptador_xml.py --input fondoprueba1.xml

Uso como módulo:
    from adaptador_xml import extraer_datos_xml
    datos = extraer_datos_xml("fondoprueba1.xml")
"""

import re
import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict

# Clases que se muestran en la Ficha Única (en orden)
CLASES_FICHA = ["A", "B", "C"]

# Colores por defecto para subclases en el gráfico de torta
COLORES_SUBCLASE = [
    "#2E75B6", "#ED7D31", "#A9D18E", "#FFC000",
    "#5A5A5A", "#70AD47", "#FF0000", "#9E480E",
    "#997300", "#43682B", "#264478", "#FF66FF",
]


def _fix_xml(content: str) -> str:
    """Corrige tags mal cerrados que puede tener el XML del sistema."""
    content = re.sub(r'</RenImpD\s*\n', '</RenImpD>\n', content)
    return content


def _parse_float(val) -> float:
    if val is None or str(val).strip() in ("", "None"):
        return 0.0
    try:
        return float(str(val).strip())
    except ValueError:
        return 0.0


def extraer_datos_xml(path: str, top_n: int = 10) -> dict:
    """
    Parsea el XML y retorna un dict con:
      {
        "moneda_fondo":    str,           # "ARS" o "USD"
        "moneda_fondo_nom": str,          # nombre completo
        "fecha_info":      str,           # "2026-03-10"
        "fondo_nombre":    str,
        "pn_total":        float,         # patrimonio neto en moneda del fondo
        "tc_compra":       dict,          # {"USD": float, "USB": float}
        "clases":          list[dict],    # solo A/B/C si existen
        "tenencias":       list[list],    # [[nombre, monto_fdo, pct], ...]
        "composicion":     list[dict],    # [{"categoria", "porcentaje", "color"}, ...]
      }
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    root = ET.fromstring(_fix_xml(content))

    # ── Identificación del fondo ──────────────────────────────────────────────
    moneda_fondo_nom = root.findtext(".//MonFdoNom") or "Peso Argentina"
    moneda_fondo_cod = "USD" if "dolar" in moneda_fondo_nom.lower() else "ARS"
    fecha_info       = root.findtext(".//FechaInfo") or ""
    fondo_nombre     = root.findtext(".//FdoNom") or ""

    # ── Tipos de cambio (usamos TCambioCod="C" = compra) ────────────────────
    tc_compra = {}
    for tc in root.findall(".//TCambio"):
        if tc.findtext("TCambioCod") == "C":
            mon_o   = tc.findtext("MonOCod")   # USD o USB
            cant_o  = _parse_float(tc.findtext("MonOCant"))
            cant_d  = _parse_float(tc.findtext("MonDCant"))
            if cant_o and cant_d:
                tc_compra[mon_o] = cant_d / cant_o   # ARS por 1 unidad extranjera
    # Si el fondo es en USD, necesitamos el inverso (cuántos USD por 1 ARS)
    # pero MtoMFdo ya viene convertido, así que solo usamos tc para validación

    # ── Clases (solo A, B, C) ────────────────────────────────────────────────
    clases = []
    for vd in root.findall(".//VDiario"):
        nombre_clase = vd.findtext("ClaseNom") or ""
        # Determinar si es Clase A, B o C
        letra = _detectar_letra_clase(nombre_clase)
        if letra not in CLASES_FICHA:
            continue
        clases.append({
            "letra":    letra,
            "nombre":   nombre_clase,
            "vcp":      _parse_float(vd.findtext("VCP")),
            "pn":       _parse_float(vd.findtext("PNMFdo")),
            "vcp_prev": _parse_float(vd.findtext("VCPr")),
            "ren_dia":  _parse_float(vd.findtext("RenImpD")),
        })
    # Ordenar A → B → C
    clases.sort(key=lambda x: CLASES_FICHA.index(x["letra"]))

    # ── Patrimonio neto total ────────────────────────────────────────────────
    pn_total = _parse_float(root.findtext(".//PNTotal"))

    # ── Activos: tenencias y composición ────────────────────────────────────
    activos = root.findall(".//Activo")

    tenencias_raw  = []
    composicion_raw = defaultdict(float)

    for a in activos:
        nombre  = a.findtext("ActNom") or ""
        scl     = a.findtext("SCl")    or "Otros"
        mto_fdo = _parse_float(a.findtext("MtoMFdo"))  # ya en moneda del fondo

        # Acumular composición por subclase
        composicion_raw[scl] += mto_fdo

        # Agregar a tenencias (incluye disponibilidades)
        if mto_fdo != 0:
            tenencias_raw.append({
                "instrumento": nombre,
                "subclase":    scl,
                "mto_fdo":     mto_fdo,
            })

    # Calcular total activos para los porcentajes
    total_activos = _parse_float(root.findtext(".//ActTotal"))
    base_pct = total_activos if total_activos else sum(
        abs(t["mto_fdo"]) for t in tenencias_raw)

    # Ordenar tenencias por valor absoluto descendente, tomar top N
    tenencias_raw.sort(key=lambda x: abs(x["mto_fdo"]), reverse=True)
    tenencias_top = tenencias_raw[:top_n]

    tenencias = [
        [
            t["instrumento"],
            t["mto_fdo"],
            round(t["mto_fdo"] / base_pct * 100, 2) if base_pct else 0,
        ]
        for t in tenencias_top
    ]

    # Composición: calcular porcentajes sobre activo total
    composicion = []
    for i, (scl, mto) in enumerate(
        sorted(composicion_raw.items(), key=lambda x: -x[1])
    ):
        pct = round(mto / total_activos * 100, 2) if total_activos else 0
        composicion.append({
            "categoria":   scl,
            "porcentaje":  pct,
            "color":       COLORES_SUBCLASE[i % len(COLORES_SUBCLASE)],
        })

    return {
        "moneda_fondo":     moneda_fondo_cod,
        "moneda_fondo_nom": moneda_fondo_nom,
        "fecha_info":       fecha_info,
        "fondo_nombre":     fondo_nombre,
        "pn_total":         pn_total,
        "tc_compra":        tc_compra,
        "clases":           clases,
        "tenencias":        tenencias,
        "composicion":      composicion,
    }


def _detectar_letra_clase(nombre: str) -> str:
    """
    Detecta la letra de clase a partir del nombre del VDiario.
    Ejemplos:
      "Fondo Uno - Clase A"  → "A"
      "Fondo Uno - Clase B"  → "B"
      "Fondo Uno - Clase C"  → "C"
      "Fondo Uno - Clase D"  → "D"  (se excluirá)
    """
    nombre_upper = nombre.upper()
    # Buscar patrón "CLASE X" donde X es una letra
    m = re.search(r'CLASE\s+([A-Z])\b', nombre_upper)
    if m:
        return m.group(1)
    # Fallback: última letra mayúscula aislada al final
    m = re.search(r'\b([A-Z])\s*$', nombre.strip())
    if m:
        return m.group(1)
    return "?"


def imprimir_resumen(datos: dict):
    print(f"\n{'='*65}")
    print(f"  Fondo: {datos['fondo_nombre']}")
    print(f"  Fecha: {datos['fecha_info']}  |  Moneda: {datos['moneda_fondo_nom']}")
    print(f"  PN Total: {datos['pn_total']:>20,.2f} {datos['moneda_fondo']}")
    print(f"{'='*65}")

    print(f"\n--- CLASES (Ficha Única) ---")
    if datos["clases"]:
        for c in datos["clases"]:
            print(f"  Clase {c['letra']}: VCP={c['vcp']:,.4f}  PN={c['pn']:,.2f}")
    else:
        print("  (No se encontraron clases A, B o C)")

    print(f"\n--- TIPOS DE CAMBIO (compra) ---")
    for mon, tc in datos["tc_compra"].items():
        print(f"  1 {mon} = {tc:,.2f} ARS")

    print(f"\n--- PRINCIPALES TENENCIAS (top {len(datos['tenencias'])}) ---")
    print(f"  {'INSTRUMENTO':<45} {'MONTO FONDO':>18} {'%':>8}")
    print(f"  {'-'*73}")
    for t in datos["tenencias"]:
        print(f"  {t[0]:<45} {t[1]:>18,.2f} {t[2]:>7.2f}%")

    print(f"\n--- COMPOSICIÓN POR SUBCLASE ---")
    for c in datos["composicion"]:
        print(f"  {c['categoria']:<40} {c['porcentaje']:>7.2f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extrae datos de cartera desde XML CNV/CAFCI")
    parser.add_argument("--input", required=True,
                        help="Ruta al archivo XML")
    parser.add_argument("--top", type=int, default=10,
                        help="Cantidad de tenencias a mostrar (default: 10)")
    args = parser.parse_args()

    datos = extraer_datos_xml(args.input, top_n=args.top)
    imprimir_resumen(datos)
