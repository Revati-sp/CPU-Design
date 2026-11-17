"""Assembler tests: parsing, labels, encoding, directives, error reporting."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import isa                                              # noqa: E402
from assembler import AssemblyError, assemble          # noqa: E402


def words(source):
    """Assemble and return the list of instruction words."""
    program = assemble(source)
    return [(e.data[0] << 8) | e.data[1] for e in program.instructions()]


class TestEncoding(unittest.TestCase):
    """Hand-computed words prove the documented bit layout."""

    EXPECTED = {
        "NOP":              0x0000,   # 0000 00 00 00000000
        "LDI R3, 0xFF":     0x1CFF,   # 0001 11 00 11111111
        "LOAD R1, [0xF1]":  0x24F1,   # 0010 01 00 11110001
        "STORE R2, [0x80]": 0x3880,   # 0011 10 00 10000000
        "MOV R1, R0":       0x4400,   # 0100 01 00 00000000
        "ADD R1, R2":       0x5600,   # 0101 01 10 00000000
        "SUB R3, R1":       0x6D00,   # 0110 11 01 00000000
        "MUL R0, R1":       0x7100,   # 0111 00 01 00000000
        "INC R3":           0x8C00,   # 1000 11 00 00000000
        "DEC R1":           0x9400,   # 1001 01 00 00000000
        "CMP R0, R3":       0xA300,   # 1010 00 11 00000000
        "JMP 0x0A":         0xB00A,   # 1011 00 00 00001010
        "JZ 0x18":          0xC018,   # 1100 00 00 00011000
        "JNZ 0x02":         0xD002,   # 1101 00 00 00000010
        "HALT":             0xF000,   # 1111 00 00 00000000
    }

    def test_every_instruction_encoding(self):
        for text, expected in self.EXPECTED.items():
            with self.subTest(text=text):
                self.assertEqual(words(text), [expected])

    def test_expected_table_covers_whole_isa(self):
        covered = {t.split()[0] for t in self.EXPECTED}
        self.assertEqual(covered, set(isa.BY_MNEMONIC))

    def test_opcode_in_top_nibble(self):
        for op in isa.INSTRUCTIONS:
            self.assertEqual(isa.encode(op.mnemonic) >> 12, op.opcode)

    def test_case_insensitive_mnemonics_and_registers(self):
        self.assertEqual(words("add r1, r2"), words("ADD R1, R2"))

    def test_number_formats(self):
        self.assertEqual(words("LDI R0, 10\nLDI R0, 0x0A\nLDI R0, 0b1010"),
                         [0x100A] * 3)
        self.assertEqual(words("LDI R0, -1"), [0x10FF])   # two's complement


class TestSyntax(unittest.TestCase):

    def test_comments_and_blank_lines_ignored(self):
        src = "; header comment\n\n   NOP   ; trailing comment\n\nHALT\n"
        self.assertEqual(words(src), [0x0000, 0xF000])

    def test_forward_and_backward_labels(self):
        src = ("start: JZ end\n"       # forward reference
               "       JMP start\n"     # backward reference
               "end:   HALT\n")
        program = assemble(src)
        self.assertEqual(program.labels, {"start": 0x00, "end": 0x04})
        self.assertEqual(words(src), [0xC004, 0xB000, 0xF000])

    def test_label_on_own_line(self):
        program = assemble("NOP\nhere:\n  HALT\n")
        self.assertEqual(program.labels["here"], 0x02)

    def test_label_as_memory_operand(self):
        src = "LOAD R0, [val]\nHALT\n.org 0xF1\nval: .byte 8\n"
        self.assertEqual(words(src), [0x20F1, 0xF000])

    def test_org_and_byte_place_data(self):
        program = assemble(".org 0xF0\n.byte 1, 0x22, 0b11, -2\n")
        self.assertEqual(bytes(program.image[0xF0:0xF4]),
                         bytes([1, 0x22, 3, 0xFE]))

    def test_image_is_big_endian(self):
        program = assemble("LDI R3, 0xFF\n")
        self.assertEqual(program.image[0], 0x1C)
        self.assertEqual(program.image[1], 0xFF)

    def test_deterministic_output(self):
        src = "loop: DEC R1\nJNZ loop\nHALT\n"
        self.assertEqual(assemble(src).image, assemble(src).image)


class TestErrors(unittest.TestCase):

    def assert_error(self, source, fragment, line_no):
        with self.assertRaises(AssemblyError) as ctx:
            assemble(source)
        self.assertIn(fragment, str(ctx.exception))
        self.assertEqual(ctx.exception.line_no, line_no)

    def test_unknown_mnemonic(self):
        self.assert_error("NOP\nMOVE R1, R0\n", "unknown mnemonic", 2)

    def test_invalid_register(self):
        self.assert_error("ADD R1, R4\n", "invalid register", 1)

    def test_undefined_label(self):
        self.assert_error("NOP\nNOP\nJMP nowhere\n", "undefined label", 3)

    def test_duplicate_label(self):
        self.assert_error("a: NOP\na: NOP\n", "duplicate label", 2)

    def test_reserved_word_label(self):
        self.assert_error("r1: NOP\n", "reserved word", 1)

    def test_wrong_operand_count(self):
        self.assert_error("ADD R1\n", "expects 2 operand", 1)

    def test_memory_operand_needs_brackets(self):
        self.assert_error("LOAD R0, 0xF0\n", "brackets", 1)

    def test_immediate_out_of_range(self):
        self.assert_error("LDI R0, 256\n", "out of range", 1)

    def test_instruction_at_odd_address(self):
        self.assert_error(".byte 1\nNOP\n", "odd address", 2)

    def test_overlapping_code(self):
        self.assert_error("NOP\n.org 0x00\nHALT\n", "already used", 3)

    def test_program_too_large(self):
        self.assert_error(".org 0xFF\n.byte 1, 2\n", "does not fit", 2)

    def test_unknown_directive(self):
        self.assert_error(".word 5\n", "unknown directive", 1)

    def test_error_message_has_file_and_line(self):
        with self.assertRaises(AssemblyError) as ctx:
            assemble("NOP\nBAD\n", filename="demo.asm")
        self.assertTrue(str(ctx.exception).startswith("demo.asm:2: error:"))


if __name__ == "__main__":
    unittest.main()
