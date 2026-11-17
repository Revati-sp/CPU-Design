#!/usr/bin/env python3
"""
MiniCPU-8 two-pass assembler.

Usage
    python3 assembler.py programs/square8.asm             # print listing
    python3 assembler.py programs/square8.asm -o out.hex  # also save RAM image

Syntax (one statement per line, case-insensitive mnemonics/registers)
    ; comment                      everything after ';' is ignored
    label:                         define a label (case-sensitive)
    .org  0xF0                     set the location counter
    .byte 8, 0x10, 0b101, -1       emit data bytes
    LDI   R0, 1                    register + immediate (-128..255)
    LOAD  R1, [n]                  register + memory operand in brackets
    JNZ   loop                     jump target (label or number)

Numbers: decimal (12), hex (0x0C) or binary (0b1100).
Pass 1 assigns addresses to labels; pass 2 encodes using isa.encode().
"""

import argparse
import re
import sys
from collections import namedtuple

import isa

LABEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# One row of the assembly listing (instruction or data)
ListingEntry = namedtuple("ListingEntry",
                          "address data line_no label statement comment kind")
#   data      : tuple of bytes emitted at `address`
#   label     : label(s) defined on the line, e.g. "loop:" (or "")
#   statement : normalized statement, e.g. "CMP R1, R2"
#   comment   : text after ';' (or "")
#   kind      : "instr" or "data"


class AssemblyError(Exception):
    """Syntax or semantic error, reported with file name and line number."""

    def __init__(self, line_no, message, source="", filename="<source>"):
        self.line_no = line_no
        self.message = message
        self.source = source
        self.filename = filename
        super().__init__(str(self))

    def __str__(self):
        text = "%s:%d: error: %s" % (self.filename, self.line_no, self.message)
        if self.source:
            text += "\n    %s" % self.source.strip()
        return text


class Program:
    """Result of assembly: a 256-byte RAM image plus listing and labels."""

    def __init__(self, image, listing, labels):
        self.image = image          # bytearray(256)
        self.listing = listing      # list of ListingEntry
        self.labels = labels        # {name: address}

    def instructions(self):
        return [e for e in self.listing if e.kind == "instr"]


# --------------------------------------------------------------------------
# Line parsing
# --------------------------------------------------------------------------
_Line = namedtuple("_Line", "line_no source labels head operands")


def _split_line(line_no, source):
    """Strip comments, peel off labels, split mnemonic and operands."""
    text = source.split(";", 1)[0].strip()
    labels = []
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:(.*)$", text)
        if not m:
            break
        labels.append(m.group(1))
        text = m.group(2).strip()
    if not text:
        return _Line(line_no, source, labels, None, [])
    parts = text.split(None, 1)
    head = parts[0].upper()
    operands = []
    if len(parts) > 1:
        operands = [op.strip() for op in parts[1].split(",")]
        if any(op == "" for op in operands):
            raise AssemblyError(line_no, "empty operand", source)
    return _Line(line_no, source, labels, head, operands)


def _parse_number(token):
    """Return int for a numeric literal, or None if `token` is not one."""
    t = token.strip().lower()
    neg = t.startswith("-")
    if neg:
        t = t[1:]
    try:
        if t.startswith("0x"):
            value = int(t[2:], 16)
        elif t.startswith("0b"):
            value = int(t[2:], 2)
        elif t.isdigit():
            value = int(t, 10)
        else:
            return None
    except ValueError:
        return None
    return -value if neg else value


# --------------------------------------------------------------------------
# Assembler
# --------------------------------------------------------------------------
def assemble(source_text, filename="<source>"):
    """Assemble MiniCPU-8 source text and return a Program."""

    def error(line, message):
        return AssemblyError(line.line_no, message, line.source, filename)

    # ---- Pass 1: parse lines, assign addresses, collect labels ----------
    lines, labels, labels_seen = [], {}, {}
    location = 0
    for line_no, source in enumerate(source_text.splitlines(), start=1):
        try:
            line = _split_line(line_no, source)
        except AssemblyError as exc:
            exc.filename = filename
            raise
        for name in line.labels:
            upper = name.upper()
            if upper in isa.BY_MNEMONIC or upper in isa.REG_NAMES:
                raise error(line, "label '%s' is a reserved word" % name)
            if name in labels:
                raise error(line, "duplicate label '%s' (first defined on "
                                  "line %d)" % (name, labels_seen[name]))
            labels[name] = location
            labels_seen[name] = line_no
        if line.head is None:
            continue

        if line.head == ".ORG":
            if len(line.operands) != 1:
                raise error(line, ".org expects exactly one address")
            value = _parse_number(line.operands[0])
            if value is None or not 0 <= value < isa.MEM_SIZE:
                raise error(line, ".org address must be 0..255")
            location = value
            lines.append((line, location, 0))
        elif line.head == ".BYTE":
            if not line.operands:
                raise error(line, ".byte expects at least one value")
            lines.append((line, location, len(line.operands)))
            location += len(line.operands)
        elif line.head in isa.BY_MNEMONIC:
            if location % 2:
                raise error(line, "instruction at odd address 0x%02X "
                                  "(instructions must be 2-byte aligned)"
                            % location)
            lines.append((line, location, isa.WORD_BYTES))
            location += isa.WORD_BYTES
        elif line.head.startswith("."):
            raise error(line, "unknown directive '%s'" % line.head.lower())
        else:
            raise error(line, "unknown mnemonic '%s'" % line.head)

        if location > isa.MEM_SIZE:
            raise error(line, "program does not fit in 256 bytes of RAM")

    # ---- Pass 2: encode ---------------------------------------------------
    image = bytearray(isa.MEM_SIZE)
    written = {}                       # address -> line_no (overlap check)
    listing = []

    def value_of(line, token, low, high, what):
        value = _parse_number(token)
        if value is None:
            if not LABEL_RE.match(token):
                raise error(line, "invalid %s '%s'" % (what, token))
            if token.upper() in isa.REG_NAMES:
                raise error(line, "expected %s, got register '%s'"
                            % (what, token))
            if token not in labels:
                raise error(line, "undefined label '%s'" % token)
            value = labels[token]
        if not low <= value <= high:
            raise error(line, "%s %d out of range (%d..%d)"
                        % (what, value, low, high))
        return value & 0xFF            # negative values -> two's complement

    def register(line, token):
        name = token.strip().upper()
        if name not in isa.REG_NAMES:
            raise error(line, "invalid register '%s' (use R0..R3)" % token)
        return isa.REG_NAMES.index(name)

    def memory_operand(line, token):
        m = re.match(r"^\[\s*(.+?)\s*\]$", token)
        if not m:
            raise error(line, "memory operand must be in brackets, "
                              "e.g. [0xF0] or [result]")
        return value_of(line, m.group(1), 0, 255, "address")

    for line, address, size in lines:
        if line.head == ".ORG":
            continue
        if line.head == ".BYTE":
            data = tuple(value_of(line, tok, -128, 255, "byte value")
                         for tok in line.operands)
            kind = "data"
        else:
            op = isa.BY_MNEMONIC[line.head]
            fmt, ops = op.fmt, line.operands
            expected = len([s for s in fmt.syntax.split(",") if s.strip()])
            if len(ops) != expected:
                raise error(line, "%s expects %d operand(s): %s %s"
                            % (op.mnemonic, expected, op.mnemonic, fmt.syntax))
            ra = rb = imm = 0
            if fmt is isa.F_REG_IMM:
                ra = register(line, ops[0])
                imm = value_of(line, ops[1], -128, 255, "immediate")
            elif fmt is isa.F_REG_MEM:
                ra = register(line, ops[0])
                imm = memory_operand(line, ops[1])
            elif fmt is isa.F_REG_REG:
                ra, rb = register(line, ops[0]), register(line, ops[1])
            elif fmt is isa.F_REG:
                ra = register(line, ops[0])
            elif fmt is isa.F_ADDR:
                imm = value_of(line, ops[0], 0, 255, "address")
            word = isa.encode(op.mnemonic, ra, rb, imm)
            data = (word >> 8, word & 0xFF)
            kind = "instr"

        for offset, byte in enumerate(data):
            addr = address + offset
            if addr in written:
                raise error(line, "address 0x%02X already used by line %d"
                            % (addr, written[addr]))
            written[addr] = line.line_no
            image[addr] = byte
        statement = " ".join(filter(None, (
            line.head if kind == "instr" else line.head.lower(),
            ", ".join(line.operands))))
        comment = line.source.split(";", 1)[1].strip() \
            if ";" in line.source else ""
        listing.append(ListingEntry(
            address, data, line.line_no,
            " ".join(name + ":" for name in line.labels),
            statement, comment, kind))

    return Program(image, listing, labels)


def assemble_file(path):
    """Read and assemble a .asm file."""
    with open(path, "r", encoding="utf-8") as handle:
        return assemble(handle.read(), filename=str(path))


# --------------------------------------------------------------------------
# Text output
# --------------------------------------------------------------------------
def format_listing(program):
    """Assembly listing: address, machine word, bit fields, source."""
    rows = ["ADDR  WORD  %-21s  %-7s  %-18s  ; COMMENT"
            % ("op   ra rb imm", "LABEL", "STATEMENT"),
            "----  ----  ---------------------  -------  "
            "------------------  " + "-" * 26]
    for e in program.listing:
        if e.kind == "instr":
            word = (e.data[0] << 8) | e.data[1]
            code, bits = "%04X" % word, isa.word_bits(word)
        else:
            code, bits = " ".join("%02X" % b for b in e.data), "(data)"
        comment = "; " + e.comment if e.comment else ""
        rows.append(("0x%02X  %-4s  %-21s  %-7s  %-18s  %s"
                     % (e.address, code, bits, e.label, e.statement,
                        comment)).rstrip())
    return "\n".join(rows)


def format_image(image):
    """Full 256-byte RAM image as a 16x16 hex grid."""
    rows = ["      " + " ".join("+%X" % c for c in range(16))]
    for base in range(0, isa.MEM_SIZE, 16):
        rows.append("0x%02X: " % base +
                    " ".join("%02X" % b for b in image[base:base + 16]))
    return "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MiniCPU-8 assembler")
    parser.add_argument("source", help="assembly file (.asm)")
    parser.add_argument("-o", "--output",
                        help="write the 256-byte RAM image as hex text")
    args = parser.parse_args(argv)
    try:
        program = assemble_file(args.source)
    except (AssemblyError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    print(format_listing(program))
    print("\nLABELS: " + ", ".join("%s=0x%02X" % (k, v)
                                   for k, v in sorted(program.labels.items(),
                                                      key=lambda kv: kv[1])))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(format_image(program.image) + "\n")
        print("RAM image written to %s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
