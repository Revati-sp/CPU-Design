"""CPU tests: every instruction, flags, memory, branches, HALT, faults."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import isa                                              # noqa: E402
from assembler import assemble                         # noqa: E402
from cpu import CPU, CPUError                          # noqa: E402


def run(source, max_steps=1000):
    """Assemble, run to HALT, return (cpu, records)."""
    cpu = CPU(max_steps=max_steps)
    cpu.load(assemble(source).image)
    return cpu, cpu.run()


class TestDataMovement(unittest.TestCase):

    def test_ldi_and_mov(self):
        cpu, _ = run("LDI R2, 42\nMOV R3, R2\nHALT")
        self.assertEqual(cpu.regs, [0, 0, 42, 42])

    def test_load_and_store(self):
        cpu, recs = run("LOAD R1, [v]\nSTORE R1, [0x80]\nHALT\n"
                        ".org 0xF1\nv: .byte 0x5A")
        self.assertEqual(cpu.regs[1], 0x5A)
        self.assertEqual(cpu.ram[0x80], 0x5A)
        self.assertEqual(recs[1].mem_writes, ((0x80, 0x00, 0x5A),))

    def test_moves_do_not_change_flags(self):
        cpu, _ = run("LDI R0, 0\nLDI R1, 0x80\nMOV R2, R0\nHALT")
        self.assertEqual((cpu.z, cpu.n), (0, 0))


class TestALUAndFlags(unittest.TestCase):

    def test_add_wraps_modulo_256(self):
        cpu, _ = run("LDI R0, 200\nLDI R1, 100\nADD R0, R1\nHALT")
        self.assertEqual(cpu.regs[0], 44)
        self.assertEqual((cpu.z, cpu.n), (0, 0))

    def test_sub_negative_sets_n(self):
        cpu, _ = run("LDI R0, 1\nLDI R1, 2\nSUB R0, R1\nHALT")
        self.assertEqual(cpu.regs[0], 0xFF)
        self.assertEqual((cpu.z, cpu.n), (0, 1))

    def test_mul_keeps_low_8_bits_and_sets_z(self):
        cpu, _ = run("LDI R0, 16\nLDI R1, 16\nMUL R0, R1\nHALT")
        self.assertEqual(cpu.regs[0], 0)
        self.assertEqual((cpu.z, cpu.n), (1, 0))

    def test_inc_wraps_to_zero(self):
        cpu, _ = run("LDI R3, 255\nINC R3\nHALT")
        self.assertEqual(cpu.regs[3], 0)
        self.assertEqual(cpu.z, 1)

    def test_dec_below_zero(self):
        cpu, _ = run("DEC R1\nHALT")
        self.assertEqual(cpu.regs[1], 0xFF)
        self.assertEqual((cpu.z, cpu.n), (0, 1))

    def test_cmp_sets_flags_only(self):
        cpu, _ = run("LDI R0, 7\nLDI R1, 7\nCMP R0, R1\nHALT")
        self.assertEqual(cpu.regs[:2], [7, 7])
        self.assertEqual((cpu.z, cpu.n), (1, 0))


class TestControlFlow(unittest.TestCase):

    def test_pc_advances_by_two(self):
        _, recs = run("NOP\nNOP\nHALT")
        self.assertEqual([r.pc for r in recs], [0x00, 0x02, 0x04])

    def test_jmp(self):
        cpu, _ = run("JMP skip\nLDI R0, 1\nskip: HALT")
        self.assertEqual(cpu.regs[0], 0)

    def test_jz_taken_and_not_taken(self):
        cpu, _ = run("LDI R0, 1\nDEC R0\nJZ a\nLDI R1, 9\na: HALT")
        self.assertEqual(cpu.regs[1], 0)                # taken (Z=1)
        cpu, _ = run("LDI R0, 2\nDEC R0\nJZ b\nLDI R1, 9\nb: HALT")
        self.assertEqual(cpu.regs[1], 9)                # not taken

    def test_jnz_loop(self):
        cpu, recs = run("LDI R0, 3\nloop: INC R1\nDEC R0\nJNZ loop\nHALT")
        self.assertEqual(cpu.regs[:2], [0, 3])
        self.assertEqual(len(recs), 1 + 3 * 3 + 1)

    def test_halt_stops_and_holds_pc(self):
        cpu, recs = run("NOP\nHALT\nLDI R0, 5")
        self.assertTrue(cpu.halted)
        self.assertEqual(cpu.pc, 0x02)
        self.assertEqual(cpu.regs[0], 0)
        self.assertTrue(recs[-1].halted)
        with self.assertRaises(CPUError):
            cpu.step()


class TestFaults(unittest.TestCase):

    def load_words(self, *ws):
        cpu = CPU()
        image = bytearray(isa.MEM_SIZE)
        for i, w in enumerate(ws):
            image[2 * i], image[2 * i + 1] = w >> 8, w & 0xFF
        cpu.load(image)
        return cpu

    def test_invalid_opcode(self):
        cpu = self.load_words(0xE000)
        with self.assertRaisesRegex(CPUError, "invalid opcode 0xE"):
            cpu.step()

    def test_reserved_field_non_zero(self):
        cpu = self.load_words(0x5601)            # ADD R1, R2 with imm8 = 1
        with self.assertRaisesRegex(CPUError, "reserved field"):
            cpu.step()

    def test_infinite_loop_guard(self):
        with self.assertRaisesRegex(CPUError, "step limit of 50"):
            run("here: JMP here", max_steps=50)

    def test_bad_image_size(self):
        with self.assertRaises(CPUError):
            CPU().load(bytes(10))


class TestDecoderConsistency(unittest.TestCase):

    def test_all_65536_words(self):
        """decode -> disassemble -> assemble reproduces every valid word."""
        valid = 0
        for word in range(0x10000):
            try:
                d = isa.decode(word)
            except isa.DecodeError:
                continue
            valid += 1
            self.assertEqual(isa.encode(d.op.mnemonic, d.ra, d.rb, d.imm),
                             word)
            image = assemble(isa.disassemble(word)).image
            self.assertEqual((image[0] << 8) | image[1], word)
        # NOP,HALT:1 each; INC,DEC:4; MOV..CMP(5):16; LDI,LOAD,STORE:4*256;
        # JMP,JZ,JNZ:256
        self.assertEqual(valid, 2 + 2 * 4 + 5 * 16 + 3 * 1024 + 3 * 256)


if __name__ == "__main__":
    unittest.main()
