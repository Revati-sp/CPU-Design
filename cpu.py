#!/usr/bin/env python3
"""
MiniCPU-8 simulator: 256-byte RAM, R0..R3, 8-bit PC, Z/N flags.

Each call to CPU.step() performs one full instruction cycle

    FETCH    IR <- RAM[PC] : RAM[PC+1]      (big-endian 16-bit word)
             PC <- PC + 2
    DECODE   opcode / ra / rb / imm8 via isa.decode()
    EXECUTE  ALU / memory / branch, update flags, or HALT

and returns a StepRecord describing exactly what changed, which the
tracer turns into the per-instruction execution trace.

Usage
    python3 cpu.py programs/factorial.asm               # run + full trace
    python3 cpu.py programs/factorial.asm --rows 00,10,F0 --max-steps 500
"""

import argparse
import sys
from collections import namedtuple

import assembler
import isa
import tracer

DEFAULT_MAX_STEPS = 1000            # guard against accidental infinite loops

StepRecord = namedtuple("StepRecord", [
    "step",          # 1-based instruction count
    "pc",            # address the instruction was fetched from
    "word",          # 16-bit instruction register (IR) value
    "text",          # disassembled instruction
    "regs_before",   # tuple(R0..R3) before execution
    "regs_after",    # tuple(R0..R3) after execution
    "flags_before",  # (Z, N) before execution
    "flags_after",   # (Z, N) after execution
    "next_pc",       # PC after execution
    "mem_writes",    # tuple of (address, old_byte, new_byte)
    "ram_after",     # bytes: full RAM snapshot after execution
    "halted",        # True if this instruction was HALT
])


class CPUError(RuntimeError):
    """Run-time fault: invalid instruction, bad PC, or step limit hit."""


class CPU:
    """Cycle-level model of MiniCPU-8 (one instruction per step)."""

    def __init__(self, max_steps=DEFAULT_MAX_STEPS):
        self.max_steps = max_steps
        self.reset()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def reset(self):
        """Clear RAM, registers, flags and PC."""
        self.ram = bytearray(isa.MEM_SIZE)
        self.regs = [0] * isa.NUM_REGS
        self.pc = 0
        self.z = 0
        self.n = 0
        self.halted = False
        self.steps = 0

    def load(self, image):
        """Reset and copy a 256-byte RAM image (e.g. Program.image)."""
        if len(image) != isa.MEM_SIZE:
            raise CPUError("RAM image must be exactly %d bytes" % isa.MEM_SIZE)
        self.reset()
        self.ram[:] = image

    # ------------------------------------------------------------------
    # Instruction cycle
    # ------------------------------------------------------------------
    def fetch(self):
        """Read the 16-bit word at PC (high byte first)."""
        if self.pc % 2 or self.pc > isa.MEM_SIZE - 2:
            raise CPUError("invalid PC 0x%02X (must be even and <= 0xFE)"
                           % self.pc)
        return (self.ram[self.pc] << 8) | self.ram[self.pc + 1]

    def _set_flags(self, value):
        self.z = 1 if value == 0 else 0
        self.n = (value >> 7) & 1

    def step(self):
        """Execute exactly one instruction and return its StepRecord."""
        if self.halted:
            raise CPUError("CPU is halted")
        if self.steps >= self.max_steps:
            raise CPUError("step limit of %d reached at PC 0x%02X "
                           "(possible infinite loop)"
                           % (self.max_steps, self.pc))

        pc = self.pc
        regs_before = tuple(self.regs)
        flags_before = (self.z, self.n)

        # FETCH
        word = self.fetch()
        self.pc = (pc + isa.WORD_BYTES) & 0xFF

        # DECODE
        try:
            op, ra, rb, imm = isa.decode(word)
        except isa.DecodeError as exc:
            raise CPUError("at PC 0x%02X: %s" % (pc, exc))

        # EXECUTE
        writes = []
        m = op.mnemonic
        r = self.regs
        if m == "NOP":
            pass
        elif m == "LDI":
            r[ra] = imm
        elif m == "LOAD":
            r[ra] = self.ram[imm]
        elif m == "STORE":
            writes.append((imm, self.ram[imm], r[ra]))
            self.ram[imm] = r[ra]
        elif m == "MOV":
            r[ra] = r[rb]
        elif m in ("ADD", "SUB", "MUL", "CMP"):
            a, b = r[ra], r[rb]
            result = {"ADD": a + b, "SUB": a - b,
                      "MUL": a * b, "CMP": a - b}[m] & 0xFF
            self._set_flags(result)
            if m != "CMP":                       # CMP only sets flags
                r[ra] = result
        elif m == "INC":
            r[ra] = (r[ra] + 1) & 0xFF
            self._set_flags(r[ra])
        elif m == "DEC":
            r[ra] = (r[ra] - 1) & 0xFF
            self._set_flags(r[ra])
        elif m == "JMP":
            self.pc = imm
        elif m == "JZ":
            if self.z:
                self.pc = imm
        elif m == "JNZ":
            if not self.z:
                self.pc = imm
        elif m == "HALT":
            self.halted = True
            self.pc = pc                         # PC stays on HALT
        else:                                    # unreachable: table-driven
            raise CPUError("unimplemented opcode %s" % m)

        self.steps += 1
        return StepRecord(self.steps, pc, word, isa.disassemble(word),
                          regs_before, tuple(self.regs), flags_before,
                          (self.z, self.n), self.pc, tuple(writes),
                          bytes(self.ram), self.halted)

    def run(self):
        """Run until HALT; return the list of StepRecords."""
        records = []
        while not self.halted:
            records.append(self.step())
        return records


def main(argv=None):
    parser = argparse.ArgumentParser(description="MiniCPU-8 simulator")
    parser.add_argument("source", help="assembly file (.asm)")
    parser.add_argument("--rows", default="00,10,F0",
                        help="RAM rows to show each step (hex, comma list)")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    args = parser.parse_args(argv)
    try:
        rows = [int(x, 16) & 0xF0 for x in args.rows.split(",")]
        program = assembler.assemble_file(args.source)
        cpu = CPU(max_steps=args.max_steps)
        cpu.load(program.image)
        records = cpu.run()
    except (assembler.AssemblyError, CPUError, OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    print(tracer.format_trace(args.source, program, records, rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
