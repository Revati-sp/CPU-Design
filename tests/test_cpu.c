/*
 * test_cpu.c -- automated checks for the MiniCPU-8 simulator.
 *
 *   make test        (builds and runs this file)
 *
 * Each CHECK prints nothing when it passes and one line when it fails.
 * The program prints a summary and returns 0 only if every check passed.
 */
#include <stdio.h>
#include "../src/machine.h"
#include "../src/programs.h"

static int checks = 0, failures = 0;

#define CHECK(cond, what)                                              \
    do {                                                               \
        checks++;                                                      \
        if (!(cond)) {                                                 \
            failures++;                                                \
            printf("  FAIL line %d: %s\n", __LINE__, what);            \
        }                                                              \
    } while (0)

/* A small machine that tests can load words into and run. */
typedef struct {
    RAM ram;
    Bus bus;
    CPU cpu;
} Machine;

static void machine_load(Machine *m, const u16 *code, int n)
{
    int i;
    ram_clear(&m->ram);
    bus_init(&m->bus, &m->ram);
    for (i = 0; i < n; i++) {
        m->ram.cell[2 * i]     = (u8)(code[i] >> 8);
        m->ram.cell[2 * i + 1] = (u8)(code[i] & 0xFF);
    }
    cpu_reset(&m->cpu, &m->bus);
}

/* Run until HALT/fault or 4000 cycles. Returns cycles used. */
static unsigned long machine_run(Machine *m)
{
    while (!m->cpu.halted && m->cpu.clock < 4000)
        cpu_clock_tick(&m->cpu);
    return m->cpu.clock;
}

/* ---------------------------------------------------------------------- */
static void test_encoding(void)
{
    /* hand-computed words */
    CHECK(WORD(OP_LOAD, R0, 0, 0xF0) == 0x20F0, "LOAD R0,[0xF0] = 0x20F0");
    CHECK(WORD(OP_ADD, R1, R2, 0)    == 0x5600, "ADD R1,R2 = 0x5600");
    CHECK(WORD(OP_HALT, 0, 0, 0)     == 0xF000, "HALT = 0xF000");
    CHECK(OPCODE(0x5600) == OP_ADD && RA(0x5600) == R1 && RB(0x5600) == R2,
          "field extraction");

    /* validity rules */
    CHECK(isa_valid(0x20F0), "LOAD with address is valid");
    CHECK(!isa_valid(0xE000), "opcode 0xE is reserved");
    CHECK(!isa_valid(0xF001), "HALT with imm8 != 0 is invalid");
    CHECK(!isa_valid(0x2100), "LOAD with rb != 0 is invalid");
    CHECK(!isa_valid(0x5101), "ADD with imm8 != 0 is invalid");
    CHECK(!isa_valid(0xB400), "JMP with ra != 0 is invalid");
}

static void test_exhaustive_decode(void)
{
    /* every one of the 65536 words is either valid or rejected,
       and every valid word re-encodes to itself */
    unsigned w;
    int valid = 0, ok = 1;
    for (w = 0; w <= 0xFFFF; w++) {
        if (isa_valid((u16)w)) {
            valid++;
            if (WORD(OPCODE(w), RA(w), RB(w), IMM(w)) != w)
                ok = 0;
        }
    }
    CHECK(ok, "valid words re-encode to themselves");
    /* count: NOP,HALT 1 each; LDI,LOAD,STORE 4*256 each; MOV..MUL,CMP 16 each (5);
       INC,DEC 4 each; JMP,JZ,JNZ 256 each */
    CHECK(valid == 2 + 3 * 1024 + 5 * 16 + 2 * 4 + 3 * 256, "number of valid words");
}

static void test_bus(void)
{
    RAM ram;
    Bus bus;
    ram_clear(&ram);
    bus_init(&bus, &ram);
    bus_write(&bus, 0x80, 0x5A);
    CHECK(ram.cell[0x80] == 0x5A, "bus write reaches RAM");
    CHECK(bus.control == BUS_WRITE && bus.address == 0x80 && bus.data == 0x5A, "bus lines on write");
    CHECK(bus_read(&bus, 0x80) == 0x5A, "bus read returns RAM value");
    CHECK(bus.control == BUS_READ, "bus control on read");
    bus_idle(&bus);
    CHECK(bus.control == BUS_IDLE, "bus idle");
}

static void test_alu(void)
{
    ALU a;
    CHECK(alu_compute(&a, ALU_ADD, 200, 100) == 44, "ADD wraps mod 256");
    CHECK(alu_compute(&a, ALU_SUB, 5, 5) == 0 && a.z == 1 && a.n == 0, "SUB to zero sets Z");
    CHECK(alu_compute(&a, ALU_SUB, 3, 5) == 254 && a.z == 0 && a.n == 1, "SUB below zero sets N");
    CHECK(alu_compute(&a, ALU_MUL, 16, 17) == 16, "MUL keeps low 8 bits");
    CHECK(alu_compute(&a, ALU_INC, 255, 0) == 0 && a.z == 1, "INC 255 -> 0");
    CHECK(alu_compute(&a, ALU_DEC, 0, 0) == 255 && a.n == 1, "DEC 0 -> 255");
}

static void test_clock_cycles(void)
{
    Machine m;
    u16 prog[] = { WORD(OP_LDI, R0, 0, 7), WORD(OP_HALT, 0, 0, 0) };
    machine_load(&m, prog, 2);

    CHECK(cpu_clock_tick(&m.cpu) == PHASE_FETCH_HI && m.cpu.ir == 0x1000 && m.cpu.pc == 1,
          "cycle 1 fetches high byte");
    CHECK(cpu_clock_tick(&m.cpu) == PHASE_FETCH_LO && m.cpu.ir == 0x1007 && m.cpu.pc == 2,
          "cycle 2 fetches low byte");
    CHECK(cpu_clock_tick(&m.cpu) == PHASE_DECODE && m.cpu.opcode == OP_LDI && m.cpu.imm == 7,
          "cycle 3 decodes");
    CHECK(m.cpu.r[0] == 0, "register unchanged before execute");
    CHECK(cpu_clock_tick(&m.cpu) == PHASE_EXECUTE && m.cpu.r[0] == 7, "cycle 4 executes");
    CHECK(machine_run(&m) == 8, "two instructions take 8 cycles");
    CHECK(m.cpu.halted && m.cpu.pc == 2, "HALT stops with PC on HALT");
}

static void test_instructions(void)
{
    Machine m;
    u16 prog[] = {
        WORD(OP_LDI,   R0, 0,  10),     /* 00 R0 = 10           */
        WORD(OP_LDI,   R1, 0,  3),      /* 02 R1 = 3            */
        WORD(OP_MOV,   R2, R0, 0),      /* 04 R2 = 10           */
        WORD(OP_SUB,   R2, R1, 0),      /* 06 R2 = 7            */
        WORD(OP_INC,   R3, 0,  0),      /* 08 R3 = 1            */
        WORD(OP_DEC,   R3, 0,  0),      /* 0A R3 = 0, Z = 1     */
        WORD(OP_STORE, R2, 0,  0x90),   /* 0C RAM[0x90] = 7     */
        WORD(OP_LOAD,  R3, 0,  0x90),   /* 0E R3 = 7            */
        WORD(OP_NOP,   0,  0,  0),      /* 10                   */
        WORD(OP_HALT,  0,  0,  0),      /* 12                   */
    };
    machine_load(&m, prog, 10);
    machine_run(&m);
    CHECK(m.cpu.fault == FAULT_NONE, "no fault");
    CHECK(m.cpu.r[0] == 10 && m.cpu.r[1] == 3, "LDI");
    CHECK(m.cpu.r[2] == 7, "MOV + SUB");
    CHECK(m.ram.cell[0x90] == 7, "STORE");
    CHECK(m.cpu.r[3] == 7, "INC, DEC, LOAD");
    CHECK(m.cpu.z == 1, "flags unchanged by LOAD/STORE/NOP (Z from DEC)");
}

static void test_branches(void)
{
    /* count R0 down from 3 with a loop; R1 counts iterations */
    Machine m;
    u16 prog[] = {
        WORD(OP_LDI, R0, 0, 3),         /* 00                        */
        WORD(OP_LDI, R2, 0, 0),         /* 02 R2 = 0 (for CMP)       */
        WORD(OP_INC, R1, 0, 0),         /* 04 loop: R1++             */
        WORD(OP_DEC, R0, 0, 0),         /* 06 R0--                   */
        WORD(OP_JNZ, 0,  0, 0x04),      /* 08 repeat while R0 != 0   */
        WORD(OP_CMP, R0, R2, 0),        /* 0A R0 == 0 -> Z = 1       */
        WORD(OP_JZ,  0,  0, 0x10),      /* 0C taken                  */
        WORD(OP_LDI, R3, 0, 99),        /* 0E skipped                */
        WORD(OP_JMP, 0,  0, 0x14),      /* 10                        */
        WORD(OP_LDI, R3, 0, 98),        /* 12 skipped                */
        WORD(OP_HALT, 0, 0, 0),         /* 14                        */
    };
    machine_load(&m, prog, 11);
    machine_run(&m);
    CHECK(m.cpu.r[1] == 3, "JNZ loops 3 times");
    CHECK(m.cpu.r[0] == 0 && m.cpu.r[2] == 0, "CMP leaves registers unchanged");
    CHECK(m.cpu.r[3] == 0, "JZ and JMP skip code");
    CHECK(m.cpu.halted && m.cpu.pc == 0x14, "halts at 0x14");
}

static void test_faults(void)
{
    Machine m;
    u16 bad_op[]   = { 0xE000 };
    u16 bad_bits[] = { 0xF0FF };
    u16 bad_pc[]   = { WORD(OP_JMP, 0, 0, 0x03) };
    u16 loop[]     = { WORD(OP_JMP, 0, 0, 0x00) };

    machine_load(&m, bad_op, 1);   machine_run(&m);
    CHECK(m.cpu.fault == FAULT_BAD_OPCODE, "reserved opcode faults");
    machine_load(&m, bad_bits, 1); machine_run(&m);
    CHECK(m.cpu.fault == FAULT_RESERVED_BITS, "non-zero unused field faults");
    machine_load(&m, bad_pc, 1);   machine_run(&m);
    CHECK(m.cpu.fault == FAULT_BAD_PC, "odd PC faults");
    machine_load(&m, loop, 1);     machine_run(&m);
    CHECK(!m.cpu.halted, "infinite loop never halts (main.c stops it)");
}

static void test_flags_and_branches_on_cpu(void)
{
    Machine m;
    u16 prog[] = {
        WORD(OP_LDI, R0, 0, 200),       /* 00                                */
        WORD(OP_LDI, R1, 0, 100),       /* 02                                */
        WORD(OP_ADD, R0, R1, 0),        /* 04 200+100 = 44, Z=0 N=0          */
        WORD(OP_JZ,  0,  0, 0x0E),      /* 06 not taken (Z = 0)              */
        WORD(OP_LDI, R3, 0, 1),         /* 08 runs: proves JZ fell through   */
        WORD(OP_CMP, R3, R1, 0),        /* 0A 1-100 -> Z=0 N=1, R3 unchanged */
        WORD(OP_HALT, 0, 0, 0),         /* 0C                                */
        WORD(OP_HALT, 0, 0, 0),         /* 0E                                */
    };
    machine_load(&m, prog, 8);
    machine_run(&m);
    CHECK(m.cpu.r[0] == 44, "ADD on the CPU wraps mod 256");
    CHECK(m.cpu.r[3] == 1 && m.cpu.pc == 0x0C, "JZ not taken when Z = 0");
    CHECK(m.cpu.z == 0 && m.cpu.n == 1, "CMP unequal: Z = 0, N = 1");
    CHECK(m.cpu.r[3] == 1 && m.cpu.r[1] == 100, "CMP does not change registers");
}

static void test_flags_unchanged(void)
{
    /* SUB sets Z = 1, then LDI and MOV must leave the flags alone */
    Machine m;
    u16 prog[] = {
        WORD(OP_SUB, R0, R0, 0),        /* 0 - 0 = 0 -> Z = 1 */
        WORD(OP_LDI, R1, 0, 0x80),      /* bit 7 set, no flag change */
        WORD(OP_MOV, R2, R1, 0),
        WORD(OP_HALT, 0, 0, 0),
    };
    machine_load(&m, prog, 4);
    machine_run(&m);
    CHECK(m.cpu.z == 1 && m.cpu.n == 0, "LDI and MOV leave Z and N unchanged");
    CHECK(m.cpu.r[2] == 0x80, "MOV copies the value");
}

static void test_mar_mdr_and_bus(void)
{
    Machine m;
    u16 prog[] = {
        WORD(OP_LDI,   R0, 0, 0x5A),
        WORD(OP_STORE, R0, 0, 0xA0),
        WORD(OP_LOAD,  R1, 0, 0xA0),
        WORD(OP_HALT,  0,  0, 0),
    };
    int i;
    machine_load(&m, prog, 4);
    for (i = 0; i < 8; i++)                 /* run LDI and STORE (8 cycles) */
        cpu_clock_tick(&m.cpu);
    CHECK(m.cpu.mar == 0xA0 && m.cpu.mdr == 0x5A, "STORE sets MAR and MDR");
    CHECK(m.bus.control == BUS_WRITE && m.bus.address == 0xA0 && m.bus.data == 0x5A,
          "STORE drives a bus WRITE");
    for (i = 0; i < 4; i++)                 /* run LOAD */
        cpu_clock_tick(&m.cpu);
    CHECK(m.cpu.mar == 0xA0 && m.cpu.mdr == 0x5A && m.cpu.r[1] == 0x5A, "LOAD via MAR/MDR");
    CHECK(m.bus.control == BUS_READ && m.bus.address == 0xA0, "LOAD drives a bus READ");
}

static void test_fault_details(void)
{
    Machine m;
    u16 bad_ra[] = { WORD(OP_LDI, R2, 0, 9), 0xF400 };   /* HALT with ra = 01 */
    u16 bad_rb[] = { 0x8100 };                          /* INC with rb = 01  */

    machine_load(&m, bad_ra, 2);
    machine_run(&m);
    CHECK(m.cpu.fault == FAULT_RESERVED_BITS, "non-zero ra on HALT faults");
    CHECK(m.cpu.r[2] == 9 && m.cpu.pc == 4, "state kept after a fault");
    machine_load(&m, bad_rb, 1);
    machine_run(&m);
    CHECK(m.cpu.fault == FAULT_RESERVED_BITS, "non-zero rb on INC faults");
    CHECK(m.cpu.r[0] == 0, "faulting instruction does not execute");
}

static void test_program(const Program *p)
{
    RAM ram;
    Bus bus;
    CPU cpu;
    bus_init(&bus, &ram);
    program_load(p, &bus);
    cpu_reset(&cpu, &bus);
    while (!cpu.halted && cpu.clock < 4000)
        cpu_clock_tick(&cpu);
    CHECK(cpu.fault == FAULT_NONE, p->title);
    CHECK(ram.cell[p->result_addr] == p->expected, p->title);
    CHECK(cpu.clock == (unsigned long)p->code_len * CYCLES_PER_INSTRUCTION,
          "4 clock cycles per instruction");
}

int main(void)
{
    printf("MiniCPU-8 tests\n");
    test_encoding();
    test_exhaustive_decode();
    test_bus();
    test_alu();
    test_clock_cycles();
    test_instructions();
    test_branches();
    test_faults();
    test_flags_and_branches_on_cpu();
    test_flags_unchanged();
    test_mar_mdr_and_bus();
    test_fault_details();
    test_program(&PROGRAM_ADD);
    test_program(&PROGRAM_MUL);
    printf("%d / %d checks passed\n", checks - failures, checks);
    return failures ? 1 : 0;
}
