#!/usr/bin/env python3
"""
Build docs/CPU_Design_Report.pdf and docs/figures/*.svg.

Every listing, encoding table, RAM dump, trace row and test count in the
report is produced here by running the real assembler, simulator and test
suite -- nothing is typed in by hand.

    pip install -r tools/requirements.txt      # reportlab (PDF only)
    python3 tools/build_report.py

Title-page details (course, team, members) are set in the CONFIG block.
"""

import contextlib
import io
import re
import sys
import unittest
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

from reportlab import rl_config                                # noqa: E402
from reportlab.graphics import renderSVG                       # noqa: E402
from reportlab.lib import colors                               # noqa: E402
from reportlab.lib.enums import TA_CENTER                      # noqa: E402
from reportlab.lib.pagesizes import letter                     # noqa: E402
from reportlab.lib.styles import ParagraphStyle                # noqa: E402
from reportlab.pdfbase import pdfmetrics                       # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont                   # noqa: E402
from reportlab.pdfgen import canvas                            # noqa: E402
from reportlab.platypus import (KeepTogether, PageBreak,       # noqa: E402
                                Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle, XPreformatted)

import diagrams                                                # noqa: E402
import isa                                                     # noqa: E402
import run_demo                                                # noqa: E402

rl_config.invariant = 1          # reproducible PDF bytes (no timestamps)

# ==========================================================================
# CONFIG -- replace the bracketed placeholders before submitting
# ==========================================================================
TITLE = "CPU Design & Simulation"
CPU_NAME = "MiniCPU-8"
SUBJECT = "CMPE-220 – Systems Software"
ASSIGNMENT = "CPU Design & Simulation (own CPU, own ISA, simulator)"
INSTRUCTOR = "Prof. Eswar, Ishie"
DATE = "November 2026"
REPO_URL = "https://github.com/Revati-sp/CPU-Design.git"
MEMBERS = (                                # project contributors
    "Revati Dharmadhikari",
    "Renuka Patwari",
    "Atharva Mokashi",
)
CONTRIBUTIONS = (                          # one row per member, same order
    ("ISA & assembler",
     "Defined the 16-bit instruction format and the 15-instruction opcode "
     "map (isa.py); wrote the two-pass assembler with label resolution, "
     ".org/.byte directives and line-numbered errors (assembler.py); wrote "
     "Program A (square8.asm); wrote tests/test_assembler.py; produced "
     "the encoding, memory-map and syntax tables.",
     "isa.py, assembler.py, programs/square8.asm, tests/test_assembler.py"),
    ("Simulator & Program B",
     "Implemented fetch/decode/execute, Z/N flag logic and the fault checks "
     "(invalid opcode, reserved bits, PC alignment, 1000-step limit) in "
     "cpu.py; built the per-step RAM/register tracer (tracer.py); wrote "
     "factorial.c and its manual translation factorial.asm; wrote "
     "tests/test_cpu.py and tests/test_programs.py.",
     "cpu.py, tracer.py, programs/factorial.c, programs/factorial.asm, "
     "tests/test_cpu.py, tests/test_programs.py"),
    ("Diagrams, automation & report",
     "Drew the architecture, instruction-format and cycle diagrams "
     "(tools/diagrams.py); wrote run_demo.py and "
     "validate.py; wrote the PDF generator that builds every table and "
     "trace from live simulator output (tools/build_report.py); wrote "
     "README.md and tests/test_docs.py; ran the final cross-check of "
     "documentation vs. assembler vs. decoder.",
     "run_demo.py, validate.py, tools/, README.md, tests/test_docs.py"),
)

OUT_PDF = ROOT / "docs" / "CPU_Design_Report.pdf"
OUT_FIG = ROOT / "docs" / "figures"

# ==========================================================================
# Fonts (Unicode TTFs if present; built-in Type 1 fonts otherwise)
# ==========================================================================
FONT_CANDIDATES = (
    {"sans": "/System/Library/Fonts/Supplemental/Arial.ttf",
     "bold": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "italic": "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
     "mono": ("/System/Library/Fonts/Menlo.ttc", 0),
     "mono_bold": ("/System/Library/Fonts/Menlo.ttc", 1)},
    {"sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
     "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
     "mono": ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
     "mono_bold": ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                   0)},
)
SANS, BOLD, ITALIC = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"
MONO, MONO_B = "Courier", "Courier-Bold"
UNICODE = False


def setup_fonts():
    global SANS, BOLD, ITALIC, MONO, MONO_B, UNICODE
    for cand in FONT_CANDIDATES:
        try:
            pdfmetrics.registerFont(TTFont("R-Sans", cand["sans"]))
            pdfmetrics.registerFont(TTFont("R-Bold", cand["bold"]))
            pdfmetrics.registerFont(TTFont("R-Italic", cand["italic"]))
            pdfmetrics.registerFont(TTFont("R-Mono", cand["mono"][0],
                                           subfontIndex=cand["mono"][1]))
            pdfmetrics.registerFont(TTFont("R-MonoB", cand["mono_bold"][0],
                                           subfontIndex=cand["mono_bold"][1]))
        except Exception:                   # font file missing -> next set
            continue
        SANS, BOLD, ITALIC = "R-Sans", "R-Bold", "R-Italic"
        MONO, MONO_B = "R-Mono", "R-MonoB"
        UNICODE = True
        break
    diagrams.set_fonts(SANS, BOLD, MONO)


def sym(s):
    """Pretty symbols when a Unicode font is available."""
    if not UNICODE:
        for uni, ascii_ in (("✓", "OK"), ("²", "^2"), ("→", "->"),
                            ("←", "<-"), ("↔", "<->"), ("≤", "<=")):
            s = s.replace(uni, ascii_)
        return s
    return s.replace("<-", "←").replace("->", "→") \
            .replace(" * ", " × ")


def p(s):
    """Escape plain text for Paragraph markup, with pretty symbols."""
    return escape(sym(s))


# ==========================================================================
# Styles & palette
# ==========================================================================
NAVY = colors.HexColor("#1F3A5F")
GRID = colors.HexColor("#B8C4D2")
ZEBRA = colors.HexColor("#F4F7FA")
CODE_BG = colors.HexColor("#F6F8FA")
HL_CHANGE = colors.HexColor("#FFE08A")    # changed by this instruction
HL_PC = colors.HexColor("#CFE3FF")        # bytes of executing instruction
HL_CODE = colors.HexColor("#D3E3F8")
HL_DATA = colors.HexColor("#FFE2A8")
HL_RESULT = colors.HexColor("#CDEFD7")
PASS_GREEN = colors.HexColor("#1E7B45")
GRAY = colors.HexColor("#5F6B7A")

PAGE_W, PAGE_H = letter
MARGIN = 50
FRAME_W = PAGE_W - 2 * MARGIN


def styles():
    s = {}
    s["body"] = ParagraphStyle("body", fontName=SANS, fontSize=9, leading=12)
    s["note"] = ParagraphStyle("note", fontName=SANS, fontSize=7.5,
                               leading=9.5, textColor=GRAY)
    s["cell"] = ParagraphStyle("cell", fontName=SANS, fontSize=7.6,
                               leading=9.4)
    s["cellc"] = ParagraphStyle("cellc", parent=s["cell"], alignment=TA_CENTER)
    s["mono"] = ParagraphStyle("mono", fontName=MONO, fontSize=7.2,
                               leading=9.2)
    s["monoc"] = ParagraphStyle("monoc", parent=s["mono"],
                                alignment=TA_CENTER)
    s["head"] = ParagraphStyle("head", fontName=BOLD, fontSize=7.8,
                               leading=9.4, textColor=colors.white,
                               alignment=TA_CENTER)
    s["h1"] = ParagraphStyle("h1", fontName=BOLD, fontSize=15, leading=19,
                             textColor=NAVY, spaceAfter=2)
    s["h2"] = ParagraphStyle("h2", fontName=BOLD, fontSize=10.5, leading=13,
                             textColor=NAVY, spaceBefore=6, spaceAfter=3)
    s["caption"] = ParagraphStyle("caption", fontName=ITALIC, fontSize=8.5,
                                  leading=11, alignment=TA_CENTER,
                                  textColor=NAVY, spaceBefore=3,
                                  spaceAfter=8)
    s["code"] = ParagraphStyle("code", fontName=MONO, fontSize=7.4,
                               leading=9.6)
    return s


S = None                       # filled in main() after fonts are registered


# ==========================================================================
# Captions (automatic numbering)
# ==========================================================================
class Counter:
    figures = 0
    tables = 0


def fig_caption(text):
    Counter.figures += 1
    return Paragraph("<font name='%s'>Figure %d.</font> %s"
                     % (BOLD, Counter.figures, p(text)), S["caption"])


def tab_caption(text):
    Counter.tables += 1
    return Paragraph("<font name='%s'>Table %d.</font> %s"
                     % (BOLD, Counter.tables, p(text)), S["caption"])


def h1(text):
    rule = Table([[""]], colWidths=[FRAME_W], rowHeights=[2],
                 style=[("LINEABOVE", (0, 0), (-1, -1), 1.5, NAVY)])
    return [Paragraph(p(text), S["h1"]), rule, Spacer(1, 6)]


def h2(text):
    return Paragraph(p(text), S["h2"])


def note(text):
    return Paragraph(text, S["note"])


# ==========================================================================
# Table helpers
# ==========================================================================
def grid_table(rows, widths, header_rows=1, zebra=True, extra=(),
               align="CENTER"):
    """Standard table: navy header, light grid, zebra rows."""
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if header_rows:
        style.append(("BACKGROUND", (0, 0), (-1, header_rows - 1), NAVY))
    if zebra:
        for r in range(header_rows, len(rows)):
            if (r - header_rows) % 2:
                style.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
    style.extend(extra)
    t = Table(rows, colWidths=widths, repeatRows=header_rows, hAlign=align)
    t.setStyle(TableStyle(style))
    return t


def hd(*cells):
    return [Paragraph(p(c), S["head"]) for c in cells]


def c(text, style="cell"):
    return Paragraph(text, S[style])


def mono(text, center=False):
    return Paragraph(p(text), S["monoc" if center else "mono"])


def mono_lines(lines, center=False):
    """Monospace cell with one line per item."""
    return Paragraph("<br/>".join(p(x) for x in lines),
                     S["monoc" if center else "mono"])


def code_block(markup, width=FRAME_W):
    """Shaded, bordered code listing (markup already escaped)."""
    t = Table([[XPreformatted(markup, S["code"])]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.8, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


COMMENT = "<font color='#6A737D'>%s</font>"


def asm_markup(source):
    """Assembly source with gray comments and bold labels."""
    out = []
    for line in source.rstrip("\n").splitlines():
        code, _, comment = line.partition(";")
        code_m = escape(code)
        code_m = re.sub(r"^([A-Za-z_]\w*:)",
                        r"<font name='%s' color='#1F3A5F'>\1</font>" % MONO_B,
                        code_m)
        out.append(code_m + (COMMENT % escape(";" + comment) if _ else ""))
    return "\n".join(out)


def c_markup(source):
    """C source with gray /* comments */."""
    out, in_comment = [], False
    for line in source.rstrip("\n").splitlines():
        parts, rest = [], line
        while rest:
            if in_comment:
                end = rest.find("*/")
                seg = rest if end < 0 else rest[:end + 2]
                parts.append(COMMENT % escape(seg))
                rest = "" if end < 0 else rest[end + 2:]
                in_comment = end < 0
            else:
                start = rest.find("/*")
                seg = rest if start < 0 else rest[:start]
                parts.append(escape(seg))
                rest = "" if start < 0 else rest[start:]
                in_comment = start >= 0
        out.append("".join(parts))
    return "\n".join(out)


# ==========================================================================
# RAM block rendering
# ==========================================================================
RAM_ADDR_W, RAM_CELL_W = 19, 14.2
RAM_W = RAM_ADDR_W + 16 * RAM_CELL_W


def ram_grid(ram, rows, header=False, changed=(), pc=None, code=(),
             data=(), result=None, cell_h=8.6, font_size=6.3):
    """Nested hex grid of selected RAM rows with colored cells."""
    data_rows, style = [], [
        ("FONT", (0, 0), (-1, -1), MONO, font_size),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, GRID),
        ("BOX", (0, 0), (-1, -1), 0.5, GRID),
        ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
    ]
    if header:
        data_rows.append(["addr"] + ["+%X" % i for i in range(16)])
        style += [("TEXTCOLOR", (0, 0), (-1, 0), GRAY)]
    offset = len(data_rows)
    for r, base in enumerate(rows):
        data_rows.append(["%02X" % base] +
                         ["%02X" % ram[a] for a in range(base, base + 16)])
        for col in range(16):
            addr, cell = base + col, (col + 1, r + offset)
            fill = None
            if addr in code:
                fill = HL_CODE
            if addr in data:
                fill = HL_DATA
            if addr == result:
                fill = HL_RESULT
            if pc is not None and addr in (pc, pc + 1):
                fill = HL_PC
            if addr in changed:
                fill = HL_CHANGE
                style.append(("FONT", cell, cell, MONO_B, font_size))
                style.append(("TEXTCOLOR", cell, cell,
                              colors.HexColor("#B42318")))
            if fill is not None:
                style.append(("BACKGROUND", cell, cell, fill))
    t = Table(data_rows, colWidths=[RAM_ADDR_W] + [RAM_CELL_W] * 16,
              rowHeights=cell_h)
    t.setStyle(TableStyle(style))
    return t


def legend(items):
    """Inline color legend: [(color, label), ...]."""
    cells, style = [], [("FONT", (0, 0), (-1, -1), SANS, 7),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]
    widths = []
    for i, (color, text) in enumerate(items):
        cells += ["", text]
        widths += [11, len(text) * 3.6 + 10]
        style += [("BACKGROUND", (2 * i, 0), (2 * i, 0), color),
                  ("BOX", (2 * i, 0), (2 * i, 0), 0.4, GRID)]
    t = Table([cells], colWidths=widths, rowHeights=9)
    t.setStyle(TableStyle(style))
    return t


# ==========================================================================
# Data from the real tools
# ==========================================================================
def capture_demo():
    """Run each program and the quiet demo; capture everything."""
    results = {}
    for demo in run_demo.DEMOS:
        program, records, value = run_demo.run_program(demo)
        source = (ROOT / demo.source).read_text(encoding="utf-8")
        results[demo.key] = (demo, program, records, value, source)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        status = run_demo.main(["--quiet"])
    if status != 0:
        raise SystemExit("run_demo failed -- refusing to build the report")
    return results, buf.getvalue()


def capture_tests():
    """Run the unittest suite; return per-module counts and totals."""
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"),
                            top_level_dir=str(ROOT / "tests"))
    per_module = {}

    def walk(s):                 # count first: running empties the suite
        for t in s:
            if isinstance(t, unittest.TestSuite):
                walk(t)
            else:
                mod = type(t).__module__
                per_module[mod] = per_module.get(mod, 0) + 1
    walk(suite)
    result = unittest.TextTestRunner(stream=io.StringIO(),
                                     verbosity=0).run(suite)
    if not result.wasSuccessful() or result.testsRun != sum(
            per_module.values()):
        raise SystemExit("tests failed -- refusing to build the report")
    skipped = {type(t).__module__: why for t, why in result.skipped}
    return per_module, result.testsRun, skipped


# ==========================================================================
# Page decoration: header + "NN/TT" page numbers
# ==========================================================================
class NumberedCanvas(canvas.Canvas):
    """Defers page output so each page can show 'current/total'."""

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self._decorate(total)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _decorate(self, total):
        page = self._pageNumber
        label = "%02d/%02d" % (page, total)
        self.setFillColor(NAVY)
        self.roundRect(PAGE_W / 2 - 24, 20, 48, 17, 4, fill=1, stroke=0)
        self.setFillColor(colors.white)
        self.setFont(BOLD, 9.5)
        self.drawCentredString(PAGE_W / 2, 25.5, label)
        if page > 1:
            self.setStrokeColor(GRID)
            self.setLineWidth(0.6)
            self.line(MARGIN, PAGE_H - 36, PAGE_W - MARGIN, PAGE_H - 36)
            self.setFillColor(GRAY)
            self.setFont(SANS, 7.5)
            self.drawString(MARGIN, PAGE_H - 32,
                            "%s  |  %s" % (CPU_NAME, TITLE))
            self.drawRightString(PAGE_W - MARGIN, PAGE_H - 32, SUBJECT)


# ==========================================================================
# Report sections
# ==========================================================================
def title_page(results, total_tests):
    story = [Spacer(1, 50)]
    big = ParagraphStyle("big", fontName=BOLD, fontSize=30, leading=36,
                         alignment=TA_CENTER, textColor=NAVY)
    sub = ParagraphStyle("sub", fontName=BOLD, fontSize=19, leading=24,
                         alignment=TA_CENTER, textColor=colors.HexColor(
                             "#2A7F9E"))
    tag = ParagraphStyle("tag", fontName=SANS, fontSize=10.5, leading=14,
                         alignment=TA_CENTER, textColor=GRAY)
    story += [Paragraph(p(TITLE), big), Spacer(1, 6),
              Paragraph(p(CPU_NAME), sub), Spacer(1, 6),
              Paragraph(p("8-bit CPU  •  custom 16-bit ISA  •  "
                          "assembler  •  cycle-by-cycle simulator"),
                        tag),
              Spacer(1, 34)]

    info = [[c("<b>Subject</b>"), c(p(SUBJECT))],
            [c("<b>Assignment</b>"), c(p(ASSIGNMENT))],
            [c("<b>Instructor</b>"), c(p(INSTRUCTOR))],
            [c("<b>Date</b>"), c(p(DATE))]]
    story.append(tab_caption("Submission Details"))
    story.append(grid_table(info, [110, 300], header_rows=0, zebra=False,
                            extra=[("BACKGROUND", (0, 0), (0, -1), ZEBRA)]))
    story.append(Spacer(1, 22))

    story.append(tab_caption("Project Contributors"))
    rows = [hd("#", "Name", "Role (details: Section 10)")]
    for i, (name, (role, _, _)) in enumerate(zip(MEMBERS, CONTRIBUTIONS), 1):
        rows.append([c(str(i), "cellc"), c("<b>%s</b>" % p(name)),
                     c(p(role))])
    story.append(grid_table(rows, [24, 190, 196]))
    story.append(Spacer(1, 22))

    _, _, _, va, _ = results["A"]
    _, _, _, vb, _ = results["B"]
    story.append(tab_caption("Results at a Glance (from simulator run)"))
    rows = [hd("Item", "Result", "Status")]
    ok = "✓ PASS" if UNICODE else "PASS"
    for item, res in (("Program A (assembly): 8²", "RAM[0xF0] = 0x%02X "
                       "= %d" % (va, va)),
                      ("Program B (C → assembly): 5!",
                       "RAM[0xF0] = 0x%02X = %d" % (vb, vb)),
                      ("Automated tests", "%d / %d passed"
                       % (total_tests, total_tests))):
        rows.append([c(p(item)), mono(res, True),
                     Paragraph("<font name='%s' color='#1E7B45'>%s</font>"
                               % (MONO_B, ok), S["monoc"])])
    story.append(grid_table(rows, [170, 160, 80]))
    story.append(PageBreak())
    return story


def architecture_page():
    story = h1("1. CPU Architecture")
    d = diagrams.architecture()
    story += [d, fig_caption("MiniCPU-8 Architecture (address, data and "
                             "control paths)")]
    story.append(tab_caption("CPU Specifications"))
    spec = (
        ("Data width", "8 bits (all registers, ALU, RAM cells)"),
        ("Address width / RAM", "8 bits  →  256 bytes (0x00–0xFF)"),
        ("Registers", "R0, R1, R2, R3 (8-bit, general purpose)"),
        ("PC / IR", "8-bit program counter / 16-bit instruction register"),
        ("Flags", "Z (result = 0),  N (result bit 7)"),
        ("Instruction size", "16 bits fixed, big-endian, 2-byte aligned"),
        ("Instructions", "15 defined (opcode 0xE reserved → fault)"),
        ("ALU operations", "ADD SUB MUL INC DEC CMP (results mod 256)"),
        ("Cycle", "1 instruction per step: FETCH → DECODE → "
                  "EXECUTE (Figure 3)"),
        ("Safeguards", "invalid opcode, non-zero reserved bits, bad PC, "
                       "1000-step limit"),
    )
    rows = [hd("Parameter", "Value")] + [[c("<b>%s</b>" % p(k)), c(p(v))]
                                         for k, v in spec]
    story.append(grid_table(rows, [130, 330]))
    story.append(PageBreak())
    return story


def isa_page():
    story = h1("2. Instruction Set Architecture")
    story += [diagrams.instruction_format(),
              fig_caption("MiniCPU-8 Instruction Format (16-bit word)")]
    story.append(tab_caption("Instruction Encoding (generated from isa.py)"))
    rows = [hd("Mnemonic", "Opcode", "Operands", "Encoding (15 → 0)",
               "Operation", "Flags")]
    for op in isa.INSTRUCTIONS:
        rows.append([mono(op.mnemonic, True),
                     mono("0x%X" % op.opcode, True),
                     mono(op.fmt.syntax or "—", True),
                     mono(isa.encoding_pattern(op), True),
                     c(p(op.operation)),
                     c(p(op.flags), "cellc")])
    rows.append([mono("—", True), mono("0xE", True), mono("—", True),
                 mono("1110 xx xx xxxxxxxx", True),
                 c("<i>reserved → CPUError (invalid opcode)</i>"),
                 c("-", "cellc")])
    story.append(grid_table(rows, [52, 40, 64, 116, 142, 36]))
    story.append(Spacer(1, 4))
    story.append(note(p("  ·  ".join((
        "aa = Ra, bb = Rb (00 = R0 … 11 = R3)", "iiiiiiii = imm8",
        "dddddddd = addr8", "0 = must be zero", "Z = 1 if result = 0",
        "N = result bit 7", "'-' = flags unchanged",
        "arithmetic wraps mod 256")))))
    story.append(PageBreak())
    return story


def memory_page():
    story = h1("3. Memory Map & Execution Model")
    story.append(tab_caption("MiniCPU-8 Memory Map"))
    rows = [hd("Address", "Size", "Purpose", "Program A", "Program B")]
    mm = (("0x00–0x7F", "128 B", "Program instructions (max 64)",
           "0x00–0x09", "0x00–0x19"),
          ("0x80–0xEF", "112 B", "General data (free)", "—",
           "—"),
          ("0x%02X" % isa.RESULT_ADDR, "1 B", "RESULT", "result = 64",
           "result = 120"),
          ("0x%02X" % isa.INPUT_ADDR, "1 B", "INPUT operand", "x = 8",
           "n = 5"),
          ("0x%02X" % isa.VAR_ADDR, "1 B", "Loop variable", "—",
           "i"),
          ("0xF3–0xFF", "13 B", "Scratch / reserved", "—",
           "—"))
    for r in mm:
        rows.append([mono(r[0], True), c(r[1], "cellc"), c(p(r[2])),
                     mono(r[3], True), mono(r[4], True)])
    story.append(grid_table(rows, [80, 40, 160, 90, 90], extra=[
        ("BACKGROUND", (0, 3), (-1, 3), HL_RESULT)]))
    story.append(Spacer(1, 10))
    story += [diagrams.cycle(),
              fig_caption("Fetch–Decode–Execute Cycle "
                          "(one CPU.step())")]
    story.append(tab_caption("Assembler Syntax"))
    rows = [hd("Element", "Example", "Meaning")]
    syn = (("Comment", "; text", "ignored to end of line"),
           ("Label", "loop:", "names the current address"),
           ("Register", "R0 … R3", "2-bit register field"),
           ("Number", "12   0x0C   0b1100   -1", "decimal / hex / binary "
                                                 "(negative → two's "
                                                 "complement)"),
           ("Memory operand", "[0xF0]   [result]", "addr8 in brackets"),
           ("Jump target", "JNZ loop", "label or number"),
           (".org", ".org 0xF0", "set location counter"),
           (".byte", ".byte 5, 0x10", "emit data bytes"))
    for r in syn:
        rows.append([c(p(r[0])), mono(r[1]), c(p(r[2]))])
    story.append(grid_table(rows, [90, 150, 220]))
    story.append(PageBreak())
    return story


def encoding_table(program, comments_as="Comment"):
    """Machine-encoding table from the assembler's listing."""
    rows = [hd("Addr", "Bytes", "op", "ra", "rb", "imm8", "Label",
               "Assembly", comments_as)]
    extra = []
    for e in program.listing:
        r = len(rows)
        if e.kind == "instr":
            word = (e.data[0] << 8) | e.data[1]
            f = isa.word_bits(word).split()
            cols = ["%02X %02X" % e.data] + f
        else:
            cols = [" ".join("%02X" % b for b in e.data)] + ["—"] * 4
            extra.append(("BACKGROUND", (0, r), (-1, r), HL_DATA))
        rows.append([mono("0x%02X" % e.address, True)] +
                    [mono(x, True) for x in cols] +
                    [mono(e.label), mono(e.statement), c(p(e.comment))])
    return grid_table(rows, [30, 38, 32, 18, 18, 52, 40, 92, 140],
                      extra=extra)


def initial_ram(program, rows, title):
    code = {e.address + i for e in program.listing if e.kind == "instr"
            for i in range(2)}
    data = {e.address + i for e in program.listing if e.kind == "data"
            for i in range(len(e.data))}
    return [KeepTogether([
        tab_caption(title),
        ram_grid(program.image, rows, header=True, code=code, data=data,
                 result=isa.RESULT_ADDR, cell_h=11, font_size=7.2),
        Spacer(1, 4),
        legend(((HL_CODE, "instruction bytes"), (HL_DATA, "data bytes"),
                (HL_RESULT, "RESULT (0xF0)")))])]


def trace_table(records, rows_shown):
    """One row per executed instruction, with the RAM block after it."""
    ram_head = Table([["RAM block after execution"], [_ram_header()]],
                     rowHeights=[10, 9])
    header = hd("Step", "PC", "IR", "Decoded instruction", "R0", "R1", "R2",
                "R3", "Z", "N") + [ram_head]
    ram_head.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), BOLD, 7.8),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    data, extra = [header], []
    reg_style = ParagraphStyle("reg", parent=S["monoc"], fontSize=6.8,
                               leading=7.6)
    for rec in records:
        r = len(data)
        regs = []
        for i, v in enumerate(rec.regs_after):
            regs.append(Paragraph("%02X<br/><font size='5.6' color='#5F6B7A'>"
                                  "%d</font>" % (v, v), reg_style))
            if v != rec.regs_before[i]:
                extra.append(("BACKGROUND", (4 + i, r), (4 + i, r),
                              HL_CHANGE))
        for k in (0, 1):
            if rec.flags_after[k] != rec.flags_before[k]:
                extra.append(("BACKGROUND", (8 + k, r), (8 + k, r),
                              HL_CHANGE))
        if rec.halted:
            extra.append(("BACKGROUND", (0, r), (9, r), HL_RESULT))
        changed = {w[0] for w in rec.mem_writes}
        data.append([mono("%02d" % rec.step, True),
                     mono("%02X" % rec.pc, True),
                     mono("%04X" % rec.word, True),
                     mono(rec.text),
                     *regs,
                     mono(str(rec.flags_after[0]), True),
                     mono(str(rec.flags_after[1]), True),
                     ram_grid(rec.ram_after, rows_shown, changed=changed,
                              pc=rec.pc)])
    t = grid_table(data, [20, 18, 26, 74, 22, 22, 22, 22, 12, 12,
                          RAM_W + 4], zebra=False, extra=extra + [
        ("LEFTPADDING", (10, 0), (10, -1), 2),
        ("RIGHTPADDING", (10, 0), (10, -1), 2),
        ("TOPPADDING", (0, 1), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (9, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (9, -1), 1.5)])
    return t


def _ram_header():
    t = Table([["addr"] + ["+%X" % i for i in range(16)]],
              colWidths=[RAM_ADDR_W] + [RAM_CELL_W] * 16, rowHeights=8)
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), MONO, 6.2),
                           ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


def trace_legend():
    return legend(((HL_PC, "bytes of executing instruction"),
                   (HL_CHANGE, "changed by this instruction"),
                   (HL_RESULT, "HALT (final state)")))


def final_state(key, claim_markup, value):
    """Large, unmistakable result box."""
    ok = "✓" if UNICODE else "OK"
    big = ParagraphStyle("fs", fontName=MONO_B, fontSize=11, leading=14)
    rows = [[Paragraph("PROGRAM %s — FINAL STATE" % key,
                       ParagraphStyle("fsh", fontName=BOLD, fontSize=11,
                                      leading=14, textColor=colors.white)),
             ""],
            [Paragraph("RESULT ADDRESS", big),
             Paragraph("0x%02X" % isa.RESULT_ADDR, big)],
            [Paragraph("RAM[0x%02X]" % isa.RESULT_ADDR, big),
             Paragraph("0x%02X" % value, big)],
            [Paragraph("DECIMAL", big), Paragraph(str(value), big)],
            [Paragraph("<font color='#1E7B45'>%s %s</font>"
                       % (ok, claim_markup),
                       ParagraphStyle("fsok", fontName=MONO_B, fontSize=14,
                                      leading=18)), ""]]
    t = Table(rows, colWidths=[150, 150], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)), ("SPAN", (0, 4), (1, 4)),
        ("BACKGROUND", (0, 0), (-1, 0), PASS_GREEN),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#EFF9F2")),
        ("BOX", (0, 0), (-1, -1), 1.5, PASS_GREEN),
        ("LINEBELOW", (0, 1), (-1, 3), 0.4, colors.HexColor("#A9D8B8")),
        ("ALIGN", (0, 4), (-1, 4), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    return t


def program_a_pages(results):
    demo, program, records, value, source = results["A"]
    story = h1("4. Program A — 8² = 64 (written directly in "
               "assembly)")
    story += [code_block(asm_markup(source)),
              fig_caption("Program A Source: programs/square8.asm")]
    story.append(tab_caption("Program A Machine Encoding (assembler.py "
                             "output)"))
    story.append(encoding_table(program))
    story.append(Spacer(1, 8))
    story += initial_ram(program, demo.rows,
                         "Program A Initial RAM Block (before execution)")
    story.append(PageBreak())

    story += h1("5. Program A — Execution Trace")
    story.append(tab_caption("Program A Execution Trace (%d instructions; "
                             "registers: hex over decimal)" % len(records)))
    story.append(trace_table(records, demo.rows))
    story += [Spacer(1, 4), trace_legend(), Spacer(1, 14)]
    story.append(KeepTogether([
        tab_caption("Program A Final State"),
        final_state("A", "8² = 64" if UNICODE else "8^2 = 64", value)]))
    story.append(PageBreak())
    return story


# C construct -> the assembly statements (in factorial.asm) that implement it
C_MAPPING = (
    ("unsigned char result, n = 5, i;", "globals",
     (".byte 0", ".byte 5", ".byte 0")),
    ("result = 1;", "statement", ("LDI R0, 1", "STORE R0, [result]")),
    ("i = n", "for: init", ("LOAD R1, [n]", "STORE R1, [i]")),
    ("constant 1 for the test", "setup", ("LDI R2, 1",)),
    ("i > 1", "for: condition", ("CMP R1, R2", "JZ done")),
    ("result *= i;", "loop body", ("MUL R0, R1", "STORE R0, [result]")),
    ("i--", "for: update", ("DEC R1", "STORE R1, [i]")),
    ("}  (back to the test)", "loop edge", ("JMP loop",)),
    ("printf(...); return 0;", "end", ("HALT",)),
)


def mapping_rows(program):
    """Locate every mapped statement in the listing (fails if missing)."""
    entries = list(program.listing)
    used, rows = set(), []
    for c_text, role, stmts in C_MAPPING:
        addrs, asm = [], []
        for stmt in stmts:
            match = next((i for i, e in enumerate(entries)
                          if i not in used and
                          re.sub(r"\s+", " ", e.statement.strip()) == stmt),
                         None)
            if match is None:
                raise SystemExit("C mapping: '%s' not in factorial.asm" % stmt)
            used.add(match)
            e = entries[match]
            addrs.append("0x%02X" % e.address)
            asm.append((e.label + " " if e.label else "") + e.statement)
        rows.append((c_text, role, asm, addrs))
    if len(used) != len(entries):
        raise SystemExit("C mapping does not cover every assembly line")
    return rows


def program_b_pages(results):
    demo, program, records, value, source = results["B"]
    c_source = (ROOT / "programs" / "factorial.c").read_text(encoding="utf-8")
    story = h1("6. Program B — 5! = 120 (C source)")
    story += [code_block(c_markup(c_source)),
              fig_caption("Program B C Source: programs/factorial.c")]

    story.append(tab_caption("Program B Variable Allocation"))
    rows = [hd("C variable", "RAM address", "Register", "Initial value")]
    for var, addr, reg, init in (("result", isa.RESULT_ADDR, "R0", "0"),
                                 ("n", isa.INPUT_ADDR, "R1 (copied)", "5"),
                                 ("i", isa.VAR_ADDR, "R1", "0"),
                                 ("constant 1", None, "R2", "—")):
        rows.append([mono(var, True),
                     mono("0x%02X" % addr if addr else "—", True),
                     mono(reg, True), mono(init, True)])
    story.append(grid_table(rows, [110, 90, 90, 90]))
    story.append(Spacer(1, 6))

    story.append(tab_caption("Manual C-to-MiniCPU-8 Assembly Translation"))
    rows = [hd("C construct", "Role", "MiniCPU-8 assembly", "Address")]
    for c_text, role, asm, addrs in mapping_rows(program):
        rows.append([mono(c_text), c(p(role)), mono_lines(asm),
                     mono_lines(addrs, center=True)])
    story.append(grid_table(rows, [140, 66, 190, 64]))
    story.append(Spacer(1, 4))
    story.append(note(p("Translated by hand (no compiler targets MiniCPU-8). "
                        "Variables live in registers and are written back "
                        "to RAM after each change, so the trace shows them. "
                        "Loop exits when i - 1 = 0 (Z = 1); valid for "
                        "1 ≤ n ≤ 5 (5! = 120 is the largest "
                        "8-bit factorial).")))
    story.append(PageBreak())

    story += h1("7. Program B — Translated Assembly")
    story += [code_block(asm_markup(source)),
              fig_caption("Program B Assembly (manual translation): "
                          "programs/factorial.asm")]
    story.append(tab_caption("Program B Machine Encoding (assembler.py "
                             "output)"))
    story.append(encoding_table(program, comments_as="C meaning"))
    story.append(Spacer(1, 8))
    story += initial_ram(program, demo.rows,
                         "Program B Initial RAM Block (before execution)")
    story.append(PageBreak())

    story += h1("8. Program B — Execution Trace")
    story.append(tab_caption("Program B Execution Trace (%d instructions; "
                             "registers: hex over decimal)" % len(records)))
    story.append(trace_table(records, demo.rows))
    story += [Spacer(1, 4), trace_legend(), Spacer(1, 12)]
    story.append(KeepTogether([
        tab_caption("Program B Final State"),
        final_state("B", "5! = 120", value)]))
    story.append(PageBreak())
    return story


def how_to_run_page(demo_output, per_module, total, skipped):
    story = h1("9. How to Run & Verification")
    commands = ("git clone %s\n"
                "cd CPU-Design\n"
                "python3 run_demo.py          # assemble + run + verify both "
                "programs\n"
                "python3 validate.py          # tests + demos + report check"
                % REPO_URL)
    story += [code_block(_cmd_markup(commands)),
              fig_caption("Commands for the Grader (Python 3.9+, standard "
                          "library only)")]

    story.append(tab_caption("Individual Commands"))
    rows = [hd("Command", "What it does")]
    for cmd, what in (
            ("python3 run_demo.py", "Both programs, full per-step traces, "
                                    "PASS/FAIL, exit 0 on success"),
            ("python3 run_demo.py --quiet", "PASS/FAIL summary only"),
            ("python3 assembler.py programs/square8.asm",
             "Assembly listing + labels"),
            ("python3 cpu.py programs/factorial.asm", "Run any program with "
                                                      "a full trace"),
            ("python3 -m unittest discover -s tests -v", "Automated tests"),
            ("python3 validate.py", "Tests + demos + PDF present; exit 0 "
                                    "only if all pass")):
        rows.append([mono(cmd), c(p(what))])
    story.append(grid_table(rows, [220, 240]))
    story.append(Spacer(1, 6))

    lines = [ln for ln in demo_output.strip().splitlines() if ln.strip()]
    story += [code_block(_cmd_markup("\n".join(lines))),
              fig_caption("Actual Output of python3 run_demo.py --quiet "
                          "(captured while building this report)")]

    story.append(tab_caption("Automated Test Results (run while building "
                             "this report)"))
    covers = {
        "test_assembler": "encoding of all 15 instructions, labels, "
                          "directives, number formats, 12 error cases with "
                          "file:line messages",
        "test_cpu": "every instruction, Z/N flags, LOAD/STORE, jumps, HALT, "
                    "faults, all 65,536 words decode ↔ assemble",
        "test_programs": "Program A = 64, Program B = 120 (n = 1…5), "
                         "saved traces = live output, C reference",
        "test_docs": "README encoding table = isa.py; README expected "
                     "output = real output",
    }
    rows = [hd("Test module", "Tests", "Covers", "Status")]
    for mod in sorted(per_module):
        status = "✓ PASS" if UNICODE else "PASS"
        if mod in skipped:
            status += " (1 skipped)"
        rows.append([mono(mod + ".py"), c(str(per_module[mod]), "cellc"),
                     c(p(covers.get(mod, ""))),
                     Paragraph("<font color='#1E7B45'>%s</font>" % status,
                               S["monoc"])])
    rows.append([c("<b>Total</b>"), c("<b>%d</b>" % total, "cellc"), c(""),
                 Paragraph("<font color='#1E7B45'><b>%d/%d</b></font>"
                           % (total, total), S["monoc"])])
    story.append(grid_table(rows, [90, 36, 270, 64]))
    story.append(PageBreak())
    return story


def _cmd_markup(text):
    out = []
    for line in text.splitlines():
        code, sep, comment = line.partition("#")
        out.append(escape(code) + (COMMENT % escape(sep + comment)
                                   if sep else ""))
    return "\n".join(out)


def team_page():
    story = h1("10. Team Contributions")
    story.append(tab_caption("Team Contributions (specific work items)"))
    rows = [hd("Member", "Area", "Specific contribution", "Files")]
    for name, (role, what, files) in zip(MEMBERS, CONTRIBUTIONS):
        rows.append([c("<b>%s</b>" % p(name)), c(p(role)), c(p(what)),
                     mono_lines(files.split(", "))])
    story.append(grid_table(rows, [80, 70, 190, 120], extra=[
        ("VALIGN", (0, 1), (-1, -1), "TOP")]))
    return story


# ==========================================================================
# Build
# ==========================================================================
def export_svgs():
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    for name, fn in (("architecture", diagrams.architecture),
                     ("instruction_format", diagrams.instruction_format),
                     ("fetch_decode_execute", diagrams.cycle)):
        renderSVG.drawToFile(fn(), str(OUT_FIG / ("%s.svg" % name)))


def main():
    global S
    setup_fonts()
    S = styles()
    results, demo_output = capture_demo()
    per_module, total, skipped = capture_tests()

    story = []
    story += title_page(results, total)
    story += architecture_page()
    story += isa_page()
    story += memory_page()
    story += program_a_pages(results)
    story += program_b_pages(results)
    story += how_to_run_page(demo_output, per_module, total, skipped)
    story += team_page()

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT_PDF), pagesize=letter,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=48, bottomMargin=48,
                            title="%s — %s" % (CPU_NAME, TITLE),
                            author=", ".join(MEMBERS),
                            subject="CPU design, ISA, assembler and "
                                    "simulator report")
    doc.build(story, canvasmaker=NumberedCanvas)
    export_svgs()
    print("Report written: %s  (%d figures, %d tables)"
          % (OUT_PDF.relative_to(ROOT), Counter.figures, Counter.tables))
    print("Figures written: %s/*.svg" % OUT_FIG.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
