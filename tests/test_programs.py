"""End-to-end tests: Program A, Program B, saved traces, C reference."""

import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import isa                                              # noqa: E402
import run_demo                                         # noqa: E402
import tracer                                           # noqa: E402
from assembler import assemble_file                    # noqa: E402
from cpu import CPU                                    # noqa: E402

DEMO_A, DEMO_B = run_demo.DEMOS


class TestProgramA(unittest.TestCase):

    def test_square_of_8_is_64(self):
        _, records, value = run_demo.run_program(DEMO_A)
        self.assertEqual(value, 64)
        self.assertEqual(len(records), 5)
        self.assertTrue(records[-1].halted)

    def test_result_label_matches_memory_map(self):
        program = assemble_file(os.path.join(ROOT, DEMO_A.source))
        self.assertEqual(program.labels["result"], isa.RESULT_ADDR)
        self.assertEqual(program.labels["x"], isa.INPUT_ADDR)


class TestProgramB(unittest.TestCase):

    def test_factorial_of_5_is_120(self):
        _, records, value = run_demo.run_program(DEMO_B)
        self.assertEqual(value, 120)
        self.assertEqual(records[-1].ram_after[isa.VAR_ADDR], 1)    # i
        self.assertEqual(records[-1].ram_after[isa.INPUT_ADDR], 5)  # n
        self.assertEqual(len(records), 36)

    def test_factorial_for_every_n_1_to_5(self):
        program = assemble_file(os.path.join(ROOT, DEMO_B.source))
        for n in range(1, 6):
            with self.subTest(n=n):
                image = bytearray(program.image)
                image[isa.INPUT_ADDR] = n
                cpu = CPU()
                cpu.load(image)
                cpu.run()
                self.assertEqual(cpu.ram[isa.RESULT_ADDR], math.factorial(n))

    def test_labels_match_memory_map(self):
        program = assemble_file(os.path.join(ROOT, DEMO_B.source))
        self.assertEqual(program.labels["result"], isa.RESULT_ADDR)
        self.assertEqual(program.labels["n"], isa.INPUT_ADDR)
        self.assertEqual(program.labels["i"], isa.VAR_ADDR)

    def test_c_reference_prints_120(self):
        """Optional: compile factorial.c natively; skip if no compiler."""
        compiler = shutil.which("cc") or shutil.which("gcc")
        if not compiler:
            self.skipTest("no C compiler found (optional cross-check)")
        with tempfile.TemporaryDirectory() as tmp:
            exe = os.path.join(tmp, "factorial")
            try:
                build = subprocess.run(
                    [compiler, os.path.join(ROOT, "programs", "factorial.c"),
                     "-o", exe], capture_output=True, timeout=60)
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.skipTest("C compiler not usable: %s" % exc)
            if build.returncode != 0:
                self.skipTest("C compiler not usable (exit %d)"
                              % build.returncode)
            out = subprocess.run([exe], check=True, capture_output=True,
                                 text=True, timeout=10).stdout
        self.assertEqual(out.strip(), "5! = 120")


class TestSavedTraces(unittest.TestCase):
    """output/*.txt must equal what the simulator produces right now."""

    def test_trace_files_are_current(self):
        for demo in run_demo.DEMOS:
            with self.subTest(trace=demo.trace):
                program, records, value = run_demo.run_program(demo)
                expected = tracer.format_trace(
                    demo.source, program, records, demo.rows,
                    footer=run_demo.final_state(demo, value, True))
                with open(os.path.join(ROOT, demo.trace),
                          encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), expected)

    def test_trace_words_match_assembler_output(self):
        for demo in run_demo.DEMOS:
            program, records, _ = run_demo.run_program(demo)
            for rec in records:
                self.assertEqual(rec.word, (program.image[rec.pc] << 8)
                                 | program.image[rec.pc + 1])


if __name__ == "__main__":
    unittest.main()
