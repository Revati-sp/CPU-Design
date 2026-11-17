"""Documentation tests: README tables must agree with isa.py."""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import isa                                              # noqa: E402
import run_demo                                         # noqa: E402


def readme_isa_rows():
    """Parse README rows: | `MNEMONIC` | 0xN | operands | `bits` | ..."""
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
        text = handle.read()
    pattern = re.compile(r"^\|\s*`(\w+)`\s*\|\s*0x([0-9A-F])\s*\|[^|]*\|"
                         r"\s*`([01a-z ]+)`\s*\|", re.MULTILINE)
    return {m.group(1): (int(m.group(2), 16), m.group(3))
            for m in pattern.finditer(text)}


class TestReadme(unittest.TestCase):

    def test_readme_isa_table_matches_isa(self):
        rows = readme_isa_rows()
        self.assertEqual(set(rows), set(isa.BY_MNEMONIC))
        for op in isa.INSTRUCTIONS:
            with self.subTest(op=op.mnemonic):
                self.assertEqual(rows[op.mnemonic],
                                 (op.opcode, isa.encoding_pattern(op)))

    def test_readme_expected_output_is_real(self):
        """The Quick Start 'expected ending' equals real run_demo output."""
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as h:
            readme = h.read()
        for demo in run_demo.DEMOS:
            line = run_demo.run_demo(demo, quiet=True)
            self.assertTrue(line.startswith("[PASS]"))
            self.assertIn(line, readme)
        self.assertIn("[PASS] All MiniCPU-8 demonstrations completed "
                      "successfully.", readme)


if __name__ == "__main__":
    unittest.main()
