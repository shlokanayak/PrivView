# report_pdf.py - builds the downloadable PDF analysis report (reportlab).
# It receives the SAME analysis result the workspace shows, so the PDF always matches
# the screen (same filters, same numbers). Nothing is invented here.
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

BLUE = colors.HexColor("#2a78d6")
ORANGE = colors.HexColor("#eb6834")
INK = colors.HexColor("#18242f")
MUTED = colors.HexColor("#5f6f7e")
LINE = colors.HexColor("#dde3ea")
SOFT = colors.HexColor("#f3f5f8")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=20, textColor=INK, alignment=0, spaceAfter=2)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, textColor=INK, spaceBefore=14, spaceAfter=6)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=10.5, textColor=INK, spaceBefore=8, spaceAfter=2)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=12.5, textColor=INK)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8, leading=10.5, textColor=MUTED)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8, leading=10)


def p(text, style=BODY):
    return Paragraph(escape(str(text)), style)      # escape: dataset text can contain & or <


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def thin(labels, limit=12):
    """Show only every n-th axis label so they do not overlap."""
    step = max(1, -(-len(labels) // limit))
    return [l if i % step == 0 else "" for i, l in enumerate(labels)]


def line_chart(labels, values, width, height=170):
    d = Drawing(width, height)
    c = HorizontalLineChart()
    c.x, c.y, c.width, c.height = 48, 38, width - 64, height - 54
    c.data = [values]
    c.categoryAxis.categoryNames = thin(labels)
    c.categoryAxis.labels.fontSize = 7
    c.categoryAxis.labels.angle = 30
    c.categoryAxis.labels.boxAnchor = "ne"
    c.categoryAxis.labels.dy = -2
    c.valueAxis.labels.fontSize = 7
    c.valueAxis.labels.rightPadding = 4
    low, high = min(values), max(values)
    pad = (high - low) * 0.15 or abs(high) * 0.1 or 1
    c.valueAxis.valueMin, c.valueAxis.valueMax = low - pad, high + pad
    c.valueAxis.gridStrokeColor = LINE
    c.valueAxis.visibleGrid = True
    c.lines[0].strokeColor = BLUE
    c.lines[0].strokeWidth = 2
    c.lines[0].symbol = makeMarker("FilledCircle")
    c.lines[0].symbol.size = 4
    c.lines[0].symbol.fillColor = BLUE
    c.lines[0].symbol.strokeColor = colors.white
    d.add(c)
    return d


def bar_chart(labels, values, width, height=170, signed=False, fixed_range=None, zero_base=False):
    d = Drawing(width, height)
    c = VerticalBarChart()
    c.x, c.y, c.width, c.height = 48, 42, width - 64, height - 58
    c.data = [values]
    c.categoryAxis.categoryNames = thin(labels, 10)
    c.categoryAxis.labels.fontSize = 7
    c.categoryAxis.labels.angle = 30
    c.categoryAxis.labels.boxAnchor = "ne"
    c.categoryAxis.labelAxisMode = "low"
    c.valueAxis.labels.fontSize = 7
    c.valueAxis.visibleGrid = True
    c.valueAxis.gridStrokeColor = LINE
    c.barSpacing = 2
    c.groupSpacing = 6
    c.bars[0].strokeColor = None
    c.bars[0].fillColor = BLUE
    if signed:                                          # positive = blue, negative = orange
        for i, v in enumerate(values):
            c.bars[(0, i)].fillColor = BLUE if v >= 0 else ORANGE
    if fixed_range:
        c.valueAxis.valueMin, c.valueAxis.valueMax = fixed_range
    elif zero_base:                                    # counts must start at zero
        c.valueAxis.valueMin = 0
    d.add(c)
    return d


def table(rows, widths, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
             ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), SOFT), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "PrivView - protected analysis report. Contains only sanitised and masked data.")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_report(info, protection, result, params, username):
    """info: dataset facts, protection: protection_info(), result: analyse() output,
    params: {measure, group_by, filters}. Returns the PDF as bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            title=f"PrivView report - {info['name']}", author="PrivView")
    width = A4[0] - 36 * mm
    story = [p("Protected analysis report", H1), p(info["name"], H3)]
    now = datetime.now().astimezone().strftime("%d %b %Y, %H:%M %Z")
    f = params["filters"]
    filters_text = []
    if f.get("date_from") or f.get("date_to"):
        filters_text.append(f"date {f.get('date_from') or 'start'} to {f.get('date_to') or 'end'}")
    meta = [["Dataset file", info["filename"], "Generated by", username],
            ["Records in dataset", fmt(result["records_total"]), "Generated on", now],
            ["Records analysed", fmt(result["records_selected"]), "Last updated", f"{info['updated_at']} by {info['updated_by']}"],
            ["Measure", params["measure"] or "-", "Filters", "; ".join(filters_text) or "none"]]
    story += [Spacer(1, 4), table([[p(c, CELL) for c in row] for row in meta],
                                  [32 * mm, 52 * mm, 28 * mm, width - 112 * mm], header=False)]

    # ---- protection
    s, m = protection["sanitisation"], protection["masking"]
    story.append(p("Data protection", H2))
    story.append(table([
        [p("Layer", CELL), p("Status", CELL), p("Detail", CELL)],
        [p("Sanitisation", CELL), p(s["status"], CELL),
         p(f"{fmt(s['cells_checked'])} cells checked; {fmt(s['xss_cells'])} XSS-like and "
           f"{fmt(s['formula_cells'])} formula-injection cells neutralised; records affected: "
           f"{fmt(s['records_affected']) if s['records_affected'] is not None else 'not recorded'}", CELL)],
        [p("Privacy masking", CELL), p(m["status"], CELL),
         p(f"{m['fields_affected']} field(s), {fmt(m['records_affected'])} record(s): "
           f"{', '.join(m['columns']) or 'none'}", CELL)],
        [p("Encryption", CELL), p("Active", CELL),
         p(f"{protection['encryption']} at rest; raw upload not retained", CELL)],
    ], [30 * mm, 24 * mm, width - 54 * mm]))
    if protection["categories"]:
        story.append(Spacer(1, 4))
        story.append(p("Categories protected: " + "; ".join(
            f"{c['category']} ({', '.join(c['columns'])})" for c in protection["categories"]), SMALL))

    if result.get("suppressed") or result.get("no_measures"):
        story += [p("Results", H2), p(result["message"])]
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        return buffer.getvalue()

    masked = result["measure"]["masked"]
    scale = " (masked scale)" if masked else ""
    st = result["stats"]

    # ---- key figures
    story.append(p("Key figures", H2))
    story.append(table([
        [p("Mean" + scale, CELL), p("Median" + scale, CELL), p("Std. deviation", CELL),
         p("Minimum" + scale, CELL), p("Maximum" + scale, CELL)],
        [p(fmt(st["mean"]), CELL), p(fmt(st["median"]), CELL), p(fmt(st["std"]), CELL),
         p(fmt(st["min"]), CELL), p(fmt(st["max"]), CELL)],
    ], [width / 5] * 5))

    # ---- charts
    story.append(p("Trend, comparison and distribution", H2))
    tr = result["trend"]
    if tr["available"]:
        block = [p(f"Average {params['measure']} per {tr['grain'] if tr['grain'] != 'sequence' else 'record group'}{scale}", H3),
                 line_chart([pt["label"] for pt in tr["points"]], [pt["mean"] for pt in tr["points"]], width),
                 p(f"The average is {tr['direction']} (change of {fmt(tr['change'])} from first to last point). "
                   f"{tr['hidden_periods']} period(s) with fewer than 3 records are hidden.", SMALL)]
    else:
        block = [p("Trend", H3), p(tr["reason"], SMALL)]
    story.append(KeepTogether(block))

    gr = result.get("groups")
    if gr and gr["available"]:
        story.append(KeepTogether([
            p(f"{params['measure']} by {gr['group_column']}: difference from the overall average", H3),
            bar_chart([g["group"] for g in gr["groups"]], [g["diff_from_overall"] for g in gr["groups"]], width, signed=True),
            table([[p("Group", CELL), p("Records", CELL), p("Mean" + scale, CELL), p("Std. dev.", CELL), p("Difference", CELL)]]
                  + [[p(g["group"], CELL), p(fmt(g["count"]), CELL), p(fmt(g["mean"]), CELL),
                      p(fmt(g["std"]), CELL), p(f"{g['diff_from_overall']:+,.2f}", CELL)] for g in gr["groups"]],
                  [width * 0.34, width * 0.14, width * 0.18, width * 0.16, width * 0.18]),
            p(f"Groups with fewer than 3 records are hidden ({gr['hidden_groups']} hidden). Differences between groups are exact even when values are masked.", SMALL)]))

    dist = result["distribution"]
    story.append(KeepTogether([
        p(f"Distribution of {params['measure']}{scale}", H3),
        bar_chart([b["label"] for b in dist], [b["count"] for b in dist], width, zero_base=True),
        p("Number of records in each value range.", SMALL)]))

    cor = result["correlations"]
    if cor:
        story.append(KeepTogether([
            p(f"Correlation of {params['measure']} with other numeric fields", H3),
            bar_chart([c["column"] for c in cor], [c["r"] for c in cor], width, signed=True, fixed_range=(-1, 1)),
            p("Pearson correlation (-1 to +1). Correlations are unaffected by masking.", SMALL)]))

    # ---- summary statistics
    rows = [[p(h, CELL) for h in ["Field", "n", "Mean", "Median", "Std. dev.", "Min", "Max"]]]
    for r in result["summary_stats"]:
        rows.append([p(r["column"] + (" *" if r["masked"] else ""), CELL), p(fmt(r["n"]), CELL),
                     p(fmt(r["mean"]), CELL), p(fmt(r["median"]), CELL), p(fmt(r["std"]), CELL),
                     p(fmt(r["min"]), CELL), p(fmt(r["max"]), CELL)])
    story.append(KeepTogether([p("Summary statistics (all numeric fields)", H2),
                               table(rows, [width * 0.28] + [width * 0.12] * 6)]))
    story.append(Spacer(1, 4))
    story.append(p("* Masked field: its level figures (mean, median, min, max) are on the masked scale - the real "
                   "values were shifted by a secret constant before storage. Standard deviation, correlation, "
                   "differences between groups and changes over time are exact.", SMALL))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
