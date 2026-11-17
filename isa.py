"""
MiniCPU-8 Instruction Set Architecture -- the single source of truth.

The assembler, the CPU decoder, the tests and the PDF report all import
this module, so documentation, assembler and simulator cannot disagree.

Instruction word (16 bits, stored big-endian: high byte at the lower address)

    15      12 11  10 9    8 7                0
    +---------+------+------+------------------+
    | opcode  |  ra  |  rb  |   imm8 / addr8   |
    +---------+------+------+------------------+
      4 bits   2 bits 2 bits       8 bits

Fields an instruction does not use MUST be zero; the decoder rejects
anything else, so every 16-bit word has at most one meaning.
"""

from collections import namedtuple

# --------------------------------------------------------------------------
# Machine parameters
# --------------------------------------------------------------------------
MEM_SIZE = 256                       # bytes of RAM (8-bit addresses)
NUM_REGS = 4                         # R0..R3
REG_NAMES = ("R0", "R1", "R2", "R3")
WORD_BYTES = 2                       # every instruction is 16 bits wide

# Memory map (Table 3 in the report)
CODE_START, CODE_END = 0x00, 0x7F    # program instructions
DATA_START, DATA_END = 0x80, 0xEF    # general-purpose data (free)
RESULT_ADDR = 0xF0                   # program result
INPUT_ADDR = 0xF1                    # program input operand
VAR_ADDR = 0xF2                      # loop variable (Program B: i)

# --------------------------------------------------------------------------
# Operand formats: which fields an instruction uses
# --------------------------------------------------------------------------
Format = namedtuple("Format", "syntax uses_ra uses_rb uses_imm pattern")

F_NONE = Format("",            False, False, False, "oooo 00 00 00000000")
F_REG_IMM = Format("Ra, imm8",  True, False, True,  "oooo aa 00 iiiiiiii")
F_REG_MEM = Format("Ra, [addr]", True, False, True, "oooo aa 00 dddddddd")
F_REG_REG = Format("Ra, Rb",    True, True,  False, "oooo aa bb 00000000")
F_REG = Format("Ra",            True, False, False, "oooo aa 00 00000000")
F_ADDR = Format("addr",         False, False, True, "oooo 00 00 dddddddd")

# --------------------------------------------------------------------------
# Instruction table (Table 2 in the report)
#   flags: "Z N" = instruction updates Z and N;  "-" = flags unchanged
# --------------------------------------------------------------------------
Op = namedtuple("Op", "mnemonic opcode fmt operation flags")

INSTRUCTIONS = (
    Op("NOP",   0x0, F_NONE,    "no operation",              "-"),
    Op("LDI",   0x1, F_REG_IMM, "Ra <- imm8",                "-"),
    Op("LOAD",  0x2, F_REG_MEM, "Ra <- RAM[addr]",           "-"),
    Op("STORE", 0x3, F_REG_MEM, "RAM[addr] <- Ra",           "-"),
    Op("MOV",   0x4, F_REG_REG, "Ra <- Rb",                  "-"),
    Op("ADD",   0x5, F_REG_REG, "Ra <- Ra + Rb",             "Z N"),
    Op("SUB",   0x6, F_REG_REG, "Ra <- Ra - Rb",             "Z N"),
    Op("MUL",   0x7, F_REG_REG, "Ra <- Ra * Rb (low 8 bits)", "Z N"),
    Op("INC",   0x8, F_REG,     "Ra <- Ra + 1",              "Z N"),
    Op("DEC",   0x9, F_REG,     "Ra <- Ra - 1",              "Z N"),
    Op("CMP",   0xA, F_REG_REG, "Ra - Rb (result discarded)", "Z N"),
    Op("JMP",   0xB, F_ADDR,    "PC <- addr",                "-"),
    Op("JZ",    0xC, F_ADDR,    "if Z = 1: PC <- addr",      "-"),
    Op("JNZ",   0xD, F_ADDR,    "if Z = 0: PC <- addr",      "-"),
    Op("HALT",  0xF, F_NONE,    "stop execution",            "-"),
)
RESERVED_OPCODES = (0xE,)            # decoding 0xE raises DecodeError

BY_MNEMONIC = {op.mnemonic: op for op in INSTRUCTIONS}
BY_OPCODE = {op.opcode: op for op in INSTRUCTIONS}

# Flag rules (apply to every instruction whose flags column is "Z N")
#   Z = 1 if the 8-bit result is 0x00, else 0
#   N = bit 7 of the 8-bit result (1 = negative in two's complement)
# Arithmetic wraps modulo 256.

Decoded = namedtuple("Decoded", "op ra rb imm")


class DecodeError(ValueError):
    """Raised when a 16-bit word is not a valid MiniCPU-8 instruction."""


def encode(mnemonic, ra=0, rb=0, imm=0):
    """Return the 16-bit machine word for one instruction."""
    op = BY_MNEMONIC[mnemonic]
    for value, limit, name in ((ra, 3, "ra"), (rb, 3, "rb"),
                               (imm, 255, "imm")):
        if not 0 <= value <= limit:
            raise ValueError("%s field out of range: %r" % (name, value))
    return (op.opcode << 12) | (ra << 10) | (rb << 8) | imm


def decode(word):
    """Split a 16-bit word into (op, ra, rb, imm); reject invalid words."""
    if not 0 <= word <= 0xFFFF:
        raise DecodeError("word out of range: %r" % (word,))
    opcode = (word >> 12) & 0xF
    ra = (word >> 10) & 0x3
    rb = (word >> 8) & 0x3
    imm = word & 0xFF

    op = BY_OPCODE.get(opcode)
    if op is None:
        raise DecodeError("invalid opcode 0x%X in word 0x%04X"
                          % (opcode, word))
    fmt = op.fmt
    if (not fmt.uses_ra and ra) or (not fmt.uses_rb and rb) or \
            (not fmt.uses_imm and imm):
        raise DecodeError("reserved field is non-zero in %s word 0x%04X"
                          % (op.mnemonic, word))
    return Decoded(op, ra, rb, imm)


def disassemble(word):
    """Return readable assembly text for a valid 16-bit word."""
    d = decode(word)
    fmt, name = d.op.fmt, d.op.mnemonic
    ra, rb = REG_NAMES[d.ra], REG_NAMES[d.rb]
    if fmt is F_NONE:
        return name
    if fmt is F_REG_IMM:
        return "%s %s, %d" % (name, ra, d.imm)
    if fmt is F_REG_MEM:
        return "%s %s, [0x%02X]" % (name, ra, d.imm)
    if fmt is F_REG_REG:
        return "%s %s, %s" % (name, ra, rb)
    if fmt is F_REG:
        return "%s %s" % (name, ra)
    return "%s 0x%02X" % (name, d.imm)           # F_ADDR


def encoding_pattern(op):
    """Bit pattern with the literal opcode, e.g. '0101 aa bb 00000000'."""
    return "{:04b}".format(op.opcode) + op.fmt.pattern[4:]


def word_bits(word):
    """Format a word as grouped bits: 'oooo aa bb iiiiiiii'."""
    b = "{:016b}".format(word)
    return "%s %s %s %s" % (b[0:4], b[4:6], b[6:8], b[8:16])
