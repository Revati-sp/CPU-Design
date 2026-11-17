"""
Vector diagrams for the MiniCPU-8 report (reportlab Drawings).

    architecture()        Figure: CPU datapath / block diagram
    instruction_format()  Figure: 16-bit instruction word layout
    cycle()               Figure: fetch-decode-execute flow

Each function returns a reportlab Drawing that is embedded in the PDF
and also exported to docs/figures/*.svg by build_report.py.
"""

from reportlab.graphics.shapes import (Drawing, Group, Line, Polygon, Rect,
                                       String, PolyLine)
from reportlab.lib import colors

import isa

# ---- palette -------------------------------------------------------------
NAVY = colors.HexColor("#1F3A5F")
ADDR = colors.HexColor("#1F6FD1")      # address bus
DATA = colors.HexColor("#1E9E5A")      # data / instruction bus
CTRL = colors.HexColor("#7A7A7A")      # control / status
FILL = colors.HexColor("#EEF3F8")
FILL_CU = colors.HexColor("#FFF4E0")
FILL_ALU = colors.HexColor("#FDEBEC")
FILL_REG = colors.HexColor("#E8F5EC")
FILL_MEM = colors.HexColor("#EAF1FB")
FIELD_COLORS = (colors.HexColor("#F6C177"), colors.HexColor("#9CCFD8"),
                colors.HexColor("#C4A7E7"), colors.HexColor("#A6DA95"))

FONT = "Helvetica"          # replaced by build_report.set_fonts()
FONT_B = "Helvetica-Bold"
MONO = "Courier"


def set_fonts(sans, sans_bold, mono):
    global FONT, FONT_B, MONO
    FONT, FONT_B, MONO = sans, sans_bold, mono


# ---- primitives ------------------------------------------------------------
def text(x, y, s, size=8, bold=False, color=colors.black, anchor="middle",
         mono=False):
    font = MONO if mono else (FONT_B if bold else FONT)
    if FONT != "Helvetica":                      # Unicode font available
        s = s.replace("<-", "\u2190").replace("->", "\u2192")
    return String(x, y, s, fontName=font, fontSize=size, fillColor=color,
                  textAnchor=anchor)


def box(x, y, w, h, fill=FILL, stroke=NAVY, width=1.2, radius=4):
    return Rect(x, y, w, h, rx=radius, ry=radius, fillColor=fill,
                strokeColor=stroke, strokeWidth=width)


def arrow(points, color, width=1.6, dashed=False, both=False, head=5):
    """Polyline through points with an arrow head at the end."""
    g = Group()
    pl = PolyLine(points, strokeColor=color, strokeWidth=width)
    if dashed:
        pl.strokeDashArray = [3, 2]
    g.add(pl)

    def head_at(x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5 or 1
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        return Polygon([x2, y2,
                        x2 - head * 1.6 * ux + head * px,
                        y2 - head * 1.6 * uy + head * py,
                        x2 - head * 1.6 * ux - head * px,
                        y2 - head * 1.6 * uy - head * py],
                       fillColor=color, strokeColor=color, strokeWidth=0.5)

    g.add(head_at(points[-4], points[-3], points[-2], points[-1]))
    if both:
        g.add(head_at(points[2], points[3], points[0], points[1]))
    return g


def label(x, y, s, color, size=6.5, anchor="middle"):
    """Small bus label with a white backing so it stays readable."""
    g = Group()
    w = len(s) * size * 0.5 + 4
    left = {"middle": x - w / 2, "start": x - 2, "end": x - w + 2}[anchor]
    g.add(Rect(left, y - 2, w, size + 3, fillColor=colors.white,
               strokeColor=None))
    g.add(text(x, y, s, size=size, color=color, anchor=anchor))
    return g


# ---- Figure: architecture ---------------------------------------------------
def architecture():
    d = Drawing(512, 372)

    # RAM with memory-map strip
    d.add(box(8, 52, 122, 268, fill=FILL_MEM))
    d.add(text(69, 304, "RAM", 11, bold=True, color=NAVY))
    d.add(text(69, 293, "256 bytes  (8-bit addr)", 6.5))
    regions = (("0x00-0x7F", "code", 90, FILL_MEM),
               ("0x80-0xEF", "free data", 56, colors.white),
               ("0xF0", "result", 17, colors.HexColor("#DFF3E4")),
               ("0xF1", "input (x / n)", 17, colors.HexColor("#FFF4D6")),
               ("0xF2", "i (Program B)", 17, colors.HexColor("#FFF4D6")),
               ("0xF3-0xFF", "spare", 14, colors.white))
    y = 285
    for addr, name, h, fill in regions:
        y -= h
        d.add(Rect(18, y, 102, h, fillColor=fill, strokeColor=NAVY,
                   strokeWidth=0.6))
        d.add(text(22, y + h / 2 - 2.5, addr, 6.2, anchor="start", mono=True))
        d.add(text(116, y + h / 2 - 2.5, name, 6.2, anchor="end"))
    d.add(text(69, 60, "instruction = 2 bytes", 6.2, color=CTRL))

    # PC
    d.add(box(196, 290, 104, 36))
    d.add(text(248, 312, "PC", 10, bold=True, color=NAVY))
    d.add(text(248, 298, "8-bit, PC <- PC + 2", 6.5))

    # IR with fields
    d.add(box(196, 200, 104, 50))
    d.add(text(248, 236, "IR  (16-bit)", 9, bold=True, color=NAVY))
    fx = 202
    for (name, w), fill in zip((("op", 30), ("ra", 15), ("rb", 15),
                                ("imm8", 32)), FIELD_COLORS):
        d.add(Rect(fx, 207, w, 18, fillColor=fill, strokeColor=NAVY,
                   strokeWidth=0.6))
        d.add(text(fx + w / 2, 213, name, 6.5, mono=True))
        fx += w

    # Control unit
    d.add(box(352, 196, 152, 74, fill=FILL_CU))
    d.add(text(428, 254, "CONTROL UNIT", 10, bold=True, color=NAVY))
    d.add(text(428, 241, "instruction decoder", 7))
    d.add(text(428, 229, "FETCH -> DECODE -> EXECUTE", 6.5, mono=True))
    d.add(text(428, 216, "faults: bad opcode / reserved bits", 6, color=CTRL))
    d.add(text(428, 206, "step limit 1000", 6, color=CTRL))

    # Register file
    d.add(box(196, 66, 104, 104, fill=FILL_REG))
    d.add(text(248, 156, "REGISTER FILE", 8.5, bold=True, color=NAVY))
    for i, name in enumerate(isa.REG_NAMES):
        ry = 130 - i * 19
        d.add(Rect(212, ry, 72, 16, fillColor=colors.white, strokeColor=NAVY,
                   strokeWidth=0.6))
        d.add(text(232, ry + 4.5, name, 7.5, bold=True))
        d.add(text(262, ry + 4.5, "8 bit", 6.5, color=CTRL))

    # ALU (classic notched shape: operands enter wide side, result exits)
    ax, ay = 352, 66
    d.add(Polygon([ax, ay + 100, ax, ay + 60, ax + 14, ay + 50, ax, ay + 40,
                   ax, ay, ax + 84, ay + 26, ax + 84, ay + 74],
                  fillColor=FILL_ALU, strokeColor=NAVY, strokeWidth=1.2))
    d.add(text(ax + 46, ay + 62, "ALU", 11, bold=True, color=NAVY))
    d.add(text(ax + 46, ay + 48, "ADD SUB MUL", 6, mono=True))
    d.add(text(ax + 46, ay + 39, "INC DEC CMP", 6, mono=True))
    d.add(text(ax + 46, ay + 27, "mod 256", 6, color=CTRL))

    # Flags
    d.add(box(458, 96, 48, 44, fill=colors.white))
    d.add(text(482, 127, "FLAGS", 7, bold=True, color=NAVY))
    d.add(Rect(463, 102, 18, 16, fillColor=FILL, strokeColor=NAVY,
               strokeWidth=0.6))
    d.add(Rect(483, 102, 18, 16, fillColor=FILL, strokeColor=NAVY,
               strokeWidth=0.6))
    d.add(text(472, 107, "Z", 8, bold=True))
    d.add(text(492, 107, "N", 8, bold=True))

    # ---- buses: address (blue) ----
    d.add(arrow([196, 308, 130, 308], ADDR))
    d.add(label(163, 312, "fetch addr", ADDR))
    d.add(arrow([196, 210, 130, 210], ADDR))
    d.add(label(163, 196, "addr8 (LOAD/STORE)", ADDR, size=6))
    d.add(arrow([284, 250, 284, 290], ADDR))
    d.add(label(284, 266, "addr8 (jumps)", ADDR, size=6))

    # ---- buses: data / instruction (green) ----
    d.add(arrow([130, 236, 196, 236], DATA))
    d.add(label(163, 240, "instruction", DATA))
    d.add(arrow([130, 112, 196, 112], DATA, both=True))
    d.add(label(163, 116, "data", DATA))
    d.add(label(163, 100, "LOAD / STORE", DATA, size=6))
    d.add(arrow([232, 200, 232, 170], DATA))
    d.add(label(232, 182, "imm8 (LDI)", DATA, size=6))
    d.add(arrow([300, 146, 352, 146], DATA))
    d.add(label(326, 150, "A = Ra", DATA, size=6))
    d.add(arrow([300, 86, 352, 86], DATA))
    d.add(label(326, 90, "B = Rb", DATA, size=6))
    d.add(arrow([436, 116, 458, 116], DATA, width=1.2))
    d.add(arrow([446, 116, 446, 50, 248, 50, 248, 66], DATA))
    d.add(label(347, 46, "result -> Ra", DATA, size=6))

    # ---- control / status (gray dashed) ----
    d.add(arrow([300, 225, 352, 225], CTRL, dashed=True))
    d.add(label(326, 229, "op ra rb", CTRL, size=6))
    d.add(arrow([397, 196, 397, 154], CTRL, dashed=True))
    d.add(label(397, 176, "ALU op", CTRL, size=6))
    d.add(arrow([482, 140, 482, 196], CTRL, dashed=True))
    d.add(label(482, 164, "Z, N", CTRL, size=6))
    d.add(arrow([360, 196, 360, 182, 300, 160], CTRL, dashed=True))
    d.add(label(338, 184, "reg write", CTRL, size=6))
    d.add(arrow([428, 270, 428, 308, 300, 308], CTRL, dashed=True))
    d.add(label(364, 312, "PC write (branch)", CTRL, size=6))
    d.add(arrow([470, 270, 470, 336, 69, 336, 69, 320], CTRL, dashed=True))
    d.add(label(270, 340, "RAM read / write", CTRL, size=6))

    # ---- legend ----
    lx, ly = 150, 10
    for i, (name, color, dashed) in enumerate(
            (("address bus", ADDR, False), ("data / instruction bus", DATA,
                                            False),
             ("control / status", CTRL, True))):
        x = lx + i * 120
        ln = Line(x, ly + 3, x + 24, ly + 3, strokeColor=color, strokeWidth=2)
        if dashed:
            ln.strokeDashArray = [3, 2]
        d.add(ln)
        d.add(text(x + 30, ly, name, 7, anchor="start"))
    return d


# ---- Figure: instruction format --------------------------------------------
def instruction_format():
    d = Drawing(512, 168)
    cell, x0 = 28, 32
    fields = (("opcode", 4, FIELD_COLORS[0]), ("ra", 2, FIELD_COLORS[1]),
              ("rb", 2, FIELD_COLORS[2]), ("imm8 / addr8", 8,
                                           FIELD_COLORS[3]))

    def word_row(y, bits=None):
        x = x0
        for _, width, fill in fields:
            d.add(Rect(x, y, cell * width, 20, fillColor=fill,
                       strokeColor=NAVY, strokeWidth=1.6))
            if bits:                    # thin per-bit dividers
                for k in range(1, width):
                    d.add(Line(x + k * cell, y, x + k * cell, y + 20,
                               strokeColor=NAVY, strokeWidth=0.5))
            x += cell * width
        if bits:
            for i, b in enumerate(bits):
                d.add(text(x0 + i * cell + cell / 2, y + 6, b, 9, bold=True,
                           mono=True))

    # bit numbers + generic word
    for i in range(16):
        d.add(text(x0 + i * cell + cell / 2, 148, str(15 - i), 7,
                   color=CTRL))
    word_row(122)
    x = x0
    for name, width, _ in fields:
        d.add(text(x + cell * width / 2, 128, name, 8.5, bold=True))
        d.add(text(x + cell * width / 2, 110, "bits %d-%d (%d)"
                   % (15 - (x - x0) // cell, 16 - (x - x0) // cell - width,
                      width), 6.5, color=CTRL))
        x += cell * width

    # example word
    example = isa.encode("ADD", 1, 2, 0)
    bits = "{:016b}".format(example)
    d.add(text(x0, 86, "Example:  ADD R1, R2  =  0x%04X" % example, 8,
               bold=True, anchor="start"))
    word_row(58, bits)
    x = x0
    for note, width in (("ADD = 0x5", 4), ("R1", 2), ("R2", 2),
                        ("unused -> must be 0", 8)):
        d.add(text(x + cell * width / 2, 46, note, 7, color=NAVY))
        x += cell * width

    d.add(text(x0, 22, "Register code:  00 = R0   01 = R1   10 = R2   "
               "11 = R3          Byte order: big-endian (RAM[PC] = bits "
               "15-8, RAM[PC+1] = bits 7-0)", 6.8, anchor="start"))
    d.add(text(x0, 8, "Unused fields must be zero; the decoder rejects any "
               "other value, so every word has exactly one meaning.", 6.8,
               anchor="start", color=CTRL))
    return d


# ---- Figure: fetch / decode / execute ---------------------------------------
def cycle():
    d = Drawing(512, 176)
    steps = (("1  FETCH", ("IR <- RAM[PC] : RAM[PC+1]", "PC <- PC + 2")),
             ("2  DECODE", ("op=IR[15:12] ra=IR[11:10]",
                            "rb=IR[9:8]  imm8=IR[7:0]")),
             ("3  EXECUTE", ("ALU / LOAD / STORE / branch",
                             "update Z, N (ALU ops only)")))
    w, h, y, gap = 128, 66, 92, 22
    x = 6
    for i, (title, lines) in enumerate(steps):
        d.add(box(x, y, w, h, fill=(FILL, FILL_CU, FILL_REG)[i]))
        d.add(text(x + w / 2, y + h - 16, title, 10, bold=True, color=NAVY))
        for j, line in enumerate(lines):
            d.add(text(x + w / 2, y + 26 - j * 13, line, 6.6, mono=True))
        if i < 2:
            d.add(arrow([x + w, y + h / 2, x + w + gap, y + h / 2], NAVY))
        x += w + gap

    # HALT decision
    cx, cy = 482, y + h / 2
    d.add(Polygon([cx, cy + 26, cx + 28, cy, cx, cy - 26, cx - 28, cy],
                  fillColor=colors.white, strokeColor=NAVY, strokeWidth=1.2))
    d.add(text(cx, cy - 3, "HALT?", 7.5, bold=True, color=NAVY))
    d.add(arrow([x - gap + 2, cy, cx - 28, cy], NAVY))   # execute -> HALT?

    # "no" -> back to fetch
    d.add(arrow([cx, cy + 26, cx, 172, 80, 172, 80, y + h], NAVY))
    d.add(label(280, 168, "no: next instruction (PC already advanced or "
                "branched)", NAVY, size=6.5))

    # "yes" -> stop
    d.add(arrow([cx, cy - 26, cx, 52], colors.HexColor("#1E7B45")))
    d.add(text(cx + 4, 64, "yes", 7, anchor="start",
               color=colors.HexColor("#1E7B45")))
    d.add(box(cx - 30, 30, 60, 22, fill=colors.HexColor("#DFF3E4")))
    d.add(text(cx, 38, "STOP", 8, bold=True, color=colors.HexColor("#1E7B45")))

    # fault path
    d.add(arrow([250, y, 250, 52], colors.HexColor("#C0392B"), dashed=True))
    d.add(box(130, 22, 240, 30, fill=colors.HexColor("#FDEBEC"),
              stroke=colors.HexColor("#C0392B")))
    d.add(text(250, 39, "CPUError: invalid opcode 0xE, reserved bits set,",
               6.6, color=colors.HexColor("#C0392B")))
    d.add(text(250, 29, "odd/out-of-range PC, or > 1000 steps", 6.6,
               color=colors.HexColor("#C0392B")))
    d.add(text(6, 4, "One loop iteration = one 'STEP' row in the execution "
               "traces.", 6.8, anchor="start", color=CTRL))
    return d
