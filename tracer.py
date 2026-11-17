"""
Text formatting for MiniCPU-8 execution traces.

Every executed instruction produces one block showing
    step, PC, raw IR word (hex + bit fields), decoded instruction,
    R0..R3 (hex + decimal), Z/N flags, next PC,
    RAM writes (address: before -> after), and
    the selected RAM block AFTER the instruction.

A '*' after a value marks something this instruction changed.
"""

import isa
from assembler import format_listing

RULE = "=" * 78
THIN = "-" * 78


def format_ram_block(ram, rows, changed=()):
    """Selected 16-byte RAM rows; changed addresses get a '*' marker."""
    lines = ["        " + " ".join("+%X" % c for c in range(16))]
    for base in rows:
        cells = []
        for addr in range(base, base + 16):
            mark = "*" if addr in changed else " "
            cells.append("%02X%s" % (ram[addr], mark))
        lines.append("  0x%02X: %s" % (base, "".join(cells).rstrip()))
    return "\n".join(lines)


def format_registers(regs, changed=()):
    """'R0=0x40 (64)*  R1=0x08 (8)  ...' with '*' on changed registers."""
    parts = []
    for i, value in enumerate(regs):
        mark = "*" if i in changed else ""
        parts.append("%s=0x%02X %-6s" % (isa.REG_NAMES[i], value,
                                         "(%d)%s" % (value, mark)))
    return " ".join(parts).rstrip()


def format_step(rec, rows):
    """One execution-trace block for a StepRecord."""
    reg_changed = [i for i in range(isa.NUM_REGS)
                   if rec.regs_before[i] != rec.regs_after[i]]
    flag_mark = "*" if rec.flags_before != rec.flags_after else ""
    writes = ", ".join("[0x%02X] 0x%02X -> 0x%02X" % w for w in rec.mem_writes)
    changed = {w[0] for w in rec.mem_writes}
    return "\n".join([
        THIN,
        "STEP %02d | PC 0x%02X | IR 0x%04X = %s | %s"
        % (rec.step, rec.pc, rec.word, isa.word_bits(rec.word), rec.text),
        "  Registers : " + format_registers(rec.regs_after, reg_changed),
        "  Flags     : Z=%d N=%d%s   Next PC: 0x%02X%s"
        % (rec.flags_after[0], rec.flags_after[1], flag_mark, rec.next_pc,
           "   (HALTED)" if rec.halted else ""),
        "  RAM write : " + (writes or "none"),
        "  RAM block after execution:",
        format_ram_block(rec.ram_after, rows, changed),
    ])


def format_trace(source_name, program, records, rows, footer=""):
    """Complete trace: listing, initial state, every step, footer."""
    out = [
        RULE,
        "MiniCPU-8 EXECUTION TRACE : %s" % source_name,
        RULE,
        "",
        "ASSEMBLY LISTING (machine code produced by assembler.py)",
        format_listing(program),
        "",
        "INITIAL STATE",
        "  Registers : " + format_registers((0,) * isa.NUM_REGS),
        "  Flags     : Z=0 N=0   PC: 0x00",
        "  RAM block before execution:",
        format_ram_block(program.image, rows),
        "",
        "Legend: '*' = changed by this instruction.  All values hex unless "
        "shown in (decimal).",
    ]
    out.extend(format_step(rec, rows) for rec in records)
    out.append(THIN)
    out.append("HALT reached after %d instructions." % len(records))
    if footer:
        out.extend(["", footer])
    return "\n".join(out) + "\n"
