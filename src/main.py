"""
main.py — Orquestador de generación de Fichas Únicas CNV (RG 1121/2026)

Procesa uno o todos los fondos combinando:
  - datos_fondos.xlsx  → configuración, rendimientos, honorarios
  - vcp.xlsx           → evolución diaria del valor de cuotaparte
  - xml/               → cartera, tenencias, composición (un XML por fondo)

Uso:
  # Generar todos los fondos:
  python main.py --datos data/datos_fondos.xlsx --vcp data/vcp.xlsx --xml_dir xml/

  # Generar un solo fondo:
  python main.py --datos data/datos_fondos.xlsx --vcp data/vcp.xlsx --xml_dir xml/ --fondo fondo_uno

  # Generar sin XML (tenencias y composición desde el Excel):
  python main.py --datos data/datos_fondos.xlsx --vcp data/vcp.xlsx
"""

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lector_maestro import leer_datos_fondo, leer_vcp, listar_fondos, normalizar_nombre
from adaptador_xml   import extraer_datos_xml
from generar_factsheet import construir_pdf


def encontrar_xml(xml_dir: str, fdo_nombre: str) -> str | None:
    """
    Busca el XML del fondo en xml_dir.
    Estrategia: normaliza el <FdoNom> de cada XML y compara con fdo_nombre.
    """
    import re, xml.etree.ElementTree as ET

    fdo_key = normalizar_nombre(fdo_nombre)
    xml_dir = Path(xml_dir)

    for xml_file in sorted(xml_dir.glob("*.xml")):
        try:
            with open(xml_file, "r", encoding="utf-8") as f:
                content = re.sub(r'</RenImpD\s*\n', '</RenImpD>\n', f.read())
            root = ET.fromstring(content)
            nombre_xml = root.findtext(".//FdoNom") or ""
            if normalizar_nombre(nombre_xml) == fdo_key:
                return str(xml_file)
        except Exception:
            continue
    return None


def generar_fondo(fdo_nombre: str, path_datos: str, path_vcp: str,
                  xml_dir: str | None, output_dir: str) -> bool:
    """
    Genera la Ficha Única de un fondo. Retorna True si tuvo éxito.
    """
    print(f"\n{'─'*60}")
    print(f"  Procesando: {fdo_nombre}")
    print(f"{'─'*60}")

    try:
        # 1. Leer configuración del Excel maestro
        config = leer_datos_fondo(path_datos, fdo_nombre)
        datos      = config["datos"]
        rendimientos = config["rendimientos"]
        honorarios   = config["honorarios"]
        print(f"  ✓ Datos cargados desde Excel maestro")

        # 2. Leer VCP diario
        clase_grafico = str(datos.get("clase_grafico_vcp", "B") or "B").strip().upper()
        evolucion = leer_vcp(path_vcp, fdo_nombre, clase=clase_grafico)
        print(f"  ✓ VCP cargado — {len(evolucion)} días, Clase {clase_grafico}")

        # 3. Cartera desde XML (si está disponible)
        composicion = []
        tenencias   = []

        if xml_dir:
            xml_path = encontrar_xml(xml_dir, fdo_nombre)
            if xml_path:
                print(f"  ✓ XML encontrado: {Path(xml_path).name}")
                xml_data    = extraer_datos_xml(xml_path, top_n=10)
                tenencias   = xml_data["tenencias"]
                composicion = [
                    [c["categoria"], c["porcentaje"], c["color"]]
                    for c in xml_data["composicion"]
                ]
                # Enriquecer datos con patrimonio neto del XML
                datos["patrimonio_neto"] = f"$ {xml_data['pn_total']:,.2f}"
                print(f"  ✓ {len(tenencias)} tenencias, {len(composicion)} subclases de cartera")
            else:
                print(f"  ⚠ XML no encontrado para '{fdo_nombre}' — cartera vacía")
        else:
            print(f"  ⚠ Sin directorio XML — cartera vacía")

        # 4. Generar PDF
        fdo_key     = normalizar_nombre(fdo_nombre)
        fecha_rep   = str(datos.get("fecha_reporte", "")).replace("/", "-")
        output_path = os.path.join(output_dir, f"ficha_{fdo_key}_{fecha_rep}.pdf")

        construir_pdf(
            datos, rendimientos, composicion, tenencias,
            honorarios, evolucion, output_path
        )
        print(f"  ✓ PDF generado: {output_path}")
        return True

    except Exception as e:
        print(f"  ✗ Error procesando '{fdo_nombre}': {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generador de Fichas Únicas CNV — Multi-fondo")
    parser.add_argument("--datos",   required=True,
                        help="Excel maestro (datos_fondos.xlsx)")
    parser.add_argument("--vcp",     required=True,
                        help="Excel con evolución diaria de cuotapartes (vcp.xlsx)")
    parser.add_argument("--xml_dir", default=None,
                        help="Carpeta con XMLs de cartera (uno por fondo)")
    parser.add_argument("--fondo",   default=None,
                        help="Procesar solo este fondo (nombre normalizado). "
                             "Si no se especifica, procesa todos.")
    parser.add_argument("--output",  default="output",
                        help="Carpeta de salida para los PDFs (default: output/)")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # Determinar qué fondos procesar
    if args.fondo:
        fondos = [args.fondo]
    else:
        fondos = listar_fondos(args.datos)
        print(f"Fondos encontrados en el Excel: {fondos}")

    # Procesar
    resultados = {}
    for fdo in fondos:
        ok = generar_fondo(
            fdo_nombre=fdo,
            path_datos=args.datos,
            path_vcp=args.vcp,
            xml_dir=args.xml_dir,
            output_dir=args.output,
        )
        resultados[fdo] = "✓ OK" if ok else "✗ ERROR"

    # Resumen final
    print(f"\n{'═'*60}")
    print(f"  RESUMEN")
    print(f"{'═'*60}")
    for fdo, estado in resultados.items():
        print(f"  {estado}  {fdo}")
    print(f"{'═'*60}")
    exitosos = sum(1 for v in resultados.values() if "OK" in v)
    print(f"  {exitosos}/{len(resultados)} fondos generados correctamente")


if __name__ == "__main__":
    main()
