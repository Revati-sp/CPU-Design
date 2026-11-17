#!/usr/bin/env python3
"""
MiniCPU-8 demonstration -- one command runs everything:

    python3 run_demo.py            # full per-instruction traces + PASS/FAIL
    python3 run_demo.py --quiet    # PASS/FAIL summary only

For each program: assemble -> load RAM -> execute until HALT ->
verify RAM[0xF0] -> save the trace to output/<name>_trace.txt.
Exit status 0 only if every program produces its expected result.
"""

import argparse
import sys
from collections import namedtuple
from pathlib import Path

import assembler
import isa
import tracer
from cpu import CPU, CPUError

ROOT = Path(__file__).resolve().parent

Demo = namedtuple("Demo", "key claim source trace rows expected")

DEMOS = (
    Demo("A", "8^2 = 64", "programs/square8.asm",
         "output/square8_trace.txt", (0x00, 0xF0), 64),
    Demo("B", "5! = 120", "programs/factorial.asm",
         "output/factorial_trace.txt", (0x00, 0x10, 0xF0), 120),
)


def final_state(demo, value, passed):
    """The highlighted end-of-trace result block."""
    return "\n".join([
        tracer.RULE,
        "PROGRAM %s -- FINAL STATE" % demo.key,
        "  RESULT ADDRESS : 0x%02X" % isa.RESULT_ADDR,
        "  RAM[0x%02X]      : 0x%02X" % (isa.RESULT_ADDR, value),
        "  DECIMAL        : %d" % value,
        "  EXPECTED       : %d   (%s)" % (demo.expected, demo.claim),
        "  STATUS         : %s" % ("PASS" if passed else "FAIL"),
        tracer.RULE,
    ])


def run_program(demo):
    """Assemble + execute one demo. Returns (program, records, value)."""
    program = assembler.assemble_file(ROOT / demo.source)
    if program.labels.get("result") != isa.RESULT_ADDR:
        raise CPUError("%s: label 'result' must be at 0x%02X"
                       % (demo.source, isa.RESULT_ADDR))
    cpu = CPU()
    cpu.load(program.image)
    records = cpu.run()
    return program, records, cpu.ram[isa.RESULT_ADDR]


def run_demo(demo, quiet=False):
    """Run, verify and save the trace; return the PASS/FAIL summary line."""
    try:
        program, records, value = run_program(demo)
    except (assembler.AssemblyError, CPUError, OSError) as exc:
        return "[FAIL] Program %s: %s   error: %s" % (demo.key, demo.claim,
                                                      exc)

    passed = value == demo.expected
    text = tracer.format_trace(demo.source, program, records, demo.rows,
                               footer=final_state(demo, value, passed))
    out_path = ROOT / demo.trace
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    if not quiet:
        print(text)
    return ("[%s] Program %s: %-9s  RAM[0x%02X] = 0x%02X = %3d  %2d steps  %s"
            % ("PASS" if passed else "FAIL", demo.key, demo.claim,
               isa.RESULT_ADDR, value, value, len(records), demo.trace))


def main(argv=None):
    parser = argparse.ArgumentParser(description="MiniCPU-8 demonstration")
    parser.add_argument("--quiet", action="store_true",
                        help="print only PASS/FAIL lines (traces still saved)")
    args = parser.parse_args(argv)

    lines = [run_demo(demo, args.quiet) for demo in DEMOS]
    failures = sum(line.startswith("[FAIL]") for line in lines)
    print("\nSUMMARY")
    print("\n".join(lines))
    if failures:
        print("[FAIL] %d of %d demonstrations failed."
              % (failures, len(lines)))
        return 1
    print("[PASS] All MiniCPU-8 demonstrations completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
