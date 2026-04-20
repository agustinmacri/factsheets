"""
generar_factsheet.py
Genera la Ficha Única CNV — RG 1121/2026 — Anexo III en formato PDF.

Soporta ambos modelos:
  - Fondos Comunes de Dinero (Money Market)
  - Otros FCI (distintos de Fondos de Dinero)

No se usa directamente — es invocado por main.py a través de construir_pdf().
"""

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)

# ── Paleta de colores ─────────────────────────────────────────────────────────
AZUL_CNV   = colors.HexColor("#1F4E79")
AZUL_MEDIO = colors.HexColor("#2E75B6")
GRIS_CLARO = colors.HexColor("#F2F2F2")
GRIS_BORDE = colors.HexColor("#BFBFBF")
NEGRO      = colors.HexColor("#1A1A1A")
BLANCO     = colors.white


# ── Estilos de texto ──────────────────────────────────────────────────────────
def make_styles():
    return {
        "titulo_seccion": ParagraphStyle(
            "titulo_seccion", fontName="Helvetica-Bold", fontSize=7,
            textColor=BLANCO, alignment=TA_CENTER, leading=10,
        ),
        "label": ParagraphStyle(
            "label", fontName="Helvetica", fontSize=7,
            textColor=NEGRO, leading=9,
        ),
        "small": ParagraphStyle(
            "small", fontName="Helvetica", fontSize=6,
            textColor=colors.HexColor("#595959"), leading=8,
        ),
        "objetivo": ParagraphStyle(
            "objetivo", fontName="Helvetica", fontSize=6.5,
            textColor=NEGRO, leading=9, alignment=TA_JUSTIFY,
        ),
        "header_col": ParagraphStyle(
            "header_col", fontName="Helvetica-Bold", fontSize=6.5,
            textColor=BLANCO, alignment=TA_CENTER, leading=8,
        ),
        "celda": ParagraphStyle(
            "celda", fontName="Helvetica", fontSize=6.5,
            textColor=NEGRO, alignment=TA_CENTER, leading=8,
        ),
        "celda_izq": ParagraphStyle(
            "celda_izq", fontName="Helvetica", fontSize=6.5,
            textColor=NEGRO, alignment=TA_LEFT, leading=8,
        ),
        "leyenda": ParagraphStyle(
            "leyenda", fontName="Helvetica", fontSize=5.5,
            textColor=NEGRO, leading=7.5, alignment=TA_JUSTIFY,
        ),
    }


# ── Gráfico de torta — composición de cartera ────────────────────────────────
def grafico_torta(composicion, ancho_px=260, alto_px=160):
    if not composicion:
        return _imagen_vacia(ancho_px, alto_px)

    labels  = [r[0] for r in composicion]
    sizes   = [abs(float(str(r[1]).replace("%", "").replace(",", "."))) for r in composicion]
    default_colors = ["#2E75B6", "#ED7D31", "#A9D18E", "#FFC000",
                      "#5A5A5A", "#70AD47", "#FF0000", "#264478"]
    colores = [r[2] if len(r) > 2 and r[2] else default_colors[i % len(default_colors)]
               for i, r in enumerate(composicion)]

    data = [(l, s, c) for l, s, c in zip(labels, sizes, colores) if s > 0]
    if not data:
        return _imagen_vacia(ancho_px, alto_px)
    labels, sizes, colores = zip(*data)

    fig, ax = plt.subplots(figsize=(ancho_px / 96, alto_px / 96))
    _, _, autotexts = ax.pie(
        sizes, colors=colores,
        autopct=lambda p: f"{p:.1f}%" if p > 4 else "",
        startangle=90, pctdistance=0.72,
        wedgeprops={"linewidth": 0.5, "edgecolor": "white"},
    )
    for at in autotexts:
        at.set_fontsize(5)
        at.set_color("white")
        at.set_fontweight("bold")

    patches = [mpatches.Patch(color=c, label=f"{l}  {s:.1f}%")
               for l, s, c in zip(labels, sizes, colores)]
    ax.legend(handles=patches, loc="center left", bbox_to_anchor=(1, 0.5),
              fontsize=4.5, frameon=False, labelspacing=0.7)
    ax.set_aspect("equal")
    plt.tight_layout(pad=0.2)
    return _fig_to_buf(fig)


# ── Gráfico de línea — evolución VCP diaria ──────────────────────────────────
def grafico_evolucion(evolucion, ancho_px=260, alto_px=160):
    """
    evolucion: lista de [fecha_str, valor_float]
    Con datos diarios (~365 puntos) dibuja solo la línea sin markers,
    muestra ~8 fechas en el eje X y anota el valor inicial y final.
    """
    if not evolucion:
        return _imagen_vacia(ancho_px, alto_px)

    fechas  = [str(r[0]) for r in evolucion]
    valores = [float(r[1]) for r in evolucion if r[1] is not None]

    if not valores:
        return _imagen_vacia(ancho_px, alto_px)

    fig, ax = plt.subplots(figsize=(ancho_px / 96, alto_px / 96))
    xs = list(range(len(fechas)))

    ax.plot(xs, valores, "-", color="#2E75B6", linewidth=1.0)
    ax.fill_between(xs, valores, alpha=0.08, color="#2E75B6")

    # Valor inicial y final anotados
    ax.annotate(f"{valores[0]:.4f}", (xs[0], valores[0]),
                textcoords="offset points", xytext=(3, 4),
                fontsize=4.5, color="#595959")
    ax.annotate(f"{valores[-1]:.4f}", (xs[-1], valores[-1]),
                textcoords="offset points", xytext=(-28, 4),
                fontsize=4.5, color="#2E75B6", fontweight="bold")

    # ~8 etiquetas en eje X
    n    = len(xs)
    paso = max(1, n // 8)
    ticks = list(range(0, n, paso))
    if ticks[-1] != n - 1:
        ticks.append(n - 1)
    ax.set_xticks(ticks)
    ax.set_xticklabels([fechas[i] for i in ticks], fontsize=4.5,
                       rotation=30, ha="right")
    ax.tick_params(axis="y", labelsize=4.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linewidth=0.3, alpha=0.4, linestyle="--")
    ax.set_xlim(0, n - 1)
    plt.tight_layout(pad=0.3)
    return _fig_to_buf(fig)


# ── Gráfico de barras — principales tenencias ────────────────────────────────
def grafico_tenencias(tenencias, ancho_px=260, alto_px=180):
    if not tenencias:
        return _imagen_vacia(ancho_px, alto_px)

    n      = min(10, len(tenencias))
    items  = tenencias[:n]
    labels = [str(r[0])[:38] for r in items]
    valores = []
    for r in items:
        try:
            pct = float(str(r[2]).replace("%", "").replace(",", "."))
            valores.append(pct)
        except (ValueError, TypeError, IndexError):
            valores.append(0.0)

    fig, ax = plt.subplots(figsize=(ancho_px / 96, alto_px / 96))
    ys   = list(range(n))
    bars = ax.barh(ys, valores, color="#2E75B6", height=0.55)

    max_val = max(valores) if valores else 1
    for bar, val in zip(bars, valores):
        ax.text(bar.get_width() + max_val * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}%", va="center", fontsize=4.5, color="#1A1A1A")

    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=4.5)
    ax.invert_yaxis()
    ax.spines[["top", "right", "bottom"]].set_visible(False)
    ax.tick_params(axis="x", labelsize=4)
    ax.set_xlim(0, max_val * 1.18)
    plt.tight_layout(pad=0.3)
    return _fig_to_buf(fig)


# ── Helpers internos ──────────────────────────────────────────────────────────
def _fig_to_buf(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _imagen_vacia(ancho_px, alto_px):
    fig, ax = plt.subplots(figsize=(ancho_px / 96, alto_px / 96))
    ax.text(0.5, 0.5, "Sin datos", ha="center", va="center",
            fontsize=8, color="#BFBFBF", transform=ax.transAxes)
    ax.axis("off")
    return _fig_to_buf(fig)


def _placeholder_logo(texto, ancho, alto):
    t = Table(
        [[Paragraph(texto, ParagraphStyle("ph", fontName="Helvetica",
           fontSize=6, alignment=TA_CENTER, textColor=GRIS_BORDE, leading=8))]],
        colWidths=[ancho], rowHeights=[alto],
    )
    t.setStyle(TableStyle([
        ("BOX",    (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
    ]))
    return t


def _tabla_rendimientos(rendimientos, ancho, S, tipo="TNA"):
    """Tabla de rendimientos — muestra solo las clases con datos."""
    tiene = {"a": False, "b": False, "c": False}
    for r in rendimientos:
        if len(r) > 1 and str(r[1]).strip() not in ("", "nan", "None"):
            tiene["a"] = True
        if len(r) > 2 and str(r[2]).strip() not in ("", "nan", "None"):
            tiene["b"] = True
        if len(r) > 3 and str(r[3]).strip() not in ("", "nan", "None"):
            tiene["c"] = True

    clases_activas = [k.upper() for k, v in tiene.items() if v]
    n_clases  = max(1, len(clases_activas))
    w_periodo = ancho * 0.30
    w_clase   = (ancho * 0.70) / n_clases

    enc = [Paragraph("Valor Cuotaparte", S["celda_izq"])]
    for cl in clases_activas:
        enc.append(Paragraph(f"CLASE {cl}", S["header_col"]))
    rows = [enc]

    for r in rendimientos:
        fila = [Paragraph(str(r[0]), S["celda_izq"])]
        for idx, key in enumerate(["a", "b", "c"]):
            if tiene[key]:
                v = str(r[idx + 1]).strip() if len(r) > idx + 1 else tipo
                fila.append(Paragraph(
                    v if v not in ("", "nan", "None") else tipo, S["celda"]))
        rows.append(fila)

    t = Table(rows, colWidths=[w_periodo] + [w_clase] * n_clases)
    style = [
        ("BACKGROUND", (1, 0), (-1, 0), AZUL_MEDIO),
        ("TEXTCOLOR",  (1, 0), (-1, 0), BLANCO),
        ("BOX",  (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("GRID", (0, 0), (-1, -1), 0.3, GRIS_BORDE),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))
    t.setStyle(TableStyle(style))
    return t


def _tabla_honorarios(honorarios, ancho, S):
    """Tabla de honorarios — muestra solo las clases con datos."""
    tiene = {"a": False, "b": False, "c": False}
    for r in honorarios:
        if len(r) > 1 and str(r[1]).strip() not in ("", "nan", "None"):
            tiene["a"] = True
        if len(r) > 2 and str(r[2]).strip() not in ("", "nan", "None"):
            tiene["b"] = True
        if len(r) > 3 and str(r[3]).strip() not in ("", "nan", "None"):
            tiene["c"] = True

    clases_activas = [k.upper() for k, v in tiene.items() if v]
    n_clases   = max(1, len(clases_activas))
    w_concepto = ancho * 0.46
    w_clase    = (ancho * 0.54) / n_clases

    enc = [Paragraph("", S["celda"])]
    for cl in clases_activas:
        enc.append(Paragraph(f"CLASE {cl}", S["header_col"]))
    rows = [enc]

    for r in honorarios:
        fila = [Paragraph(str(r[0]), S["celda_izq"])]
        for idx, key in enumerate(["a", "b", "c"]):
            if tiene[key]:
                v = str(r[idx + 1]).strip() if len(r) > idx + 1 else "%"
                fila.append(Paragraph(
                    v if v not in ("", "nan", "None") else "%", S["celda"]))
        rows.append(fila)

    t = Table(rows, colWidths=[w_concepto] + [w_clase] * n_clases)
    style = [
        ("BACKGROUND", (1, 0), (-1, 0), AZUL_MEDIO),
        ("TEXTCOLOR",  (1, 0), (-1, 0), BLANCO),
        ("BOX",  (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("GRID", (0, 0), (-1, -1), 0.3, GRIS_BORDE),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))
    t.setStyle(TableStyle(style))
    return t


# ── Función principal ─────────────────────────────────────────────────────────
def construir_pdf(datos, rendimientos, composicion, tenencias,
                  honorarios, evolucion, output_path):
    """
    Genera el PDF de la Ficha Única CNV.

    Parámetros:
      datos        : dict  — campos de DATOS_FONDO
      rendimientos : list  — [[periodo, clase_a, clase_b, clase_c], ...]
      composicion  : list  — [[categoria, porcentaje, color], ...]
      tenencias    : list  — [[instrumento, monto, pct], ...]
      honorarios   : list  — [[concepto, clase_a, clase_b, clase_c], ...]
      evolucion    : list  — [[fecha_str, valor], ...]  datos diarios
      output_path  : str   — ruta del PDF a generar
    """
    S  = make_styles()
    es_money_market = str(datos.get("tipo_fondo", "")).lower() == "money_market"

    W, H       = A4
    margen     = 12 * mm
    ancho_util = W - 2 * margen

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=margen, rightMargin=margen,
        topMargin=10 * mm, bottomMargin=10 * mm,
    )
    story = []

    # ── Encabezado normativo ─────────────────────────────────────────────────
    tipo_str = ("FONDOS COMUNES DE DINERO"
                if es_money_market
                else "OTROS FCI (DISTINTOS DE FONDOS COMUNES DE DINERO)")
    enc_txt = (
        f"ANEXO III - MODELO FICHA ÚNICA FCI ABIERTOS CONFORME ARTÍCULO 31 BIS "
        f"DE LA SECCIÓN VII DEL CAPÍTULO I DEL TÍTULO V\n{tipo_str}"
    )
    enc = Table(
        [[Paragraph(enc_txt, ParagraphStyle("enc", fontName="Helvetica-Bold",
          fontSize=6.5, alignment=TA_CENTER, textColor=NEGRO, leading=9))]],
        colWidths=[ancho_util],
    )
    enc.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(enc)
    story.append(Spacer(1, 2 * mm))

    # ── Logos + nombre FCI ───────────────────────────────────────────────────
    w3     = ancho_util / 3
    logo_g = _placeholder_logo("LOGOTIPO\nSOCIEDAD GERENTE",     w3 * 0.9, 18 * mm)
    logo_d = _placeholder_logo("LOGOTIPO\nSOCIEDAD DEPOSITARIA", w3 * 0.9, 18 * mm)
    centro = [
        Paragraph(f"<b>{datos.get('nombre_fci', '')}</b>",
                  ParagraphStyle("nfci", fontName="Helvetica-Bold", fontSize=9,
                                 alignment=TA_CENTER, textColor=AZUL_CNV, leading=12)),
        Paragraph(f"Fecha del reporte: {datos.get('fecha_reporte', '')}",
                  ParagraphStyle("frep", fontName="Helvetica", fontSize=7,
                                 alignment=TA_CENTER, textColor=NEGRO)),
    ]
    ht = Table([[logo_g, centro, logo_d]], colWidths=[w3, w3, w3])
    ht.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOX",           (0, 0), (-1, -1), 0.8, GRIS_BORDE),
        ("LINEBEFORE",    (1, 0), (1, -1),  0.5, GRIS_BORDE),
        ("LINEAFTER",     (1, 0), (1, -1),  0.5, GRIS_BORDE),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ht)
    story.append(Spacer(1, 2 * mm))

    # ── Objetivo y política ──────────────────────────────────────────────────
    objetivo = str(datos.get("objetivo_politica", "") or "")
    obj = Table(
        [[Paragraph("DESCRIPCIÓN DEL FCI. OBJETIVO Y POLÍTICA DE INVERSIÓN",
                    S["titulo_seccion"])],
         [Paragraph(objetivo, S["objetivo"])]],
        colWidths=[ancho_util],
    )
    obj.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 1), (0, 1), 5),
        ("RIGHTPADDING",  (0, 1), (0, 1), 5),
    ]))
    story.append(obj)
    story.append(Spacer(1, 2 * mm))

    # ── Info FCI + Rendimientos ──────────────────────────────────────────────
    w_info = ancho_util * 0.48
    w_rend = ancho_util * 0.52

    cal_riesgo = str(datos.get("calificacion_riesgo", "") or "")
    benchmark  = str(datos.get("benchmark", "") or "")
    cal_bench  = cal_riesgo + (" / " + benchmark if benchmark else "")

    campos_info = [
        ("Patrimonio neto:",                datos.get("patrimonio_neto", "")),
        ("Moneda del FCI:",                 datos.get("moneda_fci", "")),
        ("Monto mínimo de suscripción:",    datos.get("monto_minimo_suscripcion", "")),
        ("Plazo de pago de rescates:",      datos.get("plazo_rescates", "")),
        ("Clasificación:",                  datos.get("clasificacion", "")),
        ("Horizonte de inversión:",         datos.get("horizonte_inversion", "")),
        ("Indicador de riesgo:",            datos.get("indicador_riesgo", "")),
        ("Perfil del inversor:",            datos.get("perfil_inversor", "")),
        ("Número de registro ante CNV:",    datos.get("numero_registro_cnv", "")),
        ("Fecha de inicio de operaciones:", datos.get("fecha_inicio_operaciones", "")),
        ("Identificación de los Auditores:", datos.get("auditores", "")),
        ("Correo electrónico de contacto:", datos.get("email_contacto", "")),
        ("Calificación de riesgo y Benchmark:", cal_bench),
    ]
    info_rows = [[Paragraph("INFORMACIÓN DEL FCI", S["titulo_seccion"])]]
    for label, val in campos_info:
        info_rows.append([Paragraph(f"{label} <b>{val}</b>", S["label"])])

    t_info = Table(info_rows, colWidths=[w_info])
    st_info = [
        ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 1), (-1, -1), 5),
    ]
    for i in range(1, len(info_rows)):
        if i % 2 == 0:
            st_info.append(("BACKGROUND", (0, i), (0, i), GRIS_CLARO))
    t_info.setStyle(TableStyle(st_info))

    tipo_rend    = "TNA" if es_money_market else "Directo"
    t_rend_inner = _tabla_rendimientos(rendimientos, w_rend, S, tipo_rend)
    t_rend = Table(
        [[Paragraph("RENDIMIENTO HISTÓRICO", S["titulo_seccion"])],
         [t_rend_inner]],
        colWidths=[w_rend],
    )
    t_rend.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    fila_1 = Table([[t_info, t_rend]], colWidths=[w_info, w_rend])
    fila_1.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(fila_1)
    story.append(Spacer(1, 2 * mm))

    # ── Composición + Honorarios ─────────────────────────────────────────────
    w_comp = ancho_util * 0.48
    w_hon  = ancho_util * 0.52

    buf_torta = grafico_torta(composicion, ancho_px=int(w_comp * 2.5), alto_px=130)
    img_torta = Image(buf_torta, width=w_comp - 4 * mm, height=35 * mm)

    t_comp = Table(
        [[Paragraph("COMPOSICIÓN DE LA CARTERA", S["titulo_seccion"])],
         [img_torta]],
        colWidths=[w_comp],
    )
    t_comp.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("ALIGN",         (0, 1), (0, 1), "CENTER"),
        ("VALIGN",        (0, 1), (0, 1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    t_hon_inner = _tabla_honorarios(honorarios, w_hon, S)
    t_hon = Table(
        [[Paragraph("HONORARIOS, GASTOS Y COMISIONES", S["titulo_seccion"])],
         [t_hon_inner],
         [Paragraph("(*) Los Honorarios de la Sociedad Depositaria incluyen IVA.",
                    S["small"])],
         [Paragraph("(**) Incluye la retribución de los Agentes de la Colocación "
                    "de las cuotapartes.", S["small"])]],
        colWidths=[w_hon],
    )
    t_hon.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("LEFTPADDING",   (0, 1), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 1), (-1, -1), 3),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    fila_2 = Table([[t_comp, t_hon]], colWidths=[w_comp, w_hon])
    fila_2.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(fila_2)
    story.append(Spacer(1, 2 * mm))

    # ── Tenencias + Evolución VCP ────────────────────────────────────────────
    w_ten = ancho_util * 0.48
    w_evo = ancho_util * 0.52

    buf_ten = grafico_tenencias(tenencias, ancho_px=int(w_ten * 2.5), alto_px=160)
    img_ten = Image(buf_ten, width=w_ten - 2 * mm, height=42 * mm)

    t_ten = Table(
        [[Paragraph("PRINCIPALES TENENCIAS", S["titulo_seccion"])],
         [img_ten]],
        colWidths=[w_ten],
    )
    t_ten.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("ALIGN",         (0, 1), (0, 1), "CENTER"),
        ("VALIGN",        (0, 1), (0, 1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    buf_evo = grafico_evolucion(evolucion, ancho_px=int(w_evo * 2.5), alto_px=160)
    img_evo = Image(buf_evo, width=w_evo - 2 * mm, height=42 * mm)

    t_evo = Table(
        [[Paragraph("EVOLUCIÓN VALOR CUOTAPARTE", S["titulo_seccion"])],
         [img_evo]],
        colWidths=[w_evo],
    )
    t_evo.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("ALIGN",         (0, 1), (0, 1), "CENTER"),
        ("VALIGN",        (0, 1), (0, 1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    fila_3 = Table([[t_ten, t_evo]], colWidths=[w_ten, w_evo])
    fila_3.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(fila_3)
    story.append(Spacer(1, 2 * mm))

    # ── Tratamiento impositivo + Acceso CAFCI ────────────────────────────────
    url_imp = str(datos.get("tratamiento_impositivo_url", "") or "")
    url_caf = str(datos.get("comparador_cafci_url", "") or "")
    w_imp   = ancho_util / 2 if es_money_market else ancho_util

    t_imp = Table(
        [[Paragraph("TRATAMIENTO IMPOSITIVO", S["titulo_seccion"])],
         [Paragraph(f"Enlace directo de acceso público al régimen impositivo "
                    f"aplicable\n{url_imp}", S["small"])]],
        colWidths=[w_imp],
    )
    t_imp.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("LEFTPADDING",   (0, 1), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    if es_money_market and url_caf:
        t_caf = Table(
            [[Paragraph("ACCESO DIGITAL", S["titulo_seccion"])],
             [Paragraph(f"Enlace directo al comparador de FCI — CAFCI\n{url_caf}",
                        S["small"])]],
            colWidths=[ancho_util / 2],
        )
        t_caf.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), AZUL_CNV),
            ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_BORDE),
            ("LEFTPADDING",   (0, 1), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        fila_4 = Table([[t_imp, t_caf]],
                       colWidths=[ancho_util / 2, ancho_util / 2])
    else:
        fila_4 = Table([[t_imp]], colWidths=[w_imp])

    fila_4.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(fila_4)
    story.append(Spacer(1, 3 * mm))

    # ── Leyenda legal obligatoria ────────────────────────────────────────────
    entidad = str(datos.get("leyenda_depositos", "[entidad financiera]") or
                  "[entidad financiera]")
    leyenda = (
        f"Las inversiones en cuotas del FCI no constituyen depósitos en {entidad}, "
        f"a los fines de la Ley de Entidades Financieras ni cuentan con ninguna de las "
        f"garantías que tales depósitos a la vista o a plazo puedan gozar de acuerdo a "
        f"la legislación y reglamentación aplicables en materia de depósitos en entidades "
        f"financieras. Asimismo, {entidad} se encuentra impedida por normas del BCRA de "
        f"asumir, tácita o expresamente, compromiso alguno en cuanto al mantenimiento, "
        f"en cualquier momento, del valor del capital invertido, al rendimiento, al valor "
        f"de rescate de las cuotapartes o al otorgamiento de liquidez a tal fin."
    )
    story.append(Paragraph(leyenda, S["leyenda"]))

    doc.build(story)
    print(f"PDF generado: {output_path}")
